from __future__ import annotations

from datetime import datetime

from flask import current_app, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required
from flask_restx import Namespace, Resource, fields

from app.extensions.database import db
from app.models import Order, Payment, Payout, Rider, Restaurant, User
from app.services.mpesa_service import MpesaService
from app.realtime.events import (
    emit_admin_event,
    emit_customer_event,
    emit_restaurant_event,
    emit_rider_event,
)
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
        "phone_number": fields.String,
        "checkout_request_id": fields.String,
        "merchant_request_id": fields.String,
        "mpesa_receipt_number": fields.String,
        "result_code": fields.String,
        "result_desc": fields.String,
        "transaction_date": fields.String,
        "created_at": fields.String,
        "updated_at": fields.String,
    },
)

stk_push_request = payments_ns.model(
    "MpesaStkPushRequest",
    {
        "order_id": fields.Integer(required=True),
        "phone_number": fields.String(required=True),
        "amount": fields.Float(required=False, description="Defaults to order total if omitted"),
    },
)

b2c_request = payments_ns.model(
    "MpesaRiderPayoutRequest",
    {
        "order_id": fields.Integer(required=True),
        "phone_number": fields.String(required=True),
        "amount": fields.Float(required=True),
        "command_id": fields.String(required=False, default="BusinessPayment"),
    },
)

mpesa_status_model = payments_ns.model(
    "MpesaStatus",
    {
        "success": fields.Boolean,
        "checkout_request_id": fields.String,
        "result_code": fields.String,
        "result_desc": fields.String,
        "provider_status": fields.String,
    },
)


def _serialize_payment(payment: Payment) -> dict:
    return {
        "id": payment.id,
        "order_id": payment.order_id,
        "amount": float(payment.amount),
        "delivery_fee": float(payment.delivery_fee or 0),
        "total_amount": float(payment.total_amount or payment.amount),
        "provider": payment.provider,
        "status": payment.status,
        "customer_id": payment.customer_id,
        "restaurant_id": payment.restaurant_id,
        "rider_id": payment.rider_id,
        "phone_number": payment.phone_number,
        "checkout_request_id": payment.checkout_request_id,
        "merchant_request_id": payment.merchant_request_id,
        "mpesa_receipt_number": payment.mpesa_receipt_number,
        "result_code": payment.result_code,
        "result_desc": payment.result_desc,
        "restaurant_paid": payment.restaurant_paid,
        "rider_paid": payment.rider_paid,
        "restaurant_payout_date": payment.restaurant_payout_date.isoformat()
        if payment.restaurant_payout_date
        else None,
        "rider_payout_date": payment.rider_payout_date.isoformat()
        if payment.rider_payout_date
        else None,
        "transaction_date": payment.transaction_date.isoformat()
        if payment.transaction_date
        else None,
        "created_at": payment.created_at.isoformat() if payment.created_at else None,
        "updated_at": payment.updated_at.isoformat() if payment.updated_at else None,
    }


def _is_allowed_for_order(order: Order, *, user_id: int, role: str | None) -> bool:
    if role == "admin":
        return True
    if role == "customer":
        return order.customer_id == user_id
    if role == "restaurant":
        from app.models import Restaurant

        owned_ids = [item.id for item in Restaurant.query.filter_by(owner_id=user_id).all()]
        return order.restaurant_id in owned_ids
    return False


def _find_payment_by_checkout_request_id(checkout_request_id: str) -> Payment | None:
    return Payment.query.filter_by(checkout_request_id=checkout_request_id).first()


def _serialize_payout(payout: Payout) -> dict:
    return {
        "id": payout.id,
        "payment_id": payout.payment_id,
        "recipient_type": payout.recipient_type,
        "recipient_id": payout.recipient_id,
        "recipient_phone": payout.recipient_phone,
        "amount": float(payout.amount),
        "conversation_id": payout.conversation_id,
        "originator_conversation_id": payout.originator_conversation_id,
        "status": payout.status,
        "result_code": payout.result_code,
        "result_desc": payout.result_desc,
        "payout_date": payout.payout_date.isoformat() if payout.payout_date else None,
        "created_at": payout.created_at.isoformat() if payout.created_at else None,
    }


