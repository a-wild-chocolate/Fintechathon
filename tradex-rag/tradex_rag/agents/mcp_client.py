"""One stdio MCP session per user turn; tools call the owning HTTP service."""
import json
import os
import sys
from contextlib import asynccontextmanager
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
from .workflows import ALLOW
from .extensions import enabled

class WorkflowClient:
    def __init__(self, session, tools, run_id):
        self.session, self.tools, self.run_id = session, tools, run_id

    def definitions(self, role):
        result = []
        for tool in self.tools:
            if tool.name not in ALLOW[role]: continue
            if tool.name.startswith('web_') and not enabled('web'): continue
            if tool.name == 'sandbox_python' and not enabled('sandbox'): continue
            schema = json.loads(json.dumps(tool.input_schema))
            for key in ('run_id', 'role'): schema['properties'].pop(key, None)
            schema['required'] = [k for k in schema.get('required', []) if k not in ('run_id', 'role')]
            result.append({'type': 'function', 'function': {'name': tool.name, 'description': tool.description, 'parameters': schema}})
        return result

    async def call(self, role, name, args):
        if name not in ALLOW[role]: raise ValueError('Tool is not assigned to this role')
        result = await self.session.call_tool(name, dict(args, run_id=self.run_id, role=role))
        if result.is_error:
            raise ValueError('MCP workflow failed: ' + ' '.join(getattr(c, 'text', '') for c in result.content))
        if result.structured_content is not None: return result.structured_content
        return json.loads(next(c.text for c in result.content if c.type == 'text'))

@asynccontextmanager
async def connect(run_id):
    env = dict(os.environ)
    env['TRADEX_RAG_URL'] = os.getenv('TRADEX_RAG_URL', 'http://127.0.0.1:' + os.getenv('TRADEX_RAG_PORT', '8765'))
    params = StdioServerParameters(command=sys.executable, args=['-m', 'tradex_rag.mcp_server'], env=env)
    async with stdio_client(params) as streams:
        async with ClientSession(streams[0], streams[1]) as session:
            await session.initialize()
            listed = await session.list_tools()
            yield WorkflowClient(session, listed.tools, run_id)
