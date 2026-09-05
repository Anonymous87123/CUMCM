#!/usr/bin/env python3
"""Small regression test for prepare_competition_evidence.py."""

from __future__ import annotations

import json
import hashlib
import platform
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from prepare_competition_evidence import attach_execution, audit_bundle, init_bundle


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        source = root / "main.tex"
        source.write_text("\\documentclass{article}\\begin{document}x\\end{document}\n", encoding="utf-8")
        files = {}
        for kind, suffix in (("problem", ".pdf"), ("data", ".csv"), ("code", ".py"), ("result", ".json")):
            path = root / f"{kind}{suffix}"
            path.write_text(f"{kind}\n", encoding="utf-8")
            files[kind] = path
        provenance = root / "provenance.json"
        provenance.write_text(json.dumps({
            "files": [{
                "path": str(files["data"]),
                "source_kind": "network",
                "source_url": "https://example.invalid/data.csv",
                "fetched_at": "2026-08-20",
            }],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        class Args:
            pass
        args = Args()
        args.source = source
        args.output_dir = root / "bundle"
        args.problem_type = "A"
        args.provenance = provenance
        args.repro_manifest = None
        args.copy = True
        for kind in ("problem", "data", "code", "result"):
            setattr(args, f"{kind}_file", [files[kind]])
            setattr(args, f"{kind}_dir", [])
        manifest, _ = init_bundle(args)
        report = audit_bundle(manifest)
        assert report["status"] == "review", report
        assert report["counts"] == {"problem": 1, "data": 1, "code": 1, "result": 1}
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        assert payload["policy"]["results_must_be_generated"] is True
        for item in payload["materials"]:
            assert Path(item["path"]).is_file()
        config = root / "config.json"
        config.write_text("{}\n", encoding="utf-8")
        figure = root / "figure.png"
        figure.write_bytes(b"PNG")
        repro = root / "repro.json"
        artifacts = [
            ("analysis_script", files["code"]),
            ("result", files["result"]),
            ("figure", figure),
            ("data_config", config),
        ]
        repro.write_text(json.dumps({
            "run": {
                "command": "python code.py",
                "python_version": platform.python_version(),
                "random_seed": 2026,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "data_config": str(config),
                "packages": {},
            },
            "artifacts": [
                {"role": role, "path": str(path), "sha256": digest(path)}
                for role, path in artifacts
            ],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        executed, _, repro_report = attach_execution(manifest, repro)
        assert repro_report["status"] == "pass", repro_report
        final = audit_bundle(executed, require_execution=True)
        assert final["status"] == "pass", final
        assert final["errors"] == 0, final
        print("PASS test_competition_evidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