def _resolve_order_access(order: Order) -> tuple[int | None, str | None]:
    identity = get_jwt_identity()
    if identity is None:
        return None, None
    claims = get_jwt()
    return int(identity), claims.get("role")


def _create_payout(
    *,
    payment: Payment,
    recipient_type: str,
    recipient_id: int,
    recipient_phone: str,
    amount: float,
    command_id: str = "BusinessPayment",
) -> Payout:
    result = MpesaService.b2c_payment(
        phone_number=recipient_phone,
        amount=amount,
        reference=f"ORDER-{payment.order_id}",
        command_id=command_id,
    )
    payout = Payout(
        payment_id=payment.id,
        recipient_type=recipient_type,
        recipient_id=recipient_id,
        recipient_phone=MpesaService.normalize_phone_number(recipient_phone),
        amount=amount,
        conversation_id=result.get("ConversationID"),
        originator_conversation_id=result.get("OriginatorConversationID"),
        status="processing" if str(result.get("ResponseCode")) == "0" else "failed",
        result_code=str(result.get("ResponseCode")) if result.get("ResponseCode") is not None else None,
        result_desc=result.get("ResponseDescription"),
        payout_date=datetime.utcnow(),
    )
    db.session.add(payout)
    return payout


@payments_ns.route("")
class PaymentList(Resource):
    @payments_ns.marshal_list_with(payment_model)
    @payments_ns.doc(security="Bearer Auth")
    @jwt_required()
    @roles_required("admin")
    def get(self):
        """List all payments (admin-only)."""
        return [_serialize_payment(item) for item in Payment.query.order_by(Payment.id.desc()).all()]


@payments_ns.route("/mpesa/stk-push")
class MpesaStkPush(Resource):
    @payments_ns.expect(stk_push_request, validate=True)
    @payments_ns.doc(security="Bearer Auth")
    @jwt_required(optional=True)
    def post(self):
        """Initiate an M-Pesa STK push for an order."""
        payload = request.get_json() or {}
        order = Order.query.get_or_404(int(payload["order_id"]))

        identity = get_jwt_identity()
        if identity is not None:
            claims = get_jwt()
            if not _is_allowed_for_order(order, user_id=int(identity), role=claims.get("role")):
                return {"error": "Forbidden"}, 403

        amount = float(payload.get("amount") or float(order.total_amount))
        phone_number = payload["phone_number"]

        try:
            result = MpesaService.stk_push(
                phone_number=phone_number,
                amount=amount,
                order_id=order.id,
                account_reference=f"ORDER-{order.id}",
            )
        except Exception as exc:  # pragma: no cover - network/credentials dependent
            current_app.logger.exception("Failed to initiate STK push: %s", exc)
            return {"success": False, "error": str(exc)}, 400

        payment = Payment(
            order_id=order.id,
            customer_id=order.customer_id,
            restaurant_id=order.restaurant_id,
            amount=amount,
            delivery_fee=max(float(order.total_amount) - amount, 0.0)
            if payload.get("amount")
            else 0.0,
            total_amount=float(order.total_amount),
            provider="mpesa",
            status="pending",
            phone_number=MpesaService.normalize_phone_number(phone_number),
            checkout_request_id=result.get("CheckoutRequestID"),
            merchant_request_id=result.get("MerchantRequestID"),
            result_code=result.get("ResponseCode"),
            result_desc=result.get("ResponseDescription"),
        )
        order.payment_method = "mpesa"
        order.payment_status = "pending"
        db.session.add(payment)
        db.session.commit()

        return {
            "success": True,
            "checkout_request_id": payment.checkout_request_id,
            "merchant_request_id": payment.merchant_request_id,
            "provider_status": payment.status,
            "message": result.get("CustomerMessage")
            or result.get("ResponseDescription")
            or "STK push initiated. Check your phone.",
        }, 200


