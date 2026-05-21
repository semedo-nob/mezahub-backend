from __future__ import annotations

from app.services.mpesa_service import MpesaService


class PaymentService:
    """Facade for payment operations used by the API layer."""

    @staticmethod
    def initiate_payment(*, phone_number: str, amount: float, order_id: int) -> dict:
        return MpesaService.stk_push(
            phone_number=phone_number,
            amount=amount,
            order_id=order_id,
            account_reference=f"ORDER-{order_id}",
        )

    @staticmethod
    def query_payment(*, checkout_request_id: str) -> dict:
        return MpesaService.transaction_status(checkout_request_id=checkout_request_id)

    @staticmethod
    def pay_rider(*, phone_number: str, amount: float, order_id: int) -> dict:
        return MpesaService.b2c_payment(
            phone_number=phone_number,
            amount=amount,
            reference=f"ORDER-{order_id}",
        )
