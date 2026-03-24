from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import jwt_required, get_jwt

from app.models import Delivery
from app.utils.decorators import roles_required

deliveries_ns = Namespace("deliveries", description="Delivery operations")

delivery_model = deliveries_ns.model(
    "Delivery",
    {
        "id": fields.Integer(readonly=True),
        "order_id": fields.Integer,
        "rider_id": fields.Integer,
        "status": fields.String,
    },
)


@deliveries_ns.route("")
class DeliveryList(Resource):
    @deliveries_ns.marshal_list_with(delivery_model)
    @deliveries_ns.doc(security="Bearer Auth")
    @jwt_required()
    def get(self):
        """
        List deliveries:
        - rider: their deliveries
        - admin: all deliveries
        """
        claims = get_jwt()
        role = claims.get("role")

        query = Delivery.query
        if role == "rider":
            from flask_jwt_extended import get_jwt_identity

            user_id = int(get_jwt_identity())
            from app.models import Rider as RiderModel

            rider = RiderModel.query.filter_by(user_id=user_id).first()
            if rider:
                query = query.filter_by(rider_id=rider.id)
            else:
                query = query.filter_by(id=None)
        elif role != "admin":
            return [], 200

        return query.all()

