import asyncio
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from cloudflare.api import create_app
from cloudflare.store import Store
from cloudflare import state
from app.agent.validator import HireInput, Decision
from conftest import submit, approve


class Statement:
    def __init__(self, db, sql, args=()):
        self.db, self.sql, self.args = db, sql, args

    def bind(self, *args):
        return Statement(self.db, self.sql, args)

    async def first(self):
        row = self.db.execute(self.sql, self.args).fetchone()
        return dict(row) if row else None

    async def run(self):
        result = self.db.execute(self.sql, self.args)
        self.db.commit()
        return {'meta': {'changes': result.rowcount}}


class Binding:
    def __init__(self):
        self.db = sqlite3.connect(':memory:', check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(Path('migrations/0001_sandbox.sql').read_text())

    def prepare(self, sql):
        return Statement(self.db, sql)


@pytest.fixture
def worker(monkeypatch):
    binding = Binding()
    env = SimpleNamespace(ACCESS_POLICY_MODE='approval')
    app = create_app(lambda request: Store(binding), lambda request: env)
    with TestClient(app) as client:
        yield client
    binding.db.close()


def test_all_tools_approval_and_audit(worker, hire_data):
    hire = submit(worker, hire_data)
    assert hire['status'] == 'pending_approval'
    assert not worker.get('/api/mock/jira/inspect?email=alex@example.com').json()['exists']
    result = approve(worker, hire)
    assert len(result['results']) == 8
    assert all(r['status'] == 'created' for r in result['results'])
    assert all(r['actual_role'] == r['requested_role'] for r in result['results'])
    assert result['logs'][-1]['action'] == 'finished'
    assert worker.get('/api/health').json()['storage'] == 'cloudflare-d1'
    assert len(worker.get('/api/catalog').json()) == 8
    assert worker.get('/api/dashboard').json()[0]['id'] == hire['id']
    assert worker.get(f'/api/hires/{hire["id"]}').json() == result


def test_existing_and_repeated_approval(worker, hire_data):
    hire_data['email'] = 'existing@example.com'
    hire = submit(worker, hire_data)
    result = approve(worker, hire)
    assert sum(r['status'] == 'already_existed' for r in result['results']) == 3
    assert approve(worker, hire) == result
    second = approve(worker, submit(worker, hire_data))
    assert all(r['status'] == 'already_existed' for r in second['results'])


@pytest.mark.parametrize('tool', list(state.TOOLS))
def test_capacity_each_tool(worker, hire_data, tool):
    info = worker.get(f'/api/mock/{tool}/inspect').json()
    assert worker.put(f'/api/mock/{tool}/settings', json={'total': info['seats']['used'], 'default_role': info['default_role']}).status_code == 200
    result = approve(worker, submit(worker, hire_data))
    assert next(r for r in result['results'] if r['tool'] == tool)['status'] == 'partial'
    assert any(r['status'] == 'created' for r in result['results'])


def test_edit_reject_and_stale_revision(worker, hire_data):
    hire = submit(worker, hire_data)
    edited = worker.put(f'/api/hires/{hire["id"]}/plan', json={'revision': 1, 'assignments': [{'tool': 'github'}]}).json()
    assert edited['revision'] == 2 and len(edited['plan']) == 1
    assert worker.post(f'/api/hires/{hire["id"]}/decision', json={'revision': 1, 'decision': 'approve', 'confirmed': True}).status_code == 409
    assert worker.post(f'/api/hires/{hire["id"]}/decision', json={'revision': 2, 'decision': 'approve', 'confirmed': False}).status_code == 400
    rejected = worker.post(f'/api/hires/{hire["id"]}/decision', json={'revision': 2, 'decision': 'reject', 'confirmed': True}).json()
    assert rejected['status'] == 'rejected'
    assert not worker.get('/api/mock/github/inspect?email=alex@example.com').json()['exists']


@pytest.mark.parametrize('fault', ['fail_create', 'fail_group'])
def test_faults_preserve_partial_outcomes(worker, hire_data, fault):
    worker.put('/api/mock/google_workspace/settings', json={'total': 100, 'default_role': 'viewer', fault: True})
    result = approve(worker, submit(worker, hire_data))
    rows = {r['tool']: r for r in result['results']}
    assert rows['google_workspace']['status'] == ('failed' if fault == 'fail_create' else 'partial')
    assert rows['slack']['status'] == ('partial' if fault == 'fail_create' else 'created')
    assert rows['github']['status'] == 'created'


def test_recommend_fallback_and_validation(worker, hire_data):
    body = {k: v for k, v in hire_data.items() if k != 'assignments'}
    result = worker.post('/api/hires/recommend', json={**body, 'responsibilities': 'Build backend APIs and review code.'})
    assert result.status_code == 201
    assert result.json()['agent_mode'] == 'rules'
    assert all(s['reason'] for s in result.json()['plan'])
    assert worker.post('/api/hires', json={**hire_data, 'email': 'person@gmail.com'}).status_code == 422


def test_stale_d1_writes_cannot_overbook_final_seat(hire_data):
    async def scenario():
        binding = Binding()
        store = Store(binding)
        version, data = await store.load()
        data['providers']['github']['total'] = 14  # One seeded account + twelve reserved.
        body = HireInput.model_validate({**hire_data, 'assignments': [{'tool': 'github'}]})
        h1 = state.create(data, body, body.assignments)
        h2 = state.create(data, body.model_copy(update={'email': 'second@example.com'}), body.assignments)
        await store.save(version, data)
        v1, d1 = await store.load()
        v2, d2 = await store.load()
        decision = Decision(revision=1, decision='approve', confirmed=True)
        state.decide(d1, h1['id'], decision)
        state.decide(d2, h2['id'], decision)
        await store.save(v1, d1)
        with pytest.raises(HTTPException) as error:
            await store.save(v2, d2)
        assert error.value.status_code == 409
        version, current = await store.load()
        assert state.get_hire(current, h2['id'])['status'] == 'pending_approval'
        result = state.decide(current, h2['id'], decision)
        assert result['results'][0]['status'] == 'partial'
        await store.save(version, current)
        assert state.inspect(current, 'github')['seats'] == {'used': 14, 'total': 14}
        binding.db.close()
    asyncio.run(scenario())


def test_state_limit_does_not_overwrite_saved_data():
    async def scenario():
        binding = Binding()
        store = Store(binding)
        version, data = await store.load()
        data['large'] = 'a' * 900_001
        with pytest.raises(HTTPException) as error:
            await store.save(version, data)
        assert error.value.status_code == 507
        assert (await store.load())[0] == version
        binding.db.close()
    asyncio.run(scenario())


def test_worker_ai_structured_recommendations(worker, hire_data, monkeypatch):
    from cloudflare import ai
    from app.agent.recommender import Suggestions

    class Model:
        def with_structured_output(self, schema, method):
            assert schema is Suggestions and method == 'function_calling'
            return self

        async def ainvoke(self, messages):
            assert 'responsibilities' in messages[-1].content
            return Suggestions(assignments=[{'tool': 'github', 'role': 'editor',
                'reason': 'Contributing code requires access to edit repositories.'}])

    monkeypatch.setattr(ai, 'model_for', lambda env: Model())
    body = {k: v for k, v in hire_data.items() if k != 'assignments'}
    response = worker.post('/api/hires/recommend', json={**body, 'responsibilities': 'Contribute code and review pull requests.'})
    assert response.status_code == 201
    hire = response.json()
    assert hire['agent_mode'] == 'ai'
    assert hire['plan'][0]['role'] == 'editor'
    assert not worker.get('/api/mock/github/inspect?email=alex@example.com').json()['exists']


def test_worker_ai_failure_uses_labeled_fallback(worker, hire_data, monkeypatch):
    from cloudflare import ai

    def unavailable(env):
        raise RuntimeError('Provider unavailable')

    monkeypatch.setattr(ai, 'model_for', unavailable)
    body = {k: v for k, v in hire_data.items() if k != 'assignments'}
    response = worker.post('/api/hires/recommend', json={**body, 'responsibilities': 'Contribute code and review pull requests.'})
    assert response.status_code == 201
    assert response.json()['agent_mode'] == 'rules'
    assert 'unavailable' in response.json()['agent_note']
