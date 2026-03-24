from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import jwt_required

from app.models import User
from app.utils.decorators import roles_required

customers_ns = Namespace("customers", description="Customer operations")

customer_model = customers_ns.model(
    "Customer",
    {
        "id": fields.Integer(readonly=True),
        "name": fields.String,
        "email": fields.String,
        "phone": fields.String,
        "profile_image": fields.String,
        "is_active": fields.Boolean,
    },
)


@customers_ns.route("")
class CustomerList(Resource):
    @customers_ns.marshal_list_with(customer_model)
    @customers_ns.doc(security="Bearer Auth")
    @jwt_required()
    @roles_required("admin")
    def get(self):
        """List all customers (admin-only)."""
        customers = User.query.filter_by(role="customer").all()
        return customers

