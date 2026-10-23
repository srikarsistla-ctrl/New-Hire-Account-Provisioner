from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Employee, ToolConfig
from app.agent.validator import TOOLS, MockSettings
from app.services.mock_saas import provider
from app.services.provisioning_service import lock

router = APIRouter(prefix='/api', tags=['Dashboard and mock consoles'])

@router.get('/catalog')
def catalog(db: Session = Depends(get_db)):
    return [{'id': key, **value, 'seats': provider(db, key).get_seat_count(), 'default_role': provider(db, key).get_default_role()} for key, value in TOOLS.items()]

@router.get('/dashboard')
def dashboard(db: Session = Depends(get_db)):
    hires = db.scalars(select(Employee).order_by(Employee.id.desc()).limit(100)).all()
    return [{'id': h.id, 'full_name': h.full_name, 'email': h.email, 'department': h.department, 'status': h.status, 'tools': len(h.plan), 'start_date': str(h.start_date)} for h in hires]

@router.get('/mock/{tool}/inspect')
def inspect(tool: str, email: str = Query(default='new.hire@example.com'), db: Session = Depends(get_db)):
    if tool not in TOOLS:
        raise HTTPException(404, 'Unknown tool')
    api = provider(db, tool)
    account = api.account(email)
    return {'exists': bool(account), 'seats': api.get_seat_count(), 'default_role': api.get_default_role(),
            'account': {'role': account.role, 'groups': account.groups} if account else None}

@router.put('/mock/{tool}/settings')
def settings(tool: str, data: MockSettings, db: Session = Depends(get_db)):
    if tool not in TOOLS or data.default_role not in TOOLS[tool]['roles']:
        raise HTTPException(422, 'Unknown tool or unsupported default role')
    lock(db)
    config = db.get(ToolConfig, tool)
    for key, value in data.model_dump().items():
        setattr(config, key, value)
    db.commit()
    return {'tool': tool, **data.model_dump()}
