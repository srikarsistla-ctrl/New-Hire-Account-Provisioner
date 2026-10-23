from app.models import ToolAccount, ToolConfig
from app.agent.validator import TOOLS

def seed(db):
    for tool, meta in TOOLS.items():
        if db.get(ToolConfig, tool):
            continue
        db.add(ToolConfig(tool=tool, total=100, reserved=12, default_role='admin' if tool == 'github' else meta['roles'][0]))
        if tool in {'slack', 'github', 'google_workspace'}:
            db.add(ToolAccount(tool=tool, email='existing@example.com', name='Morgan Example', role=meta['roles'][0], groups=['general']))
    db.commit()
