from __future__ import annotations

import asyncio
import time

from fastapi import Request

from exceptions.exception import ServiceException


class IdempotencyUtil:
    """
    Best-effort idempotency key guard.
    Priority: redis -> in-memory fallback.
    """

    _memory_lock = asyncio.Lock()
    _memory_key_expire_at: dict[str, float] = {}

    @classmethod
    async def require_and_lock_key(
        cls,
        request: Request,
        *,
        scope: str,
        key: str | None,
        ttl_seconds: int = 3600,
    ) -> None:
        """
        Validate idempotency key presence and reject duplicates.
        """
        normalized = (key or '').strip()
        if not normalized:
            raise ServiceException(message='Idempotency-Key header is required')

        composite_key = f'idempotency:{scope}:{normalized}'

        app_state = getattr(getattr(request, 'app', None), 'state', None)
        redis_client = getattr(app_state, 'redis', None) if app_state is not None else None
        if redis_client is not None:
            locked = await redis_client.set(composite_key, '1', ex=ttl_seconds, nx=True)
            if not locked:
                raise ServiceException(message='Duplicate idempotency key')
            return

        await cls._lock_in_memory(composite_key, ttl_seconds)

    @classmethod
    async def _lock_in_memory(cls, key: str, ttl_seconds: int) -> None:
        now = time.time()
        async with cls._memory_lock:
            # lazy cleanup of expired keys
            expired = [k for k, exp in cls._memory_key_expire_at.items() if exp <= now]
            for k in expired:
                cls._memory_key_expire_at.pop(k, None)

            if key in cls._memory_key_expire_at:
                raise ServiceException(message='Duplicate idempotency key')

            cls._memory_key_expire_at[key] = now + ttl_seconds
