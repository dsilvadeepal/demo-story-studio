from contextlib import contextmanager
import psycopg
from psycopg.rows import dict_row
from langgraph.checkpoint.postgres import PostgresSaver
from sqlalchemy import text


def _connection(database):
    url=database.url
    return psycopg.connect(host=url.host,port=url.port,dbname=url.database,user=url.username,password=url.password,autocommit=True,row_factory=dict_row)


@contextmanager
def checkpoint_store(database):
    with _connection(database) as connection:yield PostgresSaver(connection)


def setup_checkpoints(admin,writer_role):
    # DDL is exclusively a privileged setup operation.
    with checkpoint_store(admin) as saver:saver.setup()
    with admin.begin() as c:
        role=c.dialect.identifier_preparer.quote(writer_role)
        c.execute(text(f'GRANT SELECT,INSERT,UPDATE,DELETE ON checkpoints,checkpoint_blobs,checkpoint_writes TO {role}'))
        c.execute(text(f'GRANT SELECT ON checkpoint_migrations TO {role}'))

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from sqlalchemy.exc import DBAPIError
from langchain_core.messages import HumanMessage,RemoveMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.types import Command
from ..scenarios.repository import canonical
from ..contracts import Period
from ..scenarios.lifecycle import ScenarioError
from ..memory.repository import list_items
from .contracts import RunContext,RunStatus,RunScope,ProviderConfig
from .graph import build_graph
from .registry import build_tools
from .provider import build_model,invoke_bounded,bind_studio_tools,select_studio_tools
from .tracing import span

EXECUTOR=ThreadPoolExecutor(max_workers=1,thread_name_prefix='studio-agent')


def _transition(c,owner,action,payload):
    try:
        with c.begin_nested():
            return c.scalar(text('SELECT studio_run(:o,:w,:a,CAST(:p AS jsonb))'),dict(o=owner.owner_id,w=owner.workspace_id,a=action,p=canonical(payload)))
    except DBAPIError:raise ScenarioError('RUN_UNAVAILABLE') from None


def _status(row):return RunStatus(**{k:row[k] for k in RunStatus.model_fields})


class BoundedModel:
    def __init__(self,context):
        with context.database.connect() as c:
            credit=c.execute(text('SELECT provider,model FROM studio_credit WHERE credit_only AND verified_until>now() ORDER BY provider')).mappings().first()
        if not credit:raise ScenarioError('BUDGET_UNAVAILABLE')
        self.context=context;self.config=ProviderConfig(**dict(credit))
        self.model=build_model(self.config)
    def invoke(self,messages):
        ctx=self.context
        return invoke_bounded(ctx.database,ctx.owner,ctx.run_id,self.config,bind_studio_tools(self.model,select_studio_tools(build_tools(ctx),messages)),messages)


