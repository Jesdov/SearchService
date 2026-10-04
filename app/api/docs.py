"""Тексты и примеры для документации OpenAPI."""

from app.schemas.common import Detail

SERVERS = [
    {
        "url": "http://localhost:8000",
        "description": "Локальный запуск через docker compose",
    }
]

TAGS = [
    {"name": "Посты", "description": "Импорт, поиск и удаление документов."},
    {"name": "Служебное", "description": "Проверка работоспособности сервиса."},
]

APP_DESCRIPTION = (
    "Сервис поиска по текстам документов.\n\n"
    "Документы хранятся в PostgreSQL, полнотекстовый поиск выполняется по индексу "
    "Elasticsearch. Хранилища синхронизируются через паттерн **outbox**: API пишет "
    "данные и событие изменения в одной транзакции PostgreSQL, а отдельный воркер "
    "переносит события в Elasticsearch. Если Elasticsearch недоступен, события "
    "остаются в БД и применяются позже.\n\n"
    "Эндпоинты:\n"
    "* `POST /api/v1/posts/import` — импорт документов из файла .xlsx или .csv;\n"
    "* `GET /api/v1/posts/search` — поиск по тексту, до 20 документов;\n"
    "* `DELETE /api/v1/posts/{post_id}` — удаление документа из БД и индекса;\n"
    "* `GET /health` — проверка работоспособности сервиса."
)

IMPORT_DESCRIPTION = (
    "Импортирует посты из файла `.xlsx` или `.csv` с колонками `text`, "
    "`created_date` (`ДД.ММ.ГГГГ ЧЧ:ММ`) и `rubrics` (список строк, например "
    "`['python']`). Для .csv поддерживаются UTF-8 и cp1251, разделитель `,` или `;` "
    "определяется по строке заголовка.\n\n"
    "Посты и события outbox сохраняются в PostgreSQL одной транзакцией, индексацию "
    "в Elasticsearch воркер выполняет асинхронно."
)

IMPORT_RESPONSES = {
    201: {
        "description": "Посты импортированы",
        "content": {
            "application/json": {
                "example": {"detail": "Посты успешно импортированы", "count": 2}
            }
        },
    },
    400: {
        "model": Detail,
        "description": "Неподдерживаемое расширение файла",
        "content": {
            "application/json": {
                "example": {"detail": "Поддерживается только .xlsx и .csv"}
            }
        },
    },
    500: {
        "model": Detail,
        "description": "Ошибка при импорте",
        "content": {"application/json": {"example": {"detail": "Ошибка при импорте"}}},
    },
}

SEARCH_DESCRIPTION = (
    "Ищет документы по текстовому запросу в Elasticsearch и возвращает до 20 постов "
    "со всеми полями БД, упорядоченных по убыванию даты создания. Если совпадений "
    "нет, возвращается пустой массив."
)

SEARCH_EXAMPLE = [
    {
        "id": 2,
        "rubrics": ["fastapi"],
        "text": "Post about FastAPI",
        "created_date": "2026-10-02T10:00:00",
    },
    {
        "id": 1,
        "rubrics": ["python"],
        "text": "Post about Python",
        "created_date": "2026-10-01T10:00:00",
    },
]

SEARCH_RESPONSES = {
    200: {
        "description": "Найденные посты (до 20, по убыванию даты создания)",
        "content": {"application/json": {"example": SEARCH_EXAMPLE}},
    }
}

DELETE_DESCRIPTION = (
    "Удаляет пост из PostgreSQL и ставит его удаление из индекса Elasticsearch "
    "в outbox одной транзакцией; из индекса документ убирает воркер."
)

DELETE_RESPONSES = {
    200: {
        "description": "Пост удалён",
        "content": {"application/json": {"example": {"detail": "Пост удалён"}}},
    },
    404: {
        "model": Detail,
        "description": "Пост не найден",
        "content": {"application/json": {"example": {"detail": "Пост не найден"}}},
    },
    500: {
        "model": Detail,
        "description": "Ошибка при удалении",
        "content": {"application/json": {"example": {"detail": "Ошибка при удалении"}}},
    },
}

HEALTH_RESPONSES = {
    200: {
        "description": "Сервис работает",
        "content": {"application/json": {"example": {"status": "ok"}}},
    }
}
