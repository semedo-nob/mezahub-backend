from __future__ import annotations

import os
from typing import Optional

import redis


class RedisCache:
    def __init__(self) -> None:
        self._client: Optional[redis.Redis] = None

    def init_app(self, app) -> None:
        url = app.config.get("REDIS_URL") or os.environ.get("REDIS_URL")
        if not url:
            self._client = None
            return
        try:
            self._client = redis.Redis.from_url(url, decode_responses=True)
            self._client.ping()
        except Exception:
            self._client = None

    @property
    def client(self) -> Optional[redis.Redis]:
        return self._client


cache = RedisCache()

