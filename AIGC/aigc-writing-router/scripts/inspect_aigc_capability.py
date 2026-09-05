#!/usr/bin/env python3
"""Inspect native and adapted interfaces for one or all AIGC packages."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from adapter_core import find_package, package_preflight, read_registry


def inspect(registry: Path, package: str) -> dict:
    payload = read_registry(registry)
    root = registry.resolve().parents[2]
    entries = payload.get("packages", []) if package == "all" else [find_package(payload, package)]
    packages = []
    for entry in entries:
        item = package_preflight(root, entry)
        item.update({
            "kind": entry.get("kind"),
            "route": entry.get("route"),
            "status": entry.get("status"),
            "skill_name": entry.get("skill_name"),
        })
        packages.append(item)
    blocked = [item for item in packages if not item["entrypoints_present"]]
    return {
        "schema": "aigc-capability-inspection/v1",
        "status": "pass" if not blocked else "fail",
        "registered": len(packages),
        "blocked": len(blocked),
        "packages": packages,
    }


def main() -> int:
    skill_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", default="all")
    parser.add_argument("--registry", type=Path, default=skill_root / "references" / "stack-registry.json")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    report = inspect(args.registry.resolve(), args.package)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"AIGC CAPABILITIES {report['status'].upper()} "
            f"registered={report['registered']} blocked={report['blocked']}"
        )
        for item in report["packages"]:
            print(
                f"{item['directory']}: interfaces={','.join(item['interfaces'])} "
                f"offline={item['offline_action']} entrypoints={'ok' if item['entrypoints_present'] else 'missing'} "
                f"network_generation={str(item['network_for_generation']).lower()}"
            )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

