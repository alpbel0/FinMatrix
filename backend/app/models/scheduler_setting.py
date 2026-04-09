"""Scheduler settings model for runtime configuration.

This model stores scheduler configuration that can be modified at runtime,
particularly the financial reporting mode.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SchedulerSetting(Base):
    """Scheduler runtime settings.

    This is a single-row table (enforced by check constraint) that stores
    global scheduler configuration like reporting mode.

    Attributes:
        id: Always 1 (single row constraint)
        financial_reporting_mode: If True, financial sync runs every 4 hours
        financial_reporting_until: Datetime when reporting mode expires
        updated_by_user_id: User who last modified settings
        updated_at: Last modification timestamp
    """

    __tablename__ = "scheduler_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_scheduler_settings_single_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    financial_reporting_mode: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    financial_reporting_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )