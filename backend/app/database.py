import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


class PaymentStatus(str, enum.Enum):
    FAILED = "failed"
    RETRY_SCHEDULED = "retry_scheduled"
    RETRYING = "retrying"
    RECOVERED = "recovered"
    ABANDONED = "abandoned"


class DeclineCategory(str, enum.Enum):
    HARD = "hard"
    SOFT = "soft"
    RETRYABLE = "retryable"
    UNKNOWN = "unknown"


class AttemptStatus(str, enum.Enum):
    FAILED = "failed"
    SUCCEEDED = "succeeded"
    SCHEDULED = "scheduled"
    SKIPPED = "skipped"


class PlanTier(str, enum.Enum):
    STARTER = "starter"
    GROWTH = "growth"
    ENTERPRISE = "enterprise"


class RetryAggressiveness(str, enum.Enum):
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"


class PaymentRail(str, enum.Enum):
    CARD = "card"
    UPI = "upi"


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    plan: Mapped[PlanTier] = mapped_column(Enum(PlanTier), default=PlanTier.GROWTH)
    stripe_connected: Mapped[bool] = mapped_column(Boolean, default=True)
    stripe_account_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dunning_emails_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    dunning_sms_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    razorpay_connected: Mapped[bool] = mapped_column(Boolean, default=False)
    razorpay_account_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    razorpay_account_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    retry_aggressiveness: Mapped[RetryAggressiveness] = mapped_column(
        Enum(RetryAggressiveness), default=RetryAggressiveness.BALANCED
    )
    api_key: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    customers: Mapped[list["Customer"]] = relationship(back_populates="workspace")
    payments: Mapped[list["Payment"]] = relationship(back_populates="workspace")
    activity_events: Mapped[list["ActivityEvent"]] = relationship(back_populates="workspace")


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("workspace_id", "stripe_customer_id", name="uq_workspace_stripe_customer"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    stripe_customer_id: Mapped[str] = mapped_column(String(255), index=True)
    email: Mapped[str] = mapped_column(String(255))
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    upi_vpa: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    workspace: Mapped["Workspace"] = relationship(back_populates="customers")
    payments: Mapped[list["Payment"]] = relationship(back_populates="customer")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    stripe_payment_intent_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    stripe_invoice_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    payment_rail: Mapped[PaymentRail] = mapped_column(
        Enum(PaymentRail), default=PaymentRail.CARD
    )
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="usd")
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus), default=PaymentStatus.FAILED
    )
    decline_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    decline_category: Mapped[DeclineCategory | None] = mapped_column(
        Enum(DeclineCategory), nullable=True
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=4)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    recovered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    dunning_email_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    workspace: Mapped["Workspace"] = relationship(back_populates="payments")
    customer: Mapped["Customer"] = relationship(back_populates="payments")
    attempts: Mapped[list["PaymentAttempt"]] = relationship(
        back_populates="payment", order_by="PaymentAttempt.attempt_number"
    )


class PaymentAttempt(Base):
    __tablename__ = "payment_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id"))
    attempt_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[AttemptStatus] = mapped_column(Enum(AttemptStatus))
    decline_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    payment: Mapped["Payment"] = relationship(back_populates="attempts")


class ActivityEvent(Base):
    __tablename__ = "activity_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(255))
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_id: Mapped[int | None] = mapped_column(ForeignKey("payments.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    workspace: Mapped["Workspace"] = relationship(back_populates="activity_events")


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    __table_args__ = (UniqueConstraint("stripe_event_id", name="uq_stripe_event_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int | None] = mapped_column(ForeignKey("workspaces.id"), nullable=True)
    stripe_event_id: Mapped[str] = mapped_column(String(255), index=True)
    event_type: Mapped[str] = mapped_column(String(100))
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
