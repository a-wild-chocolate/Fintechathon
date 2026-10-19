from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from .parsing import parse
from .vision import IMAGE_TYPES
from fastapi import FastAPI,UploadFile,File,Form,Request,BackgroundTasks
from fastapi.responses import FileResponse,JSONResponse
from pydantic import BaseModel,Field
from typing import Literal
import httpx
from .config import Settings
from .service import Library,Conflict,NotFound,AccessDenied
from .assistant import Assistant
from .agents.runtime import AgentRuntime
from .agents.human import HumanAnswer
from .agents.workflows import Workspace
from .business_records import CompanyInput, OrderInput
import re
import json
import time

class Query(BaseModel):
    query:str=Field(min_length=1,max_length=2000)
    market:str|None=None
    as_of:str|None=None
    limit:int=Field(default=5,ge=1,le=20)
    mode:str='hybrid'
    document_id:str|None=None
    order_id:str|None=None
class PriorTurn(BaseModel):
    question:str=Field(max_length=2000)
    answer:str=Field(max_length=6000)
class ChatRequest(BaseModel):
    question:str=Field(min_length=1,max_length=2000)
    language:Literal['zh','en']='zh'
    document_id:str|None=None
    order_id:str|None=None
    market:str|None=None
    history:list[PriorTurn]=Field(default_factory=list,max_length=4)
    session_id:str|None=None
    workspace:Workspace|None=None
class HumanReply(BaseModel):
    answers:list[HumanAnswer]=Field(min_length=1,max_length=3)
    language:Literal['zh','en']='zh'

class BusinessViewRequest(BaseModel):
    revision:int=Field(ge=0)
    workspace:dict

class LeaseRequest(BaseModel):seconds:int=Field(default=120,ge=1,le=3600)
class SaveRequest(BaseModel):
    token:str
    base_version:int
    filename:str
    text:str
class ReleaseRequest(BaseModel):token:str
class TextUpload(BaseModel):
    filename:str
    title:str
    text:str
    order_id:str|None=None

class AgentToolRequest(BaseModel):
    run_id:str
    role:str
    arguments:dict=Field(default_factory=dict)

