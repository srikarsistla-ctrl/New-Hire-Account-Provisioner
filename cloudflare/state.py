"""Bounded demo state. D1 saves the entire transition with compare-and-swap.

No external account mutations occur: all eight providers are simulations.
"""
import re
from datetime import datetime, timezone
from fastapi import HTTPException
from app.agent.validator import TOOLS, Assignment
from app.agent.policy import enforce_policy, POLICY_VERSION


def initial_state():
    return {'next_id': 1, 'hires': {}, 'providers': {
        tool: {'total': 100, 'reserved': 12,
               'default_role': 'admin' if tool == 'github' else meta['roles'][0],
               'fail_create': False, 'fail_group': False,
               'accounts': {'existing@example.com': {'role': meta['roles'][0], 'groups': ['general']}}
               if tool in {'slack', 'github', 'google_workspace'} else {}}
        for tool, meta in TOOLS.items()}}


def inspect(state, tool, email='new.hire@example.com'):
    if tool not in TOOLS:
        raise HTTPException(404, 'Unknown tool')
    p = state['providers'][tool]
    account = p['accounts'].get(email.lower())
    return {'exists': account is not None, 'account': account,
            'seats': {'used': p['reserved'] + len(p['accounts']), 'total': p['total']},
            'default_role': p['default_role']}


def plan(state, hire, assignments):
    enforce_policy(hire['department'], assignments)
    requested = {a.tool: a.role for a in assignments}
    group = re.sub(r'[^a-z0-9]+', '-', hire['department'].lower()).strip('-') or 'new-hires'
    steps = []
    for tool, meta in TOOLS.items():
        if tool not in requested:
            continue
        info = inspect(state, tool, hire['email'])
        role = requested[tool]
        warnings = []
        actual = info['account']['role'] if info['exists'] else None
        if info['exists']:
            warnings.append(f'Existing account will be reused; role {actual} will be reconciled to {role}.')
        elif info['seats']['used'] >= info['seats']['total']:
            warnings.append('Seat limit reached. This tool will report partial access; other tools can continue.')
        if info['default_role'] != role:
            warnings.append(f'Provider default ({info["default_role"]}) will be overridden with {role}.')
        if role != meta['roles'][0]:
            warnings.append('Elevated access requested. Approving this plan explicitly approves this role.')
        steps.append({'tool': tool, 'name': meta['name'], 'role': role, 'requested_role': role,
                      'group': group, 'exists': info['exists'], 'actual_role': actual,
                      'seats': info['seats'], 'default_role': info['default_role'], 'warnings': warnings,
                      'dependencies': ['google_workspace'] if tool == 'slack' and 'google_workspace' in requested else [],
                      'policy_version': POLICY_VERSION,
                      'reason': 'Selected by the requester. Verify that this access is needed for the job.'})
    return steps


def log(hire, action, detail, tool='agent'):
    hire['logs'].append({'id': len(hire['logs']) + 1, 'tool': tool, 'action': action,
                         'detail': detail, 'timestamp': datetime.now(timezone.utc).isoformat()})


def create(state, data, assignments, mode='rules', note=None):
    hire = data.model_dump(mode='json', exclude={'assignments', 'responsibilities'})
    hire.update(id=state['next_id'], revision=1, status='pending_approval', results=[], logs=[],
                agent_mode=mode, agent_note=note or 'Policy checks complete. Human approval is required.')
    hire['plan'] = plan(state, hire, assignments)
    if hasattr(data, 'responsibilities'):
        log(hire, 'job_context', data.responsibilities)
        for step in hire['plan']:
            suggestion = next(a for a in assignments if a.tool == step['tool'])
            step.update(reason=suggestion.reason, recommendation_source=mode)
            log(hire, 'recommendation', f'{step["role"]}: {step["reason"]}', step['tool'])
    log(hire, 'collect', 'Validated synthetic hire details and tool/role combinations.')
    log(hire, 'plan', 'Applied least-privilege defaults and dependency ordering.')
    for step in hire['plan']:
        log(hire, 'inspect', f'Exists: {step["exists"]}; seats: {step["seats"]}; default role: {step["default_role"]}.', step['tool'])
    log(hire, 'await_approval', 'Plan saved. No accounts have been changed.')
    state['hires'][str(hire['id'])] = hire
    state['next_id'] += 1
    return hire


