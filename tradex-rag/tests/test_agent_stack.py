"""Run explicitly: real HTTP + stdio MCP + Deep Agents, with deterministic model replies."""
import os
import socket
import threading
import time
import httpx
import pytest
import uvicorn
from tradex_rag.api import create_app
from tradex_rag.service import Library
from tradex_rag.config import Settings
from test_library import TestEmbedding, add
from test_agents import ScriptedModel, SNAPSHOT

@pytest.mark.integration
def test_http_mcp_agent_clarification_stack(tmp_path, monkeypatch):
    monkeypatch.setenv('TRADEX_AGENTS_ENABLED', '1')
    library = Library(Settings(data_dir=tmp_path, tenant='test'), embedding=TestEmbedding())
    doc = add(library, 'We will pay the undisputed portion first. Remaining balance follows quality review.', tenant='test', metadata={'order_id':'TF-26104'})['document_id']
    model = ScriptedModel(doc)
    with socket.socket() as reserved:
        reserved.bind(('127.0.0.1',0)); port = reserved.getsockname()[1]
    monkeypatch.setenv('TRADEX_RAG_URL',f'http://127.0.0.1:{port}')
    app = create_app(library.settings, library, agent_model=model)
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='error'))
    thread = threading.Thread(target=server.run, daemon=True); thread.start()
    try:
        for _ in range(100):
            if server.started: break
            time.sleep(.05)
        assert server.started
        with httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=60) as client:
            assert client.get('/api/assistant/status').json()['mode']=='multi_agent'
            body={'language':'en','order_id':'TF-26104','document_id':doc,'workspace':SNAPSHOT}
            for question, expected in [('read email','needs_information'),('6000','needs_information'),('2026-10-29','needs_approval')]:
                response=client.post('/api/assistant/chat',json=dict(body,question=question))
                response.raise_for_status();result=response.json()
                assert result['task_status']==expected,result
                body['session_id']=result['session_id']
            confirmed=client.post('/api/agents/proposals/'+result['proposal']['id']+'/confirm').json()
            assert confirmed['workspace']['version']==2 and confirmed['after']['peak_shortfall_cny']==34000
            response=client.post('/api/assistant/chat',json=dict(body,question='confirmed'))
            result=response.json();assert result['task_status']=='completed',result
            tools={t['tool'] for t in result['trace'] if t['event']=='tool_result'}
            assert {'wf_cash','wf_options','wf_draft','task'} <= tools
            assert client.get(result['sources'][0]['original_url']).status_code==200
            assert client.get('/api/agents/workspace').json()['workspace']['amountUSD']==6000
            assert client.get('/api/agents/runs/'+result['run_id']).json()['status']=='completed'
            clarification=client.post('/api/assistant/chat',json={'question':'read email','language':'en','order_id':'TF-26104','document_id':doc}).json()
            answers=[{'question_id':q['id'],'action':'answer','option_index':0,
                      'comment':'6000' if q['field']=='amount_usd' else '2026-10-29'} for q in clarification['questions']]
            path='/api/agents/runs/'+clarification['run_id']+'/answers'
            reply=client.post(path,json={'answers':answers,'language':'en'})
            assert reply.status_code==202,reply.text
            next_run=reply.json()
            assert client.post(path,json={'answers':answers,'language':'en'}).json()['run_id']==next_run['run_id']
            for _ in range(100):
                progress=client.get('/api/agents/runs/'+next_run['run_id']+'/progress').json()
                if progress['result']: break
                time.sleep(.1)
            assert progress['status']=='needs_approval'
            assert progress['session_id']==clarification['session_id']
            assert client.get('/api/agents/workspace').json()['workspace']['version']==2

    finally:
        server.should_exit=True;thread.join(timeout=10)
        assert not thread.is_alive()

@pytest.mark.integration
def test_progress_is_visible_before_model_completes(tmp_path, monkeypatch):
    monkeypatch.setenv('TRADEX_AGENTS_ENABLED', '1')
    library = Library(Settings(data_dir=tmp_path, tenant='test'), embedding=TestEmbedding())
    doc = add(library, 'Payment amount and date are missing.', tenant='test', metadata={'order_id':'TF-26104'})['document_id']
    entered, release = threading.Event(), threading.Event()
    class PausedModel(ScriptedModel):
        def chat(self, role, messages, tools):
            if not entered.is_set():
                entered.set(); assert release.wait(15)
            return super().chat(role, messages, tools)
    with socket.socket() as reserved:
        reserved.bind(('127.0.0.1',0)); port=reserved.getsockname()[1]
    monkeypatch.setenv('TRADEX_RAG_URL',f'http://127.0.0.1:{port}')
    app=create_app(library.settings,library,agent_model=PausedModel(doc))
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_level='error'))
    thread=threading.Thread(target=server.run,daemon=True);thread.start()
    try:
        for _ in range(100):
            if server.started: break
            time.sleep(.05)
        with httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=20) as client:
            response=client.post('/api/assistant/runs',json={'question':'read email','document_id':doc,'order_id':'TF-26104','workspace':SNAPSHOT})
            assert response.status_code==202
            run=response.json();assert entered.wait(10)
            path='/api/agents/runs/'+run['run_id']+'/progress'
            progress=client.get(path).json()
            assert progress['status']=='running' and progress['result'] is None
            assert any(e['event']=='model_started' and e['agent']=='coordinator' for e in progress['trace'])
            assert all(set(e)<={'event','agent','tool','status','timestamp'} for e in progress['trace'])
            release.set()
            for _ in range(100):
                progress=client.get(path).json()
                if progress['result']:break
                time.sleep(.1)
            assert progress['status']=='needs_information'
            assert progress['result']['session_id']==run['session_id']
            assert any(e.get('tool')=='wf_reconcile' and e['event']=='tool_started' for e in progress['trace'])
    finally:
        release.set();server.should_exit=True;thread.join(timeout=15)
        assert not thread.is_alive()
