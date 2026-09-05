#!/usr/bin/env python3
"""Validate a Chinese academic-style rewrite or supplied-content draft."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import check_humanize_invariants as invariants  # noqa: E402
import extract_detector_report_scope as detector_scope  # noqa: E402
import scan_humanize_chinese as lexical  # noqa: E402


VAGUE_REASON_RE = re.compile(
    r"^(?:(?:经过)?(?:人工)?(?:已经|已)?(?:确认|复核|审核)(?:保留|接受|通过|无误|确认)?"
    r"(?:此项|该项|内容|原句)?|(?:这是|此为|属于)?(?:一个)?(?:具体)?理由|"
    r"(?:用户)?(?:要求|同意)?(?:保留|接受)|"
    r"(?:此处|这里|该处|本处|此项|该项)?(?:表达|内容|语句)?功能(?:需要|应当|必须)?保留)$"
)
SPECIFIC_REASON_ANCHORS = (
    "用户",
    "题面",
    "原句",
    "术语",
    "定义",
    "引用",
    "法规",
    "方法",
    "材料",
    "算法",
    "名称",
    "结论",
    "否定",
    "模态",
    "语气",
    "重复",
    "范围",
    "表达",
    "功能",
    "上下文",
    "证据",
    "锁定",
    "命令",
    "条件",
)
WARNING_REVIEW_REQUEST_SCHEMA = "humanize-warning-review-request/v1"
PAIRED_QUALITY_REVIEW_REQUEST_SCHEMA = "humanize-paired-quality-review-request/v1"
DIRECT_VALIDATION_EVIDENCE_SCHEMA = "humanize-direct-validation-evidence/v5"
DIRECT_VALIDATION_EVIDENCE_ERROR_SCHEMA = "humanize-direct-validation-evidence-error/v1"
DIRECT_VALIDATION_INPUT_ERROR_SCHEMA = "humanize-direct-validation-input-error/v1"
VALIDATION_INVOCATION_SCHEMA = "humanize-validation-invocation/v4"
VALIDATION_RUN_PREFIX = "hvr4"
VALIDATION_MODES = ("REWRITE", "DRAFT")
TEMPLATE_FIELD_EDIT_SCOPE_SCHEMA = "humanize-template-field-edit-scope/v1"
TEMPLATE_FIELD_SOURCE_ROLE = "TEMPLATE_FIELD"
TEMPLATE_FIELD_PERMISSION = "PAYLOAD_ONLY"
TEMPLATE_FIELD_LABELS = ("适用题目", "逻辑链条", "给定首句", "用词建议")
TEMPLATE_FIELD_LINE_RE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<label>适用题目|逻辑链条|给定首句|用词建议)"
    r"(?P<separator>[：:])(?P<payload>.*)$"
)
TEMPLATE_FIELD_APPLICABILITY_OBJECTS = (
    "题目",
    "话题",
    "主题",
    "命题",
    "任务",
)
TEMPLATE_FIELD_APPLICABILITY_PREDICATES = (
    "带有",
    "涉及",
    "强调",
    "要求",
    "需要",
    "适合",
    "适用于",
    "围绕",
    "讨论",
    "说明",
)
TEMPLATE_FIELD_DIRECTIVE_MARKERS = (
    "要求",
    "请",
    "应当",
    "应该",
    "必须",
    "展开",
    "说明",
    "分析",
    "讨论",
    "论证",
)
TEMPLATE_FIELD_STRONG_FORCE_MARKERS = (
    "更是",
    "必须",
    "务必",
    "绝不能",
    "不得",
    "当务之急",
    "必然",
)
TEMPLATE_FIELD_WEAK_FORCE_MARKERS = (
    "也能",
    "可能",
    "可以",
    "有望",
    "或许",
    "似乎",
)
TEMPLATE_FIELD_NEGATION_MARKERS = (
    "不是",
    "并非",
    "不能",
    "不可",
    "不得",
    "绝不能",
    "不应",
    "不会",
)
TEMPLATE_FIELD_CAUSAL_CONDITION_MARKERS = (
    "因此",
    "因而",
    "所以",
    "由于",
    "鉴于",
    "如果",
    "若",
    "则",
    "从而",
)
TEMPLATE_FIELD_RANGE_MARKERS = (
    "所有",
    "任何",
    "均",
    "都",
    "仅",
    "只",
    "主要",
    "普遍",
    "特定",
)
_PAIRED_QUALITY_CONTRACT_NAME = "paired" + "-quality-clearance-contract.md"
_PAIRED_QUALITY_VERIFIER_NAME = "verify" + "_humanize_paired_quality_response.py"
DRAFT_DERIVED_COMPARISON_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "DRAFT-COMP-01",
        re.compile(
            r"(?:降幅|增幅|末值|数值|指标|结果|变化)"
            r"[^。！？!?；;\n]{0,18}?(?:更大|更小|更高|更低|高于|低于)"
        ),
    ),
    (
        "DRAFT-COMP-02",
        re.compile(
            r"(?:高于|低于|超过|小于)[^。！？!?；;\n]{0,24}?"
            r"(?:情景|对照|基线|组)"
        ),
    ),
    (
        "DRAFT-COMP-03",
        re.compile(
            r"(?:进一步|更进一步)[^。！？!?；;\n]{0,14}?"
            r"(?:侵蚀|下降|上升|降低|提高|扩大|缩小)"
        ),
    ),
)

# These paired transitions come from a real COURSE forward test in which a
# mechanically clean candidate erased a coherent teaching voice.  They are
# deliberately hunk-bound and cluster-gated: no individual word is a ban.
COURSE_VOICE_FLATTENING_TRANSITIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "COURSE-FLAT-01",
        "family": "bounded_directness",
        "removed_forms": ("完全够用",),
        "introduced_forms": ("足以描述", "足以说明", "足以刻画"),
    },
    {
        "id": "COURSE-FLAT-02",
        "family": "teaching_attention",
        "removed_forms": ("盯住",),
        "introduced_forms": ("考察", "进行考察"),
    },
    {
        "id": "COURSE-FLAT-03",
        "family": "contrast_emphasis",
        "removed_forms": ("明明",),
        "introduced_forms": ("仍随", "仍然随"),
    },
    {
        "id": "COURSE-FLAT-04",
        "family": "process_motion",
        "removed_forms": ("跟着变",),
        "introduced_forms": ("随之变化", "相应变化"),
    },
    {
        "id": "COURSE-FLAT-05",
        "family": "relation_fit",
        "removed_forms": ("接得上",),
        "introduced_forms": ("严格对应", "相互对应"),
    },
    {
        "id": "COURSE-FLAT-06",
        "family": "local_explanatory_metaphor",
        "removed_forms": ("记成",),
        "introduced_forms": ("纳入", "归入"),
    },
    {
        "id": "COURSE-FLAT-07",
        "family": "supplement_relation",
        "removed_forms": ("补成",),
        "introduced_forms": ("改写为", "写为"),
    },
    {
        "id": "COURSE-FLAT-08",
        "family": "local_explanatory_metaphor",
        "removed_forms": ("统一记账",),
        "introduced_forms": ("合在一起", "统一处理"),
    },
    {
        "id": "COURSE-FLAT-09",
        "family": "local_explanatory_metaphor",
        "removed_forms": ("记账始终一致", "记账保持一致"),
        "introduced_forms": ("总电流始终一致", "总电流保持一致"),
    },
)
COURSE_VOICE_FLATTENING_POLICY_REVISION = (
    "humanize-course-voice-non-regression/v3"
)
COURSE_VOICE_FLATTENING_MIN_TRANSITIONS = 4
COURSE_VOICE_FLATTENING_MIN_FAMILIES = 3
COURSE_VOICE_FLATTENING_MIN_HUNKS = 3
COURSE_VOICE_FLATTENING_MAX_CLUSTER_CHARS = 1200
COURSE_VOICE_FLATTENING_MAX_CLUSTER_LINES = 24
COURSE_VOICE_FLATTENING_MAX_EQUAL_BRIDGE = 1


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _pretty_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _absolute_without_resolving(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _assert_no_reparse_ancestors(path: Path) -> None:
    current = _absolute_without_resolving(path)
    while True:
        if current.exists() or current.is_symlink():
            info = current.lstat()
            attributes = int(getattr(info, "st_file_attributes", 0))
            if current.is_symlink() or attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise ValueError(f"evidence path crosses a symlink or reparse point: {current}")
        parent = current.parent
        if parent == current:
            return
        current = parent


def _write_exclusive(path: Path, raw: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def _assert_capturable_file(path: Path, *, label: str) -> Path:
    absolute = _absolute_without_resolving(path)
    _assert_no_reparse_ancestors(absolute)
    info = absolute.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError(f"{label} must be a regular file")
    if int(getattr(info, "st_nlink", 1)) != 1:
        raise ValueError(f"{label} must not be a hard link")
    return absolute


def _strict_json_bytes(raw: bytes, *, label: str) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"{label} contains duplicate JSON key: {key}")
            result[key] = value
        return result

    def reject_nonfinite(value: str) -> Any:
        raise ValueError(f"{label} contains non-finite JSON number: {value}")

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"{label} must be UTF-8 JSON") from error
    try:
        return json.loads(
            text,
            object_pairs_hook=reject_duplicates,
            parse_constant=reject_nonfinite,
        )
    except json.JSONDecodeError as error:
        raise ValueError(f"{label} is invalid JSON: {error.msg}") from error


def _capture_record(path: Path, raw: bytes, *, archive_path: str) -> dict[str, Any]:
    return {
        "archive_path": archive_path,
        "original_suffix": path.suffix,
        "sha256": _sha256(raw),
        "size": len(raw),
    }


def _archive_report_scope_bytes(scope_payload: dict[str, Any]) -> bytes:
    archived = json.loads(json.dumps(scope_payload, ensure_ascii=False))
    archived["report_path"] = "inputs/report.bin"
    archived["source_path"] = "inputs/before.bin"
    return _pretty_json_bytes(archived)


def _report_scope_semantic_sha256(scope_payload: dict[str, Any]) -> str:
    semantic = json.loads(json.dumps(scope_payload, ensure_ascii=False))
    semantic["report_path"] = "<ARCHIVED_REPORT>"
    semantic["source_path"] = "<ARCHIVED_SOURCE>"
    return _sha256(_canonical_json_bytes(semantic))


def _build_invocation_request(
    payload: dict[str, Any],
    *,
    before: Path,
    after: Path,
    mode: str | None = None,
    scene: str | None = None,
    output_format: str = "json",
    strict_speech_acts: bool = False,
    fragment_mode: bool = False,
    report_scope_path: Path | None = None,
    template_field_edit_scope_path: Path | None = None,
    protected_terms: Sequence[str] = (),
) -> dict[str, Any]:
    evidence = payload.get("evidence")
    if not isinstance(evidence, dict):
        raise ValueError("validation payload is missing evidence bindings")

    before_path = _assert_capturable_file(before, label="before artifact")
    after_path = _assert_capturable_file(after, label="after artifact")
    before_raw = before_path.read_bytes()
    after_raw = after_path.read_bytes()
    if _sha256(before_raw) != str(evidence.get("before_sha256", "")):
        raise ValueError("before artifact changed after validation")
    if _sha256(after_raw) != str(evidence.get("after_sha256", "")):
        raise ValueError("after artifact changed after validation")

    inputs: dict[str, Any] = {
        "before": _capture_record(
            before_path,
            before_raw,
            archive_path="inputs/before.bin",
        ),
        "after": _capture_record(
            after_path,
            after_raw,
            archive_path="inputs/after.bin",
        ),
    }
    report_scope: dict[str, Any] = {"provided": False}
    if report_scope_path is not None:
        scope_path = _assert_capturable_file(
            report_scope_path,
            label="report scope artifact",
        )
        scope_raw = scope_path.read_bytes()
        scope_payload = _strict_json_bytes(scope_raw, label="report scope artifact")
        if not isinstance(scope_payload, dict):
            raise ValueError("report scope artifact must contain a JSON object")
        report_path = _assert_capturable_file(
            _resolve_scope_locator(
                scope_path,
                scope_payload.get("report_path"),
                field="report_path",
            ),
            label="detector report artifact",
        )
        report_raw = report_path.read_bytes()
        archived_scope_raw = _archive_report_scope_bytes(scope_payload)
        scope_check = payload.get("report_scope_check")
        if not isinstance(scope_check, dict) or scope_check.get("status") != "PASS":
            raise ValueError("report scope was not validated as PASS")
        if _report_scope_semantic_sha256(scope_payload) != str(
            scope_check.get("scope_semantic_sha256", "")
        ):
            raise ValueError("report scope artifact changed after validation")
        if _sha256(report_raw) != str(scope_check.get("report_sha256", "")):
            raise ValueError("detector report artifact changed after validation")
        inputs["report_scope"] = _capture_record(
            scope_path,
            archived_scope_raw,
            archive_path="inputs/report-scope.json",
        )
        inputs["report"] = _capture_record(
            report_path,
            report_raw,
            archive_path="inputs/report.bin",
        )
        report_scope = {
            "provided": True,
            "scope_archive_path": "inputs/report-scope.json",
            "report_archive_path": "inputs/report.bin",
            "report_original_suffix": report_path.suffix,
            "scope_semantic_sha256": str(
                scope_check.get("scope_semantic_sha256") or ""
            ),
        }

    template_field_edit_scope: dict[str, Any] = {"provided": False}
    if template_field_edit_scope_path is not None:
        scope_path = _assert_capturable_file(
            template_field_edit_scope_path,
            label="template field edit scope artifact",
        )
        scope_raw = scope_path.read_bytes()
        scope_check, _authorization_by_line = _load_template_field_edit_scope(
            scope_path,
            before_raw=before_raw,
            before_text=before_raw.decode("utf-8-sig"),
            document_format=str(evidence.get("document_format", "")),
        )
        recorded_scope_check = payload.get("template_field_edit_scope_check")
        if not isinstance(recorded_scope_check, dict) or recorded_scope_check != scope_check:
            raise ValueError("template field edit scope changed after validation")
        inputs["template_field_edit_scope"] = _capture_record(
            scope_path,
            scope_raw,
            archive_path="inputs/template-field-edit-scope.json",
        )
        template_field_edit_scope = {
            "provided": True,
            "archive_path": "inputs/template-field-edit-scope.json",
            "sha256": str(scope_check["scope_sha256"]),
            "source_sha256": str(scope_check["source_sha256"]),
            "permission_boundary": TEMPLATE_FIELD_PERMISSION,
            "local_clearance_supported": False,
        }

    warning_proposal = payload.get("warning_proposal_state")
    if not isinstance(warning_proposal, dict):
        warning_proposal = {}
    warning_resolutions = payload.get("warning_resolutions")
    if not isinstance(warning_resolutions, dict):
        warning_resolutions = {}
    replay_reasons: list[str] = []
    replay_reasons = sorted(set(replay_reasons))
    recorded_policy_hashes = evidence.get("policy_hashes")
    if not isinstance(recorded_policy_hashes, dict):
        raise ValueError("validation payload is missing policy hash evidence")
    if _policy_hashes() != recorded_policy_hashes:
        raise ValueError("validation policy changed before evidence capture")

    invocation_body = {
        "schema": VALIDATION_INVOCATION_SCHEMA,
        "validator_entrypoint": "scripts/validate_humanize_output.py",
        "arguments": {
            "mode": str(mode or payload.get("mode", "REWRITE")).upper(),
            "scene": str(scene or payload.get("scene", "AUTO")).upper(),
            "document_format": str(evidence.get("document_format", "")),
            "output_format": output_format,
            "strict_speech_acts": bool(strict_speech_acts),
            "fragment_mode": bool(fragment_mode),
            "protected_terms": list(protected_terms),
            "keep_reasons": dict(sorted(payload.get("keep_reasons", {}).items())),
            "warning_resolutions": dict(sorted(warning_resolutions.items())),
            "warning_review_request_sha256": str(
                warning_proposal.get("warning_review_request_sha256") or ""
            ),
            "report_scope": report_scope,
            "template_field_edit_scope": template_field_edit_scope,
        },
        "inputs": inputs,
        "policy_hashes": recorded_policy_hashes,
        "expected": {
            "delivery_gate_status": str(payload.get("delivery_gate_status", "")),
            "exit_code": int(payload.get("exit_code", 1)),
            "paired_quality_review_request_sha256": str(
                (payload.get("paired_quality_review_request") or {}).get(
                    "request_sha256", ""
                )
            ),
        },
        "reexecution": {
            "status": (
                "REEXECUTION_NOT_SUPPORTED" if replay_reasons else "SUPPORTED"
            ),
            "reasons": replay_reasons,
        },
        "privacy": {
            "reviewer_identifier_collected": False,
            "stable_reviewer_pseudonym_archived": False,
            "source_locator_archived": False,
            "contains_unredacted_proposal_text": bool(warning_resolutions),
        },
    }
    invocation_sha = _sha256(_canonical_json_bytes(invocation_body))
    return {
        **invocation_body,
        "invocation_sha256": invocation_sha,
        "run_id": f"{VALIDATION_RUN_PREFIX}-{invocation_sha}",
    }


def _evidence_bundle_record(
    payload: dict[str, Any],
    *,
    run_id: str = "",
) -> dict[str, Any]:
    request = payload.get("paired_quality_review_request")
    request_path = (
        "paired-quality-review-request.json" if isinstance(request, dict) else ""
    )
    warning_request_path = (
        "warning-review-request.json"
        if isinstance(payload.get("warning_review_request"), dict)
        else ""
    )
    return {
        "status": "PERSISTED",
        "schema": DIRECT_VALIDATION_EVIDENCE_SCHEMA,
        "manifest_path": "evidence-manifest.json",
        "result_path": "validation-result.json",
        "invocation_path": "invocation-request.json",
        "rendered_output_path": "rendered-output.txt",
        "stderr_path": "stderr.txt",
        "execution_record_path": "execution-record.json",
        "paired_quality_request_path": request_path,
        "warning_review_request_path": warning_request_path,
        "run_id": run_id,
    }


def _persist_evidence_bundle(
    payload: dict[str, Any],
    *,
    before: Path,
    after: Path,
    output_dir: Path,
    invocation_request: dict[str, Any] | None = None,
    rendered_output: bytes | None = None,
    rendered_stderr: bytes = b"",
    report_scope_path: Path | None = None,
    template_field_edit_scope_path: Path | None = None,
) -> dict[str, Any]:
    output_dir = _absolute_without_resolving(output_dir)
    before_resolved = _assert_capturable_file(before, label="before artifact")
    after_resolved = _assert_capturable_file(after, label="after artifact")
    if output_dir in {before_resolved, after_resolved}:
        raise ValueError("evidence directory must not replace an input artifact")
    _assert_no_reparse_ancestors(output_dir.parent)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    _assert_no_reparse_ancestors(output_dir.parent)
    evidence = payload.get("evidence")
    if not isinstance(evidence, dict):
        raise ValueError("validation payload is missing evidence bindings")
    source_records: dict[str, dict[str, Any]] = {}
    input_artifacts: dict[str, bytes] = {}
    dependency_rechecks: list[tuple[str, Path, str]] = []
    for label, path, expected_key in (
        ("before", before_resolved, "before_sha256"),
        ("after", after_resolved, "after_sha256"),
    ):
        raw = path.read_bytes()
        actual_sha = _sha256(raw)
        expected_sha = str(evidence.get(expected_key, ""))
        if actual_sha != expected_sha:
            raise ValueError(f"{label} artifact changed after validation")
        source_records[label] = {
            "sha256": actual_sha,
            "size": len(raw),
        }
        input_artifacts[f"inputs/{label}.bin"] = raw

    if invocation_request is None:
        invocation_request = _build_invocation_request(
            payload,
            before=before,
            after=after,
            report_scope_path=report_scope_path,
            template_field_edit_scope_path=template_field_edit_scope_path,
        )
    invocation_body = dict(invocation_request)
    invocation_sha = str(invocation_body.pop("invocation_sha256", ""))
    run_id = str(invocation_body.pop("run_id", ""))
    if not re.fullmatch(r"[0-9a-f]{64}", invocation_sha):
        raise ValueError("invocation request has an invalid invocation_sha256")
    if _sha256(_canonical_json_bytes(invocation_body)) != invocation_sha:
        raise ValueError("invocation request self-hash mismatch")
    if run_id != f"{VALIDATION_RUN_PREFIX}-{invocation_sha}":
        raise ValueError("invocation request run_id mismatch")
    invocation_raw = _pretty_json_bytes(invocation_request)

    if report_scope_path is not None:
        scope_path = _assert_capturable_file(
            report_scope_path,
            label="report scope artifact",
        )
        scope_raw = scope_path.read_bytes()
        scope_payload = _strict_json_bytes(scope_raw, label="report scope artifact")
        if not isinstance(scope_payload, dict):
            raise ValueError("report scope artifact must contain a JSON object")
        report_path = _assert_capturable_file(
            _resolve_scope_locator(
                scope_path,
                scope_payload.get("report_path"),
                field="report_path",
            ),
            label="detector report artifact",
        )
        report_raw = report_path.read_bytes()
        archived_scope_raw = _archive_report_scope_bytes(scope_payload)
        for key, raw in (("report_scope", archived_scope_raw), ("report", report_raw)):
            record = invocation_request.get("inputs", {}).get(key)
            if not isinstance(record, dict):
                raise ValueError(f"invocation request is missing {key} binding")
            if _sha256(raw) != record.get("sha256") or len(raw) != record.get("size"):
                raise ValueError(f"{key} artifact changed after invocation capture")
        input_artifacts["inputs/report-scope.json"] = archived_scope_raw
        input_artifacts["inputs/report.bin"] = report_raw
        dependency_rechecks.extend(
            (
                ("report_scope", scope_path, _sha256(scope_raw)),
                ("report", report_path, _sha256(report_raw)),
            )
        )

    if template_field_edit_scope_path is not None:
        scope_path = _assert_capturable_file(
            template_field_edit_scope_path,
            label="template field edit scope artifact",
        )
        scope_raw = scope_path.read_bytes()
        record = invocation_request.get("inputs", {}).get(
            "template_field_edit_scope"
        )
        if not isinstance(record, dict):
            raise ValueError(
                "invocation request is missing template_field_edit_scope binding"
            )
        if _sha256(scope_raw) != record.get("sha256") or len(scope_raw) != record.get(
            "size"
        ):
            raise ValueError(
                "template field edit scope changed after invocation capture"
            )
        input_artifacts["inputs/template-field-edit-scope.json"] = scope_raw
        dependency_rechecks.append(
            ("template_field_edit_scope", scope_path, _sha256(scope_raw))
        )

    if rendered_output is None:
        rendered_output = _pretty_json_bytes(payload)

    artifacts: dict[str, bytes] = {
        **input_artifacts,
        "invocation-request.json": invocation_raw,
        "validation-result.json": _pretty_json_bytes(payload),
        "rendered-output.txt": rendered_output,
        "stderr.txt": rendered_stderr,
    }
    request = payload.get("paired_quality_review_request")
    if isinstance(request, dict):
        artifacts["paired-quality-review-request.json"] = _pretty_json_bytes(request)
    warning_request = payload.get("warning_review_request")
    if isinstance(warning_request, dict):
        artifacts["warning-review-request.json"] = _pretty_json_bytes(warning_request)
    execution_record = {
        "schema": "humanize-validation-execution-record/v1",
        "run_id": run_id,
        "intended_exit_code": int(payload.get("exit_code", 1)),
        "rendered_stdout_sha256": _sha256(rendered_output),
        "rendered_stderr_sha256": _sha256(rendered_stderr),
        "process_exit_observation": "NOT_EXTERNALLY_OBSERVED",
        "integrity_scope": "SELF_CONSISTENCY_ONLY",
        "limitations": [
            "NO_EXTERNAL_TIMESTAMP_OR_SIGNATURE",
            "OS_PROCESS_EXIT_NOT_OBSERVED_BY_AN_INDEPENDENT_PARENT",
            "NO_ACADEMIC_CORRECTNESS_OR_QUALITY_CLEARANCE",
        ],
    }
    artifacts["execution-record.json"] = _pretty_json_bytes(execution_record)

    artifact_records = {
        name: {"sha256": _sha256(raw), "size": len(raw)}
        for name, raw in sorted(artifacts.items())
    }
    request_sha = (
        str(request.get("request_sha256", "")) if isinstance(request, dict) else ""
    )
    manifest_body = {
        "schema": DIRECT_VALIDATION_EVIDENCE_SCHEMA,
        "run_id": run_id,
        "integrity_scope": "SELF_CONSISTENCY_ONLY",
        "external_anchor_status": "NOT_PROVIDED",
        "contains_source_content": True,
        "invocation_request_sha256": invocation_sha,
        "status": str(payload.get("status", "")),
        "delivery_gate_status": str(payload.get("delivery_gate_status", "")),
        "exit_code": int(payload.get("exit_code", 1)),
        "mode": str(payload.get("mode", "")),
        "scene": str(payload.get("scene", "")),
        "paired_quality_review_status": str(
            payload.get("paired_quality_review_status", "NOT_APPLICABLE")
        ),
        "paired_quality_review_request_sha256": request_sha,
        "source_bindings": source_records,
        "artifacts": artifact_records,
    }
    record_identity = {
        "schema": DIRECT_VALIDATION_EVIDENCE_SCHEMA,
        "run_id": run_id,
        "artifacts": artifact_records,
    }
    manifest_body["record_sha256"] = _sha256(
        _canonical_json_bytes(record_identity)
    )
    manifest = {
        **manifest_body,
        "manifest_sha256": _sha256(_canonical_json_bytes(manifest_body)),
    }
    manifest_raw = _pretty_json_bytes(manifest)

    expected_files = {**artifacts, "evidence-manifest.json": manifest_raw}
    if output_dir.exists() or output_dir.is_symlink():
        existing_lock = output_dir.with_name(f".{output_dir.name}.publish.lock")
        existing_lock_fd: int | None = None
        try:
            existing_lock_fd = os.open(
                existing_lock,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
            _assert_no_reparse_ancestors(output_dir)
            if not output_dir.is_dir():
                raise ValueError("evidence path exists and is not a directory")
            expected_dirs = {
                str(Path(name).parent).replace("\\", "/")
                for name in expected_files
                if Path(name).parent != Path(".")
            }

            def verify_existing_tree() -> None:
                actual_paths: set[str] = set()
                actual_dirs: set[str] = set()
                for path in output_dir.rglob("*"):
                    relative = path.relative_to(output_dir).as_posix()
                    _assert_no_reparse_ancestors(path)
                    if path.is_symlink():
                        raise ValueError(
                            f"evidence run_id conflict: symlink present: {relative}"
                        )
                    if path.is_dir():
                        actual_dirs.add(relative)
                    elif path.is_file():
                        actual_paths.add(relative)
                    else:
                        raise ValueError(
                            f"evidence run_id conflict: special path present: {relative}"
                        )
                if actual_paths != set(expected_files) or actual_dirs != expected_dirs:
                    raise ValueError(
                        "evidence run_id conflict: existing file or directory inventory differs"
                    )
                for name, expected_raw in expected_files.items():
                    path = output_dir / Path(name)
                    _assert_capturable_file(path, label=f"existing evidence file {name}")
                    if path.read_bytes() != expected_raw:
                        raise ValueError(
                            f"evidence run_id conflict: existing bytes differ: {name}"
                        )

            verify_existing_tree()
            verify_existing_tree()
            return {**manifest, "publication_status": "IDEMPOTENT_REPLAY"}
        finally:
            if existing_lock_fd is not None:
                os.close(existing_lock_fd)
                try:
                    existing_lock.unlink()
                except OSError:
                    pass

    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{output_dir.name}.staging-",
            dir=output_dir.parent,
        )
    )
    lock_path = output_dir.with_name(f".{output_dir.name}.publish.lock")
    lock_fd: int | None = None
    published = False
    try:
        _assert_no_reparse_ancestors(staging)
        (staging / "inputs").mkdir()
        for name, raw in artifacts.items():
            target = staging / Path(name)
            target.parent.mkdir(parents=True, exist_ok=True)
            _write_exclusive(target, raw)
        _write_exclusive(staging / "evidence-manifest.json", manifest_raw)
        for name, record in artifact_records.items():
            raw = (staging / name).read_bytes()
            if len(raw) != record["size"] or _sha256(raw) != record["sha256"]:
                raise ValueError(f"staged evidence drifted: {name}")
        if (staging / "evidence-manifest.json").read_bytes() != manifest_raw:
            raise ValueError("staged evidence manifest drifted")
        for label, path, expected_key in (
            ("before", before_resolved, "before_sha256"),
            ("after", after_resolved, "after_sha256"),
        ):
            current_path = _assert_capturable_file(path, label=f"{label} artifact")
            if _sha256(current_path.read_bytes()) != str(evidence.get(expected_key, "")):
                raise ValueError(f"{label} artifact changed before evidence publication")
        for label, path, expected_sha in dependency_rechecks:
            current_path = _assert_capturable_file(path, label=f"{label} artifact")
            if _sha256(current_path.read_bytes()) != expected_sha:
                raise ValueError(f"{label} artifact changed before evidence publication")
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        if output_dir.exists() or output_dir.is_symlink():
            raise ValueError("evidence directory appeared during publication")
        staging.rename(output_dir)
        published = True
    finally:
        if lock_fd is not None:
            os.close(lock_fd)
            try:
                lock_path.unlink(missing_ok=True)
            except OSError:
                pass
        if not published:
            shutil.rmtree(staging, ignore_errors=True)
    return {**manifest, "publication_status": "PUBLISHED"}


def _evidence_failure_payload(payload: dict[str, Any], error: Exception) -> dict[str, Any]:
    return {
        "schema": DIRECT_VALIDATION_EVIDENCE_ERROR_SCHEMA,
        "status": "FAIL",
        "delivery_gate_status": "FAIL",
        "exit_code": 1,
        "academic_correctness": "NOT_EVALUATED",
        "error_code": "EVIDENCE_PERSISTENCE_FAILED",
        "error": str(error),
        "validation_status_before_evidence_failure": str(payload.get("status", "")),
        "validation_exit_code_before_evidence_failure": int(payload.get("exit_code", 1)),
        "evidence_bundle": {"status": "FAIL"},
    }


def _input_failure_payload(error: Exception) -> dict[str, Any]:
    if isinstance(error, UnicodeError):
        code = "INPUT_ENCODING_INVALID"
    elif isinstance(error, FileNotFoundError):
        code = "INPUT_NOT_FOUND"
    elif isinstance(error, PermissionError):
        code = "INPUT_PERMISSION_DENIED"
    elif isinstance(error, json.JSONDecodeError):
        code = "INPUT_JSON_INVALID"
    elif isinstance(error, OSError):
        code = "INPUT_READ_FAILED"
    else:
        code = "INPUT_CONTRACT_INVALID"
    return {
        "schema": DIRECT_VALIDATION_INPUT_ERROR_SCHEMA,
        "status": "FAIL",
        "delivery_gate_status": "FAIL",
        "exit_code": 1,
        "academic_correctness": "NOT_EVALUATED",
        "error_code": code,
        "error": "Validation input could not be accepted; inspect the local invocation and files.",
    }


def _read_utf8(path: Path) -> tuple[bytes, str]:
    raw = path.read_bytes()
    return raw, raw.decode("utf-8-sig")


def _resolve_scope_locator(scope_path: Path, value: Any, *, field: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"report scope artifact is missing {field}")
    locator = Path(value)
    if locator.is_absolute():
        return locator
    if value.startswith("<"):
        raise ValueError(f"report scope {field} is not replayable")
    base = scope_path.parent.resolve(strict=False)
    candidate = (base / locator).resolve(strict=False)
    try:
        candidate.relative_to(base)
    except ValueError as error:
        raise ValueError(f"report scope {field} escapes its artifact root") from error
    return candidate


def _document_format(
    before: Path,
    after: Path,
    requested: str | None = None,
) -> str:
    if requested is not None and requested.casefold() != "auto":
        normalized = requested.casefold()
        if normalized not in {"markdown", "tex"}:
            raise ValueError("document_format must be 'markdown', 'tex', or 'auto'")
        return normalized
    if before.suffix.lower() in {".tex", ".ltx"} or after.suffix.lower() in {".tex", ".ltx"}:
        return "tex"
    return "markdown"


def _validate_reason(reason: str, label: str) -> str:
    reason = reason.strip()
    if len(reason.encode("utf-8")) > 1024:
        raise ValueError(f"{label} 不得超过 1024 个 UTF-8 字节")
    if any(ord(char) < 32 or ord(char) == 127 for char in reason):
        raise ValueError(f"{label} 不得包含换行、NUL 或其他控制字符")
    chinese_count = len(re.findall(r"[\u3400-\u9fff]", reason))
    normalized = re.sub(r"[\s，。！？；：、,.!?;:'\"（）()\[\]{}_-]+", "", reason)
    if (
        chinese_count < 6
        or VAGUE_REASON_RE.fullmatch(normalized)
        or not any(anchor in normalized for anchor in SPECIFIC_REASON_ANCHORS)
    ):
        raise ValueError(f"{label} 必须说明具体位置的表达功能或人工判断依据")
    return reason


def _template_field_payload_role(label: str) -> str:
    return {
        "适用题目": "EDITORIAL_PAYLOAD/APPLICABILITY_CLASSIFICATION",
        "逻辑链条": "EDITORIAL_PAYLOAD/TEACHING_REASONING",
        "给定首句": "READER_FACING_ARTIFACT_ROLE/PROMPT_STEM",
        "用词建议": "EDITORIAL_PAYLOAD/LEXICAL_GUIDANCE",
    }[label]


def _template_field_surface(text: str, document_format: str) -> str:
    """Mask opaque/code regions without changing offsets or line structure.

    Template-looking examples inside Markdown fences, inline code, TeX verbatim-like
    environments, or TeX comments are source material rather than live editorial
    fields.  The invariant checker already owns the canonical protected-span parser;
    reuse it here so this contract cannot drift to a weaker ad-hoc fence regex.
    """

    if document_format not in {"markdown", "tex"}:
        raise ValueError("document_format must be 'markdown' or 'tex'")
    _items, code_ranges = invariants._code_spans(text, exact=True)
    protected_ranges = list(code_ranges)
    if document_format == "tex":
        protected_ranges.extend(invariants._tex_comment_ranges(text))
    chars = list(text)
    for start, end in invariants._merge_ranges(protected_ranges):
        for index in range(start, end):
            if chars[index] not in {"\r", "\n"}:
                chars[index] = " "
    return "".join(chars)


def _template_field_records(
    text: str,
    *,
    artifact_role: str,
    artifact_raw: bytes,
    document_format: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    surface_lines = _template_field_surface(text, document_format).splitlines(
        keepends=True
    )
    char_offset = 0
    original_lines = text.splitlines(keepends=True)
    if len(surface_lines) != len(original_lines):
        raise ValueError("template field protected-span masking changed line structure")
    for line_number, (line_with_end, surface_line_with_end) in enumerate(
        zip(original_lines, surface_lines),
        1,
    ):
        line = line_with_end.rstrip("\r\n")
        surface_line = surface_line_with_end.rstrip("\r\n")
        surface_match = TEMPLATE_FIELD_LINE_RE.fullmatch(surface_line)
        if surface_match is not None:
            match = TEMPLATE_FIELD_LINE_RE.fullmatch(line)
            if match is None:
                raise ValueError("template field masking changed a live field header")
            payload = match.group("payload")
            payload_start = char_offset + match.start("payload")
            payload_end = char_offset + match.end("payload")
            records.append(
                {
                    "artifact_role": artifact_role,
                    "artifact_sha256": _sha256(artifact_raw),
                    "source_role": TEMPLATE_FIELD_SOURCE_ROLE,
                    "payload_role": _template_field_payload_role(match.group("label")),
                    "line": line_number,
                    "label": match.group("label"),
                    "separator": match.group("separator"),
                    "indent": match.group("indent"),
                    "payload": payload,
                    "payload_sha256": _sha256(payload.encode("utf-8")),
                    "line_sha256": _sha256(line.encode("utf-8")),
                    "char_start": payload_start,
                    "char_end": payload_end,
                }
            )
        char_offset += len(line_with_end)
    return records


def _load_template_field_edit_scope(
    scope_path: Path | None,
    *,
    before_raw: bytes,
    before_text: str,
    document_format: str,
) -> tuple[dict[str, Any], dict[int, dict[str, Any]]]:
    if scope_path is None:
        return (
            {
                "status": "N/A",
                "provided": False,
                "schema_version": None,
                "scope_sha256": None,
                "source_sha256": _sha256(before_raw),
                "permission_boundary": TEMPLATE_FIELD_PERMISSION,
                "authorized_edit_count": 0,
                "authorized_edits": [],
                "local_clearance_supported": False,
            },
            {},
        )

    resolved = _assert_capturable_file(
        scope_path,
        label="template field edit scope artifact",
    )
    raw = resolved.read_bytes()
    payload = _strict_json_bytes(raw, label="template field edit scope artifact")
    if not isinstance(payload, dict):
        raise ValueError("template field edit scope artifact must contain a JSON object")
    expected_top = {"schema_version", "source_sha256", "edits"}
    if set(payload) != expected_top:
        unknown = sorted(set(payload) - expected_top)
        missing = sorted(expected_top - set(payload))
        raise ValueError(
            "template field edit scope keys differ"
            + (f"; unknown={','.join(unknown)}" if unknown else "")
            + (f"; missing={','.join(missing)}" if missing else "")
        )
    if payload.get("schema_version") != TEMPLATE_FIELD_EDIT_SCOPE_SCHEMA:
        raise ValueError("template field edit scope schema_version is invalid")
    source_sha256 = payload.get("source_sha256")
    if not isinstance(source_sha256, str) or not re.fullmatch(
        r"[0-9a-f]{64}", source_sha256
    ):
        raise ValueError("template field edit scope source_sha256 is invalid")
    actual_source_sha256 = _sha256(before_raw)
    if source_sha256 != actual_source_sha256:
        raise ValueError("template field edit scope source_sha256 does not match before")
    edits = payload.get("edits")
    if not isinstance(edits, list) or not edits:
        raise ValueError("template field edit scope edits must be a non-empty array")

    source_fields = {
        int(item["line"]): item
        for item in _template_field_records(
            before_text,
            artifact_role="before",
            artifact_raw=before_raw,
            document_format=document_format,
        )
    }
    normalized_edits: list[dict[str, Any]] = []
    authorization_by_line: dict[int, dict[str, Any]] = {}
    expected_edit_keys = {"line", "label", "permission", "reason"}
    for ordinal, edit in enumerate(edits, 1):
        if not isinstance(edit, dict):
            raise ValueError(f"template field edit scope edits[{ordinal}] must be an object")
        if set(edit) != expected_edit_keys:
            unknown = sorted(set(edit) - expected_edit_keys)
            missing = sorted(expected_edit_keys - set(edit))
            raise ValueError(
                f"template field edit scope edits[{ordinal}] keys differ"
                + (f"; unknown={','.join(unknown)}" if unknown else "")
                + (f"; missing={','.join(missing)}" if missing else "")
            )
        line = edit.get("line")
        if isinstance(line, bool) or not isinstance(line, int) or line < 1:
            raise ValueError(f"template field edit scope edits[{ordinal}].line is invalid")
        if line in authorization_by_line:
            raise ValueError(f"template field edit scope duplicates source line {line}")
        label = edit.get("label")
        if label not in TEMPLATE_FIELD_LABELS:
            raise ValueError(f"template field edit scope edits[{ordinal}].label is unknown")
        if edit.get("permission") != TEMPLATE_FIELD_PERMISSION:
            raise ValueError(
                f"template field edit scope edits[{ordinal}].permission must be "
                f"{TEMPLATE_FIELD_PERMISSION}"
            )
        source_field = source_fields.get(line)
        if source_field is None or source_field["label"] != label:
            raise ValueError(
                f"template field edit scope line {line} does not identify {label} in before"
            )
        reason = _validate_reason(
            str(edit.get("reason", "")),
            f"template field edit scope line {line} 的授权理由",
        )
        normalized = {
            "line": line,
            "label": label,
            "permission": TEMPLATE_FIELD_PERMISSION,
            "reason": reason,
            "source_role": TEMPLATE_FIELD_SOURCE_ROLE,
            "payload_role": source_field["payload_role"],
            "before_payload_sha256": source_field["payload_sha256"],
        }
        authorization_by_line[line] = normalized
        normalized_edits.append(normalized)

    return (
        {
            "status": "PASS",
            "provided": True,
            "schema_version": TEMPLATE_FIELD_EDIT_SCOPE_SCHEMA,
            "scope_sha256": _sha256(raw),
            "source_sha256": actual_source_sha256,
            "permission_boundary": TEMPLATE_FIELD_PERMISSION,
            "authorized_edit_count": len(normalized_edits),
            "authorized_edits": sorted(normalized_edits, key=lambda item: item["line"]),
            "local_clearance_supported": False,
        },
        authorization_by_line,
    )


def _marker_counter(text: str, markers: Sequence[str]) -> Counter[str]:
    return Counter({marker: text.count(marker) for marker in markers if marker in text})


def _template_field_change_types(
    label: str,
    before_payload: str,
    after_payload: str,
) -> list[str]:
    change_types: list[str] = []
    before_strong = _marker_counter(before_payload, TEMPLATE_FIELD_STRONG_FORCE_MARKERS)
    after_strong = _marker_counter(after_payload, TEMPLATE_FIELD_STRONG_FORCE_MARKERS)
    before_weak = _marker_counter(before_payload, TEMPLATE_FIELD_WEAK_FORCE_MARKERS)
    after_weak = _marker_counter(after_payload, TEMPLATE_FIELD_WEAK_FORCE_MARKERS)
    removed_strong = before_strong - after_strong
    introduced_strong = after_strong - before_strong
    removed_weak = before_weak - after_weak
    introduced_weak = after_weak - before_weak
    if removed_strong and introduced_weak:
        change_types.append("ASSERTION_FORCE_WEAKENED")
    if removed_weak and introduced_strong:
        change_types.append("ASSERTION_FORCE_STRENGTHENED")

    if _marker_counter(before_payload, TEMPLATE_FIELD_NEGATION_MARKERS) != _marker_counter(
        after_payload, TEMPLATE_FIELD_NEGATION_MARKERS
    ):
        change_types.append("NEGATION_SCOPE_CHANGED")
    if _marker_counter(
        before_payload, TEMPLATE_FIELD_CAUSAL_CONDITION_MARKERS
    ) != _marker_counter(after_payload, TEMPLATE_FIELD_CAUSAL_CONDITION_MARKERS):
        change_types.append("CAUSAL_OR_CONDITION_RELATION_CHANGED")

    if label == "适用题目":
        before_head = before_payload.split("（", 1)[0]
        after_head = after_payload.split("（", 1)[0]
        if _marker_counter(
            before_head, TEMPLATE_FIELD_APPLICABILITY_OBJECTS
        ) != _marker_counter(after_head, TEMPLATE_FIELD_APPLICABILITY_OBJECTS):
            change_types.append("APPLICABILITY_OBJECT_CHANGED")
        if _marker_counter(
            before_head, TEMPLATE_FIELD_APPLICABILITY_PREDICATES
        ) != _marker_counter(after_head, TEMPLATE_FIELD_APPLICABILITY_PREDICATES):
            change_types.append("APPLICABILITY_PREDICATE_CHANGED")
        introduced_directives = _marker_counter(
            after_head, TEMPLATE_FIELD_DIRECTIVE_MARKERS
        ) - _marker_counter(before_head, TEMPLATE_FIELD_DIRECTIVE_MARKERS)
        if introduced_directives:
            change_types.append("CLASSIFICATION_TO_READER_INSTRUCTION_DRIFT")
        if _marker_counter(before_head, TEMPLATE_FIELD_RANGE_MARKERS) != _marker_counter(
            after_head, TEMPLATE_FIELD_RANGE_MARKERS
        ):
            change_types.append("APPLICABILITY_RANGE_CHANGED")
    return sorted(set(change_types))


def _template_field_change_audit(
    before_text: str,
    after_text: str,
    *,
    before_raw: bytes,
    after_raw: bytes,
    authorization_by_line: dict[int, dict[str, Any]],
    scope_provided: bool,
    document_format: str,
) -> tuple[list[invariants.Diagnostic], list[invariants.Diagnostic], list[dict[str, Any]]]:
    before_lines = before_text.splitlines(keepends=True)
    after_lines = after_text.splitlines(keepends=True)
    before_fields = _template_field_records(
        before_text,
        artifact_role="before",
        artifact_raw=before_raw,
        document_format=document_format,
    )
    after_fields = _template_field_records(
        after_text,
        artifact_role="after",
        artifact_raw=after_raw,
        document_format=document_format,
    )
    before_by_line = {int(item["line"]): item for item in before_fields}
    after_by_line = {int(item["line"]): item for item in after_fields}
    errors: list[invariants.Diagnostic] = []
    warnings: list[invariants.Diagnostic] = []
    findings: list[dict[str, Any]] = []
    used_authorizations: set[int] = set()
    changed_records = _changed_line_records(before_text, after_text)
    matcher = difflib.SequenceMatcher(a=before_lines, b=after_lines, autojunk=False)
    changed_opcodes = [item for item in matcher.get_opcodes() if item[0] != "equal"]
    for hunk_ordinal, (_tag, before_start, before_end, after_start, after_end) in enumerate(
        changed_opcodes,
        1,
    ):
        before_hunk_fields = [
            before_by_line[line]
            for line in range(before_start + 1, before_end + 1)
            if line in before_by_line
        ]
        after_hunk_fields = [
            after_by_line[line]
            for line in range(after_start + 1, after_end + 1)
            if line in after_by_line
        ]
        used_authorizations.update(
            int(item["line"])
            for item in before_hunk_fields
            if int(item["line"]) in authorization_by_line
        )
        if not before_hunk_fields and not after_hunk_fields:
            continue
        change_id = str(changed_records[hunk_ordinal - 1]["change_id"])
        before_headers = [
            (str(item["label"]), str(item["separator"])) for item in before_hunk_fields
        ]
        after_headers = [
            (str(item["label"]), str(item["separator"])) for item in after_hunk_fields
        ]
        if before_headers != after_headers:
            details = {
                "change_id": change_id,
                "source_role": TEMPLATE_FIELD_SOURCE_ROLE,
                "before_headers": [
                    {
                        "line": item["line"],
                        "label": item["label"],
                        "separator": item["separator"],
                        "line_sha256": item["line_sha256"],
                    }
                    for item in before_hunk_fields
                ],
                "after_headers": [
                    {
                        "line": item["line"],
                        "label": item["label"],
                        "separator": item["separator"],
                        "line_sha256": item["line_sha256"],
                    }
                    for item in after_hunk_fields
                ],
                "permission_boundary": TEMPLATE_FIELD_PERMISSION,
                "scope_provided": scope_provided,
            }
            errors.append(
                invariants.Diagnostic(
                    code="TEMPLATE_FIELD_HEADER_CHANGED",
                    severity="error",
                    message=(
                        "A protected template-field label or colon changed, moved, was added, "
                        "or was removed"
                    ),
                    details=details,
                )
            )
            findings.append(
                {
                    "code": "TEMPLATE_FIELD_HEADER_CHANGED",
                    "severity": "error",
                    "change_id": change_id,
                    "source_role": TEMPLATE_FIELD_SOURCE_ROLE,
                    "authorization_status": "HEADER_CHANGE_NOT_AUTHORIZABLE",
                    "change_types": ["FIELD_HEADER_OR_POSITION_CHANGED"],
                    **details,
                }
            )
            continue

        for before_field, after_field in zip(before_hunk_fields, after_hunk_fields):
            if before_field["payload"] == after_field["payload"]:
                continue
            line = int(before_field["line"])
            authorization = authorization_by_line.get(line)
            authorization_status = (
                "AUTHORIZED_PAYLOAD_ONLY" if authorization is not None else "NOT_AUTHORIZED"
            )
            change_types = _template_field_change_types(
                str(before_field["label"]),
                str(before_field["payload"]),
                str(after_field["payload"]),
            )
            finding = {
                "code": (
                    "TEMPLATE_FIELD_PAYLOAD_EDIT_UNAUTHORIZED"
                    if authorization is None
                    else "TEMPLATE_FIELD_ROLE_OR_FORCE_DRIFT"
                    if change_types
                    else "TEMPLATE_FIELD_PAYLOAD_EDIT_AUTHORIZED"
                ),
                "severity": "warning" if authorization is None or change_types else "info",
                "change_id": change_id,
                "field_label": before_field["label"],
                "source_role": TEMPLATE_FIELD_SOURCE_ROLE,
                "payload_role": before_field["payload_role"],
                "source_line": line,
                "after_line": int(after_field["line"]),
                "authorization_status": authorization_status,
                "permission": (
                    TEMPLATE_FIELD_PERMISSION if authorization is not None else None
                ),
                "authorization_reason": (
                    authorization["reason"] if authorization is not None else None
                ),
                "change_types": change_types,
                "before_span": {
                    "line": line,
                    "payload_sha256": before_field["payload_sha256"],
                    "line_sha256": before_field["line_sha256"],
                },
                "after_span": {
                    "line": int(after_field["line"]),
                    "payload_sha256": after_field["payload_sha256"],
                    "line_sha256": after_field["line_sha256"],
                },
                "local_clearance_supported": False,
            }
            findings.append(finding)
            if authorization is None:
                warnings.append(
                    invariants.Diagnostic(
                        code="TEMPLATE_FIELD_PAYLOAD_EDIT_UNAUTHORIZED",
                        severity="warning",
                        message=(
                            "A template-field payload changed without a source-bound "
                            "PAYLOAD_ONLY edit scope"
                        ),
                        details=finding,
                    )
                )
            elif change_types:
                warnings.append(
                    invariants.Diagnostic(
                        code="TEMPLATE_FIELD_ROLE_OR_FORCE_DRIFT",
                        severity="warning",
                        message=(
                            "An authorized template-field payload edit changes field duty, "
                            "applicability, logical relation, or assertion force"
                        ),
                        details=finding,
                    )
                )

    unused_authorizations = sorted(set(authorization_by_line) - used_authorizations)
    if unused_authorizations:
        raise ValueError(
            "template field edit scope authorizes unchanged or unmapped source lines: "
            + ",".join(str(item) for item in unused_authorizations)
        )
    return errors, warnings, findings


def _parse_keep_key(key: str, valid_ids: set[str]) -> tuple[str, str | None]:
    signal_id, separator, binding = key.partition("@")
    if signal_id not in valid_ids:
        raise ValueError(f"未知 signal id: {signal_id}")
    if not separator:
        return signal_id, None
    if re.fullmatch(r"\d+:\d+", binding):
        return signal_id, binding
    if re.fullmatch(r"sha256:[0-9a-fA-F]{12,64}", binding):
        return signal_id, binding.lower()
    raise ValueError(f"{key} 的定位必须是 LINE:COLUMN 或 sha256:HASH")


def _parse_keep_reasons(values: Sequence[str], valid_ids: set[str]) -> dict[str, str]:
    reasons: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("--keep-reason 必须使用 SIGNAL_ID=具体理由")
        key, reason = (part.strip() for part in value.split("=", 1))
        _parse_keep_key(key, valid_ids)
        reasons[key] = _validate_reason(reason, f"{key} 的 KEEP 理由")
    return reasons


def _parse_reason_pairs(values: Sequence[str], option: str) -> dict[str, str]:
    reasons: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"{option} 必须使用 CODE=具体理由")
        code, reason = (part.strip() for part in value.split("=", 1))
        if not code:
            raise ValueError(f"{option} 缺少 CODE")
        if code in reasons:
            raise ValueError(f"{option} 重复提交 CODE: {code}")
        reasons[code] = _validate_reason(reason, f"{code} 的具体理由")
    return reasons


def _policy_hashes() -> dict[str, str]:
    paths = {
        "validator_sha256": Path(__file__).resolve(),
        "invariant_checker_sha256": Path(invariants.__file__).resolve(),
        "scanner_sha256": Path(lexical.__file__).resolve(),
        "lexicon_sha256": Path(lexical.DEFAULT_LEXICON).resolve(),
        "report_extractor_sha256": Path(detector_scope.__file__).resolve(),
    }
    skill_root = Path(__file__).resolve().parent.parent
    paths.update(
        {
            "paired_quality_verifier_sha256": skill_root
            / "scripts"
            / _PAIRED_QUALITY_VERIFIER_NAME,
            "paired_quality_contract_sha256": skill_root
            / "references"
            / _PAIRED_QUALITY_CONTRACT_NAME,
        }
    )
    result = {name: _sha256(path.read_bytes()) for name, path in paths.items()}
    policy_reference_paths = {
        "skill_md": skill_root / "SKILL.md",
        "operational_contract": skill_root / "references" / "operational-contract.md",
        "workflow": skill_root / "references" / "workflow.md",
        "scene_routing_policy": skill_root / "references" / "scene-routing-policy.json",
        "source_provenance_trust": skill_root / "references" / "source-provenance-trust.json",
        "paired_quality_clearance_contract": skill_root
        / "references"
        / _PAIRED_QUALITY_CONTRACT_NAME,
    }
    runtime_contract = {
        "implementation": sys.implementation.name,
        "cache_tag": sys.implementation.cache_tag,
        "python_version": list(sys.version_info[:3]),
        "unicode_version": unicodedata.unidata_version,
        "os_name": os.name,
        "policy_reference_hashes": {
            name: _sha256(path.read_bytes())
            for name, path in sorted(policy_reference_paths.items())
        },
    }
    result["runtime_contract_sha256"] = _sha256(
        _canonical_json_bytes(runtime_contract)
    )
    return result


def _canonical_warning(warning: Any) -> dict[str, Any]:
    return {
        "code": warning.code,
        "severity": warning.severity,
        "message": warning.message,
        "details": warning.details,
    }


def _warning_fingerprint(warning: Any) -> str:
    return _sha256(_canonical_json_bytes(_canonical_warning(warning)))


def _public_warning(warning: Any) -> dict[str, Any]:
    public = _canonical_warning(warning)
    public["warning_fingerprint"] = _warning_fingerprint(warning)
    return public


def _build_warning_review_request(
    warnings: Sequence[Any],
    *,
    before_sha256: str,
    after_sha256: str,
    mode: str,
    scene: str,
    document_format: str,
    protected_terms: dict[str, Any],
    strict_speech_acts: bool,
    fragment_mode: bool,
    policy_hashes: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    if not warnings:
        return None
    request_body = {
        "schema": WARNING_REVIEW_REQUEST_SCHEMA,
        "artifact": {
            "before_sha256": before_sha256,
            "after_sha256": after_sha256,
        },
        "validation_context": {
            "mode": mode.upper(),
            "scene": scene.upper(),
            "document_format": document_format,
            "document_scope": "FRAGMENT" if fragment_mode else "DOCUMENT",
            "strict_speech_acts": strict_speech_acts,
            "protected_terms": protected_terms,
        },
        "policy_hashes": policy_hashes or _policy_hashes(),
        "warnings": [_public_warning(item) for item in warnings],
    }
    return {
        **request_body,
        "request_sha256": _sha256(_canonical_json_bytes(request_body)),
    }


def _changed_line_records(before_text: str, after_text: str) -> list[dict[str, Any]]:
    # Preserve line terminators so an EOL-only rewrite is still represented by
    # an auditable change hunk. Full artifact hashes already bind the bytes;
    # hunk hashes must not silently normalize a CRLF/LF difference away.
    before_lines = before_text.splitlines(keepends=True)
    after_lines = after_text.splitlines(keepends=True)
    records: list[dict[str, Any]] = []
    matcher = difflib.SequenceMatcher(a=before_lines, b=after_lines, autojunk=False)
    for ordinal, (tag, before_start, before_end, after_start, after_end) in enumerate(
        (item for item in matcher.get_opcodes() if item[0] != "equal"),
        1,
    ):
        before_block = "".join(before_lines[before_start:before_end])
        after_block = "".join(after_lines[after_start:after_end])
        record = {
            "ordinal": ordinal,
            "operation": tag.upper(),
            "before": {
                "start_line": before_start + 1 if before_end > before_start else None,
                "end_line": before_end if before_end > before_start else None,
                "line_count": before_end - before_start,
                "han_chars": len(re.findall(r"[\u3400-\u9fff]", before_block)),
                "sha256": _sha256(before_block.encode("utf-8")),
            },
            "after": {
                "start_line": after_start + 1 if after_end > after_start else None,
                "end_line": after_end if after_end > after_start else None,
                "line_count": after_end - after_start,
                "han_chars": len(re.findall(r"[\u3400-\u9fff]", after_block)),
                "sha256": _sha256(after_block.encode("utf-8")),
            },
        }
        record["change_id"] = "QCH-" + _sha256(
            _canonical_json_bytes(record)
        )[:20]
        records.append(record)
    return records


def _exact_text_span(
    text: str,
    start: int,
    end: int,
    *,
    artifact_role: str,
    artifact_raw: bytes,
) -> dict[str, Any]:
    line_start = text.rfind("\n", 0, start) + 1
    end_line_start = text.rfind("\n", 0, end) + 1
    value = text[start:end]
    bom_bytes = 3 if artifact_raw.startswith(b"\xef\xbb\xbf") else 0
    return {
        "artifact_role": artifact_role,
        "artifact_sha256": _sha256(artifact_raw),
        "text": value,
        "line": text.count("\n", 0, start) + 1,
        "column": start - line_start + 1,
        "end_line": text.count("\n", 0, end) + 1,
        "end_column_exclusive": end - end_line_start + 1,
        "char_start": start,
        "char_end": end,
        "utf8_start": bom_bytes + len(text[:start].encode("utf-8")),
        "utf8_end": bom_bytes + len(text[:end].encode("utf-8")),
        "sha256": _sha256(value.encode("utf-8")),
    }


def _literal_occurrences(
    text: str,
    forms: Sequence[str],
    *,
    overlap_start: int,
    overlap_end: int,
) -> list[tuple[int, int, str]]:
    candidates: list[tuple[int, int, str]] = []
    for form in sorted(set(forms), key=lambda item: (-len(item), item)):
        if not form:
            continue
        cursor = 0
        while True:
            start = text.find(form, cursor)
            if start < 0:
                break
            end = start + len(form)
            if start < overlap_end and end > overlap_start:
                candidates.append((start, end, form))
            cursor = start + 1
    kept: list[tuple[int, int, str]] = []
    for candidate in sorted(candidates, key=lambda item: (item[0], -(item[1] - item[0]), item[2])):
        start, end, _form = candidate
        if any(start < old_end and end > old_start for old_start, old_end, _ in kept):
            continue
        kept.append(candidate)
    return sorted(kept)


def _character_change_regions(
    before_block: str,
    after_block: str,
) -> list[dict[str, Any]]:
    matcher = difflib.SequenceMatcher(
        a=before_block,
        b=after_block,
        autojunk=False,
    )
    regions: list[dict[str, Any]] = []
    for tag, before_start, before_end, after_start, after_end in matcher.get_opcodes():
        if tag == "equal":
            continue
        if (
            regions
            and before_start - int(regions[-1]["before_end"])
            <= COURSE_VOICE_FLATTENING_MAX_EQUAL_BRIDGE
            and after_start - int(regions[-1]["after_end"])
            <= COURSE_VOICE_FLATTENING_MAX_EQUAL_BRIDGE
        ):
            region = regions[-1]
            region["before_end"] = before_end
            region["after_end"] = after_end
            region["operations"].append(tag.upper())
            continue
        regions.append(
            {
                "before_start": before_start,
                "before_end": before_end,
                "after_start": after_start,
                "after_end": after_end,
                "operations": [tag.upper()],
            }
        )
    return [
        {
            **region,
            "character_change_id": "QCC-"
            + _sha256(_canonical_json_bytes(region))[:20],
        }
        for region in regions
        if int(region["before_end"]) > int(region["before_start"])
        and int(region["after_end"]) > int(region["after_start"])
    ]


_TEX_HEADING_RE = re.compile(
    r"(?m)^[ \t]*\\(?P<level>part|chapter|section|subsection|subsubsection|paragraph)"
    r"\*?\s*(?:\[[^\]\n]*\]\s*)?\{(?P<title>[^{}\n]*)\}[^\n]*"
)
_MARKDOWN_HEADING_RE = re.compile(
    r"(?m)^[ \t]{0,3}(?P<marks>#{1,6})[ \t]+(?P<title>[^\n]+?)\s*$"
)


def _heading_records(text: str, document_format: str) -> list[dict[str, Any]]:
    if document_format == "tex":
        view = lexical._tex_structure_view(text)
        matches = list(_TEX_HEADING_RE.finditer(view))
        return [
            {
                "ordinal": ordinal,
                "start": match.start(),
                "end": match.end(),
                "level": match.group("level"),
                "heading_sha256": _sha256(
                    text[match.start() : match.end()].encode("utf-8")
                ),
            }
            for ordinal, match in enumerate(matches, 1)
        ]
    matches = list(_MARKDOWN_HEADING_RE.finditer(text))
    return [
        {
            "ordinal": ordinal,
            "start": match.start(),
            "end": match.end(),
            "level": len(match.group("marks")),
            "heading_sha256": _sha256(
                text[match.start() : match.end()].encode("utf-8")
            ),
        }
        for ordinal, match in enumerate(matches, 1)
    ]


def _section_at(records: Sequence[dict[str, Any]], offset: int) -> dict[str, Any]:
    current = {
        "ordinal": 0,
        "level": "DOCUMENT_ROOT",
        "heading_sha256": None,
    }
    for record in records:
        if int(record["start"]) > offset:
            break
        current = {
            "ordinal": int(record["ordinal"]),
            "level": record["level"],
            "heading_sha256": record["heading_sha256"],
        }
    return current


def _overlaps_any_range(
    start: int,
    end: int,
    ranges: Sequence[tuple[int, int]],
) -> bool:
    return any(start < other_end and end > other_start for other_start, other_end in ranges)


def _transition_cluster_candidates(
    transitions: Sequence[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    by_section: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for transition in transitions:
        before_section = transition["section_binding"]["before"]
        after_section = transition["section_binding"]["after"]
        if (
            before_section["ordinal"] != after_section["ordinal"]
            or before_section["level"] != after_section["level"]
            or before_section["heading_sha256"] != after_section["heading_sha256"]
        ):
            continue
        key = (
            before_section["ordinal"],
            before_section["level"],
            before_section["heading_sha256"],
        )
        by_section.setdefault(key, []).append(transition)

    candidates: list[list[dict[str, Any]]] = []
    for section_transitions in by_section.values():
        ordered = sorted(
            section_transitions,
            key=lambda item: (
                item["removed"]["char_start"],
                item["introduced"]["char_start"],
                item["occurrence_id"],
            ),
        )
        for start_index in range(len(ordered)):
            for end_index in range(start_index, len(ordered)):
                window = ordered[start_index : end_index + 1]
                before_envelope = _transition_envelope(window, "removed")
                after_envelope = _transition_envelope(window, "introduced")
                if (
                    before_envelope["char_width"]
                    > COURSE_VOICE_FLATTENING_MAX_CLUSTER_CHARS
                    or after_envelope["char_width"]
                    > COURSE_VOICE_FLATTENING_MAX_CLUSTER_CHARS
                    or before_envelope["line_count"]
                    > COURSE_VOICE_FLATTENING_MAX_CLUSTER_LINES
                    or after_envelope["line_count"]
                    > COURSE_VOICE_FLATTENING_MAX_CLUSTER_LINES
                ):
                    continue
                transition_ids = {item["transition_id"] for item in window}
                families = {item["family"] for item in window}
                hunks = {item["change_id"] for item in window}
                if (
                    len(transition_ids) >= COURSE_VOICE_FLATTENING_MIN_TRANSITIONS
                    and len(families) >= COURSE_VOICE_FLATTENING_MIN_FAMILIES
                    and len(hunks) >= COURSE_VOICE_FLATTENING_MIN_HUNKS
                ):
                    candidates.append(window)

    unique: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for candidate in candidates:
        key = tuple(sorted(item["occurrence_id"] for item in candidate))
        unique[key] = candidate
    maximal = [
        candidate
        for key, candidate in unique.items()
        if not any(set(key) < set(other_key) for other_key in unique)
    ]
    selected: list[list[dict[str, Any]]] = []
    occupied: set[str] = set()
    for candidate in sorted(
        maximal,
        key=lambda items: (
            -len(items),
            items[0]["removed"]["char_start"],
            tuple(item["occurrence_id"] for item in items),
        ),
    ):
        occurrence_ids = {item["occurrence_id"] for item in candidate}
        if occurrence_ids & occupied:
            continue
        selected.append(candidate)
        occupied.update(occurrence_ids)
    return sorted(
        selected,
        key=lambda items: items[0]["removed"]["char_start"],
    )


def _transition_envelope(
    transitions: Sequence[dict[str, Any]],
    span_role: str,
) -> dict[str, int]:
    spans = [item[span_role] for item in transitions]
    char_start = min(int(item["char_start"]) for item in spans)
    char_end = max(int(item["char_end"]) for item in spans)
    line_start = min(int(item["line"]) for item in spans)
    line_end = max(int(item["end_line"]) for item in spans)
    return {
        "char_start": char_start,
        "char_end": char_end,
        "char_width": char_end - char_start,
        "line_start": line_start,
        "line_end": line_end,
        "line_count": line_end - line_start + 1,
    }


def _course_voice_flattening_findings(
    before_text: str,
    after_text: str,
    *,
    before_raw: bytes,
    after_raw: bytes,
    mode: str,
    scene: str,
    document_format: str,
    editable_style_wrappers: Sequence[str],
    before_style_findings: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Find character-bound clusters of COURSE register flattening."""

    if mode != "REWRITE" or scene.upper() != "COURSE" or before_text == after_text:
        return []

    before_lines = before_text.splitlines(keepends=True)
    after_lines = after_text.splitlines(keepends=True)
    before_offsets = [0]
    after_offsets = [0]
    for line in before_lines:
        before_offsets.append(before_offsets[-1] + len(line))
    for line in after_lines:
        after_offsets.append(after_offsets[-1] + len(line))

    editable_wrappers = frozenset(editable_style_wrappers)
    before_extra_spans: list[tuple[int, int, str]] = []
    after_extra_spans: list[tuple[int, int, str]] = []
    if document_format == "tex":
        before_extra_spans.extend(
            lexical._tex_command_call_spans(before_text, editable_wrappers)
        )
        after_extra_spans.extend(
            lexical._tex_command_call_spans(after_text, editable_wrappers)
        )
    else:
        before_extra_spans.extend(lexical._markdown_structure_spans(before_text))
        after_extra_spans.extend(lexical._markdown_structure_spans(after_text))
    before_protected = lexical.ProtectedIndex(
        before_text,
        document_format=document_format,
        extra_spans=before_extra_spans,
    )
    after_protected = lexical.ProtectedIndex(
        after_text,
        document_format=document_format,
        extra_spans=after_extra_spans,
    )
    before_headings = _heading_records(before_text, document_format)
    after_headings = _heading_records(after_text, document_format)
    excluded_source_ranges = [
        (int(item["start_char"]), int(item["end_char"]))
        for item in before_style_findings
        if item.get("candidate")
        and item.get("severity") == "high"
        and item.get("action") in {"DELETE", "REWRITE"}
    ]

    transitions: list[dict[str, Any]] = []
    matcher = difflib.SequenceMatcher(a=before_lines, b=after_lines, autojunk=False)
    changed_opcodes = [item for item in matcher.get_opcodes() if item[0] != "equal"]
    changed_records = _changed_line_records(before_text, after_text)
    for hunk_ordinal, (tag, before_start, before_end, after_start, after_end) in enumerate(
        changed_opcodes,
        1,
    ):
        before_block = "".join(before_lines[before_start:before_end])
        after_block = "".join(after_lines[after_start:after_end])
        if not before_block or not after_block:
            continue
        change_id = str(changed_records[hunk_ordinal - 1]["change_id"])
        for region in _character_change_regions(before_block, after_block):
            for rule in COURSE_VOICE_FLATTENING_TRANSITIONS:
                removed_occurrences = _literal_occurrences(
                    before_block,
                    tuple(rule["removed_forms"]),
                    overlap_start=int(region["before_start"]),
                    overlap_end=int(region["before_end"]),
                )
                introduced_occurrences = _literal_occurrences(
                    after_block,
                    tuple(rule["introduced_forms"]),
                    overlap_start=int(region["after_start"]),
                    overlap_end=int(region["after_end"]),
                )
                removed_candidates: list[tuple[int, int, str]] = []
                for removed_local, removed_end, removed_text in removed_occurrences:
                    if _literal_occurrences(
                        after_block,
                        (removed_text,),
                        overlap_start=int(region["after_start"]),
                        overlap_end=int(region["after_end"]),
                    ):
                        continue
                    absolute_start = before_offsets[before_start] + removed_local
                    absolute_end = before_offsets[before_start] + removed_end
                    if before_protected.overlap_reason_for_span(
                        absolute_start,
                        absolute_end,
                    ):
                        continue
                    if _overlaps_any_range(
                        absolute_start,
                        absolute_end,
                        excluded_source_ranges,
                    ):
                        continue
                    removed_candidates.append(
                        (removed_local, removed_end, removed_text)
                    )
                introduced_candidates: list[tuple[int, int, str]] = []
                for introduced_local, introduced_end, introduced_text in introduced_occurrences:
                    if _literal_occurrences(
                        before_block,
                        (introduced_text,),
                        overlap_start=int(region["before_start"]),
                        overlap_end=int(region["before_end"]),
                    ):
                        continue
                    absolute_start = after_offsets[after_start] + introduced_local
                    absolute_end = after_offsets[after_start] + introduced_end
                    if after_protected.overlap_reason_for_span(
                        absolute_start,
                        absolute_end,
                    ):
                        continue
                    introduced_candidates.append(
                        (introduced_local, introduced_end, introduced_text)
                    )
                if len(removed_candidates) != len(introduced_candidates):
                    continue
                for removed, introduced in zip(
                    removed_candidates,
                    introduced_candidates,
                ):
                    removed_local, removed_end, removed_text = removed
                    introduced_local, introduced_end, introduced_text = introduced
                    removed_start = before_offsets[before_start] + removed_local
                    removed_absolute_end = before_offsets[before_start] + removed_end
                    introduced_start = after_offsets[after_start] + introduced_local
                    introduced_absolute_end = after_offsets[after_start] + introduced_end
                    occurrence_body = {
                        "transition_id": rule["id"],
                        "change_id": change_id,
                        "character_change_id": region["character_change_id"],
                        "removed_start": removed_start,
                        "removed_end": removed_absolute_end,
                        "introduced_start": introduced_start,
                        "introduced_end": introduced_absolute_end,
                    }
                    transitions.append(
                        {
                            "occurrence_id": "CVF-"
                            + _sha256(_canonical_json_bytes(occurrence_body))[:20],
                            "transition_id": rule["id"],
                            "family": rule["family"],
                            "hunk_ordinal": hunk_ordinal,
                            "change_id": change_id,
                            "hunk_operation": tag.upper(),
                            "character_change_id": region["character_change_id"],
                            "character_change_operations": region["operations"],
                            "binding_scope": "SAME_CHARACTER_CHANGE_REGION",
                            "section_binding": {
                                "before": _section_at(before_headings, removed_start),
                                "after": _section_at(after_headings, introduced_start),
                            },
                            "removed": _exact_text_span(
                                before_text,
                                removed_start,
                                removed_absolute_end,
                                artifact_role="before",
                                artifact_raw=before_raw,
                            ),
                            "introduced": _exact_text_span(
                                after_text,
                                introduced_start,
                                introduced_absolute_end,
                                artifact_role="after",
                                artifact_raw=after_raw,
                            ),
                        }
                    )

    findings: list[dict[str, Any]] = []
    for cluster_ordinal, cluster in enumerate(
        _transition_cluster_candidates(transitions),
        1,
    ):
        transition_ids = sorted({item["transition_id"] for item in cluster})
        families = sorted({item["family"] for item in cluster})
        hunk_ids = sorted({item["change_id"] for item in cluster})
        hunk_ordinals = sorted({item["hunk_ordinal"] for item in cluster})
        before_envelope = _transition_envelope(cluster, "removed")
        after_envelope = _transition_envelope(cluster, "introduced")
        findings.append(
            {
            "code": "STYLE_COURSE_VOICE_FLATTENING_CLUSTER",
            "cluster_id": "CVFC-"
            + _sha256(
                _canonical_json_bytes(
                    sorted(item["occurrence_id"] for item in cluster)
                )
            )[:20],
            "cluster_ordinal": cluster_ordinal,
            "severity": "warning",
            "status": "REVIEW",
            "scene": "COURSE",
            "message": (
                "Multiple functional teaching expressions were removed while "
                "abstract formal replacements were introduced across changed hunks"
            ),
            "detector_scope": "PAIRED_COURSE_VOICE_NON_REGRESSION_CANDIDATE",
            "policy_provenance": COURSE_VOICE_FLATTENING_POLICY_REVISION,
            "threshold": {
                "minimum_distinct_transitions": COURSE_VOICE_FLATTENING_MIN_TRANSITIONS,
                "minimum_distinct_families": COURSE_VOICE_FLATTENING_MIN_FAMILIES,
                "minimum_changed_hunks": COURSE_VOICE_FLATTENING_MIN_HUNKS,
                "maximum_cluster_chars_per_artifact": COURSE_VOICE_FLATTENING_MAX_CLUSTER_CHARS,
                "maximum_cluster_lines_per_artifact": COURSE_VOICE_FLATTENING_MAX_CLUSTER_LINES,
                "same_heading_required": True,
            },
            "observed": {
                "distinct_transition_count": len(transition_ids),
                "distinct_transition_ids": transition_ids,
                "distinct_family_count": len(families),
                "families": families,
                "changed_hunk_count": len(hunk_ids),
                "changed_hunks": hunk_ordinals,
                "change_ids": hunk_ids,
                "bound_transition_occurrences": len(cluster),
                "envelope_measurement": "FULL_SPAN_CHARS_AND_INCLUSIVE_LINES",
                "before_char_envelope": before_envelope["char_width"],
                "after_char_envelope": after_envelope["char_width"],
                "before_line_envelope": before_envelope["line_count"],
                "after_line_envelope": after_envelope["line_count"],
            },
            "transitions": cluster,
            "limitations": {
                "authorship": "NOT_EVALUATED",
                "academic_correctness": "NOT_EVALUATED",
                "quality_clearance_granted": False,
                "authorship_inference": False,
                "single_word_is_prohibited": False,
                "quality_judgment_complete": False,
                "unencoded_voice_flattening_can_pass": True,
            },
        }
        )
    return findings


