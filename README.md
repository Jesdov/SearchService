# Search Service

Поисковик по текстам документов: FastAPI + PostgreSQL + Elasticsearch, всё асинхронно, работает в Docker.

Сервис принимает файлы `.xlsx`/`.csv` с документами (колонки `text`, `created_date`, `rubrics`),
ищет по тексту средствами Elasticsearch — до 20 документов со всеми полями БД, от новых к старым —
и удаляет документы по `id`. Сами документы хранятся в PostgreSQL, полнотекстовый поиск идёт по
индексу Elasticsearch.

Хранилища синхронизируются через outbox: API в одной транзакции с данными пишет событие изменения,
а отдельный воркер переносит события в Elasticsearch. Outbox выбран за счёт большей отказоустойчивости —
если Elasticsearch недоступен или сервис упал между записями, изменение не теряется: событие остаётся
в БД и применится позже.

## Запуск

Требуется Docker с Compose v2 и ~4 ГБ свободной памяти. Конфигурация берётся из `.env`, пример — в `.env.example`: обязательны пароли `ELASTIC_PASSWORD` и `DB_PASSWORD`, а также `STACK_VERSION` — версия образа Elasticsearch.

```bash
cp .env.example .env
docker compose up --build -d
```

Первый старт Elasticsearch занимает 1–2 минуты, готовность видна в `docker compose ps`.
Проверка: `curl localhost:8000/health` возвращает `{"status":"ok"}`.

- API — http://localhost:8000
- Swagger — http://localhost:8000/docs, спецификация OpenAPI — [docs.json](docs.json)

Остановить сервисы: `docker compose down`, остановить и удалить данные: `docker compose down -v`.

## Данные

База и индекс стартуют пустыми, поэтому сначала нужно загрузить посты: `POST /api/v1/posts/import`,
файл [посты.xlsx](посты.xlsx) (1500 документов) или другой `.xlsx`/`.csv` с колонками `text`,
`created_date`, `rubrics` — в поле `file`. После импорта воркер индексирует документы в течение
секунды, и их начинает находить поиск — `GET /api/v1/posts/search?query=...`.

## Тесты

```bash
cp .env.test.example .env.test
docker compose --env-file .env.test -f docker-compose.test.yaml run --build --rm tests
```

Тесты поднимают отдельные PostgreSQL и Elasticsearch и прогоняют pytest в контейнере.

## Структура

```
app/
  main.py           # сборка FastAPI-приложения
  api/              # роуты постов и тексты для OpenAPI
  core/config.py    # настройки из .env
  database/         # engine, сессия, модели posts и outbox
  elasticsearch/    # клиент и маппинг индекса
  repositories/     # запросы к PostgreSQL и Elasticsearch
  schemas/          # pydantic-модели запросов и ответов
  services/         # логика: посты и применение событий outbox
  workers/          # воркер переноса событий в Elasticsearch
  utils/            # разбор .xlsx и .csv
  exceptions.py     # доменные исключения
migration/          # Alembic: env.py и versions/ с миграциями
alembic.ini         # конфиг Alembic
tests/              # функциональные тесты (api, services, repositories, workers)
Dockerfile          # образ приложения
docker-compose.yaml        # основной стек
docker-compose.test.yaml   # тестовый стек
docker-compose.dev.yaml    # override для разработки
docs.json           # спецификация OpenAPI
посты.xlsx          # датасет для импорта: 1500 постов
requirements.txt    # зависимости
pytest.ini          # настройки pytest
.env.example        # шаблон конфигурации
.env.test.example   # шаблон конфигурации тестов
```
