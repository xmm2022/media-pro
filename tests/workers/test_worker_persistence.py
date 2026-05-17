from datetime import datetime, timedelta, timezone

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
