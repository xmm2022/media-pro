from gateway.workers import recover_cooldown_status


def test_recover_cooldown_status_promotes_expired_entries() -> None:
    assert recover_cooldown_status(
        [
            {"status": "cooldown", "cooldown_until_passed": True},
            {"status": "ready", "cooldown_until_passed": False},
        ]
    ) == ["ready", "ready"]
