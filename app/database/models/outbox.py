from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models.base import Base


class OutboxOperation(StrEnum):
    """Тип изменения поста, которое нужно применить в Elasticsearch."""

    CREATE = "create"
    DELETE = "delete"


class Outbox(Base):
    __tablename__ = "outbox"

    id: Mapped[int] = mapped_column(primary_key=True)
    # без ForeignKey: событие удаления должно жить после исчезновения поста
    post_id: Mapped[int] = mapped_column()
    operation: Mapped[str] = mapped_column(String(16))
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_outbox_unprocessed", "id", postgresql_where=text("NOT is_processed")),
    )
