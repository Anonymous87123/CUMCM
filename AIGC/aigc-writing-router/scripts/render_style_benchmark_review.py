#!/usr/bin/env python3
"""Render and audit a provenance-free offline page for blind writing review.

Public interface:
    python render_style_benchmark_review.py render evaluation-packet.json \
        --output review.html [--ratings-template ratings-template.csv] \
        [--bundle review-bundle.json]
    python render_style_benchmark_review.py audit review-bundle.json --format text|json
"""

from __future__ import annotations

import argparse
import base64
import csv
import html
import json
from pathlib import Path

from adapter_core import sha256_file, write_json


PACKET_SCHEMA = "aigc-blind-packet/v1"
BUNDLE_SCHEMA = "aigc-blind-review-bundle/v1"
DIMENSIONS = (
    "naturalness",
    "judgment_trajectory",
    "specificity",
    "content_density",
    "semantic_fidelity",
)
CHOICES = ("A", "B", "TIE", "SKIP")
CSV_FIELDS = ("pair_id", "rater_id", "rater_kind", *DIMENSIONS, "notes")
ROOT_FIELDS = {"schema", "instructions", "dimensions", "choices", "pairs"}
PAIR_FIELDS = {"pair_id", "A", "B"}


def load_packet(path: Path) -> dict:
    path = path.resolve()
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict) or payload.get("schema") != PACKET_SCHEMA:
        raise ValueError(f"expected schema {PACKET_SCHEMA}")
    extras = set(payload) - ROOT_FIELDS
    if extras:
        raise ValueError(f"packet contains non-review fields: {sorted(extras)}")
    if tuple(payload.get("dimensions", [])) != DIMENSIONS:
        raise ValueError("packet dimensions are missing or out of order")
    if tuple(payload.get("choices", [])) != CHOICES:
        raise ValueError("packet choices are missing or out of order")
    pairs = payload.get("pairs")
    if not isinstance(pairs, list) or not pairs:
        raise ValueError("packet must contain at least one pair")
    seen: set[str] = set()
    for index, pair in enumerate(pairs, start=1):
        if not isinstance(pair, dict) or set(pair) != PAIR_FIELDS:
            raise ValueError(f"pair {index} contains missing or non-review fields")
        pair_id = str(pair.get("pair_id", "")).strip()
        if not pair_id or pair_id in seen:
            raise ValueError(f"pair {index} has an empty or duplicate id")
        if not str(pair.get("A", "")).strip() or not str(pair.get("B", "")).strip():
            raise ValueError(f"pair {pair_id} has an empty visible passage")
        seen.add(pair_id)
    return payload


def _locked_relative(path: Path, parent: Path) -> dict:
    path = path.resolve()
    return {
        "path": path.relative_to(parent.resolve()).as_posix(),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }


