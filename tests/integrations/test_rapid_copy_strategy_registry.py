import pytest

from gateway.integrations.rapid_copy_strategy import (
    RapidCopyStrategyRegistry,
    UnsupportedDriveType,
)


class FakeStrategy:
    def __init__(self, drive_type: str) -> None:
        self.drive_type = drive_type


def test_registry_returns_strategy_for_registered_drive_type() -> None:
    registry = RapidCopyStrategyRegistry()
    strategy = FakeStrategy("115")
    registry.register(strategy)

    assert registry.get("115") is strategy


def test_registry_raises_for_unknown_drive_type() -> None:
    registry = RapidCopyStrategyRegistry()

    with pytest.raises(UnsupportedDriveType):
        registry.get("aliyun")


def test_registry_replaces_strategy_on_re_register() -> None:
    registry = RapidCopyStrategyRegistry()
    first = FakeStrategy("115")
    second = FakeStrategy("115")

    registry.register(first)
    registry.register(second)

    assert registry.get("115") is second
