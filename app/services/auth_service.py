from __future__ import annotations

from flask_jwt_extended import create_access_token

from app.extensions.database import db
from app.models.user import User


class AuthService:
    @staticmethod
    def _create_token(user: User) -> str:
        # Include role in JWT for RBAC checks.
        return create_access_token(identity=str(user.id), additional_claims={"role": user.role})

    @staticmethod
    def register_user(data: dict) -> dict:
        try:
            email = (data.get("email") or "").strip().lower()
            if not email:
                return {"success": False, "error": "Email required"}
            if User.find_by_email(email):
                return {"success": False, "error": "Email already exists"}

            user = User(
                name=data.get("name") or "",
                email=email,
                phone=data.get("phone") or "",
                role=data.get("role") or "customer",
                profile_image=data.get("profile_image"),
                is_active=True,
            )
            user.set_password(data.get("password") or "")

            db.session.add(user)
            db.session.commit()

            token = AuthService._create_token(user)
            return {"success": True, "user": user, "token": token}
        except Exception as e:
            db.session.rollback()
            return {"success": False, "error": str(e)}

    @staticmethod
    def login_user(email: str, password: str) -> dict:
        user = User.find_by_email((email or "").strip().lower())
        if not user or not user.check_password(password or ""):
            return {"success": False, "error": "Invalid credentials"}
        if not user.is_active:
            return {"success": False, "error": "Account suspended"}
        token = AuthService._create_token(user)
        return {"success": True, "user": user, "token": token}