@payments_ns.route("/mpesa/callback")
class MpesaCallback(Resource):
    def post(self):
        """Receive Safaricom STK callback updates."""
        callback_payload = request.get_json(silent=True) or {}
        parsed = MpesaService.parse_stk_callback(callback_payload)
        payment = _find_payment_by_checkout_request_id(parsed["checkout_request_id"])

        if payment is None:
            current_app.logger.warning(
                "M-Pesa callback received for unknown checkout_request_id=%s",
                parsed["checkout_request_id"],
            )
            return {"ResultCode": 0, "ResultDesc": "Accepted"}, 200

        payment.result_code = str(parsed["result_code"]) if parsed["result_code"] is not None else None
        payment.result_desc = parsed["result_desc"]
        payment.raw_callback = parsed["raw"]
        payment.phone_number = (
            str(parsed["phone_number"]) if parsed["phone_number"] is not None else payment.phone_number
        )
        payment.mpesa_receipt_number = parsed["mpesa_receipt_number"]

        if parsed["transaction_date"]:
            try:
                payment.transaction_date = datetime.strptime(
                    str(parsed["transaction_date"]), "%Y%m%d%H%M%S"
                )
            except ValueError:
                payment.transaction_date = datetime.utcnow()

        order = Order.query.get(payment.order_id)
        if str(parsed["result_code"]) == "0":
            payment.status = "completed"
            if order is not None:
                order.payment_method = "mpesa"
                order.payment_status = "completed"
                emit_customer_event(
                    order.customer_id,
                    "payment_successful",
                    {
                        "order_id": order.id,
                        "payment_id": payment.id,
                        "amount": float(payment.total_amount or payment.amount),
                        "status": payment.status,
                        "mpesa_receipt_number": payment.mpesa_receipt_number,
                    },
                )
                emit_restaurant_event(
                    order.restaurant_id,
                    "order_paid",
                    {
                        "order_id": order.id,
                        "payment_id": payment.id,
                        "amount": float(payment.total_amount or payment.amount),
                    },
                )
                emit_admin_event(
                    "payment_completed",
                    {
                        "order_id": order.id,
                        "payment_id": payment.id,
                        "restaurant_id": order.restaurant_id,
                        "customer_id": order.customer_id,
                    },
                )
        else:
            payment.status = "failed"
            if order is not None:
                order.payment_method = "mpesa"
                order.payment_status = "failed"
                emit_customer_event(
                    order.customer_id,
                    "payment_failed",
                    {
                        "order_id": order.id,
                        "payment_id": payment.id,
                        "status": payment.status,
                        "result_desc": payment.result_desc,
                    },
                )

        db.session.commit()
        return {"ResultCode": 0, "ResultDesc": "Success"}, 200


@payments_ns.route("/mpesa/query/<string:checkout_request_id>")
class MpesaQuery(Resource):
    @payments_ns.marshal_with(mpesa_status_model)
    @payments_ns.doc(security="Bearer Auth")
    @jwt_required(optional=True)
    def get(self, checkout_request_id: str):
        """Query Safaricom and local DB for the latest STK status."""
        payment = _find_payment_by_checkout_request_id(checkout_request_id)
        if payment is None:
            return {"success": False, "result_desc": "Payment not found"}, 404

        identity = get_jwt_identity()
        if identity is not None:
            claims = get_jwt()
            order = Order.query.get(payment.order_id)
            if order and not _is_allowed_for_order(
                order, user_id=int(identity), role=claims.get("role")
            ):
                return {"error": "Forbidden"}, 403

        try:
            result = MpesaService.transaction_status(checkout_request_id=checkout_request_id)
            payment.result_code = str(result.get("ResultCode")) if result.get("ResultCode") is not None else payment.result_code
            payment.result_desc = result.get("ResultDesc") or payment.result_desc
            if str(result.get("ResultCode")) == "0":
                payment.status = "completed"
            elif result.get("ResultCode") is not None:
                payment.status = "failed"
            db.session.commit()
        except Exception as exc:  # pragma: no cover - network/credentials dependent
            current_app.logger.exception("Failed to query M-Pesa transaction: %s", exc)
            return {
                "success": False,
                "checkout_request_id": checkout_request_id,
                "provider_status": payment.status,
                "result_desc": str(exc),
            }, 400

        return {
            "success": True,
            "checkout_request_id": checkout_request_id,
            "result_code": payment.result_code,
            "result_desc": payment.result_desc,
            "provider_status": payment.status,
        }


