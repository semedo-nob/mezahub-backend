import logging
from typing import Optional

from redis import Redis


class RedisClient:
    def __init__(self) -> None:
        self._client: Optional[Redis] = None

    def init_app(self, app) -> None:
        redis_url = app.config.get("REDIS_URL", "redis://localhost:6379/0")
        try:
            client = Redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
                retry_on_timeout=True,
            )
            client.ping()
            self._client = client
            app.logger.info(f"Redis connected: {redis_url}")
        except Exception as exc:  # pragma: no cover - best-effort logging
            app.logger.warning(f"Redis connection failed: {exc}")
            self._client = None

    @property
    def client(self) -> Optional[Redis]:
        return self._client

    def get(self, key: str):
        if not self._client:
            return None
        try:
            return self._client.get(key)
        except Exception as exc:
            logging.error(f"Redis get error: {exc}")
            return None

    def set(self, key: str, value, expire: Optional[int] = None) -> bool:
        if not self._client:
            return False
        try:
            if expire:
                self._client.setex(key, expire, value)
            else:
                self._client.set(key, value)
            return True
        except Exception as exc:
            logging.error(f"Redis set error: {exc}")
            return False


redis_client = RedisClient()

