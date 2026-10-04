import logging

from fastapi import APIRouter, UploadFile, HTTPException, Depends, File, Path, Query

from sqlalchemy.ext.asyncio import AsyncSession

from app.api import docs
from app.database.session import get_db
from app.services.post import PostService
from app.elasticsearch.client import client
from app.schemas.post import DeleteResponse, ImportResponse, PostResponse
from app.exceptions import PostNotFoundException


logger = logging.getLogger(__name__)

router = APIRouter(prefix = "/posts", tags = ["Посты"])

def get_post_service(
        session: AsyncSession = Depends(get_db)
):
    """Создаёт сервис постов с текущей сессией БД и клиентом Elasticsearch."""
    return PostService(session, client)

@router.post(
    "/import",
    status_code=201,
    response_model=ImportResponse,
    summary="Импорт постов",
    description=docs.IMPORT_DESCRIPTION,
    responses=docs.IMPORT_RESPONSES,
)
async def import_posts(
    file: UploadFile = File(description="Файл .xlsx или .csv"),
    service: PostService = Depends(get_post_service)
):
    """Импортирует посты из загруженного файла .xlsx или .csv."""
    file_extension = file.filename.split(".")[-1].lower()
    if file_extension not in ["xlsx", "csv"]:
        logger.warning(
            "Отклонён импорт файла с неподдерживаемым расширением: %s",
            file.filename,
        )
        raise HTTPException(
            status_code=400,
            detail="Поддерживается только .xlsx и .csv"
        )

    try:
        posts = await service.import_posts(file.file, file_extension)
    except Exception:
        logger.exception("Ошибка при импорте постов из файла %s", file.filename)
        raise HTTPException(
            status_code=500,
            detail="Ошибка при импорте"
        )

    return {
        "detail": "Посты успешно импортированы",
        "count": len(posts)
    }


@router.get(
    "/search",
    response_model=list[PostResponse],
    summary="Поиск постов",
    description=docs.SEARCH_DESCRIPTION,
    responses=docs.SEARCH_RESPONSES,
)
async def search_posts(
    query: str = Query(description="Произвольный текстовый запрос"),
    service: PostService = Depends(get_post_service)
):
    """Ищет посты по текстовому запросу."""
    posts = await service.search_posts(query)
    return posts

@router.delete(
    "/{post_id}",
    response_model=DeleteResponse,
    summary="Удаление поста",
    description=docs.DELETE_DESCRIPTION,
    responses=docs.DELETE_RESPONSES,
)
async def delete_post(
    post_id: int = Path(description="Идентификатор поста"),
    service: PostService = Depends(get_post_service)
):
    """Удаляет пост по его идентификатору."""
    try:
        await service.delete_post(post_id)
    except PostNotFoundException:
        logger.warning("Пост с id=%s не найден", post_id)
        raise HTTPException(
            status_code=404,
            detail="Пост не найден"
        )
    except Exception:
        logger.exception("Ошибка при удалении поста с id=%s", post_id)
        raise HTTPException(
            status_code=500,
            detail="Ошибка при удалении"
        ) 

    return {"detail": "Пост удалён"}
