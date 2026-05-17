from gateway.models import PoolObjectStatus
from gateway.workers import recover_cooldown_status


def test_recover_cooldown_status_promotes_expired_entries() -> None:
    assert recover_cooldown_status(
        [
            {"status": "cooldown", "cooldown_until_passed": True},
            {"status": "ready", "cooldown_until_passed": False},
        ]
    ) == ["ready", "ready"]


def test_recover_cooldown_status_keeps_active_cooldown_entries() -> None:
    assert recover_cooldown_status(
        [{"status": "cooldown", "cooldown_until_passed": False}]
    ) == ["cooldown"]


def test_recover_cooldown_status_normalizes_enum_backed_statuses() -> None:
    assert recover_cooldown_status(
        [{"status": PoolObjectStatus.READY, "cooldown_until_passed": False}]
    ) == ["ready"]
