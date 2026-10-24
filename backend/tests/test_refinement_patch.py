from copy import deepcopy
import pytest
from app.agent.refinement import AdaptationPatch,merge_patch
from test_industry_adaptation import proposal

def test_sparse_template_patch_preserves_every_other_rule():
    base=proposal().model_dump(mode='json');original=deepcopy(base)
    request='Change opportunity template to {family} installation project {number}.'
    patch=AdaptationPatch(edits=[dict(field='opportunity_template',value='{family} installation project {number}',request_quote=request)])
    out=merge_patch(base,patch,request)
    assert base==original
    out['operations'][0]['opportunity_template']=original['operations'][0]['opportunity_template']
    assert out==original

@pytest.mark.parametrize('edit',[
 dict(field='industry',value='Retail',request_quote='Keep industry Retail'),
 dict(field='company_descriptor',value='Unrequested',request_quote='Change region Central to Laval'),
 dict(field='opportunity_template',value='{family} invented {number}',request_quote='Change opportunity template to installation project'),
])
def test_unrequested_or_unquoted_changes_fail_closed(edit):
    with pytest.raises(ValueError):merge_patch(proposal().model_dump(mode='json'),AdaptationPatch(edits=[edit]),edit['request_quote'])

def test_region_patch_preserves_other_regions_and_rejects_collisions():
    base=proposal().model_dump(mode='json');base['operations'][0]['divisions']=[dict(source='Central',target='Laval'),dict(source='East',target='Longueuil')]
    request='Change region Laval to Montréal Centre.'
    out=merge_patch(base,AdaptationPatch(edits=[dict(field='divisions',source='Laval',value='Montréal Centre',request_quote=request)]),request)
    assert out['operations'][0]['divisions']==[dict(source='Central',target='Montréal Centre'),dict(source='East',target='Longueuil')]
    request='Change region Laval to Longueuil.'
    with pytest.raises(ValueError):merge_patch(base,AdaptationPatch(edits=[dict(field='divisions',source='Central',value='Longueuil',request_quote=request)]),request)

def test_graph_refines_reviewed_proposal_without_reinspection_or_activation(phase2_db):
    from langchain_core.messages import AIMessage,HumanMessage
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langgraph.types import Command
    from test_phase2_graph import graph,CFG
    from test_industry_adaptation import wording
    from sqlalchemy import text
    from test_phase2_candidates import BASE
    request='Change opportunity template to {family} installation project {number}.'
    model=FakeMessagesListChatModel(responses=[
      AIMessage(content='',tool_calls=[dict(id='i',name='inspect_industry_context',args={})]),
      AIMessage(content='',tool_calls=[dict(id='p',name='propose_industry_adaptation',args=wording())]),
      AIMessage(content='',tool_calls=[dict(id='r',name='refine_industry_adaptation',args={'edits':[dict(field='opportunity_template',value='{family} installation project {number}',request_quote=request)]})])])
    g=graph(phase2_db,model);first=g.invoke({'messages':[HumanMessage(content='Adapt manufacturing')]},CFG)
    second=g.invoke(Command(resume={'kind':'refine','text':request}),CFG)
    assert second['candidate_id']!=first['candidate_id'] and second['model_calls']==1
    assert [m.name for m in second['messages'] if getattr(m,'type',None)=='tool']==['inspect_industry_context','propose_industry_adaptation','refine_industry_adaptation']
    old=deepcopy(first['plan']);new=deepcopy(second['plan']);new['operations'][0]['opportunity_template']=old['operations'][0]['opportunity_template'];assert new==old
    with phase2_db.reader.connect() as c:assert c.scalar(text('SELECT dataset_id FROM studio_active'))==BASE


def test_chained_refinement_keeps_previous_edit_and_all_unrequested_rules():
    base=proposal().model_dump(mode='json')
    base['operations'][0]['divisions']=[dict(source='Central',target='Laval')]
    first='Change opportunity template to {family} installation project {number}.'
    out=merge_patch(base,AdaptationPatch(edits=[dict(field='opportunity_template',value='{family} installation project {number}',request_quote=first)]),first)
    second='Change region Laval to Montréal Centre.'
    final=merge_patch(out,AdaptationPatch(edits=[dict(field='divisions',source='Laval',value='Montréal Centre',request_quote=second)]),second)
    assert final['operations'][0]['opportunity_template']==out['operations'][0]['opportunity_template']
    final['operations'][0]['divisions']=out['operations'][0]['divisions']
    assert final==out

def test_fabricated_authorization_quote_cannot_change_an_unrequested_field():
    patch=AdaptationPatch(edits=[dict(field='industry',value='Retail',request_quote='Change industry to Retail')])
    with pytest.raises(ValueError):merge_patch(proposal().model_dump(mode='json'),patch,'Change region Central to Laval.')
