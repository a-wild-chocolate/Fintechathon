import base64
import json

import httpx
from fastapi.testclient import TestClient

from tradex_rag.api import create_app
from tradex_rag.config import Settings
from tradex_rag.models import ModelClient
from tradex_rag.service import Library
from tradex_rag.vision import read_image
from test_library import TestEmbedding

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jF9kAAAAASUVORK5CYII=')
FIELDS = {'transcription': 'Order TF-26104. We will pay the undisputed portion first.',
          'order_id': 'TF-26104', 'payment_kind': 'partial_promise', 'amount': None,
          'currency': None, 'payment_date': None, 'conditions': 'Remaining balance follows quality review.'}


def vision_client(monkeypatch, calls, fields=FIELDS):
    monkeypatch.setenv('TRADEX_MODEL_PROVIDER', 'openrouter')
    monkeypatch.setenv('OPENROUTER_API_KEY', 'fixture')
    monkeypatch.setenv('TRADEX_MODEL_VISION', 'deepseek/deepseek-v4.1-flash')
    def respond(request):
        payload = json.loads(request.content)
        calls.append(payload)
        return httpx.Response(200, json={'model': payload['model'], 'usage': {'total_tokens': 100},
            'choices': [{'message': {'role': 'assistant', 'content': json.dumps(fields)}, 'finish_reason': 'stop'}]})
    return ModelClient(httpx.MockTransport(respond))


def test_native_image_payload_missing_fields_and_reuse(tmp_path, monkeypatch):
    calls = []
    model = vision_client(monkeypatch, calls)
    path = tmp_path/'email.png'
    path.write_bytes(PNG)
    result = read_image(path, model)
    assert result['fields']['amount'] is None and result['fields']['payment_date'] is None
    image = calls[0]['messages'][1]['content'][1]
    assert image['type'] == 'image_url'
    assert base64.b64decode(image['image_url']['url'].split(',')[1]) == PNG
    assert read_image(path, model) == result and len(calls) == 1


def test_explicit_payment_fields(tmp_path, monkeypatch):
    model = vision_client(monkeypatch, [], dict(FIELDS, amount=6000, currency='USD', payment_date='2026-10-29'))
    path = tmp_path/'reply.jpg'
    path.write_bytes(b'image-fixture')
    assert read_image(path, model)['fields']['payment_date'] == '2026-10-29'


def test_image_ingestion_citations_preview_and_retry(tmp_path, monkeypatch):
    calls = []
    library = Library(Settings(data_dir=tmp_path), embedding=TestEmbedding(), vision_model=vision_client(monkeypatch, calls))
    record = library.create('buyer.png', PNG, 'Buyer email screenshot', library.settings.tenant, {'order_id': 'TF-26104'})
    def embedding_down(texts): raise RuntimeError('Embedding unavailable')
    library.embedding.documents = embedding_down
    library.process_next()
    assert library.jobs(library.settings.tenant)[0]['status'] == 'embedding_failed'
    library.embedding.documents = TestEmbedding().documents
    library.retry(record['job_id'], library.settings.tenant)
    library.process_next()
    assert len(calls) == 1
    doc = library.document(record['document_id'], library.settings.tenant)
    assert doc['image_analysis']['fields']['amount'] is None
    hits = library.search('undisputed payment', library.settings.tenant, document_id=doc['id'])['results']
    assert hits and hits[0]['citation']['locator'].startswith('Screenshot')
    assert library.original(doc['id'], 1, library.settings.tenant)['filename'] == 'buyer.png'
    with TestClient(create_app(library.settings, library)) as client:
        response = client.get(f"/api/documents/{doc['id']}/versions/1/image")
        assert response.headers['content-type'] == 'image/png' and response.content == PNG
        assert client.get('/api/agents/workspace').json()['workspace'] is None
