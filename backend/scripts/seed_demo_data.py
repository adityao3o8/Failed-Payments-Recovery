"""Seed demo data for portfolio demos and local development."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import (
    AttemptStatus,
    Customer,
    DeclineCategory,
    Payment,
    PaymentAttempt,
    PaymentStatus,
    SessionLocal,
    engine,
    Base,
)
from app.services.retry_engine import schedule_retry


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        if db.query(Payment).count() > 0:
            print("Database already seeded. Skipping.")
            return

        customers_data = [
            ("cus_seed_alice", "alice@startup.io"),
            ("cus_seed_bob", "bob@agency.com"),
            ("cus_seed_carol", "carol@saas.co"),
            ("cus_seed_dave", "dave@freelance.dev"),
            ("cus_seed_eve", "eve@ecommerce.shop"),
        ]

        customers = {}
        for cid, email in customers_data:
            c = Customer(stripe_customer_id=cid, email=email)
            db.add(c)
            customers[cid] = c
        db.flush()

        scenarios = [
            # (customer_key, amount, decline_code, final_status)
            ("cus_seed_alice", 4999, "insufficient_funds", PaymentStatus.RECOVERED),
            ("cus_seed_bob", 2999, "insufficient_funds", PaymentStatus.RETRY_SCHEDULED),
            ("cus_seed_carol", 9999, "expired_card", PaymentStatus.RETRY_SCHEDULED),
            ("cus_seed_dave", 1999, "stolen_card", PaymentStatus.ABANDONED),
            ("cus_seed_eve", 7999, "try_again_later", PaymentStatus.RECOVERED),
            ("cus_seed_alice", 1499, "processing_error", PaymentStatus.ABANDONED),
            ("cus_seed_bob", 5999, "card_declined", PaymentStatus.RETRY_SCHEDULED),
        ]

        for i, (cid, amount, decline, final_status) in enumerate(scenarios):
            payment = Payment(
                stripe_payment_intent_id=f"pi_seed_{i:03d}",
                customer_id=customers[cid].id,
                amount_cents=amount,
                status=PaymentStatus.FAILED,
                decline_code=decline,
                created_at=datetime.utcnow() - timedelta(days=7 - i),
            )
            db.add(payment)
            db.flush()

            if final_status == PaymentStatus.RECOVERED:
                schedule_retry(db, payment, decline)
                payment = db.query(Payment).filter(Payment.id == payment.id).first()
                payment.status = PaymentStatus.RECOVERED
                payment.recovered_at = datetime.utcnow() - timedelta(days=2)
                payment.next_retry_at = None
                # Mark scheduled attempt as succeeded
                for attempt in payment.attempts:
                    if attempt.status == AttemptStatus.SCHEDULED:
                        attempt.status = AttemptStatus.SUCCEEDED
                        attempt.executed_at = payment.recovered_at
            elif final_status == PaymentStatus.ABANDONED:
                schedule_retry(db, payment, decline)
                payment = db.query(Payment).filter(Payment.id == payment.id).first()
                payment.status = PaymentStatus.ABANDONED
                payment.next_retry_at = None
            else:
                schedule_retry(db, payment, decline)

        db.commit()
        print(f"Seeded {len(scenarios)} demo payments.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
