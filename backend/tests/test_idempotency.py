from __future__ import annotations

import asyncio
import json

import anyio
import pytest
import requests
from redis.exceptions import RedisError
from starlette.responses import JSONResponse

from app import main
from app.idempotency import idempotent_write
from app.routes import cmn, commerce, transfer
from tests.contract_support import FakeResponse, authed_request, run_endpoint

KEY = "synthetic-operation-0000000000000001"
BODY = {"account_id": "a@b.com"}


def request(body=None, key=KEY):
    return authed_request(
        "/api/sim/transfer",
        "POST",
        body=json.dumps(body or BODY).encode(),
        headers={"idempotency-key": key},
    )


@pytest.mark.parametrize(
    "path,module,validator,payload",
    [
        (
            "/api/sim/transfer",
            transfer,
            "validate_transfer",
            {
                "sourceMsisdn": "91234567",
                "targetMsisdn": "92345678",
                "amount": 10,
                "userOfferId": "u1",
                "balanceResourceId": 1,
                "unit": "MB",
                "productFamily": "DATA",
            },
        ),
        (
            "/api/purchase",
            commerce,
            "validate_purchase",
            {
                "price": 10,
                "items": [{"offerId": "plan", "quantity": 1}],
            },
        ),
        (
            "/api/cmn/purchase",
            cmn,
            "validate_cmn",
            {
                "price": 10,
                "offerId": "cmn",
                "selectedNumber": "93456789",
            },
        ),
    ],
)
@pytest.mark.parametrize(
    "failure", ["timeout", "500", "invalid_json", "success", "direct_success"]
)
def test_financial_routes_never_repeat_a_claimed_write(
    monkeypatch, path, module, validator, payload, failure
):
    monkeypatch.setattr(module, validator, lambda *_: "THREE")
    writes = []

    class Upstream:
        def __init__(self):
            self.cookies = requests.cookies.RequestsCookieJar()

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def request(self, method, url, **kwargs):
            if method == "POST":
                writes.append(kwargs["json"])
                if failure == "timeout":
                    raise requests.exceptions.ReadTimeout(
                        "synthetic response loss after execution"
                    )
                if failure == "500":
                    return FakeResponse(500)
                if failure == "direct_success":
                    return FakeResponse(200, {"code": 1, "purchaseId": "completed"})
                if failure == "invalid_json" and path != "/api/sim/transfer":
                    response = FakeResponse(200)
                    response.json = lambda: (_ for _ in ()).throw(
                        ValueError("invalid json")
                    )
                    return response
                return FakeResponse(
                    200, {"paymentUrl": "https://pay.example.test/receipt"}
                )
            return FakeResponse(
                200,
                {
                    "accessPurchaseKey": "synthetic-purchase-key",
                    "offers": [
                        {
                            "offerSubType": "DTO",
                            "offerId": "dto",
                            "products": [
                                {"productId": "data", "productFamily": "DATA"}
                            ],
                        }
                    ],
                },
            )

    monkeypatch.setattr(main, "get_isolated_session", Upstream)
    body = json.dumps({**BODY, "subscriptionId": "s1", **payload}).encode()
    responses = [
        run_endpoint(
            path,
            authed_request(path, "POST", body=body, headers={"idempotency-key": KEY}),
        )
        for _ in range(2)
    ]
    assert len(writes) == 1
    assert responses[0].status_code == responses[1].status_code
    assert responses[0].body == responses[1].body
    if failure in {"timeout", "500"} or (
        failure == "invalid_json" and path != "/api/sim/transfer"
    ):
        assert responses[0].status_code == 409
        assert json.loads(responses[0].body)["code"] == "upstream_result_unknown"
    else:
        assert responses[0].status_code == 200
        if failure == "direct_success" and path != "/api/sim/transfer":
            assert json.loads(responses[0].body) == {"status": "success"}


def test_concurrent_submission_and_replay_execute_once():
    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()
        calls = []

        @idempotent_write(main._main_deps)
        async def operation(req):
            calls.append(1)
            started.set()
            await asyncio.wait_for(release.wait(), 3)
            return JSONResponse({"status": "success"})

        first = asyncio.create_task(operation(request()))
        await asyncio.wait_for(started.wait(), 3)
        concurrent = await operation(request())
        assert concurrent.status_code == 409
        release.set()
        assert (await first).status_code == 200
        assert (await operation(request())).status_code == 200
        changed = await operation(request({**BODY, "amount": 20}))
        assert json.loads(changed.body)["code"] == "idempotency_conflict"
        unauthorized = request()
        unauthorized.state.session_ctx.data["csrf_token"] = "different"
        assert (await operation(unauthorized)).status_code == 403
        assert calls == [1]

    anyio.run(scenario)


def test_storage_failure_never_turns_success_into_a_retryable_failure(monkeypatch):
    calls = []

    @idempotent_write(main._main_deps)
    async def operation(req):
        calls.append(1)
        return JSONResponse({"status": "success"})

    def fail(*_, **__):
        raise RedisError("synthetic failure")

    monkeypatch.setattr(main.redis_client, "set", fail)
    assert anyio.run(operation, request()).status_code == 200
    assert anyio.run(operation, request()).status_code == 409
    assert calls == [1]


def test_missing_key_and_unavailable_store_do_not_execute(monkeypatch):
    @idempotent_write(main._main_deps)
    async def operation(req):
        pytest.fail("write must not execute")

    assert anyio.run(operation, request(key="")).status_code == 400

    def fail(*_):
        raise RedisError("synthetic failure")

    monkeypatch.setattr(main.redis_client, "eval", fail)
    assert anyio.run(operation, request()).status_code == 503
