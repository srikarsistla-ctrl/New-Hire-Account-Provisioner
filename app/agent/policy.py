"""Server-owned demo access policy. Model output never overrides these rules."""
from fastapi import HTTPException
import os
from app.agent.validator import TOOLS

POLICY_VERSION = '2026-10-21.2'
COMMON = {'google_workspace': 'member', 'slack': 'member', 'confluence': 'editor', 'zoom': 'licensed'}
DEPARTMENTS = {
    'engineering': {'github': 'editor', 'jira': 'editor', 'aws_iam': 'developer'},
    'design': {'jira': 'editor'},
    'sales': {'salesforce': 'standard', 'jira': 'editor'},
    'marketing': {'salesforce': 'standard', 'jira': 'editor'},
    'operations': {'jira': 'editor'},
    'people': {},
}

def allowed_roles(department, tool):
    roles = TOOLS[tool]['roles']
    if os.getenv('ACCESS_POLICY_MODE', 'approval').strip().lower() == 'approval':
        return roles[:]
    # Read-only access remains available for cross-department collaboration.
    cap = {**COMMON, **DEPARTMENTS.get(department.lower().strip(), {})}.get(tool, roles[0])
    return roles[:roles.index(cap) + 1]

def policy_document(department):
    strict = os.getenv('ACCESS_POLICY_MODE', 'approval').strip().lower() != 'approval'
    return {'version': POLICY_VERSION, 'department': department,
            'mode': 'strict' if strict else 'approval',
            'description': ('Minimum access is available across apps. Higher access is limited by department. Admin access requires a separate IT process and cannot be approved here.' if strict else 'Minimum access is the default. Any supported higher role, including admin, requires explicit human approval of the saved plan. No accounts change before approval.'),
            'tools': {tool: allowed_roles(department, tool) for tool in TOOLS}}

def enforce_policy(department, assignments):
    violations = []
    for assignment in assignments:
        if assignment.role not in allowed_roles(department, assignment.tool):
            violations.append(f'{TOOLS[assignment.tool]["name"]}: {assignment.role} is not allowed for {department}; allowed: {", ".join(allowed_roles(department, assignment.tool))}.')
    if violations:
        raise HTTPException(422, 'Company policy: ' + ' '.join(violations))
