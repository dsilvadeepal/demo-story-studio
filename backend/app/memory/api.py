from typing import Literal
from fastapi import APIRouter,Depends
from ..auth import require_owner
from ..db import engine,writer_engine
from ..scenarios.api import OWNER
from ..scenarios.contracts import Contract
from .contracts import MemoryDraft,MemoryScope
from .service import propose_memory,confirm_memory,save_memory,update_memory,forget_memory,delete_memory,record_outcome,search_memory
from .repository import list_items

router=APIRouter(prefix='/api/v1/memory',dependencies=[Depends(require_owner)])
class Confirm(Contract):
    content_hash:str
class Outcome(Contract):
    revision_id:str
    successful:bool
class Forget(Contract):
    confirmed:Literal[True]

@router.get('')
def listing():
    with engine().connect() as c:return list_items(c,OWNER)
@router.post('/propose')
def propose(body:MemoryDraft):
    with writer_engine().begin() as c:return propose_memory(c,OWNER,body)
@router.post('/outcome')
def outcome(body:Outcome):
    with writer_engine().begin() as c:return record_outcome(c,OWNER,body.revision_id,body.successful)
@router.post('/search')
def search(body:MemoryScope):
    with writer_engine().begin() as c:return search_memory(c,OWNER,body,body.intent)
@router.post('/{id}/confirm')
def confirm(id:str,body:Confirm):
    with writer_engine().begin() as c:return confirm_memory(c,OWNER,id,body.content_hash)
@router.post('/{id}/save')
def save(id:str):return save_memory(writer_engine(),OWNER,id)
@router.put('/{id}')
def update(id:str,body:MemoryDraft):
    with writer_engine().begin() as c:return update_memory(c,OWNER,id,body)
@router.post('/{id}/forget')
def forget(id:str,body:Forget):
    with writer_engine().begin() as c:forget_memory(c,OWNER,id)
    return delete_memory(writer_engine(),OWNER,id)
