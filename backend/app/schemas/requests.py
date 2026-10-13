"""Pydantic request models for JSON write endpoints."""

from __future__ import annotations

import math
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SafeId = Annotated[
    str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
]
Money = Annotated[float, Field(ge=0, le=1_000_000, allow_inf_nan=False)]
PaymentType = Literal["ALCN", "ALHK", "WECHAT", "MPGS"]


def valid_number(value: str | int | None) -> str | int | None:
    if value is not None and (
        not str(value).isascii()
        or not str(value).isdigit()
        or not 8 <= len(str(value)) <= 15
    ):
        raise ValueError("invalid phone number")
    return value


class PurchaseItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    offerId: SafeId
    quantity: int = Field(default=1, ge=1, le=99)


class PurchaseRequest(BaseModel):
    """Body for POST /api/purchase."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    account_id: str | None = Field(default=None, max_length=254)
    subscriptionId: SafeId | None = None
    new_line: bool = False
    txnAmount: Money = 0
    price: Money = 0
    paymentType: PaymentType = "ALCN"
    items: list[PurchaseItem] = Field(default_factory=list, max_length=100)


class TransferRequest(BaseModel):
    """Body for POST /api/sim/transfer."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    account_id: str = Field(default="", max_length=254)
    subscriptionId: SafeId | int | None = None
    productFamily: Literal["DATA", "VOICE"] | None = None
    sourceMsisdn: str | int | None = None
    targetMsisdn: str | int | None = None
    userOfferId: str | int | None = None
    balanceResourceId: str | int | None = None
    unit: (
        Literal[
            "MB",
            "GB",
            "KB",
            "Byte",
            "Minutes",
            "Minute",
            "Min",
            "Mins",
            "Seconds",
            "Second",
            "Sec",
        ]
        | None
    ) = None
    amount: str | int | float | None = None

    _phone = field_validator("sourceMsisdn", "targetMsisdn")(valid_number)

    @field_validator("amount")
    @classmethod
    def valid_amount(cls, value):
        if value is not None and (
            not math.isfinite(float(value)) or not 0 < float(value) <= 1_000_000_000
        ):
            raise ValueError("invalid transfer amount")
        return value

    @field_validator("balanceResourceId")
    @classmethod
    def valid_resource(cls, value):
        if value is not None and (isinstance(value, bool) or int(value) < 0):
            raise ValueError("invalid resource ID")
        return value


class CmnPurchaseRequest(BaseModel):
    """Body for POST /api/cmn/purchase."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    account_id: str = Field(default="", max_length=254)
    subscriptionId: SafeId | int | None = None
    txnAmount: Money = 0
    price: Money = 0
    paymentType: PaymentType = "ALCN"
    selectedNumber: str | int | None = None
    offerId: str | int | None = None

    _phone = field_validator("selectedNumber")(valid_number)


class CheckUserRequest(BaseModel):
    """Body for POST /api/check-user."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    identifier: str = Field(min_length=1, max_length=254)


class SendOtpRequest(BaseModel):
    """Body for POST /api/send-otp."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    auth_code: str | None = Field(default=None, max_length=512)
    identifier: str = Field(default="", max_length=254)
