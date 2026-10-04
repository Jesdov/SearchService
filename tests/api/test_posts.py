from datetime import datetime
from io import BytesIO

import pytest
from elasticsearch import AsyncElasticsearch
from httpx import AsyncClient
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.outbox import Outbox, OutboxOperation
from app.database.models.post import Post
from app.elasticsearch.indexes import POST_INDEX


POSTS = [
    ("Post about Python", "01.10.2026 10:00", "['python']"),
    ("Post about FastAPI", "02.10.2026 10:00", "['fastapi']"),
]


def make_excel(rows: list[tuple[str, str, str]]) -> BytesIO:
    """Собирает .xlsx-файл с постами в памяти."""
    workbook = Workbook()
    sheet = workbook.active

    sheet.append(["text", "created_date", "rubrics"])

    for row in rows:
        sheet.append(list(row))

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)

    return buffer


def make_file(rows: list[tuple[str, str, str]], filename: str = "posts.xlsx") -> dict:
    """Собирает multipart-содержимое запроса с файлом постов."""
    return {"file": (filename, make_excel(rows))}


def make_csv_file(rows: list[tuple[str, str, str]], delimiter: str) -> dict:
    """Собирает multipart-содержимое запроса с .csv-файлом в кодировке Excel."""
    lines = [delimiter.join(("text", "created_date", "rubrics"))]
    lines += [delimiter.join(row) for row in rows]
    content = ("\r\n".join(lines) + "\r\n").encode("utf-8-sig")

    return {"file": ("posts.csv", BytesIO(content))}


async def test_import_posts(
    api_client: AsyncClient,
    session: AsyncSession,
    elasticsearch_client: AsyncElasticsearch,
):
    """Проверка импорта через API: посты и события в БД, в Elasticsearch ничего не уходит."""
    response = await api_client.post(
        "/api/v1/posts/import",
        files=make_file(POSTS),
    )

    assert response.status_code == 201
    assert response.json() == {
        "detail": "Посты успешно импортированы",
        "count": len(POSTS),
    }

    posts = (await session.scalars(select(Post).order_by(Post.id))).all()

    assert [post.text for post in posts] == [text for text, _, _ in POSTS]
    assert posts[0].rubrics == ["python"]
    assert posts[0].created_date == datetime(2026, 10, 1, 10, 0)

    events = (await session.scalars(select(Outbox).order_by(Outbox.id))).all()

    assert [event.operation for event in events] == [OutboxOperation.CREATE] * len(POSTS)
    assert all(not event.is_processed for event in events)

    assert not await elasticsearch_client.indices.exists(index=POST_INDEX)


@pytest.mark.parametrize("delimiter", [",", ";"])
async def test_import_posts_csv(
    api_client: AsyncClient,
    session: AsyncSession,
    delimiter: str,
):
    """Проверка импорта из .csv с запятой и точкой с запятой в качестве разделителя."""
    response = await api_client.post(
        "/api/v1/posts/import",
        files=make_csv_file(POSTS, delimiter),
    )

    assert response.status_code == 201
    assert response.json() == {
        "detail": "Посты успешно импортированы",
        "count": len(POSTS),
    }

    posts = (await session.scalars(select(Post).order_by(Post.id))).all()

    assert [post.text for post in posts] == [text for text, _, _ in POSTS]
    assert posts[0].rubrics == ["python"]
    assert posts[0].created_date == datetime(2026, 10, 1, 10, 0)


async def test_import_posts_unsupported_extension(api_client: AsyncClient):
    """Проверка отказа на файл неподдерживаемого формата."""
    response = await api_client.post(
        "/api/v1/posts/import",
        files={"file": ("posts.txt", BytesIO(b"fake posts"), "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Поддерживается только .xlsx и .csv"


async def test_search_posts_after_outbox_processed(
    api_client: AsyncClient,
    elasticsearch_client: AsyncElasticsearch,
    outbox_service,
):
    """Проверка, что импортированные посты находятся поиском после переноса событий воркером."""
    await api_client.post(
        "/api/v1/posts/import",
        files=make_file(POSTS),
    )

    # события переносит отдельный процесс-воркер
    await outbox_service.process_pending(100)
    await elasticsearch_client.indices.refresh(index=POST_INDEX)

    response = await api_client.get(
        "/api/v1/posts/search",
        params={"query": "Python"},
    )

    assert response.status_code == 200
    assert [post["text"] for post in response.json()] == ["Post about Python"]


async def test_delete_post(
    api_client: AsyncClient,
    session: AsyncSession,
    elasticsearch_client: AsyncElasticsearch,
    outbox_service,
):
    """Проверка удаления поста через API и обработки события удаления воркером."""
    await api_client.post(
        "/api/v1/posts/import",
        files=make_file(POSTS[:1]),
    )

    await outbox_service.process_pending(100)
    await elasticsearch_client.indices.refresh(index=POST_INDEX)

    post_id = await session.scalar(select(Post.id).order_by(Post.id.desc()).limit(1))

    response = await api_client.delete(f"/api/v1/posts/{post_id}")

    assert response.status_code == 200
    assert await session.scalar(select(Post).where(Post.id == post_id)) is None

    events = (await session.scalars(select(Outbox).where(Outbox.is_processed.is_(False)))).all()

    assert [event.operation for event in events] == [OutboxOperation.DELETE]

    assert await elasticsearch_client.exists(index=POST_INDEX, id=post_id)

    await outbox_service.process_pending(100)
    await elasticsearch_client.indices.refresh(index=POST_INDEX)

    assert not await elasticsearch_client.exists(index=POST_INDEX, id=post_id)


async def test_delete_post_not_found(api_client: AsyncClient):
    """Проверка ответа 404 при удалении несуществующего поста."""
    response = await api_client.delete("/api/v1/posts/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Пост не найден"
