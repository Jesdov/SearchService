from sqlalchemy import select, insert, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.post import Post
from app.schemas.post import PostCreate

class PostRepository:

    def __init__(self, session: AsyncSession):
        """Сохраняет сессию базы данных."""
        self.session = session

    async def create_bulk(self, posts: list[PostCreate]):
        """Вставляет список постов и возвращает созданные записи."""
        data = [post.model_dump() for post in posts]
        result = await self.session.execute(
            insert(Post).returning(Post), 
            data
        )

        return result.scalars().all()

    async def get_by_ids(self, ids: list[int]):
        """Возвращает до 20 постов с указанными id, отсортированных по дате."""
        stmt = (
            select(Post)
            .where(Post.id.in_(ids))
            .order_by(Post.created_date.desc())
            .limit(20)
        )

        result = await self.session.scalars(stmt)
        return result.all()

    async def get_all_by_ids(self, ids: list[int]):
        """Возвращает все посты с указанными id без ограничения выборки."""
        stmt = select(Post).where(Post.id.in_(ids))

        result = await self.session.scalars(stmt)
        return list(result.all())

    async def delete_by_id(self, post_id: int):
        """Удаляет пост по id и возвращает его id или None, если пост не найден."""
        result = await self.session.execute(delete(Post).where(Post.id == post_id).returning(Post.id))

        return result.scalar_one_or_none()
