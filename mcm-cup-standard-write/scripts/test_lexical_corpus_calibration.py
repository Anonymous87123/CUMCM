#!/usr/bin/env python3
"""Regression checks for CUMCM human-corpus lexical calibration."""

from __future__ import annotations

from audit_lexical_corpus_calibration import DEFAULT_INDEX, DEFAULT_LEXICON, audit


def main() -> int:
    report = audit(DEFAULT_LEXICON, DEFAULT_INDEX)
    rows = {item["phrase"]: item for item in report["phrases"]}
    if (
        report["status"] != "pass"
        or report["papers"] != 59
        or report["strict_inventory_entries"] != 1423
        or rows["更好"]["disposition"] != "contextual-human-attested"
        or rows["更好"]["paper_count"] < 20
        or rows["可视化"]["disposition"] != "contextual-human-attested"
        or rows["我会"]["disposition"] != "strict-unattested"
    ):
        print(report)
        return 1
    print("PASS: MCM lexical hard blockers are calibrated against all 59 verified human papers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
