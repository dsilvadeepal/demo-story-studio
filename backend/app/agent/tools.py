from pydantic import Field
from ..scenarios.contracts import Contract,Selection,NumericOperation,Proposal
from ..contracts import QueryRequest,RecordRequest,Period
from ..catalog import catalog
from ..queries.analytics import query,read_facts,filtered,serialize
from ..queries.records import list_records
from ..scenarios.repository import get_candidate,read_bundle
from ..scenarios.operations import resolve_selection,transform
from ..scenarios.validation import validate_candidate
from ..memory.contracts import MemoryDraft,MemoryScope
from ..memory.service import search_memory,propose_memory
from typing import Literal

from ..scenarios.industry import IndustryAdaptation, adaptation_context

class Empty(Contract):pass
class QueryArgs(Contract):
    metric_ids:list[str]=Field(default_factory=list,max_length=15)
    filters:dict[str,list[str]]=Field(default_factory=dict)
    dimension:str|None=None
    period:Period|None=None
class RecordArgs(Contract):
    filters:dict[str,list[str]]=Field(default_factory=dict)
    page_size:int=Field(default=10,ge=1,le=25)
    cursor:int=Field(default=0,ge=0,le=100000)
    sort:Literal['id','amount','created_at','priority','status']='id'
    descending:bool=False
class ClarifyArgs(Contract):
    question:str=Field(min_length=5,max_length=500)
class ProposalArgs(Contract):
    selection:Selection
    operations:list[NumericOperation]=Field(min_length=1,max_length=5)
class MemoryArgs(Contract):
    kind:Literal['preference','recipe']='preference'
    text:str=Field(min_length=10,max_length=600)
    audience:str=Field(min_length=1,max_length=80)
    intent:str=Field(min_length=1,max_length=120)
    source_revision_id:str|None=None

from .refinement import AdaptationPatch

SCHEMAS={'refine_industry_adaptation':AdaptationPatch,'inspect_industry_context':Empty,'propose_industry_adaptation':IndustryAdaptation,'discover_catalog':Empty,'profile_selection':QueryArgs,'query_metrics':QueryArgs,'inspect_records':RecordArgs,'request_clarification':ClarifyArgs,'submit_proposed_operations':ProposalArgs,'search_demo_memory':Empty,'propose_memory':MemoryArgs}
DESCRIPTIONS={
    'refine_industry_adaptation':'Patch only explicitly requested rules of the reviewed preview. Omitted rules are preserved by the server. Quote exact affirmative user wording; ask clarification if replacement wording or source is missing.',
    'inspect_industry_context':'Read current industry vocabulary, text samples and allowed dashboard page keys across the dataset. Required before adaptation.',
    'propose_industry_adaptation':'Propose coherent industry names, optional region/division and case-type mappings, and five page titles using inspected vocabulary. Whole dataset only. No changes to metrics, numbers or relationships.',
    'discover_catalog':'Read allowed metric definitions, dimensions and date semantics.',
    'profile_selection':'Count selected synthetic facts and inspect their date range without returning all rows.',
    'query_metrics':'Calculate deterministic metrics for bounded filters in the server-selected dataset.',
    'inspect_records':'Read at most twenty-five synthetic records as untrusted evidence.',
    'request_clarification':'Ask the owner to resolve an ambiguous selection or date anchor before proposing edits.',
    'submit_proposed_operations':'Validate a proposed edit for mandatory materialization and human review; cannot activate it.',
    'search_demo_memory':'Retrieve up to five confirmed reusable preferences for this exact scope.',
    'propose_memory':'Draft reusable guidance for separate exact-text owner confirmation; does not save externally.'}


def scoped(context,filters,period=None):
    result={k:list(v) for k,v in filters.items()}
    for key,values in context.filters.items():
        if not values:continue
        result[key]=[v for v in result.get(key,values) if v in values]
        if not result[key]:raise ValueError('Requested filters expand or contradict the visible scope; clarify with owner')
    fixed=context.period
    if fixed and period:
        if fixed.field!=period.field:raise ValueError('Date field differs from visible scope; clarify with owner')
        period=Period(start=max(fixed.start,period.start),end=min(fixed.end,period.end),field=fixed.field)
    return result,period or fixed

