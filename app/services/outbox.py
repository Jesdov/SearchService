import logging

from elasticsearch import AsyncElasticsearch
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.elastic_post import ElasticPostRepository
from app.repositories.outbox import OutboxRepository
from app.repositories.post import PostRepository


logger = logging.getLogger(__name__)


class OutboxService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], client: AsyncElasticsearch):
        """Сохраняет фабрику сессий БД и клиент Elasticsearch."""
        self.session_factory = session_factory
        self.elastic_post_repo = ElasticPostRepository(client)

    async def process_pending(self, limit: int) -> int:
        """Применяет пачку необработанных событий outbox и возвращает их количество."""
        async with self.session_factory() as session:
            events = await OutboxRepository(session).get_unprocessed(limit)

            if not events:
                return 0

            event_ids = [event.id for event in events]
            post_ids = list({event.post_id for event in events})
            posts = await PostRepository(session).get_all_by_ids(post_ids)

        found_ids = {post.id for post in posts}
        delete_ids = [post_id for post_id in post_ids if post_id not in found_ids]

        await self.elastic_post_repo.sync_bulk(posts, delete_ids)

        async with self.session_factory() as session:
            await OutboxRepository(session).mark_processed(event_ids)
            await session.commit()

        logger.info("События outbox применены в Elasticsearch: %s", len(event_ids))
        return len(event_ids)
