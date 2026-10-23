from conftest import submit, approve

def test_all_eight_approved_tools(client, hire_data):
    hire = submit(client, hire_data)
    assert hire['status'] == 'pending_approval'
    assert hire['plan'][0]['tool'] == 'google_workspace'
    for item in hire['plan']:
        state = client.get(f'/api/mock/{item["tool"]}/inspect', params={'email': hire_data['email']}).json()
        assert not state['exists']
    result = approve(client, hire)
    assert result['status'] == 'completed'
    assert len(result['results']) == 8
    for row in result['results']:
        assert row['status'] == 'created'
        assert row['actual_role'] == row['requested_role']
        state = client.get(f'/api/mock/{row["tool"]}/inspect', params={'email': hire_data['email']}).json()
        assert state['account']['groups'] == ['engineering']
    assert all(l['timestamp'] for l in result['logs'])

def test_minimum_roles_when_omitted(client, hire_data):
    hire_data['assignments'] = [{'tool': 'github'}, {'tool': 'slack'}]
    hire = submit(client, hire_data)
    assert {s['tool']: s['role'] for s in hire['plan']} == {'github': 'viewer', 'slack': 'guest'}

def test_explicit_elevated_approval(client, hire_data):
    hire_data['assignments'] = [{'tool': 'github', 'role': 'editor'}]
    hire = submit(client, hire_data)
    assert any('Elevated' in w for w in hire['plan'][0]['warnings'])
    assert approve(client, hire)['results'][0]['actual_role'] == 'editor'
