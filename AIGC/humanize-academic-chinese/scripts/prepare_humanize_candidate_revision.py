#!/usr/bin/env python3
"""Prepare an explicit, lineage-bound revision of a Humanize candidate package.

The helper never guesses replacement anchors.  An anchor that disappeared from
the new candidate body must be supplied explicitly as ``ID=EXACT_TEXT`` and
that text must occur exactly once.  A previous queue result can be bound as the
revision's ``supersedes_candidate_sha256`` so the queue validator can replace
the old accepted/review/rejected state without a candidate-id collision.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Sequence


SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
STALE_WARNING_REVIEW_FIELDS = (
    "accepted_warnings",
    "warning_resolutions",
    "warning_review_request_sha256",
    "warning_review",
)


class RevisionError(ValueError):
    """Raised when a candidate revision cannot be prepared deterministically."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RevisionError(f"duplicate_json_key:{key}")
        result[key] = value
    return result


def _reject_nonfinite(value: str) -> Any:
    raise RevisionError(f"non_finite_json_number:{value}")


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8-sig"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RevisionError(f"{label}_unreadable:{path}:{type(error).__name__}") from error
    if not isinstance(value, dict):
        raise RevisionError(f"{label}_must_be_object")
    return value


def _read_utf8(path: Path, label: str) -> str:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as error:
        raise RevisionError(f"{label}_unreadable:{path}:{type(error).__name__}") from error
    if "\ufffd" in text:
        raise RevisionError(f"{label}_contains_replacement_character")
    return text


def _previous_hash(path: Path) -> str:
    payload = _load_object(path, "supersedes_result")
    value = payload.get("candidate_sha256")
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise RevisionError("supersedes_result_missing_candidate_sha256")
    return value


def prepare_revision(
    candidate_path: Path,
    after_path: Path,
    output_path: Path,
    *,
    anchor_updates: dict[str, str] | None = None,
    supersedes_result_path: Path | None = None,
) -> dict[str, Any]:
    """Create one new candidate package without overwriting inputs or outputs."""
    candidate_path = candidate_path.resolve()
    after_path = after_path.resolve()
    output_path = output_path.resolve()
    if output_path.exists():
        raise RevisionError(f"output_exists:{output_path}")
    payload = deepcopy(_load_object(candidate_path, "candidate"))
    # Warning proposals and reviewer attestations are bound to the exact old
    # after bytes. A revision must obtain a fresh validator request instead of
    # replaying any previous resolution or review state.
    for field in STALE_WARNING_REVIEW_FIELDS:
        payload.pop(field, None)
    after_text = _read_utf8(after_path, "after")
    anchors = payload.get("anchors")
    if not isinstance(anchors, list) or not anchors:
        raise RevisionError("candidate_anchors_missing")

    updates = anchor_updates or {}
    anchor_ids: set[str] = set()
    for raw_anchor in anchors:
        if not isinstance(raw_anchor, dict):
            raise RevisionError("candidate_anchor_invalid")
        anchor_id = raw_anchor.get("id")
        if not isinstance(anchor_id, str) or not anchor_id:
            raise RevisionError("candidate_anchor_id_invalid")
        if anchor_id in anchor_ids:
            raise RevisionError(f"candidate_anchor_duplicate:{anchor_id}")
        anchor_ids.add(anchor_id)
    for anchor_id in updates:
        if anchor_id not in anchor_ids:
            raise RevisionError(f"unknown_anchor:{anchor_id}")

    for raw_anchor in anchors:
        anchor_id = str(raw_anchor["id"])
        current = raw_anchor.get("after_text")
        if not isinstance(current, str) or not current:
            raise RevisionError(f"candidate_anchor_after_invalid:{anchor_id}")
        replacement = updates.get(anchor_id)
        if replacement is None:
            count = after_text.count(current)
            if count == 0:
                raise RevisionError(f"anchor_update_required:{anchor_id}")
            if count > 1:
                raise RevisionError(f"anchor_after_ambiguous:{anchor_id}")
            continue
        if not isinstance(replacement, str) or not replacement:
            raise RevisionError(f"anchor_update_empty:{anchor_id}")
        count = after_text.count(replacement)
        if count == 0:
            raise RevisionError(f"anchor_after_missing:{anchor_id}")
        if count > 1:
            raise RevisionError(f"anchor_after_ambiguous:{anchor_id}")
        raw_anchor["after_text"] = replacement

    payload["after_path"] = str(after_path)
    payload.pop("supersedes_candidate_sha256", None)
    if supersedes_result_path is not None:
        payload["supersedes_candidate_sha256"] = _previous_hash(supersedes_result_path.resolve())

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(output_path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output_path)
    return payload


def _parse_anchor_updates(values: Sequence[str]) -> dict[str, str]:
    updates: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise RevisionError("--set-anchor must use ID=EXACT_TEXT")
        anchor_id, replacement = value.split("=", 1)
        anchor_id = anchor_id.strip()
        if not anchor_id or not replacement:
            raise RevisionError("--set-anchor must use ID=EXACT_TEXT")
        if anchor_id in updates:
            raise RevisionError(f"duplicate_anchor_update:{anchor_id}")
        updates[anchor_id] = replacement
    return updates


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path, help="previous candidate package JSON")
    parser.add_argument("--after", type=Path, required=True, help="revised candidate body")
    parser.add_argument("--output", type=Path, required=True, help="new candidate package path")
    parser.add_argument(
        "--set-anchor",
        action="append",
        default=[],
        metavar="ID=EXACT_TEXT",
        help="explicit replacement for an anchor that no longer survives; repeatable",
    )
    parser.add_argument(
        "--supersedes-result",
        type=Path,
        help="previous queue result JSON whose candidate hash this revision supersedes",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    try:
        payload = prepare_revision(
            args.candidate,
            args.after,
            args.output,
            anchor_updates=_parse_anchor_updates(args.set_anchor),
            supersedes_result_path=args.supersedes_result,
        )
    except RevisionError as error:
        print(f"revision error: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": "READY",
                "candidate_id": payload.get("candidate_id", ""),
                "output": str(args.output.resolve()),
                "supersedes_candidate_sha256": payload.get("supersedes_candidate_sha256", ""),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
