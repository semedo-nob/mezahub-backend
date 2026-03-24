from __future__ import annotations

from datetime import datetime

from app.extensions.database import db


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False, index=True)

    status = db.Column(db.String(30), default="pending", nullable=False, index=True)
    total_amount = db.Column(db.Numeric(10, 2), default=0, nullable=False)

    delivery_address = db.Column(db.String(255), default="")
    contact_name = db.Column(db.String(120))
    contact_phone = db.Column(db.String(30))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    special_instructions = db.Column(db.Text)

    payment_status = db.Column(db.String(30), default="pending")
    payment_method = db.Column(db.String(30), default="cash")

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    items = db.relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    history = db.relationship(
        "OrderStatusHistory", back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False, index=True)
    menu_item_id = db.Column(db.Integer, db.ForeignKey("menu_items.id"), nullable=False, index=True)

    quantity = db.Column(db.Integer, default=1, nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), default=0, nullable=False)
    subtotal = db.Column(db.Numeric(10, 2), default=0, nullable=False)

    order = db.relationship("Order", back_populates="items")


class OrderStatusHistory(db.Model):
    __tablename__ = "order_status_history"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False, index=True)
    status = db.Column(db.String(30), nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    order = db.relationship("Order", back_populates="history")

