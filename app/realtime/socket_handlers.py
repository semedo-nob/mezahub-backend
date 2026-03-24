from __future__ import annotations

from datetime import datetime
from typing import Any

from flask import request
from flask_jwt_extended import decode_token

from app.extensions.socketio import socketio
from app.extensions.database import db
from app.models import Delivery, Rider, RiderLocation, Order, User


def _get_bearer_token_from_headers() -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return None


def _get_token_from_auth_payload(auth_payload: Any) -> str | None:
    if isinstance(auth_payload, dict):
        token = auth_payload.get("token") or auth_payload.get("access_token")
        if isinstance(token, str) and token.strip():
            return token.strip()
    return None


def _decode_jwt(token: str) -> dict:
    # Uses Flask-JWT-Extended configuration (SECRET/JWT_SECRET) already set.
    return decode_token(token)


def init_socket_handlers() -> None:
    @socketio.on("connect")
    def on_connect(auth):  # type: ignore[no-untyped-def]
        token = _get_token_from_auth_payload(auth) or _get_bearer_token_from_headers()
        if not token:
            return False
        try:
            decoded = _decode_jwt(token)
            user = User.query.get(int(decoded["sub"]))
            if not user or not user.is_active:
                return False
            # Stash identity/role into Socket.IO session.
            socketio.server.session(request.sid)["user_id"] = int(decoded["sub"])
            socketio.server.session(request.sid)["role"] = decoded.get("role")
        except Exception:
            return False
        return True

    @socketio.on("join_order")
    def join_order(data):  # type: ignore[no-untyped-def]
        """
        Client subscribes to an order room: { "order_id": 123 }
        """
        sess = socketio.server.session(request.sid)
        user_id = sess.get("user_id")
        role = sess.get("role")
        order_id = int((data or {}).get("order_id", 0))
        if not user_id or not order_id:
            return {"ok": False, "error": "Missing user or order_id"}

        user = User.query.get(int(user_id))
        if not user or not user.is_active:
            return {"ok": False, "error": "Account suspended"}

        order = Order.query.get(order_id)
        if not order:
            return {"ok": False, "error": "Order not found"}

        # Authorization: customer owning order, restaurant owner, assigned rider, or admin.
        allowed = False
        if role == "admin":
            allowed = True
        elif role == "customer" and order.customer_id == user_id:
            allowed = True
        elif role == "restaurant":
            from app.models import Restaurant

            restaurant_ids = [r.id for r in Restaurant.query.filter_by(owner_id=user_id).all()]
            allowed = order.restaurant_id in restaurant_ids
        elif role == "rider":
            rider = Rider.query.filter_by(user_id=user_id).first()
            if rider:
                delivery = Delivery.query.filter_by(order_id=order.id).first()
                allowed = delivery is not None and delivery.rider_id == rider.id

        if not allowed:
            return {"ok": False, "error": "Forbidden"}

        room = f"order:{order_id}"
        socketio.enter_room(request.sid, room)
        return {"ok": True, "room": room}

    @socketio.on("rider_location_update")
    def rider_location_update(data):  # type: ignore[no-untyped-def]
        """
        Rider sends location updates:
          { "order_id": 123, "latitude": -1.2, "longitude": 36.8 }

        Server validates rider assignment and broadcasts to room "order:<id>".
        """
        sess = socketio.server.session(request.sid)
        user_id = sess.get("user_id")
        role = sess.get("role")
        if role != "rider":
            return {"ok": False, "error": "Only riders can send location updates"}

        user = User.query.get(int(user_id)) if user_id else None
        if not user or not user.is_active:
            return {"ok": False, "error": "Account suspended"}

        payload = data or {}
        order_id = int(payload.get("order_id", 0))
        lat = payload.get("latitude")
        lng = payload.get("longitude")
        if not order_id or lat is None or lng is None:
            return {"ok": False, "error": "Missing order_id/latitude/longitude"}

        rider = Rider.query.filter_by(user_id=int(user_id)).first()
        if not rider:
            return {"ok": False, "error": "Rider profile not found"}

        delivery = Delivery.query.filter_by(order_id=order_id).first()
        if not delivery or delivery.rider_id != rider.id:
            return {"ok": False, "error": "Rider not assigned to this order"}

        loc = RiderLocation(
            rider_id=rider.id,
            latitude=float(lat),
            longitude=float(lng),
            updated_at=datetime.utcnow(),
        )
        db.session.add(loc)
        db.session.commit()

        event = {
            "order_id": order_id,
            "rider_id": rider.id,
            "latitude": float(lat),
            "longitude": float(lng),
            "updated_at": loc.updated_at.isoformat(),
        }
        socketio.emit("order_location", event, room=f"order:{order_id}")
        return {"ok": True}
