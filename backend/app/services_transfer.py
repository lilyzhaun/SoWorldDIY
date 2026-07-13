"""Transfer helpers: DTO offer selection and transfer payload assembly."""

from __future__ import annotations

from typing import Any


def select_dto_offer(offers: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the first DTO offer, or None if unsupported."""
    return next((o for o in offers if o.get("offerSubType") == "DTO"), None)


def select_transfer_product_id(
    dto: dict[str, Any],
    product_family: str,
) -> Any:
    """Pick productId matching productFamily, else first product."""
    return next(
        (
            p["productId"]
            for p in dto.get("products", [])
            if p.get("productFamily") == product_family
        ),
        dto["products"][0]["productId"],
    )


def build_transfer_payload(
    *,
    dto_offer_id: Any,
    target_product_id: Any,
    source_msisdn: str,
    subscription_id: Any,
    target_msisdn: str,
    user_offer_id: Any,
    balance_resource_id: int,
    unit: str,
    amount: float,
) -> dict[str, Any]:
    """Assemble the upstream transfer body (keeps deliberate tranferOrder typo)."""
    return {
        "tranferOrder": {
            "channel": "WEB",
            "orderSubscription": {
                "msisdn": source_msisdn,
                "subscriptionId": subscription_id,
                "volumeUpMsisdn": target_msisdn,
                "lang": "tc",
                "offers": [
                    {
                        "offerId": dto_offer_id,
                        "transferOfferId": user_offer_id,
                        "offerProduct": {
                            "balanceResourceId": balance_resource_id,
                            "productId": target_product_id,
                            "productData": {
                                "unit": unit,
                                "volume": amount,
                            },
                        },
                    }
                ],
            },
        }
    }


def assemble_transfer_payload(
    offers: list[dict[str, Any]],
    *,
    product_family: str,
    source_msisdn: str,
    subscription_id: Any,
    target_msisdn: str,
    user_offer_id: Any,
    balance_resource_id: int,
    unit: str,
    amount: float,
) -> dict[str, Any] | None:
    """Select DTO offer and build payload; None when transfer is unsupported."""
    dto = select_dto_offer(offers)
    if not dto:
        return None
    target_product_id = select_transfer_product_id(dto, product_family)
    return build_transfer_payload(
        dto_offer_id=dto["offerId"],
        target_product_id=target_product_id,
        source_msisdn=source_msisdn,
        subscription_id=subscription_id,
        target_msisdn=target_msisdn,
        user_offer_id=user_offer_id,
        balance_resource_id=balance_resource_id,
        unit=unit,
        amount=amount,
    )