class Runner:
    def __init__(self,database,model_factory=None,enqueue=True):
        self.database=database;self.model_factory=model_factory or BoundedModel;self.enqueue=enqueue
    def _row(self,owner,id):
        with self.database.connect() as c:
            row=c.execute(text('SELECT * FROM studio_runs WHERE id=:id AND owner_id=:o AND workspace_id=:w'),dict(id=id,o=owner.owner_id,w=owner.workspace_id)).mappings().first()
        if not row:raise ScenarioError('RUN_UNAVAILABLE')
        return dict(row)
    def get_run(self,owner,id):
        self.recover_expired(owner)
        return _status(self._row(owner,id))
    def _schedule(self,owner,id):
        if self.enqueue:EXECUTOR.submit(self.execute,owner,id)
    def start_run(self,owner,brief,scope,parent_id):
        if not isinstance(brief,str) or not 1<=len(brief.strip())<=2000:raise ValueError('Brief must contain one to two thousand characters')
        scope=RunScope.model_validate(scope)
        id=str(uuid4())
        with self.database.begin() as c:row=_transition(c,owner,'start',dict(id=id,brief=brief,parent_id=parent_id,scope=scope.model_dump()))
        with span(id,None,'run',{'status':'queued'},span_id=id):pass
        self._schedule(owner,id)
        return _status(row)
    def resume_run(self,owner,id,input):
        row=self._row(owner,id)
        kind=row['result'].get('interrupt',{}).get('kind')
        if row['status']=='paused' and ((kind=='clarification' and input.kind!='clarify') or (kind=='review' and input.kind not in ('refine','finish'))):raise ScenarioError('RUN_UNAVAILABLE')
        if input.kind in ('clarify','refine') and not input.text.strip():raise ValueError('A clarification or refinement needs text')
        with self.database.begin() as c:row=_transition(c,owner,'resume',dict(id=id,input=input.model_dump()))
        self._schedule(owner,id)
        return _status(row)
    def cancel_run(self,owner,id):
        with self.database.begin() as c:return _status(_transition(c,owner,'cancel',dict(id=id)))
    def ignore_memory(self,owner,id,ids):
        try:
            with self.database.begin() as c:
                c.execute(text('SELECT studio_ignore_memory(:o,:w,:id,CAST(:ids AS jsonb))'),dict(o=owner.owner_id,w=owner.workspace_id,id=id,ids=canonical(ids)))
        except DBAPIError:raise ScenarioError('MEMORY_UNAVAILABLE') from None
        return self.get_run(owner,id)
    def recover_expired(self,owner,startup=False):
        with self.database.connect() as c:
            rows=c.execute(text("SELECT id,status FROM studio_runs WHERE owner_id=:o AND workspace_id=:w AND ((status='running' AND lease_until<now()) OR (:startup AND status IN ('queued','retrying')))"),dict(o=owner.owner_id,w=owner.workspace_id,startup=startup)).mappings().all()
        for row in rows:
            with _connection(self.database) as lock:
                key='run:'+row['id']
                if not lock.execute('SELECT pg_try_advisory_lock(hashtextextended(%s,1)) AS ok',(key,)).fetchone()['ok']:continue
                try:
                    with self.database.begin() as c:
                        if row['status']=='running':_transition(c,owner,'expire',dict(id=row['id']))
                        else:c.execute(text('SELECT studio_interrupt_queued(:o,:w,:r)'),dict(o=owner.owner_id,w=owner.workspace_id,r=row['id']))
                finally:lock.execute('SELECT pg_advisory_unlock(hashtextextended(%s,1))',(key,))
    def execute(self,owner,id):
        with _connection(self.database) as lock:
            acquired=lock.execute('SELECT pg_try_advisory_lock(hashtextextended(%s,1)) AS acquired',('run:'+id,)).fetchone()['acquired']
            if not acquired:return self.get_run(owner,id)
            try:
                existing=self._row(owner,id)
                if existing['status'] not in ('queued','retrying'):return _status(existing)
                with self.database.begin() as c:row=_transition(c,owner,'claim',dict(id=id))
                if row['status']!='running':return _status(row)
                # A previous executor's unexpired running lease is not a new claim.
                ctx=RunContext(owner=owner,dataset_id=row['parent_id'],domain=row['scope']['domain'],run_id=id,thread_id=id,database=self.database,audience=row['scope'].get('audience','general'),intent=row['scope'].get('intent','demo preparation'),ignored_memory_ids=tuple(row['scope'].get('ignored_memory_ids',[])),filters=row['scope'].get('filters',{}),period=Period.model_validate(row['scope']['period']) if row['scope'].get('period') else None)
                try:
                    with span(id,id,'execution',{'status':'running'}),checkpoint_store(self.database) as saver:
                        graph=build_graph(self.model_factory(ctx),build_tools(ctx),saver,context=ctx)
                        cfg={'configurable':{'thread_id':id},'recursion_limit':60}
                        previous=graph.get_state(cfg)
                        if previous.values:
                            # Every consumed memory is pinned to its exact confirmed wording.
                            with self.database.connect() as c:live={x.id:x.content_hash for x in list_items(c,owner) if x.status=='saved' and x.id not in ctx.ignored_memory_ids}
                            used=previous.values.get('memory_versions',{})
                            changed=any(id not in live or id not in used or live[id]!=used[id] for id in previous.values.get('memory_ids',[]))
                            if changed:
                                humans=[m for m in previous.values.get('messages',[]) if isinstance(m,HumanMessage)]
                                graph.update_state(cfg,{'messages':[RemoveMessage(id=REMOVE_ALL_MESSAGES),*humans],'memory_ids':[],'memory_versions':{}})
                            answer=row['resume_input']
                            if changed and answer and answer.get('kind') in ('finish','retry'):answer={'kind':'refine','text':'Previously used guidance changed or was forgotten. Inspect again and prepare a fresh proposal using current owner instructions.'}
                            payload=Command(resume=answer) if row['interrupt_id'] and answer else None
                        else:payload=dict(messages=[HumanMessage(content=row['brief'])],run_id=id,thread_id=id,budget_reference=id)
                        result=graph.invoke(payload,cfg)
                        interrupts=result.get('__interrupt__',())
                        interruption=interrupts[0] if interrupts else None
                        safe={k:v for k,v in result.items() if k not in ('messages','__interrupt__')}
                        if interruption:safe['interrupt']=interruption.value
                        status='paused' if interruption else 'complete'
                        if safe.get('review_state',{}).get('status') in ('limit_reached','cancelled'):status='failed'
                        with self.database.begin() as c:row=_transition(c,owner,'finish',dict(id=id,version=row['version'],status=status,result=safe,interrupt_id=interruption.id if interruption else None))
                except Exception as error:
                    code=error.code if isinstance(error,ScenarioError) else 'RUN_UNAVAILABLE'
                    with self.database.begin() as c:row=_transition(c,owner,'finish',dict(id=id,version=row['version'],status='interrupted' if code=='OUTCOME_UNKNOWN' else 'failed',result={'error':code}))
                return _status(row)
            finally:
                lock.execute('SELECT pg_advisory_unlock(hashtextextended(%s,1))',('run:'+id,))
