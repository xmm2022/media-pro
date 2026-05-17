from gateway.playback import PlaybackService


def test_playback_service_falls_back_when_budget_exhausted() -> None:
    service = PlaybackService(total_budget_ms=2000)

    decision = service.resolve(
        self_hit=None,
        donor_available=False,
        source_copy_supported=False,
        source_stream_url="https://openlist.local/source.mkv",
        elapsed_ms=2100,
    )

    assert decision.route == "source_stream"
    assert decision.stream_url == "https://openlist.local/source.mkv"
