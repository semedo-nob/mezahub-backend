from flask import request
from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions.database import db
from app.extensions.socketio import socketio
from app.models import Rider, User, Delivery, Order, OrderStatusHistory, Restaurant, RiderLocation
from app.utils.decorators import roles_required

riders_ns = Namespace("riders", description="Rider operations")

rider_model = riders_ns.model(
    "Rider",
    {
        "id": fields.Integer(readonly=True),
        "user_id": fields.Integer,
        "name": fields.String,
        "phone": fields.String,
        "vehicle_type": fields.String,
        "license_plate": fields.String,
        "is_available": fields.Boolean,
    },
)

rider_profile_model = riders_ns.model(
    "RiderProfileCreate",
    {
        "vehicle_type": fields.String(description="e.g. Motorbike, Bicycle"),
        "license_plate": fields.String(description="Optional"),
    },
)


@riders_ns.route("/me")
class RiderMe(Resource):
    """Create or update rider profile for the current user (rider role)."""

    @riders_ns.expect(rider_profile_model)
    @riders_ns.response(200, "Updated")
    @riders_ns.response(201, "Created")
    @riders_ns.doc(security="Bearer Auth")
    @jwt_required()
    @roles_required("rider")
    def post(self):
        user_id = int(get_jwt_identity())
        rider = Rider.query.filter_by(user_id=user_id).first()
        payload = (request.get_json(silent=True) or {})
        vehicle_type = (payload.get("vehicle_type") or "").strip() or "Motorbike"
        license_plate = (payload.get("license_plate") or "").strip() or None

        if rider:
            rider.vehicle_type = vehicle_type
            rider.license_plate = license_plate
            db.session.commit()
            return {"id": rider.id, "user_id": rider.user_id, "message": "Rider profile updated"}, 200

        rider = Rider(
            user_id=user_id,
            vehicle_type=vehicle_type,
            license_plate=license_plate,
            is_available=True,
        )
        db.session.add(rider)
        db.session.commit()
        return {"id": rider.id, "user_id": rider.user_id, "message": "Rider profile created"}, 201


@riders_ns.route("")
class RiderList(Resource):
    @riders_ns.marshal_list_with(rider_model)
    @riders_ns.doc(security="Bearer Auth")
    @jwt_required()
    @roles_required("admin", "restaurant")
    def get(self):
        """List all riders (admin and restaurant can list for assignment)."""
        riders = Rider.query.all()
        result = []
        for r in riders:
            user: User | None = User.query.get(r.user_id)
            result.append(
                {
                    "id": r.id,
                    "user_id": r.user_id,
                    "name": user.name if user else None,
                    "phone": user.phone if user else None,
                    "vehicle_type": r.vehicle_type,
                    "license_plate": r.license_plate,
                    "is_available": r.is_available,
                }
            )
        return result


assignment_model = riders_ns.model(
    "RiderAssignment",
    {
        "delivery_id": fields.Integer,
        "order_id": fields.Integer,
        "delivery_status": fields.String,
        "order_status": fields.String,
        "delivery_address": fields.String,
        "latitude": fields.Float,
        "longitude": fields.Float,
        "restaurant_name": fields.String,
        "contact_name": fields.String,
        "contact_phone": fields.String,
        "total_amount": fields.Float,
        "restaurant_latitude": fields.Float,
        "restaurant_longitude": fields.Float,
        "created_at": fields.String(description="Order created_at ISO format"),
    },
)


available_order_model = riders_ns.model(
    "AvailableOrder",
    {
        "order_id": fields.Integer,
        "restaurant_name": fields.String,
        "delivery_address": fields.String,
        "latitude": fields.Float,
        "longitude": fields.Float,
        "contact_name": fields.String,
        "contact_phone": fields.String,
        "total_amount": fields.Float,
        "restaurant_latitude": fields.Float,
        "restaurant_longitude": fields.Float,
        "created_at": fields.String,
    },
)


