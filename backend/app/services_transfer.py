"""Transfer helpers: DTO offer selection and transfer payload assembly."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TypedDict


class ProductDataPayload(TypedDict):
    unit: str | None
    volume: float


class OfferProductPayload(TypedDict):
    balanceResourceId: int
    productId: object
    productData: ProductDataPayload


class TransferOfferItemPayload(TypedDict):
    offerId: object
    transferOfferId: object
    offerProduct: OfferProductPayload


class OrderSubscriptionPayload(TypedDict):
    msisdn: str
    subscriptionId: object
    volumeUpMsisdn: str
    lang: str
    offers: list[TransferOfferItemPayload]


class TranferOrderPayload(TypedDict):
    channel: str
    orderSubscription: OrderSubscriptionPayload


class TransferPayload(TypedDict):
    # Deliberate upstream field name (typo preserved).
    tranferOrder: TranferOrderPayload


def require_mapping_list(value: object) -> list[Mapping[str, object]]:
    """Require a list of mappings; malformed containers raise TypeError."""
    if not isinstance(value, list):
        raise TypeError(
            f"expected list of mappings, got {type(value).__name__}"
        )
    result: list[Mapping[str, object]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise TypeError(
                f"sequence element {index} must be a mapping, got {type(item).__name__}"
            )
        result.append(item)
    return result


def coerce_request_int(value: str | int | None) -> int:
    """int() for transfer request fields; None raises TypeError like bare int(None)."""
    if value is None:
        raise TypeError(
            "int() argument must be a string, a bytes-like object or a real number, not 'NoneType'"
        )
    return int(value)


def coerce_request_float(value: str | int | float | None) -> float:
    """float() for transfer request fields; None raises TypeError like bare float(None)."""
    if value is None:
        raise TypeError(
            "float() argument must be a string or a real number, not 'NoneType'"
        )
    return float(value)


def select_dto_offer(offers: object) -> Mapping[str, object] | None:
    """Return the first DTO offer, or None when the list has no DTO entry."""
    for offer in require_mapping_list(offers):
        if offer.get("offerSubType") == "DTO":
            return offer
    return None


def select_transfer_product_id(
    dto: Mapping[str, object],
    product_family: str | None,
) -> object:
    """Pick productId matching productFamily, else first product."""
    products = require_mapping_list(dto["products"])
    return next(
        (
            p["productId"]
            for p in products
            if p.get("productFamily") == product_family
        ),
        products[0]["productId"],
    )


def build_transfer_payload(
    *,
    dto_offer_id: object,
    target_product_id: object,
    source_msisdn: str,
    subscription_id: object,
    target_msisdn: str,
    user_offer_id: object,
    balance_resource_id: int,
    unit: str | None,
    amount: float,
) -> TransferPayload:
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
    offers: Sequence[Mapping[str, object]],
    *,
    product_family: str | None,
    source_msisdn: str,
    subscription_id: object,
    target_msisdn: str,
    user_offer_id: object,
    balance_resource_id: int,
    unit: str | None,
    amount: float,
) -> TransferPayload | None:
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
