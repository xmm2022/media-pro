from gateway.api.admin import summarize_routes


def test_summarize_routes_returns_all_buckets() -> None:
    summary = summarize_routes(["self", "source_stream", "source_stream"])

    assert summary == {"self": 1, "pool": 0, "source_copy": 0, "source_stream": 2}
