import re


def validate_email(email: str | None) -> bool:
    if not email:
        return False
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) is not None


def validate_password(password: str | None) -> bool:
    if not password:
        return False
    return len(password) >= 8

