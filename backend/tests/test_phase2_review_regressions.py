import pytest
from sqlalchemy import text
from test_phase2_candidates import OWNER,BASE
from test_phase2_graph import prepare_runner,responses

def test_poll_reconciles_expired_orphan_and_restart_marks_queued_without_dispatch(phase2_db):
    from app.agent.runner import Runner,_transition
    prepare_runner(phase2_db);calls=[]
    runner=Runner(phase2_db.writer,model_factory=lambda ctx:calls.append(ctx),enqueue=False)
    run=runner.start_run(OWNER,'Inspect sales',{'domain':'sales'},BASE)
    with phase2_db.writer.begin() as c:_transition(c,OWNER,'claim',{'id':run.id})
    restarted=Runner(phase2_db.writer,model_factory=lambda ctx:calls.append(ctx),enqueue=False)
    restarted.recover_expired(OWNER)
    with phase2_db.admin.begin() as c:c.execute(text("UPDATE studio_runs SET lease_until=now()-interval '1 second' WHERE id=:id"),{'id':run.id})
    assert restarted.get_run(OWNER,run.id).status=='interrupted'
    queued=runner.start_run(OWNER,'Queued before restart',{'domain':'sales'},BASE)
    restarted.recover_expired(OWNER,startup=True)
    assert restarted.get_run(OWNER,queued.id).status=='interrupted'
    assert not calls

@pytest.mark.parametrize('read_calls',[[('inspect_records',{})],[('discover_catalog',{}),('inspect_records',{})]])
def test_default_evidence_fits_real_schemas_and_refinement(phase2_db,read_calls):
    from app.agent.runner import Runner
    from app.agent.provider import invoke_bounded,bind_studio_tools,select_studio_tools
    from app.agent.registry import build_tools
    from app.agent.contracts import ProviderConfig,ResumeInput
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import AIMessage
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from test_phase2_budget import credit
    prepare_runner(phase2_db);credit(phase2_db)
    replies=[AIMessage(content='',tool_calls=[dict(id='read'+str(i),name=name,args=args)]) for i,(name,args) in enumerate(read_calls)]+[responses()[1]]
    class Model:
        def __init__(self,ctx):self.ctx=ctx;self.fake=FakeMessagesListChatModel(responses=replies)
        def invoke(self,messages):
            outer=self
            class Transport:
                kwargs=bind_studio_tools(ChatOpenAI(api_key='offline-placeholder',model='offline'),select_studio_tools(build_tools(outer.ctx),messages)).kwargs
                def invoke(self,m):return outer.fake.invoke(m)
            return invoke_bounded(phase2_db.writer,OWNER,self.ctx.run_id,ProviderConfig(provider='nebius',model='fixture'),Transport(),messages)
    runner=Runner(phase2_db.writer,model_factory=Model,enqueue=False)
    run=runner.start_run(OWNER,'Inspect and increase selected deal',{'domain':'sales'},BASE)
    result=runner.execute(OWNER,run.id)
    assert result.status=='paused',result.result

    runner.resume_run(OWNER,run.id,ResumeInput(kind='refine',interrupt_id=result.interrupt_id,text='Keep the selected scope and inspect again.'))
    result=runner.execute(OWNER,run.id)
    assert result.status=='paused',result.result
    if len(read_calls)==1:
        # Each explicit refinement receives its own bounded generation; costs remain cumulative.
        runner.resume_run(OWNER,run.id,ResumeInput(kind='refine',interrupt_id=result.interrupt_id,text='Keep the same selected record and five percent increase.'))
        result=runner.execute(OWNER,run.id)
        assert result.status=='paused',result.result
        assert result.result['model_calls']==2
        with phase2_db.writer.connect() as c:
            assert c.scalar(text('SELECT count(*) FROM studio_reservations WHERE run_id=:id'),{'id':run.id})==6


def test_visible_scope_constrains_top_n_and_inspection(phase2_db):
    from app.agent.contracts import RunContext,RunScope
    from app.agent.registry import invoke_tool
    from app.contracts import QueryRequest
    from app.queries.analytics import read_facts,filtered
    prepare_runner(phase2_db)
    with phase2_db.reader.connect() as c:
        rows,_=read_facts(c,QueryRequest(dataset_id=BASE,dashboard='sales'))
    account=rows[0]['account'];period={'start':'2026-01-01','end':'2026-12-31','field':'close_date'}
    scope=RunScope(domain='sales',filters={'account':[account]},period=period)
    ctx=RunContext(owner=OWNER,dataset_id=BASE,domain='sales',run_id='scope',thread_id='scope',database=phase2_db.writer,filters=scope.filters,period=scope.period)
    result=invoke_tool(ctx,'submit_proposed_operations',{'selection':{'dashboard':'sales','top_n':5},'operations':[{'kind':'scale_line_prices','factor':'1.1'}]})
    expected=filtered(rows,QueryRequest(dataset_id=BASE,dashboard='sales',filters=scope.filters,period=scope.period));expected.sort(key=lambda r:(-r['amount'],r['id']))
    assert not result.error,result
    assert result.data['proposal']['selection']['record_ids']==[r['id'] for r in expected[:5]]
    inspected=invoke_tool(ctx,'inspect_records',{})
    assert all(r['account']==account for r in inspected.data['rows'])