@payments_ns.route("/orders/<int:order_id>/status")
class OrderPaymentStatus(Resource):
    @payments_ns.doc(security="Bearer Auth")
    @jwt_required()
    def get(self, order_id: int):
        """Get consolidated payment status for an order."""
        order = Order.query.get_or_404(order_id)
        user_id, role = _resolve_order_access(order)
        if user_id is None or not _is_allowed_for_order(order, user_id=user_id, role=role):
            if role == "rider":
                rider = Rider.query.filter_by(user_id=user_id).first() if user_id else None
                if not rider or order.status not in ("assigned", "out_for_delivery", "delivered"):
                    return {"error": "Forbidden"}, 403
            else:
                return {"error": "Forbidden"}, 403

        payment = Payment.query.filter_by(order_id=order.id).order_by(Payment.id.desc()).first()
        if payment is None:
            return {
                "order_id": order.id,
                "order_status": order.status,
                "payment_status": order.payment_status,
                "payment": None,
            }
        payouts = Payout.query.filter_by(payment_id=payment.id).order_by(Payout.id.desc()).all()
        return {
            "order_id": order.id,
            "order_status": order.status,
            "payment_status": order.payment_status,
            "payment": _serialize_payment(payment),
            "payouts": [_serialize_payout(item) for item in payouts],
        }


@payments_ns.route("/mpesa/rider-payout")
class MpesaRiderPayout(Resource):
    @payments_ns.expect(b2c_request, validate=True)
    @payments_ns.doc(security="Bearer Auth")
    @jwt_required()
    @roles_required("admin")
    def post(self):
        """Initiate an M-Pesa B2C payout to a rider."""
        payload = request.get_json() or {}
        order = Order.query.get_or_404(int(payload["order_id"]))

        try:
            result = MpesaService.b2c_payment(
                phone_number=payload["phone_number"],
                amount=float(payload["amount"]),
                reference=f"ORDER-{order.id}",
                command_id=(payload.get("command_id") or "BusinessPayment"),
            )
        except Exception as exc:  # pragma: no cover - network/credentials dependent
            current_app.logger.exception("Failed to initiate rider payout: %s", exc)
            return {"success": False, "error": str(exc)}, 400

        payment = Payment(
            order_id=order.id,
            amount=float(payload["amount"]),
            provider="mpesa_b2c",
            status="processing",
            phone_number=MpesaService.normalize_phone_number(payload["phone_number"]),
            conversation_id=result.get("ConversationID"),
            originator_conversation_id=result.get("OriginatorConversationID"),
            result_code=result.get("ResponseCode"),
            result_desc=result.get("ResponseDescription"),
        )
        db.session.add(payment)
        db.session.commit()

        return {
            "success": True,
            "payment_id": payment.id,
            "conversation_id": payment.conversation_id,
            "originator_conversation_id": payment.originator_conversation_id,
            "message": payment.result_desc or "Rider payout initiated.",
        }, 200


@payments_ns.route("/<int:payment_id>/restaurant-payout")
class RestaurantPayout(Resource):
    @payments_ns.doc(security="Bearer Auth")
    @jwt_required()
    @roles_required("admin")
    def post(self, payment_id: int):
        """Admin-triggered payout to a restaurant after successful customer payment."""
        payment = Payment.query.get_or_404(payment_id)
        if payment.status != "completed":
            return {"error": "Only completed customer payments can be paid out"}, 400
        if payment.restaurant_paid:
            return {"error": "Restaurant has already been paid for this payment"}, 400
        restaurant = Restaurant.query.get(payment.restaurant_id)
        if restaurant is None or not restaurant.phone:
            return {"error": "Restaurant phone is missing"}, 400

        try:
            payout = _create_payout(
                payment=payment,
                recipient_type="restaurant",
                recipient_id=restaurant.id,
                recipient_phone=restaurant.phone,
                amount=float(payment.amount),
            )
        except Exception as exc:  # pragma: no cover
            current_app.logger.exception("Failed to initiate restaurant payout: %s", exc)
            return {"success": False, "error": str(exc)}, 400

        payment.restaurant_paid = payout.status in ("processing", "completed")
        payment.restaurant_payout_date = payout.payout_date
        db.session.commit()

        emit_restaurant_event(
            restaurant.id,
            "restaurant_payout_initiated",
            {
                "payment_id": payment.id,
                "order_id": payment.order_id,
                "amount": float(payment.amount),
                "payout_id": payout.id,
            },
        )
        emit_admin_event(
            "restaurant_payout_initiated",
            {"payment_id": payment.id, "order_id": payment.order_id, "payout_id": payout.id},
        )
        return {"success": True, "payment": _serialize_payment(payment), "payout": _serialize_payout(payout)}


