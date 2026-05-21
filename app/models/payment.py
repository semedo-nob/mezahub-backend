from __future__ import annotations

from datetime import datetime

from app.extensions.database import db


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), index=True)
    rider_id = db.Column(db.Integer, db.ForeignKey("riders.id"), index=True)
    amount = db.Column(db.Numeric(10, 2), default=0, nullable=False)
    delivery_fee = db.Column(db.Numeric(10, 2), default=0, nullable=False)
    total_amount = db.Column(db.Numeric(10, 2), default=0, nullable=False)
    provider = db.Column(db.String(50), default="cash")
    status = db.Column(db.String(30), default="pending")
    phone_number = db.Column(db.String(20))
    checkout_request_id = db.Column(db.String(120), index=True, unique=True)
    merchant_request_id = db.Column(db.String(120))
    conversation_id = db.Column(db.String(120))
    originator_conversation_id = db.Column(db.String(120))
    mpesa_receipt_number = db.Column(db.String(120))
    result_code = db.Column(db.String(20))
    result_desc = db.Column(db.Text)
    transaction_date = db.Column(db.DateTime)
    raw_callback = db.Column(db.JSON)
    restaurant_paid = db.Column(db.Boolean, default=False, nullable=False)
    rider_paid = db.Column(db.Boolean, default=False, nullable=False)
    restaurant_payout_date = db.Column(db.DateTime)
    rider_payout_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class Payout(db.Model):
    __tablename__ = "payouts"

    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey("payments.id"), nullable=False, index=True)
    recipient_type = db.Column(db.String(20), nullable=False)
    recipient_id = db.Column(db.Integer, nullable=False, index=True)
    recipient_phone = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Numeric(10, 2), default=0, nullable=False)
    conversation_id = db.Column(db.String(120))
    originator_conversation_id = db.Column(db.String(120))
    status = db.Column(db.String(30), default="pending", nullable=False)
    result_code = db.Column(db.String(20))
    result_desc = db.Column(db.Text)
    payout_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
