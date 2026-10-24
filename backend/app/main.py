import os
from pathlib import Path
from fastapi import FastAPI,Depends,Request,Response,HTTPException
from fastapi.responses import FileResponse,JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field,ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from .auth import require_owner,verify_password,signer,check_origin,rate_limit
from .db import engine,manifest,ROOT
from .catalog import catalog,FILTERS
from .contracts import QueryRequest,RecordRequest
from .queries.analytics import query,dataset,read_facts,serialize
from .queries.records import list_records,get_record
app=FastAPI(title='Demo Story Studio',version='1.0.0',docs_url=None,redoc_url=None,openapi_url=None)
class Login(BaseModel):
    model_config=ConfigDict(extra='forbid')
    password:str=Field(min_length=1,max_length=256)
@app.middleware('http')
async def security(request:Request,call_next):
    if request.method not in ['GET','HEAD','OPTIONS']:
        try: check_origin(request)
        except HTTPException as exc:return JSONResponse({'detail':exc.detail},status_code=exc.status_code)
    response=await call_next(request)
    response.headers['Cache-Control']='no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='same-origin'
    return response
@app.exception_handler(ValueError)
async def validation_error(request,exc): return JSONResponse({'detail':str(exc),'code':'INVALID_QUERY'},status_code=422)
@app.exception_handler(LookupError)
async def missing_error(request,exc): return JSONResponse({'detail':str(exc),'code':'NOT_FOUND'},status_code=404)
@app.exception_handler(DBAPIError)
async def database_error(request,exc): return JSONResponse({'detail':'Query could not complete. Retry or narrow your filters.','code':'QUERY_UNAVAILABLE'},status_code=503)
@app.post('/api/login')
def login(body:Login,request:Request,response:Response):
    rate_limit(request)
    if not verify_password(body.password): raise HTTPException(401,'Incorrect password')
    response.set_cookie('studio_session',signer().dumps({'owner':True}),httponly=True,secure=os.getenv('STUDIO_LOCAL')!='1',samesite='strict',max_age=28800)
    return {'authenticated':True}
@app.post('/api/logout')
def logout(response:Response):
    response.delete_cookie('studio_session'); return {'authenticated':False}
@app.get('/api/session',dependencies=[Depends(require_owner)])
def session(): return {'authenticated':True}
@app.get('/api/v1/dataset',dependencies=[Depends(require_owner)])
def get_dataset(dataset_id:str|None=None):
    with engine().connect() as c:
        from .scenarios.repository import get_active,get_candidate
        from .scenarios.api import OWNER
        candidate=get_candidate(c,OWNER,dataset_id) if dataset_id else get_active(c,OWNER)
        row=c.execute(select(manifest).where(manifest.c.id==candidate.id)).mappings().first()
        if not row: raise HTTPException(503,'Seed the baseline first')
        return serialize(dict(row))
@app.get('/api/v1/catalog',dependencies=[Depends(require_owner)])
def get_catalog(dataset_id:str|None=None):
    out=catalog(); out['options']={}
    with engine().connect() as c:
        from .scenarios.repository import get_active,get_candidate
        from .scenarios.api import OWNER
        ds=(get_candidate(c,OWNER,dataset_id) if dataset_id else get_active(c,OWNER)).id
        for domain in ['sales','service']:
            rows,_=read_facts(c,QueryRequest(dashboard=domain,dataset_id=ds))
            out['options'][domain]={k:sorted({r[k] for r in rows}) for k in FILTERS[domain]}
    return out
@app.post('/api/v1/query',dependencies=[Depends(require_owner)])
def run_query(body:QueryRequest):
    with engine().connect() as c:return query(c,body)
@app.post('/api/v1/records',dependencies=[Depends(require_owner)])
def records(body:RecordRequest):
    with engine().connect() as c:return list_records(c,body)
@app.get('/api/v1/records/{entity}/{id}',dependencies=[Depends(require_owner)])
def record(entity:str,id:str,dataset_id:str):
    with engine().connect() as c:return get_record(c,dataset_id,entity,id)
@app.get('/api/v1/openapi.json',dependencies=[Depends(require_owner)])
def schema():return app.openapi()
# The public bootstrap contains no data or secret; the session gate protects every API.
DIST=ROOT/'frontend/dist'
if (DIST/'assets').exists(): app.mount('/assets',StaticFiles(directory=DIST/'assets'),name='assets')
@app.get('/')
def index():
    if not (DIST/'index.html').exists():return JSONResponse({'detail':'Build the frontend first'},status_code=503)
    return FileResponse(DIST/'index.html')

from .scenarios.api import router as scenario_router
from .scenarios.lifecycle import ScenarioError
app.include_router(scenario_router)
from .memory.api import router as memory_router
app.include_router(memory_router)
from .agent.api import router as agent_router
app.include_router(agent_router)

@app.on_event("startup")
def recover_agent_runs():
    if os.getenv("STUDIO_WRITER_DATABASE_URL"):
        from .agent.api import runner
        from .scenarios.api import OWNER
        runner().recover_expired(OWNER,startup=True)
@app.exception_handler(ScenarioError)
async def scenario_error(request,exc):
    status=409 if exc.code in ('STALE_VERSION','APPROVAL_REQUIRED') else 403 if exc.code=='INVALID_SCOPE' else 422
    return JSONResponse({'detail':str(exc),'code':exc.code},status_code=status)
