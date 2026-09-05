#!/usr/bin/env python3
"""Validate independent same-source writing candidates and their selection.

Public interface:
    python audit_candidate_portfolio.py <portfolio.json> --format text|json
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import re
from pathlib import Path


ACADEMIC_TYPES = {
    "mcm", "modeling", "research", "course-notes", "academic-mixed",
    "academic-en", "medical-en",
}
ALLOWED_PROVIDERS = {
    "mcm": {"humanize-academic-chinese", "baibai-aigc"},
    "modeling": {"humanize-academic-chinese", "baibai-aigc"},
    "research": {"humanize-academic-chinese", "baibai-aigc"},
    "course-notes": {"humanize-academic-chinese", "baibai-aigc"},
    "academic-mixed": {"humanize-academic-chinese", "baibai-aigc"},
    "academic-en": {"academic-humanizer"},
    "medical-en": {"humanizer-medical-academic", "academic-humanizer"},
    "technical": {
        "humanizer", "humanizer-brandonwise", "humanizer-voice-profile",
        "humanize-english-editor", "patina",
    },
    "general-en": {
        "humanizer", "humanizer-brandonwise", "humanizer-voice-profile",
        "humanize-english-editor", "patina",
    },
    "general-zh": {"humanizer-zh", "humanize-chinese-copy-lab", "patina"},
}
PASS_STATES = {"pass"}
# Do not split identifiers such as Q38, model_v2, or A1 into stray number tokens.
NUMBER_RE = re.compile(r"(?<![A-Za-z0-9_])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?%?(?![A-Za-z0-9_])")
TEX_COMMAND_RE = re.compile(r"\\[A-Za-z@]+\*?")
TEX_KEY_RE = re.compile(r"\\(?:label|ref|eqref|autoref|cite|citep|citet)\{[^{}]+\}")
INLINE_MATH_RE = re.compile(r"(?<![\\$])\$(?!\$)(.*?)(?<![\\$])\$(?!\$)", re.DOTALL)
DOLLAR_DISPLAY_RE = re.compile(r"(?<!\\)\$\$(.*?)(?<!\\)\$\$", re.DOTALL)
DISPLAY_MATH_RE = re.compile(r"\\\[(.*?)\\\]", re.DOTALL)
ENV_MATH_RE = re.compile(
    r"\\begin\{(equation\*?|align\*?|gather\*?|multline\*?)\}(.*?)"
    r"\\end\{\1\}",
    re.DOTALL,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_path(base: Path, raw: object) -> Path:
    path = Path(str(raw))
    return path if path.is_absolute() else (base / path).resolve()


def protected_inventory(text: str) -> dict[str, Counter]:
    return {
        "numbers": Counter(NUMBER_RE.findall(text)),
        "tex_commands": Counter(TEX_COMMAND_RE.findall(text)),
        "tex_keys": Counter(TEX_KEY_RE.findall(text)),
        "inline_math": Counter(match.group(1) for match in INLINE_MATH_RE.finditer(text)),
        "dollar_display_math": Counter(match.group(1) for match in DOLLAR_DISPLAY_RE.finditer(text)),
        "display_math": Counter(match.group(1) for match in DISPLAY_MATH_RE.finditer(text)),
        "math_environments": Counter(
            f"{match.group(1)}\n{match.group(2)}" for match in ENV_MATH_RE.finditer(text)
        ),
    }


def audit(manifest_path: Path) -> dict:
    payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    findings: list[dict] = []
    base = manifest_path.resolve().parent

    if payload.get("schema") != "aigc-candidate-portfolio/v1":
        findings.append({"severity": "error", "code": "SCHEMA_MISMATCH"})

    document_type = str(payload.get("document_type", ""))
    if document_type not in ALLOWED_PROVIDERS:
        findings.append({"severity": "error", "code": "UNKNOWN_DOCUMENT_TYPE", "value": document_type})

    source = payload.get("source", {})
    source_path = resolve_path(base, source.get("path", ""))
    declared_source_sha = str(source.get("sha256", ""))
    actual_source_sha = None
    if not source_path.is_file():
        findings.append({"severity": "error", "code": "SOURCE_FILE_MISSING", "path": str(source_path)})
    else:
        actual_source_sha = sha256_file(source_path)
        if declared_source_sha != actual_source_sha:
            findings.append({
                "severity": "error",
                "code": "SOURCE_HASH_MISMATCH",
                "declared": declared_source_sha,
                "actual": actual_source_sha,
            })
    source_text = source_path.read_text(encoding="utf-8-sig") if source_path.is_file() else ""
    source_inventory = protected_inventory(source_text)

    candidates = payload.get("candidates", [])
    if not isinstance(candidates, list):
        findings.append({"severity": "error", "code": "CANDIDATES_NOT_LIST"})
        candidates = []
    max_candidates = 2 if document_type in ACADEMIC_TYPES else 1
    if len(candidates) > max_candidates:
        findings.append({
            "severity": "error",
            "code": "TOO_MANY_CANDIDATES",
            "actual": len(candidates),
            "maximum": max_candidates,
        })

    seen_ids: set[str] = set()
    seen_providers: set[str] = set()
    candidate_by_id: dict[str, dict] = {}
    allowed = ALLOWED_PROVIDERS.get(document_type, set())

    for candidate in candidates:
        candidate_id = str(candidate.get("id", ""))
        provider = str(candidate.get("provider", ""))
        if not candidate_id or candidate_id in seen_ids:
            findings.append({"severity": "error", "code": "CANDIDATE_ID_INVALID", "id": candidate_id})
        else:
            seen_ids.add(candidate_id)
            candidate_by_id[candidate_id] = candidate
        if provider not in allowed:
            findings.append({
                "severity": "error",
                "code": "PROVIDER_NOT_ALLOWED",
                "id": candidate_id,
                "provider": provider,
            })
        if provider in seen_providers:
            findings.append({
                "severity": "error",
                "code": "DUPLICATE_PROVIDER_BRANCH",
                "provider": provider,
            })
        seen_providers.add(provider)

        if candidate.get("input_sha256") != declared_source_sha:
            findings.append({
                "severity": "error",
                "code": "CANDIDATE_NOT_FROM_SOURCE",
                "id": candidate_id,
            })
        if candidate.get("parent_candidate") is not None:
            findings.append({
                "severity": "error",
                "code": "SERIAL_CANDIDATE_CHAIN",
                "id": candidate_id,
            })
        if candidate.get("pass_count") != 1:
            findings.append({
                "severity": "error",
                "code": "PASS_COUNT_MUST_BE_ONE",
                "id": candidate_id,
            })
        if provider == "baibai-aigc" and candidate.get("round") != 1:
            findings.append({
                "severity": "error",
                "code": "BAIBAI_ROUND_ONE_REQUIRED",
                "id": candidate_id,
            })

        output_path = resolve_path(base, candidate.get("output_path", ""))
        if source_path.is_file() and output_path == source_path.resolve():
            findings.append({
                "severity": "error",
                "code": "CANDIDATE_OVERWRITES_SOURCE",
                "id": candidate_id,
            })
        if not output_path.is_file():
            findings.append({
                "severity": "error",
                "code": "CANDIDATE_FILE_MISSING",
                "id": candidate_id,
                "path": str(output_path),
            })
        else:
            actual_output_sha = sha256_file(output_path)
            if candidate.get("output_sha256") != actual_output_sha:
                findings.append({
                    "severity": "error",
                    "code": "CANDIDATE_HASH_MISMATCH",
                    "id": candidate_id,
                    "actual": actual_output_sha,
                })
            output_text = output_path.read_text(encoding="utf-8-sig")
            output_inventory = protected_inventory(output_text)
            for inventory_name, source_values in source_inventory.items():
                if output_inventory[inventory_name] != source_values:
                    findings.append({
                        "severity": "error",
                        "code": "PROTECTED_INVENTORY_DRIFT",
                        "id": candidate_id,
                        "inventory": inventory_name,
                        "source": dict(source_values),
                        "candidate": dict(output_inventory[inventory_name]),
                    })

    selection = payload.get("selection", {})
    accepted = selection.get("accepted")
    human_review = selection.get("human_review", "pending")
    reason = str(selection.get("reason", "")).strip()
    decision_status = "pending"

    if accepted in {None, ""}:
        if human_review == "accepted":
            findings.append({"severity": "error", "code": "ACCEPTED_SELECTION_MISSING"})
    elif accepted == "SOURCE":
        if human_review != "accepted" or not reason:
            findings.append({"severity": "error", "code": "SOURCE_SELECTION_REQUIRES_HUMAN_REASON"})
        else:
            decision_status = "source-accepted"
    elif accepted not in candidate_by_id:
        findings.append({"severity": "error", "code": "UNKNOWN_ACCEPTED_CANDIDATE", "id": accepted})
    else:
        selected = candidate_by_id[accepted]
        for field in ("invariant_status", "domain_audit_status", "document_status"):
            if selected.get(field) not in PASS_STATES:
                findings.append({
                    "severity": "error",
                    "code": "ACCEPTED_CANDIDATE_GATE_FAILED",
                    "id": accepted,
                    "field": field,
                    "value": selected.get(field),
                })
        if human_review != "accepted" or not reason:
            findings.append({
                "severity": "error",
                "code": "CANDIDATE_SELECTION_REQUIRES_HUMAN_REASON",
                "id": accepted,
            })
        else:
            decision_status = "candidate-accepted"

    errors = sum(item["severity"] == "error" for item in findings)
    if errors:
        decision_status = "invalid"
    return {
        "status": "pass" if errors == 0 else "fail",
        "decision_status": decision_status,
        "manifest": str(manifest_path.resolve()),
        "document_type": document_type,
        "source_sha256": actual_source_sha,
        "candidate_count": len(candidates),
        "accepted": accepted,
        "errors": errors,
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    report = audit(args.manifest.resolve())
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"CANDIDATE PORTFOLIO {report['status'].upper()} "
            f"decision={report['decision_status']} candidates={report['candidate_count']} "
            f"errors={report['errors']}"
        )
        print(f"accepted={report['accepted'] or 'NONE'} source_sha256={report['source_sha256'] or 'UNKNOWN'}")
        for finding in report["findings"]:
            detail = ", ".join(
                f"{key}={value}" for key, value in finding.items() if key not in {"severity", "code"}
            )
            print(f"[{finding['severity'].upper()}] {finding['code']}: {detail}")
    if report["status"] != "pass":
        return 1
    return 0 if report["decision_status"] != "pending" else 2


if __name__ == "__main__":
    raise SystemExit(main())
