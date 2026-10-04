from elasticsearch import AsyncElasticsearch
from datetime import datetime

from app.repositories.elastic_post import ElasticPostRepository
from app.database.models.post import Post
from app.elasticsearch.indexes import POST_INDEX

def make_posts(count: int) -> list[Post]:
    """Собирает список тестовых постов для индекса."""
    return [
        Post(
            id=index,
            text=f"Post about topic {index}",
            rubrics=["test"],
            created_date=datetime.now(),
        )
        for index in range(1, count + 1)
    ]


async def test_sync_bulk_indexes_posts(elasticsearch_client: AsyncElasticsearch):
    """Проверка индексации постов через sync_bulk."""
    elastic_post_repo = ElasticPostRepository(elasticsearch_client)

    posts = make_posts(2)

    await elastic_post_repo.sync_bulk(posts, [])

    await elasticsearch_client.indices.refresh(index=POST_INDEX)

    response = await elasticsearch_client.mget(
        index=POST_INDEX,
        ids=[post.id for post in posts],
    )

    assert response["docs"][0]["_source"] == {"id": 1, "text": "Post about topic 1"}
    assert response["docs"][1]["_source"] == {"id": 2, "text": "Post about topic 2"}


async def test_sync_bulk_deletes_missing_posts(elasticsearch_client: AsyncElasticsearch):
    """Проверка, что sync_bulk удаляет документы, отсутствующие в БД."""
    elastic_post_repo = ElasticPostRepository(elasticsearch_client)

    post1, post2 = make_posts(2)

    await elastic_post_repo.sync_bulk([post1, post2], [])
    await elasticsearch_client.indices.refresh(index=POST_INDEX)

    await elastic_post_repo.sync_bulk([post1], [post2.id])
    await elasticsearch_client.indices.refresh(index=POST_INDEX)

    assert await elasticsearch_client.exists(index=POST_INDEX, id=post1.id)
    assert not await elasticsearch_client.exists(index=POST_INDEX, id=post2.id)


async def test_sync_bulk_ignores_missing_delete(elasticsearch_client: AsyncElasticsearch):
    """Проверка, что удаление отсутствующего документа не поднимает ошибку."""
    elastic_post_repo = ElasticPostRepository(elasticsearch_client)

    post1, = make_posts(1)

    await elastic_post_repo.sync_bulk([post1], [])
    await elasticsearch_client.indices.refresh(index=POST_INDEX)

    await elastic_post_repo.sync_bulk([], [post1.id, 999])
    await elasticsearch_client.indices.refresh(index=POST_INDEX)

    assert not await elasticsearch_client.exists(index=POST_INDEX, id=post1.id)


async def test_search(elasticsearch_client: AsyncElasticsearch):
    """Проверка поиска постов по тексту."""
    elastic_post_repo = ElasticPostRepository(elasticsearch_client)

    await elastic_post_repo.sync_bulk(make_posts(2), [])

    await elasticsearch_client.indices.refresh(index=POST_INDEX)

    ids = await elastic_post_repo.search("Post")

    assert set(ids) == {1, 2}


async def test_search_not_found(elasticsearch_client: AsyncElasticsearch):
    """Проверка пустого результата поиска."""
    elastic_post_repo = ElasticPostRepository(elasticsearch_client)

    await elastic_post_repo.index_create()

    ids = await elastic_post_repo.search("Java")

    assert ids == []
