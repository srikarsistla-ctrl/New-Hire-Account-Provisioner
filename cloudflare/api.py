import os
from fastapi import FastAPI, Request, HTTPException
from app.agent.validator import TOOLS, HireInput, RecommendationInput, PlanUpdate, Decision, MockSettings
from app.agent.policy import policy_document
from cloudflare import state, ai
from cloudflare.store import Store


def create_app(store_factory=None, env_factory=None):
    app = FastAPI(title='New Hire Account Provisioner')

    def env_for(request):
        return env_factory(request) if env_factory else request.scope['env']

    def store_for(request):
        env = env_for(request)
        os.environ['ACCESS_POLICY_MODE'] = getattr(env, 'ACCESS_POLICY_MODE', 'approval')
        if store_factory:
            return store_factory(request)
        if not hasattr(env, 'DB'):
            raise HTTPException(503, 'Bind the Cloudflare D1 database as DB and apply its migration.')
        return Store(env.DB)

    @app.get('/api/health')
    async def health(request: Request):
        await store_for(request).load()
        return {'status': 'ok', 'environment': 'synthetic sandbox', 'storage': 'cloudflare-d1'}

    @app.get('/api/catalog')
    async def catalog(request: Request):
        _, data = await store_for(request).load()
        return [{'id': tool, **meta, 'seats': state.inspect(data, tool)['seats'],
                 'default_role': data['providers'][tool]['default_role']} for tool, meta in TOOLS.items()]

    @app.get('/api/hires/policy')
    async def policy(request: Request, department: str = 'Engineering'):
        store_for(request)
        return policy_document(department)

    @app.post('/api/hires/recommend', status_code=201)
    async def recommend(request: Request, body: RecommendationInput):
        store = store_for(request)
        assignments, mode, note = await ai.recommend(body, env_for(request))
        version, data = await store.load()
        hire = state.create(data, body, assignments, mode, note)
        await store.save(version, data)
        return hire

    @app.post('/api/hires', status_code=201)
    async def create(request: Request, body: HireInput):
        store = store_for(request)
        version, data = await store.load()
        hire = state.create(data, body, body.assignments)
        await ai.review(data, hire, env_for(request))
        await store.save(version, data)
        return hire

    @app.get('/api/hires/{hire_id}')
    async def get_hire(request: Request, hire_id: int):
        _, data = await store_for(request).load()
        return state.get_hire(data, hire_id)

    @app.put('/api/hires/{hire_id}/plan')
    async def update(request: Request, hire_id: int, body: PlanUpdate):
        store = store_for(request)
        version, data = await store.load()
        hire = state.update(data, hire_id, body)
        await store.save(version, data)
        return hire

    @app.post('/api/hires/{hire_id}/decision')
    async def decide(request: Request, hire_id: int, body: Decision):
        store = store_for(request)
        version, data = await store.load()
        hire = state.decide(data, hire_id, body)
        await store.save(version, data)
        return hire

    @app.get('/api/dashboard')
    async def dashboard(request: Request):
        _, data = await store_for(request).load()
        return [{key: h[key] for key in ('id', 'full_name', 'email', 'department', 'status', 'start_date')} | {'tools': len(h['plan'])}
                for h in sorted(data['hires'].values(), key=lambda h: h['id'], reverse=True)[:100]]

    @app.get('/api/mock/{tool}/inspect')
    async def inspect(request: Request, tool: str, email: str = 'new.hire@example.com'):
        _, data = await store_for(request).load()
        return state.inspect(data, tool, email)

    @app.put('/api/mock/{tool}/settings')
    async def settings(request: Request, tool: str, body: MockSettings):
        if tool not in TOOLS or body.default_role not in TOOLS[tool]['roles']:
            raise HTTPException(422, 'Unknown tool or unsupported default role')
        store = store_for(request)
        version, data = await store.load()
        data['providers'][tool].update(body.model_dump())
        await store.save(version, data)
        return {'tool': tool, **body.model_dump()}

    return app
