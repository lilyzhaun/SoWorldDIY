"""Validate sensitive writes against fresh, read-only upstream data."""

from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import Request

from .routes.deps import RouteDeps
from .schemas.requests import CmnPurchaseRequest, PurchaseRequest, TransferRequest
from .services_commerce import BASE_NEW_LINE_OFFER, parse_wallet_balance
from .services_profile import fetch_and_build_profile
from .session_store import SessionContext
from .upstream_urls import simworld_url, three_offer_url


class WriteValidationError(ValueError):
    pass


def money(value: object) -> Decimal:
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise WriteValidationError("金额无效") from exc
    if not amount.is_finite() or amount < 0:
        raise WriteValidationError("金额无效")
    return amount


def read_upstream(
    deps: RouteDeps, request: Request, ctx: SessionContext, account_id: str, url: str
) -> Any:
    account = deps.get_account_context(ctx, account_id)
    response = deps.make_3hk_request(
        request=request,
        ctx=ctx,
        method="GET",
        url=url,
        account_id=account_id,
        account_context=account,
    )
    if response is None or response.status_code != 200:
        raise WriteValidationError("无法核对上游资料，请刷新后重试")
    return response.json()


def require_subscription(
    deps: RouteDeps,
    request: Request,
    ctx: SessionContext,
    account_id: str,
    subscription_id: str | int | None,
) -> dict[str, Any]:
    result = fetch_and_build_profile(
        brands=deps.SUB_BRANDS,
        make_request=deps.make_3hk_request,
        request=request,
        ctx=ctx,
        req_ident=account_id,
        account_ctx=deps.get_account_context(ctx, account_id) or {},
        accounts=ctx.data.get("accounts", {}),
    )
    for sub in result["data"]["subscriptions"]:
        if subscription_id is not None and str(sub["subscriptionId"]) == str(
            subscription_id
        ):
            return dict(sub)
    raise WriteValidationError("订阅不属于当前账号或已失效")


def verify_payment(
    deps: RouteDeps,
    request: Request,
    ctx: SessionContext,
    account_id: str,
    body: PurchaseRequest | CmnPurchaseRequest,
    brand: str,
    total: Decimal,
) -> None:
    # Browser totals use IEEE-754 numbers; normalize only the sub-cent rounding
    # noise, never trust a client-supplied total instead of the live catalog.
    if abs(money(body.price) - total) > Decimal("0.0000001"):
        raise WriteValidationError("套餐价格已变化，请刷新后重新确认")
    txn = money(body.txnAmount)
    if txn > total:
        raise WriteValidationError("余额抵扣不能超过订单金额")
    if txn:
        if isinstance(body, PurchaseRequest) and body.new_line:
            raise WriteValidationError("新开号码不支持当前号码余额抵扣")
        wallet = read_upstream(
            deps,
            request,
            ctx,
            account_id,
            simworld_url(brand, "sim", str(body.subscriptionId), "WalletBalances"),
        )
        if txn > money(parse_wallet_balance(wallet)):
            raise WriteValidationError("可用余额不足，请刷新后重试")


def validate_purchase(
    deps: RouteDeps,
    request: Request,
    ctx: SessionContext,
    account_id: str,
    body: PurchaseRequest,
) -> str:
    if not body.items:
        raise WriteValidationError("购物车不能为空")
    if body.new_line:
        brand = str(
            (deps.get_account_context(ctx, account_id) or {}).get("sub_brand", "THREE")
        )
    else:
        brand = str(
            require_subscription(deps, request, ctx, account_id, body.subscriptionId)[
                "brand"
            ]
        )
    catalog = read_upstream(
        deps, request, ctx, account_id, three_offer_url(brand, "offer/getPlanOffers/")
    )
    offers = {str(offer["offerId"]): offer for offer in catalog.get("offers", [])}
    quantities = {}
    for item in body.items:
        quantities[item.offerId] = quantities.get(item.offerId, 0) + item.quantity
    if body.new_line:
        quantities[BASE_NEW_LINE_OFFER] = 1
    total = Decimal(0)
    for offer_id, quantity in quantities.items():
        offer = offers.get(offer_id)
        if offer is None or quantity > 99:
            raise WriteValidationError("套餐无效或数量超限，请刷新后重试")
        total += money(offer["offerPrice"]) * quantity
    verify_payment(deps, request, ctx, account_id, body, brand, total)
    return brand


def validate_cmn(
    deps: RouteDeps,
    request: Request,
    ctx: SessionContext,
    account_id: str,
    body: CmnPurchaseRequest,
) -> str:
    brand = str(
        require_subscription(deps, request, ctx, account_id, body.subscriptionId)[
            "brand"
        ]
    )
    offers = read_upstream(
        deps, request, ctx, account_id, simworld_url(brand, "offer/getCmnOffer")
    ).get("offers", [])
    offer = next((o for o in offers if str(o["offerId"]) == str(body.offerId)), None)
    if offer is None or body.selectedNumber is None:
        raise WriteValidationError("换号资格或号码无效，请重新查询")
    verify_payment(
        deps, request, ctx, account_id, body, brand, money(offer["offerPrice"])
    )
    return brand


def validate_transfer(
    deps: RouteDeps,
    request: Request,
    ctx: SessionContext,
    account_id: str,
    body: TransferRequest,
) -> str:
    sub = require_subscription(deps, request, ctx, account_id, body.subscriptionId)
    if (
        str(sub["mobile"]) != str(body.sourceMsisdn)
        or body.targetMsisdn is None
        or body.targetMsisdn == body.sourceMsisdn
        or body.amount is None
    ):
        raise WriteValidationError("转移来源或目标号码无效")
    for offer in sub["activeOffers"]:
        for usage in offer["usage"]:
            if str(usage["userOfferId"]) == str(body.userOfferId) and str(
                usage["balanceResourceId"]
            ) == str(body.balanceResourceId):
                amount = float(body.amount)
                if (
                    not usage["canTransfer"]
                    or usage["productFamily"] != body.productFamily
                    or usage["unit"] != body.unit
                    or not float(usage["minTransfer"])
                    <= amount
                    <= float(usage["remain"])
                ):
                    raise WriteValidationError("转移资源、单位或额度无效")
                return str(sub["brand"])
    raise WriteValidationError("资源不属于当前订阅")
