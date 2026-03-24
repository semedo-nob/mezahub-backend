from __future__ import annotations


class EmailService:
    """Placeholder email service."""

    @staticmethod
    def send(to_email: str, subject: str, body: str) -> None:
        print(f"[EmailService] To={to_email} Subject={subject}")

