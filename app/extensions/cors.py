from flask_cors import CORS


def init_cors(app):
    return CORS(app, origins=app.config.get("CORS_ORIGINS", ["*"]))

