import json

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Customer, Payment, PaymentStatus, WebhookEvent, get_db
from app.deps import get_or_create_default_workspace
from app.services import activity as activity_svc
from app.services.retry_engine import schedule_retry

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

if settings.stripe_secret_key:
    stripe.api_key = settings.stripe_secret_key


def _get_or_create_customer(
    db: Session, workspace_id: int, stripe_customer_id: str, email: str
) -> Customer:
    customer = (
        db.query(Customer)
        .filter(
            Customer.workspace_id == workspace_id,
            Customer.stripe_customer_id == stripe_customer_id,
        )
        .first()
    )
    if not customer:
        customer = Customer(
            workspace_id=workspace_id,
            stripe_customer_id=stripe_customer_id,
            email=email,
        )
        db.add(customer)
        db.flush()
    return customer


def _handle_payment_failed(db: Session, workspace_id: int, event_data: dict) -> None:
    obj = event_data.get("object", {})
    pi_id = obj.get("id")
    if not pi_id:
        return

    existing = db.query(Payment).filter(Payment.stripe_payment_intent_id == pi_id).first()
    if existing:
        return

    amount = obj.get("amount", 0)
    currency = obj.get("currency", "usd")
    last_error = obj.get("last_payment_error") or {}
    decline_code = last_error.get("decline_code") or last_error.get("code")

    customer_id = obj.get("customer")
    email = "unknown@stripe.webhook"
    if customer_id and settings.stripe_secret_key:
        try:
            stripe_customer = stripe.Customer.retrieve(customer_id)
            email = stripe_customer.get("email") or email
        except stripe.StripeError:
            pass

    customer = _get_or_create_customer(
        db, workspace_id, customer_id or f"anon_{pi_id}", email
    )

    payment = Payment(
        workspace_id=workspace_id,
        stripe_payment_intent_id=pi_id,
        customer_id=customer.id,
        amount_cents=amount,
        currency=currency,
        status=PaymentStatus.FAILED,
        decline_code=decline_code,
    )
    db.add(payment)
    db.flush()
    activity_svc.payment_failed(
        db, workspace_id, payment.id, email, amount, decline_code
    )
    schedule_retry(db, payment, decline_code)


def _handle_invoice_payment_failed(db: Session, workspace_id: int, event_data: dict) -> None:
    obj = event_data.get("object", {})
    pi_id = obj.get("payment_intent")
    if not pi_id:
        return

    existing = db.query(Payment).filter(Payment.stripe_payment_intent_id == pi_id).first()
    if existing:
        return

    amount = obj.get("amount_due", 0)
    currency = obj.get("currency", "usd")
    customer_id = obj.get("customer")
    email = obj.get("customer_email") or "unknown@stripe.webhook"

    customer = _get_or_create_customer(
        db, workspace_id, customer_id or f"anon_{pi_id}", email
    )

    payment = Payment(
        workspace_id=workspace_id,
        stripe_payment_intent_id=pi_id,
        stripe_invoice_id=obj.get("id"),
        customer_id=customer.id,
        amount_cents=amount,
        currency=currency,
        status=PaymentStatus.FAILED,
        decline_code="card_declined",
    )
    db.add(payment)
    db.flush()
    activity_svc.payment_failed(db, workspace_id, payment.id, email, amount, "card_declined")
    schedule_retry(db, payment, "card_declined")


@router.post("/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if settings.stripe_webhook_secret:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.stripe_webhook_secret
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid payload")
        except stripe.SignatureVerificationError:
            raise HTTPException(status_code=400, detail="Invalid signature")
    else:
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON")

    event_id = event.get("id", f"dev_{hash(payload)}")
    event_type = event.get("type", "")

    existing_event = (
        db.query(WebhookEvent).filter(WebhookEvent.stripe_event_id == event_id).first()
    )
    if existing_event:
        return {"status": "already_processed"}

    workspace = get_or_create_default_workspace(db)

    webhook_record = WebhookEvent(
        workspace_id=workspace.id,
        stripe_event_id=event_id,
        event_type=event_type,
        payload=payload.decode("utf-8", errors="replace"),
        processed=False,
    )
    db.add(webhook_record)

    data = event.get("data", {})

    if event_type == "payment_intent.payment_failed":
        _handle_payment_failed(db, workspace.id, data)
    elif event_type == "invoice.payment_failed":
        _handle_invoice_payment_failed(db, workspace.id, data)

    webhook_record.processed = True
    db.commit()

    return {"status": "ok", "event_type": event_type}
