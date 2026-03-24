from flask import request, current_app
from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import (
    jwt_required,
    get_jwt_identity,
    create_refresh_token,
    get_jwt,
)
from sqlalchemy.exc import OperationalError

from app.extensions.database import db
from app.models.user import User
from app.services.auth_service import AuthService
from app.utils.media import save_uploaded_image
from app.utils.validators import validate_email, validate_password
from app.extensions.jwt import revoke_token

auth_ns = Namespace("auth", description="Authentication operations")

register_model = auth_ns.model(
    "Register",
    {
        "name": fields.String(required=True, description="User full name"),
        "email": fields.String(required=True, description="User email"),
        "phone": fields.String(description="Phone number"),
        "password": fields.String(required=True, description="Password"),
        "role": fields.String(
            required=True, description="User role", enum=["customer", "restaurant", "rider", "admin"]
        ),
    },
)

login_model = auth_ns.model(
    "Login",
    {"email": fields.String(required=True), "password": fields.String(required=True)},
)

token_response = auth_ns.model(
    "TokenResponse",
    {
        "access_token": fields.String,
        "refresh_token": fields.String,
        "user": fields.Raw,
    },
)


@auth_ns.route("/register")
class Register(Resource):
    @auth_ns.expect(register_model)
    @auth_ns.response(201, "Success", token_response)
    @auth_ns.response(400, "Validation Error")
    def post(self):
        data = request.get_json(silent=True) or {}

        if not validate_email(data.get("email")):
            return {"error": "Invalid email format"}, 400
        if not validate_password(data.get("password")):
            return {"error": "Password must be at least 8 characters"}, 400

        result = AuthService.register_user(data)
        if not result["success"]:
            return {"error": result["error"]}, 400

        user = result["user"]
        access = result["token"]
        refresh = create_refresh_token(identity=str(user.id), additional_claims={"role": user.role})
        return {"access_token": access, "refresh_token": refresh, "user": user.to_dict()}, 201


@auth_ns.route("/login")
class Login(Resource):
    @auth_ns.expect(login_model)
    @auth_ns.response(200, "Success", token_response)
    @auth_ns.response(401, "Invalid credentials")
    def post(self):
        data = request.get_json(silent=True) or {}
        email = data.get("email")
        password = data.get("password")
        if not email or not password:
            return {"error": "Email and password required"}, 400

        try:
            result = AuthService.login_user(email, password)
        except OperationalError as e:
            current_app.logger.exception("Database error during login: %s", e)
            return {
                "error": "Database error. Run: flask db upgrade (and ensure PostgreSQL/SQLite is running).",
                "detail": str(e) if current_app.debug else None,
            }, 503

        if not result["success"]:
            if result.get("error") == "Account suspended":
                return {"error": "Account suspended", "message": "Your account is currently paused"}, 403
            return {"error": "Invalid credentials"}, 401
        try:
            user = result["user"]
            access = result["token"]
            refresh = create_refresh_token(identity=str(user.id), additional_claims={"role": user.role})
            return {"access_token": access, "refresh_token": refresh, "user": user.to_dict()}
        except OperationalError as e:
            current_app.logger.exception("Database error serializing user: %s", e)
            return {
                "error": "Database schema may be out of date. Run: flask db upgrade",
                "detail": str(e) if current_app.debug else None,
            }, 503


@auth_ns.route("/profile")
class Profile(Resource):
    @auth_ns.doc(security="Bearer Auth")
    @jwt_required()
    def get(self):
        try:
            user_id = get_jwt_identity()
            user = User.query.get(int(user_id))
            if not user:
                return {"error": "User not found"}, 404
            return user.to_dict()
        except OperationalError as e:
            current_app.logger.exception("Database error in profile: %s", e)
            return {
                "error": "Database error. Run: flask db upgrade",
                "detail": str(e) if current_app.debug else None,
            }, 503

    @auth_ns.doc(security="Bearer Auth")
    @jwt_required()
    def put(self):
        try:
            user_id = get_jwt_identity()
            data = request.get_json(silent=True) or {}

            user = User.query.get(int(user_id))
            if not user:
                return {"error": "User not found"}, 404

            if "name" in data:
                user.name = data["name"]
            if "phone" in data:
                user.phone = data["phone"]
            if "profile_image" in data:
                user.profile_image = data["profile_image"]

            db.session.commit()
            return user.to_dict()
        except OperationalError as e:
            db.session.rollback()
            current_app.logger.exception("Database error updating profile: %s", e)
            return {
                "error": "Database error. Run: flask db upgrade",
                "detail": str(e) if current_app.debug else None,
            }, 503


@auth_ns.route("/profile/image")
class ProfileImageUpload(Resource):
    @auth_ns.doc(security="Bearer Auth")
    @jwt_required()
    def post(self):
        user_id = get_jwt_identity()
        user = User.query.get_or_404(int(user_id))

        image = request.files.get("image")
        if image is None:
            return {"error": "Image file is required"}, 400

        try:
            user.profile_image = save_uploaded_image(image, "profiles")
            db.session.commit()
            return {"profile_image": user.to_dict().get("profile_image")}
        except ValueError as exc:
            db.session.rollback()
            return {"error": str(exc)}, 400


refresh_response = auth_ns.model(
    "RefreshResponse",
    {
        "access_token": fields.String,
    },
)


@auth_ns.route("/refresh")
class Refresh(Resource):
    @auth_ns.doc(security="Bearer Auth")
    @jwt_required(refresh=True)
    @auth_ns.marshal_with(refresh_response)
    def post(self):
        """Refresh access token using a refresh token."""
        claims = get_jwt()
        user_id = claims["sub"]
        role = claims.get("role")
        access = AuthService._create_token(User.query.get(int(user_id)))  # type: ignore[arg-type]
        return {"access_token": access}


@auth_ns.route("/logout")
class Logout(Resource):
    @auth_ns.doc(security="Bearer Auth")
    @jwt_required()
    def post(self):
        """Logout current user by revoking current access token."""
        jwt_data = get_jwt()
        jti = jwt_data["jti"]
        # Expire revocation slightly beyond remaining token lifetime.
        revoke_token(jti, expires_seconds=jwt_data.get("exp", 0) - jwt_data.get("iat", 0))
        return {"msg": "Logged out"}
