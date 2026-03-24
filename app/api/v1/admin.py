from flask import request, current_app
from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import jwt_required

from app.extensions.database import db
from app.models import User, Restaurant, Order
from app.utils.decorators import roles_required
from app.api.v1.orders import _serialize_order
from app.api.v1.restaurants import restaurant_model

admin_ns = Namespace("admin", description="Admin operations")

# Models for Swagger documentation
admin_restaurant_model = admin_ns.clone("AdminRestaurant", restaurant_model, {
    "approved": fields.Boolean(description="Review approval status")
})


@admin_ns.route("/stats")
class AdminStats(Resource):
    @admin_ns.doc(security="Bearer Auth")
    @jwt_required()
    @roles_required("admin")
    def get(self):
        """Basic admin stats (admin-only)."""
        return {
            "users": User.query.count(),
            "restaurants": Restaurant.query.count(),
            "orders": Order.query.count(),
        }


@admin_ns.route("/restaurants")
class AdminRestaurantList(Resource):
    @admin_ns.marshal_list_with(admin_restaurant_model)
    @admin_ns.doc(
        security="Bearer Auth",
        params={'status': 'Filter by status: "approved" or "pending" (all by default)'}
    )
    @jwt_required()
    @roles_required("admin")
    def get(self):
        """Get all restaurants, filterable by approval status."""
        status_filter = request.args.get('status')
        query = Restaurant.query
        
        if status_filter == 'approved':
            query = query.filter_by(approved=True)
        elif status_filter == 'pending':
            query = query.filter_by(approved=False)
            
        return query.order_by(Restaurant.id.desc()).all()


@admin_ns.route("/restaurants/<int:restaurant_id>/approve")
class AdminRestaurantApprove(Resource):
    @admin_ns.marshal_with(admin_restaurant_model)
    @admin_ns.doc(security="Bearer Auth")
    @jwt_required()
    @roles_required("admin")
    def patch(self, restaurant_id):
        """Approve a pending restaurant."""
        restaurant = Restaurant.query.get_or_404(restaurant_id)
        restaurant.approved = True
        db.session.commit()
        return restaurant


@admin_ns.route("/restaurants/<int:restaurant_id>/reject")
class AdminRestaurantReject(Resource):
    @admin_ns.doc(security="Bearer Auth")
    @jwt_required()
    @roles_required("admin")
    def delete(self, restaurant_id):
        """Reject and delete a pending restaurant."""
        restaurant = Restaurant.query.get_or_404(restaurant_id)
        db.session.delete(restaurant)
        db.session.commit()
        return {"message": "Restaurant rejected and deleted"}, 200


@admin_ns.route("/orders")
class AdminOrderList(Resource):
    @admin_ns.doc(security="Bearer Auth")
    @jwt_required()
    @roles_required("admin")
    def get(self):
        """Get all orders across the system."""
        page = int(request.args.get("page", 1))
        per_page = min(int(request.args.get("per_page", 20)), 100)
        pagination = Order.query.order_by(Order.id.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        return [_serialize_order(o) for o in pagination.items]
