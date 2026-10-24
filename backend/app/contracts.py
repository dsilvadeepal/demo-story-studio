from datetime import date
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator
class Period(BaseModel):
    model_config=ConfigDict(extra='forbid')
    start:date
    end:date
    field:Literal['created_at','close_date','closed_date']='created_at'
    @model_validator(mode='after')
    def ordered(self):
        if self.end<self.start: raise ValueError('Period end must follow start')
        return self
class QueryRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    dataset_id:str='baseline-v1-42-2026-10-21'
    semantic_version:Literal['1.0.0']='1.0.0'
    dashboard:Literal['sales','service']
    metric_ids:list[str]=Field(default_factory=list,max_length=15)
    dimension:str|None=None
    filters:dict[str,list[str]]=Field(default_factory=dict)
    period:Period|None=None
class RecordRequest(QueryRequest):
    entity:Literal['opportunities','cases']
    page_size:int=Field(default=25,ge=1,le=100)
    cursor:int=Field(default=0,ge=0,le=100000)
    sort:Literal['name','amount','created_at','close_date','priority','status','id']='id'
    descending:bool=False
