import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import (
    ActivityEvent,
    Customer,
    Payment,
    PaymentRail,
    PaymentStatus,
    RetryAggressiveness,
    Workspace,
    get_db,
)
from app.services.upi_classifier import UPI_FAILURE_MAP, get_salary_cycle_retry_note
from app.deps import get_current_workspace, log_activity
from app.services import activity as activity_svc
from app.services.decline_classifier import DECLINE_MAP
from app.services.retry_engine import execute_retry, schedule_retry

router = APIRouter(prefix="/api", tags=["api"])


class WorkspaceResponse(BaseModel):
    id: int
    name: str
    slug: str
    plan: str
    stripe_connected: bool
    stripe_account_id: str | None
    razorpay_connected: bool
    dunning_emails_enabled: bool
    dunning_sms_enabled: bool
    retry_aggressiveness: str
    api_key: str


class WorkspaceUpdateRequest(BaseModel):
    dunning_emails_enabled: bool | None = None
    dunning_sms_enabled: bool | None = None
    retry_aggressiveness: str | None = None


class ActivityItem(BaseModel):
    id: int
    event_type: str
    title: str
    detail: str | None
    payment_id: int | None
    created_at: datetime


class SimulateFailureRequest(BaseModel):
    email: str = "demo@example.com"
    amount_cents: int = 2999
    decline_code: str = "insufficient_funds"
    payment_rail: str = "card"
    currency: str = "usd"
    upi_vpa: str | None = None
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
    customer_name: str | None
    payment_rail: str
    amount_cents: int
    amount_dollars: float
    currency: str
    status: str
    decline_code: str | None
    decline_category: str | None
    retry_count: int
    next_retry_at: datetime | None
    recovered_at: datetime | None
    dunning_email_sent: bool
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
    mrr_saved_estimate: float
    dunning_emails_sent: int


class RetryPolicyResponse(BaseModel):
    aggressiveness: str
    dunning_emails_enabled: bool
    decline_rules: dict


class ChartPoint(BaseModel):
    date: str
    recovered_cents: int
    failed_cents: int


def _payment_query(db: Session, workspace: Workspace):
    return db.query(Payment).filter(Payment.workspace_id == workspace.id)


def _payment_to_summary(payment: Payment) -> PaymentSummary:
    return PaymentSummary(
        id=payment.id,
        stripe_payment_intent_id=payment.stripe_payment_intent_id,
        customer_email=payment.customer.email,
        customer_name=payment.customer.name,
        payment_rail=payment.payment_rail.value,
        amount_cents=payment.amount_cents,
        amount_dollars=payment.amount_cents / 100,
        currency=payment.currency,
        status=payment.status.value,
        decline_code=payment.decline_code,
        decline_category=payment.decline_category.value if payment.decline_category else None,
        retry_count=payment.retry_count,
        next_retry_at=payment.next_retry_at,
        recovered_at=payment.recovered_at,
        dunning_email_sent=payment.dunning_email_sent,
        created_at=payment.created_at,
    )


def _after_schedule(db: Session, payment: Payment, workspace: Workspace) -> None:
    email = payment.customer.email
    if payment.status == PaymentStatus.RETRY_SCHEDULED and payment.next_retry_at:
        activity_svc.retry_scheduled(
            db, workspace.id, payment.id, email, payment.next_retry_at.isoformat()
        )
        if workspace.dunning_emails_enabled and not payment.dunning_email_sent:
            payment.dunning_email_sent = True
            activity_svc.dunning_email_sent(db, workspace.id, payment.id, email)
        elif (
            payment.payment_rail == PaymentRail.UPI
            and workspace.dunning_sms_enabled
            and not payment.dunning_email_sent
        ):
            payment.dunning_email_sent = True
            log_activity(
                db,
                workspace.id,
                "dunning_sms",
                "Dunning SMS sent",
                f"{email} · UPI payment reminder",
                payment.id,
            )
    elif payment.status == PaymentStatus.ABANDONED:
        activity_svc.payment_abandoned(
            db, workspace.id, payment.id, email, payment.decline_code
        )


@router.get("/workspace", response_model=WorkspaceResponse)
def get_workspace(workspace: Workspace = Depends(get_current_workspace)):
    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        slug=workspace.slug,
        plan=workspace.plan.value,
        stripe_connected=workspace.stripe_connected,
        stripe_account_id=workspace.stripe_account_id,
        razorpay_connected=workspace.razorpay_connected,
        dunning_emails_enabled=workspace.dunning_emails_enabled,
        dunning_sms_enabled=workspace.dunning_sms_enabled,
        retry_aggressiveness=workspace.retry_aggressiveness.value,
        api_key=workspace.api_key,
    )


