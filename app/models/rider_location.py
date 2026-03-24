from __future__ import annotations

from datetime import datetime

from app.extensions.database import db


class RiderLocation(db.Model):
    __tablename__ = "rider_locations"

    id = db.Column(db.Integer, primary_key=True)
    rider_id = db.Column(db.Integer, db.ForeignKey("riders.id"), nullable=False, index=True)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