@payments_ns.route("/<int:payment_id>/rider-payout")
class RiderPayout(Resource):
    @payments_ns.doc(security="Bearer Auth")
    @jwt_required()
    @roles_required("admin", "rider")
    def post(self, payment_id: int):
        """Trigger rider payout after delivery completion."""
        payment = Payment.query.get_or_404(payment_id)
        if payment.status != "completed":
            return {"error": "Only completed customer payments can fund rider payout"}, 400
        if payment.rider_paid:
            return {"error": "Rider has already been paid for this payment"}, 400

        user_id = int(get_jwt_identity())
        role = get_jwt().get("role")
        rider = None
        if role == "rider":
            rider = Rider.query.filter_by(user_id=user_id).first()
            if rider is None or payment.rider_id not in (None, rider.id):
                return {"error": "Forbidden"}, 403
        else:
            rider = Rider.query.get(payment.rider_id) if payment.rider_id else None
        if rider is None:
            return {"error": "Rider is not assigned on this payment yet"}, 400

        rider_user = User.query.get(rider.user_id)
        if rider_user is None or not rider_user.phone:
            return {"error": "Rider phone is missing"}, 400
        amount = float(payment.delivery_fee or 0)
        if amount <= 0:
            return {"error": "No rider payout amount is available for this payment"}, 400

        try:
            payout = _create_payout(
                payment=payment,
                recipient_type="rider",
                recipient_id=rider.id,
                recipient_phone=rider_user.phone,
                amount=amount,
            )
        except Exception as exc:  # pragma: no cover
            current_app.logger.exception("Failed to initiate rider payout: %s", exc)
            return {"success": False, "error": str(exc)}, 400

        payment.rider_id = rider.id
        payment.rider_paid = payout.status in ("processing", "completed")
        payment.rider_payout_date = payout.payout_date
        db.session.commit()

        emit_rider_event(
            rider.id,
            "rider_payout_initiated",
            {
                "payment_id": payment.id,
                "order_id": payment.order_id,
                "amount": amount,
                "payout_id": payout.id,
            },
        )
        emit_admin_event(
            "rider_payout_initiated",
            {"payment_id": payment.id, "order_id": payment.order_id, "payout_id": payout.id},
        )
        return {"success": True, "payment": _serialize_payment(payment), "payout": _serialize_payout(payout)}


@payments_ns.route("/payouts")
class PayoutList(Resource):
    @payments_ns.doc(security="Bearer Auth")
    @jwt_required()
    @roles_required("admin")
    def get(self):
        """List payouts for admin reporting."""
        payouts = Payout.query.order_by(Payout.id.desc()).all()
        return [_serialize_payout(item) for item in payouts]


@payments_ns.route("/mpesa/b2c/result")
class MpesaB2CResult(Resource):
    def post(self):
        """Accept Safaricom B2C result callbacks."""
        current_app.logger.info("Received M-Pesa B2C result callback: %s", request.get_json(silent=True))
        return {"ResultCode": 0, "ResultDesc": "Success"}, 200


@payments_ns.route("/mpesa/b2c/timeout")
class MpesaB2CTimeout(Resource):
    def post(self):
        """Accept Safaricom B2C timeout callbacks."""
        current_app.logger.warning(
            "Received M-Pesa B2C timeout callback: %s", request.get_json(silent=True)
        )
        return {"ResultCode": 0, "ResultDesc": "Success"}, 200
