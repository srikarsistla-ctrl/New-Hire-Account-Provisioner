from conftest import submit, approve

def test_existing_users_reused(client, hire_data):
    hire_data['email'] = 'EXISTING@example.com'
    before = {t: client.get(f'/api/mock/{t}/inspect').json()['seats']['used'] for t in ['github', 'slack', 'google_workspace']}
    result = approve(client, submit(client, hire_data))
    for row in result['results']:
        if row['tool'] in before:
            assert row['status'] == 'already_existed'
            assert client.get(f'/api/mock/{row["tool"]}/inspect').json()['seats']['used'] == before[row['tool']]
        else:
            assert row['status'] == 'created'
    again = approve(client, result)
    assert again['results'] == result['results']
    assert len(again['logs']) == len(result['logs'])
