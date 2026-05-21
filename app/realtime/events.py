from __future__ import annotations

from app.extensions.socketio import socketio


def emit_customer_event(customer_user_id: int, event: str, payload: dict) -> None:
    socketio.emit(event, payload, room=f"user:{customer_user_id}")


def emit_restaurant_event(restaurant_id: int, event: str, payload: dict) -> None:
    socketio.emit(event, payload, room=f"restaurant:{restaurant_id}")


def emit_rider_event(rider_id: int, event: str, payload: dict) -> None:
    socketio.emit(event, payload, room=f"rider:{rider_id}")


def emit_admin_event(event: str, payload: dict) -> None:
    socketio.emit(event, payload, room="admin_dashboard")
