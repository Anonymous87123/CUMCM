#!/usr/bin/env python3
"""Ensure a TeX preamble cannot make the abstract unit unresolved."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile


SKILLS_ROOT = Path(__file__).resolve().parents[3]
PREPARE = (
    SKILLS_ROOT / "AIGC" / "humanize-academic-chinese" / "scripts"
    / "prepare_humanize_long_document.py"
)


def require(condition: bool, message: str, payload: object) -> None:
    if not condition:
        raise AssertionError(message + "\n" + json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="humanize-preamble-") as temp:
        root = Path(temp)
        source = root / "main.tex"
        run_dir = root / "run"
        source.write_text(
            "% !TeX program = xelatex\n"
            "\\documentclass{ctexart}\n"
            "\\renewcommand{\\headrulewidth}{0pt}\n"
            "\\begin{document}\n"
            "\\begin{abstract}\n"
            "观测序列在第六个时段出现折点，相邻测点没有同步变化。\n"
            "\\end{abstract}\n"
            "\\section{模型建立}\n"
            "边界项由守恒关系直接给出，状态量按小时更新。\n"
            "\\end{document}\n",
            encoding="utf-8",
        )
        completed = subprocess.run(
            [
                sys.executable, str(PREPARE), str(source), "--output", str(run_dir),
                "--scene", "MODELING", "--intensity", "BALANCED",
            ],
            text=True, encoding="utf-8", errors="replace", capture_output=True,
            timeout=120, check=False,
        )
        require(completed.returncode in {0, 2}, "prepare did not return a valid state", completed.stderr)
        with (run_dir / "coverage_ledger.csv").open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        require(rows, "prepare produced no units", rows)
        unresolved = [row for row in rows if row.get("status") == "UNRESOLVED"]
        preamble = [row for row in rows if "tex_preamble_locked" in row.get("notes", "")]
        abstract = [
            row for row in rows
            if int(row.get("start_line", "0")) >= 4
            and int(row.get("end_line", "0")) <= 7
        ]
        require(not unresolved, "preamble macro definition leaked into an unresolved body unit", rows)
        require(
            len(preamble) == 1 and preamble[0]["status"] == "SKIPPED_PROTECTED",
            "TeX preamble was not locked as one protected unit",
            rows,
        )
        require(
            any(row["status"] == "PENDING" for row in abstract),
            "abstract did not remain editable after the preamble boundary",
            rows,
        )

    print("PASS: TeX preamble is locked separately and the abstract remains editable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
