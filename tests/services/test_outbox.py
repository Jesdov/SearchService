from datetime import datetime

import pytest
from elasticsearch import AsyncElasticsearch
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.outbox import OutboxOperation
from app.database.models.post import Post
from app.elasticsearch.indexes import POST_INDEX
from app.repositories.elastic_post import ElasticPostRepository
from app.repositories.outbox import OutboxRepository
from app.repositories.post import PostRepository
from app.schemas.post import PostCreate


async def test_process_pending_indexes_posts(
    session: AsyncSession,
    elasticsearch_client: AsyncElasticsearch,
    outbox_service,
):
    """Проверка переноса событий создания постов в Elasticsearch."""
    created_posts = await PostRepository(session).create_bulk([
        PostCreate(text="Post about Python", rubrics=["python"], created_date=datetime.now()),
        PostCreate(text="Post about FastAPI", rubrics=["fastapi"], created_date=datetime.now()),
    ])
    await OutboxRepository(session).create_bulk(
        [post.id for post in created_posts],
        OutboxOperation.CREATE,
    )
    await session.commit()

    processed = await outbox_service.process_pending(100)

    assert processed == len(created_posts)

    await elasticsearch_client.indices.refresh(index=POST_INDEX)

    response = await elasticsearch_client.mget(
        index=POST_INDEX,
        ids=[post.id for post in created_posts],
    )

    assert response["docs"][0]["_source"]["text"] == "Post about Python"
    assert response["docs"][1]["_source"]["text"] == "Post about FastAPI"
    assert await OutboxRepository(session).get_unprocessed(100) == []


async def test_process_pending_deletes_posts(
    session: AsyncSession,
    elasticsearch_client: AsyncElasticsearch,
    outbox_service,
):
    """Проверка удаления документов постов по событиям outbox."""
    created_posts = await PostRepository(session).create_bulk([
        PostCreate(text="Post about Python", rubrics=["python"], created_date=datetime.now()),
    ])
    post_id = created_posts[0].id

    await OutboxRepository(session).create_bulk([post_id], OutboxOperation.CREATE)
    await session.commit()

    await outbox_service.process_pending(100)
    await elasticsearch_client.indices.refresh(index=POST_INDEX)

    await PostRepository(session).delete_by_id(post_id)
    await OutboxRepository(session).create_bulk([post_id], OutboxOperation.DELETE)
    await session.commit()

    processed = await outbox_service.process_pending(100)

    assert processed == 1

    await elasticsearch_client.indices.refresh(index=POST_INDEX)

    exists = await elasticsearch_client.exists(index=POST_INDEX, id=post_id)

    assert not exists


async def test_process_pending_indexes_current_state(
    session: AsyncSession,
    elasticsearch_client: AsyncElasticsearch,
    outbox_service,
):
    """Проверка, что в индекс попадает актуальное состояние поста из БД."""
    created_posts = await PostRepository(session).create_bulk([
        PostCreate(text="Old text", rubrics=["python"], created_date=datetime.now()),
    ])
    post_id = created_posts[0].id

    await OutboxRepository(session).create_bulk([post_id], OutboxOperation.CREATE)
    await session.commit()

    await session.execute(
        update(Post).where(Post.id == post_id).values(text="New text")
    )
    await session.commit()

    await outbox_service.process_pending(100)
    await elasticsearch_client.indices.refresh(index=POST_INDEX)

    response = await elasticsearch_client.get(index=POST_INDEX, id=post_id)

    assert response["_source"]["text"] == "New text"


async def test_process_pending_without_events(outbox_service):
    """Проверка обработки пустого outbox."""
    assert await outbox_service.process_pending(100) == 0


async def test_process_pending_keeps_events_on_es_error(
    mocker,
    session: AsyncSession,
    outbox_service,
):
    """Проверка, что при сбое Elasticsearch события остаются необработанными."""
    created_posts = await PostRepository(session).create_bulk([
        PostCreate(text="Post about Python", rubrics=["python"], created_date=datetime.now()),
    ])
    await OutboxRepository(session).create_bulk([created_posts[0].id], OutboxOperation.CREATE)
    await session.commit()

    mocker.patch.object(
        ElasticPostRepository,
        "sync_bulk",
        side_effect=Exception("Elasticsearch недоступен"),
    )

    with pytest.raises(Exception):
        await outbox_service.process_pending(100)

    assert len(await OutboxRepository(session).get_unprocessed(100)) == 1
