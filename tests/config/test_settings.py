from gateway.config import Settings


def test_settings_load_real_integration_fields_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("GATEWAY_OPENLIST_PROBE_PATH", "/Movies/real.mkv")
    monkeypatch.setenv("GATEWAY_CATALOG_ROOT_PATH", "/Movies")
    monkeypatch.setenv("GATEWAY_RAPID_COPY_DONOR_COOKIE", "UID=donor")
    monkeypatch.setenv("GATEWAY_RAPID_COPY_TARGET_COOKIE", "UID=target")
    monkeypatch.setenv("GATEWAY_RAPID_COPY_SOURCE_PATH", "/Movies/real.mkv")
    monkeypatch.setenv("GATEWAY_RAPID_COPY_TARGET_PATH", "/EmbyCache/real.mkv")
    monkeypatch.setenv("GATEWAY_OPENLIST_COPY_VERIFY_ATTEMPTS", "12")
    monkeypatch.setenv("GATEWAY_OPENLIST_COPY_VERIFY_INTERVAL_SECONDS", "0.5")
    monkeypatch.setenv("GATEWAY_ADMIN_PASSWORD", "admin-secret")
    monkeypatch.setenv("GATEWAY_ADMIN_SESSION_TTL_SECONDS", "1800")

    settings = Settings(_env_file=None)

    assert settings.openlist_probe_path == "/Movies/real.mkv"
    assert settings.catalog_root_path == "/Movies"
    assert settings.rapid_copy_target_path == "/EmbyCache/real.mkv"
    assert settings.openlist_copy_verify_attempts == 12
    assert settings.openlist_copy_verify_interval_seconds == 0.5
    assert settings.admin_password == "admin-secret"
    assert settings.admin_session_ttl_seconds == 1800
