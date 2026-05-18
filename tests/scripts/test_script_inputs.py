import pytest

from gateway.config import Settings
from gateway.script_inputs import RapidCopyProbe, build_openlist_probe_path, build_rapid_copy_probe


def test_build_openlist_probe_path_returns_settings_value() -> None:
    app_settings = Settings(_env_file=None, openlist_probe_path="/Movies/real.mkv")

    assert build_openlist_probe_path(app_settings) == "/Movies/real.mkv"


def test_build_rapid_copy_probe_rejects_missing_required_values() -> None:
    app_settings = Settings(
        _env_file=None,
        rapid_copy_donor_cookie="",
        rapid_copy_target_cookie="",
        rapid_copy_source_path="/Movies/real.mkv",
        rapid_copy_target_path="/EmbyCache/real.mkv",
    )

    with pytest.raises(ValueError, match="GATEWAY_RAPID_COPY_DONOR_COOKIE"):
        build_rapid_copy_probe(app_settings)


def test_build_rapid_copy_probe_returns_env_driven_payload() -> None:
    app_settings = Settings(
        _env_file=None,
        rapid_copy_donor_cookie="UID=donor",
        rapid_copy_target_cookie="UID=target",
        rapid_copy_source_path="/Movies/real.mkv",
        rapid_copy_target_path="/EmbyCache/real.mkv",
    )

    assert build_rapid_copy_probe(app_settings) == RapidCopyProbe(
        donor_cookie="UID=donor",
        target_cookie="UID=target",
        source_path="/Movies/real.mkv",
        target_path="/EmbyCache/real.mkv",
    )
