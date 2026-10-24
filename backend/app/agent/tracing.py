"""Allowlisted local spans. Never log prompts, table rows, credentials or reasoning."""
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from uuid import uuid4
import json,os,time

CURRENT_SPAN=ContextVar('studio_span',default=None)

ALLOWED={'provider','model_version','prompt_version','tool_version','input_tokens','output_tokens','estimated_credit','settled_credit','status','error_code','candidate_id','tool_name'}

@contextmanager
def span(run_id,parent_id,name,attributes,*,span_id=None):
    started=time.monotonic();id=span_id or str(uuid4())
    parent_id=parent_id or CURRENT_SPAN.get()
    token=CURRENT_SPAN.set(id)
    record={'id':id,'run_id':run_id,'parent_id':parent_id,'name':name,
            'attributes':{k:v for k,v in attributes.items() if k in ALLOWED and isinstance(v,(str,int,float,bool,type(None)))}}
    try:
        yield id
        record['status']='ok'
    except BaseException as exc:
        record.update(status='error',error_type=type(exc).__name__)
        raise
    finally:
        CURRENT_SPAN.reset(token)
        record['duration_ms']=round((time.monotonic()-started)*1000,2)
        directory=Path(os.environ.get('STUDIO_TRACE_DIR',str(Path(__file__).resolve().parents[3]/'.local/traces')))
        directory.mkdir(parents=True,exist_ok=True,mode=0o700)
        fd=os.open(directory/'spans.jsonl',os.O_WRONLY|os.O_APPEND|os.O_CREAT,0o600)
        with os.fdopen(fd,'a') as output:output.write(json.dumps(record)+'\n')
