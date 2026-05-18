"""
AdminConfig model — key/value store for runtime admin settings.

Table: admin_config
Skill ref: skill_db_schema.md (Table 3)
"""

from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AdminConfig(Base):
    """Key-value configuration table managed via the Admin Dashboard."""

    __tablename__ = "admin_config"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    setting_key: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        nullable=False,
        index=True,
        doc="Configuration key (e.g., 'enable_redis_cache', 'max_retries').",
    )
    setting_value: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        doc="Configuration value (e.g., 'true', '3').",
    )

    def __repr__(self) -> str:
        return f"<AdminConfig {self.setting_key}={self.setting_value}>"
