"""Product-level activity logging for the Recover dashboard."""

from sqlalchemy.orm import Session

from app.deps import log_activity


def payment_failed(
    db: Session,
    workspace_id: int,
    payment_id: int,
    customer_email: str,
    amount_cents: int,
    decline_code: str | None,
) -> None:
    amount = amount_cents / 100
    log_activity(
        db,
        workspace_id,
        "payment_failed",
        f"Payment failed — ${amount:.2f}",
        f"{customer_email} · decline: {decline_code or 'unknown'}",
        payment_id,
    )


def retry_scheduled(
    db: Session,
    workspace_id: int,
    payment_id: int,
    customer_email: str,
    next_retry_at: str,
) -> None:
    log_activity(
        db,
        workspace_id,
        "retry_scheduled",
        "Retry scheduled",
        f"{customer_email} · next attempt {next_retry_at}",
        payment_id,
    )


def payment_recovered(
    db: Session,
    workspace_id: int,
    payment_id: int,
    customer_email: str,
    amount_cents: int,
) -> None:
    amount = amount_cents / 100
    log_activity(
        db,
        workspace_id,
        "payment_recovered",
        f"Recovered ${amount:.2f}",
        customer_email,
        payment_id,
    )


def payment_abandoned(
    db: Session,
    workspace_id: int,
    payment_id: int,
    customer_email: str,
    decline_code: str | None,
) -> None:
    log_activity(
        db,
        workspace_id,
        "payment_abandoned",
        "Recovery abandoned",
        f"{customer_email} · {decline_code or 'max retries reached'}",
        payment_id,
    )


def dunning_email_sent(
    db: Session,
    workspace_id: int,
    payment_id: int,
    customer_email: str,
) -> None:
    log_activity(
        db,
        workspace_id,
        "dunning_email",
        "Dunning email sent",
        customer_email,
        payment_id,
    )
