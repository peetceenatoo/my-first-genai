from __future__ import annotations

import json
from typing import Any, Callable


def _canonicalize(value: Any) -> str:
    if value is None:
        return "__NONE__"
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    return str(value)


def _normalize_vote_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned if cleaned else None
    if isinstance(value, (list, dict)):
        return value if len(value) > 0 else None
    return value


def aggregate_votes(
    votes: list[dict[str, Any]],
    field_names: list[str],
) -> tuple[dict[str, Any], dict[str, float | None]]:
    merged: dict[str, Any] = {}
    confidences: dict[str, float | None] = {}
    total_votes = max(len(votes), 1)

    for field_name in field_names:
        counts: dict[str, int] = {}
        samples: dict[str, Any] = {}

        for vote in votes:
            value = _normalize_vote_value(vote.get(field_name, None))
            key = _canonicalize(value)
            counts[key] = counts.get(key, 0) + 1
            if key not in samples:
                samples[key] = value

        if not counts:
            merged[field_name] = None
            confidences[field_name] = None
            continue

        best = max(counts, key=lambda k: counts[k])
        merged[field_name] = samples.get(best, None)
        confidences[field_name] = counts[best] / total_votes

    return merged, confidences


def run_vote_cycle(
    *,
    field_names: list[str],
    vote_runs: int,
    extract_single_vote: Callable[[int], dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, float | None]]:
    votes: list[dict[str, Any]] = []
    for vote_index in range(vote_runs):
        vote_payload = extract_single_vote(vote_index)
        votes.append(vote_payload if isinstance(vote_payload, dict) else {})

    return aggregate_votes(votes, field_names)
