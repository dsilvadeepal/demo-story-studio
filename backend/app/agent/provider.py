"""LangChain adapter plus serialized, durably reserved billable dispatch."""
import os
from sqlalchemy import text
from langchain_openai import ChatOpenAI
from langsmith import tracing_context
from .contracts import CallReservation,Usage
from .budget import reserve_call,settle_call
from .tracing import span
from ..scenarios.repository import canonical
from ..scenarios.lifecycle import ScenarioError

ENDPOINTS={'nebius':'https://api.tokenfactory.nebius.com/v1/','fireworks':'https://api.fireworks.ai/inference/v1/'}
KEYS={'nebius':'NEBIUS_API_KEY','fireworks':'FIREWORKS_API_KEY'}


def build_model(config):
    key=os.getenv(KEYS[config.provider],'')
    if not key or key.startswith('REPLACE_'):raise ScenarioError('BUDGET_UNAVAILABLE','Provider key is not configured')
    return ChatOpenAI(model=config.model,api_key=key,base_url=ENDPOINTS[config.provider],
        max_tokens=config.max_output_tokens,timeout=config.timeout_seconds,max_retries=0,
        temperature=0,stream_usage=False,use_responses_api=False)


def invoke_bounded(database,owner,run_id,config,model,messages):
    serialized=[m.model_dump(mode='json') for m in messages]
    tools=getattr(model,'kwargs',{}).get('tools',[])
    # UTF-8 bytes plus framing allowance is a conservative input-token bound.
    input_bound=len(canonical({'messages':serialized,'tools':tools}).encode())+256
    if input_bound>config.max_input_tokens:raise ScenarioError('LIMIT_REACHED','LIMIT_REACHED: prompt exceeds bounded input')
    request=CallReservation(provider=config.provider,model=config.model,input_tokens=input_bound,output_tokens=config.max_output_tokens)
    with database.connect() as lock:
        # A different lock from budget accounting avoids a cross-connection deadlock.
        locked=lock.scalar(text('SELECT pg_try_advisory_lock(61820261023)'))
        if not locked:raise ScenarioError('BUDGET_UNAVAILABLE','Another billable request is active; retry explicitly')
        try:
            with database.begin() as c:id=reserve_call(c,owner,run_id,request)
            attributes={'provider':config.provider,'model_version':config.model,'prompt_version':'phase2-v1','tool_version':'phase2-v1','input_tokens':input_bound}
            with span(run_id,None,'model',attributes) as span_id:
                try:
                    # External tracing remains off until its own verified spending gate exists.
                    with tracing_context(enabled=False):response=model.invoke(messages)
                except Exception:
                    with database.begin() as c:settle_call(c,id,None)
                    raise ScenarioError('OUTCOME_UNKNOWN','OUTCOME_UNKNOWN: request may have been charged; no automatic retry') from None
                usage=response.usage_metadata
                settled=Usage(input_tokens=usage['input_tokens'],output_tokens=usage['output_tokens']) if usage else None
                with database.begin() as c:
                    settle_call(c,id,settled)
                    cost=c.execute(text('SELECT reserved,actual,status FROM studio_reservations WHERE id=:id'),{'id':id}).mappings().one()
                with span(run_id,span_id,'usage',{'estimated_credit':str(cost['reserved']),'settled_credit':str(cost['actual']) if cost['actual'] is not None else None,'status':cost['status']}):
                    pass
                return response
        finally:
            lock.execute(text('SELECT pg_advisory_unlock(61820261023)'))


def bind_studio_tools(model,tools):
    """Omit redundant schema annotations; validation remains in typed server tools."""
    from langchain_core.utils.function_calling import convert_to_openai_tool
    def compact(value):
        if isinstance(value,dict):return {k:compact(v) for k,v in value.items() if k not in ('title','default')}
        if isinstance(value,list):return [compact(v) for v in value]
        return value
    return model.bind_tools([compact(convert_to_openai_tool(tool)) for tool in tools])


def select_studio_tools(tools,messages):
    """Stage schemas to leave room for evidence under the fixed byte/token ceiling."""
    from langchain_core.messages import ToolMessage
    if any(getattr(m,'type',None)=='system' and 'REFINEMENT_PATCH_MODE' in m.content for m in messages):
        return [t for t in tools if t.name in ('refine_industry_adaptation','request_clarification')]
    if any(isinstance(m,ToolMessage) and m.name in ('inspect_industry_context','propose_industry_adaptation') for m in messages):
        return [t for t in tools if t.name in ('propose_industry_adaptation','request_clarification')]
    inspected=any(isinstance(m,ToolMessage) and m.name in ('discover_catalog','profile_selection','query_metrics','inspect_records','submit_proposed_operations') for m in messages)
    names=({'inspect_records','submit_proposed_operations','request_clarification','propose_memory'} if inspected else
           {'inspect_industry_context','discover_catalog','profile_selection','query_metrics','inspect_records','request_clarification','search_demo_memory'})
    return [t for t in tools if t.name in names]
