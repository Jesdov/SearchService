import asyncio
import logging

from app.core.config import settings
from app.database.session import SessionFactory
from app.elasticsearch.client import client
from app.repositories.elastic_post import ElasticPostRepository
from app.services.outbox import OutboxService


logger = logging.getLogger(__name__)


async def run_outbox_worker() -> None:
    """Постоянно переносит изменения постов из outbox в Elasticsearch."""
    elastic_post_repo = ElasticPostRepository(client)
    outbox_service = OutboxService(SessionFactory, client)

    try:
        await elastic_post_repo.index_create()
    except Exception:
        logger.exception("Не удалось создать индекс постов")

    while True:
        try:
            processed = await outbox_service.process_pending(settings.OUTBOX_BATCH_SIZE)
        except Exception:
            logger.exception("Ошибка при обработке событий outbox")
            processed = 0

        if processed < settings.OUTBOX_BATCH_SIZE:
            await asyncio.sleep(settings.OUTBOX_POLL_INTERVAL)


def main() -> None:
    """Запускает воркер отдельным процессом."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info(
        "Воркер outbox запущен: интервал опроса %s с, размер пачки %s",
        settings.OUTBOX_POLL_INTERVAL,
        settings.OUTBOX_BATCH_SIZE,
    )

    asyncio.run(run_outbox_worker())


if __name__ == "__main__":
    main()
