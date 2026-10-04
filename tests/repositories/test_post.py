from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.post import PostRepository
from app.schemas.post import PostCreate


def make_posts(count: int) -> list[PostCreate]:
    """Собирает список тестовых постов."""
    return [
        PostCreate(
            rubrics=["test"],
            text=f"Post about topic {index}",
            created_date=datetime.now(),
        )
        for index in range(1, count + 1)
    ]


async def test_create_bulk(session: AsyncSession):
    """Проверка массового создания постов."""
    post_repo = PostRepository(session)

    created_posts = await post_repo.create_bulk(make_posts(3))

    assert [post.text for post in created_posts] == [
        "Post about topic 1",
        "Post about topic 2",
        "Post about topic 3",
    ]
    assert all(post.id is not None for post in created_posts)


async def test_get_by_ids(session: AsyncSession):
    """Проверка получения постов по списку id."""
    post_repo = PostRepository(session)

    ids = [post.id for post in await post_repo.create_bulk(make_posts(3))]

    result = await post_repo.get_by_ids(ids)

    assert len(result) == 3
    assert {post.id for post in result} == set(ids)


async def test_get_all_by_ids_without_limit(session: AsyncSession):
    """Проверка, что получение постов для outbox не ограничено 20 записями."""
    post_repo = PostRepository(session)

    ids = [post.id for post in await post_repo.create_bulk(make_posts(25))]

    result = await post_repo.get_all_by_ids(ids)

    assert len(result) == 25
    assert {post.id for post in result} == set(ids)


async def test_delete_by_id(session: AsyncSession):
    """Проверка удаления поста по id."""
    post_repo = PostRepository(session)

    post_id = (await post_repo.create_bulk(make_posts(1)))[0].id

    deleted_id = await post_repo.delete_by_id(post_id)

    assert await post_repo.get_by_ids([post_id]) == []
    assert deleted_id == post_id
