from __future__ import annotations


class PaymentService:
    """Placeholder payment service (e.g., M-Pesa integration)."""

    @staticmethod
    def initiate_payment(*_args, **_kwargs) -> dict:
        return {"status": "mocked", "reference": "TEST-REF"}

