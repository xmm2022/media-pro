from dataclasses import dataclass


@dataclass(slots=True)
class TransferOutcome:
    ok: bool
    route: str
    stream_url: str | None = None
    error_code: str | None = None


class TransferService:
    def build_idempotency_key(self, user_id: int, media_id: int, route_stage: str) -> str:
        return f"{user_id}:{media_id}:{route_stage}"
