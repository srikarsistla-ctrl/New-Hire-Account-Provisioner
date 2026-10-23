from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

TOOLS = {
    'google_workspace': {'name': 'Google Workspace', 'roles': ['viewer', 'member', 'admin'], 'color': '#4285f4', 'icon': 'G'},
    'slack': {'name': 'Slack', 'roles': ['guest', 'member', 'admin'], 'color': '#743d77', 'icon': '#'},
    'github': {'name': 'GitHub', 'roles': ['viewer', 'editor', 'admin'], 'color': '#24292f', 'icon': 'GH'},
    'jira': {'name': 'Jira', 'roles': ['viewer', 'editor', 'admin'], 'color': '#1868db', 'icon': 'J'},
    'confluence': {'name': 'Confluence', 'roles': ['viewer', 'editor', 'admin'], 'color': '#2684ff', 'icon': 'C'},
    'zoom': {'name': 'Zoom', 'roles': ['basic', 'licensed', 'admin'], 'color': '#2d8cff', 'icon': 'Z'},
    'salesforce': {'name': 'Salesforce', 'roles': ['viewer', 'standard', 'admin'], 'color': '#009edb', 'icon': 'SF'},
    'aws_iam': {'name': 'AWS IAM', 'roles': ['viewer', 'developer', 'admin'], 'color': '#b9740b', 'icon': 'AWS'},
}

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

class Assignment(StrictModel):
    tool: str
    role: str | None = None

    @model_validator(mode='after')
    def valid_role(self):
        if self.tool not in TOOLS:
            raise ValueError('Unknown SaaS tool')
        if self.role is None:
            self.role = TOOLS[self.tool]['roles'][0]
        if self.role not in TOOLS[self.tool]['roles']:
            raise ValueError(f'Invalid role for {self.tool}')
        return self

class HireDetails(StrictModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    department: str = Field(min_length=2, max_length=80)
    job_title: str = Field(min_length=2, max_length=100)
    manager: str = Field(min_length=2, max_length=100)
    start_date: date

    @field_validator('email')
    @classmethod
    def synthetic_email(cls, value):
        value = value.lower()
        if value.split('@')[1] not in {'example.com', 'example.org', 'example.net'}:
            raise ValueError('Use a synthetic email at example.com, example.org, or example.net')
        return value

class HireInput(HireDetails):
    assignments: list[Assignment] = Field(min_length=1, max_length=8)

    @field_validator('assignments')
    @classmethod
    def unique_tools(cls, value):
        if len({a.tool for a in value}) != len(value):
            raise ValueError('Select each tool only once')
        return value

class RecommendationInput(HireDetails):
    responsibilities: str = Field(min_length=10, max_length=2000)

class PlanUpdate(StrictModel):
    revision: int = Field(ge=1)
    assignments: list[Assignment] = Field(min_length=1, max_length=8)
    _unique = field_validator('assignments')(HireInput.unique_tools.__func__)

class Decision(StrictModel):
    revision: int = Field(ge=1)
    decision: Literal['approve', 'reject']
    confirmed: bool

class MockSettings(StrictModel):
    total: int = Field(ge=0, le=10000)
    default_role: str
    fail_create: bool = False
    fail_group: bool = False
