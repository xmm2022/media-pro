from dataclasses import dataclass

from gateway.config import Settings


@dataclass(frozen=True, slots=True)
class RapidCopyProbe:
    donor_cookie: str
    target_cookie: str
    source_path: str
    target_path: str


def build_openlist_probe_path(app_settings: Settings) -> str:
    if not app_settings.openlist_probe_path:
        raise ValueError("GATEWAY_OPENLIST_PROBE_PATH must not be empty")
    return app_settings.openlist_probe_path


def build_rapid_copy_probe(app_settings: Settings) -> RapidCopyProbe:
    required_values = {
        "GATEWAY_RAPID_COPY_DONOR_COOKIE": app_settings.rapid_copy_donor_cookie,
        "GATEWAY_RAPID_COPY_TARGET_COOKIE": app_settings.rapid_copy_target_cookie,
        "GATEWAY_RAPID_COPY_SOURCE_PATH": app_settings.rapid_copy_source_path,
        "GATEWAY_RAPID_COPY_TARGET_PATH": app_settings.rapid_copy_target_path,
    }
    missing = [name for name, value in required_values.items() if not value]
    if missing:
        raise ValueError(f"Missing probe settings: {', '.join(missing)}")
    return RapidCopyProbe(
        donor_cookie=app_settings.rapid_copy_donor_cookie,
        target_cookie=app_settings.rapid_copy_target_cookie,
        source_path=app_settings.rapid_copy_source_path,
        target_path=app_settings.rapid_copy_target_path,
    )
