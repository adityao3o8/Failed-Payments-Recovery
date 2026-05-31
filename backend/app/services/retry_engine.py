from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.database import (
    AttemptStatus,
    DeclineCategory,
    Payment,
    PaymentAttempt,
    PaymentStatus,
)
from app.services.decline_classifier import DeclineType, classify_decline


def _map_decline_type_to_category(decline_type: DeclineType) -> DeclineCategory:
    mapping = {
        DeclineType.HARD: DeclineCategory.HARD,
        DeclineType.SOFT: DeclineCategory.SOFT,
        DeclineType.RETRYABLE: DeclineCategory.RETRYABLE,
        DeclineType.UNKNOWN: DeclineCategory.UNKNOWN,
    }
    return mapping[decline_type]


def schedule_retry(db: Session, payment: Payment, decline_code: str | None) -> Payment:
    """Evaluate decline and schedule next retry if appropriate."""
    info = classify_decline(decline_code)

    payment.decline_code = decline_code or info.code
    payment.decline_category = _map_decline_type_to_category(info.decline_type)
    payment.max_retries = min(info.max_retries, settings.max_retries)

    # Record the failed attempt
    attempt_number = payment.retry_count + 1
    attempt = PaymentAttempt(
        payment_id=payment.id,
        attempt_number=attempt_number,
        status=AttemptStatus.FAILED,
        decline_code=decline_code,
        executed_at=datetime.utcnow(),
        notes=info.reason,
    )
    db.add(attempt)

    if not info.should_retry or payment.retry_count >= payment.max_retries:
        payment.status = PaymentStatus.ABANDONED
        payment.next_retry_at = None
        db.commit()
        db.refresh(payment)
        return payment

    # Calculate next retry time from interval schedule
    interval_index = min(payment.retry_count, len(info.retry_intervals_hours) - 1)
    hours_until_retry = info.retry_intervals_hours[interval_index]
    next_retry = datetime.utcnow() + timedelta(hours=hours_until_retry)

    payment.status = PaymentStatus.RETRY_SCHEDULED
    payment.retry_count += 1
    payment.next_retry_at = next_retry

    scheduled_attempt = PaymentAttempt(
        payment_id=payment.id,
        attempt_number=attempt_number + 1,
        status=AttemptStatus.SCHEDULED,
        decline_code=None,
        scheduled_at=next_retry,
        notes=f"Scheduled retry in {hours_until_retry}h ({info.reason})",
    )
    db.add(scheduled_attempt)
    db.commit()
    db.refresh(payment)
    return payment


def execute_retry(db: Session, payment: Payment, success: bool = False) -> Payment:
    """Simulate or execute a retry attempt."""
    payment.status = PaymentStatus.RETRYING

    scheduled = (
        db.query(PaymentAttempt)
        .filter(
            PaymentAttempt.payment_id == payment.id,
            PaymentAttempt.status == AttemptStatus.SCHEDULED,
        )
        .order_by(PaymentAttempt.attempt_number.desc())
        .first()
    )

    if scheduled:
        scheduled.status = AttemptStatus.SUCCEEDED if success else AttemptStatus.FAILED
        scheduled.executed_at = datetime.utcnow()

    if success:
        payment.status = PaymentStatus.RECOVERED
        payment.recovered_at = datetime.utcnow()
        payment.next_retry_at = None
    else:
        schedule_retry(db, payment, payment.decline_code)

    db.commit()
    db.refresh(payment)
    return payment


def get_due_retries(db: Session) -> list[Payment]:
    """Return payments scheduled for retry that are past due."""
    now = datetime.utcnow()
    return (
        db.query(Payment)
        .filter(
            Payment.status == PaymentStatus.RETRY_SCHEDULED,
            Payment.next_retry_at <= now,
        )
        .all()
    )
