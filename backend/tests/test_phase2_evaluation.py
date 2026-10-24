import json
from pathlib import Path
import pytest
from sqlalchemy import text
from test_phase2_candidates import OWNER,BASE

ROOT=Path(__file__).resolve().parents[2]

def test_fixed_offline_cases_are_separate_from_adversarial_and_never_live():
    from app.agent.evaluation import load_cases,evaluate_offline
    cases=load_cases()
    assert [sum(c['group']==g for c in cases['standard']) for g in ('sales','service','refresh')]==[5,3,2]
    result=evaluate_offline()
    assert result['mode']=='offline' and result['live_acceptance']=='pending'
    assert result['passed']==10 and len(result['cases'])==10
    assert result['adversarial'] and all(c['passed'] for c in result['adversarial'])
    assert result['provider_calls']==0

def test_live_unverified_gate_never_constructs_model(phase2_db,monkeypatch):
    from app.agent.evaluation import evaluate_live
    from test_phase2_graph import prepare_runner
    prepare_runner(phase2_db)
    calls=[]
    monkeypatch.setattr('app.agent.provider.build_model',lambda config:calls.append(config))
    result=evaluate_live(phase2_db.writer,'nebius')
    assert result['status']=='blocked' and result['provider_calls']==0 and not calls

def test_bound_real_tool_schema_allows_inspect_then_proposal(phase2_db,monkeypatch):
    from app.agent.runner import Runner
    from app.agent.provider import invoke_bounded,bind_studio_tools,select_studio_tools
    from app.agent.registry import build_tools
    from app.agent.contracts import ProviderConfig
    from langchain_openai import ChatOpenAI
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from test_phase2_graph import prepare_runner,responses
    from test_phase2_budget import credit
    prepare_runner(phase2_db);credit(phase2_db)
    class FakeBound:
        def __init__(self,ctx):
            self.ctx=ctx;self.fake=FakeMessagesListChatModel(responses=responses())
            self.kwargs=bind_studio_tools(ChatOpenAI(api_key='offline-placeholder',model='offline'),build_tools(ctx)).kwargs
        def for_messages(self,messages):
            self.kwargs=bind_studio_tools(ChatOpenAI(api_key='offline-placeholder',model='offline'),select_studio_tools(build_tools(self.ctx),messages)).kwargs
            return self
        def invoke(self,messages):return self.fake.invoke(messages)
    class Bounded:
        def __init__(self,ctx):self.ctx=ctx;self.bound=FakeBound(ctx)
        def invoke(self,messages):return invoke_bounded(phase2_db.writer,OWNER,self.ctx.run_id,ProviderConfig(provider='nebius',model='fixture'),self.bound.for_messages(messages),messages)
    runner=Runner(phase2_db.writer,model_factory=Bounded,enqueue=False)
    run=runner.start_run(OWNER,'Inspect then increase opportunities-0000 prices by ten percent',{'domain':'sales'},BASE)
    result=runner.execute(OWNER,run.id)
    assert result.status=='paused',result.result

@pytest.mark.parametrize('case_id',['sales-price-up','sales-price-down','sales-close-won','sales-expected-close','sales-close-offset','service-half','service-target','service-zero','refresh-forward','refresh-backward'])
def test_fixed_case_materializes_real_revision_without_activation(phase2_db,case_id):
    from app.agent.evaluation import load_cases,case_proposal
    from app.agent.graph import build_graph
    from app.agent.registry import build_tools
    from app.agent.contracts import RunContext
    from app.scenarios.repository import read_bundle,digest
    from app.scenarios.operations import transform
    from langchain_core.messages import AIMessage,HumanMessage
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langgraph.checkpoint.memory import InMemorySaver
    from test_phase2_graph import prepare_runner
    prepare_runner(phase2_db)
    case=next(c for c in load_cases()['standard'] if c['id']==case_id)
    ctx=RunContext(owner=OWNER,dataset_id=BASE,domain=case['selection']['dashboard'],run_id=case_id,thread_id=case_id,database=phase2_db.writer)
    model=FakeMessagesListChatModel(responses=[AIMessage(content='',tool_calls=[dict(id='read',name='inspect_records',args={'page_size':1})]),AIMessage(content='',tool_calls=[dict(id='proposal',name='submit_proposed_operations',args={k:case[k] for k in ('selection','operations')})])])
    graph=build_graph(model,build_tools(ctx),InMemorySaver(),context=ctx)
    result=graph.invoke(dict(messages=[HumanMessage(content=case['brief'])]),{'configurable':{'thread_id':case_id}})
    assert result['__interrupt__'][0].value['kind']=='review'
    with phase2_db.reader.connect() as c:
        assert c.scalar(text('SELECT dataset_id FROM studio_active'))==BASE
        parent=read_bundle(c,OWNER,BASE);candidate=read_bundle(c,OWNER,result['candidate_id'])
        expected=transform(parent,case_proposal(case,BASE))
        for table,rows in candidate['tables'].items():
            assert [{k:v for k,v in row.items() if k!='dataset_id'} for row in rows]==[{k:v for k,v in row.items() if k!='dataset_id'} for row in expected['tables'][table]]
        assert candidate['manifest']['as_of_date']==expected['manifest']['as_of_date']


def test_two_thread_leadership_memory_recall_and_forgotten_exclusion(phase2_db,monkeypatch):
    from test_phase2_memory import prepare_memory,draft,FakeMemory
    from test_phase2_graph import prepare_runner,responses
    from app.memory.service import propose_memory,confirm_memory,save_memory,search_memory,forget_memory
    import app.agent.tools as tool_module
    from app.agent.runner import Runner
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    prepare_runner(phase2_db);prepare_memory(phase2_db);client=FakeMemory()
    with phase2_db.writer.begin() as c:
        item=propose_memory(c,OWNER,draft());confirm_memory(c,OWNER,item.id,item.content_hash)
    save_memory(phase2_db.writer,OWNER,item.id,client)
    monkeypatch.setattr(tool_module,'search_memory',lambda c,o,s,q:search_memory(c,o,s,q,client))
    runner=Runner(phase2_db.writer,model_factory=lambda ctx:FakeMessagesListChatModel(responses=responses()),enqueue=False)
    scope=dict(domain='sales',audience='leadership',intent='quarterly review')
    a=runner.start_run(OWNER,'Inspect selected deal',scope,BASE);first=runner.execute(OWNER,a.id)
    b=runner.start_run(OWNER,'Prepare another leadership demo',scope,BASE);second=runner.execute(OWNER,b.id)
    assert a.id!=b.id and first.result['memory_ids']==second.result['memory_ids']==[item.id]
    assert first.result['candidate_id']!=second.result['candidate_id']
    with phase2_db.writer.begin() as c:forget_memory(c,OWNER,item.id)
    c_run=runner.start_run(OWNER,'Prepare without forgotten guidance',scope,BASE)
    assert runner.execute(OWNER,c_run.id).result['memory_ids']==[]
