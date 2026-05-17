from gateway.pool import DonorCandidate, PoolService


def test_select_donor_prefers_ready_then_recent_success() -> None:
    service = PoolService()
    selected = service.select_donor(
        [
            DonorCandidate(user_id=2, target_path="/b", status="suspect", last_success_score=5),
            DonorCandidate(user_id=1, target_path="/a", status="ready", last_success_score=10),
        ]
    )

    assert selected.user_id == 1
    assert selected.target_path == "/a"
