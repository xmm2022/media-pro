from gateway.playback import PlaybackDecision, PlaybackService


def test_playback_service_falls_back_to_source_stream_when_copy_fails() -> None:
    service = PlaybackService()

    decision = service.resolve(
        self_hit=None,
        donor_available=False,
        source_copy_supported=False,
        source_stream_url="https://openlist.local/source.mkv",
    )

    assert decision == PlaybackDecision(route="source_stream", stream_url="https://openlist.local/source.mkv")
