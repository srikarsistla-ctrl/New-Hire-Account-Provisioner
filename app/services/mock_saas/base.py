from sqlalchemy import func, select
from app.models import ToolAccount, ToolConfig
from app.agent.validator import TOOLS

class MockSaaS:
    tool = ''

    def __init__(self, db):
        self.db = db
        self.config = db.get(ToolConfig, self.tool)

    def account(self, email):
        return self.db.scalar(select(ToolAccount).where(ToolAccount.tool == self.tool, ToolAccount.email == email.lower()))

    def check_user_exists(self, email):
        return self.account(email) is not None

    def get_seat_count(self):
        count = self.db.scalar(select(func.count()).select_from(ToolAccount).where(ToolAccount.tool == self.tool))
        return {'used': self.config.reserved + count, 'total': self.config.total}

    def get_default_role(self):
        return self.config.default_role

    def create_account(self, email, name, role):
        if role not in TOOLS[self.tool]['roles']:
            return {'success': False, 'reason': 'Role conflict: unsupported role'}
        if self.check_user_exists(email):
            return {'success': False, 'reason': 'Account already exists'}
        seats = self.get_seat_count()
        if seats['used'] >= seats['total']:
            return {'success': False, 'reason': 'Seat limit reached'}
        if self.config.fail_create:
            return {'success': False, 'reason': 'Simulated provider outage'}
        # Explicitly override the provider default, even when that default is admin.
        self.db.add(ToolAccount(tool=self.tool, email=email.lower(), name=name, role=role, groups=[]))
        self.db.flush()
        return {'success': True}

    def assign_group(self, email, group):
        account = self.account(email)
        if not account or self.config.fail_group:
            return {'success': False, 'reason': 'Simulated group assignment failure'}
        account.groups = sorted(set(account.groups + [group]))
        self.db.flush()
        return {'success': True}

    def set_role(self, email, role):
        account = self.account(email)
        if not account or role not in TOOLS[self.tool]['roles']:
            return {'success': False, 'reason': 'Role conflict'}
        account.role = role
        self.db.flush()
        return {'success': True}
