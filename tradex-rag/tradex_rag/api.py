from contextlib import asynccontextmanager
from pathlib import Path
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
    app=FastAPI(title='TradeX Evidence Library',version='0.1.0',lifespan=lifespan)
    @app.exception_handler(ValueError)
    async def value_error(request,exc):
        status=409 if isinstance(exc,Conflict) else 404 if isinstance(exc,NotFound) else 403 if isinstance(exc,AccessDenied) else 400
        return JSONResponse({'detail':str(exc)},status_code=status)
    @app.get('/')
    def home():return FileResponse(Path(__file__).with_name('workbench.html'))
    @app.get('/api/health')
    def health():return app.state.library.stats(settings.tenant)
    @app.get('/api/assistant/status')
    def assistant_status():
        return app.state.agents.status() if app.state.agents.enabled else app.state.assistant.status()
    @app.post('/api/assistant/chat')
    def chat(body:ChatRequest):
        try:
            if app.state.agents.enabled:
                return app.state.agents.answer(**body.model_dump())
            return app.state.assistant.answer(**body.model_dump(exclude={'session_id', 'workspace'}))
        except httpx.HTTPError:
            return JSONResponse({'detail':'Model request failed. Check model configuration and retry.'},status_code=502)
    @app.post('/api/assistant/runs', status_code=202)
    def start_agent_run(body:ChatRequest, background:BackgroundTasks):
        runtime=app.state.agents
        if not runtime.enabled:
            return JSONResponse({'detail':'Multi-agent service is not enabled.'},status_code=409)
        prepared=runtime.prepare(**body.model_dump())
        background.add_task(runtime.execute,*prepared)
        return {'run_id':prepared[0],'session_id':prepared[1],'status':'running'}
    @app.post('/api/agents/runs/{run_id}/answers', status_code=202)
    def answer_agent_questions(run_id:str, body:HumanReply, background:BackgroundTasks):
        runtime=app.state.agents
        response, prepared=runtime.store.respond(run_id,settings.tenant,body.answers,body.language)
        if prepared: background.add_task(runtime.execute,*prepared)
        return response
    @app.get('/api/agents/runs/{run_id}/progress')
    def agent_progress(run_id:str):
        run=app.state.agents.store.run(run_id,settings.tenant)
        events=[{k:event[k] for k in ('event','agent','tool','status','timestamp') if k in event} for event in run['trace']]
        return {'run_id':run_id,'session_id':run['session_id'],'status':run['status'],
                'created_at':run['created_at'],'trace':events,'result':run['result']}
    @app.get('/api/agents/status')
    def agents_status():return app.state.agents.status()
    @app.get('/api/agents/runs/{run_id}')
    def agent_run(run_id:str):return app.state.agents.store.run(run_id,settings.tenant)
    @app.get('/api/agents/workspace')
    def agent_workspace():return {'workspace':app.state.agents.store.workspace(settings.tenant)}
    @app.post('/api/agents/proposals/{proposal_id}/confirm')
    def confirm_agent_proposal(proposal_id:str):return app.state.agents.workflows.confirm(proposal_id)
    @app.post('/api/agent-tools/{name}')
    def agent_tool(name:str,body:AgentToolRequest):
        return app.state.agents.workflows.execute(name,body.run_id,body.role,body.arguments)
    @app.get('/api/documents')
    def documents():return app.state.library.list_documents(settings.tenant)
    @app.post('/api/uploads',status_code=202)
    async def upload(file:UploadFile=File(...),title:str=Form(''),order_id:str=Form('')):
        data=await file.read(20*1024*1024+1)
        if len(data)>20*1024*1024:raise ValueError('Maximum file size is 20 MB')
        return app.state.library.create(file.filename,data,title or file.filename,settings.tenant,{'order_id':order_id,'source_kind':'user_upload'})
    @app.post('/api/text-uploads',status_code=202)
    def text_upload(body:TextUpload):
        return app.state.library.create(body.filename,body.text.encode(),body.title,settings.tenant,{'order_id':body.order_id,'source_kind':'user_upload'})
    @app.get('/api/documents/{document_id}')
    def document(document_id:str):return app.state.library.document(document_id,settings.tenant)
    @app.get('/api/documents/{document_id}/versions/{version}')
    def document_version(document_id:str,version:int):return app.state.library.document(document_id,settings.tenant,version)
    @app.get('/api/documents/{document_id}/versions/{version}/original')
    def original(document_id:str,version:int):
        v=app.state.library.original(document_id,version,settings.tenant)
        return FileResponse(v['path'],filename=v['filename'],media_type='application/octet-stream')
    @app.post('/api/documents/{document_id}/lease')
    def lease(document_id:str,body:LeaseRequest):
        return app.state.library.lease(document_id,settings.tenant,settings.actor,body.seconds)
    @app.post('/api/documents/{document_id}/release')
    def release(document_id:str,body:ReleaseRequest):
        app.state.library.release(document_id,settings.tenant,body.token);return {'status':'released'}
    @app.post('/api/documents/{document_id}/versions',status_code=202)
    def save(document_id:str,body:SaveRequest):
        return app.state.library.revise(document_id,settings.tenant,body.token,body.base_version,body.filename,body.text.encode())
    @app.delete('/api/documents/{document_id}')
    def delete(document_id:str):
        app.state.library.delete(document_id,settings.tenant);return {'status':'archived'}
    @app.get('/api/jobs')
    def jobs():return app.state.library.jobs(settings.tenant)
    @app.post('/api/jobs/{job_id}/retry',status_code=202)
    def retry(job_id:str):
        app.state.library.retry(job_id,settings.tenant);return {'status':'queued'}
    @app.get('/api/events')
    def events(after:int=0):return app.state.library.events(settings.tenant,after)
    @app.post('/api/search')
    def search(body:Query):return app.state.library.search(tenant=settings.tenant,**body.model_dump())
    return app
app=create_app()
