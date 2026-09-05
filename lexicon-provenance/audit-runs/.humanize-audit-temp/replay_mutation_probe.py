import copy
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from unittest import mock


SKILL = Path.home() / ".codex" / "skills" / "humanize-academic-chinese"
BASE = Path(__file__).parent / "direct-current.evidence"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


validator = load("humanize_probe_validator", SKILL / "scripts" / "validate_humanize_output.py")
replayer = load("humanize_probe_replayer", SKILL / "scripts" / "replay_humanize_validation_record.py")


def pretty(value):
    return validator._pretty_json_bytes(value)


def copy_case(name: str) -> Path:
    target = Path(__file__).parent / name
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(BASE, target)
    return target


def reseal_manifest(root: Path, updates=None) -> None:
    path = root / "evidence-manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if updates:
        manifest.update(updates)
    for name in manifest["artifacts"]:
        raw = (root / name).read_bytes()
        manifest["artifacts"][name] = {
            "sha256": validator._sha256(raw),
            "size": len(raw),
        }
    identity = {
        "schema": manifest["schema"],
        "run_id": manifest["run_id"],
        "artifacts": manifest["artifacts"],
    }
    manifest["record_sha256"] = validator._sha256(
        validator._canonical_json_bytes(identity)
    )
    body = dict(manifest)
    body.pop("manifest_sha256", None)
    manifest["manifest_sha256"] = validator._sha256(
        validator._canonical_json_bytes(body)
    )
    path.write_bytes(pretty(manifest))


def replay_summary(name: str, root: Path) -> None:
    try:
        payload, exit_code = replayer.replay_record(root)
        print(json.dumps({
            "case": name,
            "exit": exit_code,
            "status": payload.get("replay_status"),
            "integrity": payload.get("record_integrity_status"),
            "reexecution": payload.get("reexecution_status"),
            "reasons": payload.get("reexecution_reasons", []),
        }, ensure_ascii=False, sort_keys=True))
    except replayer.ReplayError as error:
        print(json.dumps({
            "case": name,
            "exit": 1,
            "status": "FAIL",
            "error_code": error.code,
        }, ensure_ascii=False, sort_keys=True))


extra = copy_case("mut-extra")
(extra / "unbound.txt").write_text("extra", encoding="utf-8")
replay_summary("extra_artifact", extra)

missing = copy_case("mut-missing")
(missing / "stderr.txt").unlink()
replay_summary("missing_artifact", missing)

duplicate = copy_case("mut-duplicate")
invocation_path = duplicate / "invocation-request.json"
raw = invocation_path.read_bytes()
invocation_path.write_bytes(b'{"schema":"duplicate",' + raw.lstrip()[1:])
reseal_manifest(duplicate)
replay_summary("duplicate_json_key", duplicate)


def rewrite_invocation(root: Path, mutate) -> None:
    invocation_path = root / "invocation-request.json"
    invocation = json.loads(invocation_path.read_text(encoding="utf-8"))
    mutate(invocation)
    body = dict(invocation)
    body.pop("invocation_sha256")
    body.pop("run_id")
    invocation_sha = validator._sha256(validator._canonical_json_bytes(body))
    run_id = f"hvr3-{invocation_sha}"
    invocation["invocation_sha256"] = invocation_sha
    invocation["run_id"] = run_id
    invocation_path.write_bytes(pretty(invocation))
    execution_path = root / "execution-record.json"
    execution = json.loads(execution_path.read_text(encoding="utf-8"))
    execution["run_id"] = run_id
    execution_path.write_bytes(pretty(execution))
    reseal_manifest(root, {
        "run_id": run_id,
        "invocation_request_sha256": invocation_sha,
    })


unknown_invocation = copy_case("mut-unknown-invocation")
rewrite_invocation(
    unknown_invocation,
    lambda value: value["arguments"].update({"hidden_override": True}),
)
replay_summary("unknown_invocation_field", unknown_invocation)

format_tamper = copy_case("mut-format")
rewrite_invocation(
    format_tamper,
    lambda value: value["arguments"].update({"document_format": "tex"}),
)
replay_summary("coordinated_format_tamper", format_tamper)

unknown_result = copy_case("mut-unknown-result")
result_path = unknown_result / "validation-result.json"
result = json.loads(result_path.read_text(encoding="utf-8"))
result["unexpected_result_field"] = {"accepted": True}
result_raw = pretty(result)
result_path.write_bytes(result_raw)
(unknown_result / "rendered-output.txt").write_bytes(result_raw)
execution_path = unknown_result / "execution-record.json"
execution = json.loads(execution_path.read_text(encoding="utf-8"))
execution["rendered_stdout_sha256"] = validator._sha256(result_raw)
execution_path.write_bytes(pretty(execution))
reseal_manifest(unknown_result)
replay_summary("unknown_result_field", unknown_result)

manifest, artifacts = replayer._load_record(BASE)
invocation = replayer._validate_invocation(manifest, artifacts)
changed_policy = copy.deepcopy(invocation["policy_hashes"])
changed_policy["validator_sha256"] = "0" * 64
with mock.patch.object(replayer, "_current_policy_hashes", return_value=changed_policy):
    payload, exit_code = replayer.replay_record(BASE)
print(json.dumps({
    "case": "policy_drift",
    "exit": exit_code,
    "status": payload.get("replay_status"),
    "integrity": payload.get("record_integrity_status"),
    "reexecution": payload.get("reexecution_status"),
    "reasons": payload.get("reexecution_reasons", []),
}, ensure_ascii=False, sort_keys=True))
