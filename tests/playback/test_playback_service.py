from gateway.playback import PlaybackDecision, PlaybackService


def test_playback_service_prefers_self_hit_over_pool_and_source_options() -> None:
    service = PlaybackService()

    decision = service.resolve(
        self_hit="https://target.local/self-hit.mkv",
        donor_available=True,
        source_copy_supported=True,
        source_stream_url="https://openlist.local/source.mkv",
    )

    assert decision == PlaybackDecision(route="self", stream_url="https://target.local/self-hit.mkv")


def test_playback_service_uses_pool_when_self_hit_is_absent() -> None:
    service = PlaybackService()

    decision = service.resolve(
        self_hit=None,
        donor_available=True,
        source_copy_supported=True,
        source_stream_url="https://openlist.local/source.mkv",
        pool_stream_url="https://target.local/pool.mkv",
    )

    assert decision == PlaybackDecision(route="pool", stream_url="https://target.local/pool.mkv")


def test_playback_service_uses_source_copy_when_self_and_pool_are_unavailable() -> None:
    service = PlaybackService()

    decision = service.resolve(
        self_hit=None,
        donor_available=False,
        source_copy_supported=True,
        source_stream_url="https://openlist.local/source.mkv",
        source_copy_stream_url="https://target.local/source-copy.mkv",
    )

    assert decision == PlaybackDecision(
        route="source_copy",
        stream_url="https://target.local/source-copy.mkv",
    )


def test_playback_service_falls_back_to_source_stream_when_copy_fails() -> None:
    service = PlaybackService()

    decision = service.resolve(
        self_hit=None,
        donor_available=False,
        source_copy_supported=False,
        source_stream_url="https://openlist.local/source.mkv",
    )

    assert decision == PlaybackDecision(route="source_stream", stream_url="https://openlist.local/source.mkv")


def test_playback_service_uses_supplied_pool_stream_url() -> None:
    service = PlaybackService()

    decision = service.resolve(
        self_hit=None,
        donor_available=True,
        source_copy_supported=True,
        source_stream_url="https://openlist.local/source.mkv",
        pool_stream_url="https://target.local/pool.mkv",
    )

    assert decision == PlaybackDecision(route="pool", stream_url="https://target.local/pool.mkv")
