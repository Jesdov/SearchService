from pydantic import BaseModel, Field


class Detail(BaseModel):
    detail: str = Field(description="Текст ошибки")


class HealthResponse(BaseModel):
    status: str = Field(description="Статус сервиса")
