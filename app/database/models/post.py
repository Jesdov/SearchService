from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ARRAY, String

from app.database.models.base import Base


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    rubrics: Mapped[list[str]] = mapped_column(ARRAY(String))
    text: Mapped[str] = mapped_column(String)
    created_date: Mapped[datetime] = mapped_column()
