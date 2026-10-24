"""Fixed synthetic evaluation: offline transforms are never live model evidence."""
import json,time
from decimal import Decimal
from pathlib import Path
from sqlalchemy import text
from ..seed import generate
from ..scenarios.contracts import Proposal,OwnerContext
from ..scenarios.operations import transform
from ..scenarios.validation import validate_candidate
from ..scenarios.repository import digest

ROOT=Path(__file__).resolve().parents[3]
OWNER=OwnerContext(owner_id='owner',workspace_id='local')

def load_cases():return json.loads((ROOT/'evals/phase2_cases.json').read_text())

def case_proposal(case,parent):return Proposal(parent_id=parent,selection=case['selection'],operations=case['operations'])

def evaluate_offline():
    bundle=generate();results=[];adversarial=[]
    for case in load_cases()['standard']:
        begin=time.monotonic();proposal=case_proposal(case,bundle['manifest']['id'])
        before=digest(bundle);changed=transform(bundle,proposal)
        report=validate_candidate(bundle,changed,proposal)
        passed=not report.hard_errors and digest(bundle)==before
        results.append(dict(id=case['id'],passed=passed,hard_errors=report.hard_errors,active_seconds=round(time.monotonic()-begin,4),human_seconds=0,clarifications=0,corrections=0,model_calls=0,tokens=None,estimated_credit='0',settled_credit='0',memory_references=[]))
    for case in load_cases()['adversarial']:
        try:transform(bundle,case_proposal(case,bundle['manifest']['id']));rejected=False
        except ValueError:rejected=True
        adversarial.append(dict(id=case['id'],passed=rejected))
    return dict(mode='offline',status='complete',method='deterministic transformation and independent invariants; no model',live_acceptance='pending',passed=sum(r['passed'] for r in results),provider_calls=0,cases=results,adversarial=adversarial)


def evaluate_live(database,provider):
    from .runner import Runner,_connection
    from .provider import build_model,bind_studio_tools,invoke_bounded,select_studio_tools
    from .registry import build_tools
    from .contracts import ProviderConfig
    from ..scenarios.repository import read_bundle
    from ..scenarios.lifecycle import ScenarioError
    with database.connect() as c:
        credit=c.execute(text('SELECT * FROM studio_credit WHERE provider=:p AND credit_only AND verified_until>now() AND balance>0'),{'p':provider}).mappings().first()
    if not credit:return dict(mode='live',status='blocked',reason='Verified credit-only provider configuration is unavailable',provider=provider,provider_calls=0,cases=[],live_acceptance='pending')
    # All evaluation calls, across providers and processes, share this separate lock.
    with _connection(database) as lock:
        if not lock.execute('SELECT pg_try_advisory_lock(61820261024) AS ok').fetchone()['ok']:
            return dict(mode='live',status='blocked',reason='Another evaluation is active',provider_calls=0,cases=[],live_acceptance='pending')
        try:
            config=ProviderConfig(provider=provider,model=credit['model'])
            def spent(c):
                return c.scalar(text("SELECT coalesce(sum(coalesce(actual,reserved)),0) FROM studio_reservations r JOIN studio_runs s ON s.id=r.run_id WHERE s.scope->>'intent'='phase two evaluation'"))
            with database.connect() as c:
                eligible=c.scalar(text('SELECT coalesce(sum(balance),0) FROM studio_credit WHERE credit_only AND verified_until>now()'))
                cap=min(Decimal('1'),eligible/10)
                initial_count=c.scalar(text('SELECT count(*) FROM studio_reservations'))
            class EvaluatedModel:
                def __init__(self,ctx):
                    self.ctx=ctx;self.model=build_model(config)
                def invoke(self,messages):
                    worst=(Decimal(config.max_input_tokens)*credit['input_rate']+Decimal(config.max_output_tokens)*credit['output_rate'])/1000000
                    with database.connect() as c:
                        if spent(c)+worst>cap:raise ScenarioError('LIMIT_REACHED')
                    return invoke_bounded(database,OWNER,self.ctx.run_id,config,bind_studio_tools(self.model,select_studio_tools(build_tools(self.ctx),messages)),messages)
            runner=Runner(database,model_factory=EvaluatedModel,enqueue=False)
            results=[]
            for case in load_cases()['standard']:
                # Each case uses the same immutable seeded parent, never an earlier model result.
                parent=generate()['manifest']['id']
                run=runner.start_run(OWNER,case['brief'],dict(domain=case['selection']['dashboard'],intent='phase two evaluation'),parent)
                result=runner.execute(OWNER,run.id)
                with database.connect() as c:
                    costs=c.execute(text('SELECT input_tokens,output_tokens,reserved,actual,status,usage FROM studio_reservations WHERE run_id=:id'),{'id':run.id}).mappings().all()
                    candidate=result.result.get('candidate_id');passed=False;hard_errors=[]
                    if candidate:
                        original=read_bundle(c,OWNER,parent);actual=read_bundle(c,OWNER,candidate)
                        expected=transform(original,case_proposal(case,parent))
                        hard_errors=validate_candidate(original,actual,case_proposal(case,parent)).hard_errors
                        # Dataset identities legitimately differ; business values must be exact.
                        def values(bundle):return {k:[{f:v for f,v in r.items() if f!='dataset_id'} for r in rows] for k,rows in bundle['tables'].items()}
                        passed=not hard_errors and digest(values(actual))==digest(values(expected)) and actual['manifest']['as_of_date']==expected['manifest']['as_of_date']
                results.append(dict(id=case['id'],run_id=run.id,status=result.status,passed=passed,hard_errors=hard_errors,clarifications=int(result.result.get('interrupt',{}).get('kind')=='clarification'),corrections=0,active_seconds=result.result.get('active_seconds'),human_seconds=0,model_calls=len(costs),tokens=[r['usage'] for r in costs],estimated_credit=str(sum(r['reserved'] for r in costs)),settled_credit=None if any(r['actual'] is None for r in costs) else str(sum(r['actual'] for r in costs)),memory_references=result.result.get('memory_ids',[])))
                if any(r['status']=='unknown' for r in costs) or result.result.get('error') in ('BUDGET_UNAVAILABLE','LIMIT_REACHED','OUTCOME_UNKNOWN'):break
            with database.connect() as c:count=c.scalar(text('SELECT count(*) FROM studio_reservations'))-initial_count
            return dict(mode='live',status='complete' if len(results)==10 else 'stopped',provider=provider,model=config.model,passed=sum(r['passed'] for r in results),provider_calls=count,cases=results,adversarial=[],live_acceptance='passed' if len(results)==10 and sum(r['passed'] for r in results)>=9 else 'pending',activation='No candidates activated by evaluator',evaluation_cap=str(cap))
        finally:lock.execute('SELECT pg_advisory_unlock(61820261024)')
