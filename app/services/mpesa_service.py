from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import Any

import requests
from flask import current_app


class MpesaService:
    SANDBOX_URL = "https://sandbox.safaricom.co.ke"
    PRODUCTION_URL = "https://api.safaricom.co.ke"
    TIMEOUT_SECONDS = 30

    @classmethod
    def base_url(cls) -> str:
        env = (current_app.config.get("MPESA_ENV") or "sandbox").strip().lower()
        return cls.PRODUCTION_URL if env == "production" else cls.SANDBOX_URL

    @classmethod
    def is_configured(cls) -> bool:
        required = (
            current_app.config.get("MPESA_CONSUMER_KEY"),
            current_app.config.get("MPESA_CONSUMER_SECRET"),
            current_app.config.get("MPESA_SHORTCODE"),
            current_app.config.get("MPESA_PASSKEY"),
        )
        return all(value for value in required)

    @classmethod
    def get_access_token(cls) -> str:
        consumer_key = current_app.config.get("MPESA_CONSUMER_KEY")
        consumer_secret = current_app.config.get("MPESA_CONSUMER_SECRET")
        if not consumer_key or not consumer_secret:
            raise ValueError("M-Pesa consumer key/secret are not configured.")

        url = f"{cls.base_url()}/oauth/v1/generate"
        auth = base64.b64encode(f"{consumer_key}:{consumer_secret}".encode("utf-8")).decode(
            "utf-8"
        )
        response = requests.get(
            url,
            params={"grant_type": "client_credentials"},
            headers={"Authorization": f"Basic {auth}"},
            timeout=cls.TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise ValueError("M-Pesa access token was missing from OAuth response.")
        return token

    @classmethod
    def generate_password(cls) -> tuple[str, str]:
        shortcode = current_app.config.get("MPESA_SHORTCODE")
        passkey = current_app.config.get("MPESA_PASSKEY")
        if not shortcode or not passkey:
            raise ValueError("M-Pesa shortcode/passkey are not configured.")

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        raw = f"{shortcode}{passkey}{timestamp}"
        encoded = base64.b64encode(raw.encode("utf-8")).decode("utf-8")
        return encoded, timestamp

    @staticmethod
    def normalize_phone_number(phone_number: str) -> str:
        value = "".join(ch for ch in str(phone_number or "").strip() if ch.isdigit() or ch == "+")
        if value.startswith("+254"):
            value = value[1:]
        if value.startswith("254") and len(value) == 12:
            return value
        if value.startswith("0") and len(value) == 10:
            return f"254{value[1:]}"
        raise ValueError("Phone number must be a valid Kenyan mobile number.")

    @classmethod
    def stk_callback_url(cls) -> str:
        explicit = (current_app.config.get("MPESA_STK_CALLBACK_URL") or "").strip()
        if explicit:
            return explicit
        base = (current_app.config.get("MPESA_CALLBACK_BASE_URL") or "").strip()
        if not base:
            base = (current_app.config.get("PUBLIC_API_BASE_URL") or "").strip()
        if not base:
            raise ValueError(
                "Set MPESA_STK_CALLBACK_URL or MPESA_CALLBACK_BASE_URL for public callbacks."
            )
        return f"{base.rstrip('/')}/api/v1/payments/mpesa/callback"

    @classmethod
    def b2c_result_url(cls) -> str:
        explicit = (current_app.config.get("MPESA_B2C_RESULT_URL") or "").strip()
        if explicit:
            return explicit
        base = (current_app.config.get("MPESA_CALLBACK_BASE_URL") or "").strip()
        if not base:
            base = (current_app.config.get("PUBLIC_API_BASE_URL") or "").strip()
        if not base:
            raise ValueError(
                "Set MPESA_B2C_RESULT_URL or MPESA_CALLBACK_BASE_URL for public callbacks."
            )
        return f"{base.rstrip('/')}/api/v1/payments/mpesa/b2c/result"

    @classmethod
    def b2c_timeout_url(cls) -> str:
        explicit = (current_app.config.get("MPESA_B2C_TIMEOUT_URL") or "").strip()
        if explicit:
            return explicit
        base = (current_app.config.get("MPESA_CALLBACK_BASE_URL") or "").strip()
        if not base:
            base = (current_app.config.get("PUBLIC_API_BASE_URL") or "").strip()
        if not base:
            raise ValueError(
                "Set MPESA_B2C_TIMEOUT_URL or MPESA_CALLBACK_BASE_URL for public callbacks."
            )
        return f"{base.rstrip('/')}/api/v1/payments/mpesa/b2c/timeout"

    @classmethod
    def _request(cls, method: str, path: str, *, payload: dict[str, Any]) -> dict[str, Any]:
        token = cls.get_access_token()
        response = requests.request(
            method=method,
            url=f"{cls.base_url()}{path}",
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=cls.TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()

    @classmethod
    def stk_push(
        cls,
        *,
        phone_number: str,
        amount: float | int,
        order_id: int,
        account_reference: str | None = None,
    ) -> dict[str, Any]:
        if not cls.is_configured():
            raise ValueError("M-Pesa STK is not configured. Add M-Pesa env variables first.")

        normalized_phone = cls.normalize_phone_number(phone_number)
        password, timestamp = cls.generate_password()
        payload = {
            "BusinessShortCode": current_app.config["MPESA_SHORTCODE"],
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": max(1, int(round(float(amount)))),
            "PartyA": normalized_phone,
            "PartyB": current_app.config["MPESA_SHORTCODE"],
            "PhoneNumber": normalized_phone,
            "CallBackURL": cls.stk_callback_url(),
            "AccountReference": account_reference or f"ORDER-{order_id}",
            "TransactionDesc": f"Payment for order {order_id}",
        }
        return cls._request("POST", "/mpesa/stkpush/v1/processrequest", payload=payload)

    @classmethod
    def transaction_status(cls, *, checkout_request_id: str) -> dict[str, Any]:
        password, timestamp = cls.generate_password()
        payload = {
            "BusinessShortCode": current_app.config["MPESA_SHORTCODE"],
            "Password": password,
            "Timestamp": timestamp,
            "CheckoutRequestID": checkout_request_id,
        }
        return cls._request("POST", "/mpesa/stkpushquery/v1/query", payload=payload)

    @classmethod
    def b2c_payment(
        cls,
        *,
        phone_number: str,
        amount: float | int,
        reference: str,
        command_id: str = "BusinessPayment",
    ) -> dict[str, Any]:
        initiator_name = current_app.config.get("MPESA_INITIATOR_NAME")
        security_credential = current_app.config.get("MPESA_B2C_SECURITY_CREDENTIAL")
        if not initiator_name or not security_credential:
            raise ValueError(
                "M-Pesa B2C is not configured. Set MPESA_INITIATOR_NAME and "
                "MPESA_B2C_SECURITY_CREDENTIAL."
            )

        normalized_phone = cls.normalize_phone_number(phone_number)
        payload = {
            "InitiatorName": initiator_name,
            "SecurityCredential": security_credential,
            "CommandID": command_id,
            "Amount": max(1, int(round(float(amount)))),
            "PartyA": current_app.config["MPESA_SHORTCODE"],
            "PartyB": normalized_phone,
            "Remarks": f"Payment for {reference}",
            "QueueTimeOutURL": cls.b2c_timeout_url(),
            "ResultURL": cls.b2c_result_url(),
            "Occasion": "MezaHub payout",
        }
        return cls._request("POST", "/mpesa/b2c/v1/paymentrequest", payload=payload)

    @staticmethod
    def parse_stk_callback(payload: dict[str, Any] | None) -> dict[str, Any]:
        payload = payload or {}
        body = payload.get("Body") or {}
        callback = body.get("stkCallback") or {}
        metadata_items = (
            ((callback.get("CallbackMetadata") or {}).get("Item")) or []
        )
        metadata = {
            item.get("Name"): item.get("Value")
            for item in metadata_items
            if isinstance(item, dict) and item.get("Name")
        }
        return {
            "merchant_request_id": callback.get("MerchantRequestID"),
            "checkout_request_id": callback.get("CheckoutRequestID"),
            "result_code": callback.get("ResultCode"),
            "result_desc": callback.get("ResultDesc"),
            "amount": metadata.get("Amount"),
            "mpesa_receipt_number": metadata.get("MpesaReceiptNumber"),
            "transaction_date": metadata.get("TransactionDate"),
            "phone_number": metadata.get("PhoneNumber"),
            "raw": payload,
        }
