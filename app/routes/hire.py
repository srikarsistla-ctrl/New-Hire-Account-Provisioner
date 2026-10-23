from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.agent.validator import HireInput, PlanUpdate, RecommendationInput
from app.agent.recommender import recommend
from app.agent.policy import policy_document
from app.agent.planner import build_plan
from app.agent.provisioner import review_plan
from app.models import Employee
from app.services.provisioning_service import lock, log, snapshot, get_hire, check_pending

router = APIRouter(prefix='/api/hires', tags=['Hires'])

@router.get('/policy')
def get_policy(department: str = 'Engineering'):
    return policy_document(department)

@router.post('/recommend', status_code=201)
def recommend_hire(data: RecommendationInput, db: Session = Depends(get_db)):
    assignments, mode, note = recommend(data)
    hire = Employee(**data.model_dump(exclude={'responsibilities'}))
    hire.plan = build_plan(db, hire, assignments)
    explanations = {a.tool: a.reason for a in assignments}
    for step in hire.plan:
        step['reason'] = explanations[step['tool']]
        step['recommendation_source'] = mode
    hire.agent_mode, hire.agent_note = mode, note
    db.add(hire)
    db.flush()
    log(db, hire, 'job_context', data.responsibilities)
    log(db, hire, 'recommend', note)
    for step in hire.plan:
        log(db, hire, 'recommendation', f'{step["role"]}: {step["reason"]} Policy {step["policy_version"]}.', step['tool'])
        log(db, hire, 'inspect', f'Exists: {step["exists"]}; seats: {step["seats"]}; default role: {step["default_role"]}.', step['tool'])
    log(db, hire, 'await_approval', 'Recommended plan saved. No accounts have been changed.')
    db.commit()
    return snapshot(db, hire)

@router.post('', status_code=201)
def create_hire(data: HireInput, db: Session = Depends(get_db)):
    hire = Employee(**data.model_dump(exclude={'assignments'}))
    db.add(hire)
    db.flush()
    log(db, hire, 'collect', 'Validated synthetic hire details and tool/role combinations.')
    hire.plan = build_plan(db, hire, data.assignments)
    log(db, hire, 'plan', 'Applied least-privilege defaults and dependency ordering.')
    for step in hire.plan:
        log(db, hire, 'inspect', f'Exists: {step["exists"]}; seats: {step["seats"]}; default role: {step["default_role"]}.', step['tool'])
    # Commit before optional network work, avoiding a long SQLite writer lock.
    db.commit()
    hire.agent_mode, hire.agent_note = review_plan(db, hire)
    log(db, hire, 'await_approval', 'Plan prepared. No SaaS accounts have been changed.')
    db.commit()
    return snapshot(db, hire)

@router.get('/{hire_id}')
def get_request(hire_id: int, db: Session = Depends(get_db)):
    return snapshot(db, get_hire(db, hire_id))

@router.put('/{hire_id}/plan')
def update_plan(hire_id: int, data: PlanUpdate, db: Session = Depends(get_db)):
    lock(db)
    hire = get_hire(db, hire_id)
    check_pending(hire, data.revision)
    hire.plan = build_plan(db, hire, data.assignments)
    hire.revision += 1
    hire.agent_mode = 'rules'
    hire.agent_note = 'Updated plan revalidated. Previous AI commentary was cleared. Review and approve this revision.'
    log(db, hire, 'plan_updated', f'Assignments modified; revision {hire.revision} requires fresh approval.')
    db.commit()
    return snapshot(db, hire)
