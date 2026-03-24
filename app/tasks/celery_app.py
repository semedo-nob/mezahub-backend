from __future__ import annotations

import os

from celery import Celery


def make_celery() -> Celery:
    broker_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    backend_url = broker_url

    celery = Celery(
        "mezahub",
        broker=broker_url,
        backend=backend_url,
        include=[
            "app.tasks.email_tasks",
        ],
    )
    return celery


celery_app = make_celery()

