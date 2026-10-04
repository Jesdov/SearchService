from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import docs
from app.api.v1.posts import router as search_router
from app.core.config import settings
from app.elasticsearch.client import client
from app.schemas.common import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Закрывает клиент Elasticsearch на остановке приложения."""
    try:
        yield
    finally:
        await client.close()


def create_app() -> FastAPI:
    """Создаёт и настраивает FastAPI-приложение."""
    app = FastAPI(
        title=settings.APP_NAME,
        description=docs.APP_DESCRIPTION,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        servers=docs.SERVERS,
        openapi_tags=docs.TAGS,
        lifespan=lifespan,
    )

    app.include_router(search_router, prefix=settings.API_V1_PREFIX)

    @app.get(
        "/health",
        tags=["Служебное"],
        summary="Проверка работоспособности",
        response_model=HealthResponse,
        responses=docs.HEALTH_RESPONSES,
    )
    async def health() -> HealthResponse:
        """Возвращает статус работоспособности сервиса."""
        return HealthResponse(status="ok")

    return app


app = create_app()
