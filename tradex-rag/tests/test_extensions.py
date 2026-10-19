import asyncio
import json
from types import SimpleNamespace
import httpx
import pytest
from tradex_rag.agents.extensions import search, fetch, execute_python


def test_public_search_uses_only_query_and_provider_citations(monkeypatch):
    monkeypatch.setenv('TRADEX_WEB_ENABLED', '1')
    monkeypatch.setenv('OPENROUTER_API_KEY', 'fixture')
    def respond(request):
        body = json.loads(request.content)
        assert body['messages'] == [{'role':'user', 'content':'UK import VAT guidance'}]
        assert body['plugins'][0]['max_results'] == 3
        annotations = [{'type':'url_citation','url_citation':{'url':url,'title':'Guidance','content':'Excerpt'}}
                       for url in ['https://www.gov.uk/guidance/import-vat', 'http://127.0.0.1:8765/api/documents', 'https://gov.uk.example.com']]
        return httpx.Response(200,json={'choices':[{'message':{'content':'Ignored model prose','annotations':annotations}}], 'usage':{'total_tokens':50}})
    sources, usage = search('UK import VAT guidance', httpx.MockTransport(respond))
    assert len(sources) == 1 and sources[0]['content'] == 'Excerpt'
    assert usage['usage']['total_tokens'] == 50


def test_page_reader_rejects_private_redirect_and_strips_scripts(monkeypatch):
    monkeypatch.setenv('TRADEX_WEB_ENABLED','1')
    with pytest.raises(ValueError, match='Redirect'):
        fetch('https://www.gov.uk/policy', httpx.MockTransport(lambda request: httpx.Response(302,headers={'location':'http://127.0.0.1:8765'})))
    _, text, truncated = fetch('https://www.gov.uk/policy',httpx.MockTransport(lambda request: httpx.Response(200,
        headers={'content-type':'text/html'},text='<html><script>secret()</script><p>Published rule</p></html>')))
    assert text == 'Published rule' and not truncated


def test_sandbox_receives_copies_and_is_cleaned_up_on_error(monkeypatch):
    monkeypatch.setenv('TRADEX_SANDBOX_ENABLED','1')
    monkeypatch.setenv('SANDBOX_API_KEY','fixture')
    events = []
    class Files:
        async def write_files(self, files):
            assert {f.path for f in files} == {'/tmp/input.json','/tmp/analysis.py'}
            assert json.loads(files[0].data) == {'sources':[], 'workspace':{'version':1}}
    class Commands:
        async def run(self, command, opts):
            assert command == 'python /tmp/analysis.py' and opts.uid == 65534
            assert opts.timeout.total_seconds() == 20
            raise RuntimeError('fixture execution failure')
    class Container:
        files, commands = Files(), Commands()
        async def kill(self): events.append('kill')
        async def close(self): events.append('close')
    async def create(image, **kwargs):
        assert kwargs['network_policy'].default_action == 'deny'
        assert 'env' not in kwargs and 'volumes' not in kwargs
        return Container()
    with pytest.raises(RuntimeError, match='fixture execution failure'):
        asyncio.run(execute_python('print(1)', {'sources':[], 'workspace':{'version':1}}, create))
    assert events == ['kill','close']
