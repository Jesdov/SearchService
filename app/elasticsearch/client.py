from elasticsearch import AsyncElasticsearch

from app.core.config import settings

client = AsyncElasticsearch(
    settings.ELASTIC_URL,
    basic_auth=("elastic", settings.ELASTIC_PASSWORD),
    ca_certs="/certs/ca/ca.crt",
)