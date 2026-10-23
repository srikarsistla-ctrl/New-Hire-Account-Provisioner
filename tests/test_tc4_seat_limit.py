from conftest import submit, approve

def test_seat_limit_partial_other_tools_continue(client, hire_data):
    state = client.get('/api/mock/salesforce/inspect').json()
    client.put('/api/mock/salesforce/settings', json={'total': state['seats']['used'], 'default_role': 'viewer'})
    hire = submit(client, hire_data)
    assert any('Seat limit' in w for s in hire['plan'] for w in s['warnings'])
    result = approve(client, hire)
    rows = {r['tool']: r for r in result['results']}
    assert result['status'] == 'completed_with_issues'
    assert rows['salesforce']['status'] == 'partial'
    assert rows['salesforce']['actual_role'] is None
    assert all(r['status'] == 'created' for t, r in rows.items() if t != 'salesforce')

def test_capacity_rechecked_after_planning(client, hire_data):
    hire = submit(client, hire_data)
    client.put('/api/mock/zoom/settings', json={'total': 0, 'default_role': 'basic'})
    result = approve(client, hire)
    assert next(r for r in result['results'] if r['tool'] == 'zoom')['status'] == 'partial'
