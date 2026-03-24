from datetime import timedelta
from typing import Any, Set

from flask import Flask
from flask_jwt_extended import JWTManager

from app.extensions.redis import redis_client

jwt = JWTManager()

_revoked_jtis: Set[str] = set()


def init_jwt(app: Flask) -> None:
    """
    Configure JWTManager with expiry times and revocation callbacks.
    """

    from config import config as config_map

    cfg = config_map.get(app.config.get("ENV", "default"), config_map["default"])()

    app.config.setdefault(
        "JWT_ACCESS_TOKEN_EXPIRES",
        timedelta(minutes=cfg.JWT_ACCESS_TOKEN_EXPIRES_MIN),
    )
    app.config.setdefault(
        "JWT_REFRESH_TOKEN_EXPIRES",
        timedelta(days=cfg.JWT_REFRESH_TOKEN_EXPIRES_DAYS),
    )

    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(_jwt_header: dict, jwt_payload: dict) -> bool:
        jti = jwt_payload.get("jti")
        if not jti:
            return False
        client = redis_client.client
        if client:
            return client.exists(f"jwt:revoked:{jti}") == 1
        return jti in _revoked_jtis

    @jwt.revoked_token_loader
    def revoked_token_callback(_jwt_header: dict, _jwt_payload: dict):
        from flask import jsonify

        return jsonify({"error": "Token has been revoked"}), 401


def revoke_token(jti: str, expires_seconds: int | None = None) -> None:
    client = redis_client.client
    key = f"jwt:revoked:{jti}"
    if client:
        if expires_seconds:
            client.setex(key, expires_seconds, "1")
        else:
            client.set(key, "1")
    else:
        _revoked_jtis.add(jti)

