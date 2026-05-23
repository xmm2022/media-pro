from datetime import datetime, timedelta, timezone

from gateway.models import PoolObjectStatus
from gateway.workers import recover_expired_cooldowns


def test_recover_expired_cooldowns_promotes_matching_rows() -> None:
    rows = [
        {
            "status": "cooldown",
            "cooldown_until": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        {"status": "ready", "cooldown_until": None},
    ]

    assert recover_expired_cooldowns(rows) == ["ready", "ready"]


def test_recover_expired_cooldowns_keeps_active_cooldown_rows() -> None:
    rows = [
        {
            "status": "cooldown",
            "cooldown_until": datetime.now(timezone.utc) + timedelta(minutes=1),
        }
    ]

    assert recover_expired_cooldowns(rows) == ["cooldown"]


def test_recover_expired_cooldowns_normalizes_enum_backed_statuses() -> None:
    rows = [{"status": PoolObjectStatus.READY, "cooldown_until": None}]

    assert recover_expired_cooldowns(rows) == ["ready"]


def test_recover_expired_cooldowns_promotes_naive_expired_datetimes() -> None:
    expired_utc_naive = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
    rows = [{"status": "cooldown", "cooldown_until": expired_utc_naive}]

    assert recover_expired_cooldowns(rows) == ["ready"]
