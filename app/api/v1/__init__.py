from flask import Blueprint
from flask_restx import Api

from app.api.v1.auth import auth_ns
from app.api.v1.customers import customers_ns
from app.api.v1.restaurants import restaurants_ns
from app.api.v1.riders import riders_ns
from app.api.v1.orders import orders_ns
from app.api.v1.deliveries import deliveries_ns
from app.api.v1.payments import payments_ns
from app.api.v1.admin import admin_ns


api_bp = Blueprint("api", __name__)

api = Api(
    api_bp,
    version="1.0",
    title="MEZAHUB API",
    description="API for MEZAHUB Food Delivery Platform",
    doc="/docs/",
    authorizations={
        "Bearer Auth": {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization",
            "description": "Type: Bearer <your_token>",
        }
    },
)

api.add_namespace(auth_ns, path="/auth")
api.add_namespace(customers_ns, path="/customers")
api.add_namespace(restaurants_ns, path="/restaurants")
api.add_namespace(riders_ns, path="/riders")
api.add_namespace(orders_ns, path="/orders")
api.add_namespace(deliveries_ns, path="/deliveries")
api.add_namespace(payments_ns, path="/payments")
api.add_namespace(admin_ns, path="/admin")

