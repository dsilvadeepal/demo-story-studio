from sqlalchemy import text
from .contracts import Candidate, OwnerContext


def get_candidate(c, owner: OwnerContext, candidate_id: str) -> Candidate:
    row = c.execute(text('''SELECT s.id,s.parent_id,s.revision,s.content_hash,d.as_of_date,s.status
        FROM studio_candidates s JOIN datasets d ON d.id=s.id
        WHERE s.id=:id AND s.owner_id=:owner AND s.workspace_id=:workspace'''),
        dict(id=candidate_id, owner=owner.owner_id, workspace=owner.workspace_id)).mappings().first()
    if row is None:
        raise LookupError('Candidate not found in this workspace')
    return Candidate(**row)


def get_active(c, owner: OwnerContext) -> Candidate:
    id = c.execute(text('SELECT dataset_id FROM studio_active WHERE owner_id=:owner AND workspace_id=:workspace'),
        dict(owner=owner.owner_id, workspace=owner.workspace_id)).scalar_one_or_none()
    if id is None:
        raise LookupError('Workspace has not been initialized')
    return get_candidate(c, owner, id)


def canonical(value):
    import json
    from decimal import Decimal
    def encode(v):
        return format(v.normalize(),'f') if isinstance(v,Decimal) else v.isoformat()
    return json.dumps(value,sort_keys=True,separators=(',',':'),default=encode)


def digest(value):
    import hashlib
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def read_bundle(c, owner, candidate_id):
    from sqlalchemy import select
    from ..db import manifest, tables
    get_candidate(c,owner,candidate_id)
    return {'manifest':dict(c.execute(select(manifest).where(manifest.c.id==candidate_id)).mappings().one()),
            'tables':{name:[dict(r) for r in c.execute(select(t).where(t.c.dataset_id==candidate_id).order_by(t.c.id)).mappings()] for name,t in tables.items()}}


def create_candidate(c, owner, proposal, key):
    from uuid import uuid4
    from ..seed import checksum
    from .operations import resolve_selection, transform
    from .validation import validate_candidate
    if not key or len(key)>200: raise ValueError('Invalid idempotency key')
    params=dict(owner=owner.owner_id,workspace=owner.workspace_id,key=key)
    c.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:owner || ':' || :workspace,0))"),params)
    request_hash=digest(proposal.model_dump(mode='json'))
    old=c.execute(text("SELECT request_hash,result FROM studio_receipts WHERE owner_id=:owner AND workspace_id=:workspace AND action='candidate' AND key=:key"),params).mappings().first()
    if old:
        if old['request_hash']!=request_hash: raise ValueError('Idempotency key reused with different request')
        return get_candidate(c,owner,old['result']['id'])
    count=c.scalar(text('SELECT count(*) FROM studio_candidates WHERE owner_id=:owner AND workspace_id=:workspace AND archived_at IS NULL'),params)
    if count>=20: raise ValueError('LIMIT_REACHED: twenty visible revisions retained; clean up revision history')
    parent=read_bundle(c,owner,proposal.parent_id)
    ids=resolve_selection(c,proposal)
    normalized=proposal.model_copy(update={'selection':proposal.selection.model_copy(update={'record_ids':ids,'filters':{},'top_n':None,'period':None})})
    bundle=transform(parent,normalized)
    report=validate_candidate(parent,bundle,normalized)
    revision=c.scalar(text('SELECT coalesce(max(revision),0)+1 FROM studio_candidates WHERE owner_id=:owner AND workspace_id=:workspace'),params)
    id='candidate-'+str(uuid4())
    business={name:[{k:v for k,v in row.items() if k!='dataset_id'} for row in rows] for name,rows in bundle['tables'].items()}
    content_hash=digest({'tables':business,**({'presentation':bundle['manifest']['presentation']} if bundle['manifest'].get('presentation') else {}),'as_of_date':bundle['manifest']['as_of_date'],'semantic_version':proposal.semantic_version,'proposal':normalized.model_dump(mode='json')})
    bundle['manifest'].update(id=id,revision=revision)
    for rows in bundle['tables'].values():
        for row in rows:row['dataset_id']=id
    bundle['manifest']['checksums']={name:checksum(rows) for name,rows in bundle['tables'].items()}
    params.update(bundle=canonical(bundle),hash=content_hash,request_hash=request_hash,
                  proposal=canonical(normalized.model_dump(mode='json')),validation=canonical(report.model_dump()))
    c.execute(text('SELECT studio_publish(:owner,:workspace,CAST(:bundle AS jsonb),:hash,:request_hash,CAST(:proposal AS jsonb),:key,CAST(:validation AS jsonb))'),params)
    return get_candidate(c,owner,id)
