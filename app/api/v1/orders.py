from flask import request
from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from app.extensions.database import db
from app.extensions.socketio import socketio
from app.models import Order, OrderItem, MenuItem, Delivery, Rider, RiderLocation, OrderStatusHistory, User, Restaurant
from app.schemas.order_schema import OrderSchema
from app.utils.decorators import roles_required

orders_ns = Namespace("orders", description="Order operations")

order_item_model = orders_ns.model(
    "OrderItem",
    {
        "menu_item_id": fields.Integer,
        "quantity": fields.Integer,
        "unit_price": fields.Float,
        "subtotal": fields.Float,
    },
)

order_model = orders_ns.model(
    "Order",
    {
        "id": fields.Integer(readonly=True),
        "customer_id": fields.Integer,
        "restaurant_id": fields.Integer,
        "status": fields.String,
        "total_amount": fields.Float,
        "delivery_address": fields.String,
        "payment_status": fields.String,
        "payment_method": fields.String,
        "items": fields.List(fields.Nested(order_item_model)),
    },
)

order_schema = OrderSchema()
order_list_schema = OrderSchema(many=True)

track_model = orders_ns.model(
    "OrderTracking",
    {
        "order_id": fields.Integer,
        "order_status": fields.String,
        "delivery": fields.Raw,
        "rider_location": fields.Raw,
        "restaurant_latitude": fields.Float(description="Restaurant location for map (from restaurant profile)"),
        "restaurant_longitude": fields.Float(description="Restaurant location for map (from restaurant profile)"),
    },
)

assign_model = orders_ns.model(
    "AssignRider",
    {
        "rider_id": fields.Integer(required=True, description="Rider id to assign"),
    },
)

status_update_model = orders_ns.model(
    "UpdateOrderStatus",
    {
        "status": fields.String(required=True),
        "notes": fields.String,
    },
)


def _serialize_order(order: Order) -> dict:
    items = [
        {
            "menu_item_id": item.menu_item_id,
            "quantity": item.quantity,
            "unit_price": float(item.unit_price),
            "subtotal": float(item.subtotal),
        }
        for item in order.items
    ]
    rest = Restaurant.query.get(order.restaurant_id) if order.restaurant_id else None
    data = {
        "id": order.id,
        "customer_id": order.customer_id,
        "restaurant_id": order.restaurant_id,
        "status": order.status,
        "total_amount": float(order.total_amount),
        "delivery_address": order.delivery_address,
        "contact_name": order.contact_name,
        "contact_phone": order.contact_phone,
        "latitude": float(order.latitude) if order.latitude is not None else None,
        "longitude": float(order.longitude) if order.longitude is not None else None,
        "special_instructions": order.special_instructions,
        "payment_status": order.payment_status,
        "payment_method": order.payment_method,
        "items": items,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "restaurant_name": rest.name if rest else None,
        "restaurant_latitude": float(rest.latitude) if rest and rest.latitude is not None else None,
        "restaurant_longitude": float(rest.longitude) if rest and rest.longitude is not None else None,
    }
    return data


def _get_or_create_guest_user() -> User:
    """Single shared guest user for guest checkout (e.g. testing). No login."""
    guest = User.query.filter_by(email="guest@mezahub.local").first()
    if guest:
        return guest
    guest = User(
        name="Guest",
        email="guest@mezahub.local",
        phone="",
        role="customer",
        is_active=True,
    )
    guest.set_password("guest-no-login")
    db.session.add(guest)
    db.session.commit()
    return guest


def _authorize_order_access(order: Order, role: str | None, user_id: int) -> bool:
    if role == "admin":
        return True
    if role == "customer":
        return order.customer_id == user_id
    if role == "restaurant":
        from app.models import Restaurant

        restaurant_ids = [r.id for r in Restaurant.query.filter_by(owner_id=user_id).all()]
        return order.restaurant_id in restaurant_ids
    if role == "rider":
        rider = Rider.query.filter_by(user_id=user_id).first()
        if not rider:
            return False
        delivery = Delivery.query.filter_by(order_id=order.id).first()
        return delivery is not None and delivery.rider_id == rider.id
    return False


