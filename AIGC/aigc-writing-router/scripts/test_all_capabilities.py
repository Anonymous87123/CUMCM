#!/usr/bin/env python3
"""Exercise one meaningful offline adapter action for every registered package."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile

from adapter_core import read_registry
from run_aigc_adapter import execute


def require(condition: bool, message: str, payload: object) -> None:
    if not condition:
        raise AssertionError(message + "\n" + json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> int:
    skill_root = Path(__file__).resolve().parents[1]
    registry = skill_root / "references" / "stack-registry.json"
    payload = read_registry(registry)
    packages = payload.get("packages", [])
    require(len(packages) == 21, "expected the complete 21-directory portfolio", {"count": len(packages)})

    exercised: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="aigc-all-capabilities-") as temp:
        root = Path(temp)
        source = root / "source.tex"
        candidate = root / "candidate.tex"
        sample = (
            "问题二中，参数 0.35 改变后，首次触发对象由 A 转为 B。\n\n"
            "由 $x^2=1$ 可得结果 3.2，见式 \\eqref{eq:a} 与文献 \\cite{r1}。"
            "\\label{eq:a}\n"
        )
        source.write_text(sample, encoding="utf-8")
        candidate.write_text(sample, encoding="utf-8")

        for entry in packages:
            directory = str(entry["directory"])
            action = str(entry["adapter"]["offline_action"])
            output = root / "runs" / directory
            report = execute(registry, directory, action, source=source, output_dir=output)
            require(
                report["status"] in {"pass", "ready"},
                f"offline adapter action failed for {directory}",
                report,
            )
            require(any(output.iterdir()), f"adapter emitted no artifact for {directory}", report)
            if "candidate" in entry["adapter"]["interfaces"]:
                verified = execute(
                    registry,
                    directory,
                    "verify-candidate",
                    source=source,
                    candidate=candidate,
                    output_dir=output / "verify",
                )
                require(verified["status"] == "pass", f"candidate verification failed for {directory}", verified)
            exercised.append({"directory": directory, "action": action, "status": report["status"]})

        tiany = skill_root.parent / "humanize-main(Tiany)" / "scripts" / "compare_candidates.py"
        completed = subprocess.run(
            ["python", str(tiany), str(source), str(candidate), "--format", "json"],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=30,
            check=False,
        )
        require(completed.returncode == 0, "reconstructed Tiany comparator failed", {
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        })
        tiany_report = json.loads(completed.stdout)
        require(
            tiany_report["status"] == "pass" and tiany_report["automatic_acceptance"] is False,
            "Tiany comparator did not preserve its human-decision boundary",
            tiany_report,
        )

        drifted = root / "candidate-drifted.tex"
        drifted.write_text(sample.replace("3.2", "3.3"), encoding="utf-8")
        negative = execute(
            registry,
            "humanize-academic-chinese",
            "verify-candidate",
            source=source,
            candidate=drifted,
            output_dir=root / "negative-verify",
        )
        require(
            negative["status"] == "fail"
            and any(item["code"] == "PROTECTED_INVENTORY_DRIFT" for item in negative["findings"]),
            "adapter did not reject a numeric drift",
            negative,
        )

    print(
        "PASS: 21/21 packages expose a working offline adapter action; "
        "all candidate-capable packages pass protected-inventory verification; Tiany comparator runs."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
