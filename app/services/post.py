import logging

from sqlalchemy.ext.asyncio import AsyncSession
from elasticsearch import AsyncElasticsearch
from typing import BinaryIO

from app.repositories.post import PostRepository
from app.repositories.outbox import OutboxRepository
from app.repositories.elastic_post import ElasticPostRepository
from app.database.models.outbox import OutboxOperation
from app.utils.parsers import parse_posts
from app.exceptions import PostNotFoundException


logger = logging.getLogger(__name__)

class PostService:
    def __init__(self, session: AsyncSession, client: AsyncElasticsearch):
        """Создаёт сервис и его репозитории для БД и Elasticsearch."""
        self.session = session
        self.post_repo = PostRepository(session)
        self.outbox_repo = OutboxRepository(session)
        self.elastic_post_repo = ElasticPostRepository(client)

    async def import_posts(self, file: BinaryIO, extension: str):
        """Импортирует посты из файла .xlsx или .csv в БД и ставит их индексацию в outbox."""
        try:
            posts = parse_posts(file, extension)
            created_posts = await self.post_repo.create_bulk(posts)
            await self.outbox_repo.create_bulk(
                [post.id for post in created_posts],
                OutboxOperation.CREATE,
            )
            await self.session.commit()
        except Exception:
            logger.exception("Ошибка при импорте постов, выполняется откат транзакции")
            await self.session.rollback()
            raise

        return created_posts

    async def search_posts(self, text: str):
        """Ищет посты по тексту через Elasticsearch и загружает их из БД."""
        ids = await self.elastic_post_repo.search(text)

        if not ids:
            return []
        
        posts = await self.post_repo.get_by_ids(ids)
        return posts

    async def delete_post(self, post_id: int):
        """Удаляет пост из БД и ставит его удаление из индекса в outbox."""
        try:
            deleted_id = await self.post_repo.delete_by_id(post_id)

            if deleted_id is None:
                raise PostNotFoundException()

            await self.outbox_repo.create_bulk([deleted_id], OutboxOperation.DELETE)
            await self.session.commit()

        except PostNotFoundException:
            logger.warning("Пост с id=%s не найден", post_id)
            await self.session.rollback()
            raise

        except Exception:
            logger.exception("Ошибка при удалении поста с id=%s, выполняется откат транзакции", post_id)
            await self.session.rollback()
            raise

