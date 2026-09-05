#!/usr/bin/env python3
"""Positive and negative tests for the reproducibility manifest gate."""

from __future__ import annotations

import hashlib
import json
import platform
import tempfile
from pathlib import Path

from audit_repro_manifest import audit


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="mcm-repro-") as temp_dir:
        root = Path(temp_dir)
        files = {
            "analysis_script": root / "model.py",
            "result": root / "result.json",
            "figure": root / "figure.pdf",
            "data_config": root / "cleaning.json",
        }
        contents = {
            "analysis_script": b"print('run')\n",
            "result": b'{"score": 1.25}\n',
            "figure": b"%PDF-fixture\n",
            "data_config": b'{"missing": "median"}\n',
        }
        for role, path in files.items():
            path.write_bytes(contents[role])
        manifest = root / "repro.json"
        payload = {
            "run": {
                "command": "python model.py --config cleaning.json",
                "python_version": platform.python_version(),
                "random_seed": 20260814,
                "generated_at": "2026-08-14T12:00:00+08:00",
                "data_config": "cleaning.json",
                "packages": {"pip": "fixture-version"},
                "verify_runtime": False,
            },
            "artifacts": [
                {"path": path.name, "sha256": digest(path), "role": role}
                for role, path in files.items()
            ],
        }
        manifest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        good = audit(manifest)
        if good["status"] != "pass":
            print("FAIL: complete reproducibility manifest failed", good)
            return 1

        files["result"].write_text('{"score": 9.99}\n', encoding="utf-8")
        stale = audit(manifest)
        if not any(item["code"] == "ARTIFACT_HASH_MISMATCH" for item in stale["findings"]):
            print("FAIL: stale result hash was not rejected", stale)
            return 1

        payload["run"].pop("random_seed")
        payload["artifacts"] = payload["artifacts"][:-1]
        manifest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        incomplete = audit(manifest)
        codes = {item["code"] for item in incomplete["findings"]}
        if not {"RUN_FIELD_MISSING", "ARTIFACT_ROLE_MISSING"}.issubset(codes):
            print("FAIL: incomplete run metadata was not rejected", incomplete)
            return 1

    print("PASS: run metadata, artifact roles and SHA-256 drift are enforced.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
