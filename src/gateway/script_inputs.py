from dataclasses import dataclass

from gateway.config import Settings

_PLACEHOLDER_PATHS = {"/Movies/sample.mkv", "/EmbyCache/sample.mkv"}


@dataclass(frozen=True, slots=True)
class RapidCopyProbe:
    donor_cookie: str
    target_cookie: str
    source_path: str
    target_path: str


def build_openlist_probe_path(app_settings: Settings) -> str:
    if not app_settings.openlist_probe_path:
        raise ValueError("GATEWAY_OPENLIST_PROBE_PATH must not be empty")
    if app_settings.openlist_probe_path in _PLACEHOLDER_PATHS:
        raise ValueError("GATEWAY_OPENLIST_PROBE_PATH must be set to a real media path")
    return app_settings.openlist_probe_path


def build_rapid_copy_probe(app_settings: Settings) -> RapidCopyProbe:
    required_values = {
        "GATEWAY_RAPID_COPY_DONOR_COOKIE": app_settings.rapid_copy_donor_cookie,
        "GATEWAY_RAPID_COPY_TARGET_COOKIE": app_settings.rapid_copy_target_cookie,
        "GATEWAY_RAPID_COPY_SOURCE_PATH": app_settings.rapid_copy_source_path,
        "GATEWAY_RAPID_COPY_TARGET_PATH": app_settings.rapid_copy_target_path,
    }
    missing = [name for name, value in required_values.items() if not value]
    placeholder_paths = [
        name
        for name, value in required_values.items()
        if name.endswith("_PATH") and value in _PLACEHOLDER_PATHS
    ]
    if missing:
        raise ValueError(f"Missing probe settings: {', '.join(missing)}")
    if placeholder_paths:
        raise ValueError(f"Probe settings must use real paths: {', '.join(placeholder_paths)}")
    return RapidCopyProbe(
        donor_cookie=app_settings.rapid_copy_donor_cookie,
        target_cookie=app_settings.rapid_copy_target_cookie,
        source_path=app_settings.rapid_copy_source_path,
        target_path=app_settings.rapid_copy_target_path,
    )
