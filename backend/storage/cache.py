import redis.asyncio as aioredis
from backend.config import settings


async def get_valkey() -> aioredis.Redis:
    return aioredis.from_url(
        settings.valkey_url,
        encoding="utf-8",
        decode_responses=True,
    )

# Full cache operations implemented in Task #10
