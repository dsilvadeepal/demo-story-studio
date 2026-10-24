from typing import Literal
from pydantic import Field
from ..scenarios.contracts import Contract

class ProviderConfig(Contract):
    provider:Literal['nebius','fireworks']
    model:str=Field(min_length=1,max_length=150)
    max_input_tokens:int=Field(default=8000,ge=1,le=8000)
    max_output_tokens:int=Field(default=1000,ge=1,le=1000)
    timeout_seconds:int=Field(default=30,ge=1,le=60)

class CallReservation(Contract):
    provider:Literal['nebius','fireworks']
    model:str
    input_tokens:int=Field(ge=1,le=8000)
    output_tokens:int=Field(ge=1,le=1000)

class Usage(Contract):
    input_tokens:int=Field(ge=0)
    output_tokens:int=Field(ge=0)

from dataclasses import dataclass,field
from ..contracts import Period
from typing import Any
from ..scenarios.contracts import OwnerContext

@dataclass(frozen=True)
class RunContext:
    owner: OwnerContext
    dataset_id: str
    domain: Literal['sales','service']
    run_id: str
    thread_id: str
    database: Any
    audience: str = 'general'
    intent: str = 'demo preparation'
    ignored_memory_ids: tuple[str,...] = ()
    filters: dict = field(default_factory=dict)
    period: Period | None = None

class ToolObservation(Contract):
    tool: str
    evidence_id: str | None = None
    data: dict = Field(default_factory=dict)
    error: str | None = None

class RunScope(Contract):
    filters:dict[str,list[str]]=Field(default_factory=dict)
    period:Period|None=None
    domain:Literal['sales','service']
    audience:str=Field(default='general',min_length=1,max_length=80)
    intent:str=Field(default='demo preparation',min_length=1,max_length=120)

class ResumeInput(Contract):
    kind:Literal['clarify','refine','finish','retry']
    interrupt_id:str|None=None
    text:str=Field(default='',max_length=2000)

class RunStatus(Contract):
    id:str
    parent_id:str
    status:Literal['queued','running','paused','complete','failed','interrupted','retrying','cancelled']
    version:int
    interrupt_id:str|None=None
    result:dict=Field(default_factory=dict)
