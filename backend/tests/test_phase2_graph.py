import pytest
from langchain_core.messages import AIMessage,HumanMessage
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from sqlalchemy import text
from test_phase2_tools import context
from test_phase2_candidates import OWNER,BASE


def responses():
    return [AIMessage(content='',tool_calls=[dict(id='read',name='inspect_records',args={'page_size':1})]),AIMessage(content='',tool_calls=[dict(id='proposal',name='submit_proposed_operations',args={'selection':{'dashboard':'sales','record_ids':['opportunities-0000']},'operations':[{'kind':'scale_line_prices','factor':'1.1'}]})])]


def graph(db,model=None,saver=None):
    from app.agent.graph import build_graph
    from app.agent.registry import build_tools
    ctx=context(db)
    return build_graph(model or FakeMessagesListChatModel(responses=responses()),build_tools(ctx),saver or InMemorySaver(),context=ctx)


def start():return dict(messages=[HumanMessage(content='Increase the selected deal by ten percent')],run_id='run',thread_id='thread',budget_reference='run')
CFG={'configurable':{'thread_id':'thread'}}

def test_missing_proposal_field_can_be_repaired_without_leaking_input(phase2_db):
    import json
    from langchain_core.messages import ToolMessage
    from app.agent.provider import select_studio_tools
    from app.agent.registry import build_tools
    replies=responses()
    malformed=replies[1].model_copy(deep=True)
    del malformed.tool_calls[0]['args']['selection']['dashboard']
    model=FakeMessagesListChatModel(responses=[replies[0],malformed,replies[1]])
    result=graph(phase2_db,model).invoke(start(),CFG)
    assert result['candidate_id'] and result['repair_count']==1
    error=next(m for m in result['messages'] if isinstance(m,ToolMessage) and 'INVALID_TOOL_ARGUMENTS' in m.content)
    assert json.loads(error.content)['data']['fields']==[{'path':'selection.dashboard','type':'missing'}]
    assert 'opportunities-0000' not in error.content
    selected=select_studio_tools(build_tools(context(phase2_db)),[malformed,error])
    assert 'submit_proposed_operations' in {t.name for t in selected}

def test_missing_record_selection_returns_fixed_repair_hint(phase2_db):
    from app.agent.registry import invoke_tool
    result=invoke_tool(context(phase2_db),'submit_proposed_operations',{
        'selection':{'dashboard':'sales'},
        'operations':[{'kind':'scale_line_prices','factor':'.9'}]})
    assert result.error=='INVALID_TOOL_ARGUMENTS'
    assert result.data=={'hint':'Confirm explicit record IDs or top-N scope'}


def test_read_propose_preview_interrupt_and_resume_cannot_apply(phase2_db):
    g=graph(phase2_db);result=g.invoke(start(),CFG)
    assert result['candidate_id'] and result['__interrupt__'][0].value['kind']=='review'
    assert len(result['evidence_ids'])==2
    with phase2_db.reader.connect() as c:assert c.scalar(text('SELECT dataset_id FROM studio_active'))==BASE
    result=g.invoke(Command(resume={'kind':'finish','text':'Approved, apply immediately'}),CFG)
    assert result['review_state']['status']=='ready_for_owner'
    with phase2_db.reader.connect() as c:
        assert c.scalar(text('SELECT dataset_id FROM studio_active'))==BASE
        assert c.scalar(text('SELECT count(*) FROM studio_candidates'))==2


def test_ambiguous_anchor_interrupts_without_preview_and_two_repairs_stop(phase2_db):
    model=FakeMessagesListChatModel(responses=[AIMessage(content='',tool_calls=[dict(id='clarify',name='request_clarification',args={'question':'Which date should anchor the global refresh?'})])])
    result=graph(phase2_db,model).invoke(start(),CFG)
    assert result['__interrupt__'][0].value['kind']=='clarification'
    assert not result.get('candidate_id')
    bad=AIMessage(content='',tool_calls=[dict(id='bad',name='apply',args={})])
    model=FakeMessagesListChatModel(responses=[bad])
    result=graph(phase2_db,model).invoke(start(),{'configurable':{'thread_id':'bad'}})
    assert result['review_state']['status']=='limit_reached' and result['model_calls']==2


