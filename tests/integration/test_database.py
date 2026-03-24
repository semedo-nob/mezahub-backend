from sqlalchemy import text

from app.extensions.database import db


def test_database_connection(app):
    # Simple smoke test that session can be queried.
    db.session.execute(text("SELECT 1"))

