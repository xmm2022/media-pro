from dataclasses import dataclass


@dataclass(slots=True)
class PlaybackDecision:
    route: str
    stream_url: str


class PlaybackService:
    def __init__(self, total_budget_ms: int = 2000) -> None:
        self.total_budget_ms = total_budget_ms

    def resolve(
        self,
        self_hit: str | None,
        donor_available: bool,
        source_copy_supported: bool,
        source_stream_url: str,
        pool_stream_url: str | None = None,
        source_copy_stream_url: str | None = None,
        elapsed_ms: int = 0,
    ) -> PlaybackDecision:
        if self_hit:
            return PlaybackDecision(route="self", stream_url=self_hit)
        if elapsed_ms >= self.total_budget_ms:
            return PlaybackDecision(route="source_stream", stream_url=source_stream_url)
        if donor_available:
            return PlaybackDecision(route="pool", stream_url=pool_stream_url or source_stream_url)
        if source_copy_supported:
            return PlaybackDecision(
                route="source_copy",
                stream_url=source_copy_stream_url or source_stream_url,
            )
        return PlaybackDecision(route="source_stream", stream_url=source_stream_url)