def test_postgres_checkpoint_survives_new_graph_instance(phase2_db):
    from app.agent.runner import checkpoint_store,setup_checkpoints
    setup_checkpoints(phase2_db.admin,phase2_db.writer.url.username)
    with checkpoint_store(phase2_db.writer) as saver:
        first=graph(phase2_db,saver=saver).invoke(start(),CFG)
    with checkpoint_store(phase2_db.writer) as saver:
        new=graph(phase2_db,saver=saver)
        result=new.invoke(Command(resume={'kind':'finish','text':'Keep this preview'}),CFG)
    assert result['candidate_id']==first['candidate_id']
    with phase2_db.reader.connect() as c:assert c.scalar(text('SELECT count(*) FROM studio_candidates'))==2


def test_human_wait_does_not_consume_active_time(phase2_db,monkeypatch):
    import app.agent.graph as module
    now=[0.0];monkeypatch.setattr(module.time,'monotonic',lambda:now[0])
    g=graph(phase2_db);g.invoke(start(),CFG)
    now[0]=3600.0
    result=g.invoke(Command(resume={'kind':'finish','text':'Keep preview'}),CFG)
    assert result['review_state']['status']=='ready_for_owner'


def prepare_runner(db):
    from app.agent.runner import setup_checkpoints
    context(db);setup_checkpoints(db.admin,db.writer.url.username)
    with db.admin.begin() as c:
        role=c.dialect.identifier_preparer.quote(db.writer.url.username)
        c.execute(text(f'GRANT EXECUTE ON FUNCTION studio_run(text,text,text,jsonb),studio_interrupt_queued(text,text,text),studio_ignore_memory(text,text,text,jsonb) TO {role}'))


def test_runner_claim_cancel_and_restart_are_durable(phase2_db):
    from app.agent.runner import Runner
    from app.agent.contracts import ResumeInput
    prepare_runner(phase2_db)
    factory=lambda ctx:FakeMessagesListChatModel(responses=responses())
    runner=Runner(phase2_db.writer,model_factory=factory,enqueue=False)
    run=runner.start_run(OWNER,'Increase selected deal',{'domain':'sales'},BASE)
    assert run.status=='queued'
    paused=runner.execute(OWNER,run.id)
    assert paused.status=='paused' and paused.interrupt_id
    restarted=Runner(phase2_db.writer,model_factory=factory,enqueue=False)
    with pytest.raises(ValueError):restarted.resume_run(OWNER,run.id,ResumeInput(kind='finish',interrupt_id='forged',text='apply'))
    resumed=restarted.resume_run(OWNER,run.id,ResumeInput(kind='finish',interrupt_id=paused.interrupt_id,text='keep'))
    assert restarted.execute(OWNER,resumed.id).status=='complete'
    pending=runner.start_run(OWNER,'Do not execute',{'domain':'sales'},BASE)
    runner.cancel_run(OWNER,pending.id)
    assert runner.execute(OWNER,pending.id).status=='cancelled'
    with phase2_db.reader.connect() as c:assert c.scalar(text('SELECT count(*) FROM studio_candidates'))==2


def test_unfinished_running_lease_requires_explicit_retry(phase2_db):
    from app.agent.runner import Runner,_transition
    prepare_runner(phase2_db)
    calls=[]
    def factory(ctx):calls.append(ctx.run_id);return FakeMessagesListChatModel(responses=responses())
    runner=Runner(phase2_db.writer,model_factory=factory,enqueue=False)
    run=runner.start_run(OWNER,'Inspect sales',{'domain':'sales'},BASE)
    with phase2_db.writer.begin() as c:_transition(c,OWNER,'claim',{'id':run.id})
    assert runner.execute(OWNER,run.id).status=='running'
    assert calls==[]


