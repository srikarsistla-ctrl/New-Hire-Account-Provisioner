import pytest
from conftest import submit, approve

def test_approval_requires_confirmation(client, hire_data):
    hire = submit(client, hire_data)
    response = client.post(f'/api/hires/{hire["id"]}/decision', json={'revision': 1, 'decision': 'approve', 'confirmed': False})
    assert response.status_code == 400
    assert not client.get('/api/mock/github/inspect', params={'email': hire_data['email']}).json()['exists']

def test_edits_invalidate_old_approval(client, hire_data):
    hire = submit(client, hire_data)
    response = client.put(f'/api/hires/{hire["id"]}/plan', json={'revision': 1, 'assignments': [{'tool': 'github', 'role': 'editor'}]})
    assert response.status_code == 200
    changed = response.json()
    assert changed['revision'] == 2
    stale = client.post(f'/api/hires/{hire["id"]}/decision', json={'revision': 1, 'decision': 'approve', 'confirmed': True})
    assert stale.status_code == 409
    result = approve(client, changed)
    assert len(result['results']) == 1
    assert result['results'][0]['actual_role'] == 'editor'

def test_rejection_blocks_provisioning(client, hire_data):
    hire = submit(client, hire_data)
    response = client.post(f'/api/hires/{hire["id"]}/decision', json={'revision': 1, 'decision': 'reject', 'confirmed': True})
    assert response.json()['status'] == 'rejected'
    assert client.post(f'/api/hires/{hire["id"]}/decision', json={'revision': 1, 'decision': 'approve', 'confirmed': True}).status_code == 409
    assert not client.get('/api/mock/github/inspect', params={'email': hire_data['email']}).json()['exists']

@pytest.mark.parametrize('assignments', [[{'tool':'invalid'}], [{'tool':'github','role':'owner'}], [{'tool':'github'},{'tool':'github'}], []])
def test_invalid_assignments(client, hire_data, assignments):
    hire_data['assignments'] = assignments
    assert client.post('/api/hires', json=hire_data).status_code == 422

def test_non_synthetic_email_rejected(client, hire_data):
    hire_data['email'] = 'someone@gmail.com'
    assert client.post('/api/hires', json=hire_data).status_code == 422

def test_group_failure_is_partial(client, hire_data):
    client.put('/api/mock/github/settings', json={'total':100,'default_role':'admin','fail_group':True})
    result = approve(client, submit(client, hire_data))
    row = next(r for r in result['results'] if r['tool'] == 'github')
    assert row['status'] == 'partial'
    assert row['actual_role'] == 'viewer'

def test_provider_failure_and_dependency(client, hire_data):
    client.put('/api/mock/google_workspace/settings', json={'total':100,'default_role':'viewer','fail_create':True})
    result = approve(client, submit(client, hire_data))
    rows = {r['tool']:r for r in result['results']}
    assert rows['google_workspace']['status'] == 'failed'
    assert rows['slack']['status'] == 'partial'
    assert rows['github']['status'] == 'created'

def test_pages_and_api(client):
    for path in ['/', '/approval', '/dashboard', '/static/app.js', '/static/style.css', '/api/health', '/api/catalog', '/api/dashboard']:
        assert client.get(path).status_code == 200
    assert client.get('/api/hires/99999').status_code == 404
