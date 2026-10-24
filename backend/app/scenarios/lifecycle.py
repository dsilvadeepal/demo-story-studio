"""Owner-only transitions. Graph state and model output are never approval authority."""
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from .contracts import Approval, Activation, Proposal
from .repository import get_candidate, get_active, read_bundle, digest, canonical
from .validation import validate_candidate
from ..seed import checksum


class ScenarioError(ValueError):
    def __init__(self,code,detail=None):
        self.code=code
        super().__init__(detail or code)


def verify(c,owner,candidate_id):
    candidate=get_candidate(c,owner,candidate_id)
    if candidate.parent_id is None:return candidate
    bundle=read_bundle(c,owner,candidate_id)
    parent=read_bundle(c,owner,candidate.parent_id)
    raw=c.scalar(text('SELECT proposal FROM studio_candidates WHERE id=:id'),{'id':candidate_id})
    proposal=Proposal.model_validate(raw)
    report=validate_candidate(parent,bundle,proposal)
    business={name:[{k:v for k,v in row.items() if k!='dataset_id'} for row in rows] for name,rows in bundle['tables'].items()}
    actual=digest({'tables':business,**({'presentation':bundle['manifest']['presentation']} if bundle['manifest'].get('presentation') else {}),'as_of_date':bundle['manifest']['as_of_date'],'semantic_version':proposal.semantic_version,'proposal':proposal.model_dump(mode='json')})
    if report.hard_errors or actual!=candidate.content_hash or any(checksum(rows)!=bundle['manifest']['checksums'][name] for name,rows in bundle['tables'].items()):
        raise ScenarioError('VALIDATION_FAILED','VALIDATION_FAILED: revision integrity differs; create a fresh preview')
    return candidate


def transition(c,owner,action,payload):
    payload=dict(payload,id=str(uuid4()))
    try:
        with c.begin_nested():
            return c.scalar(text('SELECT studio_lifecycle(:owner,:workspace,:action,CAST(:payload AS jsonb))'),dict(owner=owner.owner_id,workspace=owner.workspace_id,action=action,payload=canonical(payload)))
    except DBAPIError as error:
        message=str(error.orig)
        code=next((code for code in ['STALE_VERSION','APPROVAL_REQUIRED','VALIDATION_FAILED','INVALID_SCOPE','UNSUPPORTED_OPERATION'] if code in message),'VALIDATION_FAILED')
        raise ScenarioError(code) from None


def record_review(c,owner,candidate_id,event):
    get_candidate(c,owner,candidate_id)
    if event.actor!=owner.owner_id:raise ScenarioError('INVALID_SCOPE')
    return transition(c,owner,'review',dict(candidate_id=candidate_id,event=event.model_dump()))


def approve(c,owner,candidate_id,expected_hash,expected_active_id):
    c.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:o || ':' || :w,0))"),dict(o=owner.owner_id,w=owner.workspace_id))
    if c.scalar(text('SELECT archived_at IS NOT NULL FROM studio_candidates WHERE id=:id AND owner_id=:o AND workspace_id=:w'),dict(id=candidate_id,o=owner.owner_id,w=owner.workspace_id)):
        raise ScenarioError('ARCHIVED_REVISION','Return this revision to history before approving it')
    candidate=verify(c,owner,candidate_id)
    if candidate.content_hash!=expected_hash or get_active(c,owner).id!=expected_active_id:raise ScenarioError('STALE_VERSION')
    return Approval(**transition(c,owner,'approve',dict(candidate_id=candidate_id,content_hash=expected_hash,expected_active_id=expected_active_id)))


def apply(c,owner,approval_id,key):
    old=c.scalar(text("SELECT result FROM studio_receipts WHERE owner_id=:owner AND workspace_id=:workspace AND action='apply' AND key=:key"),dict(owner=owner.owner_id,workspace=owner.workspace_id,key=key))
    if old:
        receipt_hash=c.scalar(text("SELECT request_hash FROM studio_receipts WHERE owner_id=:owner AND workspace_id=:workspace AND action='apply' AND key=:key"),dict(owner=owner.owner_id,workspace=owner.workspace_id,key=key))
        if receipt_hash!=approval_id:raise ScenarioError('INVALID_SCOPE')
        return Activation(**old)
    row=c.execute(text('SELECT * FROM studio_approvals WHERE id=:id AND owner_id=:owner AND workspace_id=:workspace'),dict(id=approval_id,owner=owner.owner_id,workspace=owner.workspace_id)).mappings().first()
    if not row or not row['valid']:raise ScenarioError('APPROVAL_REQUIRED')
    verify(c,owner,row['candidate_id'])
    return Activation(**transition(c,owner,'apply',dict(approval_id=approval_id,key=key)))


def recover(c,owner,target_id,expected_active_id,key):
    verify(c,owner,target_id)
    return Activation(**transition(c,owner,'recover',dict(target_id=target_id,expected_active_id=expected_active_id,key=key)))
