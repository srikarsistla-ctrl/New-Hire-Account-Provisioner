from conftest import submit, approve

def test_admin_default_overridden(client, hire_data):
    assert client.get('/api/mock/github/inspect').json()['default_role'] == 'admin'
    hire_data['assignments'] = [{'tool': 'github', 'role': 'viewer'}]
    result = approve(client, submit(client, hire_data))
    assert result['results'][0]['actual_role'] == 'viewer'
    assert client.get('/api/mock/github/inspect', params={'email': hire_data['email']}).json()['account']['role'] == 'viewer'

def test_existing_elevated_role_downgraded(client, hire_data):
    hire_data['assignments'] = [{'tool': 'github', 'role': 'editor'}]
    approve(client, submit(client, hire_data))
    hire_data['assignments'][0]['role'] = 'viewer'
    result = approve(client, submit(client, hire_data))
    assert result['results'][0]['status'] == 'already_existed'
    assert result['results'][0]['actual_role'] == 'viewer'
