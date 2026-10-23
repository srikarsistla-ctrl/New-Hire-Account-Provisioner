from sqlalchemy import JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class ToolConfig(Base):
    __tablename__ = 'tool_configs'
    tool: Mapped[str] = mapped_column(String, primary_key=True)
    total: Mapped[int] = mapped_column(default=100)
    reserved: Mapped[int] = mapped_column(default=10)
    default_role: Mapped[str] = mapped_column(String)
    fail_create: Mapped[bool] = mapped_column(default=False)
    fail_group: Mapped[bool] = mapped_column(default=False)

class ToolAccount(Base):
    __tablename__ = 'tool_accounts'
    __table_args__ = (UniqueConstraint('tool', 'email'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    tool: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    groups: Mapped[list] = mapped_column(JSON, default=list)
