import asyncio
from datetime import datetime

import pytest
from elasticsearch import AsyncElasticsearch
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.models.outbox import OutboxOperation
from app.elasticsearch.indexes import POST_INDEX
from app.repositories.elastic_post import ElasticPostRepository
from app.repositories.outbox import OutboxRepository
from app.repositories.post import PostRepository
from app.schemas.post import PostCreate
from app.workers.outbox import run_outbox_worker


async def create_post_with_event(session: AsyncSession) -> int:
    """Создаёт пост с событием outbox и возвращает его id."""
    created_posts = await PostRepository(session).create_bulk([
        PostCreate(text="Post about Python", rubrics=["python"], created_date=datetime.now()),
    ])
    post_id = created_posts[0].id

    await OutboxRepository(session).create_bulk([post_id], OutboxOperation.CREATE)
    await session.commit()

    return post_id


async def wait_until_processed(session: AsyncSession, timeout: float = 10.0) -> None:
    """Ждёт, пока воркер отметит все события outbox обработанными."""
    for _ in range(int(timeout / 0.1)):
        await asyncio.sleep(0.1)

        if await OutboxRepository(session).get_unprocessed(100) == []:
            return

    pytest.fail(f"Воркер не обработал события outbox за {timeout} с")


async def stop_worker(worker: asyncio.Task) -> None:
    """Останавливает задачу воркера и дожидается её отмены."""
    worker.cancel()

    with pytest.raises(asyncio.CancelledError):
        await worker


async def test_run_outbox_worker_processes_events(
    mocker,
    session: AsyncSession,
    elasticsearch_client: AsyncElasticsearch,
):
    """Проверка, что цикл воркера переносит события из outbox в Elasticsearch."""
    post_id = await create_post_with_event(session)

    mocker.patch.object(settings, "OUTBOX_POLL_INTERVAL", 0.05)

    worker = asyncio.create_task(run_outbox_worker())

    try:
        await wait_until_processed(session)
    finally:
        await stop_worker(worker)

    await elasticsearch_client.indices.refresh(index=POST_INDEX)

    assert await elasticsearch_client.exists(index=POST_INDEX, id=post_id)


async def test_run_outbox_worker_survives_elasticsearch_error(
    mocker,
    session: AsyncSession,
    elasticsearch_client: AsyncElasticsearch,
):
    """Проверка, что цикл воркера переживает сбой Elasticsearch и обрабатывает событие позже."""
    post_id = await create_post_with_event(session)

    original_sync_bulk = ElasticPostRepository.sync_bulk
    is_broken = {"value": True}

    async def flaky_sync_bulk(self, posts, delete_ids):
        """Первый вызов падает, дальше работает как обычно."""
        if is_broken["value"]:
            is_broken["value"] = False
            raise Exception("Elasticsearch недоступен")

        await original_sync_bulk(self, posts, delete_ids)

    mocker.patch.object(ElasticPostRepository, "sync_bulk", flaky_sync_bulk)
    mocker.patch.object(settings, "OUTBOX_POLL_INTERVAL", 0.05)

    worker = asyncio.create_task(run_outbox_worker())

    try:
        await wait_until_processed(session)

        assert not worker.done()
    finally:
        await stop_worker(worker)

    await elasticsearch_client.indices.refresh(index=POST_INDEX)

    assert await elasticsearch_client.exists(index=POST_INDEX, id=post_id)
