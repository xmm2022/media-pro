from gateway.config import Settings
from gateway.integrations.rapid_copy_client import PoolCopyRequest, SourceCopyRequest, SourceObjectRef


PoolCopyProbe = PoolCopyRequest
SourceCopyProbe = SourceCopyRequest


def build_openlist_probe_path(app_settings: Settings) -> str:
    if not app_settings.openlist_probe_path:
        raise ValueError("GATEWAY_OPENLIST_PROBE_PATH must not be empty")
    return app_settings.openlist_probe_path


def build_pool_copy_probe(app_settings: Settings) -> PoolCopyProbe:
    required_values = {
        "GATEWAY_RAPID_COPY_DONOR_COOKIE": app_settings.rapid_copy_donor_cookie,
        "GATEWAY_RAPID_COPY_TARGET_COOKIE": app_settings.rapid_copy_target_cookie,
        "GATEWAY_RAPID_COPY_SOURCE_PATH": app_settings.rapid_copy_source_path,
        "GATEWAY_RAPID_COPY_TARGET_PATH": app_settings.rapid_copy_target_path,
    }
    missing = [name for name, value in required_values.items() if not value]
    if missing:
        raise ValueError(f"Missing probe settings: {', '.join(missing)}")
    return PoolCopyProbe(
        donor_cookie=app_settings.rapid_copy_donor_cookie,
        target_cookie=app_settings.rapid_copy_target_cookie,
        source_path=app_settings.rapid_copy_source_path,
        target_path=app_settings.rapid_copy_target_path,
    )


def build_source_copy_probe(app_settings: Settings) -> SourceCopyProbe:
    required_values = {
        "GATEWAY_RAPID_COPY_TARGET_COOKIE": app_settings.rapid_copy_target_cookie,
        "GATEWAY_RAPID_COPY_SOURCE_PATH": app_settings.rapid_copy_source_path,
        "GATEWAY_RAPID_COPY_TARGET_PATH": app_settings.rapid_copy_target_path,
    }
    missing = [name for name, value in required_values.items() if not value]
    if missing:
        raise ValueError(f"Missing probe settings: {', '.join(missing)}")
    return SourceCopyProbe(
        target_cookie=app_settings.rapid_copy_target_cookie,
        source=SourceObjectRef(
            openlist_path=app_settings.rapid_copy_source_path,
            source_path=app_settings.rapid_copy_source_path,
        ),
        target_path=app_settings.rapid_copy_target_path,
    )


def build_rapid_copy_probe(app_settings: Settings) -> PoolCopyProbe:
    return build_pool_copy_probe(app_settings)
