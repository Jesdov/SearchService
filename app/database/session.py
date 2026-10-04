from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine: AsyncEngine = create_async_engine(
    url=settings.DATABASE_URL,
)

SessionFactory = async_sessionmaker[AsyncSession](engine, expire_on_commit=False)

async def get_db() -> AsyncGenerator:
    """Отдаёт асинхронную сессию БД на время обработки запроса."""
    async with SessionFactory() as session:
        yield session
