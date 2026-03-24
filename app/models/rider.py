from __future__ import annotations

from datetime import datetime

from app.extensions.database import db


class Rider(db.Model):
    __tablename__ = "riders"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False, index=True)

    vehicle_type = db.Column(db.String(30), default="Motorbike")
    license_plate = db.Column(db.String(30))
    is_available = db.Column(db.Boolean, default=True, nullable=False)
    max_delivery_radius = db.Column(db.Float, default=10.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