def _build_paired_quality_review_request(
    before_text: str,
    after_text: str,
    *,
    before_sha256: str,
    after_sha256: str,
    mode: str,
    scene: str,
    document_format: str,
    fragment_mode: bool,
    mechanical_validation_status: str,
    policy_hashes: dict[str, str] | None = None,
    report_scope_binding: dict[str, Any] | None = None,
    template_field_changes: Sequence[dict[str, Any]] = (),
) -> dict[str, Any] | None:
    if mode != "REWRITE":
        return None
    unchanged = before_sha256 == after_sha256
    if unchanged and mechanical_validation_status != "PASS":
        decision = "BLOCKED_NO_CHANGE"
    else:
        decision = "NO_CHANGE" if unchanged else "REWRITE"
    document_scope = (
        "REPORT_SELECTION"
        if report_scope_binding is not None
        else "FRAGMENT" if fragment_mode else "DOCUMENT"
    )
    validation_context: dict[str, Any] = {
        "mode": mode,
        "decision": decision,
        "artifact_relation": "UNCHANGED" if unchanged else "CHANGED",
        "decision_eligible": mechanical_validation_status == "PASS",
        "scene": scene.upper(),
        "document_format": document_format,
        "document_scope": document_scope,
        "mechanical_validation_status": mechanical_validation_status,
    }
    if report_scope_binding is not None:
        validation_context["report_scope_binding"] = report_scope_binding
    request_body = {
        "schema": PAIRED_QUALITY_REVIEW_REQUEST_SCHEMA,
        "status": (
            "PENDING_EXTERNAL_REVIEW"
            if mechanical_validation_status == "PASS"
            else "BLOCKED_BY_MECHANICAL_GATE"
        ),
        "artifact": {
            "before_sha256": before_sha256,
            "after_sha256": after_sha256,
        },
        "validation_context": validation_context,
        "policy_hashes": policy_hashes or _policy_hashes(),
        "changes": _changed_line_records(before_text, after_text),
        "template_field_changes": list(template_field_changes),
        "review_contract": {
            "required_per_change_verdicts": ["ACCEPT", "REVISE", "REVERT"],
            "required_dimensions": [
                "actionable_pathology_remaining",
                "no_change_is_best_available_decision",
                "problem_span_binding",
                "independent_reading_benefit",
                "subject_and_modifier_alignment",
                "verb_object_collocation",
                "logical_relation_preservation",
                "template_field_role_and_authorization",
                "information_density_and_rhythm",
                "author_voice_non_regression",
            ],
            "empty_or_generic_benefit_is_clearance": False,
            "local_model_or_caller_assertion_is_clearance": False,
            "validator_pass_is_quality_clearance": False,
        },
        "limitations": {
            "academic_correctness": "NOT_EVALUATED",
            "authorship": "NOT_EVALUATED",
            "quality_clearance_granted": False,
        },
    }
    return {
        **request_body,
        "request_sha256": _sha256(_canonical_json_bytes(request_body)),
    }


