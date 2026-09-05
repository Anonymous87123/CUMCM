#!/usr/bin/env python3
"""Regression tests for research draft readiness gating."""

from __future__ import annotations

import tempfile
from pathlib import Path

from audit_research_draft_readiness import audit


ABSTRACT = " ".join(
    "This study defines a bounded optimization question and evaluates one method under a fixed budget. "
    "The analysis distinguishes the observed endpoint result from the proposed mechanism and reports the "
    "comparison factors, data scope, uncertainty, and negative cases. The method is assessed against two "
    "baselines with matched preprocessing, stopping rules, and random seeds. Results are reported with the "
    "metric, aggregation, and evaluation budget stated explicitly. The conclusion is limited to the tested "
    "function families and does not claim general superiority beyond that evidence.".split()
)
BODY = (
    "The section states the research object, the comparison boundary, and the evidence used for the claim. "
    "It identifies which factors are fixed, which factor changes, and what result would contradict the proposed interpretation."
)


def _write_clean(root: Path) -> Path:
    main = root / "main.tex"
    child = root / "method.tex"
    child.write_text("\\section{Methodology}\n" + BODY, encoding="utf-8")
    main.write_text(
        "\\documentclass{article}\n\\begin{document}\n"
        f"\\begin{{abstract}}{ABSTRACT}\\end{{abstract}}\n"
        "\\section{Introduction}\n" + BODY + "\n"
        "\\section{Related Work}\n" + BODY + "\n"
        "\\input{method}\n"
        "\\section{Experiments}\n" + BODY + "\n"
        "\\section{Conclusion}\n" + BODY + "\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    return main


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="research-readiness-") as temp:
        root = Path(temp)
        clean = _write_clean(root)
        passed = audit(clean)
        assert passed["status"] == "pass", passed
        assert passed["humanization_decision"] == "READY_FOR_PROTECTED_REWRITE"
        assert passed["metrics"]["tex_files"] == 2

        bad = root / "bad.tex"
        bad.write_text(
            "\\documentclass{IEEEtran}\n\\begin{document}\n"
            "\\author{IEEE Publication Technology, Staff, IEEE}\n"
            "\\begin{abstract}A partial abstract.\\end{abstract}\n"
            "\\section{Introduction}\nThe main contributions are summarized as follows:\n"
            "The remainder of this paper is organized as follows.\n"
            "\\section{Related Work}\n% TODO add sources\n"
            "\\section{Methodology}\n\\label{same}Text with a missing Section~\\ref{missing}.\n"
            "\\section{Experiments}\n\\label{same}\n"
            "\\section{Conclusion}\n\\end{document}\n",
            encoding="utf-8",
        )
        failed = audit(bad)
        codes = {item["code"] for item in failed["findings"]}
        expected = {
            "ABSTRACT_INCOMPLETE", "SECTION_EMPTY_OR_SHELL", "UNRESOLVED_PLACEHOLDER",
            "DUPLICATE_LABELS", "UNRESOLVED_INTERNAL_REFERENCES",
            "TEMPLATE_IDENTITY_RESIDUE", "CONTRIBUTION_PROMISE_EMPTY",
        }
        assert failed["status"] == "fail", failed
        assert expected <= codes, (expected - codes, failed)
        assert failed["claims"]["research_correctness_proven"] is False
    print("research draft readiness tests: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