@riders_ns.route("/available-orders")
class RiderAvailableOrders(Resource):
    @riders_ns.marshal_list_with(available_order_model)
    @riders_ns.doc(security="Bearer Auth")
    @jwt_required()
    @roles_required("rider")
    def get(self):
        """List orders posted by restaurants (status=ready) that have no rider assigned yet."""
        orders = Order.query.filter_by(status="ready").order_by(Order.id.desc()).all()
        result = []
        for order in orders:
            delivery = Delivery.query.filter_by(order_id=order.id).first()
            if delivery is not None and delivery.rider_id is not None:
                continue
            rest = Restaurant.query.get(order.restaurant_id) if order.restaurant_id else None
            result.append(
                {
                    "order_id": order.id,
                    "restaurant_name": rest.name if rest else "",
                    "delivery_address": order.delivery_address or "",
                    "latitude": float(order.latitude) if order.latitude is not None else None,
                    "longitude": float(order.longitude) if order.longitude is not None else None,
                    "contact_name": order.contact_name or "",
                    "contact_phone": order.contact_phone or "",
                    "total_amount": float(order.total_amount) if order.total_amount is not None else 0.0,
                    "restaurant_latitude": float(rest.latitude) if rest and rest.latitude is not None else None,
                    "restaurant_longitude": float(rest.longitude) if rest and rest.longitude is not None else None,
                    "created_at": order.created_at.isoformat() if order.created_at else None,
                }
            )
        return result


@riders_ns.route("/accept-order/<int:order_id>")
@riders_ns.response(404, "Order not found")
@riders_ns.response(400, "Order not available for acceptance")
class RiderAcceptOrder(Resource):
    @riders_ns.doc(security="Bearer Auth")
    @jwt_required()
    @roles_required("rider")
    def post(self, order_id: int):
        """Accept an available order (assign current rider to it). Order must be status=ready and unassigned."""
        user_id = int(get_jwt_identity())
        rider = Rider.query.filter_by(user_id=user_id).first()
        if not rider:
            return {"error": "Rider profile not found"}, 403

        order = Order.query.get(order_id)
        if not order:
            return {"error": "Order not found"}, 404
        if order.status != "ready":
            return {"error": "Order is not available for delivery (not ready)"}, 400

        delivery = Delivery.query.filter_by(order_id=order_id).first()
        if delivery is not None and delivery.rider_id is not None:
            return {"error": "Order already assigned to a rider"}, 400

        if delivery is None:
            delivery = Delivery(order_id=order_id, rider_id=rider.id, status="assigned")
            db.session.add(delivery)
        else:
            delivery.rider_id = rider.id
            delivery.status = "assigned"

        order.status = "assigned"
        db.session.add(OrderStatusHistory(order_id=order_id, status="assigned", notes="Rider accepted order"))

        # Store rider's current location when accepting (optional from app)
        payload = request.get_json(silent=True) or {}
        try:
            rider_lat = payload.get("rider_latitude")
            rider_lng = payload.get("rider_longitude")
            if rider_lat is not None and rider_lng is not None:
                lat_f = float(rider_lat)
                lng_f = float(rider_lng)
                loc = RiderLocation(rider_id=rider.id, latitude=lat_f, longitude=lng_f)
                db.session.add(loc)
        except (TypeError, ValueError):
            pass

        db.session.commit()

        socketio.emit(
            "order_assigned",
            {"order_id": order_id, "rider_id": rider.id, "delivery_id": delivery.id},
            room=f"order:{order_id}",
        )

        return {"order_id": order_id, "delivery_id": delivery.id, "message": "Order accepted"}, 201


@riders_ns.route("/me/assignments")
class RiderAssignments(Resource):
    @riders_ns.marshal_list_with(assignment_model)
    @riders_ns.doc(security="Bearer Auth")
    @jwt_required()
    @roles_required("rider")
    def get(self):
        """Get current rider assignments (rider-only)."""
        user_id = int(get_jwt_identity())
        rider = Rider.query.filter_by(user_id=user_id).first()
        if not rider:
            return []

        deliveries = Delivery.query.filter_by(rider_id=rider.id).order_by(Delivery.id.desc()).all()
        result = []
        for d in deliveries:
            order = Order.query.get(d.order_id)
            if not order:
                continue
            rest = Restaurant.query.get(order.restaurant_id) if order.restaurant_id else None
            result.append(
                {
                    "delivery_id": d.id,
                    "order_id": order.id,
                    "delivery_status": d.status,
                    "order_status": order.status,
                    "delivery_address": order.delivery_address or "",
                    "latitude": float(order.latitude) if order.latitude is not None else None,
                    "longitude": float(order.longitude) if order.longitude is not None else None,
                    "restaurant_name": rest.name if rest else "",
                    "contact_name": order.contact_name or "",
                    "contact_phone": order.contact_phone or "",
                    "total_amount": float(order.total_amount) if order.total_amount is not None else 0.0,
                    "restaurant_latitude": float(rest.latitude) if rest and rest.latitude is not None else None,
                    "restaurant_longitude": float(rest.longitude) if rest and rest.longitude is not None else None,
                    "created_at": order.created_at.isoformat() if order.created_at else None,
                }
            )
        return result

