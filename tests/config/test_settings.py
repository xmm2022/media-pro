from gateway.config import Settings


def test_settings_load_real_integration_fields_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("GATEWAY_OPENLIST_PROBE_PATH", "/Movies/real.mkv")
    monkeypatch.setenv("GATEWAY_CATALOG_ROOT_PATH", "/Movies")
    monkeypatch.setenv("GATEWAY_RAPID_COPY_DONOR_COOKIE", "UID=donor")
    monkeypatch.setenv("GATEWAY_RAPID_COPY_TARGET_COOKIE", "UID=target")
    monkeypatch.setenv("GATEWAY_RAPID_COPY_SOURCE_PATH", "/Movies/real.mkv")
    monkeypatch.setenv("GATEWAY_RAPID_COPY_TARGET_PATH", "/EmbyCache/real.mkv")

    settings = Settings(_env_file=None)

    assert settings.openlist_probe_path == "/Movies/real.mkv"
    assert settings.catalog_root_path == "/Movies"
    assert settings.rapid_copy_target_path == "/EmbyCache/real.mkv"
