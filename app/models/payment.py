from __future__ import annotations

from datetime import datetime

from app.extensions.database import db


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False, index=True)
    amount = db.Column(db.Numeric(10, 2), default=0, nullable=False)
    provider = db.Column(db.String(50), default="cash")
    status = db.Column(db.String(30), default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