@orders_ns.route("")
class OrderList(Resource):
    @orders_ns.marshal_list_with(order_model)
    @orders_ns.doc(security="Bearer Auth")
    @jwt_required()
    def get(self):
        """
        List orders for current user:
        - customers: their own orders
        - restaurant: orders for their restaurant(s)
        - admin: all orders
        """
        claims = get_jwt()
        role = claims.get("role")
        user_id = int(get_jwt_identity())

        query = Order.query
        if role == "customer":
            query = query.filter_by(customer_id=user_id)
        elif role == "restaurant":
            # Simple: show all orders for any restaurant where this user is owner
            from app.models import Restaurant

            restaurant_ids = [r.id for r in Restaurant.query.filter_by(owner_id=user_id).all()]
            if restaurant_ids:
                query = query.filter(Order.restaurant_id.in_(restaurant_ids))
            else:
                query = query.filter(db.text("0=1"))
        # admin sees all

        page = int(request.args.get("page", 1))
        per_page = min(int(request.args.get("per_page", 20)), 100)
        pagination = query.order_by(Order.id.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        return [_serialize_order(o) for o in pagination.items]

    @orders_ns.expect(
        orders_ns.model(
            "CreateOrder",
            {
                "restaurant_id": fields.Integer(required=True),
                "delivery_address": fields.String(required=True),
                "payment_method": fields.String(required=True, default="cash"),
                "items": fields.List(
                    fields.Nested(
                        orders_ns.model(
                            "CreateOrderItem",
                            {
                                "menu_item_id": fields.Integer(required=True),
                                "quantity": fields.Integer(required=True, default=1),
                            },
                        )
                    ),
                    required=True,
                ),
                "guest_name": fields.String(description="Contact name (person placing order)"),
                "guest_email": fields.String(description="For guest checkout (no JWT)"),
                "guest_phone": fields.String(description="Contact phone (person placing order)"),
                "latitude": fields.Float(description="Delivery location latitude from app"),
                "longitude": fields.Float(description="Delivery location longitude from app"),
                "special_instructions": fields.String(description="Delivery notes / additional info"),
            },
        ),
        validate=True,
    )
    @orders_ns.marshal_with(order_model, code=201)
    @orders_ns.doc(security="Bearer Auth (optional for guest checkout)")
    @jwt_required(optional=True)
    def post(self):
        """Create a new order. Authenticated: current customer. Guest: no JWT, provide guest_* in body."""
        payload = request.get_json() or {}
        identity = get_jwt_identity()
        if identity is not None:
            # Authenticated: require customer role
            claims = get_jwt()
            if claims.get("role") != "customer":
                return {"error": "Forbidden", "message": "Insufficient role"}, 403
            user_id = int(identity)
        else:
            # Guest checkout: use shared guest user (for testing; later you can require payment/details)
            guest = _get_or_create_guest_user()
            user_id = guest.id

        restaurant_id = payload["restaurant_id"]
        items_payload = payload["items"]
        delivery_address = payload["delivery_address"]
        payment_method = payload.get("payment_method", "cash")

        if not items_payload:
            return {"error": "At least one item is required"}, 400

        contact_name = payload.get("guest_name") or payload.get("contact_name")
        contact_phone = payload.get("guest_phone") or payload.get("contact_phone")
        if identity is not None and (not contact_name or not contact_phone):
            from app.models import User
            current_user = User.query.get(user_id)
            if current_user:
                contact_name = contact_name or current_user.name
                contact_phone = contact_phone or current_user.phone or ""

        latitude = payload.get("latitude")
        longitude = payload.get("longitude")
        special_instructions = payload.get("special_instructions")

        order = Order(
            customer_id=user_id,
            restaurant_id=restaurant_id,
            status="pending",
            total_amount=0,
            delivery_address=delivery_address,
            contact_name=contact_name,
            contact_phone=contact_phone,
            latitude=float(latitude) if latitude is not None else None,
            longitude=float(longitude) if longitude is not None else None,
            special_instructions=special_instructions,
            payment_status="pending",
            payment_method=payment_method,
        )
        db.session.add(order)
        db.session.flush()

        total = 0
        for item_data in items_payload:
            menu_item = MenuItem.query.get(item_data["menu_item_id"])
            if not menu_item:
                db.session.rollback()
                return {"error": f"Menu item {item_data['menu_item_id']} not found"}, 400
            qty = int(item_data.get("quantity", 1))
            subtotal = float(menu_item.price) * qty
            total += subtotal
            db.session.add(
                OrderItem(
                    order_id=order.id,
                    menu_item_id=menu_item.id,
                    quantity=qty,
                    unit_price=menu_item.price,
                    subtotal=subtotal,
                )
            )

        order.total_amount = total
        db.session.commit()
        return _serialize_order(order), 201


@orders_ns.route("/<int:order_id>")
@orders_ns.response(404, "Order not found")
class OrderDetail(Resource):
    @orders_ns.marshal_with(order_model)
    @orders_ns.doc(security="Bearer Auth")
    @jwt_required()
    def get(self, order_id: int):
        """Get details for a single order, scoped to current user/role."""
        claims = get_jwt()
        role = claims.get("role")
        user_id = int(get_jwt_identity())

        order = Order.query.get_or_404(order_id)

        if not _authorize_order_access(order, role, user_id):
            return {"error": "Forbidden"}, 403

        return _serialize_order(order)


@orders_ns.route("/<int:order_id>/track")
@orders_ns.response(404, "Order not found")
class OrderTrack(Resource):
    @orders_ns.marshal_with(track_model)
    @orders_ns.doc(security="Bearer Auth")
    @jwt_required()
    def get(self, order_id: int):
        """Get live tracking details for an order (includes latest rider location if assigned)."""
        claims = get_jwt()
        role = claims.get("role")
        user_id = int(get_jwt_identity())

        order = Order.query.get_or_404(order_id)
        if not _authorize_order_access(order, role, user_id):
            return {"error": "Forbidden"}, 403

        delivery = Delivery.query.filter_by(order_id=order.id).first()
        latest_loc = None
        if delivery and delivery.rider_id:
            loc = (
                RiderLocation.query.filter_by(rider_id=delivery.rider_id)
                .order_by(RiderLocation.updated_at.desc())
                .first()
            )
            if loc:
                latest_loc = {
                    "rider_id": delivery.rider_id,
                    "latitude": loc.latitude,
                    "longitude": loc.longitude,
                    "updated_at": loc.updated_at.isoformat(),
                }

        # Use restaurant's saved location for tracking map (exact location from registration/profile)
        restaurant = Restaurant.query.get(order.restaurant_id)
        rest_lat = float(restaurant.latitude) if restaurant and restaurant.latitude is not None else None
        rest_lng = float(restaurant.longitude) if restaurant and restaurant.longitude is not None else None

        return {
            "order_id": order.id,
            "order_status": order.status,
            "delivery": (
                {
                    "id": delivery.id,
                    "rider_id": delivery.rider_id,
                    "status": delivery.status,
                }
                if delivery
                else None
            ),
            "rider_location": latest_loc,
            "restaurant_latitude": rest_lat,
            "restaurant_longitude": rest_lng,
        }


@orders_ns.route("/<int:order_id>/assign-rider")
@orders_ns.response(404, "Order not found")
class OrderAssignRider(Resource):
    @orders_ns.expect(assign_model, validate=True)
    @orders_ns.marshal_with(track_model)
    @orders_ns.doc(security="Bearer Auth")
    @jwt_required()
    @roles_required("restaurant", "admin")
    def post(self, order_id: int):
        """Assign a rider to an order (restaurant owner or admin)."""
        claims = get_jwt()
        role = claims.get("role")
        user_id = int(get_jwt_identity())

        order = Order.query.get_or_404(order_id)
        if role == "restaurant":
            # restaurant owner can only assign for their own restaurants
            from app.models import Restaurant

            restaurant_ids = [r.id for r in Restaurant.query.filter_by(owner_id=user_id).all()]
            if order.restaurant_id not in restaurant_ids:
                return {"error": "Forbidden"}, 403

        payload = request.get_json() or {}
        rider_id = int(payload["rider_id"])
        rider = Rider.query.get(rider_id)
        if not rider:
            return {"error": "Rider not found"}, 400

        delivery = Delivery.query.filter_by(order_id=order.id).first()
        if not delivery:
            delivery = Delivery(order_id=order.id, rider_id=rider.id, status="assigned")
            db.session.add(delivery)
        else:
            delivery.rider_id = rider.id
            delivery.status = "assigned"

        # update order status + history
        order.status = "assigned"
        db.session.add(OrderStatusHistory(order_id=order.id, status="assigned", notes="Rider assigned"))
        db.session.commit()

        # Realtime event to everyone in order room (customer, restaurant, rider)
        socketio.emit(
            "order_assigned",
            {"order_id": order.id, "rider_id": rider.id, "delivery_id": delivery.id},
            room=f"order:{order.id}",
        )

        # return tracking snapshot
        return OrderTrack().get(order.id)  # type: ignore[misc]


@orders_ns.route("/<int:order_id>/status")
@orders_ns.response(404, "Order not found")
class OrderStatus(Resource):
    @orders_ns.expect(status_update_model, validate=True)
    @orders_ns.marshal_with(order_model)
    @orders_ns.doc(security="Bearer Auth")
    @jwt_required()
    def patch(self, order_id: int):
        """Update order status. Restaurant/admin: any status. Rider: out_for_delivery, delivered only."""
        claims = get_jwt()
        role = claims.get("role")
        user_id = int(get_jwt_identity())
        order = Order.query.get_or_404(order_id)

        if role == "restaurant":
            restaurant_ids = [r.id for r in Restaurant.query.filter_by(owner_id=user_id).all()]
            if order.restaurant_id not in restaurant_ids:
                return {"error": "Forbidden"}, 403
        elif role == "rider":
            rider = Rider.query.filter_by(user_id=user_id).first()
            delivery = Delivery.query.filter_by(order_id=order.id).first()
            if not rider or not delivery or delivery.rider_id != rider.id:
                return {"error": "Forbidden"}, 403
            payload = request.get_json() or {}
            status = (payload.get("status") or "").strip().lower()
            if status not in ("out_for_delivery", "delivered"):
                return {"error": "Rider can only set status to out_for_delivery or delivered"}, 400
        elif role != "admin":
            return {"error": "Forbidden"}, 403

        payload = request.get_json() or {}
        status = payload["status"]
        notes = payload.get("notes")

        order.status = status
        db.session.add(OrderStatusHistory(order_id=order.id, status=status, notes=notes))
        if role == "rider":
            delivery = Delivery.query.filter_by(order_id=order.id).first()
            if delivery:
                delivery.status = "delivered" if status == "delivered" else ("picked_up" if status == "out_for_delivery" else delivery.status)
        db.session.commit()

        socketio.emit(
            "order_status",
            {"order_id": order.id, "status": status, "notes": notes},
            room=f"order:{order.id}",
        )
        return _serialize_order(order)

