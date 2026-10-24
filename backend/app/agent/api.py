from functools import lru_cache
from fastapi import APIRouter,Depends
from pydantic import Field
from ..auth import require_owner
from ..db import writer_engine
from ..scenarios.api import OWNER
from ..scenarios.contracts import Contract
from .contracts import RunScope,ResumeInput
from .runner import Runner

router=APIRouter(prefix='/api/v1/runs',dependencies=[Depends(require_owner)])
@lru_cache
def runner():return Runner(writer_engine())
class Start(Contract):
    brief:str=Field(min_length=1,max_length=2000)
    scope:RunScope
    parent_id:str
@router.post('',status_code=202)
def start(body:Start):return runner().start_run(OWNER,body.brief,body.scope.model_dump(),body.parent_id)
@router.get('/{id}')
def status(id:str):return runner().get_run(OWNER,id)
@router.post('/{id}/resume',status_code=202)
def resume(id:str,body:ResumeInput):return runner().resume_run(OWNER,id,body)
@router.post('/{id}/cancel')
def cancel(id:str):return runner().cancel_run(OWNER,id)

class IgnoreMemory(Contract):
    ids:list[str]=Field(min_length=1,max_length=5)
@router.post('/{id}/ignore-memory')
def ignore(id:str,body:IgnoreMemory):return runner().ignore_memory(OWNER,id,body.ids)
