"""LangChain chat model using the Workers-native fetch transport.

Avoid Python OpenAI/httpx TLS initialization in a resource-limited Worker.
"""
import asyncio
import json
from typing import Any
from pydantic import SecretStr
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.utils.function_calling import convert_to_openai_tool


async def completion(url, key, payload):
    from workers import fetch
    async with asyncio.timeout(20):
        response = await fetch(url, method='POST', headers={
            'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'},
            body=json.dumps(payload))
        if response.status >= 400:
            raise RuntimeError(f'AI provider returned HTTP {response.status}')
        return await response.json()


class WorkersChatModel(BaseChatModel):
    api_key: SecretStr
    base_url: str
    model: str

    @property
    def _llm_type(self):
        return 'cloudflare-fetch-openai-compatible'

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        raise NotImplementedError('Use the asynchronous model in Workers.')

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        options = {'tools': [convert_to_openai_tool(t) for t in tools]}
        if tool_choice:
            options['tool_choice'] = 'required' if tool_choice == 'any' else tool_choice
        return self.bind(**options)

    def with_structured_output(self, schema, *, method='function_calling', **kwargs):
        if method != 'function_calling':
            raise ValueError('Only structured tool calling is supported.')
        return super().with_structured_output(schema, **kwargs)

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        wire = []
        roles = {'human': 'user', 'ai': 'assistant', 'system': 'system', 'tool': 'tool'}
        for message in messages:
            item: dict[str, Any] = {'role': roles[message.type], 'content': message.content}
            if message.type == 'tool':
                item['tool_call_id'] = message.tool_call_id
            if message.type == 'ai' and message.tool_calls:
                item['tool_calls'] = [{'id': call['id'], 'type': 'function', 'function': {
                    'name': call['name'], 'arguments': json.dumps(call['args'])}} for call in message.tool_calls]
            wire.append(item)
        payload = {'model': self.model, 'messages': wire, 'temperature': 0,
                   'max_tokens': 1200, **{k: kwargs[k] for k in ('tools', 'tool_choice') if k in kwargs}}
        if stop:
            payload['stop'] = stop
        result = await completion(self.base_url + '/chat/completions', self.api_key.get_secret_value(), payload)
        message = result['choices'][0]['message']
        calls = [{'id': call['id'], 'name': call['function']['name'],
                  'args': json.loads(call['function']['arguments']), 'type': 'tool_call'}
                 for call in message.get('tool_calls', [])]
        return ChatResult(generations=[ChatGeneration(message=AIMessage(
            content=message.get('content') or '', tool_calls=calls))])
