"""
UPI payment failure classification for the Indian market.

Covers one-time UPI failures and UPI AutoPay (e-mandate) subscription debits.
Sources: NPCI UPI AutoPay guidelines, Razorpay/PayU failure reason codes.

Key India-specific insight: insufficient balance retries should align with
salary cycles (1st, 5th, 10th of month) — not just fixed hour backoff.
"""

from dataclasses import dataclass

from app.services.decline_classifier import DEFAULT_DECLINE, DeclineInfo, DeclineType


@dataclass
class UpiFailureInfo(DeclineInfo):
    notify_channel: str = "sms"  # sms | whatsapp | push — primary in India
    salary_cycle_retry: bool = False


UPI_FAILURE_MAP: dict[str, UpiFailureInfo] = {
    "insufficient_balance": UpiFailureInfo(
        code="insufficient_balance",
        decline_type=DeclineType.RETRYABLE,
        should_retry=True,
        max_retries=5,
        retry_intervals_hours=[24, 72, 168, 336, 504],  # + salary-cycle override
        reason="Low UPI balance — retry after salary credit (1st/5th/10th)",
        notify_channel="sms",
        salary_cycle_retry=True,
    ),
    "upi_autopay_mandate_paused": UpiFailureInfo(
        code="upi_autopay_mandate_paused",
        decline_type=DeclineType.SOFT,
        should_retry=True,
        max_retries=2,
        retry_intervals_hours=[24, 72],
        reason="Customer paused AutoPay mandate — send SMS to re-enable",
        notify_channel="sms",
    ),
    "upi_autopay_mandate_revoked": UpiFailureInfo(
        code="upi_autopay_mandate_revoked",
        decline_type=DeclineType.HARD,
        should_retry=False,
        max_retries=0,
        retry_intervals_hours=[],
        reason="Mandate revoked on customer's UPI app — must re-register",
        notify_channel="sms",
    ),
    "upi_autopay_mandate_expired": UpiFailureInfo(
        code="upi_autopay_mandate_expired",
        decline_type=DeclineType.HARD,
        should_retry=False,
        max_retries=0,
        retry_intervals_hours=[],
        reason="UPI AutoPay mandate expired — new mandate required",
        notify_channel="sms",
    ),
    "bank_declined": UpiFailureInfo(
        code="bank_declined",
        decline_type=DeclineType.SOFT,
        should_retry=True,
        max_retries=3,
        retry_intervals_hours=[6, 24, 72],
        reason="Remitter bank declined — often transient NPCI/bank downtime",
        notify_channel="sms",
    ),
    "upi_pin_incorrect": UpiFailureInfo(
        code="upi_pin_incorrect",
        decline_type=DeclineType.SOFT,
        should_retry=False,
        max_retries=0,
        retry_intervals_hours=[],
        reason="Wrong UPI PIN — customer must retry manually, send app deep link",
        notify_channel="push",
    ),
    "user_cancelled": UpiFailureInfo(
        code="user_cancelled",
        decline_type=DeclineType.SOFT,
        should_retry=True,
        max_retries=2,
        retry_intervals_hours=[48, 168],
        reason="Customer cancelled on UPI app — nudge via SMS/WhatsApp",
        notify_channel="whatsapp",
    ),
    "transaction_timeout": UpiFailureInfo(
        code="transaction_timeout",
        decline_type=DeclineType.RETRYABLE,
        should_retry=True,
        max_retries=3,
        retry_intervals_hours=[1, 6, 24],
        reason="NPCI/PSP timeout — safe to retry quickly",
        notify_channel="sms",
    ),
    "daily_limit_exceeded": UpiFailureInfo(
        code="daily_limit_exceeded",
        decline_type=DeclineType.RETRYABLE,
        should_retry=True,
        max_retries=2,
        retry_intervals_hours=[24, 48],
        reason="UPI daily limit hit — retry next calendar day",
        notify_channel="sms",
    ),
    "npci_technical_error": UpiFailureInfo(
        code="npci_technical_error",
        decline_type=DeclineType.RETRYABLE,
        should_retry=True,
        max_retries=4,
        retry_intervals_hours=[1, 4, 12, 24],
        reason="NPCI switch error — retry with exponential backoff",
        notify_channel="sms",
    ),
    "collect_request_expired": UpiFailureInfo(
        code="collect_request_expired",
        decline_type=DeclineType.SOFT,
        should_retry=True,
        max_retries=2,
        retry_intervals_hours=[24, 72],
        reason="UPI collect request expired — resend collect or AutoPay debit",
        notify_channel="sms",
    ),
    "vpa_invalid": UpiFailureInfo(
        code="vpa_invalid",
        decline_type=DeclineType.HARD,
        should_retry=False,
        max_retries=0,
        retry_intervals_hours=[],
        reason="Invalid UPI ID (VPA) — customer must update payment method",
        notify_channel="sms",
    ),
}

# India salary-cycle retry days (day of month)
SALARY_CYCLE_DAYS = [1, 5, 10, 25]


def classify_upi_failure(failure_code: str | None) -> UpiFailureInfo:
    if not failure_code:
        base = DEFAULT_DECLINE
        return UpiFailureInfo(
            code=base.code,
            decline_type=base.decline_type,
            should_retry=base.should_retry,
            max_retries=base.max_retries,
            retry_intervals_hours=base.retry_intervals_hours,
            reason=base.reason,
        )
    normalized = failure_code.lower().strip()
    return UPI_FAILURE_MAP.get(normalized, UpiFailureInfo(
        code=normalized,
        decline_type=DeclineType.UNKNOWN,
        should_retry=True,
        max_retries=2,
        retry_intervals_hours=[72, 168],
        reason="Unknown UPI failure — conservative retry",
        notify_channel="sms",
    ))


def get_salary_cycle_retry_note() -> str:
    days = ", ".join(str(d) for d in SALARY_CYCLE_DAYS)
    return f"For insufficient_balance, also retry on salary days: {days} of each month"
