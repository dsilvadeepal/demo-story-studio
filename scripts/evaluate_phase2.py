"""Run sanitized fixed evaluations; live mode enforces verified credit gates."""
import argparse,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from app.agent.evaluation import evaluate_offline,evaluate_live

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['offline','live'],required=True);parser.add_argument('--provider',choices=['nebius','fireworks'],default='nebius');parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.mode=='offline':result=evaluate_offline()
    else:
        from dotenv import load_dotenv
        load_dotenv(ROOT/'.env')
        value=os.getenv('STUDIO_WRITER_DATABASE_URL','')
        if not value or value.startswith('REPLACE_'):os.environ['STUDIO_WRITER_DATABASE_URL']=(ROOT/'.local/writer-url').read_text().strip()
        from app.db import writer_engine
        result=evaluate_live(writer_engine(),args.provider)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('mode','status','provider_calls')}))
    return 0 if result['status']=='complete' else 2
if __name__=='__main__':raise SystemExit(main())
