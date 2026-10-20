"""Public web evidence and isolated Python execution, exposed through MCP."""
import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from uuid import uuid4
import httpx
from lxml import html
from opensandbox import Sandbox
from opensandbox.config import ConnectionConfig
from opensandbox.models.execd import RunCommandOpts
from opensandbox.models.filesystem import WriteEntry
from opensandbox.models.sandboxes import NetworkPolicy

PUBLIC_DOMAINS = ('gov.cn', 'gov.uk', 'europa.eu', 'trade.gov', 'cbp.gov', 'ustr.gov', 'wto.org', 'boc.cn', 'sinosure.com.cn')

def enabled(name):
    return os.getenv('TRADEX_' + name.upper() + '_ENABLED', '0') == '1'

def public_url(url):
    parsed = urlparse(url)
    host = parsed.hostname or ''
    return parsed.scheme == 'https' and parsed.port in (None, 443) and not parsed.username and any(
        host == domain or host.endswith('.' + domain) for domain in PUBLIC_DOMAINS)

def search(query, transport=None):
    if not enabled('web'): raise ValueError('Public web search is disabled')
    if not query.strip() or len(query) > 500: raise ValueError('Use a short public policy question')
    payload = {'model': os.getenv('TRADEX_SEARCH_MODEL', 'qwen/qwen3-30b-a3b-instruct-2507'),
               'messages': [{'role': 'user', 'content': query}],
               'plugins': [{'id': 'web', 'engine': 'exa', 'max_results': 3, 'include_domains': list(PUBLIC_DOMAINS)}]}
    with httpx.Client(timeout=45, transport=transport) as client:
        response = client.post('https://openrouter.ai/api/v1/chat/completions',
                               headers={'Authorization': 'Bearer ' + os.environ['OPENROUTER_API_KEY']}, json=payload)
        response.raise_for_status()
    data = response.json()
    citations = [item['url_citation'] for item in data['choices'][0]['message'].get('annotations', [])
                 if item['type'] == 'url_citation' and public_url(item['url_citation']['url'])]
    return citations, {'model': data.get('model'), 'usage': data.get('usage', {})}

def fetch(url, transport=None):
    if not enabled('web') or not public_url(url): raise ValueError('Use an approved public-source URL')
    with httpx.Client(timeout=20, transport=transport) as client:
        for _ in range(4):
            response = client.get(url)
            if response.is_redirect:
                url = str(response.url.join(response.headers['location']))
                if not public_url(url): raise ValueError('Redirect left the public-source domains')
                continue
            response.raise_for_status()
            if len(response.content) > 2_000_000: raise ValueError('Page exceeds the text retrieval limit')
            if 'text/html' not in response.headers.get('content-type', ''): raise ValueError('Web reader currently supports HTML pages')
            page = html.fromstring(response.content)
            for node in page.xpath('//script|//style|//nav|//footer'): node.drop_tree()
            text = ' '.join(page.text_content().split())
            return url, text[:20000], len(text) > 20000
    raise ValueError('Too many page redirects')

async def execute_python(code, inputs, sandbox_factory=None):
    if not enabled('sandbox'): raise ValueError('Python sandbox is disabled')
    if len(code) > 20000: raise ValueError('Python script exceeds 20000 characters')
    config = ConnectionConfig(domain=os.getenv('SANDBOX_DOMAIN', '127.0.0.1:8080'),
                              api_key=os.environ['SANDBOX_API_KEY'], use_server_proxy=True)
    create = sandbox_factory or Sandbox.create
    sandbox = await create(os.getenv('TRADEX_SANDBOX_IMAGE', 'python:3.12-slim'),
                           connection_config=config, entrypoint=['sleep', 'infinity'],
                           timeout=timedelta(minutes=2), resource={'cpu': '1', 'memory': '512Mi'},
                           network_policy=NetworkPolicy(default_action='deny', egress=[]))
    try:
        await sandbox.files.write_files([
            WriteEntry(path='/tmp/input.json', data=json.dumps(inputs, ensure_ascii=False), mode=444),
            WriteEntry(path='/tmp/analysis.py', data=code, mode=444)])
        result = await sandbox.commands.run('python /tmp/analysis.py',
                    opts=RunCommandOpts(working_directory='/tmp', timeout=timedelta(seconds=20), uid=65534, gid=65534))
        return {'exit_code': result.exit_code, 'stdout': result.text[:16000],
                'stderr': '\n'.join(line.text for line in result.logs.stderr)[:4000],
                'error': result.error.model_dump() if result.error else None}
    finally:
        try:
            await sandbox.kill()
        finally:
            await sandbox.close()

class Extensions:
    def __init__(self, workflows): self.workflows = workflows

    def run(self, name, run, arguments):
        store, tenant = self.workflows.store, self.workflows.tenant
        run_id = run['id']
        if name == 'sandbox_python':
            ids = set(arguments.get('source_ids', []))
            sources = [source for source in run['sources'] if source['id'] in ids]
            if len(sources) != len(ids): raise ValueError('Unknown evidence reference')
            inputs = {'sources': sources, 'workspace': store.workspace(tenant)}
            result = asyncio.run(execute_python(arguments['code'], inputs))
            artifact = store.artifact(tenant, run_id, 'python_analysis', json.dumps(result, ensure_ascii=False))
            return dict(result, artifact_id=artifact['artifact_id'], authority='Exploratory analysis; use wf_cash for authoritative cash calculations')
        timestamp = datetime.now(timezone.utc).isoformat()
        if name == 'web_search':
            attempts = sum(event['event'] == 'web_search_requested' for event in run['trace'])
            if attempts >= 2: raise ValueError('This turn has used its two public searches')
            store.append(run_id, tenant, {'event': 'web_search_requested'})
            hits, usage = search(arguments['query'])
            store.append(run_id, tenant, {'event': 'web_search_usage', **usage})
            evidence = [(hit['url'], hit.get('title', hit['url']), hit.get('content', ''), 'Search excerpt') for hit in hits]
        else:
            url = arguments['url']
            if not any(s.get('kind') == 'web' and s['source_url'] == url for s in run['sources']):
                raise ValueError('Fetch a URL returned by this conversation’s public search')
            url, text, truncated = fetch(url)
            evidence = [(url, url, text, 'Page text (truncated)' if truncated else 'Page text')]
        sources = [{'document_id': 'web-' + str(uuid4()), 'kind': 'web', 'version': 1, 'title': title,
                    'source_url': url, 'original_url': None, 'locator': label + ' · ' + timestamp,
                    'retrieved_at': timestamp, 'excerpt': text, 'context': text, 'review_due': None}
                   for url, title, text, label in evidence]
        all_sources = store.sources(run_id, tenant, sources)
        ids = {s['document_id'] for s in sources}
        return {'sources': [s for s in all_sources if s['document_id'] in ids],
                'instruction': 'External evidence only. Read the page before asserting a policy condition or effective date.'}
