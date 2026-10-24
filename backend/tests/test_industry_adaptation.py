from copy import deepcopy
import pytest
from pydantic import ValidationError
from app.seed import generate
from app.scenarios.contracts import Proposal
from app.scenarios.industry import IndustryAdaptation, adaptation_context, TEXT_FIELDS
from app.scenarios.operations import transform
from app.scenarios.validation import validate_candidate


def wording(bundle=None):
    context=adaptation_context(bundle or generate())
    targets=['Assembly fixtures','Industrial controllers','Machine frames','Plant equipment','Machine guards','Shipping crates','Process pumps','Parts washers']
    subjects=['Commissioning assistance','Component delivery question','Equipment guidance','Replacement component request']
    return dict(kind='adapt_industry',industry='Industrial manufacturing',company_descriptor='Precision Manufacturing',
        families=[dict(source=s,target=t) for s,t in zip(context['families'],targets)],
        case_subjects=[dict(source=s,target=t) for s,t in zip(context['case_subjects'],subjects)],
        opportunity_template='{family} supply agreement {number}',
        page_titles=dict(executive='Manufacturing sales overview',pipeline='Equipment sales pipeline',detail='Equipment deal details',trend='Manufacturing service trends',breakdown='Manufacturing service workload'))


def proposal(bundle=None):
    b=bundle or generate()
    return Proposal(parent_id=b['manifest']['id'],selection={'dashboard':'sales'},operations=[wording(b)])


def test_semantic_rewrite_preserves_facts_and_links_and_is_reproducible():
    b=generate();before=deepcopy(b);p=proposal(b);out=transform(b,p)
    assert b==before and out==transform(b,p)
    for table,rows in b['tables'].items():
        assert len(rows)==len(out['tables'][table])
        for old,new in zip(rows,out['tables'][table]):
            assert {k:v for k,v in old.items() if k not in TEXT_FIELDS.get(table,set())}=={k:v for k,v in new.items() if k not in TEXT_FIELDS.get(table,set())}
    assert out['tables']['accounts'][0]['industry']=='Industrial manufacturing'
    assert 'supply agreement' in out['tables']['opportunities'][0]['name']
    assert not validate_candidate(b,out,p).hard_errors
    # A second adaptation uses the current vocabulary; IDs remain stable.
    assert not validate_candidate(out,transform(out,proposal(out)),proposal(out)).hard_errors


def test_reject_partial_scope_missing_vocabulary_and_tampering():
    b=generate();p=proposal();out=transform(b,p)
    with pytest.raises(ValueError):transform(b,p.model_copy(update={'selection':p.selection.model_copy(update={'record_ids':['opportunities-0000']})}))
    raw=wording();raw['families'].pop()
    with pytest.raises(ValueError):transform(b,p.model_copy(update={'operations':[IndustryAdaptation(**raw)]}))
    out['tables']['opportunities'][0]['name']='unapproved wording'
    assert validate_candidate(b,out,p).hard_errors
    out=transform(b,p);out['tables']['opportunity_line_items'][0]['quantity']+=1
    assert validate_candidate(b,out,p).hard_errors
    out=transform(b,p);out['manifest']['presentation']['page_titles']['executive']='tampered'
    assert validate_candidate(b,out,p).hard_errors


@pytest.mark.parametrize('template',['{family.__class__} {number}','{family!r} {number}','{family:>10000} {number}','{unknown}'])
def test_template_is_not_code(template):
    raw=wording();raw['opportunity_template']=template
    with pytest.raises(ValidationError):IndustryAdaptation(**raw)