def create_app(settings=None,library=None,agent_model=None,agent_connector=None):
    settings=settings or Settings()
    @asynccontextmanager
    async def lifespan(app):
        app.state.library=library or Library(settings);app.state.library.start_worker()
        app.state.assistant=Assistant(app.state.library,settings)
        app.state.agents=AgentRuntime(app.state.library,agent_model,agent_connector)
        yield
        app.state.library.close()
    app=FastAPI(title='CashWeave Evidence Library',version='0.1.0',lifespan=lifespan)
    @app.middleware('http')
    async def company_context(request:Request, call_next):
        tenant=settings.tenant
        match=re.match(r'^/api/companies/([^/]+)(/.*)$',request.scope['path'])
        if match:
            tenant=match[1]
            try: app.state.agents.store.business.check_company(settings.tenant,tenant)
            except NotFound as exc: return JSONResponse({'detail':str(exc)},status_code=404)
            request.scope['path']='/api'+match[2]
            request.scope['raw_path']=request.scope['path'].encode()
        request.state.tenant=tenant
        request.state.agents=app.state.agents if tenant==settings.tenant else app.state.agents.for_company(tenant)
        request.state.assistant=Assistant(request.state.agents.library,request.state.agents.library.settings)
        return await call_next(request)

    @app.exception_handler(ValueError)
    async def value_error(request,exc):
        status=409 if isinstance(exc,Conflict) else 404 if isinstance(exc,NotFound) else 403 if isinstance(exc,AccessDenied) else 400
        return JSONResponse({'detail':str(exc)},status_code=status)
    @app.get('/')
    def home(request:Request):return FileResponse(Path(__file__).with_name('workbench.html'))
    @app.get('/api/health')
    def health(request:Request):return app.state.library.stats(request.state.tenant)
    @app.get('/api/assistant/status')
    def assistant_status(request:Request):
        return request.state.agents.status() if request.state.agents.enabled else app.state.assistant.status()
    @app.post('/api/assistant/chat')
    def chat(request:Request, body:ChatRequest):
        try:
            if request.state.agents.enabled:
                return request.state.agents.answer(**body.model_dump())
            return request.state.assistant.answer(**body.model_dump(exclude={'session_id', 'workspace'}))
        except httpx.HTTPError:
            return JSONResponse({'detail':'Model request failed. Check model configuration and retry.'},status_code=502)
    @app.post('/api/assistant/runs', status_code=202)
    def start_agent_run(request:Request, body:ChatRequest, background:BackgroundTasks):
        runtime=request.state.agents
        if not runtime.enabled:
            return JSONResponse({'detail':'Multi-agent service is not enabled.'},status_code=409)
        prepared=runtime.prepare(**body.model_dump())
        background.add_task(runtime.execute,*prepared)
        return {'run_id':prepared[0],'session_id':prepared[1],'status':'running'}
    @app.post('/api/agents/runs/{run_id}/answers', status_code=202)
    def answer_agent_questions(request:Request, run_id:str, body:HumanReply, background:BackgroundTasks):
        runtime=request.state.agents
        response, prepared=runtime.store.respond(run_id,request.state.tenant,body.answers,body.language)
        if prepared: background.add_task(runtime.execute,*prepared)
        return response
    @app.get('/api/agents/runs/{run_id}/progress')
    def agent_progress(request:Request, run_id:str):
        run=request.state.agents.store.run(run_id,request.state.tenant)
        events=[{k:event[k] for k in ('event','agent','tool','status','timestamp') if k in event} for event in run['trace']]
        return {'run_id':run_id,'session_id':run['session_id'],'status':run['status'],
                'created_at':run['created_at'],'trace':events,'result':run['result']}
    @app.get('/api/agents/status')
    def agents_status(request:Request):return request.state.agents.status()
    @app.get('/api/agents/runs/{run_id}')
    def agent_run(request:Request, run_id:str):return request.state.agents.store.run(run_id,request.state.tenant)
    @app.get('/api/agents/workspace')
    def agent_workspace(request:Request):return {'workspace':request.state.agents.store.workspace(request.state.tenant)}
    @app.post('/api/agents/proposals/{proposal_id}/confirm')
    def confirm_agent_proposal(request:Request, proposal_id:str):return request.state.agents.workflows.confirm(proposal_id)
    @app.post('/api/agent-tools/{name}')
    def agent_tool(request:Request, name:str,body:AgentToolRequest):
        with app.state.agents.store.db.connect() as db:
            run=db.execute('SELECT tenant FROM agent_runs WHERE id=?',(body.run_id,)).fetchone()
        if not run: raise NotFound('Run not found.')
        if run['tenant']!=settings.tenant: app.state.agents.store.business.check_company(settings.tenant,run['tenant'])
        return app.state.agents.for_company(run['tenant']).workflows.execute(name,body.run_id,body.role,body.arguments)
    @app.get('/api/companies')
    def companies(): return app.state.agents.store.business.list_companies(settings.tenant)
    @app.post('/api/companies',status_code=201)
    def create_company(body:CompanyInput): return app.state.agents.store.business.create_company(settings.tenant,body)
    @app.get('/api/business/overview')
    def overview(request:Request): return app.state.agents.store.business.overview(request.state.tenant)
    @app.post('/api/business/orders/preview')
    def preview_order(request:Request,body:OrderInput,create:bool=True):
        return app.state.agents.store.business.save_order(request.state.tenant,body,create=create,preview=True)
    @app.post('/api/business/orders',status_code=201)
    def create_order(request:Request,body:OrderInput):
        return app.state.agents.store.business.save_order(request.state.tenant,body,create=True)
    @app.put('/api/business/orders/{order_id}')
    def update_order(request:Request,order_id:str,body:OrderInput):
        if order_id!=body.id: raise ValueError('Order number cannot change during editing.')
        return app.state.agents.store.business.save_order(request.state.tenant,body,create=False)
    @app.get('/api/business/view')
    def get_view(request:Request):
        with app.state.agents.store.db.connect() as db:
            row=db.execute("SELECT * FROM workspace_views WHERE company_id=? AND view_key='business'",(request.state.tenant,)).fetchone()
        return {'revision':row['revision'] if row else 0,'workspace':json.loads(row['payload']) if row else None}
    @app.put('/api/business/view')
    def put_view(request:Request,body:BusinessViewRequest):
        with app.state.agents.store.db.connect(write=True) as db:
            row=db.execute("SELECT revision FROM workspace_views WHERE company_id=? AND view_key='business'",(request.state.tenant,)).fetchone()
            if body.revision!=(row['revision'] if row else 0): raise Conflict('Conversation updated in another window. Reload to continue.')
            db.execute('INSERT OR REPLACE INTO workspace_views VALUES(?,?,?,?,?)',(request.state.tenant,'business',body.revision+1,json.dumps(body.workspace),time.time()))
        return {'revision':body.revision+1}
    @app.get('/api/business')
    def business_records(request:Request):return request.state.agents.store.business.records(request.state.tenant)
    @app.get('/api/business/workspace')
    def business_view(request:Request, key:str='main'):
        return request.state.agents.store.business.view(request.state.tenant,key)
    @app.put('/api/business/workspace')
    def save_business_view(request:Request, body:BusinessViewRequest,key:str='main'):
        flow=body.workspace['flow']
        for record in (flow.get('setup') or {}).get('records',{}).values():
            doc=app.state.library.document(record['documentId'],request.state.tenant)
            record['version']=doc['current_version']
        if not flow.get('setup') or flow['setup'].get('complete'):
            Workspace.model_validate({**flow, 'amountUSD':(flow.get('partialReceipt') or {}).get('amountUSD',12000)})
        return request.state.agents.store.business.save_view(request.state.tenant,key,body.revision,body.workspace)
    @app.get('/api/documents')
    def documents(request:Request):return app.state.library.list_documents(request.state.tenant)
    @app.post('/api/document-preview')
    async def document_preview(request:Request, file:UploadFile=File(...)):
        suffix = Path(file.filename).suffix.lower()
        if suffix not in {'.txt', '.docx'}:
            raise ValueError('Baseline records must be TXT or DOCX files.')
        data = await file.read(20*1024*1024+1)
        if len(data) > 20*1024*1024:
            raise ValueError('Maximum file size is 20 MB')
        with NamedTemporaryFile(suffix=suffix) as source:
            source.write(data)
            source.flush()
            blocks = parse(Path(source.name))
        return {'text': '\n'.join(block['text'] for block in blocks)}
    @app.post('/api/uploads',status_code=202)
    async def upload(request:Request, file:UploadFile=File(...),title:str=Form(''),order_id:str=Form('')):
        data=await file.read(20*1024*1024+1)
        if len(data)>20*1024*1024:raise ValueError('Maximum file size is 20 MB')
        return app.state.library.create(file.filename,data,title or file.filename,request.state.tenant,{'order_id':order_id,'source_kind':'user_upload'})
    @app.post('/api/text-uploads',status_code=202)
    def text_upload(request:Request, body:TextUpload):
        return app.state.library.create(body.filename,body.text.encode(),body.title,request.state.tenant,{'order_id':body.order_id,'source_kind':'user_upload'})
    @app.get('/api/documents/{document_id}')
    def document(request:Request, document_id:str):return app.state.library.document(document_id,request.state.tenant)
    @app.get('/api/documents/{document_id}/versions/{version}')
    def document_version(request:Request, document_id:str,version:int):return app.state.library.document(document_id,request.state.tenant,version)
    @app.get('/api/documents/{document_id}/versions/{version}/original')
    def original(request:Request, document_id:str,version:int):
        v=app.state.library.original(document_id,version,request.state.tenant)
        return FileResponse(v['path'],filename=v['filename'],media_type='application/octet-stream')
    @app.get('/api/documents/{document_id}/versions/{version}/image')
    def source_image(request:Request, document_id:str,version:int):
        source=app.state.library.original(document_id,version,request.state.tenant)
        mime=IMAGE_TYPES.get(Path(source['path']).suffix.lower())
        if not mime: raise ValueError('This document is not an image.')
        return FileResponse(source['path'],media_type=mime)
    @app.post('/api/documents/{document_id}/lease')
    def lease(request:Request, document_id:str,body:LeaseRequest):
        return app.state.library.lease(document_id,request.state.tenant,settings.actor,body.seconds)
    @app.post('/api/documents/{document_id}/release')
    def release(request:Request, document_id:str,body:ReleaseRequest):
        app.state.library.release(document_id,request.state.tenant,body.token);return {'status':'released'}
    @app.post('/api/documents/{document_id}/versions',status_code=202)
    def save(request:Request, document_id:str,body:SaveRequest):
        return app.state.library.revise(document_id,request.state.tenant,body.token,body.base_version,body.filename,body.text.encode())
    @app.delete('/api/documents/{document_id}')
    def delete(request:Request, document_id:str):
        app.state.library.delete(document_id,request.state.tenant);return {'status':'archived'}
    @app.get('/api/jobs')
    def jobs(request:Request):return app.state.library.jobs(request.state.tenant)
    @app.post('/api/jobs/{job_id}/retry',status_code=202)
    def retry(request:Request, job_id:str):
        app.state.library.retry(job_id,request.state.tenant);return {'status':'queued'}
    @app.get('/api/events')
    def events(request:Request, after:int=0):return app.state.library.events(request.state.tenant,after)
    @app.post('/api/search')
    def search(request:Request, body:Query):return app.state.library.search(tenant=request.state.tenant,**body.model_dump())
    return app
app=create_app()
