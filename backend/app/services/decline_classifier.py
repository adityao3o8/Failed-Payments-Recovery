"""
Decline code classification based on Stripe decline codes and network behavior.

Hard declines: card is invalid, stolen, or permanently blocked — do not retry.
Soft declines: temporary issue — retry with backoff.
Retryable: issuer asked to retry (often insufficient funds at wrong time).
"""

from dataclasses import dataclass
from enum import Enum


class DeclineType(str, Enum):
    HARD = "hard"
    SOFT = "soft"
    RETRYABLE = "retryable"
    UNKNOWN = "unknown"


@dataclass
class DeclineInfo:
    code: str
    decline_type: DeclineType
    should_retry: bool
    max_retries: int
    retry_intervals_hours: list[int]
    reason: str


# Stripe decline codes → classification
# https://stripe.com/docs/declines/codes
DECLINE_MAP: dict[str, DeclineInfo] = {
    "insufficient_funds": DeclineInfo(
        code="insufficient_funds",
        decline_type=DeclineType.RETRYABLE,
        should_retry=True,
        max_retries=4,
        retry_intervals_hours=[24, 72, 168, 336],  # 1d, 3d, 7d, 14d
        reason="Customer may have funds later in billing cycle",
    ),
    "card_declined": DeclineInfo(
        code="card_declined",
        decline_type=DeclineType.SOFT,
        should_retry=True,
        max_retries=3,
        retry_intervals_hours=[48, 120, 240],
        reason="Generic decline — retry with backoff",
    ),
    "expired_card": DeclineInfo(
        code="expired_card",
        decline_type=DeclineType.SOFT,
        should_retry=True,
        max_retries=2,
        retry_intervals_hours=[24, 72],
        reason="Card updater may provide new expiry; notify customer",
    ),
    "incorrect_cvc": DeclineInfo(
        code="incorrect_cvc",
        decline_type=DeclineType.SOFT,
        should_retry=False,
        max_retries=0,
        retry_intervals_hours=[],
        reason="Customer must update card details",
    ),
    "processing_error": DeclineInfo(
        code="processing_error",
        decline_type=DeclineType.SOFT,
        should_retry=True,
        max_retries=3,
        retry_intervals_hours=[1, 6, 24],
        reason="Transient processor error",
    ),
    "try_again_later": DeclineInfo(
        code="try_again_later",
        decline_type=DeclineType.RETRYABLE,
        should_retry=True,
        max_retries=4,
        retry_intervals_hours=[6, 24, 72, 168],
        reason="Issuer requested retry",
    ),
    "authentication_required": DeclineInfo(
        code="authentication_required",
        decline_type=DeclineType.SOFT,
        should_retry=True,
        max_retries=2,
        retry_intervals_hours=[24, 72],
        reason="3DS required — send customer to authenticate",
    ),
    "stolen_card": DeclineInfo(
        code="stolen_card",
        decline_type=DeclineType.HARD,
        should_retry=False,
        max_retries=0,
        retry_intervals_hours=[],
        reason="Card reported stolen — never retry",
    ),
    "lost_card": DeclineInfo(
        code="lost_card",
        decline_type=DeclineType.HARD,
        should_retry=False,
        max_retries=0,
        retry_intervals_hours=[],
        reason="Card reported lost — never retry",
    ),
    "fraudulent": DeclineInfo(
        code="fraudulent",
        decline_type=DeclineType.HARD,
        should_retry=False,
        max_retries=0,
        retry_intervals_hours=[],
        reason="Suspected fraud — block and review",
    ),
    "do_not_honor": DeclineInfo(
        code="do_not_honor",
        decline_type=DeclineType.HARD,
        should_retry=False,
        max_retries=0,
        retry_intervals_hours=[],
        reason="Issuer hard decline",
    ),
    "generic_decline": DeclineInfo(
        code="generic_decline",
        decline_type=DeclineType.SOFT,
        should_retry=True,
        max_retries=2,
        retry_intervals_hours=[72, 168],
        reason="Unspecified decline — conservative retry",
    ),
}

DEFAULT_DECLINE = DeclineInfo(
    code="unknown",
    decline_type=DeclineType.UNKNOWN,
    should_retry=True,
    max_retries=2,
    retry_intervals_hours=[72, 168],
    reason="Unknown decline code — conservative retry",
)


def classify_decline(decline_code: str | None) -> DeclineInfo:
    if not decline_code:
        return DEFAULT_DECLINE
    normalized = decline_code.lower().strip()
    return DECLINE_MAP.get(normalized, DEFAULT_DECLINE)
