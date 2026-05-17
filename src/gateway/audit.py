from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(slots=True)
class AuditEvent:
    actor: str
    event_type: str
    payload: dict[str, object]


def record_audit_event(
    actor: str,
    event_type: str,
    payload: dict[str, object],
) -> dict[str, object]:
    return {"actor": actor, "event_type": event_type, "payload": payload}


def summarize_audit_types(event_types: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event_type in event_types:
        counts[event_type] = counts.get(event_type, 0) + 1
    return counts
