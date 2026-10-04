import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from elasticsearch import AsyncElasticsearch
from httpx import ASGITransport, AsyncClient

from app.database.session import SessionFactory
from app.core.config import settings
from app.elasticsearch.indexes import POST_INDEX
from app.main import app
from app.services.outbox import OutboxService


async def truncate_tables() -> None:
    """Удаляет посты и события outbox."""
    async with SessionFactory() as session:
        await session.execute(
            text("TRUNCATE TABLE posts, outbox RESTART IDENTITY CASCADE")
        )
        await session.commit()


@pytest.fixture(autouse=True, scope="function")
async def clean_tables():
    """Фикстура очистки: удаляет посты и события outbox до и после каждого теста."""
    await truncate_tables()

    yield

    await truncate_tables()


@pytest.fixture(scope="function")
async def session():
    """Фикстура сессии БД."""
    async with SessionFactory() as session:
        yield session
        await session.rollback()


@pytest.fixture(scope="function")
async def elasticsearch_client():
    """Фикстура клиента Elasticsearch: отдаёт клиент и удаляет индекс после теста."""
    client = AsyncElasticsearch(
        settings.ELASTIC_URL,
        basic_auth=("elastic", settings.ELASTIC_PASSWORD),
        ca_certs="/certs/ca/ca.crt",
    )

    await client.indices.delete(
        index=POST_INDEX,
        ignore_unavailable=True,
    )

    yield client

    await client.indices.delete(
        index=POST_INDEX,
        ignore_unavailable=True,
    )

    await client.close()


@pytest.fixture(scope="function")
async def outbox_service(elasticsearch_client: AsyncElasticsearch):
    """Фикстура сервиса outbox: применяет события к Elasticsearch."""
    return OutboxService(SessionFactory, elasticsearch_client)


@pytest.fixture(scope="function")
async def api_client():
    """Фикстура HTTP-клиента: отправляет запросы в приложение без сети и без lifespan."""
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
