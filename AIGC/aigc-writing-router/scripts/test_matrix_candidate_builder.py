#!/usr/bin/env python3
"""Regression tests for source-derived matrix candidate fixtures."""

from __future__ import annotations

import tempfile
from pathlib import Path

from build_matrix_dev_candidates import build


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="matrix-candidates-") as temp:
        root = Path(temp)
        for document_type, text in (
            ("modeling", "原文段落。\n"),
            ("course-notes", "课程段落。\n"),
            ("research", "研究段落。\n"),
        ):
            # The real anchors are intentionally not duplicated here; the fixture
            # builder must reject unknown source material rather than hallucinate.
            source = root / document_type
            source.mkdir()
            (source / "x.tex").write_text(text, encoding="utf-8")
            try:
                build(source, root / f"out-{document_type}", document_type)
            except ValueError:
                pass
            else:
                raise AssertionError("unknown source anchor was accepted")
    print("matrix candidate builder tests: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
