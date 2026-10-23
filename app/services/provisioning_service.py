import logging
from fastapi import HTTPException
from sqlalchemy import select, text
from app.models import Employee, ProvisioningLog
from app.services.mock_saas import provider

logger = logging.getLogger(__name__)

def lock(db):
    # Serialize writes across threads/processes: seats, duplicates and approvals stay atomic.
    db.execute(text('BEGIN IMMEDIATE'))

def log(db, hire, action, detail, tool='agent'):
    db.add(ProvisioningLog(employee_id=hire.id, tool=tool, action=action, detail=detail))

def get_hire(db, hire_id):
    hire = db.get(Employee, hire_id)
    if not hire:
        raise HTTPException(404, 'Provisioning request not found')
    return hire

def check_pending(hire, revision):
    if hire.revision != revision:
        raise HTTPException(409, 'The plan changed. Reload and review the latest revision.')
    if hire.status != 'pending_approval':
        raise HTTPException(409, 'This request has already been decided.')

def snapshot(db, hire):
    logs = db.scalars(select(ProvisioningLog).where(ProvisioningLog.employee_id == hire.id).order_by(ProvisioningLog.id)).all()
    return {'id': hire.id, 'full_name': hire.full_name, 'email': hire.email, 'department': hire.department,
            'job_title': hire.job_title, 'manager': hire.manager, 'start_date': str(hire.start_date),
            'status': hire.status, 'revision': hire.revision, 'plan': hire.plan, 'results': hire.results,
            'agent_mode': hire.agent_mode, 'agent_note': hire.agent_note,
            'logs': [{'id': x.id, 'tool': x.tool, 'action': x.action, 'detail': x.detail,
                      'timestamp': x.timestamp.isoformat().rstrip('Z') + ('Z' if x.timestamp.tzinfo is None else '')} for x in logs]}

def execute(db, hire):
    results = []
    for step in hire.plan:
        tool = step['tool']
        result = {'tool': tool, 'name': step['name'], 'requested_role': step['requested_role'], 'actual_role': None,
                  'status': 'failed', 'message': '', 'group': step['group']}
        try:
            with db.begin_nested():
                api = provider(db, tool)
                exists = api.check_user_exists(hire.email)
                seats = api.get_seat_count()
                log(db, hire, 'preflight', f'Rechecked account existence: {exists}; seats: {seats["used"]}/{seats["total"]}; default role: {api.get_default_role()}.', tool)
                blocked = [r for r in results if r['tool'] in step['dependencies'] and r['actual_role'] is None]
                if blocked and not exists:
                    result.update(status='partial', message='Dependency unavailable: Google Workspace account was not provisioned.')
                elif not exists and seats['used'] >= seats['total']:
                    result.update(status='partial', message='Partial Access: seat limit reached. No account was created; add capacity and submit a new request.')
                else:
                    outcome = api.set_role(hire.email, step['role']) if exists else api.create_account(hire.email, hire.full_name, step['role'])
                    if not outcome['success']:
                        result['message'] = outcome['reason']
                    else:
                        log(db, hire, 'reuse' if exists else 'create', f'Account {"reused" if exists else "created"}; approved role explicitly set to {step["role"]}.', tool)
                        result['actual_role'] = api.account(hire.email).role
                        group_result = api.assign_group(hire.email, step['group'])
                        if group_result['success']:
                            log(db, hire, 'assign_group', f'Assigned department group: {step["group"]}.', tool)
                            result.update(status='already_existed' if exists else 'created', message='Existing account reused and role reconciled.' if exists else 'Account and department group ready.')
                        else:
                            result.update(status='partial', message='Account ready; ' + group_result['reason'])
                            log(db, hire, 'group_failed', group_result['reason'], tool)
                log(db, hire, result['status'], result['message'], tool)
        except Exception:
            logger.exception('Mock provider action failed for %s', tool)
            result.update(status='failed', actual_role=None, message='Provider operation failed and was rolled back for this tool. Other tools continue.')
            log(db, hire, 'failed', result['message'], tool)
        results.append(result)
    hire.results = results
    hire.status = 'completed' if all(r['status'] in {'created', 'already_existed'} for r in results) else 'completed_with_issues'
    log(db, hire, 'finished', f'Provisioning finished: {hire.status}.')