def get_hire(state, hire_id):
    hire = state['hires'].get(str(hire_id))
    if not hire:
        raise HTTPException(404, 'Provisioning request not found')
    return hire


def pending(hire, revision):
    if hire['revision'] != revision:
        raise HTTPException(409, 'The plan changed. Reload and review the latest revision.')
    if hire['status'] != 'pending_approval':
        raise HTTPException(409, 'This request has already been decided.')


def update(state, hire_id, data):
    hire = get_hire(state, hire_id)
    pending(hire, data.revision)
    hire['plan'] = plan(state, hire, data.assignments)
    hire['revision'] += 1
    hire.update(agent_mode='rules', agent_note='Updated plan revalidated. Review and approve this revision.')
    log(hire, 'plan_updated', f'Assignments modified; revision {hire["revision"]} requires fresh approval.')
    return hire


def decide(state, hire_id, data):
    if not data.confirmed:
        raise HTTPException(400, 'Explicit human confirmation is required.')
    hire = get_hire(state, hire_id)
    if hire['revision'] == data.revision and data.decision == 'approve' and hire['status'] in {'completed', 'completed_with_issues'}:
        return hire
    pending(hire, data.revision)
    if data.decision == 'reject':
        hire['status'] = 'rejected'
        log(hire, 'rejected', 'Human rejected the plan; no accounts changed.')
        return hire
    enforce_policy(hire['department'], [Assignment(tool=s['tool'], role=s['role']) for s in hire['plan']])
    log(hire, 'approved', f'Human explicitly approved revision {hire["revision"]}.')
    results = []
    for step in hire['plan']:
        tool = step['tool']
        p = state['providers'][tool]
        info = inspect(state, tool, hire['email'])
        result = {'tool': tool, 'name': step['name'], 'requested_role': step['requested_role'],
                  'actual_role': None, 'status': 'failed', 'message': '', 'group': step['group']}
        log(hire, 'preflight', f'Rechecked account existence: {info["exists"]}; seats: {info["seats"]}.', tool)
        blocked = any(r['tool'] in step['dependencies'] and r['actual_role'] is None for r in results)
        if blocked and not info['exists']:
            result.update(status='partial', message='Dependency unavailable: Google Workspace account was not provisioned.')
        elif not info['exists'] and info['seats']['used'] >= info['seats']['total']:
            result.update(status='partial', message='Partial Access: seat limit reached. No account was created; add capacity and submit a new request.')
        elif not info['exists'] and p['fail_create']:
            result['message'] = 'Simulated provider outage'
        else:
            account = p['accounts'].setdefault(hire['email'], {'role': step['role'], 'groups': []})
            account['role'] = step['role']
            result['actual_role'] = step['role']
            log(hire, 'reuse' if info['exists'] else 'create', f'Approved role explicitly set to {step["role"]}.', tool)
            if p['fail_group']:
                result.update(status='partial', message='Account ready; simulated group assignment failure')
                log(hire, 'group_failed', result['message'], tool)
            else:
                account['groups'] = sorted(set(account['groups'] + [step['group']]))
                result.update(status='already_existed' if info['exists'] else 'created', message='Account and department group ready.')
                log(hire, 'assign_group', f'Assigned department group: {step["group"]}.', tool)
        log(hire, result['status'], result['message'], tool)
        results.append(result)
    hire['results'] = results
    hire['status'] = 'completed' if all(r['status'] in {'created', 'already_existed'} for r in results) else 'completed_with_issues'
    log(hire, 'finished', f'Provisioning finished: {hire["status"]}.')
    return hire
