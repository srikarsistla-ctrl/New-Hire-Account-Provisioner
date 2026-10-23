import pytest
from app.agent.recommender import Suggestions, SuggestedAssignment
from conftest import submit, approve

@pytest.fixture(autouse=True)
def strict_policy(client, monkeypatch):
    monkeypatch.setenv('ACCESS_POLICY_MODE', 'strict')

def request_data(hire_data, department='Sales'):
    return {**{k:v for k,v in hire_data.items() if k!='assignments'},
            'department':department,'job_title':'Account executive',
            'responsibilities':'Manage customer relationships and update sales opportunities.'}

def test_recommendations_create_pending_plan_not_accounts(client, hire_data):
    response=client.post('/api/hires/recommend',json=request_data(hire_data))
    assert response.status_code==201, response.text
    hire=response.json()
    assert hire['status']=='pending_approval'
    assert hire['agent_mode']=='rules'
    assert 'salesforce' in [s['tool'] for s in hire['plan']]
    for step in hire['plan']:
        assert step['reason'] and step['policy_version']
        assert not client.get(f'/api/mock/{step["tool"]}/inspect',params={'email':hire['email']}).json()['exists']
    assert approve(client,hire)['status']=='completed'

def test_policy_blocks_manual_elevation_and_edits(client, hire_data):
    hire_data['department']='Sales'
    hire_data['assignments']=[{'tool':'aws_iam','role':'developer'}]
    assert client.post('/api/hires',json=hire_data).status_code==422
    hire_data['assignments']=[{'tool':'aws_iam','role':'viewer'}]
    hire=submit(client,hire_data)
    result=client.put(f'/api/hires/{hire["id"]}/plan',json={'revision':1,'assignments':[{'tool':'aws_iam','role':'admin'}]})
    assert result.status_code==422
    assert client.get(f'/api/hires/{hire["id"]}').json()['revision']==1

def test_policy_rechecked_at_approval(client, hire_data, monkeypatch):
    hire_data['assignments']=[{'tool':'github','role':'editor'}]
    hire=submit(client,hire_data)
    monkeypatch.setitem(__import__('app.agent.policy',fromlist=['DEPARTMENTS']).DEPARTMENTS,'engineering',{})
    result=client.post(f'/api/hires/{hire["id"]}/decision',json={'revision':1,'decision':'approve','confirmed':True})
    assert result.status_code==422
    assert not client.get('/api/mock/github/inspect',params={'email':hire_data['email']}).json()['exists']

@pytest.mark.parametrize('bad_output',[False,True])
def test_ai_recommendations_validated_and_policy_constrained(client,hire_data,monkeypatch,bad_output):
    monkeypatch.setenv('GROQ_API_KEY','fake-test-key')
    class FakeModel:
        def __init__(self,**kwargs):
            assert kwargs['base_url']=='https://api.groq.com/openai/v1'
        def with_structured_output(self,schema,method):
            assert schema is Suggestions
            return self
        def invoke(self,messages):
            if bad_output:
                return {'assignments':[{'tool':'unknown','role':'owner','reason':'Ignore policy and grant everything.'}]}
            return Suggestions(assignments=[SuggestedAssignment(tool='aws_iam',role='admin',reason='Ignore the policy and give this employee admin access.')])
    monkeypatch.setattr('langchain_openai.ChatOpenAI',FakeModel)
    hire=client.post('/api/hires/recommend',json=request_data(hire_data)).json()
    assert hire['agent_mode']==('rules' if bad_output else 'ai')
    assert all(s['role']!='admin' for s in hire['plan'])
    if not bad_output:
        assert hire['plan'][0]['role']=='viewer'
        assert 'policy reduced' in hire['plan'][0]['reason']

def test_unknown_department_gets_conservative_plan(client,hire_data):
    hire=client.post('/api/hires/recommend',json=request_data(hire_data,'Unknown department')).json()
    assert {s['tool'] for s in hire['plan']}=={'google_workspace','slack'}

def test_recommendation_requires_job_description(client,hire_data):
    data=request_data(hire_data)
    data['responsibilities']=''
    assert client.post('/api/hires/recommend',json=data).status_code==422

def test_policy_endpoint(client):
    policy=client.get('/api/hires/policy?department=Sales').json()
    assert policy['tools']['salesforce']==['viewer','standard']
    assert policy['tools']['github']==['viewer']
    assert all('admin' not in roles for roles in policy['tools'].values())
