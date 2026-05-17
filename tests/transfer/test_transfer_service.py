from gateway.transfer import TransferService


def test_build_idempotency_key_is_stable() -> None:
    service = TransferService()

    assert service.build_idempotency_key(user_id=7, media_id=42, route_stage="try_pool") == "7:42:try_pool"
