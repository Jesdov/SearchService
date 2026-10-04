from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.outbox import Outbox, OutboxOperation
from app.database.session import SessionFactory
from app.repositories.outbox import OutboxRepository


async def test_create_bulk(session: AsyncSession):
    """Проверка записи событий изменения постов."""
    outbox_repo = OutboxRepository(session)

    await outbox_repo.create_bulk([1, 2, 3], OutboxOperation.CREATE)

    events = await outbox_repo.get_unprocessed(10)

    assert [event.post_id for event in events] == [1, 2, 3]
    assert all(event.operation == OutboxOperation.CREATE for event in events)
    assert all(not event.is_processed for event in events)
    assert all(event.processed_at is None for event in events)


async def test_create_bulk_empty(session: AsyncSession):
    """Проверка, что пустой список событий ничего не вставляет."""
    outbox_repo = OutboxRepository(session)

    await outbox_repo.create_bulk([], OutboxOperation.CREATE)
    await session.commit()

    assert await outbox_repo.get_unprocessed(10) == []


async def test_get_unprocessed_order_and_limit(session: AsyncSession):
    """Проверка порядка и лимита выборки необработанных событий."""
    outbox_repo = OutboxRepository(session)

    await outbox_repo.create_bulk([1], OutboxOperation.CREATE)
    await outbox_repo.create_bulk([2], OutboxOperation.CREATE)
    await outbox_repo.create_bulk([3], OutboxOperation.DELETE)
    await session.commit()

    events = await outbox_repo.get_unprocessed(2)

    assert [event.post_id for event in events] == [1, 2]


async def test_mark_processed(session: AsyncSession):
    """Проверка отметки событий обработанными."""
    outbox_repo = OutboxRepository(session)

    await outbox_repo.create_bulk([1, 2], OutboxOperation.CREATE)
    await session.commit()

    events = await outbox_repo.get_unprocessed(10)
    await outbox_repo.mark_processed([events[0].id])
    await session.commit()

    assert [event.post_id for event in await outbox_repo.get_unprocessed(10)] == [2]

    async with SessionFactory() as check_session:
        processed = await check_session.get(Outbox, events[0].id)

        assert processed.is_processed
        assert processed.processed_at is not None