def test_database_review_apply_restore_and_legacy_hashes(phase2_db):
    from test_phase2_candidates import OWNER,BASE,prepare
    from app.scenarios.repository import create_candidate,read_bundle,get_active
    from app.scenarios.lifecycle import approve,apply,recover,verify,record_review
    from app.scenarios.contracts import ReviewEvent
    from app.scenarios.comparison import record_diff,compare
    from app.contracts import QueryRequest
    prepare(phase2_db)
    from sqlalchemy import text
    with phase2_db.admin.begin() as c:
        role=c.dialect.identifier_preparer.quote(phase2_db.writer.url.username)
        c.execute(text(f'GRANT EXECUTE ON FUNCTION studio_lifecycle(text,text,text,jsonb) TO {role}'))
    with phase2_db.writer.begin() as c:
        new=create_candidate(c,OWNER,proposal(),'industry')
        assert verify(c,OWNER,new.id)==new
        assert get_active(c,OWNER).id==BASE
        diff=record_diff(c,OWNER,new.id)
        assert any(x['table']=='dashboard' for x in diff['changes'])
        opportunities=record_diff(c,OWNER,new.id,table='opportunities')
        assert opportunities['total']==1200 and all(x['field']=='name' for x in opportunities['changes'])
        with pytest.raises(ValueError):record_diff(c,OWNER,new.id,table='unknown')
        comparison=compare(c,OWNER,BASE,new.id,QueryRequest(dashboard='sales',dataset_id=BASE))
        assert all(v['before']==v['after'] for v in comparison.metric_deltas.values())
        record_review(c,OWNER,new.id,ReviewEvent(kind='override',actor='owner',target='warnings',reason='Reviewed the synthetic terminology and unchanged metric definitions'))
        approved=approve(c,OWNER,new.id,new.content_hash,BASE)
        assert get_active(c,OWNER).id==BASE
        apply(c,OWNER,approved.id,'apply-industry')
        assert read_bundle(c,OWNER,get_active(c,OWNER).id)['manifest']['presentation']['industry']=='Industrial manufacturing'
        recover(c,OWNER,BASE,new.id,'restore-industry')
        assert get_active(c,OWNER).id==BASE


def test_graph_inspects_and_proposes_industry_without_activation(phase2_db):
    from langchain_core.messages import AIMessage
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from test_phase2_graph import graph,start,CFG
    from test_phase2_candidates import BASE
    from sqlalchemy import text
    model=FakeMessagesListChatModel(responses=[AIMessage(content='',tool_calls=[dict(id='context',name='inspect_industry_context',args={})]),AIMessage(content='',tool_calls=[dict(id='adapt',name='propose_industry_adaptation',args=wording())])])
    result=graph(phase2_db,model).invoke(start(),CFG)
    assert result['candidate_id'] and result['__interrupt__'][0].value['kind']=='review'
    with phase2_db.reader.connect() as c:assert c.scalar(text('SELECT dataset_id FROM studio_active'))==BASE


def test_industry_tools_enforce_scope_and_provider_input_budget(phase2_db):
    from dataclasses import replace
    from test_phase2_tools import context
    from app.agent.registry import invoke_tool,build_tools
    from app.agent.provider import select_studio_tools,bind_studio_tools
    from app.agent.graph import PROMPT,CAPABILITIES
    from app.scenarios.repository import canonical
    from langchain_core.messages import SystemMessage,HumanMessage,ToolMessage
    from langchain_openai import ChatOpenAI
    ctx=context(phase2_db)
    assert invoke_tool(replace(ctx,filters={'industry':['Manufacturing']}),'propose_industry_adaptation',wording()).error
    observation=invoke_tool(ctx,'inspect_industry_context',{})
    assert not observation.error
    messages=[SystemMessage(content=PROMPT+'\n'+CAPABILITIES),HumanMessage(content='Adapt this demo to industrial manufacturing. Preserve all numeric facts. '+('More detailed user context. '*75)[:1900]),ToolMessage(content=canonical(observation.model_dump(mode='json')),tool_call_id='inspect',name='inspect_industry_context')]
    selected=select_studio_tools(build_tools(ctx),messages)
    assert {t.name for t in selected}=={'propose_industry_adaptation','request_clarification'}
    model=bind_studio_tools(ChatOpenAI(api_key='test-not-a-real-key',model='test'),selected)
    bound=len(canonical({'messages':[m.model_dump(mode='json') for m in messages],'tools':model.kwargs['tools']}).encode())+256
    assert bound+350<=8000,bound  # Reserve runtime scope and inspection tool-call framing.


def test_industry_proposal_requires_inspection(phase2_db):
    from langchain_core.messages import AIMessage
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from test_phase2_graph import graph,start,CFG
    model=FakeMessagesListChatModel(responses=[AIMessage(content='',tool_calls=[dict(id='adapt',name='propose_industry_adaptation',args=wording())])])
    result=graph(phase2_db,model).invoke(start(),CFG)
    assert not result.get('candidate_id') and result['repair_count']==2


