#!/usr/bin/env python
import os

from app import create_app
from app.extensions.socketio import socketio


def main() -> None:
    env = os.getenv("FLASK_ENV", "development")
    app = create_app(env)
    socketio.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=env == "development",
        allow_unsafe_werkzeug=True,
    )


if __name__ == "__main__":
    main()
