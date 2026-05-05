"""Stripe helper utilities.

All functions are no-ops / return None when STRIPE_SECRET_KEY is not set,
so the app degrades gracefully in environments without Stripe configured.
"""

import os
from typing import Optional

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_CREATOR_PRICE_ID = os.environ.get("STRIPE_CREATOR_PRICE_ID", "")
STRIPE_PRO_PRICE_ID = os.environ.get("STRIPE_PRO_PRICE_ID", "")


def get_stripe_client():
    """Return the configured stripe module, or None if not available."""
    if not STRIPE_SECRET_KEY:
        return None
    try:
        import stripe  # type: ignore
        stripe.api_key = STRIPE_SECRET_KEY
        return stripe
    except ImportError:
        return None


def create_customer(user) -> Optional[str]:
    """Create a Stripe Customer for *user* and return the customer ID."""
    stripe = get_stripe_client()
    if stripe is None:
        return None
    customer = stripe.Customer.create(
        email=user.email,
        name=user.name,
        metadata={"user_id": user.id},
    )
    return customer.id


def create_checkout_session(user, plan: str, success_url: str, cancel_url: str) -> Optional[str]:
    """Create a Stripe Checkout session and return the session URL.

    *plan* must be "creator" or "pro".
    Returns None if Stripe is not configured or the price ID is missing.
    """
    stripe = get_stripe_client()
    if stripe is None:
        return None

    price_id = STRIPE_CREATOR_PRICE_ID if plan == "creator" else STRIPE_PRO_PRICE_ID
    if not price_id:
        return None

    # Ensure the customer exists in Stripe
    customer_id = user.stripe_customer_id
    if not customer_id:
        customer_id = create_customer(user)

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        mode="subscription",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"user_id": user.id},
        subscription_data={"metadata": {"user_id": user.id}},
    )
    return session.url


def get_subscription(subscription_id: str):
    """Retrieve a Stripe Subscription object, or None on failure."""
    stripe = get_stripe_client()
    if stripe is None:
        return None
    try:
        return stripe.Subscription.retrieve(subscription_id)
    except Exception:
        return None


def cancel_subscription(subscription_id: str) -> bool:
    """Cancel a subscription at period end. Returns True on success."""
    stripe = get_stripe_client()
    if stripe is None:
        return False
    try:
        stripe.Subscription.modify(subscription_id, cancel_at_period_end=True)
        return True
    except Exception:
        return False
