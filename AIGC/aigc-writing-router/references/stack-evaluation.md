# AIGC 组合级评测

## 1. 评测对象

组合级评测不回答“这是不是人写的”，而是回答四个可分离的问题：

1. 当前候选是否来自已冻结源稿；
2. 场景负责人、内容负责人和编辑器是否都留下本轮证据；
3. 数字、公式、引用、格式和语义保护报告是否对应当前候选；
4. 若声称人工更偏好该候选，盲评是否覆盖当前源稿与候选，且是否另有明确人工裁决。

检测百分比、所谓 human score、困惑度或单一文风分数不得进入放行清单。

## 2. 三种非失败状态

| 状态 | 含义 | 允许声称 |
| --- | --- | --- |
| `MECHANICAL_PASS_HUMAN_PENDING` | 责任链、文件哈希和候选保护均闭合，但尚未完成人工裁决 | 机械契约通过，待人评 |
| `HUMAN_EVALUATED_PASS` | 机械门通过，锁定的 v2 盲评由 merge report 绑定至少两份单人 CSV，每个 pair-dimension 有两张有效真人票和严格多数，并有明确人工接受记录 | 本轮可见段落中观察到人工偏好 |
| `SOURCE_RETAINED` | 机械门完成后人工决定不采用候选 | 源稿被保留 |

这些状态均不证明人类作者身份、外部检测表现或学术正确性。`FAIL` 表示文件、职责、证据或结论边界至少有一项不闭合。

## 3. 角色证据

每个内容阶段使用 `aigc-stage-evidence/v1` 包装本轮真实产物。推荐让准备器自动计算哈希：

```powershell
python scripts/prepare_stack_evaluation.py stage --provider deai-modeling-writing --source source.tex --candidate candidate.tex --artifact math-gate.json --output model-owner.json
```

生成的结构为：

```json
{
  "schema": "aigc-stage-evidence/v1",
  "provider": "deai-modeling-writing",
  "status": "pass",
  "source_sha256": "<source sha256>",
  "output_sha256": "<candidate sha256>",
  "artifacts": [
    {"path": "math-gate.json", "sha256": "<artifact sha256>"}
  ]
}
```

`artifacts` 必须指向本轮实际报告、台账或门结果，不能用空白文件代替。编辑器阶段由统一适配器产生的 `candidate-verification.json` 证明；该报告必须锁定同一源稿和候选，并保留 `human_review_required=true`。

## 4. 评测清单

```json
{
  "schema": "aigc-stack-evaluation/v1",
  "scene": {
    "document_type": "mcm",
    "intent": "rewrite",
    "document_format": "tex",
    "scope": "document"
  },
  "source": {"path": "source.tex", "sha256": "<sha256>"},
  "baseline_id": "source",
  "candidate": {
    "path": "candidate.tex",
    "sha256": "<sha256>",
    "id": "H1",
    "provider": "humanize-academic-chinese"
  },
  "stage_evidence": [
    {"path": "scene-owner.json", "sha256": "<sha256>"},
    {"path": "genre-owner.json", "sha256": "<sha256>"},
    {"path": "model-owner.json", "sha256": "<sha256>"}
  ],
  "candidate_verification": {
    "path": "candidate-verification.json",
    "sha256": "<sha256>"
  },
  "human_decision": {"status": "pending"},
  "claims": ["mechanical_fidelity", "role_chain_complete"]
}
```

推荐用准备器生成并立即自审清单：

```powershell
python scripts/prepare_stack_evaluation.py manifest --document-type mcm --document-format tex --source source.tex --candidate candidate.tex --candidate-id H1 --provider humanize-academic-chinese --candidate-verification candidate-verification.json --stage-evidence scene-owner.json --stage-evidence genre-owner.json --stage-evidence model-owner.json --output evaluation.json
```

也可单独复审已生成的清单：

```powershell
python scripts/run_stack_evaluation.py evaluation.json --format text
```

人工接受时加入 `blind_score` 的路径与哈希，把 `human_decision.status` 改为 `accepted`，记录评审者和具体理由。盲评报告必须是 v2，含有效覆盖、严格多数、一致率和 merge report；组合审计会重新核对 merge report 的每个单人输入。只有盲评报告确实显示当前候选在 `naturalness` 上获得更多人工选择时，才可加入 `human_preference_observed`。脚本不会替人选稿，只检查该声明是否有本轮证据。

## 5. 角色契约

`role-contracts.json` 是 `stack-registry.json` 的职责覆盖层。它逐包规定：

- 可进入的场景；
- 必须实现的离线接口；
- 完整交付物；
- 完成证据；
- 失败回退；
- 不得声称的结论。

修改任何包、入口或场景后先运行：

```powershell
python scripts/audit_role_contracts.py --format text
python scripts/test_role_contracts.py
```

前者检查 21 个目录、全部可路由入口和 11 类场景的静态闭合；后者实际执行所有声明接口，并对每个候选接口做保护项漂移负例。
