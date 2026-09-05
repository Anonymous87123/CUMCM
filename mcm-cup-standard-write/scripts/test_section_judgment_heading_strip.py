#!/usr/bin/env python3
"""Regression test: nested headings cannot satisfy a public bridge term."""

from __future__ import annotations

from pathlib import Path
import tempfile

from audit_section_judgment_bridges import audit
from test_section_judgment_bridges import packet_for


def chars(*values: str) -> str:
    return "".join(chr(int(value, 16)) for value in values)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="mcm-heading-bridge-") as temp:
        root = Path(temp)
        question = chars("95ee", "9898", "4e00")
        route_heading = chars("6574", "6570", "89c4", "5212", "6a21", "578b", "5efa", "7acb")
        capacity = chars("5bb9", "91cf", "4e0a", "9650")
        feasible = chars("53ef", "884c", "57df")
        source = root / "nested.tex"
        source.write_text(
            "\\section{" + question + "}\n"
            "\\subsection{" + route_heading + "}\n"
            + capacity + "决定变量范围，进入" + feasible + "后再说明数学关系。\n",
            encoding="utf-8",
        )
        index = packet_for(source, root / "T01.json")
        report = audit(source, index)
        assert report["status"] == "fail", report
        assert any(
            item["code"] == "SECTION_BRIDGE_SELECTED_ROUTE_MISSING"
            for item in report["findings"]
        ), report
    print("SECTION JUDGMENT HEADING STRIP TEST PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
