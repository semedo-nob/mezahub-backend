from __future__ import annotations

from datetime import datetime

from app.extensions.database import db


class Favorite(db.Model):
    __tablename__ = "favorites"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), index=True)
    menu_item_id = db.Column(db.Integer, db.ForeignKey("menu_items.id"), index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

