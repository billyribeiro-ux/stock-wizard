"""Redis pub/sub bridge for the live signal stream."""

from __future__ import annotations

from collections.abc import AsyncIterator

import redis.asyncio as aioredis

from common.settings import get_settings

_settings = get_settings()


def signal_channel(run_id: str) -> str:
    return f"signals:{run_id}"


def get_redis() -> aioredis.Redis:
    return aioredis.from_url(_settings.redis_url, decode_responses=True)


async def publish_signal(redis: aioredis.Redis, run_id: str, payload: str) -> None:
    await redis.publish(signal_channel(run_id), payload)


async def subscribe_signals(run_id: str) -> AsyncIterator[str]:
    """Yield JSON signal payloads published to this run's channel."""
    redis = get_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(signal_channel(run_id))
    try:
        async for message in pubsub.listen():
            if message.get("type") == "message":
                yield message["data"]
    finally:
        await pubsub.unsubscribe(signal_channel(run_id))
        await pubsub.aclose()
