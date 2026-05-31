"""Seed product demo data for Recover SaaS."""

import secrets
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import (
    ActivityEvent,
    AttemptStatus,
    Customer,
    Payment,
    PaymentRail,
    PaymentStatus,
    PlanTier,
    RetryAggressiveness,
    SessionLocal,
    Workspace,
    engine,
    Base,
)
from app.services import activity as activity_svc
from app.services.retry_engine import schedule_retry


def seed():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        workspace = Workspace(
            name="Acme SaaS",
            slug="acme-saas",
            plan=PlanTier.GROWTH,
            stripe_connected=True,
            stripe_account_id="acct_demo_1N2x3Y4z",
            razorpay_connected=True,
            razorpay_account_id="acc_RZPdemoIndia",
            dunning_emails_enabled=True,
            dunning_sms_enabled=True,
            retry_aggressiveness=RetryAggressiveness.BALANCED,
            api_key=f"rcv_live_{secrets.token_hex(16)}",
        )
        db.add(workspace)
        db.flush()

        customers_data = [
            ("cus_seed_alice", "alice@startup.io", "Alice Chen", None),
            ("cus_seed_bob", "bob@agency.com", "Bob Martinez", None),
            ("cus_seed_carol", "carol@saas.co", "Carol Williams", None),
            ("cus_seed_dave", "dave@freelance.dev", "Dave Kumar", None),
            ("cus_seed_eve", "eve@ecommerce.shop", "Eve Johnson", None),
            ("cus_upi_priya", "priya.sharma@gmail.com", "Priya Sharma", "priya@paytm"),
            ("cus_upi_rahul", "rahul.verma@okicici", "Rahul Verma", "rahul@okicici"),
            ("cus_upi_ananya", "ananya@ybl", "Ananya Reddy", "ananya@ybl"),
        ]

        customers = {}
        for cid, email, name, vpa in customers_data:
            c = Customer(
                workspace_id=workspace.id,
                stripe_customer_id=cid,
                email=email,
                name=name,
                upi_vpa=vpa,
            )
            db.add(c)
            customers[cid] = c
        db.flush()

        scenarios = [
            # (customer, amount_paise, decline, status, rail, currency)
            ("cus_seed_alice", 4999, "insufficient_funds", PaymentStatus.RECOVERED, PaymentRail.CARD, "usd"),
            ("cus_seed_bob", 2999, "insufficient_funds", PaymentStatus.RETRY_SCHEDULED, PaymentRail.CARD, "usd"),
            ("cus_seed_carol", 9999, "expired_card", PaymentStatus.RETRY_SCHEDULED, PaymentRail.CARD, "usd"),
            ("cus_seed_dave", 1999, "stolen_card", PaymentStatus.ABANDONED, PaymentRail.CARD, "usd"),
            ("cus_upi_priya", 79900, "insufficient_balance", PaymentStatus.RETRY_SCHEDULED, PaymentRail.UPI, "inr"),
            ("cus_upi_rahul", 49900, "upi_autopay_mandate_paused", PaymentStatus.RETRY_SCHEDULED, PaymentRail.UPI, "inr"),
            ("cus_upi_ananya", 129900, "insufficient_balance", PaymentStatus.RECOVERED, PaymentRail.UPI, "inr"),
            ("cus_upi_priya", 29900, "transaction_timeout", PaymentStatus.RECOVERED, PaymentRail.UPI, "inr"),
            ("cus_upi_rahul", 99900, "upi_autopay_mandate_revoked", PaymentStatus.ABANDONED, PaymentRail.UPI, "inr"),
        ]

        for i, (cid, amount, decline, final_status, rail, currency) in enumerate(scenarios):
            customer = customers[cid]
            payment = Payment(
                workspace_id=workspace.id,
                stripe_payment_intent_id=f"pi_seed_{i:03d}",
                customer_id=customer.id,
                payment_rail=rail,
                amount_cents=amount,
                currency=currency,
                status=PaymentStatus.FAILED,
                decline_code=decline,
                created_at=datetime.utcnow() - timedelta(days=7 - i),
            )
            db.add(payment)
            db.flush()

            activity_svc.payment_failed(
                db, workspace.id, payment.id, customer.email, amount, decline
            )

            if final_status == PaymentStatus.RECOVERED:
                schedule_retry(db, payment, decline)
                payment = db.query(Payment).filter(Payment.id == payment.id).first()
                payment.status = PaymentStatus.RECOVERED
                payment.recovered_at = datetime.utcnow() - timedelta(days=2)
                payment.next_retry_at = None
                payment.dunning_email_sent = True
                for attempt in payment.attempts:
                    if attempt.status == AttemptStatus.SCHEDULED:
                        attempt.status = AttemptStatus.SUCCEEDED
                        attempt.executed_at = payment.recovered_at
                activity_svc.payment_recovered(
                    db, workspace.id, payment.id, customer.email, amount
                )
            elif final_status == PaymentStatus.ABANDONED:
                schedule_retry(db, payment, decline)
                payment = db.query(Payment).filter(Payment.id == payment.id).first()
                payment.status = PaymentStatus.ABANDONED
                payment.next_retry_at = None
                activity_svc.payment_abandoned(
                    db, workspace.id, payment.id, customer.email, decline
                )
            else:
                schedule_retry(db, payment, decline)
                payment = db.query(Payment).filter(Payment.id == payment.id).first()
                if payment.next_retry_at:
                    activity_svc.retry_scheduled(
                        db,
                        workspace.id,
                        payment.id,
                        customer.email,
                        payment.next_retry_at.isoformat(),
                    )
                if workspace.dunning_emails_enabled:
                    payment.dunning_email_sent = True
                    activity_svc.dunning_email_sent(
                        db, workspace.id, payment.id, customer.email
                    )

        db.add(
            ActivityEvent(
                workspace_id=workspace.id,
                event_type="integration",
                title="Razorpay connected (India)",
                detail="UPI AutoPay webhooks active · acc_RZPdemoIndia",
                created_at=datetime.utcnow() - timedelta(days=10),
            )
        )
        db.add(
            ActivityEvent(
                workspace_id=workspace.id,
                event_type="integration",
                title="Stripe connected",
                detail="Receiving webhooks from acct_demo_1N2x3Y4z",
                created_at=datetime.utcnow() - timedelta(days=14),
            )
        )

        db.commit()
        print(f"Seeded workspace '{workspace.name}' with {len(scenarios)} payments.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
