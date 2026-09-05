# Paired-Quality Clearance Contract

## 目录

- [边界](#边界)
- [当前实现](#当前实现)
- [Challenge](#challenge)
- [Response](#response)
- [验签门](#验签门)
- [信任根](#信任根)
- [失败语义](#失败语义)
- [持久化](#持久化)
- [测试矩阵](#测试矩阵)

## 边界

该文件定义“外部成对质量复核”的接入合同。普通 `validate_humanize_output.py` 和
`finalize_humanize_long_document.py` 仍不直接消费 clearance，正常 `REWRITE/NO_CHANGE` 保持
`PENDING_EXTERNAL_REVIEW -> REVIEW/2`。安装版现有独立 verifier，可以审计外部 challenge、JWS response、
keyset、anchor 和当前 artifact；仓库仍没有真实外部审批服务、受保护私钥或可直接信任的生产 anchor。

`VERIFIED_HUMAN` 或 `paired_quality_clearance_granted=true` 只能由代理无法访问私钥的外部服务产生。
仓库内的 JSON、测试私钥、调用方标签、重算 SHA、`HUMAN` 参数和本地 keyset 都不是信任根。验签依赖
缺失、keyset 未锚定或 challenge 缺失时，最多返回“密码学检查通过但未获信任”的 `REVIEW/2`。

## 当前实现

安装版审计入口：

```powershell
python "$skillRoot\scripts\verify_humanize_paired_quality_response.py" `
  --request <paired-quality-review-request.json> `
  --challenge <challenge.json> `
  --response <response.jws> `
  --review-record <review-record.json> `
  --before <before.md> --after <after.md> `
  --keyset <external-keyset.json> `
  --trust-anchor <anchor.json> `
  --format json
```

普通 caller 传入 `--trust-anchor` 只提供诊断材料，不产生信任。当前普通 CLI 无论 POSIX 还是 Windows
均不具备授予 clearance 的 launcher/ACL 边界：自建文件、`chmod 600`、当前用户拥有的 anchor、环境变量
或命令参数都不能成为 `EXTERNALLY_ANCHORED`。独立 launcher 必须在安装版之外证明 root/管理员 ACL、父进程
固定入口和不可伪造的 trust epoch，再接入专用授权路径；在此之前 verifier 只返回密码学/成对质量的局部
`PASS` 与总状态 `REVIEW/2`，不产生 clearance。

当前 verifier 已实现：严格 JWS/JSON/base64url、Ed25519、challenge/request/artifact/review-contract 绑定、
精确 change target、9 个质量维度、review record 字节绑定与具体理由门、时间窗、key 生命周期、撤销、
trust epoch，以及 grant 前对 request/challenge/response/keyset/anchor/review record 和正文的全链字节重读。
每个 request hunk 必须逐字段匹配当前 before/after 的 `difflib` 结果、行范围、内容 hash 和
content-bound `change_id`；固定 review contract、limitations 与 validation context 的额外字段会被拒绝。
policy hash 会按当前 validator、保护检查器、scanner、lexicon、report extractor、运行时、成对验签器
和本合同/参考文件重算；旧 request 缺少验签器或合同 hash 时固定拒绝，漂移在签名检查前或验证期间都固定拒绝。
request 必须完整、无额外键地携带 validator、invariant checker、scanner、lexicon、report extractor 和
Python/Unicode runtime 六项 64-hex policy hash；空对象、缺项、额外项或非法 hash 都在验签前 `FAIL/1`。
`REPORT_SELECTION` request 还要把 scope 的路径无关语义 SHA、report/source SHA、fragment 数和精确
editable ranges 纳入 `validation_context`，使外部 clearance 不能跨 detector selection 复用。
调用方提供的 `--redemption-ledger` 现在只作为诊断输入，绝不写入或授予 clearance；同一 response 的重复
调用在不同 caller 路径上结果一致，避免通过替换/删除 ledger 绕过一次性消费。真正的 redemption ledger
必须由受保护 launcher 固定位置、绑定 trust epoch 并在不可删除的持久边界中原子消费。它仍没有实现在线
远程 keyset refresh、外部服务本身、ACL/launcher 证明或把 clearance 原子提交到 long-document 发布事务。即使 paired-quality
验签局部返回 `verification_status=PASS`、`paired_quality_gate_status=PASS`，总 `delivery_gate_status` 仍是 `REVIEW`，
总 `status`/退出码仍为 `REVIEW/2`，
学术正确性、作者身份、Voice、结构语义和 second-pass 仍保持独立状态。

## Challenge

v1 schema 名保持不变，但缺少上述完整 policy surface 的旧 request 不再具备验签资格。需要防离线重放时，
外部服务先生成一个独立 challenge：

```json
{
  "schema": "humanize-paired-quality-clearance-challenge/v1",
  "challenge_id": "32-byte-base64url",
  "request_sha256": "64-hex",
  "subject_binding": {
    "kind": "SINGLE_DOCUMENT",
    "before_sha256": "64-hex",
    "after_sha256": "64-hex",
    "scene": "RESEARCH",
    "document_scope": "DOCUMENT",
    "snapshot_id": "optional-frozen-id",
    "unit_id": "optional-unit-id",
    "chunk_binding_sha256": "optional-64-hex",
    "voice_binding_sha256": "optional-64-hex"
  },
  "issued_at": 1784300000,
  "expires_at": 1784386400,
  "challenge_sha256": "sha256(canonical body without this field)"
}
```

`challenge_id` 必须使用 `secrets.token_bytes(32)` 生成并在首次生成后冻结。`request_sha256`、before/after
SHA、scene、scope、snapshot/unit/chunk/Voice 任何一项漂移都必须生成新 challenge。challenge 的 TTL
不得超过 trust policy 上限；`issued_at` 不得晚于当前时间加 clock skew，`expires_at` 必须晚于当前时间减
clock skew。没有 challenge 的 v1 response 不能阻止完整离线重放。

## Response

Response 使用 JWS Compact；签名输入是外部服务产生的原始 ASCII 三段，不得由本地工具重排。protected
header 只允许以下闭集：

```json
{"alg":"EdDSA","kid":"pq-2026-07","typ":"humanize-paired-quality-clearance+jws"}
```

签名 payload 的 required keys 为：

```json
{
  "schema": "humanize-paired-quality-clearance-response/v1",
  "iss": "configured-review-service",
  "aud": "humanize-academic-chinese/paired-quality",
  "response_id": "32-byte-base64url",
  "challenge_id": "exact-challenge-id",
  "challenge_sha256": "exact-challenge-sha256",
  "request_sha256": "exact-request-sha256",
  "review_contract_sha256": "sha256(canonical request.review_contract)",
  "review_items": [],
  "overall_verdict": "CLEAR",
  "review_record_sha256": "64-hex",
  "issued_at": 1784300100,
  "not_before": 1784300100,
  "expires_at": 1784386500,
  "trust_epoch": 17
}
```

Response 不得携带 `jwk`、`x5c`、`jku`、`x5u`、`public_key`、路径或任意未知字段。`review_items` 的
target 集合必须与 request 的全部 `change_id` 精确相等；重复、缺失、额外 target 都拒绝。每个 item
包含 `target`、`verdict` 和完整的 9 个 quality dimensions：

```text
actionable_pathology_remaining
no_change_is_best_available_decision
problem_span_binding
independent_reading_benefit
subject_and_modifier_alignment
verb_object_collocation
logical_relation_preservation
information_density_and_rhythm
author_voice_non_regression
```

只有每项 `verdict=ACCEPT` 且每个 dimension=`PASS`、`overall_verdict=CLEAR` 时才可能形成 clearance。
任何 `REVISE`、`REVERT`、部分覆盖或空泛理由都只能形成待审反馈，不能和其他 response 拼接。`NO_CHANGE`
必须使用唯一合成 target `NO_CHANGE`，不能通过空数组真空放行。

`review_record_sha256` 必须绑定单独的严格 JSON 工件，不能只填一个 64 位占位字符串：

```json
{
  "schema": "humanize-paired-quality-review-record/v1",
  "request_sha256": "exact-request-sha256",
  "challenge_sha256": "exact-challenge-sha256",
  "response_id": "exact-response-id",
  "items": [
    {
      "target": "exact-change-id-or-NO_CHANGE",
      "problem_span": "可定位的问题跨度",
      "reading_effect": "该跨度造成的具体读感后果",
      "decision_rationale": "接受、回退或维持原文的具体理由"
    }
  ]
}
```

record target 集合与 response/request 必须精确相等。缺 record 为 `REVIEW/2`，字节哈希、request、challenge、
response 或 target 错绑为 `FAIL/1`；“已人工审核、符合要求、更自然、没有问题”等空泛理由只能
`REVIEW/2`，不得因签名有效而放行。

## 验签门

按顺序执行：

1. 严格解析 JWS，拒绝空算法、算法降级、非 canonical base64url、重复 JSON 键、NaN/Infinity 和尾随数据。
2. 读取独立 keyset；`kid` 精确查找，算法必须为固定 Ed25519/EdDSA，状态、有效期和撤销状态必须通过。
3. 验证签名，再验证 response/challenge/request/artifact/review-contract 的 SHA 绑定。
4. 验证 `issued_at`、`not_before`、`expires_at`、TTL、challenge 有效期和 `trust_epoch`。
5. 精确比较 change target 集合、9 个 dimensions、verdict 和 overall verdict。
6. 重新读取当前 artifact，在发布前重新计算 request/challenge；任一漂移都使 response 失效。
7. 只有外部 keyset 信任根、challenge、签名、逐 change 质量结果和当前 artifact 全通过，才可在本地派生
   `paired_quality_clearance_granted=true`。结构语义、学术正确性、Voice 和 second-pass 仍是独立门。

本地仓库 keyset 默认 `trust_root_status=UNTRUSTED_LOCAL_KEYSET`。即使密码学签名有效，也只能返回
`cryptographic_signature_status=PASS`、`quality_clearance_granted=false`、`REVIEW/2`。keyset 必须由受保护
安装目录、管理员 ACL 或独立可信 launcher 固定；不能把 repo 内 policy 的 `enabled=true` 当作根信任。

## 信任根

独立 keyset 至少绑定 `sequence`、`issued_at`、`next_update`、issuer、audience、key `kid/alg/public_key`
、`not_before/not_after/status/usages` 和 revocations。使用受保护的最高 sequence 防止回滚；撤销至少支持
`ALL_SIGNATURES` 与 `ISSUED_AT_OR_AFTER`。keyset 过期、刷新中断、未知 key 或 sequence 回退都 fail closed。

离线 response 的首次消费必须写入 ACL 保护的 response/challenge 消费账本；challenge nonce 只能阻止跨
challenge 重放。当前 CLI 的 ledger 是严格 JSON、symlink-safe、锁文件互斥和原子 rename；同一
`response_id` 的第二次消费固定 `REVIEW/2`，不同 request/artifact 绑定的 collision 固定 `FAIL/1`。
外部 launcher 仍须在可信边界保护该 ledger；本地 caller 自行创建的 ledger 只能视为本地实现证据。

## 失败语义

| 条件 | 状态 |
|---|---|
| 机械门非 PASS | 原状态保持；response 永远不能升级 |
| 缺 challenge/未签名 response | `REVIEW/2`，`quality_clearance_granted=false` |
| 本地 keyset 无外部锚定 | `REVIEW/2`，即使签名密码学有效 |
| 签名、schema、绑定、时间窗或撤销失败 | `FAIL/1`，不发布 |
| 部分 change、REVISE/REVERT 或维度不全 | `REVIEW/2`，不清除门 |
| 验签后 artifact 漂移 | `FAIL/1`，回滚并丢弃本次 response 路径 |
| 结构语义/学术/Voice/second-pass pending | paired-quality 不得覆盖其他门 |

## 持久化

request、challenge、response 和 validation result 必须是不可变记录。建议使用同卷 staging 后原子 rename：

```text
validation/_records/<run-id>/
  artifacts/before.bin
  artifacts/after.bin
  invocation-request.json
  validation-response.json
  paired-quality-review-request.json
  challenge.json
  response.jws
  manifest.json
  commit.json
```

manifest 绑定每个文件的字节 SHA、request/challenge/response SHA、policy hash 和退出码；同 run-id 且字节
完全相同才允许幂等重放，冲突直接 `FAIL/1`。未验签 response 可以留作 `UNTRUSTED` 诊断事件，但不能覆盖
旧 request、不能进入 `accepted/`，也不能写进 `rendered/`。

## 测试矩阵

至少覆盖：本地自签并携带公钥、替换 repo keyset、旧 response 配新 challenge、before/after 单字节/BOM/EOL
漂移、scene/scope/unit/Voice 漂移、漏 change/额外 change/重复 target、NO_CHANGE 空 target、future/expired/
超长 TTL、unknown/retired/revoked kid、`alg=none/HS256/ES256`、未知键/重复键/NaN、路径注入和 symlink/
junction、response 冲突、验签后 artifact 修改、keyset rollback、消费账本重放、依赖缺失和断电式 commit。

标准库没有通用公钥验签 API。优先使用已安装的 `cryptography` Ed25519；依赖缺失必须返回 `REVIEW/2`，
不得降级到 HMAC、共享密钥、`openssl` 任意命令或调用方自述。
