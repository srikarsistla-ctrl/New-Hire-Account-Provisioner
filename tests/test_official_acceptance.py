"""Expanded acceptance coverage traced to the supplied hackathon statement."""
import pytest
from conftest import submit, approve
from app.agent.validator import TOOLS

def test_tc1_all_eight_specific_roles_wait_for_human(client, hire_data):
    hire_data['assignments'] = [{'tool':tool,'role':meta['roles'][1]} for tool,meta in TOOLS.items()]
    hire=submit(client,hire_data)
    assert len(hire['plan'])==8
    for tool in TOOLS:
        assert not client.get(f'/api/mock/{tool}/inspect',params={'email':hire['email']}).json()['exists']
    result=approve(client,hire)
    assert result['status']=='completed'
    assert all(r['status']=='created' and r['actual_role']==r['requested_role'] for r in result['results'])

@pytest.mark.parametrize('tool',list(TOOLS))
def test_tc1_explicit_admin_approval_is_supported(client,hire_data,tool):
    hire_data['assignments']=[{'tool':tool,'role':'admin'}]
    hire=submit(client,hire_data)
    assert not client.get(f'/api/mock/{tool}/inspect',params={'email':hire['email']}).json()['exists']
    assert approve(client,hire)['results'][0]['actual_role']=='admin'

def test_tc2_second_request_reuses_every_account_without_consuming_seats(client,hire_data):
    approve(client,submit(client,hire_data))
    before={tool:client.get(f'/api/mock/{tool}/inspect').json()['seats'] for tool in TOOLS}
    second=approve(client,submit(client,hire_data))
    assert all(r['status']=='already_existed' for r in second['results'])
    assert before=={tool:client.get(f'/api/mock/{tool}/inspect').json()['seats'] for tool in TOOLS}

@pytest.mark.parametrize('tool',list(TOOLS))
def test_tc3_admin_defaults_never_override_approved_minimum(client,hire_data,tool):
    assert client.put(f'/api/mock/{tool}/settings',json={'total':100,'default_role':'admin'}).status_code==200
    lowest=TOOLS[tool]['roles'][0]
    hire_data['assignments']=[{'tool':tool,'role':lowest}]
    result=approve(client,submit(client,hire_data))
    assert result['results'][0]['actual_role']==lowest

def test_tc3_existing_admin_account_is_downgraded_to_viewer(client,hire_data):
    hire_data['assignments']=[{'tool':'github','role':'admin'}]
    approve(client,submit(client,hire_data))
    hire_data['assignments'][0]['role']='viewer'
    result=approve(client,submit(client,hire_data))
    assert result['results'][0]['status']=='already_existed'
    assert result['results'][0]['actual_role']=='viewer'

@pytest.mark.parametrize('tool',list(TOOLS))
def test_tc4_full_tool_reports_partial_and_independent_tools_continue(client,hire_data,tool):
    state=client.get(f'/api/mock/{tool}/inspect').json()
    client.put(f'/api/mock/{tool}/settings',json={'total':state['seats']['used'],'default_role':state['default_role']})
    result=approve(client,submit(client,hire_data))
    rows={r['tool']:r for r in result['results']}
    assert rows[tool]['status']=='partial'
    assert rows[tool]['actual_role'] is None
    assert 'seat limit' in rows[tool]['message'].lower()
    for other,row in rows.items():
        if other==tool:
            continue
        if tool=='google_workspace' and other=='slack':
            assert row['status']=='partial' and 'Dependency' in row['message']
        else:
            assert row['status']=='created'

def test_removed_assignment_is_never_executed(client,hire_data):
    hire=submit(client,hire_data)
    changed=client.put(f'/api/hires/{hire["id"]}/plan',json={'revision':1,'assignments':[{'tool':'github','role':'viewer'}]}).json()
    result=approve(client,changed)
    assert len(result['results'])==1
    for tool in TOOLS:
        if tool!='github':
            assert not client.get(f'/api/mock/{tool}/inspect',params={'email':hire['email']}).json()['exists']
