from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import jwt_required

from app.models import Payment
from app.utils.decorators import roles_required

payments_ns = Namespace("payments", description="Payment operations")

payment_model = payments_ns.model(
    "Payment",
    {
        "id": fields.Integer(readonly=True),
        "order_id": fields.Integer,
        "amount": fields.Float,
        "provider": fields.String,
        "status": fields.String,
    },
)


@payments_ns.route("")
class PaymentList(Resource):
    @payments_ns.marshal_list_with(payment_model)
    @payments_ns.doc(security="Bearer Auth")
    @jwt_required()
    @roles_required("admin")
    def get(self):
        """List all payments (admin-only)."""
        return Payment.query.all()

