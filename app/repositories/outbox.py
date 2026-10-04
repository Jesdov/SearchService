from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.outbox import Outbox, OutboxOperation


class OutboxRepository:

    def __init__(self, session: AsyncSession):
        """Сохраняет сессию базы данных."""
        self.session = session

    async def create_bulk(self, post_ids: list[int], operation: OutboxOperation) -> None:
        """Записывает события изменения постов в outbox."""
        if not post_ids:
            return

        data = [
            {"post_id": post_id, "operation": operation}
            for post_id in post_ids
        ]

        await self.session.execute(insert(Outbox), data)

    async def get_unprocessed(self, limit: int) -> list[Outbox]:
        """Возвращает пачку необработанных событий в порядке появления."""
        stmt = (
            select(Outbox)
            .where(Outbox.is_processed.is_(False))
            .order_by(Outbox.id)
            .limit(limit)
        )

        result = await self.session.scalars(stmt)
        return list(result.all())

    async def mark_processed(self, ids: list[int]) -> None:
        """Отмечает события обработанными."""
        stmt = (
            update(Outbox)
            .where(Outbox.id.in_(ids))
            .values(is_processed=True, processed_at=func.now())
        )

        await self.session.execute(stmt)
