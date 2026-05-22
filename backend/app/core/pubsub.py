import json

import redis
import redis.asyncio as aioredis

from app.config import settings

_PREFIX = "doc:"


def publish_sync(document_id: str, payload: dict) -> None:
    r = redis.from_url(settings.REDIS_URL)
    try:
        r.publish(f"{_PREFIX}{document_id}", json.dumps(payload))
    finally:
        r.close()


async def publish_async(document_id: str, payload: dict) -> None:
    r = aioredis.from_url(settings.REDIS_URL)
    try:
        await r.publish(f"{_PREFIX}{document_id}", json.dumps(payload))
    finally:
        await r.aclose()


def channel(document_id: str) -> str:
    return f"{_PREFIX}{document_id}"
