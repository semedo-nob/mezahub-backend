from functools import wraps
from typing import Iterable

from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request

from app.models.user import User


def rate_limit(limits: Iterable[str]):
    """
    Marker decorator for attaching human-readable rate-limit hints.
    Real limiting is handled by Flask-Limiter configured globally.
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            return fn(*args, **kwargs)

        wrapper.__rate_limits__ = list(limits)  # type: ignore[attr-defined]
        return wrapper

    return decorator


def roles_required(*roles: str):
    """
    Require at least one of the given roles on the current JWT.
    Expects JWTs to include a "role" claim.
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            user = User.query.get(int(user_id)) if user_id is not None else None
            if not user or not user.is_active:
                from flask import jsonify

                return jsonify({"error": "Account suspended", "message": "Your account is currently paused"}), 403
            claims = get_jwt()
            role = claims.get("role")
            if role not in roles:
                from flask import jsonify

                return jsonify({"error": "Forbidden", "message": "Insufficient role"}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator
