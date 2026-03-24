from __future__ import annotations

from app.tasks.celery_app import celery_app


@celery_app.task
def send_welcome_email(email: str, name: str) -> None:
    # Placeholder: integrate with real email service later.
    print(f"[EMAIL] Welcome {name}! ({email})")

