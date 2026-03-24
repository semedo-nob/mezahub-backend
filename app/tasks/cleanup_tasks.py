from __future__ import annotations

from app.tasks.celery_app import celery_app


@celery_app.task
def cleanup_old_data() -> None:
    # Placeholder cleanup task.
    print("[CLEANUP] Running periodic cleanup task")

