from __future__ import annotations

import os
import uuid
from urllib.parse import urljoin

from flask import current_app, has_app_context, has_request_context, request
from PIL import Image
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename


ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def build_media_url(value: str | None) -> str | None:
    if not value:
        return value
    if value.startswith("http://") or value.startswith("https://"):
        return value
    if value.startswith("/") and has_request_context():
        return urljoin(request.host_url, value)
    return value


def _uploads_root() -> str:
    if not has_app_context():
        raise RuntimeError("Application context is required for media operations")

    static_root = current_app.static_folder
    if not static_root:
        raise RuntimeError("Flask static folder is not configured")

    uploads_root = os.path.join(static_root, current_app.config.get("UPLOAD_FOLDER", "uploads"))
    os.makedirs(uploads_root, exist_ok=True)
    return uploads_root


def save_uploaded_image(file: FileStorage, category: str) -> str:
    if file is None or not file.filename:
        raise ValueError("No image file provided")

    filename = secure_filename(file.filename)
    _, ext = os.path.splitext(filename.lower())
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Unsupported image type. Use JPG, PNG, or WEBP.")

    try:
        image = Image.open(file.stream)
        image.verify()
    except Exception as exc:
        raise ValueError("Uploaded file is not a valid image") from exc
    finally:
        file.stream.seek(0)

    category = secure_filename(category) or "general"
    category_root = os.path.join(_uploads_root(), category)
    os.makedirs(category_root, exist_ok=True)

    generated_name = f"{uuid.uuid4().hex}{ext}"
    saved_path = os.path.join(category_root, generated_name)
    file.save(saved_path)

    upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads").strip("/ ")
    return f"/static/{upload_folder}/{category}/{generated_name}"
