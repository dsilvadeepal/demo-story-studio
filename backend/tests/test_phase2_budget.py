from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import pytest
from sqlalchemy import text
from test_phase2_candidates import OWNER


def credit(db,balance='1',verified=True):
    with db.admin.begin() as c:
        c.execute(text("INSERT INTO studio_credit(provider,model,balance,credit_only,verified_until,input_rate,output_rate) VALUES('nebius','fixture',:balance,:verified,now()+interval '1 hour',1,2)"),{'balance':balance,'verified':verified})
        role=c.dialect.identifier_preparer.quote(db.writer.url.username)
        c.execute(text(f'GRANT SELECT ON studio_credit,studio_reservations TO {role}'))
        c.execute(text(f'GRANT EXECUTE ON FUNCTION studio_reserve(text,text,text,jsonb),studio_settle(text,jsonb) TO {role}'))


def request():
    from app.agent.contracts import CallReservation
    return CallReservation(provider='nebius',model='fixture',input_tokens=1000,output_tokens=1000)


@pytest.mark.parametrize('balance,verified',[('0',True),('1',False)])
def test_credit_gate_blocks_dispatch(phase2_db,balance,verified):
    from app.agent.budget import reserve_call
    credit(phase2_db,balance,verified)
    with phase2_db.writer.begin() as c:
        with pytest.raises(ValueError,match='BUDGET_UNAVAILABLE'):reserve_call(c,OWNER,'run',request())


def test_concurrent_reservations_cannot_overspend(phase2_db):
    from app.agent.budget import reserve_call
    credit(phase2_db,'.003')
    def reserve(i):
        try:
            with phase2_db.writer.begin() as c:return reserve_call(c,OWNER,'run'+str(i),request())
        except ValueError:return None
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(reserve,range(2)))
    assert sum(x is not None for x in results)==1


def test_unknown_timeout_retains_reservation_and_seventh_call_denied(phase2_db):
    from app.agent.budget import reserve_call,settle_call
    credit(phase2_db)
    with phase2_db.writer.begin() as c:
        for _ in range(6):
            id=reserve_call(c,OWNER,'run',request());settle_call(c,id,None)
        with pytest.raises(ValueError,match='LIMIT_REACHED'):reserve_call(c,OWNER,'run',request())
        assert c.scalar(text('SELECT sum(reserved) FROM studio_reservations'))==Decimal('.018')
        assert c.scalar(text('SELECT balance FROM studio_credit'))==Decimal('.982')


def test_usage_settlement_is_idempotent_and_overflow_blocked(phase2_db):
    from app.agent.budget import reserve_call,settle_call
    from app.agent.contracts import Usage,CallReservation
    credit(phase2_db)
    with phase2_db.writer.begin() as c:
        id=reserve_call(c,OWNER,'run',request())
        settle_call(c,id,Usage(input_tokens=100,output_tokens=100))
        settle_call(c,id,Usage(input_tokens=100,output_tokens=100))
        assert c.scalar(text('SELECT balance FROM studio_credit'))==Decimal('.9997')
        with pytest.raises(ValueError):CallReservation(provider='nebius',model='fixture',input_tokens=9000,output_tokens=1000)


def test_trace_redaction(tmp_path,monkeypatch):
    from app.agent.tracing import span
    monkeypatch.setenv('STUDIO_TRACE_DIR',str(tmp_path))
    with span('run',None,'model',{'provider':'nebius','api_key':'secret-value','tables':{'accounts':'private'},'model_version':'fixture','prompt_version':'v1'}):pass
    output=''.join(p.read_text() for p in tmp_path.iterdir())
    assert 'secret-value' not in output and 'private' not in output
    assert 'model_version' in output and 'prompt_version' in output


def test_langchain_runtime_settles_usage_and_timeout_stays_unknown(phase2_db,tmp_path,monkeypatch):
    from app.agent.provider import invoke_bounded
    from app.agent.contracts import ProviderConfig
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import AIMessage,HumanMessage
    credit(phase2_db);monkeypatch.setenv('STUDIO_TRACE_DIR',str(tmp_path))
    config=ProviderConfig(provider='nebius',model='fixture')
    model=FakeMessagesListChatModel(responses=[AIMessage(content='Evidence response',usage_metadata={'input_tokens':10,'output_tokens':5,'total_tokens':15})])
    response=invoke_bounded(phase2_db.writer,OWNER,'run',config,model,[HumanMessage(content='Inspect synthetic sales')])
    assert response.content=='Evidence response'
    with phase2_db.reader.connect() as c:
        assert c.scalar(text('SELECT actual FROM studio_reservations'))==Decimal('.00002')
    class TimeoutModel(FakeMessagesListChatModel):
        def _generate(self,*args,**kwargs):raise TimeoutError('provider timeout')
    with pytest.raises(ValueError,match='OUTCOME_UNKNOWN'):
        invoke_bounded(phase2_db.writer,OWNER,'run',config,TimeoutModel(responses=[]),[HumanMessage(content='Inspect')])
    with phase2_db.reader.connect() as c:assert c.scalar(text("SELECT count(*) FROM studio_reservations WHERE status='unknown'"))==1
    with pytest.raises(ValueError,match='LIMIT_REACHED'):
        invoke_bounded(phase2_db.writer,OWNER,'run',config,model,[HumanMessage(content='x'*9000)])


