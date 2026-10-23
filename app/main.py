from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError
from app.database import Base, engine, SessionLocal
from app.models import Employee, ToolAccount, ToolConfig, ProvisioningLog
from app.services.seed import seed
from app.routes import hire, provision, dashboard

@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
    yield

app = FastAPI(title='New Hire Account Provisioner', lifespan=lifespan)
for router in (hire.router, provision.router, dashboard.router):
    app.include_router(router)

@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, exc):
    return JSONResponse(status_code=503, content={'detail': 'Database operation could not complete. Refresh the request before retrying.'})

frontend = Path(__file__).resolve().parent.parent / 'frontend'
app.mount('/static', StaticFiles(directory=frontend), name='static')

@app.get('/', include_in_schema=False)
def index():
    return FileResponse(frontend / 'index.html')

@app.get('/approval', include_in_schema=False)
def approval():
    return FileResponse(frontend / 'approval.html')

@app.get('/dashboard', include_in_schema=False)
def results():
    return FileResponse(frontend / 'dashboard.html')

@app.get('/api/health')
def health():
    return {'status': 'ok', 'environment': 'synthetic sandbox'}