def _warning_review_attestation(
    warning_resolutions: dict[str, str],
    warning_review_request_sha256: str,
    reviewer_kind: str,
    reviewer_id: str,
    current_request: dict[str, Any] | None,
) -> dict[str, Any]:
    kind = reviewer_kind.strip().upper() or "NONE"
    identity = reviewer_id.strip()
    request_sha256 = warning_review_request_sha256.strip().lower()
    if kind != "NONE" or identity:
        raise ValueError(
            "warning reviewer identity metadata is retired; submit only a request-bound "
            "unverified caller proposal"
        )
    if warning_resolutions:
        if not re.fullmatch(r"[0-9a-f]{64}", request_sha256):
            raise ValueError(
                "warning_resolutions require a 64-character "
                "warning_review_request_sha256 from the current REVIEW result"
            )
        if current_request is None or request_sha256 != current_request["request_sha256"]:
            raise ValueError(
                "warning_review_request_sha256 does not match the current artifact, "
                "warning details, validation context, or policy hashes"
            )
        current_fingerprints = {
            item["warning_fingerprint"] for item in current_request["warnings"]
        }
        unknown = sorted(set(warning_resolutions) - current_fingerprints)
        if unknown:
            raise ValueError(
                "warning resolution fingerprint not present in current request: "
                + ",".join(unknown)
            )
        return {
            "proposal_source": "UNVERIFIED_CALLER_PROPOSAL",
            "reviewer_identifier_collected": False,
            "stable_reviewer_pseudonym_recorded": False,
            "cross_record_reviewer_linkability": "NOT_RECORDED",
            "identity_verified": False,
            "review_clearance_granted": False,
            "attestation_status": "NOT_APPLICABLE",
            "warning_review_request_sha256": request_sha256,
            "proposed_warning_fingerprints": sorted(warning_resolutions),
        }
    if request_sha256:
        raise ValueError(
            "warning request hash is only valid with warning_resolutions proposals"
        )
    return {
        "proposal_source": "NOT_PROVIDED",
        "reviewer_identifier_collected": False,
        "stable_reviewer_pseudonym_recorded": False,
        "cross_record_reviewer_linkability": "NOT_RECORDED",
        "identity_verified": False,
        "review_clearance_granted": False,
        "attestation_status": "NOT_PROVIDED",
        "warning_review_request_sha256": None,
        "proposed_warning_fingerprints": [],
    }


