from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from ..scenarios.repository import canonical
from ..scenarios.lifecycle import ScenarioError
from .contracts import MemoryItem


def transition(c,owner,action,payload):
    try:
        with c.begin_nested():
            result=c.scalar(text('SELECT studio_memory(:owner,:workspace,:action,CAST(:p AS jsonb))'),dict(owner=owner.owner_id,workspace=owner.workspace_id,action=action,p=canonical(payload)))
    except DBAPIError:
        raise ScenarioError('MEMORY_UNAVAILABLE') from None
    return MemoryItem.model_validate(result) if result and 'draft' in result else result


def get(c,owner,id):
    row=c.execute(text('SELECT id,provider_id,draft,content_hash,correlation,status FROM studio_memories WHERE id=:id AND owner_id=:owner AND workspace_id=:workspace'),dict(id=id,owner=owner.owner_id,workspace=owner.workspace_id)).mappings().first()
    if not row:raise ScenarioError('MEMORY_UNAVAILABLE')
    return MemoryItem.model_validate(dict(row))


def list_items(c,owner):
    ids=c.scalars(text("SELECT id FROM studio_memories WHERE owner_id=:owner AND workspace_id=:workspace AND status<>'deleted' ORDER BY created_at DESC LIMIT 100"),dict(owner=owner.owner_id,workspace=owner.workspace_id)).all()
    return [get(c,owner,id) for id in ids]
