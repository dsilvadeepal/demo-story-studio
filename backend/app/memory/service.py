from hashlib import sha256
from uuid import uuid4
from sqlalchemy import text
from ..scenarios.repository import canonical
from ..scenarios.lifecycle import ScenarioError
from .contracts import MemoryDraft
from .repository import transition,get,list_items
from .client import ManagedMemoryClient


def _draft_payload(owner,draft):
    if draft.scope.owner_id!=owner.owner_id or draft.scope.workspace_id!=owner.workspace_id:
        raise ScenarioError('MEMORY_UNAVAILABLE')
    data=draft.model_dump()
    return dict(draft=data,hash=sha256(canonical(data).encode()).hexdigest(),correlation=str(uuid4()))


def propose_memory(c,owner,draft):
    return transition(c,owner,'propose',dict(id=str(uuid4()),**_draft_payload(owner,draft)))


def update_memory(c,owner,id,draft):
    return transition(c,owner,'update',dict(id=id,**_draft_payload(owner,draft)))


def confirm_memory(c,owner,id,content_hash):
    return transition(c,owner,'confirm',dict(id=id,hash=content_hash))


def record_outcome(c,owner,revision_id,successful):
    return transition(c,owner,'outcome',dict(revision=revision_id,successful=successful))


def forget_memory(c,owner,id):return transition(c,owner,'forget',dict(id=id))


def _scope(scope):
    return dict(owner=sha256(scope.owner_id.encode()).hexdigest(),workspace=sha256(scope.workspace_id.encode()).hexdigest(),domain=scope.domain,audience=scope.audience,intent=scope.intent)


def _matches(item,remote):
    metadata=(remote or {}).get('metadata') or {}
    return bool(remote and remote.get('id') and remote.get('memory')==item.draft.text
                and all(metadata.get(k)==v for k,v in dict(_scope(item.draft.scope),correlation=item.correlation).items()))


def _quota(database,owner,kind):
    with database.begin() as c:transition(c,owner,'quota',dict(kind=kind))


def save_memory(database,owner,id,client=None):
    client=client or ManagedMemoryClient()
    # Session lock spans network work; state and quota are committed before dispatch.
    with database.connect() as lock:
        lock.execute(text('SELECT pg_advisory_lock(hashtextextended(:key,0))'),dict(key='memory:'+id));lock.commit()
        try:
            with database.begin() as c:
                item=get(c,owner,id)
                if item.status=='saved':return item
                if item.status not in ('confirmed','saving','unknown'):raise ScenarioError('MEMORY_UNAVAILABLE')
                reconcile=item.status in ('saving','unknown')
                if not reconcile:
                    transition(c,owner,'quota',dict(kind='write'))
                    item=transition(c,owner,'saving',dict(id=id))
            remote=None
            try:
                if reconcile:
                    _quota(database,owner,'read')
                    hits=client.search(item.draft.text,dict(_scope(item.draft.scope),correlation=item.correlation))
                    remote=next((x for x in hits if _matches(item,x)),None)
                else:
                    operation=client.update if item.provider_id else client.add
                    args=([item.provider_id] if item.provider_id else [])+[item.draft.text,_scope(item.draft.scope),item.correlation]
                    remote=operation(*args)
                status='saved' if _matches(item,remote) else 'unknown'
            except Exception:status='unknown'
            with database.begin() as c:
                return transition(c,owner,'result',dict(id=id,correlation=item.correlation,status=status,provider_id=(remote or {}).get('id')))
        finally:
            lock.execute(text('SELECT pg_advisory_unlock(hashtextextended(:key,0))'),dict(key='memory:'+id));lock.commit()


def search_memory(c,owner,scope,query,client=None):
    if scope.owner_id!=owner.owner_id or scope.workspace_id!=owner.workspace_id:raise ScenarioError('MEMORY_UNAVAILABLE')
    # Send only reusable scope as the query, not raw conversation or record facts.
    candidates=[x for x in list_items(c,owner) if x.status=='saved' and x.draft.scope==scope]
    if not candidates:return []
    try:
        transition(c,owner,'quota',dict(kind='read'))
        hits=(client or ManagedMemoryClient()).search(scope.intent,_scope(scope))
    except Exception:return []
    result=[]
    for item in candidates:
        if any(x.get('id')==item.provider_id and _matches(item,x) for x in hits):result.append(item)
    return result[:5]


def delete_memory(database,owner,id,client=None):
    client=client or ManagedMemoryClient()
    with database.connect() as lock:
        lock.execute(text('SELECT pg_advisory_lock(hashtextextended(:key,0))'),dict(key='memory:'+id));lock.commit()
        try:
            with database.begin() as c:
                item=get(c,owner,id)
                if item.status=='deleted':return item
                if item.status!='deletion-pending':raise ScenarioError('MEMORY_UNAVAILABLE')
            try:
                remote_id=item.provider_id
                if not remote_id:
                    _quota(database,owner,'read')
                    hits=client.search(item.draft.text,dict(_scope(item.draft.scope),correlation=item.correlation))
                    remote=next((x for x in hits if _matches(item,x)),None)
                    if not remote:return item  # A queued add may still complete later.
                    remote_id=remote['id']
                _quota(database,owner,'write');client.delete(remote_id)
                _quota(database,owner,'read')
                if client.get(remote_id) is not None:return item
            except Exception:return item
            with database.begin() as c:return transition(c,owner,'deleted',dict(id=id))
        finally:
            lock.execute(text('SELECT pg_advisory_unlock(hashtextextended(:key,0))'),dict(key='memory:'+id));lock.commit()
