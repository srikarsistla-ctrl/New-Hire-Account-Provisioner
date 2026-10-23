from .slack import Slack
from .google_workspace import GoogleWorkspace
from .github import GitHub
from .jira import Jira
from .confluence import Confluence
from .zoom import Zoom
from .salesforce import Salesforce
from .aws_iam import AWSIAM

PROVIDERS = {c.tool: c for c in [GoogleWorkspace, Slack, GitHub, Jira, Confluence, Zoom, Salesforce, AWSIAM]}

def provider(db, tool):
    return PROVIDERS[tool](db)
