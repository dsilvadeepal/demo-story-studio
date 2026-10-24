from fastapi import APIRouter, Depends
from pydantic import Field
from typing import Literal
from sqlalchemy import text
from ..auth import require_owner
from ..db import engine, writer_engine
from ..contracts import QueryRequest
from .contracts import Contract, OwnerContext, Proposal, ReviewEvent
from .repository import create_candidate, get_candidate
from .comparison import compare,record_diff
from .lifecycle import approve,apply,recover,record_review

router=APIRouter(prefix='/api/v1/scenarios',dependencies=[Depends(require_owner)])
OWNER=OwnerContext(owner_id='owner',workspace_id='local')
class PreviewRequest(Contract):
    proposal:Proposal
    key:str=Field(min_length=1,max_length=200)
class ApproveRequest(Contract):
    candidate_id:str
    expected_hash:str
    expected_active_id:str
class ApplyRequest(Contract):
    approval_id:str
    key:str=Field(min_length=1,max_length=200)
class RecoveryRequest(Contract):
    target_id:str
    expected_active_id:str
    key:str=Field(min_length=1,max_length=200)
    confirmed:Literal[True]
class CompareRequest(Contract):
    current_id:str
    candidate_id:str
    query:QueryRequest
    aligned_period:bool=False

@router.post('/preview')
def preview(body:PreviewRequest):
    with writer_engine().begin() as c:return create_candidate(c,OWNER,body.proposal,body.key)
@router.post('/compare')
def comparison(body:CompareRequest):
    with engine().connect() as c:return compare(c,OWNER,body.current_id,body.candidate_id,body.query,body.aligned_period)
class CleanupRequest(Contract):
    keep_id:str|None=None

@router.get('/history')
def history(include_archived:bool=False):
    with engine().connect() as c:
        rows=c.execute(text('SELECT id,archived_at FROM studio_candidates WHERE owner_id=:owner AND workspace_id=:workspace AND (:all OR archived_at IS NULL) ORDER BY revision DESC'),dict(owner=OWNER.owner_id,workspace=OWNER.workspace_id,all=include_archived)).mappings().all()
        return [dict(get_candidate(c,OWNER,row['id']).model_dump(),archived=bool(row['archived_at'])) for row in rows]

@router.post('/history/cleanup')
def cleanup(body:CleanupRequest):
    with writer_engine().begin() as c:
        count=c.scalar(text("SELECT studio_archive_history(:o,:w,'archive',:keep)"),dict(o=OWNER.owner_id,w=OWNER.workspace_id,keep=body.keep_id))
        return {'archived':count}

@router.post('/history/{candidate_id}/restore')
def restore_history(candidate_id:str):
    with writer_engine().begin() as c:
        get_candidate(c,OWNER,candidate_id)
        return {'restored':c.scalar(text("SELECT studio_archive_history(:o,:w,'restore',:id)"),dict(o=OWNER.owner_id,w=OWNER.workspace_id,id=candidate_id))}

@router.get('/{candidate_id}/diff')
def diff(candidate_id:str,cursor:int=0,page_size:int=100,table:str|None=None):
    with engine().connect() as c:return record_diff(c,OWNER,candidate_id,cursor,page_size,table)
@router.post('/{candidate_id}/review')
def review(candidate_id:str,body:ReviewEvent):
    with writer_engine().begin() as c:return record_review(c,OWNER,candidate_id,body)
@router.post('/approve')
def approval(body:ApproveRequest):
    with writer_engine().begin() as c:return approve(c,OWNER,body.candidate_id,body.expected_hash,body.expected_active_id)
@router.post('/apply')
def activation(body:ApplyRequest):
    with writer_engine().begin() as c:return apply(c,OWNER,body.approval_id,body.key)
@router.post('/recover')
def recovery(body:RecoveryRequest):
    with writer_engine().begin() as c:return recover(c,OWNER,body.target_id,body.expected_active_id,body.key)
