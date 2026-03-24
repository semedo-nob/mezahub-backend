from flask import Flask, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from flask_cors import CORS
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import config as config_map
from app.extensions.database import db
from app.extensions.jwt import jwt, init_jwt
from app.monitoring.sentry import init_sentry
from app.extensions.cache import cache
from app.extensions.socketio import socketio
from app.extensions.redis import redis_client
from app.middlewares.request_logger import RequestLogger
from app.models.user import User

migrate = Migrate()
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per day", "50 per hour"])


def create_app(config_name: str = "default") -> Flask:
    app = Flask(__name__)

    cfg_cls = config_map.get(config_name, config_map["default"])
    app.config.from_object(cfg_cls())

    # Configure logging for production usage.
    import logging
    from logging.handlers import RotatingFileHandler
    import os

    log_level = logging.INFO
    logging.basicConfig(level=log_level)
    log_path = os.path.join("logs", "app.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    file_handler = RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=3)
    file_handler.setLevel(log_level)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
        )
    )
    app.logger.addHandler(file_handler)

    # Optional Sentry monitoring
    init_sentry(app)

    db.init_app(app)
    jwt.init_app(app)
    init_jwt(app)
    migrate.init_app(app, db)
    
    from app.extensions.admin_panel import init_admin_panel
    init_admin_panel(app)
    
    socketio.init_app(app, cors_allowed_origins="*")
    # Initialize Redis-backed helpers (cache + generic redis_client).
    redis_client.init_app(app)
    cache.init_app(app)
    # Initialize limiter (Flask-Limiter reads RATELIMIT_* from app.config).
    limiter.init_app(app)

    @limiter.request_filter
    def exempt_public_reads():
        # Don't rate-limit public GETs (Discover page, menu) so apps don't hit "50 per hour".
        if request.method != "GET":
            return False
        path = (request.path or "").strip()
        if path.endswith("/restaurants") or "/restaurants/" in path and "/menu" in path:
            return True
        return False

    CORS(app, origins=app.config.get("CORS_ORIGINS", ["*"]))

    RequestLogger(app)

    from app.api.v1 import api_bp

    app.register_blueprint(api_bp, url_prefix="/api/v1")

    @app.before_request
    def block_suspended_users():
        path = (request.path or "").strip()
        if not path.startswith("/api/v1"):
            return None

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None

        verify_jwt_in_request(optional=True)
        user_id = get_jwt_identity()
        if user_id is None:
            return None

        user = User.query.get(int(user_id))
        if user is None or user.is_active:
            return None

        return {"error": "Account suspended", "message": "Your account is currently paused"}, 403

    # Ensure models are imported so Flask-Migrate sees them.
    from app import models as _models  # noqa: F401

    # Socket.IO event handlers
    from app.realtime import init_socket_handlers

    init_socket_handlers()

    @app.get("/health")
    def health():
        return {"status": "healthy", "version": "1.0.0"}

    @app.errorhandler(404)
    def not_found(_error):
        return {"error": "Resource not found"}, 404

    @app.errorhandler(500)
    def internal_error(_error):
        db.session.rollback()
        return {"error": "Internal server error"}, 500

    @app.cli.command("create-db")
    def create_db():
        db.create_all()
        print("Database created!")

    return app