def _write_template(packet: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for pair in packet["pairs"]:
            writer.writerow({"pair_id": pair["pair_id"]})


def _validate_template(packet: dict, path: Path) -> None:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != CSV_FIELDS:
            raise ValueError("ratings template header does not match the scoring interface")
        rows = list(reader)
    ids = [str(row.get("pair_id", "")).strip() for row in rows]
    expected = [str(pair["pair_id"]) for pair in packet["pairs"]]
    if ids != expected:
        raise ValueError("ratings template pair order does not match the packet")
    for row in rows:
        if any(str(row.get(field, "")).strip() for field in CSV_FIELDS if field != "pair_id"):
            raise ValueError("ratings template contains pre-filled reviewer data")


def _page(packet: dict, packet_hash: str) -> str:
    compact = json.dumps(packet, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    payload_b64 = base64.b64encode(compact).decode("ascii")
    escaped_hash = html.escape(packet_hash, quote=True)
    return f'''<!doctype html>
<html lang="zh-CN" data-packet-sha256="{escaped_hash}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:,">
  <title>匿名文风盲评</title>
  <style>
    :root {{ color-scheme: light; --ink:#18211d; --muted:#5c6862; --line:#ccd3cf;
      --paper:#f5f7f5; --surface:#fff; --accent:#176b4d; --warn:#a33b2b; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--paper); color:var(--ink); font:15px/1.65 system-ui,
      "Microsoft YaHei", sans-serif; letter-spacing:0; }}
    header, main, footer {{ width:min(1180px, calc(100% - 32px)); margin-inline:auto; }}
    header {{ padding:28px 0 18px; border-bottom:1px solid var(--line); }}
    h1 {{ margin:0 0 8px; font-size:24px; }}
    h2 {{ margin:0; font-size:18px; }}
    p {{ margin:6px 0; }}
    .muted {{ color:var(--muted); }}
    .toolbar {{ display:flex; gap:16px; align-items:end; flex-wrap:wrap; padding:18px 0; }}
    label.control {{ display:grid; gap:5px; min-width:min(360px,100%); font-weight:600; }}
    input[type=text] {{ min-height:40px; padding:8px 10px; border:1px solid #9ba8a1;
      border-radius:4px; background:#fff; font:inherit; }}
    button {{ min-height:40px; padding:8px 14px; border:1px solid var(--accent); border-radius:4px;
      background:var(--accent); color:#fff; font:inherit; font-weight:700; cursor:pointer; }}
    button.secondary {{ background:#fff; color:var(--accent); }}
    button:disabled {{ opacity:.5; cursor:not-allowed; }}
    #status {{ margin-left:auto; font-variant-numeric:tabular-nums; }}
    .pair {{ margin:0 0 22px; padding:20px; border:1px solid var(--line); border-radius:6px;
      background:var(--surface); }}
    .passages {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; margin:14px 0 18px; }}
    .passage {{ min-width:0; padding:14px; border-left:4px solid #7b8b83; background:#f8faf8; }}
    .passage h3 {{ margin:0 0 8px; font-size:16px; }}
    .passage-text {{ margin:0; white-space:pre-wrap; overflow-wrap:anywhere; }}
    fieldset {{ display:grid; grid-template-columns:minmax(190px,1fr) repeat(4,minmax(68px,auto));
      gap:8px 12px; align-items:center; margin:8px 0; padding:10px 12px; border:1px solid #d9dedb;
      border-radius:4px; }}
    fieldset.missing {{ border-color:var(--warn); background:#fff8f6; }}
    legend {{ position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); }}
    .dimension strong, .dimension small {{ display:block; }}
    .dimension small {{ color:var(--muted); }}
    .choice {{ display:flex; align-items:center; gap:5px; white-space:nowrap; }}
    .notes {{ display:grid; gap:5px; margin-top:12px; font-weight:600; }}
    textarea {{ width:100%; min-height:72px; resize:vertical; border:1px solid #aab4af;
      border-radius:4px; padding:8px 10px; font:inherit; }}
    .error {{ color:var(--warn); font-weight:700; }}
    footer {{ padding:10px 0 28px; color:var(--muted); font-size:13px; overflow-wrap:anywhere; }}
    @media (max-width:760px) {{
      .passages {{ grid-template-columns:1fr; }}
      fieldset {{ grid-template-columns:1fr 1fr 1fr 1fr; }}
      .dimension {{ grid-column:1/-1; }}
      #status {{ width:100%; margin-left:0; }}
    }}
  </style>
</head>
<body>
<header>
  <h1>匿名文风盲评</h1>
  <p>只比较页面中可见的两段文字，不推测作者身份，也不使用 AI 检测器。</p>
  <p class="muted">每个维度可选 A、B、持平或跳过。跳过不计正式票；两人结论相反时保留原表，再追加一名独立评审。</p>
</header>
<main>
  <div class="toolbar">
    <label class="control">评审者编号
      <input id="rater" type="text" maxlength="80" autocomplete="off" placeholder="例如 R01">
    </label>
    <button id="export" type="button">导出评分 CSV</button>
    <button id="clear" type="button" class="secondary">清空本页记录</button>
    <div id="status" aria-live="polite"></div>
  </div>
  <div id="message" aria-live="assertive"></div>
  <div id="pairs"></div>
</main>
<footer>匿名包 SHA-256：<span id="packet-hash">{escaped_hash}</span></footer>
<script>
"use strict";
const packetHash = "{escaped_hash}";
const packetBytes = Uint8Array.from(atob("{payload_b64}"), c => c.charCodeAt(0));
const packet = JSON.parse(new TextDecoder("utf-8").decode(packetBytes));
const dimensions = ["naturalness","judgment_trajectory","specificity","content_density","semantic_fidelity"];
const labels = {{
  naturalness:["自然度","是否像有目的的学术叙述，而非可互换套句"],
  judgment_trajectory:["判断过程","是否看得出由现象、困难或比较走向处理方式"],
  specificity:["具体性","对象、变量、阈值、条件和变化是否写清"],
  content_density:["内容密度","是否少重复、不跳步，每段承担明确作用"],
  semantic_fidelity:["语义忠实度","事实、范围、限定和数学方向是否保持"]
}};
const choiceLabels = {{A:"A",B:"B",TIE:"持平",SKIP:"跳过"}};
const stateKey = "aigc-blind-review:" + packetHash;
let state = {{rater:"", answers:{{}}, notes:{{}}}};
try {{ state = Object.assign(state, JSON.parse(localStorage.getItem(stateKey) || "{{}}")); }} catch (_) {{}}
const rater = document.getElementById("rater");
const pairsNode = document.getElementById("pairs");
const statusNode = document.getElementById("status");
const messageNode = document.getElementById("message");
rater.value = state.rater || "";
function save() {{ state.rater = rater.value; localStorage.setItem(stateKey, JSON.stringify(state)); updateStatus(); }}
function complete(pair) {{ return dimensions.every(d => state.answers[pair.pair_id]?.[d]); }}
function updateStatus() {{
  const done = packet.pairs.filter(complete).length;
  statusNode.textContent = `已完成 ${{done}} / ${{packet.pairs.length}} 对`;
}}
function element(tag, className, text) {{
  const node = document.createElement(tag); if (className) node.className = className;
  if (text !== undefined) node.textContent = text; return node;
}}
packet.pairs.forEach((pair, pairIndex) => {{
  state.answers[pair.pair_id] ||= {{}};
  const section = element("section", "pair"); section.dataset.pairId = pair.pair_id;
  section.append(element("h2", "", `第 ${{pairIndex + 1}} 对 · ${{pair.pair_id}}`));
  const passages = element("div", "passages");
  ["A","B"].forEach(side => {{
    const article = element("article", "passage"); article.append(element("h3", "", `文本 ${{side}}`));
    article.append(element("p", "passage-text", pair[side])); passages.append(article);
  }});
  section.append(passages);
  dimensions.forEach((dimension, dimIndex) => {{
    const fieldset = document.createElement("fieldset"); fieldset.dataset.dimension = dimension;
    fieldset.append(element("legend", "", labels[dimension][0]));
    const title = element("div", "dimension"); title.append(element("strong", "", labels[dimension][0]));
    title.append(element("small", "", labels[dimension][1])); fieldset.append(title);
    ["A","B","TIE","SKIP"].forEach(choice => {{
      const label = element("label", "choice"); const input = document.createElement("input");
      input.type = "radio"; input.name = `p${{pairIndex}}-d${{dimIndex}}`; input.value = choice;
      input.checked = state.answers[pair.pair_id][dimension] === choice;
      input.addEventListener("change", () => {{ state.answers[pair.pair_id][dimension] = choice;
        fieldset.classList.remove("missing"); save(); }});
      label.append(input, document.createTextNode(choiceLabels[choice])); fieldset.append(label);
    }});
    section.append(fieldset);
  }});
  const notesLabel = element("label", "notes", "备注（可选）"); const notes = document.createElement("textarea");
  notes.maxLength = 2000; notes.value = state.notes[pair.pair_id] || "";
  notes.addEventListener("input", () => {{ state.notes[pair.pair_id] = notes.value; save(); }});
  notesLabel.append(notes); section.append(notesLabel); pairsNode.append(section);
}});
rater.addEventListener("input", save);
function csvCell(value) {{ const text = String(value ?? ""); return /[",\\r\\n]/.test(text)
  ? `"${{text.replaceAll('"','""')}}"` : text; }}
document.getElementById("export").addEventListener("click", () => {{
  messageNode.textContent = ""; messageNode.className = "";
  const reviewer = rater.value.trim(); const missing = [];
  document.querySelectorAll("fieldset").forEach(node => node.classList.remove("missing"));
  packet.pairs.forEach(pair => dimensions.forEach(d => {{ if (!state.answers[pair.pair_id]?.[d]) {{
    missing.push([pair.pair_id,d]); document.querySelector(`.pair[data-pair-id="${{CSS.escape(pair.pair_id)}}"] fieldset[data-dimension="${{d}}"]`).classList.add("missing"); }} }}));
  if (!reviewer || missing.length) {{
    messageNode.className = "error";
    messageNode.textContent = !reviewer ? "请填写评审者编号。" : `还有 ${{missing.length}} 个维度未选择。`;
    if (missing.length) document.querySelector("fieldset.missing")?.scrollIntoView({{behavior:"smooth",block:"center"}});
    return;
  }}
  const header = ["pair_id","rater_id","rater_kind",...dimensions,"notes"];
  const lines = [header.join(",")];
  packet.pairs.forEach(pair => {{ const row = [pair.pair_id,reviewer,"human",
    ...dimensions.map(d => state.answers[pair.pair_id][d]),state.notes[pair.pair_id] || ""];
    lines.push(row.map(csvCell).join(",")); }});
  const blob = new Blob(["\\uFEFF" + lines.join("\\r\\n") + "\\r\\n"], {{type:"text/csv;charset=utf-8"}});
  const link = document.createElement("a"); link.href = URL.createObjectURL(blob);
  link.download = `ratings-${{reviewer.replace(/[^A-Za-z0-9._-]+/g,"-") || "reviewer"}}-${{packetHash.slice(0,8)}}.csv`;
  link.click(); setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  messageNode.textContent = "评分表已导出。请不要把本页记录交给另一名评审参考。";
}});
document.getElementById("clear").addEventListener("click", () => {{
  if (!confirm("确认清空本页保存的评审编号、选择和备注？")) return;
  localStorage.removeItem(stateKey); location.reload();
}});
updateStatus();
</script>
</body>
</html>
'''


def render_review(
    packet_path: Path,
    output_path: Path,
    ratings_template: Path | None = None,
    bundle_path: Path | None = None,
) -> dict:
    packet_path = packet_path.resolve()
    output_path = output_path.resolve()
    packet = load_packet(packet_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        raise FileExistsError(output_path)
    if ratings_template is None:
        ratings_template = output_path.with_name("ratings-template.csv")
        if not ratings_template.exists():
            _write_template(packet, ratings_template)
    ratings_template = ratings_template.resolve()
    if not ratings_template.is_file():
        raise FileNotFoundError(ratings_template)
    _validate_template(packet, ratings_template)
    packet_hash = sha256_file(packet_path)
    output_path.write_text(_page(packet, packet_hash), encoding="utf-8", newline="\n")
    bundle_path = (bundle_path or output_path.with_name("review-bundle.json")).resolve()
    if bundle_path.exists():
        raise FileExistsError(bundle_path)
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    bundle = {
        "schema": BUNDLE_SCHEMA,
        "state": "READY_FOR_INDEPENDENT_HUMAN_REVIEW",
        "pairs": len(packet["pairs"]),
        "dimensions": list(DIMENSIONS),
        "packet": _locked_relative(packet_path, bundle_path.parent),
        "review_page": _locked_relative(output_path, bundle_path.parent),
        "ratings_template": _locked_relative(ratings_template, bundle_path.parent),
        "claims": {
            "contains_private_key": False,
            "contains_pair_mapping": False,
            "contains_provider_identity": False,
            "human_rating_completed": False,
        },
    }
    write_json(bundle_path, bundle)
    return {
        "schema": "aigc-blind-review-render/v1",
        "status": "pass",
        "pairs": len(packet["pairs"]),
        "packet_sha256": packet_hash,
        "review_page": str(output_path),
        "review_page_sha256": sha256_file(output_path),
        "ratings_template": str(ratings_template),
        "bundle": str(bundle_path),
        "bundle_sha256": sha256_file(bundle_path),
    }


def audit_bundle(bundle_path: Path) -> dict:
    bundle_path = bundle_path.resolve()
    findings: list[dict] = []
    try:
        payload = json.loads(bundle_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        payload = {}
        findings.append({"severity": "error", "code": "REVIEW_BUNDLE_INVALID", "error": str(exc)})
    if payload.get("schema") != BUNDLE_SCHEMA:
        findings.append({"severity": "error", "code": "REVIEW_BUNDLE_SCHEMA_MISMATCH"})
    resolved: dict[str, Path] = {}
    for name in ("packet", "review_page", "ratings_template"):
        record = payload.get(name)
        if not isinstance(record, dict) or not record.get("path") or not record.get("sha256"):
            findings.append({"severity": "error", "code": "REVIEW_LOCK_INVALID", "artifact": name})
            continue
        path = (bundle_path.parent / str(record["path"])).resolve()
        try:
            path.relative_to(bundle_path.parent.resolve())
        except ValueError:
            findings.append({"severity": "error", "code": "REVIEW_PATH_ESCAPES_BUNDLE", "artifact": name})
            continue
        if not path.is_file():
            findings.append({"severity": "error", "code": "REVIEW_FILE_MISSING", "artifact": name})
            continue
        if sha256_file(path) != str(record["sha256"]):
            findings.append({"severity": "error", "code": "REVIEW_FILE_DRIFT", "artifact": name})
            continue
        resolved[name] = path
    packet = None
    if "packet" in resolved:
        try:
            packet = load_packet(resolved["packet"])
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            findings.append({"severity": "error", "code": "REVIEW_PACKET_INVALID", "error": str(exc)})
    if packet is not None and "ratings_template" in resolved:
        try:
            _validate_template(packet, resolved["ratings_template"])
        except ValueError as exc:
            findings.append({"severity": "error", "code": "REVIEW_TEMPLATE_INVALID", "error": str(exc)})
    if packet is not None and "review_page" in resolved:
        page = resolved["review_page"].read_text(encoding="utf-8")
        marker = f'data-packet-sha256="{sha256_file(resolved["packet"])}"'
        if marker not in page:
            findings.append({"severity": "error", "code": "REVIEW_PAGE_PACKET_MISMATCH"})
        if page != _page(packet, sha256_file(resolved["packet"])):
            findings.append({"severity": "error", "code": "REVIEW_PAGE_RENDERER_MISMATCH"})
        if "evaluation-key" in page or "pair-map" in page or "candidate_id" in page:
            findings.append({"severity": "error", "code": "REVIEW_PAGE_PROVENANCE_LEAK"})
    claims = payload.get("claims", {})
    if not isinstance(claims, dict) or any(
        claims.get(name) is not False
        for name in ("contains_private_key", "contains_pair_mapping", "contains_provider_identity", "human_rating_completed")
    ):
        findings.append({"severity": "error", "code": "REVIEW_BUNDLE_CLAIMS_INVALID"})
    errors = sum(item["severity"] == "error" for item in findings)
    return {
        "schema": "aigc-blind-review-audit/v1",
        "status": "pass" if errors == 0 else "fail",
        "errors": errors,
        "warnings": 0,
        "pairs": len(packet.get("pairs", [])) if packet else 0,
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    render_parser = sub.add_parser("render")
    render_parser.add_argument("packet", type=Path)
    render_parser.add_argument("--output", type=Path, required=True)
    render_parser.add_argument("--ratings-template", type=Path)
    render_parser.add_argument("--bundle", type=Path)
    render_parser.add_argument("--format", choices=("text", "json"), default="text")
    audit_parser = sub.add_parser("audit")
    audit_parser.add_argument("bundle", type=Path)
    audit_parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    if args.command == "render":
        report = render_review(args.packet, args.output, args.ratings_template, args.bundle)
        label = "BLIND REVIEW RENDER"
    else:
        report = audit_bundle(args.bundle)
        label = "BLIND REVIEW AUDIT"
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"{label} {report['status'].upper()} pairs={report.get('pairs', 0)}")
        if report.get("review_page"):
            print(f"review_page={report['review_page']}")
            print(f"bundle={report['bundle']}")
        for finding in report.get("findings", []):
            print(f"[{finding['severity'].upper()}] {finding['code']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