def test_adapter_binds_typed_tools_and_structured_output_without_network(monkeypatch):
    from app.agent.provider import build_model
    from app.agent.contracts import ProviderConfig
    from langchain_core.tools import tool
    from pydantic import BaseModel
    monkeypatch.setenv('NEBIUS_API_KEY','test-only-not-a-live-key')
    @tool
    def count_records(domain:str)->int:
        """Count records within the selected synthetic domain."""
        return 3
    class Answer(BaseModel):
        count:int
    model=build_model(ProviderConfig(provider='nebius',model='fixture'))
    assert model.bind_tools([count_records]).kwargs['tools'][0]['function']['name']=='count_records'
    assert model.with_structured_output(Answer,method='function_calling') is not None
    assert model.max_retries==0


def test_trace_records_estimated_and_settled_credit(phase2_db,tmp_path,monkeypatch):
    from app.agent.provider import invoke_bounded
    from app.agent.contracts import ProviderConfig
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import AIMessage,HumanMessage
    import json
    credit(phase2_db);monkeypatch.setenv('STUDIO_TRACE_DIR',str(tmp_path))
    model=FakeMessagesListChatModel(responses=[AIMessage(content='ok',usage_metadata={'input_tokens':10,'output_tokens':5,'total_tokens':15})])
    invoke_bounded(phase2_db.writer,OWNER,'trace-run',ProviderConfig(provider='nebius',model='fixture'),model,[HumanMessage(content='Inspect')])
    records=[json.loads(line) for line in (tmp_path/'spans.jsonl').read_text().splitlines()]
    usage=next(r for r in records if r['name']=='usage')
    assert Decimal(usage['attributes']['settled_credit'])==Decimal('.00002')
    assert Decimal(usage['attributes']['estimated_credit'])>Decimal('.00002')
    assert usage['parent_id'] in {r['id'] for r in records}


def test_nebius_project_cap_survives_credit_refresh_and_concurrent_calls(phase2_db):
    from app.agent.budget import reserve_call
    credit(phase2_db,'25')
    with phase2_db.admin.begin() as c:
        c.execute(text("""INSERT INTO studio_reservations
            (id,owner_id,workspace_id,run_id,provider,model,input_tokens,output_tokens,
             input_rate,output_rate,reserved,actual,status)
            VALUES('prior','owner','local','prior','nebius','fixture',1,1,1,2,9.997,9.997,'settled')"""))
    def reserve(i):
        try:
            with phase2_db.writer.begin() as c:return reserve_call(c,OWNER,'new'+str(i),request())
        except ValueError:return None
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(reserve,range(2)))
    assert sum(x is not None for x in results)==1
    with phase2_db.admin.begin() as c:
        c.execute(text("UPDATE studio_credit SET balance=25"))
    with phase2_db.writer.begin() as c:
        with pytest.raises(ValueError,match='LIMIT_REACHED'):reserve_call(c,OWNER,'after-refresh',request())


def test_project_cap_counts_unknown_cost_and_refunds_only_known_usage(phase2_db):
    from app.agent.budget import reserve_call,settle_call
    from app.agent.contracts import Usage
    credit(phase2_db,'25')
    with phase2_db.admin.begin() as c:
        c.execute(text("""INSERT INTO studio_reservations
            (id,owner_id,workspace_id,run_id,provider,model,input_tokens,output_tokens,
             input_rate,output_rate,reserved,status)
            VALUES('uncertain','owner','local','prior','nebius','fixture',1,1,1,2,10,'unknown')"""))
    with phase2_db.writer.begin() as c:
        with pytest.raises(ValueError,match='LIMIT_REACHED'):reserve_call(c,OWNER,'blocked',request())
        settle_call(c,'uncertain',Usage(input_tokens=1,output_tokens=1))
        assert reserve_call(c,OWNER,'released',request())
