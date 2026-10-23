import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db
from app.main import app
from app.services.seed import seed
from app.agent.validator import TOOLS

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('GROQ_API_KEY', raising=False)
    monkeypatch.setenv('ACCESS_POLICY_MODE', 'approval')
    engine = create_engine(f'sqlite:///{tmp_path / "test.db"}', connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr('app.main.engine', engine)
    monkeypatch.setattr('app.main.SessionLocal', sessions)
    with sessions() as db:
        seed(db)
    def override():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = override
    # Lifespan and route dependencies both use the isolated test database.
    with TestClient(app, raise_server_exceptions=True) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()

@pytest.fixture
def hire_data():
    return {'full_name': 'Alex Example', 'email': 'alex@example.com', 'department': 'Engineering',
            'job_title': 'Software engineer', 'manager': 'Jordan Example', 'start_date': '2026-11-01',
            'assignments': [{'tool': t, 'role': meta['roles'][0]} for t, meta in TOOLS.items()]}

def submit(client, data):
    response = client.post('/api/hires', json=data)
    assert response.status_code == 201, response.text
    return response.json()

def approve(client, hire):
    response = client.post(f'/api/hires/{hire["id"]}/decision', json={'revision': hire['revision'], 'decision': 'approve', 'confirmed': True})
    assert response.status_code == 200, response.text
    return response.json()