def test_updated_saved_memory_scrubs_old_wording_and_preserves_owner_clarification(phase2_db,monkeypatch):
    from test_phase2_memory import prepare_memory,draft,FakeMemory
    from app.memory.service import propose_memory,confirm_memory,save_memory,update_memory,search_memory
    import app.agent.tools as tool_module
    from app.agent.runner import Runner,checkpoint_store
    from app.agent.contracts import RunContext,ResumeInput
    from app.agent.graph import build_graph
    from app.agent.registry import build_tools
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import HumanMessage,AIMessage
    prepare_runner(phase2_db);prepare_memory(phase2_db);client=FakeMemory()
    with phase2_db.writer.begin() as c:
        item=propose_memory(c,OWNER,draft());confirm_memory(c,OWNER,item.id,item.content_hash)
    save_memory(phase2_db.writer,OWNER,item.id,client)
    monkeypatch.setattr(tool_module,'search_memory',lambda c,o,s,q:search_memory(c,o,s,q,client))
    runner=Runner(phase2_db.writer,model_factory=lambda ctx:FakeMessagesListChatModel(responses=responses()),enqueue=False)
    run=runner.start_run(OWNER,'Inspect selected deal',dict(domain='sales',audience='leadership',intent='quarterly review'),BASE)
    paused=runner.execute(OWNER,run.id)
    ctx=RunContext(owner=OWNER,dataset_id=BASE,domain='sales',run_id=run.id,thread_id=run.id,database=phase2_db.writer)
    cfg={'configurable':{'thread_id':run.id}}
    with checkpoint_store(phase2_db.writer) as saver:
        graph=build_graph(FakeMessagesListChatModel(responses=[]),build_tools(ctx),saver,context=ctx)
        graph.update_state(cfg,{'messages':[HumanMessage(content='Keep my explicit owner clarification.'),AIMessage(content='Obsolete remembered wording marker')]},as_node='materialize')
    with phase2_db.writer.begin() as c:
        updated=update_memory(c,OWNER,item.id,draft('Focus on selected opportunities and avoid broad changes.'));confirm_memory(c,OWNER,item.id,updated.content_hash)
    save_memory(phase2_db.writer,OWNER,item.id,client)
    runner.resume_run(OWNER,run.id,ResumeInput(kind='finish',interrupt_id=paused.interrupt_id,text='keep'))
    result=runner.execute(OWNER,run.id)
    with checkpoint_store(phase2_db.writer) as saver:
        state=build_graph(FakeMessagesListChatModel(responses=[]),build_tools(ctx),saver,context=ctx).get_state(cfg).values
    assert all('Obsolete remembered wording marker' not in str(m.content) for m in state['messages'])
    assert any('Keep my explicit owner clarification.' in str(m.content) for m in state['messages'])
    assert result.status=='paused' and result.result['candidate_id']!=paused.result['candidate_id']

@pytest.mark.parametrize('revocation',['forget','ignore'])
def test_later_memory_tool_retrieval_tracks_hash_and_forget_invalidates_resume(phase2_db,monkeypatch,revocation):
    from test_phase2_memory import prepare_memory,draft,FakeMemory
    from app.memory.service import propose_memory,confirm_memory,save_memory,search_memory,forget_memory
    import app.agent.tools as tool_module
    from app.agent.runner import Runner
    from app.agent.contracts import ResumeInput
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import AIMessage
    prepare_runner(phase2_db);prepare_memory(phase2_db);client=FakeMemory();calls=[]
    with phase2_db.writer.begin() as c:
        item=propose_memory(c,OWNER,draft());confirm_memory(c,OWNER,item.id,item.content_hash)
    save_memory(phase2_db.writer,OWNER,item.id,client)
    def search(c,o,s,q):
        calls.append(1)
        return [] if len(calls)==1 else search_memory(c,o,s,q,client)
    monkeypatch.setattr(tool_module,'search_memory',search)
    replies=[AIMessage(content='',tool_calls=[dict(id='memory',name='search_demo_memory',args={})]),*responses()]
    runner=Runner(phase2_db.writer,model_factory=lambda ctx:FakeMessagesListChatModel(responses=replies),enqueue=False)
    run=runner.start_run(OWNER,'Inspect selected deal',dict(domain='sales',audience='leadership',intent='quarterly review'),BASE)
    paused=runner.execute(OWNER,run.id)
    assert paused.result['memory_versions']=={item.id:item.content_hash}
    if revocation=='ignore':runner.ignore_memory(OWNER,run.id,[item.id])
    else:
        with phase2_db.writer.begin() as c:forget_memory(c,OWNER,item.id)
    runner.resume_run(OWNER,run.id,ResumeInput(kind='finish',interrupt_id=paused.interrupt_id,text='keep'))
    result=runner.execute(OWNER,run.id)
    assert result.result['memory_ids']==[] and result.status=='paused'

def test_comparison_exposes_resolved_selection_count(phase2_db):
    from test_phase2_lifecycle import ready
    from app.scenarios.comparison import compare
    from app.contracts import QueryRequest
    candidate=ready(phase2_db)
    with phase2_db.reader.connect() as c:
        result=compare(c,OWNER,BASE,candidate.id,QueryRequest(dataset_id=BASE,dashboard='sales'))
    assert result.selection_summary=={'domain':'sales','count':1,'global':False}
