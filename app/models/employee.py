from datetime import date, datetime, timezone
from sqlalchemy import JSON, Date, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class Employee(Base):
    __tablename__ = 'employees'
    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(254), index=True)
    department: Mapped[str] = mapped_column(String(80))
    job_title: Mapped[str] = mapped_column(String(100))
    manager: Mapped[str] = mapped_column(String(100))
    start_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default='pending_approval')
    revision: Mapped[int] = mapped_column(Integer, default=1)
    plan: Mapped[list] = mapped_column(JSON, default=list)
    results: Mapped[list] = mapped_column(JSON, default=list)
    agent_note: Mapped[str] = mapped_column(String, default='')
    agent_mode: Mapped[str] = mapped_column(String(30), default='rules')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
