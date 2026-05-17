from datetime import datetime, timezone
from enum import Enum


def _status_value(status: object) -> str:
    if isinstance(status, Enum):
        return str(status.value)
    return str(status)


def recover_cooldown_status(rows: list[dict[str, object]]) -> list[str]:
    next_statuses: list[str] = []
    for row in rows:
        if row["status"] == "cooldown" and row["cooldown_until_passed"] is True:
            next_statuses.append("ready")
        else:
            next_statuses.append(_status_value(row["status"]))
    return next_statuses


def recover_expired_cooldowns(rows: list[dict[str, object]]) -> list[str]:
    now = datetime.now(timezone.utc)
    next_statuses: list[str] = []
    for row in rows:
        if (
            _status_value(row["status"]) == "cooldown"
            and row["cooldown_until"]
            and row["cooldown_until"] <= now
        ):
            next_statuses.append("ready")
        else:
            next_statuses.append(_status_value(row["status"]))
    return next_statuses
