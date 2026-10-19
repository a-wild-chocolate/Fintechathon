"""Replaceable Chat Completions transport; no agent or financial logic here."""
import os
from uuid import uuid4
import threading
import httpx

ROLES = ('coordinator', 'reconciliation', 'cash_flow', 'decision')
DEFAULTS = {
    'openrouter': ('https://openrouter.ai/api/v1', 'OPENROUTER_API_KEY', 'deepseek/deepseek-v4.1-flash'),
    'qwen': ('', 'DASHSCOPE_API_KEY', 'qwen-plus'),
    'deepseek': ('https://api.deepseek.com', 'DEEPSEEK_API_KEY', 'deepseek-chat'),
}

class ModelOutputError(ValueError):
    def __init__(self, reason, role):
        self.reason, self.role = reason, role
        super().__init__(f'{role}: {reason}')


class ModelClient:
    def __init__(self, transport=None):
        self.provider = os.getenv('TRADEX_MODEL_PROVIDER', 'openrouter')
        base, key_env, model = DEFAULTS[self.provider]
        self.key = os.getenv(key_env, '')
        self.base = os.getenv('TRADEX_MODEL_BASE_URL') or (os.getenv('DASHSCOPE_BASE_URL', '') if self.provider == 'qwen' else base)
        default = os.getenv('TRADEX_MODEL', model)
        self.models = {role: os.getenv('TRADEX_MODEL_' + role.upper(), default) for role in ROLES}
        vision_default = 'qwen/qwen3.5-plus-20260420' if self.provider == 'openrouter' else default
        self.models['vision'] = os.getenv('TRADEX_MODEL_VISION', vision_default)
        self.transport = transport
        self.slots = threading.BoundedSemaphore(int(os.getenv('TRADEX_MODEL_CONCURRENCY', '2')))

    @property
    def configured(self):
        return bool(self.key and self.base)

    def chat(self, role, messages, tools):
        if not self.configured:
            raise ValueError('Configure the selected model provider key and base URL.')
        payload = {'model': self.models[role], 'messages': messages, 'tools': tools,
                   'tool_choice': 'auto', 'max_tokens': int(os.getenv('TRADEX_MODEL_MAX_TOKENS', '4096')), 'temperature': 0.1}
        if self.provider == 'qwen':
            payload['enable_thinking'] = False
        if self.provider == 'openrouter':
            payload['provider'] = {'require_parameters': True, 'allow_fallbacks': False}
            payload['tool_choice'] = 'required'
            if self.models[role].startswith('deepseek/'):
                payload['reasoning'] = {'enabled': False}
        if len(tools) == 1 and tools[0].get('function', {}).get('name') == 'finish':
            payload['tool_choice'] = {'type': 'function', 'function': {'name': 'finish'}}
        result_tool = None
        if self.provider == 'openrouter' and self.models[role].startswith('deepseek/') and len(tools) == 1:
            spec = tools[0]['function']
            if spec['name'] == 'finish':
                result_tool = spec['name']
                payload.pop('tools')
                payload.pop('tool_choice')
                payload['response_format'] = {'type': 'json_schema', 'json_schema': {
                    'name': result_tool, 'strict': False, 'schema': spec['parameters']}}
                payload['messages'] = [*messages, {'role': 'system', 'content':
                    f'This step returns the arguments for {result_tool} as one JSON object matching the supplied schema. '
                    'Do not emit tool calls or wrap the result in another object.'}]
        with self.slots, httpx.Client(timeout=60, transport=self.transport) as client:
            response = client.post(self.base.rstrip('/') + '/chat/completions',
                                   headers={'Authorization': 'Bearer ' + self.key}, json=payload)
            response.raise_for_status()
            data = response.json()
        if data.get('error'):
            raise ValueError('Model provider returned an error response.')
        message = data['choices'][0]['message']
        if result_tool:
            message = {'role': 'assistant', 'content': None, 'tool_calls': [{
                'id': 'result_' + uuid4().hex, 'type': 'function',
                'function': {'name': result_tool, 'arguments': message.get('content') or ''}}]}
        # Persist tool protocol, not provider-specific hidden reasoning fields.
        message = {k: message[k] for k in ('role', 'content', 'tool_calls') if k in message}
        return message, {'provider': self.provider, 'model': data.get('model', self.models[role]),
                         'usage': data.get('usage', {}), 'finish_reason': data['choices'][0].get('finish_reason')}