@router.patch("/workspace", response_model=WorkspaceResponse)
def update_workspace(
    body: WorkspaceUpdateRequest,
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
):
    if body.dunning_emails_enabled is not None:
        workspace.dunning_emails_enabled = body.dunning_emails_enabled
    if body.dunning_sms_enabled is not None:
        workspace.dunning_sms_enabled = body.dunning_sms_enabled
    if body.retry_aggressiveness is not None:
        try:
            workspace.retry_aggressiveness = RetryAggressiveness(body.retry_aggressiveness)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid retry aggressiveness")
    db.commit()
    db.refresh(workspace)
    log_activity(
        db,
        workspace.id,
        "settings_updated",
        "Recovery settings updated",
        f"Dunning: {workspace.dunning_emails_enabled}, "
        f"Retry: {workspace.retry_aggressiveness.value}",
    )
    db.commit()
    return get_workspace(workspace)


@router.get("/metrics", response_model=MetricsResponse)
def get_metrics(
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
):
    failed_statuses = [
        PaymentStatus.FAILED,
        PaymentStatus.RETRY_SCHEDULED,
        PaymentStatus.RETRYING,
        PaymentStatus.ABANDONED,
    ]
    base = _payment_query(db, workspace)

    total_failed = base.filter(Payment.status.in_(failed_statuses)).count()
    total_recovered = base.filter(Payment.status == PaymentStatus.RECOVERED).count()
    total_abandoned = base.filter(Payment.status == PaymentStatus.ABANDONED).count()
    total_retry_scheduled = base.filter(Payment.status == PaymentStatus.RETRY_SCHEDULED).count()

    failed_amount = (
        base.with_entities(func.coalesce(func.sum(Payment.amount_cents), 0))
        .filter(Payment.status.in_(failed_statuses + [PaymentStatus.ABANDONED]))
        .scalar()
    )
    recovered_amount = (
        base.with_entities(func.coalesce(func.sum(Payment.amount_cents), 0))
        .filter(Payment.status == PaymentStatus.RECOVERED)
        .scalar()
    )
    at_risk = (
        base.with_entities(func.coalesce(func.sum(Payment.amount_cents), 0))
        .filter(Payment.status.in_([PaymentStatus.RETRY_SCHEDULED, PaymentStatus.RETRYING]))
        .scalar()
    )
    dunning_sent = base.filter(Payment.dunning_email_sent.is_(True)).count()

    attempted_recovery = total_recovered + total_abandoned
    recovery_rate = (total_recovered / attempted_recovery * 100) if attempted_recovery > 0 else 0.0

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
        mrr_saved_estimate=recovered_amount / 100,
        dunning_emails_sent=dunning_sent,
    )


@router.get("/metrics/chart", response_model=list[ChartPoint])
def get_metrics_chart(
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
):
    points = []
    for days_ago in range(6, -1, -1):
        day = datetime.utcnow().date() - timedelta(days=days_ago)
        day_start = datetime.combine(day, datetime.min.time())
        day_end = day_start + timedelta(days=1)

        recovered = (
            _payment_query(db, workspace)
            .with_entities(func.coalesce(func.sum(Payment.amount_cents), 0))
            .filter(
                Payment.status == PaymentStatus.RECOVERED,
                Payment.recovered_at >= day_start,
                Payment.recovered_at < day_end,
            )
            .scalar()
        )
        failed = (
            _payment_query(db, workspace)
            .with_entities(func.coalesce(func.sum(Payment.amount_cents), 0))
            .filter(
                Payment.created_at >= day_start,
                Payment.created_at < day_end,
                Payment.status != PaymentStatus.RECOVERED,
            )
            .scalar()
        )
        points.append(
            ChartPoint(
                date=day.strftime("%a"),
                recovered_cents=recovered,
                failed_cents=failed,
            )
        )
    return points


@router.get("/activity", response_model=list[ActivityItem])
def list_activity(
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
):
    events = (
        db.query(ActivityEvent)
        .filter(ActivityEvent.workspace_id == workspace.id)
        .order_by(ActivityEvent.created_at.desc())
        .limit(20)
        .all()
    )
    return [
        ActivityItem(
            id=e.id,
            event_type=e.event_type,
            title=e.title,
            detail=e.detail,
            payment_id=e.payment_id,
            created_at=e.created_at,
        )
        for e in events
    ]


