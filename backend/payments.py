import os
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel
from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout,
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    CheckoutStatusResponse,
)

from auth import db, get_current_user

logger = logging.getLogger(__name__)
payments_router = APIRouter(prefix="/api/payments", tags=["payments"])

# Server-side defined packages ONLY (never trust frontend amounts)
PACKAGES = {
    "pro_monthly": {"amount": 4.99, "currency": "gbp", "days": 30, "label": "Pro Monthly"},
}


class CheckoutInput(BaseModel):
    package_id: str
    origin_url: str


def _stripe(request: Request) -> StripeCheckout:
    api_key = os.environ["STRIPE_API_KEY"]
    host_url = str(request.base_url)
    webhook_url = f"{host_url}api/webhook/stripe"
    return StripeCheckout(api_key=api_key, webhook_url=webhook_url)


async def _activate_pro(user_id: str, days: int):
    until = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
    from bson import ObjectId
    await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"pro_until": until}})
    return until


@payments_router.get("/packages")
async def packages():
    return [{"id": k, "amount": v["amount"], "currency": v["currency"], "label": v["label"]}
            for k, v in PACKAGES.items()]


@payments_router.post("/checkout")
async def create_checkout(payload: CheckoutInput, request: Request, user: dict = Depends(get_current_user)):
    pkg = PACKAGES.get(payload.package_id)
    if not pkg:
        raise HTTPException(status_code=400, detail="Invalid package")

    origin = payload.origin_url.rstrip("/")
    success_url = f"{origin}/dashboard?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/upgrade"

    stripe = _stripe(request)
    metadata = {
        "user_id": str(user["_id"]),
        "email": user["email"],
        "package_id": payload.package_id,
    }
    req = CheckoutSessionRequest(
        amount=float(pkg["amount"]),
        currency=pkg["currency"],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata,
    )
    session: CheckoutSessionResponse = await stripe.create_checkout_session(req)

    await db.payment_transactions.insert_one({
        "session_id": session.session_id,
        "user_id": str(user["_id"]),
        "email": user["email"],
        "package_id": payload.package_id,
        "amount": pkg["amount"],
        "currency": pkg["currency"],
        "payment_status": "initiated",
        "status": "pending",
        "processed": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"url": session.url, "session_id": session.session_id}


@payments_router.get("/status/{session_id}")
async def checkout_status(session_id: str, request: Request, user: dict = Depends(get_current_user)):
    txn = await db.payment_transactions.find_one({"session_id": session_id})
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    stripe = _stripe(request)
    status: CheckoutStatusResponse = await stripe.get_checkout_status(session_id)

    update = {"payment_status": status.payment_status, "status": status.status}
    if status.payment_status == "paid" and not txn.get("processed"):
        update["processed"] = True
        pkg = PACKAGES.get(txn["package_id"], {"days": 30})
        pro_until = await _activate_pro(txn["user_id"], pkg["days"])
        update["pro_until"] = pro_until
    await db.payment_transactions.update_one({"session_id": session_id}, {"$set": update})

    return {"payment_status": status.payment_status, "status": status.status}


webhook_router = APIRouter(tags=["payments"])


@webhook_router.post("/api/webhook/stripe")
async def stripe_webhook(request: Request):
    body = await request.body()
    sig = request.headers.get("Stripe-Signature")
    stripe = _stripe(request)
    try:
        event = await stripe.handle_webhook(body, sig)
    except Exception as e:
        logger.warning(f"Webhook error: {e}")
        raise HTTPException(status_code=400, detail="Invalid webhook")

    if event.payment_status == "paid" and event.session_id:
        txn = await db.payment_transactions.find_one({"session_id": event.session_id})
        if txn and not txn.get("processed"):
            pkg = PACKAGES.get(txn["package_id"], {"days": 30})
            pro_until = await _activate_pro(txn["user_id"], pkg["days"])
            await db.payment_transactions.update_one(
                {"session_id": event.session_id},
                {"$set": {"processed": True, "payment_status": "paid",
                          "status": "complete", "pro_until": pro_until}},
            )
    return {"received": True}
