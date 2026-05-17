import pytest

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


def test_select_donor_ignores_cooldown_and_disabled_when_valid_donor_exists() -> None:
    service = PoolService()

    selected = service.select_donor(
        [
            DonorCandidate(user_id=1, target_path="/cooldown", status="cooldown", last_success_score=100),
            DonorCandidate(user_id=2, target_path="/disabled", status="disabled", last_success_score=100),
            DonorCandidate(user_id=3, target_path="/ready", status="ready", last_success_score=1),
        ]
    )

    assert selected.user_id == 3
    assert selected.target_path == "/ready"


def test_select_donor_raises_when_every_candidate_is_filtered_out() -> None:
    service = PoolService()

    with pytest.raises(LookupError, match="no donor available"):
        service.select_donor(
            [
                DonorCandidate(user_id=1, target_path="/cooldown", status="cooldown", last_success_score=10),
                DonorCandidate(user_id=2, target_path="/disabled", status="disabled", last_success_score=20),
            ]
        )


def test_select_donor_prefers_higher_score_when_status_matches() -> None:
    service = PoolService()

    selected = service.select_donor(
        [
            DonorCandidate(user_id=1, target_path="/lower", status="stale", last_success_score=5),
            DonorCandidate(user_id=2, target_path="/higher", status="stale", last_success_score=10),
        ]
    )

    assert selected.user_id == 2
    assert selected.target_path == "/higher"