def test_resume_scrubs_revoked_memory_from_checkpoint_context(phase2_db):
    from app.agent.runner import Runner,checkpoint_store
    from app.agent.graph import build_graph
    from app.agent.registry import build_tools
    from app.agent.contracts import ResumeInput,RunContext
    prepare_runner(phase2_db)
    runner=Runner(phase2_db.writer,model_factory=lambda ctx:FakeMessagesListChatModel(responses=responses()),enqueue=False)
    run=runner.start_run(OWNER,'Increase selected deal',{'domain':'sales'},BASE)
    paused=runner.execute(OWNER,run.id)
    ctx=RunContext(owner=OWNER,dataset_id=BASE,domain='sales',run_id=run.id,thread_id=run.id,database=phase2_db.writer)
    cfg={'configurable':{'thread_id':run.id}}
    with checkpoint_store(phase2_db.writer) as saver:
        g=build_graph(FakeMessagesListChatModel(responses=[]),build_tools(ctx),saver,context=ctx)
        g.update_state(cfg,{'memory_ids':['revoked-memory'],'messages':[AIMessage(content='Old remembered guidance that was forgotten')]},as_node='materialize')
    runner.resume_run(OWNER,run.id,ResumeInput(kind='finish',interrupt_id=paused.interrupt_id,text='keep'))
    assert runner.execute(OWNER,run.id).status=='paused'  # Revoked context requires a refreshed proposal.
    with checkpoint_store(phase2_db.writer) as saver:
        state=build_graph(FakeMessagesListChatModel(responses=[]),build_tools(ctx),saver,context=ctx).get_state(cfg).values
    assert state['memory_ids']==[]
    assert all('Old remembered' not in str(m.content) for m in state['messages'])


def test_two_executors_cannot_dispatch_same_run_and_cancel_stops_next_call(phase2_db):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from app.agent.runner import Runner
    prepare_runner(phase2_db)
    entered=Event();release=Event();calls=[]
    class BlockingModel:
        def invoke(self,messages):
            calls.append(1);entered.set();assert release.wait(10)
            return responses()[0]
    runner=Runner(phase2_db.writer,model_factory=lambda ctx:BlockingModel(),enqueue=False)
    run=runner.start_run(OWNER,'Inspect sales',{'domain':'sales'},BASE)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(runner.execute,OWNER,run.id)
        assert entered.wait(10)
        second=pool.submit(runner.execute,OWNER,run.id).result(timeout=10)
        assert second.status=='running'
        runner.cancel_run(OWNER,run.id);release.set()
        assert first.result(timeout=10).status=='cancelled'
    assert calls==[1]


def test_runner_can_reserve_model_credit_with_two_connection_runtime_pool(phase2_db):
    from sqlalchemy import create_engine
    from app.agent.runner import Runner
    from app.agent.provider import invoke_bounded
    from app.agent.contracts import ProviderConfig
    from test_phase2_budget import credit
    prepare_runner(phase2_db);credit(phase2_db)
    database=create_engine(phase2_db.writer.url,pool_size=2,max_overflow=0,pool_timeout=.2,hide_parameters=True)
    class BoundedFake:
        def __init__(self,ctx):self.ctx=ctx;self.model=FakeMessagesListChatModel(responses=responses())
        def invoke(self,messages):return invoke_bounded(database,OWNER,self.ctx.run_id,ProviderConfig(provider='nebius',model='fixture'),self.model,messages)
    try:
        runner=Runner(database,model_factory=BoundedFake,enqueue=False)
        run=runner.start_run(OWNER,'Increase selected deal',{'domain':'sales'},BASE)
        assert runner.execute(OWNER,run.id).status=='paused'
    finally:database.dispose()


def test_trace_parentage_is_preserved_across_resume(phase2_db,tmp_path,monkeypatch):
    import json
    from app.agent.runner import Runner
    from app.agent.contracts import ResumeInput
    prepare_runner(phase2_db);monkeypatch.setenv('STUDIO_TRACE_DIR',str(tmp_path))
    runner=Runner(phase2_db.writer,model_factory=lambda ctx:FakeMessagesListChatModel(responses=responses()),enqueue=False)
    run=runner.start_run(OWNER,'Increase selected deal',{'domain':'sales'},BASE)
    paused=runner.execute(OWNER,run.id)
    runner.resume_run(OWNER,run.id,ResumeInput(kind='finish',interrupt_id=paused.interrupt_id,text='keep'))
    runner.execute(OWNER,run.id)
    records=[json.loads(line) for line in (tmp_path/'spans.jsonl').read_text().splitlines()]
    roots=[r for r in records if r['id']==run.id]
    executions=[r for r in records if r['name']=='execution']
    assert len(roots)==1 and len(executions)==2
    assert all(r['parent_id']==run.id for r in executions)
    ids={r['id'] for r in records}
    assert all(r['parent_id'] is None or r['parent_id'] in ids for r in records)


