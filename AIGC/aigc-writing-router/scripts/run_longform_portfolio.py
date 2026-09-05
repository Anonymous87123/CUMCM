#!/usr/bin/env python3
"""Create and audit a resumable long-form writing portfolio.

Public interface:
    python run_longform_portfolio.py init <main.tex> --output-dir RUN
        --document-type mcm --problem-type A [gate options]
    python run_longform_portfolio.py register <manifest.json> <candidate.tex>
        --provider NAME --candidate-id ID [--output NEW_MANIFEST]
    python run_longform_portfolio.py lock-generation <manifest.json>
        --workbench modeling-workbench.json --preflight reasoning-preflight.json
        --style-retrieval-plan style-retrieval-plan.json
        --authoring-brief section-authoring-brief.json
        --drafting-packet-index section-drafting-packets/packet-index.json
    python run_longform_portfolio.py select <manifest.json> --candidate-id ID
        --reviewer NAME --reason TEXT [--blind-score SCORE.json]

    A formal blind score must be an aigc-blind-scoring/v2 report with an audited
    merge-report evidence record and majority-backed effective human coverage.
    python run_longform_portfolio.py run-gates <manifest.json> --output-dir RUN
    --portfolio-plan portfolio-plan.json
    --coverage coverage.json --math-contract math.json
    --repro-manifest repro.json --result-manifest results.json
    --workbench modeling-workbench.json --preflight reasoning-preflight.json
    --reasoning-review reasoning-review.json --evidence-bundle evidence-executed.json
    --style-retrieval-plan style-retrieval-plan.json
    --authoring-brief section-authoring-brief.json
    --drafting-packet-index section-drafting-packets/packet-index.json
    --drafting-usage section-drafting-usage.json
    --judgment-ledger judgment-ledger.json
    python run_longform_portfolio.py finalize <manifest.json> --reviewer NAME
        --review-note TEXT --checked ITEM [--checked ITEM ...]
    python run_longform_portfolio.py audit <manifest.json> --format text|json

The ledger freezes source files, records candidate lineage, runs known local
quality gates against the human-selected target, and locks release evidence. It
never runs a writer, overwrites the authority manuscript, or selects a candidate.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

from adapter_core import protected_inventory, serialise_inventory, sha256_file, write_json
from merge_style_benchmark_ratings import audit_merge_report
from run_aigc_adapter import execute as run_adapter
from run_style_benchmark import _writing_rule_snapshot


SCHEMA = "aigc-longform-portfolio/v1"
SOURCE_ID = "SOURCE"
REQUIRED_RELEASE_GATES = {
    "generation-input-lock", "portfolio-selection", "evidence-bundle", "reasoning-preflight", "modeling-workbench", "corpus-overlap", "reasoning-review", "judgment-ledger",
    "manuscript", "math-semantics", "reproducibility", "result-sync",
    "academic-style-release", "public-reasoning-scaffold", "style-retrieval-plan", "section-authoring-brief", "public-judgment-bridges", "auxiliary-roles", "compile", "competition-length", "content-density",
    "section-drafting-packets", "section-drafting-usage",
}
RENDER_CHECKS = {
    "title", "cross-page-tables", "formulas", "captions", "references",
    "appendix", "overflow-and-garbled-text",
}
LATEX_LOG_BLOCKERS = {
    "undefined-reference": re.compile(
        r"LaTeX Warning: (?:Reference|Citation).*undefined|There were undefined references",
        re.I,
    ),
    "missing-file": re.compile(r"(?:LaTeX Error: )?File .+ not found", re.I),
    "missing-character": re.compile(r"Missing character:", re.I),
    "overfull-box": re.compile(r"Overfull \\[hv]box", re.I),
}
LATEX_LOG_WARNINGS = {
    "underfull-box": re.compile(r"Underfull \\[hv]box", re.I),
    "font-warning": re.compile(r"LaTeX Font Warning:", re.I),
}
INCLUDE_RE = re.compile(r"\\(?:input|include)\s*\{([^{}]+)\}")
INCLUDE_GRAPHICS_RE = re.compile(r"\\includegraphics\*?\s*(?:\[[^]]*\])?\s*\{([^{}]+)\}")
GRAPHICS_PATH_RE = re.compile(r"\\graphicspath\s*\{((?:\{[^{}]*\}\s*)+)\}")
GRAPHICS_DIR_RE = re.compile(r"\{([^{}]*)\}")
BIBLIOGRAPHY_RE = re.compile(r"\\bibliography\s*\{([^{}]+)\}")
ADD_BIB_RE = re.compile(r"\\addbibresource\s*(?:\[[^]]*\])?\s*\{([^{}]+)\}")
LISTING_RE = re.compile(r"\\lstinputlisting\s*(?:\[[^]]*\])?\s*\{([^{}]+)\}")
MINTED_RE = re.compile(r"\\inputminted\s*(?:\[[^]]*\])?\s*\{[^{}]+\}\s*\{([^{}]+)\}")
DOCUMENT_CLASS_RE = re.compile(r"\\documentclass\s*(?:\[[^]]*\])?\s*\{([^{}]+)\}")
USE_PACKAGE_RE = re.compile(r"\\usepackage\s*(?:\[[^]]*\])?\s*\{([^{}]+)\}")
BIB_STYLE_RE = re.compile(r"\\bibliographystyle\s*\{([^{}]+)\}")
HEADING_START_RE = re.compile(r"\\(section|subsection|subsubsection)\*?\s*\{")
LABEL_RE = re.compile(r"\\label\{([^{}]+)\}")
REFERENCE_RE = re.compile(r"\\(?:ref|eqref|autoref|pageref)\{([^{}]+)\}")
CITATION_RE = re.compile(r"\\(?:cite|citep|citet|parencite)\s*(?:\[[^]]*\])?\s*\{([^{}]+)\}")
FORMULA_RE = re.compile(
    r"\\begin\{(?:equation\*?|align\*?|gather\*?|multline\*?)\}.*?"
    r"\\end\{(?:equation\*?|align\*?|gather\*?|multline\*?)\}"
    r"|\$\$.*?\$\$|\\\[.*?\\\]|(?<!\$)\$(?!\$)(?:\\.|[^$])*\$",
    re.DOTALL,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_manifest(path: Path) -> dict:
    payload = json.loads(path.resolve().read_text(encoding="utf-8-sig"))
    if payload.get("schema") != SCHEMA:
        raise ValueError("long-form manifest schema mismatch")
    return payload


def _next_manifest_path(manifest_path: Path, suffix: str, output_path: Path | None) -> Path:
    source = manifest_path.resolve()
    destination = output_path.resolve() if output_path else source.with_name(f"{source.stem}-{suffix}.json")
    if destination == source:
        raise ValueError("write a new manifest path; the ledger is append-only")
    if destination.exists():
        raise FileExistsError(f"output manifest already exists: {destination}")
    return destination


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _writing_rule_tree(records: list[dict], path_key: str, hash_key: str) -> str:
    rows = [f"{item.get(path_key, '')}\0{item.get(hash_key, '')}" for item in records]
    return sha256_text("\n".join(sorted(rows)))


def _snapshot_generation_writing_rules(run_dir: Path) -> dict:
    current = _writing_rule_snapshot()
    snapshot_dir = run_dir / "writing-rule-snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for index, item in enumerate(current, start=1):
        source = Path(str(item["path"])).resolve()
        snapshot = snapshot_dir / f"{index:03d}-{source.name}"
        shutil.copy2(source, snapshot)
        files.append({
            "source_path": str(source),
            "source_sha256": str(item["sha256"]),
            "bytes": int(item["bytes"]),
            "snapshot_path": str(snapshot.resolve()),
            "snapshot_sha256": sha256_file(snapshot),
        })
    return {
        "status": "current-bound",
        "count": len(files),
        "tree_sha256": _writing_rule_tree(files, "source_path", "source_sha256"),
        "files": files,
    }


def _strip_tex_comments(text: str) -> str:
    cleaned = []
    for line in text.splitlines():
        cutoff = len(line)
        for index, char in enumerate(line):
            if char != "%":
                continue
            backslashes = 0
            cursor = index - 1
            while cursor >= 0 and line[cursor] == "\\":
                backslashes += 1
                cursor -= 1
            if backslashes % 2 == 0:
                cutoff = index
                break
        cleaned.append(line[:cutoff])
    return "\n".join(cleaned)


def _balanced_argument(text: str, opening_brace: int) -> tuple[str, int] | None:
    depth = 0
    escaped = False
    for index in range(opening_brace, len(text)):
        char = text[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[opening_brace + 1:index], index + 1
    return None


def headings(text: str) -> list[dict]:
    found: list[dict] = []
    for match in HEADING_START_RE.finditer(text):
        opening = text.find("{", match.start(), match.end())
        argument = _balanced_argument(text, opening)
        if argument is None:
            continue
        title, end = argument
        found.append({
            "level": match.group(1),
            "title": title.strip(),
            "start": match.start(),
            "heading_end": end,
        })
    return found


def parse_chunks(path: Path, text: str) -> list[dict]:
    starts = headings(text)
    chunks: list[dict] = []
    if not starts:
        starts = [{"level": "document", "title": path.name, "start": 0, "heading_end": 0}]
    elif starts[0]["start"] > 0:
        starts.insert(0, {
            "level": "document-prefix", "title": f"{path.name} prefix",
            "start": 0, "heading_end": 0,
        })
    for index, item in enumerate(starts):
        start = int(item["start"])
        end = int(starts[index + 1]["start"]) if index + 1 < len(starts) else len(text)
        body = text[start:end]
        chunks.append({
            "id": "",
            "source_file": str(path),
            "level": item["level"],
            "title": item["title"],
            "line_start": text.count("\n", 0, start) + 1,
            "line_end": text.count("\n", 0, end) + 1,
            "sha256": sha256_text(body),
            "characters": len(body),
            "paragraphs": len([part for part in re.split(r"\n\s*\n", body) if part.strip()]),
            "formulas": len(FORMULA_RE.findall(body)),
            "labels": LABEL_RE.findall(body),
            "references": REFERENCE_RE.findall(body),
            "citations": CITATION_RE.findall(body),
        })
    return chunks


def discover_tex_tree(main_tex: Path) -> list[Path]:
    discovered: list[Path] = []
    pending = [main_tex.resolve()]
    seen: set[Path] = set()
    while pending:
        path = pending.pop(0).resolve()
        if path in seen:
            continue
        seen.add(path)
        if not path.is_file():
            continue
        discovered.append(path)
        text = _strip_tex_comments(path.read_text(encoding="utf-8-sig"))
        for raw in INCLUDE_RE.findall(text):
            candidate = (path.parent / raw.strip()).resolve()
            if not candidate.is_file() and not candidate.suffix:
                candidate = candidate.with_suffix(".tex")
            if candidate not in seen:
                pending.append(candidate)
    return discovered


def _resolve_resource(
    base: Path,
    raw: str,
    extensions: tuple[str, ...],
    search_dirs: list[Path] | None = None,
) -> Path | None:
    value = raw.strip()
    if not value or "\\" in value or "#" in value:
        raise ValueError(f"dynamic release resource path is unsupported: {raw}")
    roots = search_dirs or [base]
    for root in roots:
        candidate = (root / value).resolve()
        choices = [candidate]
        if not candidate.suffix:
            choices.extend(candidate.with_suffix(extension) for extension in extensions)
        for choice in choices:
            if choice.is_file():
                return choice
    return None


def discover_compile_resources(main_tex: Path) -> list[Path]:
    main_tex = main_tex.resolve()
    tex_files = discover_tex_tree(main_tex)
    resources: list[Path] = list(tex_files)
    required: list[tuple[Path, str, tuple[str, ...], list[Path] | None, str]] = []
    optional_local: list[tuple[Path, str, str]] = []
    for tex_path in tex_files:
        text = _strip_tex_comments(tex_path.read_text(encoding="utf-8-sig"))
        graphics_dirs = [tex_path.parent]
        for block in GRAPHICS_PATH_RE.findall(text):
            graphics_dirs.extend((tex_path.parent / value.strip()).resolve() for value in GRAPHICS_DIR_RE.findall(block))
        required.extend(
            (tex_path.parent, raw, (".pdf", ".png", ".jpg", ".jpeg", ".eps"), graphics_dirs, "graphic")
            for raw in INCLUDE_GRAPHICS_RE.findall(text)
        )
        for block in BIBLIOGRAPHY_RE.findall(text):
            required.extend(
                (tex_path.parent, raw.strip(), (".bib",), None, "bibliography")
                for raw in block.split(",") if raw.strip()
            )
        required.extend(
            (tex_path.parent, raw, (".bib",), None, "bibliography")
            for raw in ADD_BIB_RE.findall(text)
        )
        required.extend(
            (tex_path.parent, raw, tuple(), None, "listing")
            for raw in LISTING_RE.findall(text) + MINTED_RE.findall(text)
        )
        optional_local.extend((tex_path.parent, raw.strip(), ".cls") for raw in DOCUMENT_CLASS_RE.findall(text))
        for block in USE_PACKAGE_RE.findall(text):
            optional_local.extend(
                (tex_path.parent, raw.strip(), ".sty")
                for raw in block.split(",") if raw.strip()
            )
        optional_local.extend((tex_path.parent, raw.strip(), ".bst") for raw in BIB_STYLE_RE.findall(text))
    for base, raw, extensions, search_dirs, kind in required:
        resolved = _resolve_resource(base, raw, extensions, search_dirs)
        if resolved is None:
            raise FileNotFoundError(f"release {kind} resource is missing: {raw}")
        resources.append(resolved)
    for base, raw, extension in optional_local:
        resolved = _resolve_resource(base, raw, (extension,))
        if resolved is not None:
            resources.append(resolved)
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in resources:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return unique


def _compile_resource_records(main_tex: Path) -> list[dict]:
    main_tex = main_tex.resolve()
    candidate_root = main_tex.parent.resolve()
    records = []
    for resource in discover_compile_resources(main_tex):
        try:
            relative = resource.relative_to(candidate_root)
        except ValueError as exc:
            raise ValueError(
                "release resources must be vendored inside the selected candidate directory: "
                f"{resource}"
            ) from exc
        records.append({
            "relative_path": str(relative),
            "path": str(resource),
            "sha256": sha256_file(resource),
            "bytes": resource.stat().st_size,
        })
    records.sort(key=lambda item: Path(item["relative_path"]).as_posix())
    return records


def _snapshot_relative(main_tex: Path, source: Path) -> Path:
    try:
        return source.relative_to(main_tex.parent)
    except ValueError:
        return Path("external") / f"{sha256_file(source)[:12]}-{source.name}"


def _artifact(raw: str) -> dict:
    if "=" not in raw:
        raise ValueError("--artifact must use KIND=PATH")
    kind, value = raw.split("=", 1)
    path = Path(value).resolve()
    if not kind.strip() or not path.is_file():
        raise ValueError(f"artifact is invalid or missing: {raw}")
    return {"kind": kind.strip(), "path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size}


def gate_plan(
    main_tex: Path | None,
    problem_type: str | None,
    coverage: Path | None,
    aux: Path | None,
    math_contract: Path | None,
    repro_manifest: Path | None,
    result_manifest: Path | None,
    workbench: Path | None,
    preflight: Path | None,
    reasoning_review: Path | None,
    evidence_bundle: Path | None = None,
    style_decisions: Path | None = None,
    portfolio_plan: Path | None = None,
    style_retrieval_plan: Path | None = None,
    authoring_brief: Path | None = None,
    judgment_ledger: Path | None = None,
    drafting_packet_index: Path | None = None,
    drafting_usage: Path | None = None,
) -> list[dict]:
    skills_root = Path(__file__).resolve().parents[3]
    mcm = skills_root / "mcm-cup-standard-write" / "scripts"
    aigc_router = skills_root / "AIGC" / "aigc-writing-router" / "scripts"
    target = str(main_tex) if main_tex is not None else "<human-selected-main.tex>"
    source_target = "<frozen-source-main.tex>"
    workbench_target = str(workbench) if workbench is not None else "<modeling-workbench.json>"
    preflight_target = str(preflight) if preflight is not None else "<reasoning-preflight.json>"
    review_target = str(reasoning_review) if reasoning_review is not None else "<reasoning-review.json>"
    evidence_target = str(evidence_bundle) if evidence_bundle is not None else "<evidence-executed.json>"
    portfolio_target = str(portfolio_plan) if portfolio_plan is not None else "<portfolio-plan.json>"
    style_retrieval_target = str(style_retrieval_plan) if style_retrieval_plan is not None else "<style-retrieval-plan.json>"
    authoring_brief_target = str(authoring_brief) if authoring_brief is not None else "<section-authoring-brief.json>"
    judgment_ledger_target = str(judgment_ledger) if judgment_ledger is not None else "<judgment-ledger.json>"
    drafting_packet_target = str(drafting_packet_index) if drafting_packet_index is not None else "<section-drafting-packets/packet-index.json>"
    drafting_usage_target = str(drafting_usage) if drafting_usage is not None else "<section-drafting-usage.json>"
    style_decisions_arg = f' --decisions "{style_decisions}"' if style_decisions is not None else ""
    gates = [
        {"id": "generation-input-lock", "required": True, "command": "validate pre-candidate generation-input lock and frozen hashes", "manual_followup": "the lock proves timing and input identity, not model consumption"},
        {"id": "portfolio-selection", "required": True, "tool_path": str(aigc_router / "audit_portfolio_selection.py"), "command": f'python "{aigc_router / "audit_portfolio_selection.py"}" "{portfolio_target}" "{target}" --candidate-id <selected-id> --source-sha256 <source-sha256> --format json'},
        {"id": "evidence-bundle", "required": True, "tool_path": str(aigc_router / "prepare_competition_evidence.py"), "command": f'python "{aigc_router / "prepare_competition_evidence.py"}" audit "{evidence_target}" --require-materials --require-execution --format json'},
        {"id": "reasoning-preflight", "required": True, "tool_path": str(mcm / "audit_reasoning_preflight.py"), "command": f'python "{mcm / "audit_reasoning_preflight.py"}" "{workbench_target}" --approval "{preflight_target}" --format json'},
        {"id": "modeling-workbench", "required": True, "tool_path": str(mcm / "audit_modeling_workbench.py"), "command": f'python "{mcm / "audit_modeling_workbench.py"}" "{target}" --workbench "{workbench_target}" --phase release --format json'},
        {"id": "corpus-overlap", "required": True, "tool_path": str(mcm / "audit_corpus_overlap.py"), "command": f'python "{mcm / "audit_corpus_overlap.py"}" "{target}" --min-chars 20 --fail-on-overlap --format json'},
        {"id": "reasoning-review", "required": True, "tool_path": str(mcm / "audit_reasoning_review.py"), "command": f'python "{mcm / "audit_reasoning_review.py"}" "{target}" --review "{review_target}" --format json'},
        {"id": "judgment-ledger", "required": True, "tool_path": str(mcm / "audit_judgment_ledger.py"), "command": f'python "{mcm / "audit_judgment_ledger.py"}" "{target}" --ledger "{judgment_ledger_target}" --workbench "{workbench_target}" --format json'},
        {"id": "public-judgment-bridges", "required": True, "tool_path": str(mcm / "audit_section_judgment_bridges.py"), "command": f'python "{mcm / "audit_section_judgment_bridges.py"}" "{target}" --packet-index "{drafting_packet_target}" --format json', "manual_followup": "checks visible source-bound bridges, not private chain-of-thought"},
        {"id": "public-reasoning-scaffold", "required": True, "tool_path": str(aigc_router / "audit_reasoning_scaffold.py"), "command": f'python "{aigc_router / "audit_reasoning_scaffold.py"}" "{target}" --mode auto --format json', "manual_followup": "checks repeated visible action sequences across substantive sections; it does not reconstruct hidden chain-of-thought"},
        {"id": "manuscript", "required": True, "tool_path": str(mcm / "audit_manuscript.py"), "command": f'python "{mcm / "audit_manuscript.py"}" "{target}" --problem-type {problem_type or "A"} --format json'},
    ]
    gates.append({
        "id": "auxiliary-roles", "required": True,
        "tool_path": str(aigc_router / "audit_longform_auxiliary_roles.py"),
        "command": (
            f'python "{aigc_router / "audit_longform_auxiliary_roles.py"}" '
            f'--source "{source_target}" --candidate "{target}" '
            f'--output-dir "<release-output>/auxiliary-roles" '
            f'--registry "{aigc_router / "references" / "stack-registry.json"}" '
            f'--document-type mcm --format json'
        ),
        "manual_followup": "read-only ai-check diagnostics and AI_paper plan; neither generates or selects a candidate",
    })
    if math_contract:
        gates.append({"id": "math-semantics", "required": True, "tool_path": str(mcm / "audit_math_semantics.py"), "command": f'python "{mcm / "audit_math_semantics.py"}" "{target}" --contract "{math_contract}" --format json'})
    if repro_manifest:
        gates.append({"id": "reproducibility", "required": True, "tool_path": str(mcm / "audit_repro_manifest.py"), "command": f'python "{mcm / "audit_repro_manifest.py"}" "{repro_manifest}" --format json'})
    if result_manifest:
        gates.append({"id": "result-sync", "required": True, "tool_path": str(mcm / "audit_result_sync.py"), "command": f'python "{mcm / "audit_result_sync.py"}" "{target}" --manifest "{result_manifest}" --format json'})
    gates.append({
        "id": "style-retrieval-plan", "required": True,
        "tool_path": str(mcm / "audit_style_retrieval_plan.py"),
        "command": f'python "{mcm / "audit_style_retrieval_plan.py"}" "{source_target}" --plan "{style_retrieval_target}" --problem-type {problem_type or "A"} --format json',
        "manual_followup": "the plan is a style observation record only; facts and claims must remain bound to the current problem",
    })
    gates.append({
        "id": "section-authoring-brief", "required": True,
        "tool_path": str(mcm / "audit_section_authoring_brief.py"),
        "command": (
            f'python "{mcm / "audit_section_authoring_brief.py"}" "{source_target}" '
            f'--brief "{authoring_brief_target}" --problem-type {problem_type or "A"} '
            f'--style-plan "{style_retrieval_target}" --workbench "{workbench_target}" '
            f'--preflight "{preflight_target}" --format json'
        ),
        "manual_followup": "write from current-problem evidence; read corpus paragraphs only for language action and rhythm",
    })
    gates.append({
        "id": "section-drafting-packets", "required": True,
        "tool_path": str(mcm / "audit_section_drafting_packets.py"),
        "command": (
            f'python "{mcm / "audit_section_drafting_packets.py"}" "{source_target}" '
            f'--brief "{authoring_brief_target}" --style-plan "{style_retrieval_target}" '
            f'--index "{drafting_packet_target}" --format json'
        ),
        "manual_followup": "read the complete packet for the target section before drafting; the packet is an input bundle, not proof of model consumption",
    })
    gates.append({
        "id": "section-drafting-usage", "required": True,
        "tool_path": str(mcm / "audit_section_drafting_usage.py"),
        "command": (
            f'python "{mcm / "audit_section_drafting_usage.py"}" "{source_target}" "{target}" '
            f'--packet-index "{drafting_packet_target}" --usage "{drafting_usage_target}" --format json'
        ),
        "manual_followup": "the receipt binds section hashes and declared packet lineage; it does not expose or prove hidden reasoning",
    })
    if coverage and aux:
        gates.extend([
            {"id": "competition-length", "required": True, "tool_path": str(mcm / "audit_competition_length.py"), "command": f'python "{mcm / "audit_competition_length.py"}" "{target}" --aux "{aux}" --coverage "{coverage}" --min-pages 25 --max-pages 30 --format json'},
            {"id": "content-density", "required": True, "tool_path": str(mcm / "audit_content_density.py"), "command": f'python "{mcm / "audit_content_density.py"}" "{target}" --aux "{aux}" --coverage "{coverage}" --problem-type {problem_type or "A"} --format json'},
        ])
    gates.append({
        "id": "academic-style-release", "required": True,
        "tool_path": str(aigc_router / "audit_academic_candidate.py"),
        "command": (
        f'python "{aigc_router / "audit_academic_candidate.py"}" '
            f'"{source_target}" "{target}" --scene MODELING --require-style-gain '
            f'--packet-index "{drafting_packet_target}" --format json{style_decisions_arg}'
        ),
        "manual_followup": "all installed humanize and protected-rewrite checks must execute; unresolved findings block release",
    })
    gates.append({
        "id": "compile-and-render", "required": True,
        "command": f'latexmk -xelatex -interaction=nonstopmode -halt-on-error "{target}"',
        "manual_followup": "inspect the rendered PDF, warnings, references, figures, tables and page boundaries",
    })
    return gates


def initialise(
    source: Path,
    output_dir: Path,
    document_type: str,
    problem_type: str | None,
    registry: Path,
    coverage: Path | None = None,
    aux: Path | None = None,
    math_contract: Path | None = None,
    repro_manifest: Path | None = None,
    result_manifest: Path | None = None,
    workbench: Path | None = None,
    preflight: Path | None = None,
    reasoning_review: Path | None = None,
    artifacts: list[str] | None = None,
    evidence_bundle: Path | None = None,
    style_decisions: Path | None = None,
    portfolio_plan: Path | None = None,
    style_retrieval_plan: Path | None = None,
    authoring_brief: Path | None = None,
    judgment_ledger: Path | None = None,
    drafting_packet_index: Path | None = None,
    drafting_usage: Path | None = None,
) -> tuple[Path, dict]:
    source = source.resolve()
    output_dir = output_dir.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    manifest_path = output_dir / "longform-manifest.json"
    if manifest_path.exists():
        raise FileExistsError(f"manifest already exists: {manifest_path}")
    output_dir.mkdir(parents=True, exist_ok=True)
    tree = discover_tex_tree(source) if source.suffix.casefold() == ".tex" else [source]
    source_files: list[dict] = []
    all_chunks: list[dict] = []
    aggregate_text: list[str] = []
    for path in tree:
        relative = _snapshot_relative(source, path)
        snapshot = output_dir / "source-tree" / relative
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, snapshot)
        text = path.read_text(encoding="utf-8-sig")
        aggregate_text.append(text)
        source_files.append({
            "authority_path": str(path),
            "snapshot_path": str(snapshot),
            "relative_path": str(relative),
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        })
        all_chunks.extend(parse_chunks(path, text))
    for index, chunk in enumerate(all_chunks, start=1):
        chunk["id"] = f"S{index:03d}"

    manifest = {
        "schema": SCHEMA,
        "document_type": document_type,
        "problem_type": problem_type,
        "state": "SOURCE_FROZEN",
        "authority": {
            "main_path": str(source),
            "main_sha256": sha256_file(source),
            "files": source_files,
            "protected_inventory": serialise_inventory(protected_inventory("\n".join(aggregate_text))),
        },
        "chunks": all_chunks,
        "artifacts": [_artifact(value) for value in (artifacts or [])],
        "candidate_policy": {
            "branch_from_frozen_source": True,
            "serial_rewrite_allowed": False,
            "pass_count": 1,
            "source_remains_candidate": True,
        },
        "candidates": [],
        "selection": {"accepted": None, "human_review": "pending", "reason": None},
        "gate_inputs": {
            "coverage": str(coverage.resolve()) if coverage else None,
            "aux": str(aux.resolve()) if aux else None,
            "math_contract": str(math_contract.resolve()) if math_contract else None,
            "repro_manifest": str(repro_manifest.resolve()) if repro_manifest else None,
            "result_manifest": str(result_manifest.resolve()) if result_manifest else None,
            "workbench": str(workbench.resolve()) if workbench else None,
            "preflight": str(preflight.resolve()) if preflight else None,
            "reasoning_review": str(reasoning_review.resolve()) if reasoning_review else None,
            "evidence_bundle": str(evidence_bundle.resolve()) if evidence_bundle else None,
            "style_decisions": str(style_decisions.resolve()) if style_decisions else None,
            "portfolio_plan": str(portfolio_plan.resolve()) if portfolio_plan else None,
            "style_retrieval_plan": str(style_retrieval_plan.resolve()) if style_retrieval_plan else None,
            "authoring_brief": str(authoring_brief.resolve()) if authoring_brief else None,
            "judgment_ledger": str(judgment_ledger.resolve()) if judgment_ledger else None,
            "drafting_packet_index": str(drafting_packet_index.resolve()) if drafting_packet_index else None,
            "drafting_usage": str(drafting_usage.resolve()) if drafting_usage else None,
        },
        "gates": gate_plan(None, problem_type, coverage, aux, math_contract, repro_manifest, result_manifest, workbench, preflight, reasoning_review, evidence_bundle, style_decisions, portfolio_plan, style_retrieval_plan, authoring_brief, judgment_ledger, drafting_packet_index, drafting_usage),
        "registry": str(registry.resolve()),
    }
    write_json(manifest_path, manifest)
    write_json(output_dir / "gate-plan.json", {"schema": "aigc-longform-gates/v1", "gates": manifest["gates"]})
    return manifest_path, manifest


def register_candidate(
    manifest_path: Path,
    candidate_path: Path,
    provider: str,
    candidate_id: str,
    output_path: Path | None = None,
) -> tuple[Path, dict, dict]:
    manifest_path = manifest_path.resolve()
    manifest = _load_manifest(manifest_path)
    if audit_manifest(manifest_path)["status"] != "pass":
        raise ValueError("manifest audit must pass before candidate registration")
    if manifest.get("document_type") == "mcm":
        generation_lock = manifest.get("generation_input_lock")
        if not isinstance(generation_lock, dict) or generation_lock.get("status") != "pass":
            raise ValueError("MCM candidate registration requires a passing pre-candidate generation-input lock")
        for label, item in generation_lock.get("inputs", {}).items():
            path = Path(str(item.get("path", ""))).resolve()
            if not path.is_file() or sha256_file(path) != item.get("sha256"):
                raise ValueError(f"generation input drifted before candidate registration: {label}")
    if manifest.get("selection", {}).get("accepted") is not None:
        raise ValueError("candidate registration is closed after human selection")
    if any(item.get("id") == candidate_id for item in manifest.get("candidates", [])):
        raise ValueError(f"candidate id already exists: {candidate_id}")
    source = Path(manifest["authority"]["main_path"])
    candidate_path = candidate_path.resolve()
    if candidate_path == source.resolve():
        raise ValueError("candidate cannot overwrite the authority path")
    candidate_tree = discover_tex_tree(candidate_path) if candidate_path.suffix.casefold() == ".tex" else [candidate_path]
    candidate_files = [
        {
            "path": str(path),
            "relative_path": str(_snapshot_relative(candidate_path, path)),
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }
        for path in candidate_tree
    ]
    authority_relatives = {
        item["relative_path"] for item in manifest["authority"].get("files", [])
    }
    candidate_relatives = {item["relative_path"] for item in candidate_files}
    tree_findings = []
    missing_relatives = sorted(authority_relatives - candidate_relatives)
    if missing_relatives:
        tree_findings.append({
            "severity": "error",
            "code": "CANDIDATE_TREE_INCOMPLETE",
            "missing": missing_relatives,
        })
    added_relatives = sorted(candidate_relatives - authority_relatives)
    if added_relatives:
        tree_findings.append({
            "severity": "error",
            "code": "CANDIDATE_TREE_ADDED_FILE",
            "added": added_relatives,
        })
    authority_paths = {
        Path(item["authority_path"]).resolve() for item in manifest["authority"].get("files", [])
    }
    reused_authority = sorted(
        str(path.resolve()) for path in candidate_tree[1:] if path.resolve() in authority_paths
    )
    if reused_authority:
        tree_findings.append({
            "severity": "error",
            "code": "CANDIDATE_REUSES_AUTHORITY_INCLUDE",
            "paths": reused_authority,
        })
    run_dir = manifest_path.parent / "candidate-runs" / candidate_id
    verification = run_adapter(
        Path(manifest["registry"]), provider, "verify-candidate",
        source=source, candidate=candidate_path, output_dir=run_dir,
    )
    candidate_by_relative = {
        item["relative_path"]: Path(item["path"]) for item in candidate_files
    }
    source_main_relative = str(_snapshot_relative(source, source))
    file_verification_reports = []
    for item in manifest["authority"].get("files", []):
        relative = item["relative_path"]
        if relative == source_main_relative or relative not in candidate_by_relative:
            continue
        file_run_dir = run_dir / "includes" / relative.replace("\\", "__").replace("/", "__")
        file_report = run_adapter(
            Path(manifest["registry"]), provider, "verify-candidate",
            source=Path(item["authority_path"]),
            candidate=candidate_by_relative[relative],
            output_dir=file_run_dir,
        )
        file_verification_reports.append({
            "relative_path": relative,
            "status": file_report["status"],
            "report": str(file_run_dir / "candidate-verification.json"),
        })
        for finding in file_report.get("findings", []):
            verification.setdefault("findings", []).append({**finding, "source_file": relative})
        if file_report["status"] != "pass":
            verification["status"] = "fail"
    if tree_findings:
        verification["findings"] = verification.get("findings", []) + tree_findings
        verification["status"] = "fail"
    if verification["status"] == "fail":
        verification["errors"] = sum(
            item.get("severity") == "error" for item in verification["findings"]
        )
    verification["file_verifications"] = file_verification_reports
    verification_path = run_dir / "candidate-verification.json"
    write_json(verification_path, verification)
    record = {
        "id": candidate_id,
        "provider": provider,
        "input_sha256": manifest["authority"]["main_sha256"],
        "output_path": str(candidate_path),
        "output_sha256": sha256_file(candidate_path),
        "output_files": candidate_files,
        "parent_candidate": None,
        "pass_count": 1,
        "verification_status": verification["status"],
        "verification_report": str(verification_path),
        "verification_report_sha256": sha256_file(verification_path),
        "file_verifications": file_verification_reports,
        "human_review": "pending",
    }
    manifest["candidates"].append(record)
    manifest["state"] = "CANDIDATES_READY" if verification["status"] == "pass" else "CANDIDATE_REJECTED"
    destination = _next_manifest_path(manifest_path, candidate_id, output_path)
    write_json(destination, manifest)
    return destination, manifest, verification


def _tree_sha256(files: list[dict], path_key: str, hash_key: str = "sha256") -> str:
    rows = [f"{item.get(path_key, '')}\0{item.get(hash_key, '')}" for item in files]
    return sha256_text("\n".join(sorted(rows)))


def _selected_target(manifest: dict) -> dict:
    selection = manifest.get("selection", {})
    accepted = selection.get("accepted")
    if accepted == SOURCE_ID:
        authority = manifest["authority"]
        files = [
            {
                "path": item["authority_path"],
                "relative_path": item["relative_path"],
                "sha256": item["sha256"],
                "bytes": item["bytes"],
            }
            for item in authority.get("files", [])
        ]
        return {
            "id": SOURCE_ID,
            "path": authority["main_path"],
            "sha256": authority["main_sha256"],
            "files": files,
        }
    candidate = next(
        (item for item in manifest.get("candidates", []) if item.get("id") == accepted),
        None,
    )
    if candidate is None:
        raise ValueError("human-selected candidate is missing")
    return {
        "id": candidate["id"],
        "path": candidate["output_path"],
        "sha256": candidate["output_sha256"],
        "files": candidate.get("output_files", []),
    }


def _blind_score_record(path: Path, required_variants: set[str]) -> dict:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if (
        payload.get("schema") != "aigc-blind-score/v1"
        or payload.get("status") != "pass"
        or payload.get("scoring_protocol") != "aigc-blind-scoring/v2"
    ):
        raise ValueError("blind score must be a passing aigc-blind-scoring/v2 report")
    if payload.get("formal_human_ready") is not True:
        raise ValueError("formal blind evidence requires declared human raters")
    coverage = payload.get("human_coverage", {})
    effective_coverage = payload.get("effective_human_coverage", {})
    if not effective_coverage or any(int(value) < 2 for value in effective_coverage.values()):
        raise ValueError("formal blind evidence requires at least two complete human ratings for every pair")
    if int(payload.get("unresolved_human_dimensions", 1)) != 0:
        raise ValueError("formal blind evidence contains unresolved pair-dimension disagreements")
    if payload.get("pairwise_exact_agreement") is None:
        raise ValueError("formal blind evidence is missing inter-rater agreement")
    variants = {str(value) for value in payload.get("variants", [])}
    if not required_variants <= variants:
        raise ValueError("blind score variants do not cover the candidate ids being compared")
    evidence = payload.get("evidence", {})
    for label in ("key", "ratings", "packet", "source_pairs", "merge_report"):
        record = evidence.get(label, {})
        evidence_path = Path(record.get("path", ""))
        if not evidence_path.is_file() or sha256_file(evidence_path) != record.get("sha256"):
            raise ValueError(f"blind score evidence drifted: {label}")
    merge_report_path = Path(evidence["merge_report"]["path"])
    merge_audit = audit_merge_report(merge_report_path)
    if merge_audit.get("status") != "pass":
        raise ValueError("blind score merge report failed audit")
    merge_payload = json.loads(merge_report_path.read_text(encoding="utf-8-sig"))
    if (
        Path(str(merge_payload.get("output", {}).get("path", ""))).resolve()
        != Path(str(evidence["ratings"]["path"])).resolve()
        or Path(str(merge_payload.get("packet", {}).get("path", ""))).resolve()
        != Path(str(evidence["packet"]["path"])).resolve()
    ):
        raise ValueError("blind score merge report is not bound to the score ratings and packet")
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "pairs": payload.get("pairs"),
        "ratings": payload.get("ratings"),
        "coverage": coverage,
        "effective_coverage": effective_coverage,
        "pairwise_exact_agreement": payload.get("pairwise_exact_agreement"),
        "formal_human_ready": True,
        "variants": sorted(variants),
        "evidence": evidence,
    }


def select_target(
    manifest_path: Path,
    candidate_id: str,
    reviewer: str,
    reason: str,
    blind_score: Path | None = None,
    output_path: Path | None = None,
    reviewer_kind: str = "human",
) -> tuple[Path, dict]:
    manifest_path = manifest_path.resolve()
    manifest = _load_manifest(manifest_path)
    if audit_manifest(manifest_path)["status"] != "pass":
        raise ValueError("manifest audit must pass before human selection")
    if manifest.get("selection", {}).get("accepted") is not None:
        raise ValueError("the manifest already contains a human selection")
    reviewer = reviewer.strip()
    reason = reason.strip()
    if reviewer_kind != "human":
        raise ValueError("candidate selection requires a human reviewer_kind")
    if not reviewer or not reason:
        raise ValueError("reviewer and a concrete selection reason are required")
    passing = [item for item in manifest.get("candidates", []) if item.get("verification_status") == "pass"]
    if candidate_id != SOURCE_ID:
        selected = next((item for item in passing if item.get("id") == candidate_id), None)
        if selected is None:
            raise ValueError("only SOURCE or a mechanically passing candidate can be selected")
    if len(passing) > 1 and blind_score is None:
        raise ValueError("multiple passing candidates require a formal blind-score report")
    passing_ids = {str(item["id"]) for item in passing}
    blind_record = _blind_score_record(blind_score, passing_ids) if blind_score else None
    for candidate in manifest.get("candidates", []):
        if candidate.get("verification_status") == "pass":
            candidate["human_review"] = "accepted" if candidate.get("id") == candidate_id else "not-selected"
    manifest["selection"] = {
        "accepted": candidate_id,
        "human_review": "accepted",
        "reviewer": reviewer,
        "reviewer_kind": reviewer_kind,
        "reason": reason,
        "decided_at": _utc_now(),
        "blind_score": blind_record,
    }
    target = _selected_target(manifest)
    compile_resource_files = _compile_resource_records(Path(target["path"]))
    manifest["selection"].update({
        "target_path": target["path"],
        "target_sha256": target["sha256"],
        "target_tree_sha256": _tree_sha256(target["files"], "relative_path"),
        "compile_resource_files": compile_resource_files,
        "compile_resource_tree_sha256": _tree_sha256(
            compile_resource_files, "relative_path"
        ),
    })
    manifest["state"] = "HUMAN_SELECTED"
    destination = _next_manifest_path(manifest_path, "selected", output_path)
    write_json(destination, manifest)
    return destination, manifest


def _default_executor(command: list[str], cwd: Path, gate_id: str, run_dir: Path) -> dict:
    del gate_id, run_dir
    try:
        completed = subprocess.run(
            command, cwd=cwd, text=True, encoding="utf-8", errors="replace",
            capture_output=True, timeout=300, check=False,
        )
        return {
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"returncode": 127, "stdout": "", "stderr": str(exc)}


def _scan_latex_log(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    blockers = {}
    warnings = {}
    examples = []
    for code, pattern in LATEX_LOG_BLOCKERS.items():
        matches = list(pattern.finditer(text))
        if matches:
            blockers[code] = len(matches)
            examples.extend(match.group(0).strip() for match in matches[:3])
    for code, pattern in LATEX_LOG_WARNINGS.items():
        matches = list(pattern.finditer(text))
        if matches:
            warnings[code] = len(matches)
    return {
        "status": "fail" if blockers else "pass",
        "blockers": blockers,
        "warnings": warnings,
        "examples": examples[:10],
    }


def _execute_gate(
    gate_id: str,
    command: list[str],
    cwd: Path,
    run_dir: Path,
    tool_path: Path | None,
    executor,
    expect_json: bool,
) -> dict:
    result = executor(command, cwd, gate_id, run_dir)
    log_dir = run_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / f"{gate_id}.stdout.txt"
    stderr_path = log_dir / f"{gate_id}.stderr.txt"
    stdout_path.write_text(str(result.get("stdout", "")), encoding="utf-8")
    stderr_path.write_text(str(result.get("stderr", "")), encoding="utf-8")
    returncode = int(result.get("returncode", 127))
    record = {
        "id": gate_id,
        "required": True,
        "status": "pass" if returncode == 0 else "fail",
        "command": command,
        "cwd": str(cwd.resolve()),
        "returncode": returncode,
        "stdout": {"path": str(stdout_path), "sha256": sha256_file(stdout_path)},
        "stderr": {"path": str(stderr_path), "sha256": sha256_file(stderr_path)},
    }
    if tool_path is not None:
        tool_record = {
            "source_path": str(tool_path.resolve()),
            "source_sha256": sha256_file(tool_path) if tool_path.is_file() else None,
        }
        if tool_path.is_file() and tool_path.suffix.casefold() == ".py":
            snapshot_dir = run_dir / "tool-snapshots"
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            snapshot_path = snapshot_dir / f"{gate_id}-{tool_path.name}"
            shutil.copy2(tool_path, snapshot_path)
            tool_record["snapshot"] = {
                "path": str(snapshot_path.resolve()),
                "sha256": sha256_file(snapshot_path),
            }
        record["tool"] = tool_record
    if expect_json and returncode == 0:
        try:
            payload = json.loads(str(result.get("stdout", "")))
            reported = str(payload.get("status", "")).casefold()
            record["reported_status"] = reported
            if reported != "pass":
                record["status"] = "fail"
                record["error"] = "gate returned zero but did not report PASS"
            dependencies = payload.get("dependencies", [])
            if gate_id == "academic-style-release" and not dependencies:
                record["status"] = "fail"
                record["error"] = "academic style gate omitted its executed dependency inventory"
            if dependencies:
                dependency_records = []
                snapshot_dir = run_dir / "tool-snapshots" / f"{gate_id}-dependencies"
                snapshot_dir.mkdir(parents=True, exist_ok=True)
                for index, dependency in enumerate(dependencies, start=1):
                    source_path = Path(str(dependency.get("path", ""))).resolve()
                    declared_hash = str(dependency.get("sha256", ""))
                    item = {
                        "role": dependency.get("role"),
                        "source_path": str(source_path),
                        "source_sha256": declared_hash,
                    }
                    if not source_path.is_file() or sha256_file(source_path) != declared_hash:
                        record["status"] = "fail"
                        record["error"] = "gate dependency is missing or differs from its executed hash"
                    else:
                        snapshot_path = snapshot_dir / f"{index:02d}-{source_path.name}"
                        shutil.copy2(source_path, snapshot_path)
                        item["snapshot"] = {
                            "path": str(snapshot_path.resolve()),
                            "sha256": sha256_file(snapshot_path),
                        }
                    dependency_records.append(item)
                record["dependencies"] = dependency_records
        except (json.JSONDecodeError, AttributeError):
            record["status"] = "fail"
            record["error"] = "gate returned invalid JSON"
    return record


def lock_generation_inputs(
    manifest_path: Path,
    workbench: Path,
    preflight: Path,
    style_retrieval_plan: Path,
    authoring_brief: Path,
    drafting_packet_index: Path,
    output_path: Path | None = None,
    executor=None,
) -> tuple[Path, dict, dict]:
    """Audit and freeze every MCM input that must exist before drafting."""
    manifest_path = manifest_path.resolve()
    manifest = _load_manifest(manifest_path)
    if manifest.get("document_type") != "mcm":
        raise ValueError("generation-input locking currently owns MCM manuscripts only")
    if manifest.get("state") != "SOURCE_FROZEN" or manifest.get("candidates"):
        raise ValueError("lock-generation must run after source freeze and before every candidate")
    if audit_manifest(manifest_path)["status"] != "pass":
        raise ValueError("manifest audit must pass before generation-input locking")
    paths = {
        "workbench": _required_input(workbench, "modeling workbench"),
        "preflight": _required_input(preflight, "reasoning preflight"),
        "style_retrieval_plan": _required_input(style_retrieval_plan, "style retrieval plan"),
        "authoring_brief": _required_input(authoring_brief, "section authoring brief"),
        "drafting_packet_index": _required_input(drafting_packet_index, "section drafting packet index"),
    }
    source_main_record = next(
        item for item in manifest["authority"]["files"]
        if Path(item["authority_path"]).resolve() == Path(manifest["authority"]["main_path"]).resolve()
    )
    frozen_source_main = Path(source_main_record["snapshot_path"]).resolve()
    run_dir = manifest_path.parent / "generation-input-lock"
    report_path = run_dir / "generation-input-lock.json"
    if report_path.exists():
        raise FileExistsError(f"generation input lock already exists: {report_path}")
    run_dir.mkdir(parents=True, exist_ok=True)
    writing_rules = _snapshot_generation_writing_rules(run_dir)
    executor = executor or _default_executor
    skills_root = Path(__file__).resolve().parents[3]
    mcm = skills_root / "mcm-cup-standard-write" / "scripts"
    python = Path(sys.executable).resolve()
    problem_type = manifest.get("problem_type") or "A"
    specs = [
        ("modeling-workbench", mcm / "audit_modeling_workbench.py", [str(python), str(mcm / "audit_modeling_workbench.py"), str(frozen_source_main), "--workbench", str(paths["workbench"]), "--phase", "preflight", "--format", "json"]),
        ("reasoning-preflight", mcm / "audit_reasoning_preflight.py", [str(python), str(mcm / "audit_reasoning_preflight.py"), str(paths["workbench"]), "--approval", str(paths["preflight"]), "--format", "json"]),
        ("style-retrieval-plan", mcm / "audit_style_retrieval_plan.py", [str(python), str(mcm / "audit_style_retrieval_plan.py"), str(frozen_source_main), "--plan", str(paths["style_retrieval_plan"]), "--problem-type", problem_type, "--format", "json"]),
        ("section-authoring-brief", mcm / "audit_section_authoring_brief.py", [str(python), str(mcm / "audit_section_authoring_brief.py"), str(frozen_source_main), "--brief", str(paths["authoring_brief"]), "--problem-type", problem_type, "--style-plan", str(paths["style_retrieval_plan"]), "--workbench", str(paths["workbench"]), "--preflight", str(paths["preflight"]), "--format", "json"]),
        ("section-drafting-packets", mcm / "audit_section_drafting_packets.py", [str(python), str(mcm / "audit_section_drafting_packets.py"), str(frozen_source_main), "--brief", str(paths["authoring_brief"]), "--style-plan", str(paths["style_retrieval_plan"]), "--index", str(paths["drafting_packet_index"]), "--format", "json"]),
    ]
    gates = [
        _execute_gate(gate_id, command, frozen_source_main.parent, run_dir, tool, executor, True)
        for gate_id, tool, command in specs
    ]
    status = "pass" if all(item.get("status") == "pass" for item in gates) else "fail"
    input_records = {
        key: {"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size}
        for key, path in paths.items()
    }
    report = {
        "schema": "aigc-mcm-generation-input-lock/v1",
        "status": status,
        "created_at": _utc_now(),
        "source": {
            "path": str(frozen_source_main),
            "sha256": sha256_file(frozen_source_main),
            "tree_sha256": _tree_sha256(manifest["authority"]["files"], "relative_path"),
        },
        "inputs": input_records,
        "writing_rules": writing_rules,
        "gates": gates,
        "candidate_exists": False,
        "interpretation": (
            "Passing proves that source-bound drafting inputs were audited and frozen before candidate registration. "
            "It does not prove model consumption, mathematical correctness, or naturalness."
        ),
    }
    write_json(report_path, report)
    manifest["generation_input_lock"] = {
        "path": str(report_path),
        "sha256": sha256_file(report_path),
        "status": status,
        "source_sha256": report["source"]["sha256"],
        "source_tree_sha256": report["source"]["tree_sha256"],
        "inputs": input_records,
        "writing_rule_tree_sha256": writing_rules["tree_sha256"],
        "writing_rule_count": writing_rules["count"],
    }
    manifest["state"] = "GENERATION_INPUTS_LOCKED" if status == "pass" else "GENERATION_INPUTS_FAILED"
    destination = _next_manifest_path(manifest_path, "generation-locked", output_path)
    write_json(destination, manifest)
    return destination, manifest, report


def _execute_review_advisory(
    gate_id: str,
    command: list[str],
    cwd: Path,
    run_dir: Path,
    tool_path: Path | None,
    executor,
) -> dict:
    """Run a read-only style signal without turning REVIEW into a release failure."""
    record = _execute_gate(gate_id, command, cwd, run_dir, tool_path, executor, False)
    record["required"] = False
    record["review_only"] = True
    if record["returncode"] == 2:
        record["status"] = "review"
        record["error"] = "advisory found passages for human reading"
    return record


def _required_input(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"{label}: {resolved}")
    return resolved


def run_release_gates(
    manifest_path: Path,
    output_dir: Path,
    coverage: Path,
    math_contract: Path,
    repro_manifest: Path,
    result_manifest: Path,
    workbench: Path,
    preflight: Path,
    reasoning_review: Path,
    evidence_bundle: Path,
    portfolio_plan: Path,
    style_decisions: Path | None = None,
    output_path: Path | None = None,
    style_retrieval_plan: Path | None = None,
    authoring_brief: Path | None = None,
    judgment_ledger: Path | None = None,
    drafting_packet_index: Path | None = None,
    drafting_usage: Path | None = None,
    executor=None,
) -> tuple[Path, dict, dict]:
    manifest_path = manifest_path.resolve()
    manifest = _load_manifest(manifest_path)
    if manifest.get("document_type") != "mcm":
        raise ValueError("the release gate runner currently owns formal MCM documents only")
    if manifest.get("state") != "HUMAN_SELECTED":
        raise ValueError("run-gates requires a HUMAN_SELECTED manifest")
    audit = audit_manifest(manifest_path)
    if audit["status"] != "pass":
        raise ValueError("manifest audit must pass before release gates")
    target = _selected_target(manifest)
    target_path = Path(target["path"]).resolve()
    if not target_path.is_file() or sha256_file(target_path) != target["sha256"]:
        raise ValueError("selected target drifted before gate execution")
    inputs = {
        "coverage": _required_input(coverage, "coverage"),
        "math_contract": _required_input(math_contract, "math contract"),
        "repro_manifest": _required_input(repro_manifest, "repro manifest"),
        "result_manifest": _required_input(result_manifest, "result manifest"),
        "workbench": _required_input(workbench, "modeling workbench"),
        "preflight": _required_input(preflight, "reasoning preflight"),
        "reasoning_review": _required_input(reasoning_review, "reasoning review"),
        "judgment_ledger": _required_input(judgment_ledger, "public judgment ledger"),
        "evidence_bundle": _required_input(evidence_bundle, "competition evidence bundle"),
        "portfolio_plan": _required_input(portfolio_plan, "AIGC portfolio plan"),
    }
    if style_decisions is not None:
        inputs["style_decisions"] = _required_input(style_decisions, "academic style decisions")
    inputs["style_retrieval_plan"] = _required_input(style_retrieval_plan, "style retrieval plan")
    inputs["authoring_brief"] = _required_input(authoring_brief, "section authoring brief")
    inputs["drafting_packet_index"] = _required_input(drafting_packet_index, "section drafting packet index")
    inputs["drafting_usage"] = _required_input(drafting_usage, "section drafting usage receipt")
    generation_lock = manifest.get("generation_input_lock")
    if not isinstance(generation_lock, dict) or generation_lock.get("status") != "pass":
        raise ValueError("release requires a passing pre-candidate generation-input lock")
    for key in ("workbench", "preflight", "style_retrieval_plan", "authoring_brief", "drafting_packet_index"):
        locked = generation_lock.get("inputs", {}).get(key, {})
        if locked.get("sha256") != sha256_file(inputs[key]):
            raise ValueError(f"release input differs from the pre-candidate generation lock: {key}")
    output_dir = output_dir.resolve()
    report_path = output_dir / "release-gates.json"
    if report_path.exists():
        raise FileExistsError(f"release report already exists: {report_path}")
    output_dir.mkdir(parents=True, exist_ok=True)
    release_source_root = output_dir / "selected-source"
    release_files = []
    release_target = None
    for item in target["files"]:
        source_file = Path(item["path"]).resolve()
        if not source_file.is_file() or sha256_file(source_file) != item["sha256"]:
            raise ValueError(f"selected source tree drifted: {source_file}")
    compile_resource_files = manifest["selection"].get("compile_resource_files")
    if not compile_resource_files:
        raise ValueError("selection predates compile-resource locking; create a new selection manifest")
    for item in compile_resource_files:
        source_file = Path(item["path"]).resolve()
        if not source_file.is_file() or sha256_file(source_file) != item["sha256"]:
            raise ValueError(f"selected compile resource drifted: {source_file}")
        relative = Path(item["relative_path"])
        snapshot = (release_source_root / relative).resolve()
        try:
            snapshot.relative_to(release_source_root.resolve())
        except ValueError as exc:
            raise ValueError(f"unsafe selected-source relative path: {relative}") from exc
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, snapshot)
        release_files.append({
            "relative_path": str(relative), "path": str(snapshot),
            "sha256": sha256_file(snapshot), "bytes": snapshot.stat().st_size,
        })
        if source_file == target_path:
            release_target = snapshot
    if release_target is None:
        raise ValueError("selected main TeX was not found in its recorded file tree")
    build_dir = output_dir / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    executor = executor or _default_executor
    skills_root = Path(__file__).resolve().parents[3]
    mcm = skills_root / "mcm-cup-standard-write" / "scripts"
    aigc_router = skills_root / "AIGC" / "aigc-writing-router" / "scripts"
    python = Path(sys.executable).resolve()
    problem_type = manifest.get("problem_type") or "A"
    source_main_record = next(
        item for item in manifest["authority"]["files"]
        if Path(item["authority_path"]).resolve() == Path(manifest["authority"]["main_path"]).resolve()
    )
    frozen_source_main = Path(source_main_record["snapshot_path"]).resolve()
    academic_style_command = [
        str(python), str(aigc_router / "audit_academic_candidate.py"),
        str(frozen_source_main), str(release_target), "--scene", "MODELING",
        "--require-style-gain", "--packet-index", str(inputs["drafting_packet_index"]),
        "--format", "json",
    ]
    if "style_decisions" in inputs:
        academic_style_command.extend(["--decisions", str(inputs["style_decisions"])])
    auxiliary_dir = output_dir / "auxiliary-roles"
    gate_specs = [
        ("portfolio-selection", aigc_router / "audit_portfolio_selection.py", [str(python), str(aigc_router / "audit_portfolio_selection.py"), str(inputs["portfolio_plan"]), str(release_target), "--candidate-id", str(target["id"]), "--source-sha256", str(manifest["authority"]["main_sha256"]), "--format", "json"]),
        ("academic-style-release", aigc_router / "audit_academic_candidate.py", academic_style_command),
        ("evidence-bundle", aigc_router / "prepare_competition_evidence.py", [str(python), str(aigc_router / "prepare_competition_evidence.py"), "audit", str(inputs["evidence_bundle"]), "--require-materials", "--require-execution", "--format", "json"]),
        ("reasoning-preflight", mcm / "audit_reasoning_preflight.py", [str(python), str(mcm / "audit_reasoning_preflight.py"), str(inputs["workbench"]), "--approval", str(inputs["preflight"]), "--format", "json"]),
        ("modeling-workbench", mcm / "audit_modeling_workbench.py", [str(python), str(mcm / "audit_modeling_workbench.py"), str(release_target), "--workbench", str(inputs["workbench"]), "--phase", "release", "--format", "json"]),
        ("corpus-overlap", mcm / "audit_corpus_overlap.py", [str(python), str(mcm / "audit_corpus_overlap.py"), str(release_target), "--min-chars", "20", "--fail-on-overlap", "--format", "json"]),
        ("reasoning-review", mcm / "audit_reasoning_review.py", [str(python), str(mcm / "audit_reasoning_review.py"), str(release_target), "--review", str(inputs["reasoning_review"]), "--format", "json"]),
        ("judgment-ledger", mcm / "audit_judgment_ledger.py", [str(python), str(mcm / "audit_judgment_ledger.py"), str(release_target), "--ledger", str(inputs["judgment_ledger"]), "--workbench", str(inputs["workbench"]), "--format", "json"]),
        ("public-judgment-bridges", mcm / "audit_section_judgment_bridges.py", [str(python), str(mcm / "audit_section_judgment_bridges.py"), str(release_target), "--packet-index", str(inputs["drafting_packet_index"]), "--format", "json"]),
        ("public-reasoning-scaffold", aigc_router / "audit_reasoning_scaffold.py", [str(python), str(aigc_router / "audit_reasoning_scaffold.py"), str(release_target), "--mode", "auto", "--format", "json"]),
        ("manuscript", mcm / "audit_manuscript.py", [str(python), str(mcm / "audit_manuscript.py"), str(release_target), "--problem-type", problem_type, "--format", "json"]),
        ("math-semantics", mcm / "audit_math_semantics.py", [str(python), str(mcm / "audit_math_semantics.py"), str(release_target), "--contract", str(inputs["math_contract"]), "--format", "json"]),
        ("reproducibility", mcm / "audit_repro_manifest.py", [str(python), str(mcm / "audit_repro_manifest.py"), str(inputs["repro_manifest"]), "--format", "json"]),
        ("result-sync", mcm / "audit_result_sync.py", [str(python), str(mcm / "audit_result_sync.py"), str(release_target), "--manifest", str(inputs["result_manifest"]), "--format", "json"]),
        ("style-retrieval-plan", mcm / "audit_style_retrieval_plan.py", [str(python), str(mcm / "audit_style_retrieval_plan.py"), str(frozen_source_main), "--plan", str(inputs["style_retrieval_plan"]), "--problem-type", problem_type, "--format", "json"]),
        ("section-authoring-brief", mcm / "audit_section_authoring_brief.py", [str(python), str(mcm / "audit_section_authoring_brief.py"), str(frozen_source_main), "--brief", str(inputs["authoring_brief"]), "--problem-type", problem_type, "--style-plan", str(inputs["style_retrieval_plan"]), "--workbench", str(inputs["workbench"]), "--preflight", str(inputs["preflight"]), "--format", "json"]),
        ("section-drafting-packets", mcm / "audit_section_drafting_packets.py", [str(python), str(mcm / "audit_section_drafting_packets.py"), str(frozen_source_main), "--brief", str(inputs["authoring_brief"]), "--style-plan", str(inputs["style_retrieval_plan"]), "--index", str(inputs["drafting_packet_index"]), "--format", "json"]),
        ("section-drafting-usage", mcm / "audit_section_drafting_usage.py", [str(python), str(mcm / "audit_section_drafting_usage.py"), str(frozen_source_main), str(release_target), "--packet-index", str(inputs["drafting_packet_index"]), "--usage", str(inputs["drafting_usage"]), "--format", "json"]),
        ("auxiliary-roles", aigc_router / "audit_longform_auxiliary_roles.py", [str(python), str(aigc_router / "audit_longform_auxiliary_roles.py"), "--source", str(frozen_source_main), "--candidate", str(release_target), "--output-dir", str(auxiliary_dir), "--registry", str(aigc_router / "references" / "stack-registry.json"), "--document-type", "mcm", "--format", "json"]),
    ]
    generation_lock_gate = {
        "id": "generation-input-lock",
        "required": True,
        "status": "pass",
        "report": {
            "path": str(Path(str(generation_lock["path"])).resolve()),
            "sha256": generation_lock["sha256"],
        },
        "inputs": generation_lock["inputs"],
        "source_sha256": generation_lock["source_sha256"],
        "source_tree_sha256": generation_lock["source_tree_sha256"],
        "writing_rule_tree_sha256": generation_lock["writing_rule_tree_sha256"],
        "writing_rule_count": generation_lock["writing_rule_count"],
        "writing_rule_freshness": audit.get("writing_rule_freshness"),
        "interpretation": (
            "pre-candidate inputs and active writing rules were audited and frozen; "
            "model consumption is not proven"
        ),
    }
    gates = [generation_lock_gate] + [
        _execute_gate(gate_id, command, release_target.parent, output_dir, tool, executor, True)
        for gate_id, tool, command in gate_specs
    ]
    latexmk = Path(shutil.which("latexmk") or "latexmk")
    compile_command = [
        str(latexmk), "-xelatex", "-interaction=nonstopmode", "-halt-on-error",
        f"-outdir={build_dir}", str(release_target),
    ]
    compile_gate = _execute_gate(
        "compile", compile_command, release_target.parent, output_dir,
        latexmk if latexmk.is_file() else None, executor, False,
    )
    pdf_path = build_dir / f"{release_target.stem}.pdf"
    aux_path = build_dir / f"{release_target.stem}.aux"
    tex_log_path = build_dir / f"{release_target.stem}.log"
    if compile_gate["status"] == "pass" and (
        not pdf_path.is_file() or not aux_path.is_file() or not tex_log_path.is_file()
    ):
        compile_gate["status"] = "fail"
        compile_gate["error"] = "latexmk returned success without PDF, AUX and TeX log artifacts"
    if tex_log_path.is_file():
        compile_gate["latex_log"] = {
            "path": str(tex_log_path.resolve()),
            "sha256": sha256_file(tex_log_path),
            "scan": _scan_latex_log(tex_log_path),
        }
        if compile_gate["latex_log"]["scan"]["status"] == "fail":
            compile_gate["status"] = "fail"
            compile_gate["error"] = "TeX log contains blocking reference, resource, glyph or overflow issues"
    gates.append(compile_gate)
    if compile_gate["status"] == "pass":
        density_specs = [
            ("competition-length", mcm / "audit_competition_length.py", [str(python), str(mcm / "audit_competition_length.py"), str(release_target), "--aux", str(aux_path), "--coverage", str(inputs["coverage"]), "--min-pages", "25", "--max-pages", "30", "--format", "json"]),
            ("content-density", mcm / "audit_content_density.py", [str(python), str(mcm / "audit_content_density.py"), str(release_target), "--aux", str(aux_path), "--coverage", str(inputs["coverage"]), "--problem-type", problem_type, "--format", "json"]),
        ]
        gates.extend(
            _execute_gate(gate_id, command, release_target.parent, output_dir, tool, executor, True)
            for gate_id, tool, command in density_specs
        )
    else:
        gates.extend([
            {"id": gate_id, "required": True, "status": "fail", "error": "blocked by compile failure"}
            for gate_id in ("competition-length", "content-density")
        ])
    gate_ids = {item["id"] for item in gates if item.get("status") == "pass"}
    status = "pass" if REQUIRED_RELEASE_GATES <= gate_ids else "fail"
    artifacts = []
    for kind, path in (("pdf", pdf_path), ("aux", aux_path), ("tex-log", tex_log_path)):
        if path.is_file():
            artifacts.append({
                "kind": kind, "path": str(path.resolve()),
                "sha256": sha256_file(path), "bytes": path.stat().st_size,
            })
    report = {
        "schema": "aigc-mcm-release-gates/v1",
        "status": status,
        "created_at": _utc_now(),
        "target": {
            "id": target["id"], "path": str(target_path),
            "release_path": str(release_target), "sha256": target["sha256"],
            "tree_sha256": _tree_sha256(target["files"], "relative_path"),
            "release_tree_sha256": _tree_sha256(release_files, "relative_path"),
            "files": release_files,
        },
        "runtime": {"python": sys.version, "executable": str(python)},
        "inputs": {
            key: {"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size}
            for key, path in inputs.items()
        },
        "gates": gates,
        "artifacts": artifacts,
        "automatic_release": False,
    }
    write_json(report_path, report)
    manifest["release_gate_run"] = {
        "path": str(report_path),
        "sha256": sha256_file(report_path),
        "status": status,
        "target_id": target["id"],
        "target_sha256": target["sha256"],
    }
    manifest["state"] = "GATES_PASS" if status == "pass" else "GATES_FAILED"
    destination = _next_manifest_path(manifest_path, "gated", output_path)
    write_json(destination, manifest)
    return destination, manifest, report


def finalize_release(
    manifest_path: Path,
    reviewer: str,
    review_note: str,
    checked: list[str],
    output_path: Path | None = None,
    reviewer_kind: str = "human",
) -> tuple[Path, dict]:
    manifest_path = manifest_path.resolve()
    manifest = _load_manifest(manifest_path)
    if manifest.get("state") != "GATES_PASS":
        raise ValueError("finalize requires a GATES_PASS manifest")
    audit = audit_manifest(manifest_path)
    if audit["status"] != "pass":
        raise ValueError("manifest audit must pass before final review")
    reviewer = reviewer.strip()
    review_note = review_note.strip()
    checked_set = set(checked)
    if reviewer_kind != "human":
        raise ValueError("final rendered review requires a human reviewer_kind")
    if not reviewer or not review_note:
        raise ValueError("reviewer and a concrete rendered-page review note are required")
    missing = sorted(RENDER_CHECKS - checked_set)
    if missing:
        raise ValueError(f"render review checklist is incomplete: {missing}")
    manifest["final_review"] = {
        "status": "accepted",
        "reviewer": reviewer,
        "reviewer_kind": reviewer_kind,
        "review_note": review_note,
        "checked": sorted(checked_set),
        "reviewed_at": _utc_now(),
        "automatic_release": False,
    }
    manifest["state"] = "RELEASE_READY"
    destination = _next_manifest_path(manifest_path, "release-ready", output_path)
    write_json(destination, manifest)
    return destination, manifest


def _audit_generation_writing_rules(
    rules: object,
    generation_lock: dict,
    state: str,
    findings: list[dict],
) -> str:
    if not isinstance(rules, dict) or rules.get("status") != "current-bound":
        findings.append({"severity": "error", "code": "GENERATION_WRITING_RULE_SNAPSHOT_MISSING"})
        return "missing"
    files = rules.get("files")
    if not isinstance(files, list) or not files:
        findings.append({"severity": "error", "code": "GENERATION_WRITING_RULE_FILES_MISSING"})
        return "missing"
    if rules.get("count") != len(files) or generation_lock.get("writing_rule_count") != len(files):
        findings.append({"severity": "error", "code": "GENERATION_WRITING_RULE_COUNT_MISMATCH"})
    seen: set[str] = set()
    source_drift = False
    for index, item in enumerate(files):
        if not isinstance(item, dict):
            findings.append({
                "severity": "error", "code": "GENERATION_WRITING_RULE_RECORD_INVALID", "index": index,
            })
            continue
        source_path = str(Path(str(item.get("source_path", ""))).resolve())
        if not source_path or source_path in seen:
            findings.append({
                "severity": "error", "code": "GENERATION_WRITING_RULE_RECORD_INVALID",
                "index": index, "source_path": source_path,
            })
            continue
        seen.add(source_path)
        snapshot = Path(str(item.get("snapshot_path", ""))).resolve()
        if not snapshot.is_file() or sha256_file(snapshot) != item.get("snapshot_sha256"):
            findings.append({
                "severity": "error", "code": "GENERATION_WRITING_RULE_SNAPSHOT_DRIFT",
                "source_path": source_path, "snapshot_path": str(snapshot),
            })
        source = Path(source_path)
        if not source.is_file() or sha256_file(source) != item.get("source_sha256"):
            source_drift = True
    tree_sha256 = _writing_rule_tree(files, "source_path", "source_sha256")
    if (
        rules.get("tree_sha256") != tree_sha256
        or generation_lock.get("writing_rule_tree_sha256") != tree_sha256
    ):
        findings.append({"severity": "error", "code": "GENERATION_WRITING_RULE_TREE_MISMATCH"})
    try:
        current = _writing_rule_snapshot()
        current_tree = _writing_rule_tree(current, "path", "sha256")
    except (OSError, ValueError) as exc:
        current_tree = None
        source_drift = True
        current_error = str(exc)
    else:
        current_error = None
    if current_tree != tree_sha256:
        source_drift = True
    if source_drift:
        severity = "warning" if state == "RELEASE_READY" else "error"
        findings.append({
            "severity": severity,
            "code": "GENERATION_WRITING_RULES_NO_LONGER_CURRENT",
            "locked_tree_sha256": tree_sha256,
            "current_tree_sha256": current_tree,
            "detail": current_error,
        })
        return "historical-bound" if state == "RELEASE_READY" else "drifted"
    return "current-bound"


def audit_manifest(manifest_path: Path) -> dict:
    manifest_path = manifest_path.resolve()
    payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    findings: list[dict] = []
    if payload.get("schema") != SCHEMA:
        findings.append({"severity": "error", "code": "SCHEMA_MISMATCH"})
    authority = payload.get("authority", {})
    for item in authority.get("files", []):
        authority_path = Path(item.get("authority_path", ""))
        snapshot_path = Path(item.get("snapshot_path", ""))
        if not authority_path.is_file() or sha256_file(authority_path) != item.get("sha256"):
            findings.append({"severity": "error", "code": "AUTHORITY_FILE_DRIFT", "path": str(authority_path)})
        if not snapshot_path.is_file() or sha256_file(snapshot_path) != item.get("sha256"):
            findings.append({"severity": "error", "code": "SNAPSHOT_FILE_DRIFT", "path": str(snapshot_path)})
    for artifact in payload.get("artifacts", []):
        path = Path(artifact.get("path", ""))
        if not path.is_file() or sha256_file(path) != artifact.get("sha256"):
            findings.append({"severity": "error", "code": "ARTIFACT_DRIFT", "path": str(path)})
    for gate in payload.get("gates", []):
        tool_path = gate.get("tool_path")
        if tool_path and not Path(tool_path).is_file():
            findings.append({
                "severity": "error", "code": "GATE_TOOL_MISSING",
                "gate": gate.get("id"), "path": str(tool_path),
            })
    generation_lock = payload.get("generation_input_lock")
    generation_lock_valid = False
    writing_rule_freshness = "unbound"
    if generation_lock is not None:
        report_path = Path(str(generation_lock.get("path", ""))).resolve()
        if not report_path.is_file() or sha256_file(report_path) != generation_lock.get("sha256"):
            findings.append({"severity": "error", "code": "GENERATION_INPUT_LOCK_REPORT_DRIFT", "path": str(report_path)})
        else:
            try:
                generation_report = json.loads(report_path.read_text(encoding="utf-8-sig"))
            except json.JSONDecodeError:
                findings.append({"severity": "error", "code": "GENERATION_INPUT_LOCK_REPORT_INVALID"})
            else:
                if generation_report.get("schema") != "aigc-mcm-generation-input-lock/v1":
                    findings.append({"severity": "error", "code": "GENERATION_INPUT_LOCK_SCHEMA_MISMATCH"})
                if generation_report.get("status") != generation_lock.get("status"):
                    findings.append({"severity": "error", "code": "GENERATION_INPUT_LOCK_STATUS_MISMATCH"})
                authority_tree = _tree_sha256(authority.get("files", []), "relative_path")
                if (
                    generation_report.get("source", {}).get("sha256") != generation_lock.get("source_sha256")
                    or generation_report.get("source", {}).get("tree_sha256") != authority_tree
                    or generation_lock.get("source_tree_sha256") != authority_tree
                ):
                    findings.append({"severity": "error", "code": "GENERATION_INPUT_LOCK_SOURCE_MISMATCH"})
                expected_gate_ids = {
                    "modeling-workbench", "reasoning-preflight", "style-retrieval-plan",
                    "section-authoring-brief", "section-drafting-packets",
                }
                passed_gate_ids = {
                    item.get("id") for item in generation_report.get("gates", [])
                    if item.get("status") == "pass"
                }
                if generation_report.get("status") == "pass" and not expected_gate_ids <= passed_gate_ids:
                    findings.append({"severity": "error", "code": "GENERATION_INPUT_LOCK_GATE_MISSING"})
                if generation_report.get("candidate_exists") is not False:
                    findings.append({"severity": "error", "code": "GENERATION_INPUT_LOCK_TIMING_INVALID"})
                writing_rule_freshness = _audit_generation_writing_rules(
                    generation_report.get("writing_rules"), generation_lock,
                    str(payload.get("state", "")), findings,
                )
                for key, item in generation_lock.get("inputs", {}).items():
                    path = Path(str(item.get("path", ""))).resolve()
                    report_item = generation_report.get("inputs", {}).get(key, {})
                    if (
                        not path.is_file()
                        or sha256_file(path) != item.get("sha256")
                        or report_item.get("sha256") != item.get("sha256")
                    ):
                        findings.append({"severity": "error", "code": "GENERATION_INPUT_DRIFT", "input": key})
                for gate in generation_report.get("gates", []):
                    for log_name in ("stdout", "stderr"):
                        log = gate.get(log_name, {})
                        log_path = Path(str(log.get("path", ""))).resolve()
                        if not log_path.is_file() or sha256_file(log_path) != log.get("sha256"):
                            findings.append({"severity": "error", "code": "GENERATION_INPUT_GATE_LOG_DRIFT", "gate": gate.get("id"), "stream": log_name})
                    tool = gate.get("tool", {})
                    snapshot = tool.get("snapshot", {}) if isinstance(tool, dict) else {}
                    snapshot_path = Path(str(snapshot.get("path", ""))).resolve()
                    if not snapshot_path.is_file() or sha256_file(snapshot_path) != snapshot.get("sha256"):
                        findings.append({"severity": "error", "code": "GENERATION_INPUT_GATE_TOOL_DRIFT", "gate": gate.get("id")})
                    for dependency in gate.get("dependencies", []):
                        dependency_snapshot = dependency.get("snapshot", {})
                        dependency_path = Path(str(dependency_snapshot.get("path", ""))).resolve()
                        if not dependency_path.is_file() or sha256_file(dependency_path) != dependency_snapshot.get("sha256"):
                            findings.append({"severity": "error", "code": "GENERATION_INPUT_GATE_DEPENDENCY_DRIFT", "gate": gate.get("id"), "role": dependency.get("role")})
                generation_lock_valid = (
                    generation_lock.get("status") == "pass"
                    and generation_report.get("status") == "pass"
                    and expected_gate_ids <= passed_gate_ids
                    and writing_rule_freshness in {"current-bound", "historical-bound"}
                )
    if payload.get("document_type") == "mcm" and payload.get("candidates") and not generation_lock_valid:
        findings.append({"severity": "error", "code": "MCM_CANDIDATE_WITHOUT_GENERATION_INPUT_LOCK"})
    seen: set[str] = set()
    for candidate in payload.get("candidates", []):
        candidate_id = str(candidate.get("id", ""))
        if not candidate_id or candidate_id in seen:
            findings.append({"severity": "error", "code": "CANDIDATE_ID_INVALID", "id": candidate_id})
        seen.add(candidate_id)
        path = Path(candidate.get("output_path", ""))
        if candidate.get("input_sha256") != authority.get("main_sha256"):
            findings.append({"severity": "error", "code": "CANDIDATE_NOT_FROM_FROZEN_SOURCE", "id": candidate_id})
        if candidate.get("parent_candidate") is not None or candidate.get("pass_count") != 1:
            findings.append({"severity": "error", "code": "SERIAL_OR_MULTI_PASS_CANDIDATE", "id": candidate_id})
        if not path.is_file() or sha256_file(path) != candidate.get("output_sha256"):
            findings.append({"severity": "error", "code": "CANDIDATE_FILE_DRIFT", "id": candidate_id})
        verification_path = Path(candidate.get("verification_report", ""))
        if (
            not verification_path.is_file()
            or sha256_file(verification_path) != candidate.get("verification_report_sha256")
        ):
            findings.append({
                "severity": "error", "code": "CANDIDATE_VERIFICATION_REPORT_DRIFT",
                "id": candidate_id, "path": str(verification_path),
            })
        for output_file in candidate.get("output_files", []):
            output_path = Path(output_file.get("path", ""))
            if not output_path.is_file() or sha256_file(output_path) != output_file.get("sha256"):
                findings.append({
                    "severity": "error", "code": "CANDIDATE_TREE_FILE_DRIFT",
                    "id": candidate_id, "path": str(output_path),
                })
    selection = payload.get("selection", {})
    accepted = selection.get("accepted")
    if accepted is not None:
        if accepted == SOURCE_ID:
            selected_path = Path(authority.get("main_path", ""))
            selected_sha256 = authority.get("main_sha256")
            selected_files = [
                {"relative_path": item.get("relative_path"), "sha256": item.get("sha256")}
                for item in authority.get("files", [])
            ]
        else:
            selected = next((item for item in payload.get("candidates", []) if item.get("id") == accepted), None)
            if selected is None:
                findings.append({"severity": "error", "code": "ACCEPTED_CANDIDATE_MISSING", "id": accepted})
                selected_path = Path("")
                selected_sha256 = None
                selected_files = []
            else:
                selected_path = Path(selected.get("output_path", ""))
                selected_sha256 = selected.get("output_sha256")
                selected_files = selected.get("output_files", [])
                if selected.get("verification_status") != "pass":
                    findings.append({"severity": "error", "code": "ACCEPTED_CANDIDATE_FAILED", "id": accepted})
        if selection.get("human_review") != "accepted" or selection.get("reviewer_kind") != "human" or not str(selection.get("reason") or "").strip():
            findings.append({"severity": "error", "code": "HUMAN_ACCEPTANCE_RECORD_MISSING"})
        if not str(selection.get("reviewer") or "").strip():
            findings.append({"severity": "error", "code": "HUMAN_REVIEWER_MISSING"})
        if (
            str(selected_path.resolve()) != str(Path(selection.get("target_path", "")).resolve())
            or selected_sha256 != selection.get("target_sha256")
        ):
            findings.append({"severity": "error", "code": "SELECTED_TARGET_MISMATCH", "id": accepted})
        if _tree_sha256(selected_files, "relative_path") != selection.get("target_tree_sha256"):
            findings.append({"severity": "error", "code": "SELECTED_TARGET_TREE_MISMATCH", "id": accepted})
        compile_resource_files = selection.get("compile_resource_files")
        if not isinstance(compile_resource_files, list) or not compile_resource_files:
            findings.append({"severity": "error", "code": "SELECTED_COMPILE_RESOURCE_LOCK_MISSING"})
        else:
            for resource in compile_resource_files:
                resource_path = Path(resource.get("path", ""))
                if not resource_path.is_file() or sha256_file(resource_path) != resource.get("sha256"):
                    findings.append({
                        "severity": "error", "code": "SELECTED_COMPILE_RESOURCE_DRIFT",
                        "path": str(resource_path),
                    })
            recorded_resource_tree = _tree_sha256(compile_resource_files, "relative_path")
            if recorded_resource_tree != selection.get("compile_resource_tree_sha256"):
                findings.append({
                    "severity": "error", "code": "SELECTED_COMPILE_RESOURCE_TREE_MISMATCH",
                })
            if selected_path.is_file():
                try:
                    current_resources = _compile_resource_records(selected_path)
                except (FileNotFoundError, ValueError) as exc:
                    findings.append({
                        "severity": "error", "code": "SELECTED_COMPILE_RESOURCE_DISCOVERY_FAILED",
                        "message": str(exc),
                    })
                else:
                    if _tree_sha256(current_resources, "relative_path") != recorded_resource_tree:
                        findings.append({
                            "severity": "error", "code": "SELECTED_COMPILE_RESOURCE_SET_MISMATCH",
                        })
        blind = selection.get("blind_score")
        if blind:
            blind_path = Path(blind.get("path", ""))
            if not blind_path.is_file() or sha256_file(blind_path) != blind.get("sha256"):
                findings.append({"severity": "error", "code": "BLIND_SCORE_DRIFT", "path": str(blind_path)})
            for label, evidence in blind.get("evidence", {}).items():
                evidence_path = Path(evidence.get("path", ""))
                if not evidence_path.is_file() or sha256_file(evidence_path) != evidence.get("sha256"):
                    findings.append({
                        "severity": "error", "code": "BLIND_EVIDENCE_DRIFT",
                        "kind": label, "path": str(evidence_path),
                    })
            merge_evidence = blind.get("evidence", {}).get("merge_report", {})
            merge_path = Path(merge_evidence.get("path", ""))
            if merge_path.is_file():
                merge_audit = audit_merge_report(merge_path)
                if merge_audit.get("status") != "pass":
                    findings.append({
                        "severity": "error",
                        "code": "BLIND_MERGE_REPORT_INVALID",
                        "merge_findings": merge_audit.get("findings", []),
                    })

    gate_run = payload.get("release_gate_run")
    gate_report = None
    if gate_run:
        report_path = Path(gate_run.get("path", ""))
        if not report_path.is_file() or sha256_file(report_path) != gate_run.get("sha256"):
            findings.append({"severity": "error", "code": "RELEASE_GATE_REPORT_DRIFT", "path": str(report_path)})
        else:
            try:
                gate_report = json.loads(report_path.read_text(encoding="utf-8-sig"))
            except json.JSONDecodeError:
                findings.append({"severity": "error", "code": "RELEASE_GATE_REPORT_INVALID", "path": str(report_path)})
        if gate_report:
            if gate_report.get("schema") != "aigc-mcm-release-gates/v1":
                findings.append({"severity": "error", "code": "RELEASE_GATE_SCHEMA_MISMATCH"})
            if gate_report.get("status") != gate_run.get("status"):
                findings.append({"severity": "error", "code": "RELEASE_GATE_STATUS_MISMATCH"})
            report_target = gate_report.get("target", {})
            if (
                report_target.get("id") != selection.get("accepted")
                or report_target.get("sha256") != selection.get("target_sha256")
                or report_target.get("tree_sha256") != selection.get("target_tree_sha256")
                or report_target.get("release_tree_sha256")
                != selection.get("compile_resource_tree_sha256")
            ):
                findings.append({"severity": "error", "code": "RELEASE_GATE_TARGET_MISMATCH"})
            release_target_path = Path(report_target.get("release_path", ""))
            if not release_target_path.is_file() or sha256_file(release_target_path) != report_target.get("sha256"):
                findings.append({
                    "severity": "error", "code": "RELEASE_SELECTED_MAIN_DRIFT",
                    "path": str(release_target_path),
                })
            release_files = report_target.get("files", [])
            for release_file in release_files:
                path = Path(release_file.get("path", ""))
                if not path.is_file() or sha256_file(path) != release_file.get("sha256"):
                    findings.append({
                        "severity": "error", "code": "RELEASE_SELECTED_TREE_DRIFT",
                        "path": str(path),
                    })
            release_tree_sha256 = (
                report_target.get("release_tree_sha256") or report_target.get("tree_sha256")
            )
            if _tree_sha256(release_files, "relative_path") != release_tree_sha256:
                findings.append({"severity": "error", "code": "RELEASE_SELECTED_TREE_HASH_MISMATCH"})
            passed = {item.get("id") for item in gate_report.get("gates", []) if item.get("status") == "pass"}
            if gate_report.get("status") == "pass" and not REQUIRED_RELEASE_GATES <= passed:
                findings.append({"severity": "error", "code": "RELEASE_REQUIRED_GATE_MISSING", "passed": sorted(passed)})
            generation_gate = next(
                (item for item in gate_report.get("gates", []) if item.get("id") == "generation-input-lock"),
                None,
            )
            if not isinstance(generation_gate, dict) or (
                generation_gate.get("writing_rule_tree_sha256")
                != generation_lock.get("writing_rule_tree_sha256")
                or generation_gate.get("writing_rule_count") != generation_lock.get("writing_rule_count")
                or generation_gate.get("writing_rule_freshness") != writing_rule_freshness
            ):
                findings.append({"severity": "error", "code": "RELEASE_WRITING_RULE_LOCK_MISMATCH"})
            for input_record in gate_report.get("inputs", {}).values():
                path = Path(input_record.get("path", ""))
                if not path.is_file() or sha256_file(path) != input_record.get("sha256"):
                    findings.append({"severity": "error", "code": "RELEASE_INPUT_DRIFT", "path": str(path)})
            for gate in gate_report.get("gates", []):
                for log_name in ("stdout", "stderr"):
                    log = gate.get(log_name)
                    if not log:
                        continue
                    path = Path(log.get("path", ""))
                    if not path.is_file() or sha256_file(path) != log.get("sha256"):
                        findings.append({"severity": "error", "code": "RELEASE_GATE_LOG_DRIFT", "path": str(path)})
                tool = gate.get("tool")
                if tool:
                    snapshot = tool.get("snapshot")
                    if snapshot:
                        path = Path(snapshot.get("path", ""))
                        if not path.is_file() or sha256_file(path) != snapshot.get("sha256"):
                            findings.append({
                                "severity": "error", "code": "RELEASE_GATE_TOOL_SNAPSHOT_DRIFT",
                                "path": str(path),
                            })
                    elif not tool.get("source_sha256"):
                        findings.append({"severity": "error", "code": "RELEASE_GATE_TOOL_HASH_MISSING"})
                for dependency in gate.get("dependencies", []):
                    snapshot = dependency.get("snapshot")
                    if not snapshot:
                        findings.append({
                            "severity": "error", "code": "RELEASE_GATE_DEPENDENCY_SNAPSHOT_MISSING",
                            "path": dependency.get("source_path"),
                        })
                        continue
                    path = Path(snapshot.get("path", ""))
                    if not path.is_file() or sha256_file(path) != snapshot.get("sha256"):
                        findings.append({
                            "severity": "error", "code": "RELEASE_GATE_DEPENDENCY_SNAPSHOT_DRIFT",
                            "path": str(path),
                        })
            artifact_kinds = set()
            for artifact in gate_report.get("artifacts", []):
                path = Path(artifact.get("path", ""))
                artifact_kinds.add(artifact.get("kind"))
                if not path.is_file() or sha256_file(path) != artifact.get("sha256"):
                    findings.append({"severity": "error", "code": "RELEASE_ARTIFACT_DRIFT", "path": str(path)})
            if gate_report.get("status") == "pass" and not {"pdf", "aux", "tex-log"} <= artifact_kinds:
                findings.append({"severity": "error", "code": "RELEASE_COMPILE_ARTIFACT_MISSING"})

    final_review = payload.get("final_review")
    if payload.get("state") == "RELEASE_READY":
        if not gate_run or gate_run.get("status") != "pass":
            findings.append({"severity": "error", "code": "RELEASE_READY_WITHOUT_PASSING_GATES"})
        if (
            not final_review
            or final_review.get("status") != "accepted"
            or final_review.get("reviewer_kind") != "human"
            or not str(final_review.get("reviewer") or "").strip()
            or not str(final_review.get("review_note") or "").strip()
        ):
            findings.append({"severity": "error", "code": "FINAL_RENDER_REVIEW_MISSING"})
        elif not RENDER_CHECKS <= set(final_review.get("checked", [])):
            findings.append({"severity": "error", "code": "FINAL_RENDER_CHECKLIST_INCOMPLETE"})
    errors = sum(item["severity"] == "error" for item in findings)
    return {
        "schema": "aigc-longform-audit/v1",
        "status": "pass" if errors == 0 else "fail",
        "manifest": str(manifest_path),
        "state": payload.get("state"),
        "source_files": len(authority.get("files", [])),
        "chunks": len(payload.get("chunks", [])),
        "candidates": len(payload.get("candidates", [])),
        "writing_rule_freshness": writing_rule_freshness,
        "errors": errors,
        "findings": findings,
        "gates": payload.get("gates", []),
    }


def _print(report: dict, label: str, fmt: str) -> None:
    if fmt == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    print(f"{label} {report.get('status', 'pass').upper()}")
    for key in ("manifest", "state", "source_files", "chunks", "candidates"):
        if key in report:
            print(f"{key}={report[key]}")
    for finding in report.get("findings", []):
        detail = ", ".join(
            f"{key}={value}" for key, value in finding.items() if key not in {"severity", "code"}
        )
        print(f"[{finding['severity'].upper()}] {finding['code']}: {detail}")


def main() -> int:
    skill_root = Path(__file__).resolve().parents[1]
    default_registry = skill_root / "references" / "stack-registry.json"
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    init_parser = sub.add_parser("init")
    init_parser.add_argument("source", type=Path)
    init_parser.add_argument("--output-dir", type=Path, required=True)
    init_parser.add_argument("--document-type", choices=("mcm", "modeling", "research", "course-notes", "academic-en", "medical-en"), required=True)
    init_parser.add_argument("--problem-type", choices=("A", "B", "C"))
    init_parser.add_argument("--registry", type=Path, default=default_registry)
    init_parser.add_argument("--coverage", type=Path)
    init_parser.add_argument("--aux", type=Path)
    init_parser.add_argument("--math-contract", type=Path)
    init_parser.add_argument("--repro-manifest", type=Path)
    init_parser.add_argument("--result-manifest", type=Path)
    init_parser.add_argument("--workbench", type=Path)
    init_parser.add_argument("--preflight", type=Path)
    init_parser.add_argument("--reasoning-review", type=Path)
    init_parser.add_argument("--evidence-bundle", type=Path)
    init_parser.add_argument("--style-decisions", type=Path)
    init_parser.add_argument("--portfolio-plan", type=Path)
    init_parser.add_argument("--style-retrieval-plan", type=Path)
    init_parser.add_argument("--authoring-brief", type=Path)
    init_parser.add_argument("--judgment-ledger", type=Path)
    init_parser.add_argument("--drafting-packet-index", type=Path)
    init_parser.add_argument("--drafting-usage", type=Path)
    init_parser.add_argument("--artifact", action="append", default=[])
    init_parser.add_argument("--format", choices=("text", "json"), default="text")

    lock_parser = sub.add_parser("lock-generation")
    lock_parser.add_argument("manifest", type=Path)
    lock_parser.add_argument("--workbench", type=Path, required=True)
    lock_parser.add_argument("--preflight", type=Path, required=True)
    lock_parser.add_argument("--style-retrieval-plan", type=Path, required=True)
    lock_parser.add_argument("--authoring-brief", type=Path, required=True)
    lock_parser.add_argument("--drafting-packet-index", type=Path, required=True)
    lock_parser.add_argument("--output", type=Path)
    lock_parser.add_argument("--format", choices=("text", "json"), default="text")

    register_parser = sub.add_parser("register")
    register_parser.add_argument("manifest", type=Path)
    register_parser.add_argument("candidate", type=Path)
    register_parser.add_argument("--provider", required=True)
    register_parser.add_argument("--candidate-id", required=True)
    register_parser.add_argument("--output", type=Path)
    register_parser.add_argument("--format", choices=("text", "json"), default="text")

    select_parser = sub.add_parser("select")
    select_parser.add_argument("manifest", type=Path)
    select_parser.add_argument("--candidate-id", required=True)
    select_parser.add_argument("--reviewer", required=True)
    select_parser.add_argument("--reason", required=True)
    select_parser.add_argument("--blind-score", type=Path)
    select_parser.add_argument("--reviewer-kind", choices=("human", "model"), required=True)
    select_parser.add_argument("--output", type=Path)
    select_parser.add_argument("--format", choices=("text", "json"), default="text")

    gates_parser = sub.add_parser("run-gates")
    gates_parser.add_argument("manifest", type=Path)
    gates_parser.add_argument("--output-dir", type=Path, required=True)
    gates_parser.add_argument("--coverage", type=Path, required=True)
    gates_parser.add_argument("--math-contract", type=Path, required=True)
    gates_parser.add_argument("--repro-manifest", type=Path, required=True)
    gates_parser.add_argument("--result-manifest", type=Path, required=True)
    gates_parser.add_argument("--workbench", type=Path, required=True)
    gates_parser.add_argument("--preflight", type=Path, required=True)
    gates_parser.add_argument("--reasoning-review", type=Path, required=True)
    gates_parser.add_argument("--evidence-bundle", type=Path, required=True)
    gates_parser.add_argument("--style-decisions", type=Path)
    gates_parser.add_argument("--portfolio-plan", type=Path, required=True)
    gates_parser.add_argument("--style-retrieval-plan", type=Path, required=True)
    gates_parser.add_argument("--authoring-brief", type=Path, required=True)
    gates_parser.add_argument("--judgment-ledger", type=Path, required=True)
    gates_parser.add_argument("--drafting-packet-index", type=Path, required=True)
    gates_parser.add_argument("--drafting-usage", type=Path, required=True)
    gates_parser.add_argument("--output", type=Path)
    gates_parser.add_argument("--format", choices=("text", "json"), default="text")

    finalize_parser = sub.add_parser("finalize")
    finalize_parser.add_argument("manifest", type=Path)
    finalize_parser.add_argument("--reviewer", required=True)
    finalize_parser.add_argument("--review-note", required=True)
    finalize_parser.add_argument("--reviewer-kind", choices=("human", "model"), required=True)
    finalize_parser.add_argument("--checked", action="append", choices=sorted(RENDER_CHECKS), required=True)
    finalize_parser.add_argument("--output", type=Path)
    finalize_parser.add_argument("--format", choices=("text", "json"), default="text")

    audit_parser = sub.add_parser("audit")
    audit_parser.add_argument("manifest", type=Path)
    audit_parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()

    if args.command == "init":
        if args.document_type == "mcm" and not args.problem_type:
            parser.error("--problem-type is required for mcm")
        manifest_path, manifest = initialise(
            args.source, args.output_dir, args.document_type, args.problem_type,
            args.registry, args.coverage, args.aux, args.math_contract,
            args.repro_manifest, args.result_manifest, args.workbench,
            args.preflight, args.reasoning_review, args.artifact, args.evidence_bundle,
            args.style_decisions,
            args.portfolio_plan,
            args.style_retrieval_plan,
            args.authoring_brief,
            args.judgment_ledger,
            args.drafting_packet_index,
            args.drafting_usage,
        )
        report = {
            "status": "pass", "manifest": str(manifest_path), "state": manifest["state"],
            "source_files": len(manifest["authority"]["files"]),
            "chunks": len(manifest["chunks"]), "candidates": 0,
        }
        _print(report, "LONGFORM INIT", args.format)
        return 0
    if args.command == "register":
        output, manifest, verification = register_candidate(
            args.manifest, args.candidate, args.provider, args.candidate_id, args.output,
        )
        report = {
            "status": verification["status"], "manifest": str(output),
            "state": manifest["state"], "candidates": len(manifest["candidates"]),
            "findings": verification.get("findings", []),
        }
        _print(report, "LONGFORM REGISTER", args.format)
        return 0 if verification["status"] == "pass" else 1
    if args.command == "lock-generation":
        output, manifest, lock_report = lock_generation_inputs(
            args.manifest, args.workbench, args.preflight,
            args.style_retrieval_plan, args.authoring_brief,
            args.drafting_packet_index, args.output,
        )
        report = {
            "status": lock_report["status"], "manifest": str(output),
            "state": manifest["state"], "gates": lock_report["gates"],
        }
        _print(report, "LONGFORM GENERATION LOCK", args.format)
        return 0 if lock_report["status"] == "pass" else 1
    if args.command == "select":
        output, manifest = select_target(
            args.manifest, args.candidate_id, args.reviewer, args.reason,
            args.blind_score, args.output, args.reviewer_kind,
        )
        report = {
            "status": "pass", "manifest": str(output), "state": manifest["state"],
            "selection": manifest["selection"],
        }
        _print(report, "LONGFORM SELECT", args.format)
        return 0
    if args.command == "run-gates":
        output, manifest, gate_report = run_release_gates(
            args.manifest, args.output_dir, args.coverage, args.math_contract,
            args.repro_manifest, args.result_manifest, args.workbench,
            args.preflight, args.reasoning_review, args.evidence_bundle,
            args.portfolio_plan, args.style_decisions, args.output,
            args.style_retrieval_plan,
            args.authoring_brief,
            judgment_ledger=args.judgment_ledger,
            drafting_packet_index=args.drafting_packet_index,
            drafting_usage=args.drafting_usage,
        )
        report = {
            "status": gate_report["status"], "manifest": str(output),
            "state": manifest["state"], "gates": gate_report["gates"],
            "artifacts": gate_report["artifacts"],
        }
        _print(report, "LONGFORM GATES", args.format)
        return 0 if gate_report["status"] == "pass" else 1
    if args.command == "finalize":
        output, manifest = finalize_release(
            args.manifest, args.reviewer, args.review_note, args.checked, args.output, args.reviewer_kind,
        )
        report = {
            "status": "pass", "manifest": str(output), "state": manifest["state"],
            "final_review": manifest["final_review"],
        }
        _print(report, "LONGFORM FINALIZE", args.format)
        return 0
    report = audit_manifest(args.manifest)
    _print(report, "LONGFORM AUDIT", args.format)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
