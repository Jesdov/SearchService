from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

class PostCreate(BaseModel):
    rubrics: list[str]
    text: str
    created_date: datetime

class PostResponse(BaseModel):
    id: int = Field(description="Идентификатор документа")
    rubrics: list[str] = Field(description="Массив рубрик документа")
    text: str = Field(description="Текст документа")
    created_date: datetime = Field(description="Дата создания документа")

    model_config = ConfigDict(from_attributes=True)

class ImportResponse(BaseModel):
    detail: str = Field(description="Результат импорта")
    count: int = Field(description="Количество импортированных постов")

class DeleteResponse(BaseModel):
    detail: str = Field(description="Результат удаления")
