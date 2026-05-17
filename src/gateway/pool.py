from dataclasses import dataclass


@dataclass(slots=True)
class DonorCandidate:
    user_id: int
    target_path: str
    status: str
    last_success_score: int


class PoolService:
    READY_ORDER = {"ready": 0, "stale": 1, "suspect": 2, "cooldown": 3, "disabled": 4}

    def select_donor(self, candidates: list[DonorCandidate]) -> DonorCandidate:
        selectable = [candidate for candidate in candidates if candidate.status not in {"cooldown", "disabled"}]
        if not selectable:
            raise LookupError("no donor available")
        selectable.sort(key=lambda item: (self.READY_ORDER[item.status], -item.last_success_score))
        return selectable[0]
