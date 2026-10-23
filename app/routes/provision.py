from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.agent.validator import Decision, Assignment
from app.agent.policy import enforce_policy
from app.services.provisioning_service import lock, get_hire, check_pending, log, execute, snapshot

router = APIRouter(prefix='/api/hires', tags=['Approval'])

@router.post('/{hire_id}/decision')
def decide(hire_id: int, data: Decision, db: Session = Depends(get_db)):
    if not data.confirmed:
        raise HTTPException(400, 'Explicit human confirmation is required.')
    lock(db)
    hire = get_hire(db, hire_id)
    if hire.revision == data.revision and data.decision == 'approve' and hire.status in {'completed', 'completed_with_issues'}:
        return snapshot(db, hire)  # Safe double-click/retry: never execute twice.
    check_pending(hire, data.revision)
    if data.decision == 'reject':
        hire.status = 'rejected'
        log(db, hire, 'rejected', f'Human rejected revision {hire.revision}; no accounts changed.')
    else:
        enforce_policy(hire.department, [Assignment(tool=s['tool'], role=s['role']) for s in hire.plan])
        hire.status = 'approved'
        log(db, hire, 'approved', f'Human explicitly approved all listed roles and groups in revision {hire.revision}.')
        execute(db, hire)
    db.commit()
    return snapshot(db, hire)