@router.get("/payments", response_model=list[PaymentSummary])
def list_payments(
    status: str | None = None,
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
):
    query = (
        _payment_query(db, workspace)
        .join(Customer)
        .order_by(Payment.created_at.desc())
    )
    if status:
        try:
            query = query.filter(Payment.status == PaymentStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    return [_payment_to_summary(p) for p in query.limit(100).all()]


@router.get("/payments/{payment_id}", response_model=PaymentDetail)
def get_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
):
    payment = (
        _payment_query(db, workspace).filter(Payment.id == payment_id).first()
    )
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
def simulate_failure(
    body: SimulateFailureRequest,
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
):
    try:
        rail = PaymentRail(body.payment_rail)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid payment rail: {body.payment_rail}")

    if rail == PaymentRail.UPI and body.decline_code == "insufficient_funds":
        body.decline_code = "insufficient_balance"

    stripe_cid = body.stripe_customer_id or f"cus_{body.email.replace('@', '_')}"

    customer = (
        db.query(Customer)
        .filter(
            Customer.workspace_id == workspace.id,
            Customer.stripe_customer_id == stripe_cid,
        )
        .first()
    )
    if not customer:
        name = body.email.split("@")[0].replace(".", " ").title()
        customer = Customer(
            workspace_id=workspace.id,
            stripe_customer_id=stripe_cid,
            email=body.email,
            name=name,
            upi_vpa=body.upi_vpa,
        )
        db.add(customer)
        db.flush()

    pi_id = f"{'upi' if rail == PaymentRail.UPI else 'pi'}_sim_{datetime.utcnow().timestamp()}"

    payment = Payment(
        workspace_id=workspace.id,
        stripe_payment_intent_id=pi_id,
        customer_id=customer.id,
        payment_rail=rail,
        amount_cents=body.amount_cents,
        currency=body.currency,
        status=PaymentStatus.FAILED,
        decline_code=body.decline_code,
    )
    db.add(payment)
    db.flush()

    activity_svc.payment_failed(
        db, workspace.id, payment.id, customer.email, body.amount_cents, body.decline_code
    )
    payment = schedule_retry(db, payment, body.decline_code)
    _after_schedule(db, payment, workspace)
    db.commit()
    db.refresh(payment)

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
def trigger_retry(
    payment_id: int,
    success: bool = False,
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
):
    payment = _payment_query(db, workspace).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.status not in (PaymentStatus.RETRY_SCHEDULED, PaymentStatus.FAILED):
        raise HTTPException(
            status_code=400,
            detail=f"Payment status '{payment.status.value}' cannot be retried",
        )

    payment = execute_retry(db, payment, success=success)
    if success:
        activity_svc.payment_recovered(
            db, workspace.id, payment.id, payment.customer.email, payment.amount_cents
        )
    else:
        _after_schedule(db, payment, workspace)
    db.commit()
    db.refresh(payment)
    return _payment_to_summary(payment)


@router.get("/retry-policy", response_model=RetryPolicyResponse)
def get_retry_policy(workspace: Workspace = Depends(get_current_workspace)):
    return RetryPolicyResponse(
        aggressiveness=workspace.retry_aggressiveness.value,
        dunning_emails_enabled=workspace.dunning_emails_enabled,
        decline_rules={
            code: {
                "type": info.decline_type.value,
                "should_retry": info.should_retry,
                "max_retries": info.max_retries,
                "intervals_hours": info.retry_intervals_hours,
                "reason": info.reason,
            }
            for code, info in DECLINE_MAP.items()
        },
    )


@router.get("/upi/failure-codes")
def list_upi_failure_codes():
    return {
        "salary_cycle_note": get_salary_cycle_retry_note(),
        "codes": {
            code: {
                "type": info.decline_type.value,
                "should_retry": info.should_retry,
                "max_retries": info.max_retries,
                "intervals_hours": info.retry_intervals_hours,
                "reason": info.reason,
                "notify_channel": info.notify_channel,
                "salary_cycle_retry": info.salary_cycle_retry,
            }
            for code, info in UPI_FAILURE_MAP.items()
        },
    }


@router.get("/decline-codes")
def list_decline_codes():
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
