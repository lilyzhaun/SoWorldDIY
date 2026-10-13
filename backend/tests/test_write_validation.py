import copy
import json
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app import main
from app.main_deps import MainDepsAdapter
from app.schemas.requests import CmnPurchaseRequest, PurchaseRequest, TransferRequest
from app.services_validation import (
    WriteValidationError,
    money,
    validate_cmn,
    validate_purchase,
    validate_transfer,
)
from tests.contract_support import FakeResponse, authed_request, run_endpoint


def fixture_upstream(monkeypatch):
    profile = {
        "subscriptions": [
            {
                "primaryMsisdn": "11111111",
                "subscriptionId": "s",
                "subscriptionOffers": [
                    {
                        "offerId": "UO",
                        "offerType": "VAS",
                        "planStatus": "ACTIVE",
                        "transferAllowed": True,
                        "subscriptionProducts": [
                            {
                                "productSpecType": "DATA",
                                "productName": "Data",
                                "minTransferQuota": 1,
                                "matrixxBalanceInfos": [
                                    {
                                        "resourceId": 9,
                                        "unit": "MB",
                                        "amount": 500,
                                        "grantAmount": 500,
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
    }
    calls = []

    def make(**kw):
        calls.append(kw)
        url = kw["url"]
        if "getProfile" in url:
            return FakeResponse(200, copy.deepcopy(profile))
        if "getPlanOffers" in url:
            return FakeResponse(
                200,
                {
                    "offers": [
                        {"offerId": "OFF", "offerPrice": 50},
                        {"offerId": "H3OF00000000001", "offerPrice": 0},
                    ]
                },
            )
        if "WalletBalances" in url:
            return FakeResponse(200, [{"amount": 30}])
        if "getCmnOffer" in url:
            return FakeResponse(200, {"offers": [{"offerId": "CMN", "offerPrice": 10}]})
        if "accessPurchaseKey" in url:
            return FakeResponse(200, {"accessPurchaseKey": "key"})
        return FakeResponse(200, {"paymentUrl": "https://pay.example/"})

    monkeypatch.setattr(main, "make_3hk_request", make)
    return calls


def context():
    req = authed_request("/api/purchase", "POST")
    return MainDepsAdapter(main), req, req.state.session_ctx


def test_fresh_quote_and_membership(monkeypatch):
    calls = fixture_upstream(monkeypatch)
    deps, req, ctx = context()
    body = PurchaseRequest(
        account_id="a@b.com",
        subscriptionId="s",
        items=[{"offerId": "OFF", "quantity": 2}],
        price=100,
        txnAmount=30,
    )
    assert validate_purchase(deps, req, ctx, "a@b.com", body) == "THREE"
    assert any("getPlanOffers" in c["url"] for c in calls)
    for changes in [
        {"price": 0},
        {"txnAmount": 31},
        {"subscriptionId": "other"},
        {"items": [{"offerId": "unknown"}]},
        {"items": []},
        {"txnAmount": 101},
    ]:
        with pytest.raises(WriteValidationError):
            validate_purchase(
                deps,
                req,
                ctx,
                "a@b.com",
                PurchaseRequest.model_validate(body.model_dump() | changes),
            )


def test_quote_rejects_subcent_underpayment_and_handles_binary_rounding(monkeypatch):
    from app.services_validation import verify_payment

    fixture_upstream(monkeypatch)
    deps, req, ctx = context()
    verify_payment(
        deps,
        req,
        ctx,
        "a@b.com",
        PurchaseRequest(price=0.1 + 0.2),
        "THREE",
        Decimal("0.30"),
    )
    with pytest.raises(WriteValidationError):
        verify_payment(
            deps,
            req,
            ctx,
            "a@b.com",
            PurchaseRequest(price=49.999),
            "THREE",
            Decimal("50"),
        )


def test_new_line_and_cmn_validation(monkeypatch):
    fixture_upstream(monkeypatch)
    deps, req, ctx = context()
    assert (
        validate_purchase(
            deps,
            req,
            ctx,
            "a@b.com",
            PurchaseRequest(new_line=True, items=[{"offerId": "OFF"}], price=50),
        )
        == "THREE"
    )
    with pytest.raises(WriteValidationError):
        validate_purchase(
            deps,
            req,
            ctx,
            "a@b.com",
            PurchaseRequest(
                new_line=True, items=[{"offerId": "OFF"}], price=50, txnAmount=1
            ),
        )
    body = CmnPurchaseRequest(
        subscriptionId="s", offerId="CMN", selectedNumber="33333333", price=10
    )
    assert validate_cmn(deps, req, ctx, "a@b.com", body) == "THREE"
    with pytest.raises(WriteValidationError):
        validate_cmn(
            deps, req, ctx, "a@b.com", body.model_copy(update={"offerId": "OTHER"})
        )


def test_transfer_checks_owner_resource_units_and_available_amount(monkeypatch):
    fixture_upstream(monkeypatch)
    deps, req, ctx = context()
    body = TransferRequest(
        subscriptionId="s",
        sourceMsisdn="11111111",
        targetMsisdn="22222222",
        productFamily="DATA",
        balanceResourceId=9,
        userOfferId="UO",
        unit="MB",
        amount=100,
    )
    assert validate_transfer(deps, req, ctx, "a@b.com", body) == "THREE"
    for changes in [
        {"sourceMsisdn": "99999999"},
        {"unit": "GB"},
        {"amount": 501},
        {"amount": 0.5},
        {"userOfferId": "foreign"},
        {"balanceResourceId": 8},
        {"productFamily": "VOICE"},
    ]:
        with pytest.raises(WriteValidationError):
            validate_transfer(
                deps, req, ctx, "a@b.com", body.model_copy(update=changes)
            )


@pytest.mark.parametrize(
    "model,body",
    [
        (PurchaseRequest, {"price": -1}),
        (PurchaseRequest, {"txnAmount": float("nan")}),
        (PurchaseRequest, {"price": float("inf")}),
        (PurchaseRequest, {"paymentType": "ARBITRARY"}),
        (PurchaseRequest, {"items": [{"offerId": "O", "quantity": -3}]}),
        (PurchaseRequest, {"subscriptionId": "../../admin"}),
        (TransferRequest, {"amount": "-1"}),
        (TransferRequest, {"amount": "nan"}),
        (TransferRequest, {"targetMsisdn": "abc12345678"}),
        (TransferRequest, {"balanceResourceId": "nope"}),
    ],
)
def test_invalid_write_schema(model, body):
    with pytest.raises(ValidationError):
        model.model_validate(body)


def test_route_does_not_forward_unverified_purchase(monkeypatch):
    calls = fixture_upstream(monkeypatch)
    body = {
        "account_id": "a@b.com",
        "subscriptionId": "s",
        "items": [{"offerId": "OFF"}],
        "price": 0,
    }
    response = run_endpoint(
        "/api/purchase",
        authed_request("/api/purchase", "POST", body=json.dumps(body).encode()),
    )
    assert response.status_code == 400
    assert not any(c["method"] == "POST" for c in calls)


@pytest.mark.parametrize("value", ["bad", -1, float("inf")])
def test_untrusted_upstream_money_rejected(value):
    with pytest.raises(WriteValidationError):
        money(value)
