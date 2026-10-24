"""Run the local private foundation; credentials never enter frontend assets."""
import json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
from dotenv import load_dotenv
load_dotenv(ROOT/'.env')
os.environ['STUDIO_LOCAL']='1'
writer=ROOT/'.local/writer-url'
if writer.exists() and (not os.getenv('STUDIO_WRITER_DATABASE_URL') or os.environ['STUDIO_WRITER_DATABASE_URL'].startswith('REPLACE_')):
    os.environ['STUDIO_WRITER_DATABASE_URL']=writer.read_text().strip()
os.environ.update(json.loads((ROOT/'.local/auth.json').read_text()))
sys.path.insert(0,str(ROOT/'backend'))
import uvicorn
uvicorn.run('app.main:app',host='127.0.0.1',port=8010)
