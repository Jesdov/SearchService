import pytest
from pytest_mock import MockerFixture
from elasticsearch import AsyncElasticsearch
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from io import BytesIO

from app.repositories.outbox import OutboxRepository
from app.database.models.outbox import Outbox, OutboxOperation
from app.database.models.post import Post
from app.elasticsearch.indexes import POST_INDEX
from app.services.post import PostService
from app.schemas.post import PostCreate
from app.exceptions import PostNotFoundException


def make_posts(count: int) -> list[PostCreate]:
    """Собирает список постов с убывающей датой создания."""
    return [
        PostCreate(
            text=f"Post about topic {index}",
            rubrics=["test"],
            created_date=datetime.now() - timedelta(days=index),
        )
        for index in range(count)
    ]


async def test_import_posts(
    mocker: MockerFixture,
    session: AsyncSession,
    elasticsearch_client: AsyncElasticsearch,
    outbox_service,
):
    """Проверка, что импорт пишет посты и события в БД, а в Elasticsearch их переносит outbox."""
    post_service = PostService(session, elasticsearch_client)

    posts = make_posts(10)

    mocker.patch("app.services.post.parse_posts", return_value=posts)

    created_posts = await post_service.import_posts(BytesIO(b"fake posts data"), "xlsx")

    assert len(created_posts) == len(posts)

    db_posts = (await session.scalars(select(Post).order_by(Post.id))).all()

    assert [post.text for post in db_posts] == [post.text for post in posts]

    # импорт пишет только в БД и outbox, в Elasticsearch ничего не уходит
    assert not await elasticsearch_client.indices.exists(index=POST_INDEX)

    events = (await session.scalars(select(Outbox).order_by(Outbox.id))).all()

    assert len(events) == len(posts)
    assert all(event.operation == OutboxOperation.CREATE for event in events)
    assert all(not event.is_processed for event in events)

    # события переносит отдельный процесс-воркер
    await outbox_service.process_pending(100)

    await elasticsearch_client.indices.refresh(index=POST_INDEX)

    response = await elasticsearch_client.search(
        index=POST_INDEX,
        query={"match_all": {}},
    )

    assert response["hits"]["total"]["value"] == len(posts)
    assert await OutboxRepository(session).get_unprocessed(100) == []


async def test_import_posts_rolls_back_without_outbox(
    mocker: MockerFixture,
    session: AsyncSession,
    elasticsearch_client: AsyncElasticsearch,
):
    """Проверка, что при сбое записи события outbox посты не сохраняются."""
    post_service = PostService(session, elasticsearch_client)

    mocker.patch("app.services.post.parse_posts", return_value=make_posts(2))
    mocker.patch.object(
        OutboxRepository,
        "create_bulk",
        side_effect=Exception("outbox недоступен"),
    )

    with pytest.raises(Exception):
        await post_service.import_posts(BytesIO(b"fake posts data"), "xlsx")

    assert (await session.scalars(select(Post))).all() == []
    assert not await elasticsearch_client.indices.exists(index=POST_INDEX)


async def test_search_posts(
    mocker: MockerFixture,
    session: AsyncSession,
    elasticsearch_client: AsyncElasticsearch,
    outbox_service,
):
    """Проверка, что поиск возвращает 20 самых свежих постов."""
    post_service = PostService(session, elasticsearch_client)

    posts = make_posts(30)

    mocker.patch("app.services.post.parse_posts", return_value=posts)

    await post_service.import_posts(BytesIO(b"fake posts data"), "xlsx")

    await outbox_service.process_pending(100)
    await elasticsearch_client.indices.refresh(index=POST_INDEX)

    searched_posts = await post_service.search_posts("Post")

    assert [post.text for post in searched_posts] == [post.text for post in posts[:20]]


async def test_delete_post(
    mocker: MockerFixture,
    session: AsyncSession,
    elasticsearch_client: AsyncElasticsearch,
    outbox_service,
):
    """Проверка, что удаление убирает пост из БД и ставит событие для воркера."""
    post_service = PostService(session, elasticsearch_client)

    mocker.patch("app.services.post.parse_posts", return_value=make_posts(1))

    created_posts = await post_service.import_posts(BytesIO(b"fake posts data"), "xlsx")

    await outbox_service.process_pending(100)
    await elasticsearch_client.indices.refresh(index=POST_INDEX)

    await post_service.delete_post(created_posts[0].id)

    post = await session.scalar(
        select(Post).where(Post.id == created_posts[0].id)
    )

    assert post is None

    # документ ещё в индексе, пока событие удаления не обработано
    assert await elasticsearch_client.exists(
        index=POST_INDEX,
        id=created_posts[0].id,
    )

    events = (await session.scalars(select(Outbox).where(Outbox.is_processed.is_(False)))).all()

    assert [event.operation for event in events] == [OutboxOperation.DELETE]

    await outbox_service.process_pending(100)
    await elasticsearch_client.indices.refresh(index=POST_INDEX)

    exists = await elasticsearch_client.exists(
        index=POST_INDEX,
        id=created_posts[0].id,
    )

    assert not exists


async def test_delete_post_not_found(session: AsyncSession, elasticsearch_client: AsyncElasticsearch):
    """Проверка ошибки PostNotFoundException"""
    post_service = PostService(session, elasticsearch_client)

    with pytest.raises(PostNotFoundException):
        await post_service.delete_post(999999)
