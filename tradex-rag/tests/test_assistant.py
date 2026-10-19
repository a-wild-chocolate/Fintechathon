import json
import httpx
import pytest
from fastapi.testclient import TestClient
from tradex_rag.assistant import Assistant
from tradex_rag.api import create_app
from tradex_rag.config import Settings
from tradex_rag.service import Library
from test_library import TestEmbedding, add

@pytest.fixture
def lib(tmp_path):
    settings = Settings(data_dir=tmp_path, tenant='a')
    library = Library(settings, embedding=TestEmbedding())
    yield library
    library.close()

def test_question_and_version_citation(lib, monkeypatch):
    monkeypatch.setenv('TRADEX_CHAT_ENABLED', '0')
    doc = add(lib, 'The partial payment is USD 6000 on 29 October 2026.', metadata={'order_id': 'TF-26104'})['document_id']
    with TestClient(create_app(lib.settings, lib)) as client:
        result = client.post('/api/assistant/chat', json={'question': 'partial payment amount', 'language': 'en', 'document_id': doc, 'order_id': 'TF-26104'}).json()
        assert result['mode'] == 'evidence' and '6000' in result['paragraphs'][0]['text']
        citation = result['sources'][0]
        assert citation['document_id'] == doc and citation['version'] == 1
        lease = lib.lease(doc, 'a', 'test')
        lib.revise(doc, 'a', lease['token'], 1, 'email.txt', b'Payment revised to USD 7000.')
        old = client.get(f'/api/documents/{doc}/versions/1').json()
        assert old['selected_version'] == 1 and '6000' in old['content'][0]['text']
        assert b'6000' in client.get(citation['original_url']).content

def test_order_scope_and_shared_documents(lib, monkeypatch):
    monkeypatch.setenv('TRADEX_CHAT_ENABLED', '0')
    current = add(lib, 'payment amount 6000', metadata={'order_id': 'TF-26104'})['document_id']
    other = add(lib, 'payment amount secret-other', metadata={'order_id': 'TF-26091'})['document_id']
    shared = add(lib, 'payment amount company terms')['document_id']
    assistant = Assistant(lib, lib.settings)
    result = assistant.answer('payment amount', order_id='TF-26104')
    ids = {s['document_id'] for s in result['sources']}
    assert current in ids and shared in ids and other not in ids
    with pytest.raises(ValueError): assistant.answer('payment', document_id=other, order_id='TF-26104')

def test_empty_evidence_does_not_fabricate_answer(lib, monkeypatch):
    monkeypatch.setenv('TRADEX_CHAT_ENABLED', '0')
    add(lib, 'payment amount 6000')
    r = Assistant(lib, lib.settings).answer('interstellar zucchini', language='en')
    assert not r['sources'] and not r['paragraphs'] and 'No matching' in r['follow_up']

def test_qwen_uses_server_citations_and_language(lib, monkeypatch):
    monkeypatch.setenv('TRADEX_CHAT_ENABLED', '1')
    monkeypatch.setenv('DASHSCOPE_API_KEY', 'test-only')
    monkeypatch.setenv('DASHSCOPE_BASE_URL', 'https://test.invalid/v1')
    doc = add(lib, 'The payment amount is USD 6000.')['document_id']
    def respond(request):
        payload = json.loads(request.content)
        question = json.loads(payload['messages'][1]['content'])
        assert question['language'] == 'en' and question['evidence'][0]['document_id'] == doc
        assert 'untrusted' in payload['messages'][0]['content']
        return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps({'paragraphs': [{'text': 'The payment is USD 6000.', 'sources': [1]}], 'follow_up': 'What is the payment date?'})}}]})
    r = Assistant(lib, lib.settings, httpx.MockTransport(respond)).answer('payment amount', language='en')
    assert r['mode'] == 'model' and r['sources'][0]['document_id'] == doc
    assert r['paragraphs'][0]['sources'] == [1]

def test_model_cannot_invent_source_ids(lib, monkeypatch):
    monkeypatch.setenv('TRADEX_CHAT_ENABLED', '1')
    monkeypatch.setenv('DASHSCOPE_API_KEY', 'test-only')
    monkeypatch.setenv('DASHSCOPE_BASE_URL', 'https://test.invalid/v1')
    add(lib, 'payment amount 6000')
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json={'choices': [{'message': {'content': '{"paragraphs":[{"text":"Invented","sources":[999]}]}'}}]}))
    with pytest.raises(ValueError, match='unknown source'):
        Assistant(lib, lib.settings, transport).answer('payment amount')
