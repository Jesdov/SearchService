from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk

from app.database.models.post import Post
from app.elasticsearch.indexes import POST_INDEX, POST_MAPPING

class ElasticPostRepository:

    def __init__(self, client: AsyncElasticsearch):
        """Сохраняет клиент Elasticsearch."""
        self.client = client

    async def index_create(self):
        """Создаёт индекс постов, если он ещё не существует."""
        if await self.client.indices.exists(index=POST_INDEX):
            return
        
        await self.client.indices.create(
            index=POST_INDEX,
            mappings=POST_MAPPING
        )

    async def sync_bulk(self, posts: list[Post], delete_ids: list[int]):
        """Одним bulk-запросом индексирует посты и удаляет отсутствующие в БД документы."""
        actions = [self._index_action(post) for post in posts]
        actions += [self._delete_action(post_id) for post_id in delete_ids]

        if not actions:
            return

        await async_bulk(
            self.client,
            actions,
            ignore_status=404,
            max_retries=3,
        )

    @staticmethod
    def _source(post: Post) -> dict:
        """Собирает документ поста для индекса."""
        return {
            "id": post.id,
            "text": post.text,
        }

    def _index_action(self, post: Post) -> dict:
        """Собирает bulk-действие для индексации поста."""
        return {
            "_index": POST_INDEX,
            "_id": post.id,
            "_source": self._source(post),
        }

    def _delete_action(self, post_id: int) -> dict:
        """Собирает bulk-действие для удаления документа поста."""
        return {
            "_index": POST_INDEX,
            "_id": post_id,
            "_op_type": "delete",
        }

    async def search(self, query: str):
        """Возвращает id постов, подходящих под текстовый запрос."""
        resp = await self.client.search(
            index = POST_INDEX,
            query = {
                "match": {
                    "text": query
                }
            },

            size=20,
        )

        ids = [int(hit["_id"]) for hit in resp["hits"]["hits"]]
        return ids
