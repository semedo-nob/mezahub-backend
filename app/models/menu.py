from __future__ import annotations

from datetime import datetime

from app.extensions.database import db


class MenuCategory(db.Model):
    __tablename__ = "menu_categories"

    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default="")
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    restaurant = db.relationship("Restaurant", back_populates="menu_categories")
    items = db.relationship("MenuItem", back_populates="category", cascade="all, delete-orphan")


class MenuItem(db.Model):
    __tablename__ = "menu_items"

    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("menu_categories.id"), nullable=False, index=True)

    name = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, default="")
    price = db.Column(db.Numeric(10, 2), nullable=False)
    image_url = db.Column(db.Text)
    preparation_time = db.Column(db.Integer, default=10)  # minutes
    calories = db.Column(db.Integer)
    available = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    restaurant = db.relationship("Restaurant", back_populates="menu_items")
    category = db.relationship("MenuCategory", back_populates="items")
    options = db.relationship("MenuItemOption", back_populates="menu_item", cascade="all, delete-orphan")


class MenuItemOption(db.Model):
    __tablename__ = "menu_item_options"

    id = db.Column(db.Integer, primary_key=True)
    menu_item_id = db.Column(db.Integer, db.ForeignKey("menu_items.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    price_adjustment = db.Column(db.Numeric(10, 2), default=0)

    menu_item = db.relationship("MenuItem", back_populates="options")