def _finding_key(finding: dict[str, Any]) -> tuple[str, str]:
    matched = re.sub(r"\s+", "", str(finding["matched"]))
    return str(finding["signal_id"]), matched


def _finding_hash(finding: dict[str, Any]) -> str:
    stable = {
        key: finding[key]
        for key in ("line", "column", "signal_id", "matched", "context", "severity", "action")
    }
    return _sha256(
        json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )


def _finding_identity(finding: dict[str, Any]) -> tuple[str, int, int, str]:
    return (
        str(finding["signal_id"]),
        int(finding["line"]),
        int(finding["column"]),
        _finding_hash(finding),
    )


def _introduced_findings(
    before: Sequence[dict[str, Any]],
    after: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    remaining = Counter(_finding_key(item) for item in before if item["candidate"])
    introduced: list[dict[str, Any]] = []
    for finding in (item for item in after if item["candidate"]):
        key = _finding_key(finding)
        if remaining[key] > 0:
            remaining[key] -= 1
        else:
            introduced.append(finding)
    return introduced


def _public_finding(finding: dict[str, Any]) -> dict[str, Any]:
    public = {
        key: finding[key]
        for key in (
            "file",
            "line",
            "column",
            "signal_id",
            "severity",
            "action",
            "matched",
            "context",
            "count",
            "rationale",
        )
    }
    public["file"] = Path(str(public["file"])).name
    public["finding_hash"] = _finding_hash(finding)
    return public


def _resolve_keep_reasons(
    reasons: dict[str, str],
    findings: Sequence[dict[str, Any]],
    valid_ids: set[str],
) -> tuple[set[tuple[str, int, int, str]], list[dict[str, Any]]]:
    accepted: set[tuple[str, int, int, str]] = set()
    records: list[dict[str, Any]] = []
    for key, raw_reason in reasons.items():
        signal_id, binding = _parse_keep_key(key, valid_ids)
        reason = _validate_reason(raw_reason, f"{key} 的 KEEP 理由")
        matches = [item for item in findings if item["signal_id"] == signal_id]
        if binding is None:
            if len(matches) != 1:
                raise ValueError(
                    f"{signal_id} 对应 {len(matches)} 个待复核位置；"
                    "必须使用 SIGNAL_ID@LINE:COLUMN 或 @sha256:HASH"
                )
        elif binding.startswith("sha256:"):
            prefix = binding.removeprefix("sha256:")
            matches = [item for item in matches if _finding_hash(item).startswith(prefix)]
        else:
            line, column = (int(part) for part in binding.split(":", 1))
            matches = [
                item
                for item in matches
                if int(item["line"]) == line and int(item["column"]) == column
            ]
        if len(matches) != 1:
            raise ValueError(f"{key} 未唯一定位待复核 finding（匹配 {len(matches)} 个）")
        finding = matches[0]
        identity = _finding_identity(finding)
        if identity in accepted:
            raise ValueError(f"{key} 重复接受同一 finding")
        accepted.add(identity)
        record = _public_finding(finding)
        record.update({"binding": key, "reason": reason})
        records.append(record)
    return accepted, records


def _source_value_missing(source: Sequence[str], output: Sequence[str]) -> list[str]:
    """Return DRAFT payload values that never occur in the supplied artifact."""
    source_values = set(source)
    return [item for item in output if item not in source_values]


def _coalesce_ranges(ranges: Sequence[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _matches_selection_only_edit(
    before_text: str,
    after_text: str,
    editable_ranges: Sequence[tuple[int, int]],
) -> bool:
    """Return whether after can be formed by replacing only the supplied ranges."""
    prefix = before_text[: editable_ranges[0][0]]
    suffix = before_text[editable_ranges[-1][1] :]
    if not after_text.startswith(prefix) or not after_text.endswith(suffix):
        return False

    cursor = len(prefix)
    suffix_start = len(after_text) - len(suffix)
    for (_, previous_end), (next_start, _) in zip(editable_ranges, editable_ranges[1:]):
        immutable = before_text[previous_end:next_start]
        if not immutable:
            continue
        found = after_text.find(immutable, cursor, suffix_start)
        if found < 0:
            return False
        cursor = found + len(immutable)
    return cursor <= suffix_start


def _report_scope_invariants(
    report_scope_path: Path,
    *,
    before_path: Path,
    before_raw: bytes,
    before_text: str,
    after_text: str,
) -> dict[str, Any]:
    """Bind a REPORT_INFORMED rewrite to exact extractor ranges and source bytes."""
    scope_raw, scope_text = _read_utf8(report_scope_path)
    payload = _strict_json_bytes(scope_raw, label="report scope")
    if not isinstance(payload, dict):
        raise ValueError("report scope must be a JSON object")
    if payload.get("schema_version") != detector_scope.SCHEMA_VERSION:
        raise ValueError("report scope schema_version is unsupported")
    if payload.get("operation") != "detector_report_scope_extraction":
        raise ValueError("report scope operation is invalid")
    if payload.get("status") != "PASS" or payload.get("exit_code") != 0:
        raise ValueError("report scope must be extractor PASS/0")

    report_path = _resolve_scope_locator(
        report_scope_path,
        payload.get("report_path"),
        field="report_path",
    )
    replayed = detector_scope.analyze_report(report_path, before_path)
    for key in (
        "status",
        "exit_code",
        "report_sha256",
        "source_sha256",
        "coverage",
        "fragments",
    ):
        if payload.get(key) != replayed.get(key):
            raise ValueError(f"report scope does not match extractor replay: {key}")

    before_sha256 = _sha256(before_raw)
    if payload.get("source_sha256") != before_sha256:
        raise ValueError("report scope source_sha256 does not match the exact before artifact")

    fragments = payload.get("fragments")
    coverage = payload.get("coverage")
    if not isinstance(fragments, list) or not fragments:
        raise ValueError("report scope must contain at least one fragment")
    if not isinstance(coverage, dict):
        raise ValueError("report scope coverage is missing")
    if coverage.get("total_fragments") != len(fragments):
        raise ValueError("report scope coverage total does not match fragments")
    if coverage.get("uniquely_mapped") != len(fragments):
        raise ValueError("report scope contains a fragment that is not uniquely mapped")
    if any(coverage.get(key) != 0 for key in ("missing", "ambiguous", "source_errors")):
        raise ValueError("report scope contains unresolved mapping results")

    raw_ranges: list[tuple[int, int]] = []
    for position, fragment in enumerate(fragments, start=1):
        if not isinstance(fragment, dict) or fragment.get("mapping_status") != "UNIQUE":
            raise ValueError(f"report scope fragment {position} is not UNIQUE")
        if fragment.get("source_occurrences") != 1:
            raise ValueError(f"report scope fragment {position} is not uniquely sourced")
        start = fragment.get("source_start")
        end = fragment.get("source_end")
        if (
            not isinstance(start, int)
            or isinstance(start, bool)
            or not isinstance(end, int)
            or isinstance(end, bool)
            or start < 0
            or end <= start
            or end > len(before_text)
        ):
            raise ValueError(f"report scope fragment {position} has an invalid source range")
        expected = fragment.get("normalized_text")
        actual = detector_scope.normalize_text(before_text[start:end])
        if not isinstance(expected, str) or actual != expected:
            raise ValueError(f"report scope fragment {position} no longer matches source text")
        raw_ranges.append((start, end))

    editable_ranges = _coalesce_ranges(raw_ranges)
    outside_unchanged = _matches_selection_only_edit(before_text, after_text, editable_ranges)
    return {
        "status": "PASS" if outside_unchanged else "FAIL",
        "scope_path": None,
        "scope_sha256": None,
        "scope_semantic_sha256": _report_scope_semantic_sha256(payload),
        "report_sha256": payload["report_sha256"],
        "source_sha256": before_sha256,
        "extractor_replay_match": True,
        "fragment_count": len(fragments),
        "editable_range_count": len(editable_ranges),
        "editable_ranges": [
            {"source_start": start, "source_end": end} for start, end in editable_ranges
        ],
        "outside_selection_unchanged": outside_unchanged,
    }


def _draft_derived_comparison_candidates(
    text: str,
    *,
    document_format: str,
) -> list[dict[str, Any]]:
    surface, _protected = invariants._speech_surface(
        text,
        document_format,
        True,
    )
    sentences = invariants._segment_spans(surface, r"[。！？!?；;\n]+", "D")
    candidates: list[dict[str, Any]] = []
    for category, pattern in DRAFT_DERIVED_COMPARISON_PATTERNS:
        for match in pattern.finditer(surface):
            sentence = invariants._containing_span(sentences, match.start())
            if sentence is None:
                continue
            line, column = invariants._line_column(surface, match.start())
            candidates.append(
                {
                    "category": category,
                    "line": line,
                    "column": column,
                    "match": re.sub(r"\s+", " ", match.group(0)).strip()[:120],
                    "sentence_context": re.sub(
                        r"\s+", " ", str(sentence["text"])
                    ).strip()[:240],
                }
            )
    return sorted(
        candidates,
        key=lambda item: (int(item["line"]), int(item["column"]), str(item["category"])),
    )


def _draft_surface_source_invariants(
    supplied_text: str,
    draft_text: str,
    *,
    document_format: str,
    protected_terms: Sequence[str],
) -> tuple[Any, dict[str, Any]]:
    """Check deterministic DRAFT surface payload without claiming semantic entailment.

    DRAFT may omit supplied material, so rewrite equality invariants are inapplicable.
    This gate instead rejects protected or literal payload that appears in the draft but
    nowhere in the supplied artifact. It deliberately does not certify natural-language
    entailment; that remains a separate NOT_EVALUATED layer.
    """
    result = invariants.check_documents(
        draft_text,
        draft_text,
        document_format=document_format,
        protected_terms=protected_terms,
    )
    supplied_normalized, supplied_code, supplied_code_ranges = invariants._prepare(
        supplied_text,
        document_format,
    )
    draft_normalized, draft_code, draft_code_ranges = invariants._prepare(
        draft_text,
        document_format,
    )
    supplied_math = invariants._math_spans(supplied_normalized, supplied_code_ranges)
    draft_math = invariants._math_spans(draft_normalized, draft_code_ranges)
    supplied_math_ranges = invariants._locate_exact_spans(supplied_normalized, supplied_math)
    draft_math_ranges = invariants._locate_exact_spans(draft_normalized, draft_math)
    supplied_excluded = sorted(supplied_code_ranges + supplied_math_ranges)
    draft_excluded = sorted(draft_code_ranges + draft_math_ranges)

    checks: list[tuple[str, str, Sequence[str], Sequence[str]]] = [
        (
            "DRAFT_CODE_NOT_SUPPLIED",
            "Code span in draft is absent from supplied content",
            supplied_code,
            draft_code,
        ),
        (
            "DRAFT_MATH_NOT_SUPPLIED",
            "Math span in draft is absent from supplied content",
            supplied_math,
            draft_math,
        ),
        (
            "DRAFT_FORMAL_STATEMENT_NOT_SUPPLIED",
            "Formal statement span in draft is absent from supplied content",
            invariants._extract_environment_spans(
                supplied_normalized,
                invariants.FORMAL_STATEMENT_ENVIRONMENTS,
            ),
            invariants._extract_environment_spans(
                draft_normalized,
                invariants.FORMAL_STATEMENT_ENVIRONMENTS,
            ),
        ),
        (
            "DRAFT_CRITICAL_COMMAND_NOT_SUPPLIED",
            "Citation, reference, label, URL, or other critical command was not supplied",
            invariants._critical_commands(supplied_normalized, supplied_code_ranges),
            invariants._critical_commands(draft_normalized, draft_code_ranges),
        ),
        (
            "DRAFT_QUOTATION_NOT_SUPPLIED",
            "Direct quotation in draft is absent from supplied content",
            invariants._quotation_spans(supplied_normalized, supplied_excluded),
            invariants._quotation_spans(draft_normalized, draft_excluded),
        ),
        (
            "DRAFT_NUMBER_OR_UNIT_NOT_SUPPLIED",
            "Number or unit in draft is absent from supplied content",
            invariants._numbers_and_units(supplied_normalized, supplied_code_ranges),
            invariants._numbers_and_units(draft_normalized, draft_code_ranges),
        ),
        (
            "DRAFT_GARBLED_TEXT_NOT_SUPPLIED",
            "Garbled span in draft is absent from supplied content",
            invariants._garbled_spans(supplied_text),
            invariants._garbled_spans(draft_text),
        ),
    ]
    details: dict[str, Any] = {}
    for code, message, source_items, output_items in checks:
        missing = _source_value_missing(source_items, output_items)
        details[code] = {
            "supplied_count": len(source_items),
            "draft_count": len(output_items),
            "not_supplied": missing,
        }
        if missing:
            result.errors.append(
                invariants.Diagnostic(
                    code=code,
                    severity="error",
                    message=message,
                    details=details[code],
                )
            )

    supplied_attribution = invariants._marker_counts(supplied_text)["attribution_source"]
    draft_attribution = invariants._marker_counts(draft_text)["attribution_source"]
    attribution_missing = list((draft_attribution - supplied_attribution).elements())
    details["DRAFT_ATTRIBUTION_NOT_SUPPLIED"] = {
        "supplied": dict(sorted(supplied_attribution.items())),
        "draft": dict(sorted(draft_attribution.items())),
        "not_supplied": attribution_missing,
    }
    if attribution_missing:
        result.errors.append(
            invariants.Diagnostic(
                code="DRAFT_ATTRIBUTION_NOT_SUPPLIED",
                severity="error",
                message="Attribution or literature-source marker was introduced without supply",
                details=details["DRAFT_ATTRIBUTION_NOT_SUPPLIED"],
            )
        )

    terms = invariants.normalize_protected_terms(protected_terms)
    supplied_term_values = set(invariants._term_occurrences(supplied_text, terms))
    draft_term_items = invariants._term_occurrences(draft_text, terms)
    term_missing = [term for term in draft_term_items if term not in supplied_term_values]
    details["DRAFT_PROTECTED_TERM_NOT_SUPPLIED"] = {
        "protected_terms": terms,
        "not_supplied": term_missing,
    }
    if term_missing:
        result.errors.append(
            invariants.Diagnostic(
                code="DRAFT_PROTECTED_TERM_NOT_SUPPLIED",
                severity="error",
                message="Protected term occurrence in draft is absent from supplied content",
                details=details["DRAFT_PROTECTED_TERM_NOT_SUPPLIED"],
            )
        )

    supplied_comparisons = _draft_derived_comparison_candidates(
        supplied_text,
        document_format=document_format,
    )
    draft_comparisons = _draft_derived_comparison_candidates(
        draft_text,
        document_format=document_format,
    )
    supplied_comparison_budget = Counter(
        str(item["category"]) for item in supplied_comparisons
    )
    introduced_comparisons: list[dict[str, Any]] = []
    for item in draft_comparisons:
        category = str(item["category"])
        if supplied_comparison_budget[category] > 0:
            supplied_comparison_budget[category] -= 1
        else:
            introduced_comparisons.append(item)
    comparison_details = {
        "supplied_candidates": supplied_comparisons,
        "draft_candidates": draft_comparisons,
        "introduced_candidates": introduced_comparisons,
        "semantic_entailment": "NOT_EVALUATED",
        "required_action": "PRESERVE_EXPLICIT_SUPPLIED_RELATIONS",
        "detector_scope": "NARROW_DERIVED_COMPARISON_SURFACE_CANDIDATES",
    }
    details["DRAFT_DERIVED_COMPARISON_NOT_SUPPLIED"] = comparison_details
    if introduced_comparisons:
        result.warnings.append(
            invariants.Diagnostic(
                code="DRAFT_DERIVED_COMPARISON_NOT_SUPPLIED",
                severity="warning",
                message=(
                    "The draft introduces a comparison or cross-scenario intensification "
                    "surface that was not explicitly supplied; semantic entailment is not "
                    "evaluated, so preserve the supplied values and relations or escalate."
                ),
                details=comparison_details,
            )
        )

    result.evidence["draft_surface_source"] = details
    surface = {
        "status": "FAIL" if result.errors else "PASS",
        "semantic_entailment_certified": False,
        "scope": [
            "code",
            "math",
            "formal_statements",
            "critical_tex_commands",
            "direct_quotations",
            "numbers_and_units",
            "garbled_spans",
            "attribution_markers",
            "explicit_protected_terms",
            "derived_comparison_markers",
        ],
        "details": details,
    }
    return result, surface


def validate(
    before_path: Path,
    after_path: Path,
    *,
    mode: str = "REWRITE",
    scene: str = "AUTO",
    keep_reasons: dict[str, str] | None = None,
    accepted_warnings: dict[str, str] | None = None,
    warning_resolutions: dict[str, str] | None = None,
    warning_review_request_sha256: str = "",
    warning_reviewer_kind: str = "NONE",
    warning_reviewer_id: str = "",
    strict_speech_acts: bool = False,
    protected_terms: Sequence[str] = (),
    fragment_mode: bool = False,
    report_scope_path: Path | None = None,
    template_field_edit_scope_path: Path | None = None,
    editable_style_wrappers: Sequence[str] = (),
    document_format: str | None = None,
) -> dict[str, Any]:
    policy_snapshot = _policy_hashes()
    mode = mode.upper()
    if mode not in VALIDATION_MODES:
        raise ValueError(f"mode must be one of {VALIDATION_MODES}")
    if fragment_mode and mode != "REWRITE":
        raise ValueError("fragment_mode is only valid for REWRITE")
    if report_scope_path is not None and mode != "REWRITE":
        raise ValueError("report_scope_path is only valid for REWRITE")
    if report_scope_path is not None and fragment_mode:
        raise ValueError("report_scope_path requires full-document validation, not fragment_mode")
    if template_field_edit_scope_path is not None and mode != "REWRITE":
        raise ValueError("template_field_edit_scope_path is only valid for REWRITE")
    before_raw, before_text = _read_utf8(before_path)
    after_raw, after_text = _read_utf8(after_path)
    document_format = _document_format(before_path, after_path, document_format)
    template_field_edit_scope_check, template_field_authorization = (
        _load_template_field_edit_scope(
            template_field_edit_scope_path,
            before_raw=before_raw,
            before_text=before_text,
            document_format=document_format,
        )
    )
    lexicon = lexical.load_lexicon()
    keep_reasons = keep_reasons or {}
    accepted_warnings = accepted_warnings or {}
    warning_resolutions = warning_resolutions or {}
    if accepted_warnings:
        raise ValueError(
            "accepted_warnings/--accept-warning is retired because a caller assertion "
            "cannot clear warnings; use warning_resolutions/--propose-warning-resolution "
            "with the current review request"
        )
    terms = invariants.normalize_protected_terms(protected_terms)
    valid_signal_ids = {item["id"] for item in lexicon["signals"]}
    for key, reason in keep_reasons.items():
        _parse_keep_key(key, valid_signal_ids)
        _validate_reason(reason, f"{key} 的 KEEP 理由")

    if mode == "DRAFT":
        invariant_result, draft_surface_source_check = _draft_surface_source_invariants(
            before_text,
            after_text,
            document_format=document_format,
            protected_terms=terms,
        )
        semantic_source_check = (
            "PASS_COPY_ONLY" if before_text.strip() == after_text.strip() else "NOT_EVALUATED"
        )
    else:
        invariant_result = invariants.check_documents(
            before_text,
            after_text,
            document_format=document_format,
            strict_speech_acts=strict_speech_acts,
            protected_terms=terms,
            fragment_mode=fragment_mode,
            editable_style_wrappers=editable_style_wrappers,
        )
        draft_surface_source_check = {
            "status": "N/A",
            "semantic_entailment_certified": False,
            "scope": [],
            "details": {},
        }
        semantic_source_check = "N/A"
    report_scope_check: dict[str, Any] = {
        "status": "N/A",
        "scope_path": None,
        "scope_sha256": None,
        "scope_semantic_sha256": None,
        "report_sha256": None,
        "source_sha256": None,
        "extractor_replay_match": None,
        "fragment_count": 0,
        "editable_range_count": 0,
        "editable_ranges": [],
        "outside_selection_unchanged": None,
    }
    if report_scope_path is not None:
        report_scope_check = _report_scope_invariants(
            report_scope_path,
            before_path=before_path,
            before_raw=before_raw,
            before_text=before_text,
            after_text=after_text,
        )
        invariant_result.evidence["document_scope"] = "REPORT_SELECTION"
        if report_scope_check["status"] == "FAIL":
            invariant_result.errors.append(
                invariants.Diagnostic(
                    code="REPORT_SCOPE_OUTSIDE_SELECTION_CHANGED",
                    severity="error",
                    message="Text outside uniquely mapped report selections changed",
                    details=report_scope_check,
                )
            )
    template_field_findings: list[dict[str, Any]] = []
    template_field_warnings: list[invariants.Diagnostic] = []
    if mode == "REWRITE":
        (
            template_field_errors,
            template_field_warnings,
            template_field_findings,
        ) = _template_field_change_audit(
            before_text,
            after_text,
            before_raw=before_raw,
            after_raw=after_raw,
            authorization_by_line=template_field_authorization,
            scope_provided=bool(template_field_edit_scope_path),
            document_format=document_format,
        )
        invariant_result.errors.extend(template_field_errors)
    before_style_findings = lexical.scan_text_with_offsets(
        before_text,
        file="before",
        scene=scene,
        lexicon=lexicon,
        document_format=document_format,
    )
    after_style_findings = lexical.scan_text_with_offsets(
        after_text,
        file="after",
        scene=scene,
        lexicon=lexicon,
        document_format=document_format,
    )
    before_findings = [
        {
            key: value
            for key, value in finding.items()
            if key not in {"start_char", "end_char"}
        }
        for finding in before_style_findings
    ]
    after_findings = [
        {
            key: value
            for key, value in finding.items()
            if key not in {"start_char", "end_char"}
        }
        for finding in after_style_findings
    ]
    introduced = _introduced_findings(before_findings, after_findings)
    paired_style_delta_findings = _course_voice_flattening_findings(
        before_text,
        after_text,
        before_raw=before_raw,
        after_raw=after_raw,
        mode=mode,
        scene=scene,
        document_format=document_format,
        editable_style_wrappers=editable_style_wrappers,
        before_style_findings=before_style_findings,
    )
    reviewable_by_identity: dict[tuple[str, int, int, str], dict[str, Any]] = {}
    for item in after_findings:
        if item["candidate"] and item["severity"] == "high":
            reviewable_by_identity[_finding_identity(item)] = item
    for item in introduced:
        reviewable_by_identity[_finding_identity(item)] = item
    accepted_identities, accepted_findings = _resolve_keep_reasons(
        keep_reasons,
        list(reviewable_by_identity.values()),
        valid_signal_ids,
    )
    unexplained_high = [
        item
        for item in after_findings
        if item["candidate"]
        and item["severity"] == "high"
        and _finding_identity(item) not in accepted_identities
    ]
    strict_before_findings = [
        item
        for item in before_findings
        if str(item.get("signal_id", "")).startswith("LEX-STRICT-CORPUS-")
        and item.get("candidate")
    ]
    strict_after_findings = [
        item
        for item in after_findings
        if str(item.get("signal_id", "")).startswith("LEX-STRICT-CORPUS-")
        and item.get("candidate")
    ]
    unexplained_strict = [
        item
        for item in strict_after_findings
        if _finding_identity(item) not in accepted_identities
    ]
    unexplained_introduced = [
        item for item in introduced if _finding_identity(item) not in accepted_identities
    ]
    normalized_resolutions: dict[str, str] = {}
    for fingerprint, reason in warning_resolutions.items():
        if not re.fullmatch(r"[0-9a-fA-F]{64}", fingerprint):
            raise ValueError(
                "warning resolution keys must be full 64-character warning fingerprints"
            )
        normalized_fingerprint = fingerprint.lower()
        if normalized_fingerprint in normalized_resolutions:
            raise ValueError(f"duplicate warning resolution: {normalized_fingerprint}")
        normalized_resolutions[normalized_fingerprint] = _validate_reason(
            reason,
            f"{normalized_fingerprint} 的处理建议",
        )
    warning_resolutions = normalized_resolutions
    before_sha256 = _sha256(before_raw)
    after_sha256 = _sha256(after_raw)
    protected_term_evidence = invariant_result.evidence["protected_terms"]
    warning_review_request = _build_warning_review_request(
        invariant_result.warnings,
        before_sha256=before_sha256,
        after_sha256=after_sha256,
        mode=mode,
        scene=scene,
        document_format=document_format,
        protected_terms=protected_term_evidence,
        strict_speech_acts=strict_speech_acts,
        fragment_mode=fragment_mode,
        policy_hashes=policy_snapshot,
    )
    warning_review = _warning_review_attestation(
        warning_resolutions,
        warning_review_request_sha256,
        warning_reviewer_kind,
        warning_reviewer_id,
        warning_review_request,
    )
    unaccepted_warnings = list(invariant_result.warnings)
    proposed_fingerprints = {item.lower() for item in warning_resolutions}
    warnings_without_resolution_proposal = [
        item
        for item in invariant_result.warnings
        if _warning_fingerprint(item) not in proposed_fingerprints
    ]

    if invariant_result.errors:
        mechanical_validation_status, mechanical_validation_exit_code = "FAIL", 1
    elif (
        unaccepted_warnings
        or template_field_warnings
        or unexplained_high
        or unexplained_introduced
        or paired_style_delta_findings
    ):
        mechanical_validation_status, mechanical_validation_exit_code = "REVIEW", 2
    else:
        mechanical_validation_status, mechanical_validation_exit_code = "PASS", 0

    paired_quality_review_request = _build_paired_quality_review_request(
        before_raw.decode("utf-8"),
        after_raw.decode("utf-8"),
        before_sha256=before_sha256,
        after_sha256=after_sha256,
        mode=mode,
        scene=scene,
        document_format=document_format,
        fragment_mode=fragment_mode,
        mechanical_validation_status=mechanical_validation_status,
        policy_hashes=policy_snapshot,
        report_scope_binding=(
            {
                "scope_semantic_sha256": report_scope_check[
                    "scope_semantic_sha256"
                ],
                "report_sha256": report_scope_check["report_sha256"],
                "source_sha256": report_scope_check["source_sha256"],
                "fragment_count": report_scope_check["fragment_count"],
                "editable_ranges": report_scope_check["editable_ranges"],
            }
            if report_scope_path is not None
            else None
        ),
        template_field_changes=template_field_findings,
    )
    if paired_quality_review_request is None:
        paired_quality_review_status = "NOT_REQUIRED"
    else:
        paired_quality_review_status = str(paired_quality_review_request["status"])

    if mechanical_validation_status == "FAIL":
        status, exit_code = "FAIL", 1
    elif mechanical_validation_status == "REVIEW":
        status, exit_code = "REVIEW", 2
    elif semantic_source_check == "NOT_EVALUATED":
        status, exit_code = "REVIEW", 2
    elif paired_quality_review_status == "PENDING_EXTERNAL_REVIEW":
        status, exit_code = "REVIEW", 2
    else:
        status, exit_code = "PASS", 0

    hard_invariant_layer_status = "FAIL" if invariant_result.errors else "PASS"
    speech_act_layer_status = "REVIEW" if unaccepted_warnings else "PASS"
    style_signal_layer_status = (
        "REVIEW"
        if unexplained_high or unexplained_introduced or paired_style_delta_findings
        else "PASS"
    )
    template_field_layer_status = (
        "NOT_APPLICABLE"
        if mode != "REWRITE"
        else "FAIL"
        if any(item.get("severity") == "error" for item in template_field_findings)
        else "REVIEW"
        if template_field_warnings
        else "PASS"
    )
    paired_style_delta_layer_status = (
        "NOT_APPLICABLE"
        if mode != "REWRITE" or scene.upper() != "COURSE"
        else "REVIEW" if paired_style_delta_findings else "PASS"
    )

    review_reasons: list[str] = []
    if unaccepted_warnings:
        review_reasons.append("speech_act_warning")
    if template_field_warnings:
        review_reasons.append("template_field_authorization_or_role_drift")
    if unexplained_high:
        review_reasons.append("unexplained_high_severity_signal")
    if unexplained_strict:
        review_reasons.append("unexplained_strict_corpus_signal")
    if unexplained_introduced:
        review_reasons.append("introduced_style_signal")
    if paired_style_delta_findings:
        review_reasons.append("course_voice_flattening_cluster")
    if semantic_source_check == "NOT_EVALUATED":
        review_reasons.append("semantic_source_not_evaluated")
    if paired_quality_review_status == "PENDING_EXTERNAL_REVIEW":
        review_reasons.append("paired_quality_not_evaluated")

    if _policy_hashes() != policy_snapshot:
        raise ValueError("validation policy changed while the validator was running")

    return {
        "status": status,
        "exit_code": exit_code,
        "candidate_assembly_status": mechanical_validation_status,
        "candidate_assembly_exit_code": mechanical_validation_exit_code,
        "mechanical_validation_status": mechanical_validation_status,
        "mechanical_validation_exit_code": mechanical_validation_exit_code,
        "delivery_gate_status": status,
        "delivery_gate_exit_code": exit_code,
        "hard_invariant_layer_status": hard_invariant_layer_status,
        "speech_act_layer_status": speech_act_layer_status,
        "speech_act_diagnostics": invariant_result.to_dict().get(
            "advisories", []
        ),
        "style_signal_layer_status": style_signal_layer_status,
        "template_field_layer_status": template_field_layer_status,
        "template_field_findings": template_field_findings,
        "template_field_edit_scope_check": template_field_edit_scope_check,
        "paired_style_delta_layer_status": paired_style_delta_layer_status,
        "paired_style_delta_findings": paired_style_delta_findings,
        "paired_quality_review_status": paired_quality_review_status,
        "paired_quality_review_request": paired_quality_review_request,
        "paired_quality_review_local_clearance_supported": False,
        "paired_quality_clearance_granted": False,
        "humanize_quality_claim_allowed": (
            mode != "DRAFT"
            and paired_quality_review_status == "NOT_REQUIRED"
            and mechanical_validation_status == "PASS"
        ),
        "academic_correctness": "NOT_EVALUATED",
        "mode": mode,
        "scene": scene.upper(),
        "draft_surface_source_check": draft_surface_source_check,
        "report_scope_check": report_scope_check,
        "semantic_source_check": semantic_source_check,
        "evidence": {
            "checker_executed": True,
            "before_path": None,
            "after_path": None,
            "source_path_archived": False,
            "before_sha256": before_sha256,
            "after_sha256": after_sha256,
            "document_format": document_format,
            "document_scope": (
                "REPORT_SELECTION"
                if report_scope_path is not None
                else "FRAGMENT" if fragment_mode else "DOCUMENT"
            ),
            "protected_terms": protected_term_evidence,
            "policy_hashes": policy_snapshot,
        },
        "invariants": invariant_result.to_dict(),
        "lexical_summary": {
            "before_candidates": len(before_findings),
            "after_candidates": len(after_findings),
            "introduced_candidates": len(introduced),
            "unexplained_high_candidates": len(unexplained_high),
            "accepted_candidates": len(accepted_findings),
        },
        "strict_corpus_summary": {
            "enabled": True,
            "before_candidates": len(strict_before_findings),
            "after_candidates": len(strict_after_findings),
            "unexplained_candidates": len(unexplained_strict),
            "accepted_candidates": sum(
                _finding_identity(item) in accepted_identities
                for item in strict_after_findings
            ),
            "no_change_allowed": not bool(unexplained_strict),
            "clean_allowed_by_strict_layer": not bool(unexplained_strict),
        },
        "paired_style_delta_summary": {
            "status": paired_style_delta_layer_status,
            "finding_count": len(paired_style_delta_findings),
            "scope": "PAIRED_COURSE_VOICE_NON_REGRESSION_CANDIDATE",
            "authorship_inference": False,
        },
        "template_field_summary": {
            "status": template_field_layer_status,
            "finding_count": len(template_field_findings),
            "review_finding_count": len(template_field_warnings),
            "authorized_edit_count": int(
                template_field_edit_scope_check["authorized_edit_count"]
            ),
            "permission_boundary": TEMPLATE_FIELD_PERMISSION,
            "local_clearance_supported": False,
        },
        "review_reasons": review_reasons,
        "keep_reasons": dict(sorted(keep_reasons.items())),
        "accepted_warning_reasons": {},
        "warning_resolutions": dict(sorted(warning_resolutions.items())),
        "warning_review_request": warning_review_request,
        "warning_proposal_state": warning_review,
        "accepted_findings": accepted_findings,
        "accepted_warnings": [],
        "proposed_warning_resolutions": [
            {
                **_public_warning(item),
                "reason": warning_resolutions[_warning_fingerprint(item)],
                "review_clearance_granted": False,
            }
            for item in invariant_result.warnings
            if _warning_fingerprint(item) in proposed_fingerprints
        ],
        "pending_warnings": [_public_warning(item) for item in unaccepted_warnings],
        "warnings_without_resolution_proposal": [
            _public_warning(item) for item in warnings_without_resolution_proposal
        ],
        "unaccepted_warnings": [_public_warning(item) for item in unaccepted_warnings],
        "unexplained_high_findings": [_public_finding(item) for item in unexplained_high],
        "unexplained_strict_findings": [
            _public_finding(item) for item in unexplained_strict
        ],
        "introduced_findings": [_public_finding(item) for item in unexplained_introduced],
    }


def _text_output(payload: dict[str, Any]) -> str:
    evidence = payload["evidence"]
    summary = payload["lexical_summary"]
    lines = [
        f"status: {payload['status']}",
        f"delivery_gate_status: {payload['delivery_gate_status']}",
        f"hard_invariant_layer_status: {payload['hard_invariant_layer_status']}",
        f"speech_act_layer_status: {payload['speech_act_layer_status']}",
        f"style_signal_layer_status: {payload['style_signal_layer_status']}",
        f"template_field_layer_status: {payload['template_field_layer_status']}",
        f"paired_style_delta_layer_status: {payload['paired_style_delta_layer_status']}",
        f"candidate_assembly_status: {payload['candidate_assembly_status']}",
        f"mechanical_validation_status: {payload['mechanical_validation_status']}",
        f"paired_quality_review_status: {payload['paired_quality_review_status']}",
        "paired_quality_review_request_sha256: "
        + (
            payload["paired_quality_review_request"]["request_sha256"]
            if payload["paired_quality_review_request"]
            else "NONE"
        ),
        "paired_quality_clearance_granted: "
        + str(payload["paired_quality_clearance_granted"]).upper(),
        "humanize_quality_claim_allowed: "
        + str(payload["humanize_quality_claim_allowed"]).upper(),
        f"academic_correctness: {payload['academic_correctness']}",
        f"mode: {payload['mode']}",
        f"document_scope: {payload['evidence']['document_scope']}",
        f"draft_surface_source_check: {payload['draft_surface_source_check']['status']}",
        f"report_scope_check: {payload['report_scope_check']['status']}",
        "template_field_edit_scope_check: "
        + str(payload["template_field_edit_scope_check"]["status"]),
        f"semantic_source_check: {payload['semantic_source_check']}",
        f"warning_proposal_source: {payload['warning_proposal_state']['proposal_source']}",
        f"warning_proposal_attestation_status: {payload['warning_proposal_state']['attestation_status']}",
        f"warning_proposal_identity_verified: {str(payload['warning_proposal_state']['identity_verified']).upper()}",
        f"warning_proposal_clearance_granted: {str(payload['warning_proposal_state']['review_clearance_granted']).upper()}",
        "warning_reviewer_identifier_collected: "
        + str(payload["warning_proposal_state"]["reviewer_identifier_collected"]).upper(),
        "warning_stable_reviewer_pseudonym_recorded: "
        + str(payload["warning_proposal_state"]["stable_reviewer_pseudonym_recorded"]).upper(),
        "warning_review_request_sha256: "
        + (
            payload["warning_review_request"]["request_sha256"]
            if payload["warning_review_request"]
            else "NONE"
        ),
        f"before_sha256: {evidence['before_sha256']}",
        f"after_sha256: {evidence['after_sha256']}",
        f"protected_terms: {evidence['protected_terms']['status']}",
        f"protected_term_count: {evidence['protected_terms']['count']}",
        f"protected_term_sha256: {evidence['protected_terms']['sha256'] or 'NONE'}",
        f"invariant_errors: {payload['invariants']['summary']['errors']}",
        f"invariant_warnings: {payload['invariants']['summary']['warnings']}",
        f"after_candidates: {summary['after_candidates']}",
        f"introduced_candidates: {summary['introduced_candidates']}",
        f"unexplained_high_candidates: {summary['unexplained_high_candidates']}",
        f"accepted_candidates: {summary['accepted_candidates']}",
        "paired_style_delta_findings: "
        + str(payload["paired_style_delta_summary"]["finding_count"]),
        "template_field_findings: "
        + str(payload["template_field_summary"]["finding_count"]),
    ]
    for reason in payload["review_reasons"]:
        lines.append(f"review: {reason}")
    for warning in payload["unaccepted_warnings"]:
        lines.append(
            f"warning: {warning['code']} [{warning['severity']}] {warning['message']}"
        )
    for finding in payload["unexplained_high_findings"]:
        display_file = Path(str(finding["file"])).name
        lines.append(
            f"[{finding['signal_id']}/{finding['severity']}] "
            f"{display_file}:{finding['line']}:{finding['column']} {finding['matched']}"
        )
    for finding in payload["paired_style_delta_findings"]:
        lines.append(
            f"paired-style: {finding['code']} [{finding['severity']}] "
            f"transitions={finding['observed']['distinct_transition_count']} "
            f"hunks={finding['observed']['changed_hunk_count']}"
        )
        for transition in finding["transitions"]:
            removed = transition["removed"]
            introduced = transition["introduced"]
            lines.append(
                f"paired-style-span: {transition['transition_id']} "
                f"before:{removed['line']}:{removed['column']}={removed['text']} "
                f"after:{introduced['line']}:{introduced['column']}={introduced['text']}"
            )
    for finding in payload["template_field_findings"]:
        lines.append(
            "template-field: "
            f"{finding['code']} [{finding['severity']}] "
            f"line={finding.get('source_line', 'N/A')} "
            f"label={finding.get('field_label', 'HEADER')} "
            f"authorization={finding['authorization_status']} "
            f"types={','.join(finding['change_types']) or 'NONE'}"
        )
    return "\n".join(lines) + "\n"


def _render_payload(payload: dict[str, Any], output_format: str) -> bytes:
    if output_format == "json":
        return _pretty_json_bytes(payload)
    if payload.get("schema") in {
        DIRECT_VALIDATION_EVIDENCE_ERROR_SCHEMA,
        DIRECT_VALIDATION_INPUT_ERROR_SCHEMA,
    }:
        return (
            "status: FAIL\n"
            f"delivery_gate_status: {payload['delivery_gate_status']}\n"
            f"error_code: {payload['error_code']}\n"
            f"error: {payload['error']}\n"
        ).encode("utf-8")
    return _text_output(payload).encode("utf-8")


def _emit_stdout(raw: bytes) -> None:
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is not None:
        buffer.write(raw)
        buffer.flush()
        return
    sys.stdout.write(raw.decode("utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="验证纯文风改写或 supplied-content 草稿的可机械边界。",
        allow_abbrev=False,
    )
    parser.add_argument("before", type=Path, help="改写前 UTF-8 Markdown/TeX")
    parser.add_argument("after", type=Path, help="改写后 UTF-8 Markdown/TeX")
    parser.add_argument(
        "--mode",
        type=str.upper,
        choices=VALIDATION_MODES,
        default="REWRITE",
        help="REWRITE 比较改前/改后；DRAFT 把第一个文件视为 supplied content，并保留语义来源 NOT_EVALUATED",
    )
    parser.add_argument(
        "--scene",
        type=str.upper,
        choices=lexical.SCENE_CHOICES,
        default="AUTO",
    )
    parser.add_argument(
        "--document-format",
        type=str.lower,
        choices=("auto", "markdown", "tex"),
        default="auto",
        help="Override suffix inference when Markdown or TeX content uses a neutral file suffix",
    )
    parser.add_argument("--format", choices=("json", "text"), default="text", dest="output_format")
    parser.add_argument(
        "--keep-reason",
        action="append",
        default=[],
        metavar="SIGNAL_ID[@LINE:COLUMN|@sha256:HASH]=具体理由",
        help=(
            "为唯一待复核的高风险 candidate 登记理由；多命中时必须绑定位置或 "
            "finding hash。受保护或排除命中天然不进入 candidate 审计，不能用 KEEP 绑定；可重复"
        ),
    )
    parser.add_argument(
        "--strict-speech-acts",
        action="store_true",
        help="把否定、模态、定义、报告状态等变化升级为硬错误",
    )
    parser.add_argument(
        "--fragment",
        action="store_true",
        help=(
            "Validate a REWRITE fragment: unchanged TeX boundary imbalance is allowed, "
            "but structural drift still fails"
        ),
    )
    parser.add_argument(
        "--report-scope",
        type=Path,
        help=(
            "Bind a REPORT_INFORMED REWRITE to extractor PASS/0 JSON and reject "
            "changes outside its UNIQUE source ranges"
        ),
    )
    parser.add_argument(
        "--template-field-edit-scope",
        type=Path,
        help=(
            "Bind edits to exact source lines whose labels are 适用题目、逻辑链条、"
            "给定首句 or 用词建议. The scope grants PAYLOAD_ONLY editing; labels and "
            "colons remain protected, and role/force drift still yields REVIEW/2."
        ),
    )
    parser.add_argument(
        "--accept-warning",
        action="append",
        default=[],
        metavar="CODE=具体理由",
        help="已停用；任何非空值都会报错，调用方声明不得清除 warning",
    )
    parser.add_argument(
        "--propose-warning-resolution",
        action="append",
        default=[],
        metavar="WARNING_FINGERPRINT=具体处理建议",
        help="对当前 review request 中的 warning 提交处理建议；只记录，不清除 REVIEW",
    )
    parser.add_argument(
        "--warning-review-request-sha256",
        default="",
        metavar="SHA256",
        help="首次 REVIEW 输出的 request_sha256；绑定 artifact、warning、配置与 policy",
    )
    parser.add_argument(
        "--warning-reviewer-kind",
        type=str.upper,
        choices=("HUMAN",),
        default="NONE",
        help="已停用；任何非空值都会报错，普通 proposal 不采集审阅者身份",
    )
    parser.add_argument(
        "--warning-reviewer-id",
        default="",
        help="已停用；任何非空值都会报错，避免在 argv、日志和证据中泄漏身份标签",
    )
    parser.add_argument(
        "--term",
        action="append",
        default=[],
        metavar="TERM",
        help="精确保护方法名、材料名或术语；可重复，未提供时不声称已自动校验",
    )
    parser.add_argument(
        "--evidence-dir",
        type=Path,
        default=None,
        metavar="DIR",
        help=(
            "原子保存输入、调用参数、validation result、paired-quality request、"
            "精确 stdout/stderr 和 evidence manifest；相同目录只允许逐字节幂等重放"
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        lexicon = lexical.load_lexicon()
        valid_ids = {item["id"] for item in lexicon["signals"]}
        keep_reasons = _parse_keep_reasons(args.keep_reason, valid_ids)
        if args.accept_warning:
            raise ValueError(
                "--accept-warning is retired because caller assertions cannot clear warnings; "
                "use --propose-warning-resolution with the current review request"
            )
        warning_resolutions = _parse_reason_pairs(
            args.propose_warning_resolution,
            "--propose-warning-resolution",
        )
        payload = validate(
            args.before,
            args.after,
            mode=args.mode,
            scene=args.scene,
            keep_reasons=keep_reasons,
            warning_resolutions=warning_resolutions,
            warning_review_request_sha256=args.warning_review_request_sha256,
            warning_reviewer_kind=args.warning_reviewer_kind,
            warning_reviewer_id=args.warning_reviewer_id,
            strict_speech_acts=args.strict_speech_acts,
            protected_terms=args.term,
            fragment_mode=args.fragment,
            report_scope_path=args.report_scope,
            template_field_edit_scope_path=args.template_field_edit_scope,
            document_format=(
                None if args.document_format == "auto" else args.document_format
            ),
        )
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        payload = _input_failure_payload(error)
        _emit_stdout(_render_payload(payload, args.output_format))
        return 1
    rendered_output: bytes
    if args.evidence_dir is not None:
        try:
            invocation_request = _build_invocation_request(
                payload,
                before=args.before,
                after=args.after,
                mode=args.mode,
                scene=args.scene,
                output_format=args.output_format,
                strict_speech_acts=args.strict_speech_acts,
                fragment_mode=args.fragment,
                report_scope_path=args.report_scope,
                template_field_edit_scope_path=args.template_field_edit_scope,
                protected_terms=args.term,
            )
            payload["evidence_bundle"] = _evidence_bundle_record(
                payload,
                run_id=invocation_request["run_id"],
            )
            rendered_output = _render_payload(payload, args.output_format)
            _persist_evidence_bundle(
                payload,
                before=args.before,
                after=args.after,
                output_dir=args.evidence_dir,
                invocation_request=invocation_request,
                rendered_output=rendered_output,
                rendered_stderr=b"",
                report_scope_path=args.report_scope,
                template_field_edit_scope_path=args.template_field_edit_scope,
            )
        except (OSError, UnicodeError, ValueError) as error:
            payload = _evidence_failure_payload(payload, error)
            rendered_output = _render_payload(payload, args.output_format)
    else:
        rendered_output = _render_payload(payload, args.output_format)
    _emit_stdout(rendered_output)
    return int(payload["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
