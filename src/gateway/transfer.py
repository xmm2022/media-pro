from dataclasses import dataclass


@dataclass(slots=True)
class TransferOutcome:
    ok: bool
    route: str
    stream_url: str | None = None
    error_code: str | None = None
