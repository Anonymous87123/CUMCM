#!/usr/bin/env python3
"""Regression test for the locked style-matrix manifest builder."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from adapter_core import sha256_file, write_json
from build_style_benchmark_matrix import _entry


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aigc-matrix-builder-test-") as temp:
        root = Path(temp)
        source = root / "source.tex"
        source.write_text("bounded source paragraph\n", encoding="utf-8")
        dev_suite = root / "dev.json"
        holdout_suite = root / "holdout.json"
        write_json(dev_suite, {"schema": "aigc-style-benchmark-suite/v1", "split": "dev"})
        write_json(holdout_suite, {"schema": "aigc-style-benchmark-suite/v1", "split": "holdout"})
        build = root / "build.json"
        write_json(build, {
            "schema": "aigc-draft-improvement-suite-build/v1",
            "dev": {"suite": str(dev_suite), "sha256": sha256_file(dev_suite), "cases": 3},
            "holdout": {"suite": str(holdout_suite), "sha256": sha256_file(holdout_suite), "cases": 3},
        })
        dev_manifest = root / "dev-manifest.json"
        holdout_manifest = root / "holdout-manifest.json"
        write_json(dev_manifest, {"state": "BLIND_READY"})
        write_json(holdout_manifest, {"state": "BLIND_READY"})
        entry = _entry(root, "research", source, build, dev_manifest, holdout_manifest)
        if entry["dev"]["state"] != "BLIND_READY" or entry["holdout"]["state"] != "BLIND_READY":
            print("FAIL: matrix entry did not preserve manifest states")
            return 1
        holdout_suite.write_text(json.dumps({"split": "drift"}), encoding="utf-8")
        try:
            _entry(root, "research", source, build, dev_manifest, holdout_manifest)
        except ValueError:
            pass
        else:
            print("FAIL: stale suite hash was accepted")
            return 1
    print("style benchmark matrix builder tests: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
