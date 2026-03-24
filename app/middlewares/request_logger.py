import time
from flask import request


class RequestLogger:
    def __init__(self, app):
        self.app = app
        self.register()

    def register(self) -> None:
        @self.app.before_request
        def _start_timer():
            request._start_time = time.time()  # type: ignore[attr-defined]

        @self.app.after_request
        def _log_response(response):
            _ = getattr(request, "_start_time", None)
            return response

