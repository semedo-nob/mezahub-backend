from app.services.auth_service import AuthService


def test_auth_service_register_missing_email(app):
    result = AuthService.register_user({"name": "X", "password": "password123", "role": "customer"})
    assert result["success"] is False

