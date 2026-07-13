"""Unit tests for pure service helpers (no ASGI / monkeypatch seams)."""

from __future__ import annotations

from app.schemas.requests import TransferRequest


def test_transfer_request_accepts_numeric_coercion_inputs() -> None:
    body = TransferRequest.model_validate(
        {
            "account_id": "a@b.com",
            "subscriptionId": 1001,
            "productFamily": "DATA",
            "sourceMsisdn": 85211112222,
            "targetMsisdn": "85233334444",
            "userOfferId": "UO",
            "balanceResourceId": "9",
            "unit": "MB",
            "amount": "500.5",
        }
    )
    assert body.subscriptionId == 1001
    assert body.sourceMsisdn == 85211112222
    assert body.balanceResourceId == "9"
    assert body.amount == "500.5"
    assert int(body.balanceResourceId) == 9
    assert float(body.amount) == 500.5
