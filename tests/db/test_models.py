from gateway.models import PoolObjectStatus, TransferRoute


def test_model_enums_expose_expected_values() -> None:
    assert PoolObjectStatus.READY.value == "ready"
    assert PoolObjectStatus.COOLDOWN.value == "cooldown"
    assert TransferRoute.SOURCE_STREAM.value == "source_stream"
