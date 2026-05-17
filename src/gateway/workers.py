def recover_cooldown_status(rows: list[dict[str, object]]) -> list[str]:
    next_statuses: list[str] = []
    for row in rows:
        if row["status"] == "cooldown" and row["cooldown_until_passed"] is True:
            next_statuses.append("ready")
        else:
            next_statuses.append(str(row["status"]))
    return next_statuses
