import os

import pytest

from app import create_app
from app.extensions.database import db


@pytest.fixture
def app():
    os.environ["FLASK_ENV"] = "testing"
    app = create_app("testing")
    with app.app_context():
        yield app


@pytest.fixture
def client(app):
    return app.test_client()

