import re
from app.agent.validator import TOOLS
from app.services.mock_saas import provider
from app.agent.policy import enforce_policy, POLICY_VERSION

def build_plan(db, hire, assignments):
    enforce_policy(hire.department, assignments)
    requested = {a.tool: a.role for a in assignments}
    plan = []
    group = re.sub(r'[^a-z0-9]+', '-', hire.department.lower()).strip('-') or 'new-hires'
    for tool in TOOLS:  # Google Workspace is first; downstream dependencies follow.
        if tool not in requested:
            continue
        api = provider(db, tool)
        existing = api.account(hire.email)
        seats = api.get_seat_count()
        role = requested[tool]
        warnings = []
        if existing:
            warnings.append(f'Existing account will be reused; role {existing.role} will be reconciled to {role}.')
        elif seats['used'] >= seats['total']:
            warnings.append('Seat limit reached. This tool will report partial access; other tools can continue.')
        if api.get_default_role() != role:
            warnings.append(f'Provider default ({api.get_default_role()}) will be overridden with {role}.')
        if role != TOOLS[tool]['roles'][0]:
            warnings.append('Elevated access requested. Approving this plan explicitly approves this role.')
        dependencies = ['google_workspace'] if tool == 'slack' and 'google_workspace' in requested else []
        plan.append({'tool': tool, 'name': TOOLS[tool]['name'], 'requested_role': role, 'role': role,
                     'group': group, 'exists': bool(existing), 'actual_role': existing.role if existing else None,
                     'seats': seats, 'default_role': api.get_default_role(), 'warnings': warnings,
                     'dependencies': dependencies, 'policy_version': POLICY_VERSION,
                     'reason': 'Selected by the requester. This access is permitted by the department policy; verify that it is needed for the job.'})
    return plan
