from __future__ import annotations

from datetime import datetime, time

from app.extensions.database import db
from app.utils.media import build_media_url


class Restaurant(db.Model):
    __tablename__ = "restaurants"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    name = db.Column(db.String(150), nullable=False, index=True)
    description = db.Column(db.Text, default="")
    address = db.Column(db.String(255), default="")
    cuisine_type = db.Column(db.String(80), default="")
    phone = db.Column(db.String(30))

    opening_time = db.Column(db.Time, default=time(9, 0))
    closing_time = db.Column(db.Time, default=time(22, 0))

    delivery_fee = db.Column(db.Numeric(10, 2), default=0)
    minimum_order = db.Column(db.Numeric(10, 2), default=0)

    approved = db.Column(db.Boolean, default=False, nullable=False)
    is_open = db.Column(db.Boolean, default=True, nullable=False)

    logo_image = db.Column(db.Text)
    cover_image = db.Column(db.Text)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    owner = db.relationship("User", back_populates="restaurants")
    menu_categories = db.relationship(
        "MenuCategory", back_populates="restaurant", cascade="all, delete-orphan"
    )
    menu_items = db.relationship("MenuItem", back_populates="restaurant", cascade="all, delete-orphan")

    @property
    def logo_image_url(self) -> str | None:
        return build_media_url(self.logo_image)

    @property
    def cover_image_url(self) -> str | None:
        return build_media_url(self.cover_image)

    def __repr__(self) -> str:
        return f"<Restaurant {self.name}>"
