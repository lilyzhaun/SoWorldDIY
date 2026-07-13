from app.upstream_urls import (
    SIMWORLD_API_BASE,
    SIMWORLD_PAYMENT_FINISHED,
    SIMWORLD_WEB_MAIN,
    THREE_ACCOUNT_BASE,
    THREE_EXISTING_CUST_DIPPING,
    simworld_url,
    three_offer_url,
)


def test_simworld_url_joins_brand_and_path() -> None:
    assert (
        simworld_url("SOSIM", "sim", "sub-1", "WalletBalances")
        == f"{SIMWORLD_API_BASE}/SOSIM/sim/sub-1/WalletBalances"
    )


def test_simworld_url_preserves_trailing_slash_segment() -> None:
    assert (
        simworld_url("THREE", "user/login/") == f"{SIMWORLD_API_BASE}/THREE/user/login/"
    )
    assert (
        simworld_url("SOSIM", "pmt/purchase/createPurchase/")
        == f"{SIMWORLD_API_BASE}/SOSIM/pmt/purchase/createPurchase/"
    )


def test_three_offer_url_plan_offers() -> None:
    assert (
        three_offer_url("THREE", "offer/getPlanOffers/")
        == f"{THREE_ACCOUNT_BASE}/THREE/offer/getPlanOffers/"
    )


def test_static_url_constants() -> None:
    assert SIMWORLD_WEB_MAIN == "https://simworld.net/SIMworld/main/tc"
    assert (
        SIMWORLD_PAYMENT_FINISHED
        == "https://simworld.net/SIMworld/main/checkout/payment/finished/"
    )
    assert (
        THREE_EXISTING_CUST_DIPPING
        == "https://www.three.com.hk/account-pro/user/existingCustDipping"
    )
