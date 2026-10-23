from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import pytest
from langchain_core.messages import AIMessage
from conftest import submit
from app.agent.provisioner import review_plan

def test_simultaneous_approvals_only_consume_one_remaining_seat(client, hire_data):
    state = client.get('/api/mock/github/inspect').json()
    client.put('/api/mock/github/settings', json={'total': state['seats']['used'] + 1, 'default_role': 'admin'})
    hire_data['assignments'] = [{'tool': 'github', 'role': 'viewer'}]
    first = submit(client, hire_data)
    second = submit(client, {**hire_data, 'email': 'second@example.com'})
    def decide(hire):
        return client.post(f'/api/hires/{hire["id"]}/decision', json={'revision':1,'decision':'approve','confirmed':True})
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(decide, [first, second]))
    assert all(r.status_code == 200 for r in responses)
    assert sorted(r.json()['results'][0]['status'] for r in responses) == ['created', 'partial']
    seats = client.get('/api/mock/github/inspect').json()['seats']
    assert seats['used'] == seats['total']

def test_simultaneous_requests_for_same_account_are_reused(client, hire_data):
    hire_data['assignments'] = [{'tool': 'github', 'role': 'viewer'}]
    hires = [submit(client, hire_data), submit(client, hire_data)]
    def decide(hire):
        return client.post(f'/api/hires/{hire["id"]}/decision', json={'revision':1,'decision':'approve','confirmed':True})
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(decide, hires))
    assert all(r.status_code == 200 for r in responses)
    assert sorted(r.json()['results'][0]['status'] for r in responses) == ['already_existed', 'created']

@pytest.mark.parametrize('backend', ['openai', 'groq'])
def test_ai_tool_loop_is_read_only(monkeypatch, backend):
    monkeypatch.delenv('GROQ_API_KEY', raising=False)
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-test-key')
    if backend == 'groq':
        monkeypatch.setenv('GROQ_API_KEY', 'synthetic-groq-key')
        monkeypatch.setenv('GROQ_MODEL', 'test-groq-model')
    calls = []
    fake_provider = SimpleNamespace(check_user_exists=lambda email: False, get_seat_count=lambda: {'used': 12, 'total': 100}, get_default_role=lambda: 'admin')
    monkeypatch.setattr('app.agent.provisioner.provider', lambda db, name: fake_provider)
    class FakeModel:
        def __init__(self, **kwargs):
            if backend == 'groq':
                assert kwargs['api_key'] == 'synthetic-groq-key'
                assert kwargs['base_url'] == 'https://api.groq.com/openai/v1'
                assert kwargs['model'] == 'test-groq-model'
                assert kwargs['use_responses_api'] is False
            else:
                assert kwargs['api_key'] == 'synthetic-test-key'
                assert 'base_url' not in kwargs
        def bind_tools(self, tools):
            assert [t.name for t in tools] == ['inspect_tool']
            return self
        def invoke(self, messages):
            calls.append(messages[-1])
            if len(calls) == 1:
                return AIMessage(content='', tool_calls=[{'id':'call1','name':'inspect_tool','args':{'tool_name':'github'},'type':'tool_call'}])
            assert 'admin' in messages[-1].content
            return AIMessage(content='Review the explicit viewer override before approval.')
    monkeypatch.setattr('langchain_openai.ChatOpenAI', FakeModel)
    hire = SimpleNamespace(email='ai@example.com', plan=[{'tool':'github','role':'viewer'}])
    mode, note = review_plan(None, hire)
    assert mode == 'ai'
    assert 'viewer' in note
    assert len(calls) == 2

def test_ai_error_falls_back_without_blocking_plan(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-test-key')
    def unavailable(**kwargs):
        raise RuntimeError('Simulated network failure')
    monkeypatch.setattr('langchain_openai.ChatOpenAI', unavailable)
    mode, note = review_plan(None, SimpleNamespace(plan=[], email='ai@example.com'))
    assert mode == 'rules'
    assert 'unavailable' in note