def test_review_summary_is_bounded_connected_and_detects_tampering():
    from app.scenarios.comparison import industry_review
    b=generate();p=proposal(b);out=transform(b,p)
    summary=industry_review(b,out,wording(b))
    assert all(c['passed'] for c in summary['checks'])
    assert len(summary['examples'])==3
    assert summary['counts']['opportunities']==1200
    for example in summary['examples']:
        account,opp,product,*cases=example['chain']
        row=next(r for r in b['tables']['opportunities'] if r['id']==opp['id'])
        assert row['account_id']==account['id']
        line=sorted((r for r in b['tables']['opportunity_line_items'] if r['opportunity_id']==opp['id']),key=lambda r:r['id'])[0]
        entry=next(r for r in b['tables']['pricebook_entries'] if r['id']==line['pricebook_entry_id'])
        assert entry['product_id']==product['id']
        assert product['after'].split(' model ')[0] in opp['after']
        for case in cases:
            assert next(r for r in b['tables']['cases'] if r['id']==case['id'])['account_id']==account['id']
    out['tables']['opportunity_line_items'][0]['quantity']+=1
    assert not industry_review(b,out,wording(b))['checks'][1]['passed']
    out['tables']['opportunities'][0]['name']='Unexpected name'
    assert not industry_review(b,out,wording(b))['checks'][2]['passed']


def test_generic_taxonomy_maps_cover_current_values_and_preserve_links():
    b=generate();raw=wording(b)
    # A non-HVAC vocabulary exercises the same mechanism without city presets.
    raw['divisions']=[dict(source=s,target=t) for s,t in zip(sorted({r['division'] for r in b['tables']['users']}),['Northern campus','Coastal campus','Southern campus'])]
    raw['case_types']=[dict(source=s,target='Campus '+s.lower()) for s in sorted({r['type'] for r in b['tables']['cases']})]
    p=proposal(b).model_copy(update={'operations':[IndustryAdaptation(**raw)]});out=transform(b,p)
    assert not validate_candidate(b,out,p).hard_errors
    assert {r['division'] for r in out['tables']['users']}=={'Northern campus','Coastal campus','Southern campus'}
    assert all(r['type'].startswith('Campus ') for r in out['tables']['cases'])
    assert [r['owner_id'] for r in b['tables']['cases']]==[r['owner_id'] for r in out['tables']['cases']]
    incomplete=dict(raw,divisions=raw['divisions'][:1])
    with pytest.raises(ValueError,match='Cover every'):transform(b,p.model_copy(update={'operations':[IndustryAdaptation(**incomplete)]}))
    out['tables']['cases'][0]['type']='unapproved'
    assert validate_candidate(b,out,p).hard_errors


def test_taxonomy_database_filters_and_charts_use_new_vocabulary(phase2_db):
    from test_phase2_candidates import OWNER,BASE,prepare
    from app.scenarios.repository import create_candidate
    from app.queries.analytics import query,read_facts
    from app.contracts import QueryRequest
    prepare(phase2_db);b=generate();raw=wording(b)
    raw['divisions']=[dict(source=s,target=t) for s,t in zip(sorted({r['division'] for r in b['tables']['users']}),['Zone A','Zone B','Zone C'])]
    raw['case_types']=[dict(source=s,target='Support '+s) for s in sorted({r['type'] for r in b['tables']['cases']})]
    p=proposal(b).model_copy(update={'operations':[IndustryAdaptation(**raw)]})
    with phase2_db.writer.begin() as c:
        new=create_candidate(c,OWNER,p,'taxonomy')
        before=query(c,QueryRequest(dataset_id=BASE,dashboard='service',filters={'type':['Order']}))
        after=query(c,QueryRequest(dataset_id=new.id,dashboard='service',filters={'type':['Support Order']}))
        assert before['values']==after['values']
        grouped=query(c,QueryRequest(dataset_id=new.id,dashboard='service',dimension='type_division'))
        assert 'Zone A' in str(grouped) and 'Support Order' in str(grouped)
        from app.scenarios.comparison import compare
        result=compare(c,OWNER,BASE,new.id,QueryRequest(dataset_id=new.id,dashboard='service',filters={'type':['Support Order'],'division':['Zone A']}))
        assert all(v['before']==v['after'] for v in result.metric_deltas.values())
        assert any('aligned' in w for w in result.warnings)
        original=compare(c,OWNER,BASE,new.id,QueryRequest(dataset_id=BASE,dashboard='service',filters={'type':['Order'],'division':['Central']}))
        assert all(v['before']==v['after'] for v in original.metric_deltas.values())
