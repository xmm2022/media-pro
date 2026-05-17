from dataclasses import dataclass


@dataclass(slots=True)
class AuditEvent:
    actor: str
    event_type: str
    payload: dict[str, object]
