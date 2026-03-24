from __future__ import annotations

from datetime import datetime

import bcrypt
from flask_jwt_extended import create_access_token
from sqlalchemy import func

from app.extensions.database import db
from app.utils.media import build_media_url


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(30))
    password_hash = db.Column(db.LargeBinary, nullable=False)
    role = db.Column(db.String(20), nullable=False, index=True)
    firebase_token = db.Column(db.Text)
    profile_image = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    restaurants = db.relationship("Restaurant", back_populates="owner", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<User {self.email}>"

    def set_password(self, raw_password: str) -> None:
        self.password_hash = bcrypt.hashpw(raw_password.encode("utf-8"), bcrypt.gensalt())

    def check_password(self, raw_password: str) -> bool:
        try:
            return bcrypt.checkpw(raw_password.encode("utf-8"), self.password_hash)
        except Exception:
            return False

    def generate_token(self) -> str:
        return create_access_token(identity=str(self.id))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "role": self.role,
            "profile_image": build_media_url(self.profile_image),
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @staticmethod
    def find_by_email(email: str) -> "User | None":
        return User.query.filter_by(email=email).first()

    @staticmethod
    def find_by_login(login: str) -> "User | None":
        normalized = (login or "").strip().lower()
        if not normalized:
            return None

        user = User.query.filter(func.lower(User.email) == normalized).first()
        if user:
            return user

        return User.query.filter(func.lower(User.name) == normalized).first()
