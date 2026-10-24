import pytest
import os
import subprocess
import sys
from pathlib import Path
from sqlalchemy import text
from test_phase2_candidates import OWNER

def test_managed_sdk_import_uses_private_project_storage():
    root=Path(__file__).resolve().parents[2]
    script="""
from pathlib import Path
from app.memory.client import ManagedMemoryClient
try:
    ManagedMemoryClient().client
except ValueError:
    pass  # Empty test key prevents any network request after SDK import.
else:
    raise AssertionError('An empty key must not create a usable client')
from mem0.memory.setup import mem0_dir
assert Path(mem0_dir) == Path.cwd()/'.local'/'mem0'
assert Path(mem0_dir).stat().st_mode & 0o077 == 0
"""
    env=dict(os.environ,MEM0_API_KEY='',PYTHONPATH=str(root/'backend'))
    result=subprocess.run([sys.executable,'-c',script],cwd=root,env=env,capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stderr

class FakeMemory:
    def __init__(self):self.items={};self.timeout_after_save=False;self.delete_unavailable=False
    def add(self,text,scope,correlation):
        id='remote-'+correlation;self.items[id]={'id':id,'memory':text,'metadata':dict(scope,correlation=correlation)}
        if self.timeout_after_save:raise TimeoutError()
        return self.items[id]
    def search(self,query,scope):return [x for x in self.items.values() if all(x['metadata'].get(k)==v for k,v in scope.items())]
    def update(self,id,text,scope,correlation):
        self.items[id]={'id':id,'memory':text,'metadata':dict(scope,correlation=correlation)};return self.items[id]
    def get(self,id):return self.items.get(id)
    def delete(self,id):
        if self.delete_unavailable:raise TimeoutError()
        self.items.pop(id,None)


def prepare_memory(db):
    with db.admin.begin() as c:
        role=c.dialect.identifier_preparer.quote(db.writer.url.username)
        c.execute(text(f'GRANT SELECT ON ALL TABLES IN SCHEMA public TO {role}'))
        c.execute(text(f'GRANT EXECUTE ON FUNCTION studio_memory(text,text,text,jsonb) TO {role}'))
        c.execute(text("INSERT INTO studio_memory_allowance VALUES(1,100,100,true,now()+interval '1 hour')"))


def draft(text_value='For leadership demos, focus on larger open deals.',domain='sales',kind='preference',revision=None):
    from app.memory.contracts import MemoryDraft,MemoryScope
    return MemoryDraft(kind=kind,text=text_value,scope=MemoryScope(owner_id='owner',workspace_id='local',domain=domain,audience='leadership',intent='quarterly review'),source_revision_id=revision)


def test_exact_confirmation_and_new_conversation_recall(phase2_db):
    from app.memory.service import propose_memory,confirm_memory,save_memory,search_memory
    prepare_memory(phase2_db);client=FakeMemory()
    with phase2_db.writer.begin() as c:item=propose_memory(c,OWNER,draft())
    with pytest.raises(ValueError):save_memory(phase2_db.writer,OWNER,item.id,client)
    assert not client.items
    with phase2_db.writer.begin() as c:
        with pytest.raises(ValueError):confirm_memory(c,OWNER,item.id,'wrong')
        confirm_memory(c,OWNER,item.id,item.content_hash)
    saved=save_memory(phase2_db.writer,OWNER,item.id,client)
    assert saved.status=='saved'
    with phase2_db.writer.begin() as c:
        hits=search_memory(c,OWNER,draft().scope,'leadership',client)
        assert [x.id for x in hits]==[item.id]
        assert search_memory(c,OWNER,draft(domain='service').scope,'leadership',client)==[]


def test_timeout_reconciles_without_duplicate_and_forget_excludes_immediately(phase2_db):
    from app.memory.service import propose_memory,confirm_memory,save_memory,forget_memory,search_memory,delete_memory
    prepare_memory(phase2_db);client=FakeMemory();client.timeout_after_save=True
    with phase2_db.writer.begin() as c:
        item=propose_memory(c,OWNER,draft());confirm_memory(c,OWNER,item.id,item.content_hash)
    assert save_memory(phase2_db.writer,OWNER,item.id,client).status=='unknown'
    assert save_memory(phase2_db.writer,OWNER,item.id,client).status=='saved'
    assert len(client.items)==1
    with phase2_db.writer.begin() as c:forget_memory(c,OWNER,item.id)
    client.delete_unavailable=True
    assert delete_memory(phase2_db.writer,OWNER,item.id,client).status=='deletion-pending'
    with phase2_db.writer.begin() as c:assert search_memory(c,OWNER,draft().scope,'leadership',client)==[]
    client.delete_unavailable=False
    assert delete_memory(phase2_db.writer,OWNER,item.id,client).status=='deleted'


def test_update_requires_new_confirmation_and_recipe_requires_explicit_outcome(phase2_db):
    from app.memory.service import propose_memory,confirm_memory,save_memory,update_memory,record_outcome
    from app.scenarios.lifecycle import approve,apply
    from test_phase2_lifecycle import ready
    prepare_memory(phase2_db);client=FakeMemory();candidate=ready(phase2_db)
    with phase2_db.writer.begin() as c:
        a=approve(c,OWNER,candidate.id,candidate.content_hash,'baseline-v1-42-2026-10-21');apply(c,OWNER,a.id,'apply')
        with pytest.raises(ValueError):propose_memory(c,OWNER,draft(kind='recipe',revision=candidate.id))
        record_outcome(c,OWNER,candidate.id,True)
        recipe=propose_memory(c,OWNER,draft(kind='recipe',revision=candidate.id))
        confirm_memory(c,OWNER,recipe.id,recipe.content_hash)
    assert save_memory(phase2_db.writer,OWNER,recipe.id,client).status=='saved'
    with phase2_db.writer.begin() as c:
        revised=update_memory(c,OWNER,recipe.id,draft('Focus on selected open deals and avoid broad increases.',kind='recipe',revision=candidate.id))
        assert revised.status=='proposed'
        with pytest.raises(ValueError):confirm_memory(c,OWNER,recipe.id,recipe.content_hash)
    with pytest.raises(ValueError):save_memory(phase2_db.writer,OWNER,recipe.id,client)


def test_memory_rejects_raw_records_and_cross_owner(phase2_db):
    from app.memory.service import propose_memory
    from app.scenarios.contracts import OwnerContext
    prepare_memory(phase2_db)
    with phase2_db.writer.begin() as c:
        with pytest.raises(ValueError):propose_memory(c,OWNER,draft('Remember opportunities-0001 has $50000 revenue.'))
        with pytest.raises(ValueError):propose_memory(c,OwnerContext(owner_id='another',workspace_id='local'),draft())


def test_missing_allowance_keeps_confirmation_retryable_without_dispatch(phase2_db):
    from app.memory.service import propose_memory,confirm_memory,save_memory
    from app.memory.repository import get
    prepare_memory(phase2_db);client=FakeMemory()
    with phase2_db.admin.begin() as c:c.execute(text('DELETE FROM studio_memory_allowance'))
    with phase2_db.writer.begin() as c:
        item=propose_memory(c,OWNER,draft());confirm_memory(c,OWNER,item.id,item.content_hash)
    with pytest.raises(ValueError):save_memory(phase2_db.writer,OWNER,item.id,client)
    assert not client.items
    with phase2_db.reader.connect() as c:assert get(c,OWNER,item.id).status=='confirmed'


def test_retrieval_is_bounded_and_rejects_changed_meaning_or_scope(phase2_db):
    from app.memory.service import propose_memory,confirm_memory,save_memory,search_memory
    prepare_memory(phase2_db);client=FakeMemory()
    for label in ['small','large','open','recent','important','regional']:
        with phase2_db.writer.begin() as c:
            item=propose_memory(c,OWNER,draft(f'Focus on {label} opportunities during leadership demos.'))
            confirm_memory(c,OWNER,item.id,item.content_hash)
        save_memory(phase2_db.writer,OWNER,item.id,client)
    with phase2_db.writer.begin() as c:assert len(search_memory(c,OWNER,draft().scope,'review',client))==5
    for value in client.items.values():value['memory']='A different meaning'
    with phase2_db.writer.begin() as c:assert search_memory(c,OWNER,draft().scope,'review',client)==[]


def test_forget_during_remote_save_never_resurrects_memory(phase2_db):
    from app.memory.service import propose_memory,confirm_memory,save_memory,forget_memory,search_memory,delete_memory
    prepare_memory(phase2_db)
    with phase2_db.writer.begin() as c:
        item=propose_memory(c,OWNER,draft());confirm_memory(c,OWNER,item.id,item.content_hash)
    class ForgetDuringSave(FakeMemory):
        def add(self,*args):
            result=super().add(*args)
            with phase2_db.writer.begin() as c:forget_memory(c,OWNER,item.id)
            return result
    client=ForgetDuringSave()
    assert save_memory(phase2_db.writer,OWNER,item.id,client).status=='deletion-pending'
    with phase2_db.writer.begin() as c:assert search_memory(c,OWNER,draft().scope,'review',client)==[]
    assert delete_memory(phase2_db.writer,OWNER,item.id,client).status=='deleted'
