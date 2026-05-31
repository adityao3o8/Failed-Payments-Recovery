import hashlib
import hmac
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Customer, Payment, PaymentRail, PaymentStatus, WebhookEvent, get_db
from app.deps import get_or_create_default_workspace
from app.services import activity as activity_svc
from app.services.retry_engine import schedule_retry

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _verify_razorpay_signature(body: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _get_or_create_customer(
    db: Session,
    workspace_id: int,
    razorpay_customer_id: str,
    email: str,
    upi_vpa: str | None = None,
) -> Customer:
    customer = (
        db.query(Customer)
        .filter(
            Customer.workspace_id == workspace_id,
            Customer.stripe_customer_id == razorpay_customer_id,
        )
        .first()
    )
    if not customer:
        customer = Customer(
            workspace_id=workspace_id,
            stripe_customer_id=razorpay_customer_id,
            email=email,
            upi_vpa=upi_vpa,
        )
        db.add(customer)
        db.flush()
    elif upi_vpa and not customer.upi_vpa:
        customer.upi_vpa = upi_vpa
    return customer


def _handle_payment_failed(db: Session, workspace_id: int, payload: dict) -> None:
    entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    if not entity:
        entity = payload.get("payload", {}).get("entity", {})

    payment_id = entity.get("id")
    if not payment_id:
        return

    existing = (
        db.query(Payment)
        .filter(Payment.stripe_payment_intent_id == f"rzp_{payment_id}")
        .first()
    )
    if existing:
        return

    amount = entity.get("amount", 0)
    currency = entity.get("currency", "inr")
    error_reason = entity.get("error_reason") or entity.get("error_code") or "bank_declined"
    email = entity.get("email") or "unknown@razorpay.webhook"
    customer_id = entity.get("customer_id") or f"cust_{payment_id}"
    vpa = entity.get("vpa") or entity.get("upi", {}).get("vpa")

    customer = _get_or_create_customer(db, workspace_id, customer_id, email, vpa)

    payment = Payment(
        workspace_id=workspace_id,
        stripe_payment_intent_id=f"rzp_{payment_id}",
        customer_id=customer.id,
        payment_rail=PaymentRail.UPI,
        amount_cents=amount,
        currency=currency,
        status=PaymentStatus.FAILED,
        decline_code=error_reason,
    )
    db.add(payment)
    db.flush()
    activity_svc.payment_failed(
        db, workspace_id, payment.id, email, amount, error_reason
    )
    schedule_retry(db, payment, error_reason)


def _handle_subscription_charge_failed(db: Session, workspace_id: int, payload: dict) -> None:
    """UPI AutoPay subscription debit failure."""
    entity = payload.get("payload", {}).get("subscription", {}).get("entity", {})
    payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})

    payment_id = payment_entity.get("id") or f"sub_{entity.get('id', 'unknown')}"
    existing = (
        db.query(Payment)
        .filter(Payment.stripe_payment_intent_id == f"rzp_{payment_id}")
        .first()
    )
    if existing:
        return

    amount = payment_entity.get("amount") or entity.get("charge_at", 0)
    if isinstance(amount, str):
        amount = 0
    error_reason = (
        payment_entity.get("error_reason")
        or "upi_autopay_mandate_paused"
    )
    email = payment_entity.get("email") or "subscriber@razorpay.webhook"
    customer_id = payment_entity.get("customer_id") or entity.get("customer_id", f"cust_{payment_id}")

    customer = _get_or_create_customer(db, workspace_id, customer_id, email)
    payment = Payment(
        workspace_id=workspace_id,
        stripe_payment_intent_id=f"rzp_{payment_id}",
        customer_id=customer.id,
        payment_rail=PaymentRail.UPI,
        amount_cents=amount if amount else 49900,
        currency="inr",
        status=PaymentStatus.FAILED,
        decline_code=error_reason,
    )
    db.add(payment)
    db.flush()
    activity_svc.payment_failed(
        db, workspace_id, payment.id, email, payment.amount_cents, error_reason
    )
    schedule_retry(db, payment, error_reason)


@router.post("/razorpay")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")

    webhook_secret = getattr(settings, "razorpay_webhook_secret", "") or ""
    if webhook_secret and signature:
        if not _verify_razorpay_signature(body, signature, webhook_secret):
            raise HTTPException(status_code=400, detail="Invalid Razorpay signature")

    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_id = event.get("event", "") + "_" + str(event.get("created_at", hash(body)))
    event_type = event.get("event", "")

    existing = db.query(WebhookEvent).filter(WebhookEvent.stripe_event_id == event_id).first()
    if existing:
        return {"status": "already_processed"}

    workspace = get_or_create_default_workspace(db)
    db.add(
        WebhookEvent(
            workspace_id=workspace.id,
            stripe_event_id=event_id,
            event_type=event_type,
            payload=body.decode("utf-8", errors="replace"),
        )
    )

    if event_type == "payment.failed":
        _handle_payment_failed(db, workspace.id, event)
    elif event_type in ("subscription.charged.failed", "payment.failed"):
        _handle_subscription_charge_failed(db, workspace.id, event)

    db.commit()
    return {"status": "ok", "event": event_type}
