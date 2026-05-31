import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import (
    AttemptStatus,
    Customer,
    Payment,
    PaymentAttempt,
    PaymentStatus,
    get_db,
)
from app.services.retry_engine import execute_retry, schedule_retry

router = APIRouter(prefix="/api", tags=["api"])


class SimulateFailureRequest(BaseModel):
    email: str = "demo@example.com"
    amount_cents: int = 2999
    decline_code: str = "insufficient_funds"
    stripe_customer_id: str | None = None


class SimulateFailureResponse(BaseModel):
    payment_id: int
    status: str
    decline_code: str
    decline_category: str | None
    next_retry_at: datetime | None
    message: str


class PaymentSummary(BaseModel):
    id: int
    stripe_payment_intent_id: str
    customer_email: str
    amount_cents: int
    amount_dollars: float
    currency: str
    status: str
    decline_code: str | None
    decline_category: str | None
    retry_count: int
    next_retry_at: datetime | None
    recovered_at: datetime | None
    created_at: datetime


class AttemptSummary(BaseModel):
    attempt_number: int
    status: str
    decline_code: str | None
    scheduled_at: datetime | None
    executed_at: datetime | None
    notes: str | None


class PaymentDetail(PaymentSummary):
    attempts: list[AttemptSummary]


class MetricsResponse(BaseModel):
    total_failed: int
    total_recovered: int
    total_abandoned: int
    total_retry_scheduled: int
    recovery_rate_percent: float
    failed_amount_cents: int
    recovered_amount_cents: int
    recovered_amount_dollars: float
    revenue_at_risk_dollars: float


def _payment_to_summary(payment: Payment) -> PaymentSummary:
    return PaymentSummary(
        id=payment.id,
        stripe_payment_intent_id=payment.stripe_payment_intent_id,
        customer_email=payment.customer.email,
        amount_cents=payment.amount_cents,
        amount_dollars=payment.amount_cents / 100,
        currency=payment.currency,
        status=payment.status.value,
        decline_code=payment.decline_code,
        decline_category=payment.decline_category.value if payment.decline_category else None,
        retry_count=payment.retry_count,
        next_retry_at=payment.next_retry_at,
        recovered_at=payment.recovered_at,
        created_at=payment.created_at,
    )


@router.get("/metrics", response_model=MetricsResponse)
def get_metrics(db: Session = Depends(get_db)):
    failed_statuses = [
        PaymentStatus.FAILED,
        PaymentStatus.RETRY_SCHEDULED,
        PaymentStatus.RETRYING,
        PaymentStatus.ABANDONED,
    ]

    total_failed = db.query(Payment).filter(Payment.status.in_(failed_statuses)).count()
    total_recovered = db.query(Payment).filter(Payment.status == PaymentStatus.RECOVERED).count()
    total_abandoned = db.query(Payment).filter(Payment.status == PaymentStatus.ABANDONED).count()
    total_retry_scheduled = (
        db.query(Payment).filter(Payment.status == PaymentStatus.RETRY_SCHEDULED).count()
    )

    failed_amount = (
        db.query(func.coalesce(func.sum(Payment.amount_cents), 0))
        .filter(Payment.status.in_(failed_statuses + [PaymentStatus.ABANDONED]))
        .scalar()
    )
    recovered_amount = (
        db.query(func.coalesce(func.sum(Payment.amount_cents), 0))
        .filter(Payment.status == PaymentStatus.RECOVERED)
        .scalar()
    )

    attempted_recovery = total_recovered + total_abandoned
    recovery_rate = (total_recovered / attempted_recovery * 100) if attempted_recovery > 0 else 0.0

    at_risk = (
        db.query(func.coalesce(func.sum(Payment.amount_cents), 0))
        .filter(Payment.status.in_([PaymentStatus.RETRY_SCHEDULED, PaymentStatus.RETRYING]))
        .scalar()
    )

    return MetricsResponse(
        total_failed=total_failed,
        total_recovered=total_recovered,
        total_abandoned=total_abandoned,
        total_retry_scheduled=total_retry_scheduled,
        recovery_rate_percent=round(recovery_rate, 1),
        failed_amount_cents=failed_amount,
        recovered_amount_cents=recovered_amount,
        recovered_amount_dollars=recovered_amount / 100,
        revenue_at_risk_dollars=at_risk / 100,
    )


@router.get("/payments", response_model=list[PaymentSummary])
def list_payments(status: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Payment).join(Customer).order_by(Payment.created_at.desc())
    if status:
        try:
            query = query.filter(Payment.status == PaymentStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    payments = query.limit(100).all()
    return [_payment_to_summary(p) for p in payments]


@router.get("/payments/{payment_id}", response_model=PaymentDetail)
def get_payment(payment_id: int, db: Session = Depends(get_db)):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    summary = _payment_to_summary(payment)
    attempts = [
        AttemptSummary(
            attempt_number=a.attempt_number,
            status=a.status.value,
            decline_code=a.decline_code,
            scheduled_at=a.scheduled_at,
            executed_at=a.executed_at,
            notes=a.notes,
        )
        for a in payment.attempts
    ]
    return PaymentDetail(**summary.model_dump(), attempts=attempts)


@router.post("/simulate/failure", response_model=SimulateFailureResponse)
def simulate_failure(body: SimulateFailureRequest, db: Session = Depends(get_db)):
    """Demo endpoint: simulate a failed payment and trigger retry scheduling."""
    stripe_cid = body.stripe_customer_id or f"cus_demo_{body.email.replace('@', '_')}"

    customer = db.query(Customer).filter(Customer.stripe_customer_id == stripe_cid).first()
    if not customer:
        customer = Customer(stripe_customer_id=stripe_cid, email=body.email)
        db.add(customer)
        db.flush()

    pi_id = f"pi_sim_{datetime.utcnow().timestamp()}"

    payment = Payment(
        stripe_payment_intent_id=pi_id,
        customer_id=customer.id,
        amount_cents=body.amount_cents,
        status=PaymentStatus.FAILED,
        decline_code=body.decline_code,
    )
    db.add(payment)
    db.flush()

    payment = schedule_retry(db, payment, body.decline_code)

    return SimulateFailureResponse(
        payment_id=payment.id,
        status=payment.status.value,
        decline_code=payment.decline_code or body.decline_code,
        decline_category=payment.decline_category.value if payment.decline_category else None,
        next_retry_at=payment.next_retry_at,
        message=f"Payment failed with '{body.decline_code}'. "
        + (
            f"Retry scheduled for {payment.next_retry_at.isoformat()}"
            if payment.next_retry_at
            else "No retry scheduled (hard decline or max retries reached)"
        ),
    )


@router.post("/payments/{payment_id}/retry")
def trigger_retry(payment_id: int, success: bool = False, db: Session = Depends(get_db)):
    """Manually trigger a retry (demo: pass success=true to simulate recovery)."""
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.status not in (PaymentStatus.RETRY_SCHEDULED, PaymentStatus.FAILED):
        raise HTTPException(
            status_code=400,
            detail=f"Payment status '{payment.status.value}' cannot be retried",
        )

    payment = execute_retry(db, payment, success=success)
    return _payment_to_summary(payment)


@router.get("/decline-codes")
def list_decline_codes():
    from app.services.decline_classifier import DECLINE_MAP

    return {
        code: {
            "type": info.decline_type.value,
            "should_retry": info.should_retry,
            "max_retries": info.max_retries,
            "intervals_hours": info.retry_intervals_hours,
            "reason": info.reason,
        }
        for code, info in DECLINE_MAP.items()
    }
