from app.models import User


def test_user_model_has_email(app):
    u = User(name="Test", email="test@example.com", phone="", role="customer", is_active=True)
    assert u.email == "test@example.com"