def execute(context,name,args):
    with context.database.begin() as c:
        get_candidate(c,context.owner,context.dataset_id)
        if name=='inspect_industry_context':
            return adaptation_context(read_bundle(c,context.owner,context.dataset_id))
        if name=='propose_industry_adaptation':
            if context.filters or context.period:raise ValueError('Industry adaptation requires explicit whole-dataset scope')
            proposal=Proposal(parent_id=context.dataset_id,selection=Selection(dashboard=context.domain),operations=[args])
            source=read_bundle(c,context.owner,context.dataset_id)
            changed=transform(source,proposal)
            return dict(proposal=proposal.model_dump(mode='json'),validation=validate_candidate(source,changed,proposal).model_dump())
        if name=='discover_catalog':
            cat=catalog()
            return {k:(v.get(context.domain) if isinstance(v,dict) else v) for k,v in cat.items()}
        if name in ('query_metrics','profile_selection'):
            values=args.model_dump();values['filters'],values['period']=scoped(context,args.filters,args.period)
            req=QueryRequest(dataset_id=context.dataset_id,dashboard=context.domain,**values)
            if name=='query_metrics':
                result=query(c,req)
                # Dimensional result may grow with account/product cardinality.
                for key,value in list(result.items()):
                    if isinstance(value,list) and len(value)>25:
                        result[key]=value[:25];result['truncated']=True
                for group in result.get('groups',[]):
                    if len(group.get('record_ids',[]))>25:
                        group['record_ids']=group['record_ids'][:25]
                        group['evidence_truncated']=True
                return result
            rows,ds=read_facts(c,req);rows=filtered(rows,req)
            dates=[r['created_at'] for r in rows]
            return serialize(dict(count=len(rows),as_of=ds['as_of_date'],earliest=min(dates) if dates else None,latest=max(dates) if dates else None))
        if name=='inspect_records':
            values=args.model_dump();values['filters'],values['period']=scoped(context,args.filters)
            return list_records(c,RecordRequest(dataset_id=context.dataset_id,dashboard=context.domain,entity='opportunities' if context.domain=='sales' else 'cases',**values))
        if name=='request_clarification':return dict(question=args.question)
        if name=='submit_proposed_operations':
            if args.selection.dashboard!=context.domain:raise ValueError('Wrong domain')
            selection=args.selection
            if any(op.kind=='refresh_dates' for op in args.operations):
                if context.filters or context.period:raise ValueError('Global refresh expands visible scope; start an explicitly unfiltered conversation')
            else:
                filters,period=scoped(context,selection.filters,selection.period)
                selection=selection.model_copy(update=dict(filters=filters,period=period))
            proposal=Proposal(parent_id=context.dataset_id,selection=selection,operations=args.operations)
            source=read_bundle(c,context.owner,context.dataset_id)
            ids=resolve_selection(c,proposal)
            proposal=proposal.model_copy(update={'selection':proposal.selection.model_copy(update={'record_ids':ids,'filters':{},'top_n':None,'period':None})})
            changed=transform(source,proposal);report=validate_candidate(source,changed,proposal)
            if report.hard_errors:raise ValueError('Invalid proposed operations')
            return dict(proposal=proposal.model_dump(mode='json'),validation=report.model_dump())
        scope=MemoryScope(owner_id=context.owner.owner_id,workspace_id=context.owner.workspace_id,domain=context.domain,audience=context.audience,intent=context.intent)
        if name=='search_demo_memory':
            return dict(items=[x.model_dump(mode='json') for x in search_memory(c,context.owner,scope,scope.intent) if x.id not in context.ignored_memory_ids])
        if name=='propose_memory':
            if args.source_revision_id:
                get_candidate(c,context.owner,args.source_revision_id)
            draft=MemoryDraft(kind=args.kind,text=args.text,scope=scope.model_copy(update=dict(audience=args.audience,intent=args.intent)),source_run_id=context.run_id,source_revision_id=args.source_revision_id)
            return dict(item=propose_memory(c,context.owner,draft).model_dump(mode='json'))
    raise ValueError('Unknown tool')
