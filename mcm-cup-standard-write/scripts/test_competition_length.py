#!/usr/bin/env python3
"""Positive and negative tests for the compiled body-page gate."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from audit_competition_length import audit


FIELDS = (
    "problem_data_basis",
    "variables_scope",
    "mathematical_relation",
    "solver_implementation",
    "result",
    "interpretation",
    "validation",
    "boundary",
)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="mcm-length-") as temp_dir:
        root = Path(temp_dir)
        tex = root / "main.tex"
        aux = root / "main.aux"
        coverage = root / "coverage.json"
        tex.write_text(
            r"\label{mcm-body-start} \label{mcm-q1-start} "
            + " ".join(f"token_{field}" for field in FIELDS)
            + r" \label{mcm-q1-end} \label{mcm-body-end}",
            encoding="utf-8",
        )
        aux.write_text(
            r"\newlabel{mcm-body-start}{{1}{3}{x}{section.1}{}}" "\n"
            r"\newlabel{mcm-body-end}{{9}{29}{y}{section.9}{}}",
            encoding="utf-8",
        )
        coverage.write_text(json.dumps({
            "questions": [{
                "id": "Q1",
                "start_label": "mcm-q1-start",
                "end_label": "mcm-q1-end",
                "evidence": {field: [f"token_{field}"] for field in FIELDS},
            }]
        }), encoding="utf-8")
        good = audit(tex, aux, coverage, 25, 30)
        if good["status"] != "pass" or good["body_pages"] != 27:
            print("FAIL: valid 27-page body did not pass", good)
            return 1

        aux.write_text(
            r"\newlabel{mcm-body-start}{{1}{3}{x}{section.1}{}}" "\n"
            r"\newlabel{mcm-body-end}{{9}{14}{y}{section.9}{}}",
            encoding="utf-8",
        )
        short = audit(tex, aux, coverage, 25, 30)
        if not any(item["code"] == "BODY_TOO_SHORT" for item in short["findings"]):
            print("FAIL: short body was not rejected", short)
            return 1

        tex.write_text(
            r"\label{mcm-q1-start} token_problem_data_basis \label{mcm-q1-end}",
            encoding="utf-8",
        )
        aux.write_text(
            r"\newlabel{mcm-body-start}{{1}{3}{x}{section.1}{}}" "\n"
            r"\newlabel{mcm-body-end}{{9}{29}{y}{section.9}{}}",
            encoding="utf-8",
        )
        missing = audit(tex, aux, coverage, 25, 30)
        if not any(item["code"] == "QUESTION_COVERAGE_MISSING" for item in missing["findings"]):
            print("FAIL: missing question evidence was not rejected", missing)
            return 1

        # A token in another question must not satisfy Q1 coverage.
        tex.write_text(
            r"\label{mcm-q1-start} token_problem_data_basis \label{mcm-q1-end} "
            r"\label{mcm-q2-start} token_result \label{mcm-q2-end}",
            encoding="utf-8",
        )
        scoped = audit(tex, aux, coverage, 25, 30)
        missing_fields = {
            item.get("field") for item in scoped["findings"]
            if item["code"] == "QUESTION_COVERAGE_MISSING"
        }
        if "result" not in missing_fields:
            print("FAIL: evidence from another question leaked into Q1", scoped)
            return 1

        tex.write_text(
            r"\label{mcm-body-start} "
            r"\label{mcm-q1-start} "
            + " ".join(f"q1_{field}" for field in FIELDS)
            + r" \label{mcm-q2-start} "
            + " ".join(f"q2_{field}" for field in FIELDS)
            + r" \label{mcm-q1-end} \label{mcm-q2-end} "
            r"\label{mcm-body-end}",
            encoding="utf-8",
        )
        coverage.write_text(json.dumps({
            "questions": [
                {
                    "id": question_id,
                    "start_label": f"mcm-{question_id.casefold()}-start",
                    "end_label": f"mcm-{question_id.casefold()}-end",
                    "evidence": {field: [f"{question_id.casefold()}_{field}"] for field in FIELDS},
                }
                for question_id in ("Q1", "Q2")
            ]
        }), encoding="utf-8")
        overlap = audit(tex, aux, coverage, 25, 30)
        if not any(item["code"] == "QUESTION_SCOPE_OVERLAP" for item in overlap["findings"]):
            print("FAIL: overlapping question spans were not rejected", overlap)
            return 1

        tex.write_text(
            r"\label{mcm-body-start}\label{mcm-body-start}"
            r"\label{mcm-q1-start}\label{mcm-q1-end}\label{mcm-body-end}",
            encoding="utf-8",
        )
        duplicate_body = audit(tex, aux, coverage, 25, 30)
        if not any(item["code"] == "BODY_SCOPE_LABEL_CARDINALITY" for item in duplicate_body["findings"]):
            print("FAIL: duplicate body boundary labels were not rejected", duplicate_body)
            return 1

    print("PASS: 25--30 page range, disjoint question spans and question coverage are enforced.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