def test_run_api_is_authenticated_and_rejects_arbitrary_state(phase2_db,monkeypatch):
    from app.agent.runner import Runner
    import app.agent.api as routes
    from test_api import client
    prepare_runner(phase2_db)
    runner=Runner(phase2_db.writer,model_factory=lambda ctx:FakeMessagesListChatModel(responses=responses()),enqueue=False)
    monkeypatch.setattr(routes,'runner',lambda:runner)
    api=client(monkeypatch)
    body={'brief':'Inspect selected deals','scope':{'domain':'sales'},'parent_id':BASE}
    assert api.post('/api/v1/runs',json=body).status_code==401
    api.post('/api/login',json={'password':'a-test-password-12345'})
    response=api.post('/api/v1/runs',json=body)
    assert response.status_code==202
    id=response.json()['id']
    assert api.post(f'/api/v1/runs/{id}/resume',json={'kind':'retry','state':{'approved':True}}).status_code==422
    assert api.post(f'/api/v1/runs/{id}/cancel',json={},headers={'origin':'https://evil.example'}).status_code==403


def test_read_tool_has_two_bounded_retries_without_repeating_model_call(phase2_db,monkeypatch):
    import app.agent.registry as registry
    original=registry.execute;attempts=[]
    def transient(ctx,name,args):
        if name=='inspect_records':
            attempts.append(1)
            if len(attempts)<3:raise TimeoutError()
        return original(ctx,name,args)
    monkeypatch.setattr(registry,'execute',transient)
    result=graph(phase2_db).invoke(start(),CFG)
    assert len(attempts)==3 and result['model_calls']==2
    assert result['tool_calls']==4 and result['candidate_id']


def test_ignoring_owned_memory_invalidates_approval_and_excludes_retrieval(phase2_db):
    from app.agent.runner import Runner
    from test_phase2_memory import prepare_memory,draft,FakeMemory
    from app.memory.service import propose_memory,confirm_memory,save_memory
    from app.scenarios.lifecycle import approve
    prepare_runner(phase2_db);prepare_memory(phase2_db)
    with phase2_db.admin.begin() as c:
        role=c.dialect.identifier_preparer.quote(phase2_db.writer.url.username)
        c.execute(text(f'GRANT EXECUTE ON FUNCTION studio_ignore_memory(text,text,text,jsonb),studio_lifecycle(text,text,text,jsonb) TO {role}'))
    with phase2_db.writer.begin() as c:
        item=propose_memory(c,OWNER,draft());confirm_memory(c,OWNER,item.id,item.content_hash)
    save_memory(phase2_db.writer,OWNER,item.id,FakeMemory())
    runner=Runner(phase2_db.writer,model_factory=lambda ctx:FakeMessagesListChatModel(responses=responses()),enqueue=False)
    run=runner.start_run(OWNER,'Increase selected deal',{'domain':'sales'},BASE)
    paused=runner.execute(OWNER,run.id);candidate=paused.result['review_state']['candidate']
    with phase2_db.writer.begin() as c:approve(c,OWNER,candidate['id'],candidate['content_hash'],BASE)
    from app.memory.service import update_memory
    with phase2_db.writer.begin() as c:update_memory(c,OWNER,item.id,draft('Focus on selected open opportunities for leadership demos.'))
    with phase2_db.reader.connect() as c:assert not c.scalar(text('SELECT valid FROM studio_approvals'))
    with phase2_db.writer.begin() as c:approve(c,OWNER,candidate['id'],candidate['content_hash'],BASE)
    runner.ignore_memory(OWNER,run.id,[item.id])
    with phase2_db.reader.connect() as c:
        assert not c.scalar(text('SELECT bool_or(valid) FROM studio_approvals'))
        assert c.scalar(text('SELECT scope FROM studio_runs WHERE id=:id'),{'id':run.id})['ignored_memory_ids']==[item.id]
    with pytest.raises(ValueError):runner.ignore_memory(OWNER,run.id,['unowned'])
