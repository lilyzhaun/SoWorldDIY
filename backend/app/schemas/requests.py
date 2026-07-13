"""Pydantic request models for JSON write endpoints."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PurchaseItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    offerId: str
    quantity: int = 1


class PurchaseRequest(BaseModel):
    """Body for POST /api/purchase."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    account_id: str | None = None
    subscriptionId: str | None = None
    new_line: bool = False
    txnAmount: float = 0
    price: float = 0
    paymentType: str = "ALCN"
    items: list[PurchaseItem] = Field(default_factory=list)


class TransferRequest(BaseModel):
    """Body for POST /api/sim/transfer."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    account_id: str = ""
    subscriptionId: str | int | None = None
    productFamily: str | None = None
    sourceMsisdn: str | int | None = None
    targetMsisdn: str | int | None = None
    userOfferId: str | int | None = None
    balanceResourceId: str | int | None = None
    unit: str | None = None
    amount: str | int | float | None = None


class CmnPurchaseRequest(BaseModel):
    """Body for POST /api/cmn/purchase."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    account_id: str = ""
    subscriptionId: str | int | None = None
    txnAmount: float = 0
    price: float = 0
    paymentType: str = "ALCN"
    selectedNumber: str | int | None = None
    offerId: str | int | None = None


class CheckUserRequest(BaseModel):
    """Body for POST /api/check-user."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    identifier: str


class SendOtpRequest(BaseModel):
    """Body for POST /api/send-otp."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    auth_code: str | None = None
    identifier: str = ""
