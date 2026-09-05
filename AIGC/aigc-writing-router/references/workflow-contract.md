# AIGC 组合执行契约

## 目录

1. 冻结源与责任
2. 同源候选清单
3. 只读复核器
4. 格式保护
5. 外部工作台
6. 交付状态
7. 统一适配器
8. 长文台账与语义门
9. 人类双盲选择
10. 原生能力证据等级
11. MCM 发布状态机
12. 完整角色证据
13. 组合级评测
14. 未见文本盲测

## 1. 冻结源与责任

每次任务先确定权威文件、文档类型、语言、格式、允许改写的范围和最终质量门。生成候选前计算权威源 SHA-256；候选不得覆盖源文件。

| 责任 | 完整交付物 | 不得降格为 |
| --- | --- | --- |
| 场景/内容责任人 | 论证、证据、结构、模型/结果或教学内容及场景门 | 只给文风标签 |
| 主编辑器 | 按自身完整保护流程生成一个源分支候选 | 禁用词替换器 |
| 独立候选 | 从同一冻结源生成另一个候选 | 接着修改上一候选 |
| 只读复核器 | 完整 audit/analyze 报告和证据位置 | 自动选稿器 |
| 文档工作台 | 快照、映射、Diff、人工操作、历史和导出证据 | 内容权威 |
| 裁决层 | 不变量核对、领域复核和人工选择记录 | 检测分数排序 |

## 2. 同源候选清单

使用 `aigc-candidate-portfolio/v1`：

```json
{
  "schema": "aigc-candidate-portfolio/v1",
  "document_type": "mcm",
  "source": {
    "path": "source.tex",
    "sha256": "<source sha256>"
  },
  "candidates": [
    {
      "id": "H1",
      "provider": "humanize-academic-chinese",
      "input_sha256": "<source sha256>",
      "output_path": "candidate-h.tex",
      "output_sha256": "<candidate sha256>",
      "pass_count": 1,
      "parent_candidate": null,
      "invariant_status": "pass",
      "domain_audit_status": "pass",
      "document_status": "pass"
    }
  ],
  "selection": {
    "accepted": "H1",
    "human_review": "accepted",
    "reason": "保留条件和数值，并把结果对象提前到主句"
  }
}
```

规则：

1. 所有 `input_sha256` 等于冻结源哈希。
2. 所有 `parent_candidate` 为 `null`，`pass_count` 为 1。
3. Baibai 仅允许 `round: 1`。
4. 中文学术最多两个候选：Humanize H 与 Baibai B；英文和一般文本按路由只产生一个显式候选，源稿始终保留。
5. 候选提供者必须属于文档类型允许集合。英文通用、医学英文和一般中英文的新增提供者已写入审计脚本。
6. 只有不变量、领域、文档三门通过且 `human_review=accepted` 才能采用。
7. 选择理由必须写具体收益，不得只写“更像人”或“分数更低”。

运行：

```powershell
python scripts/audit_candidate_portfolio.py <portfolio.json> --format text
```

## 3. 只读复核器

复核器不写权威文件，不加入候选父子链，也不决定 `selection.accepted`。

| 复核器 | 完整输入 | 完整输出 | 限制 |
| --- | --- | --- | --- |
| `patina` | 普通文本；TeX 只能给抽取正文代理 | pattern、anchor、MPS、fidelity audit | 分数只作诊断，不碰 TeX 权威源 |
| `ai-check` | 当前候选与必要上下文 | 逐项信号、原文命中和解释 | 不给作者身份概率，不自动选稿 |
| `humanizer-brandonwise` | 英文普通文本 | CLI pattern/statistical report | 不用于中文或学术正确性 |

复核器报告必须注明输入哈希、模式和是否使用正文代理。任何建议若要进入正文，必须回到冻结源重新形成候选，而不是直接在报告上续写。

## 4. 格式保护

| 格式 | 权威保护项 | 推荐治理 |
| --- | --- | --- |
| TeX | 命令、环境、公式、标签、引用、数字、单位、图表路径、章节层级 | 原生哈希 + 学术保护流程 + 领域审计 + 编译 |
| Markdown | frontmatter、代码块、链接、表格、数学和标题 | 原生哈希 + 场景门 |
| DOCX | 原包、正文映射、样式、关系、图片、批注和导出清单 | FYADR/AI_paper 人工工作台 |
| PDF | 页面不直接改写；先抽取正文或建立标注副本 | 英文可用 AI-content-detector 标注，原 PDF 保留 |
| TXT | 原字节、编码和段落边界 | 原生哈希；长文可交 FYADR |

## 5. 外部工作台

- FYADR：承接长 DOCX/TXT 的完整文档治理，不负责学术论证。
- AI_paper：承接人工写作项目、语法格式、批注、历史和导出；建议逐条采用。
- AI-Cleaner：承接中文诊断和 Diff 实验；输出重新进入候选契约。
- AI-content-detector：承接英文 PDF 句级分析和标注副本；检测提示不是结论。
- GankAIGC：承接部署、账户、BYOK、项目历史或外部反馈实验。
- BypassAIGC：承接旧流程兼容和回归比较。
- ai-humanizer：承接外部黑盒 API 演示；不得处理敏感或权威稿。
- humanize-text：承接翻译链研究基线；不得处理公式、引用或事实密集稿。
- humanize-ai：只在关闭随机 Markov、启用逐项变更轨迹和保护区核验后作为实现实验工作台。
- humanize-main-Tiany：使用重建的本地比较器承接同源候选、保护区核对和 repair 证据；不恢复、不声称恢复缺失的原生成器。

联网工作台使用前还要确认 API key、论文内容、历史记录和上传文件的保存位置。

## 6. 交付状态

普通候选组合沿用 `SOURCE_FROZEN -> CANDIDATES_READY -> HUMAN_REVIEW_PENDING -> ACCEPTED | SOURCE_RETAINED`。正式 MCM 长稿使用更严格的第 11 节状态机。检测百分比、某个文风分数或机械核验通过均不是最终放行状态。

## 7. 统一适配器

每个登记项目必须至少支持一个可离线验证的动作：

- `audit`：对文本作确定性统计与保护区清点；支持原生离线审计器时可显式 `--execute-native`。
- `prepare-candidate`：冻结源、生成保护区代理和原生调用契约；不假装远程模型已经运行。
- `verify-candidate`：核对源哈希、数字、TeX 命令、公式、引用键、标签、代码块和 URL。
- `workbench-plan`：给出真实启动命令、运行时、网络依赖、格式边界、导入与采用规则。

接口命令见 `scripts/run_aigc_adapter.py`。任何联网或 GUI 输出都必须回到 `verify-candidate`，不能因为应用成功导出就视为通过。

## 8. 长文台账与语义门

长篇 TeX 不按一个主文件假定完整。运行 `run_longform_portfolio.py init` 后，递归冻结 `\input`/`\include` 文件，保留源快照，并按章节记录行号、段落、公式、标签、引用和哈希。每个候选必须从同一冻结源独立分叉一次，并提供同构文件树；缺章节、加章节、直接复用权威章节或任一章节漂移都阻断采用。

`verify-candidate` 对 `.tex` 自动接入 CUMCM 的 `audit_rewrite_contract.py`。数字、公式、TeX 键、标题层级、目标方向和约束方向是硬错误；否定、因果标记和结论强度变化列为复核警告。警告按 diff block 给出源/候选位置、上下文和稳定指纹，不能再从全局计数猜位置。统一门只接受同时绑定源树、候选树、warning code 与 `finding_sha256` 的逐条决策；重复、未使用、漂移或指向 error 的决策一律拒绝，且不替代成对质量复核。

位置级 KEEP 和语义 warning 的接受决定还必须声明 `reviewer_kind: human`。模型意见可写入恢复包供队员快速核对，但不能解除发布阻断；缺少该字段或写成 `model` 时，候选继续停留在 `REVIEW`。

## 9. 人类双盲选择

机械门通过后，用 `blind_pair_evaluation.py prepare` 随机交换 A/B 并把映射键与评审包分离。评审者分别选择自然度、公开判断轨迹、具体性、内容密度和语义忠实度，不看提供者身份，不运行 AI 检测器。正式比较每对至少两名独立评审者；`SKIP` 不算有效票，两人分歧必须追加独立第三评审。先用合并器保存 merge report，再生成 `aigc-blind-scoring/v2` score；报告记录候选 ID、有效真人覆盖、逐维严格多数、一致率，并锁定 key、ratings、匿名 packet、原始 pairs、merge report 及其单人输入；正式选择时这些 ID 必须覆盖正在比较的候选。

## 10. 原生能力证据等级

`test_native_integrations.py --execute-safe` 只执行声明为离线安全的审计命令，不启动 GUI、服务器或远程 API。报告必须保留原等级：`native_executed`、`syntax_checked`、`prompt_contract`、`entrypoint_only`、`blocked`。适配器生成了任务包或语法检查通过，都不能改写成“原生工具运行成功”。

## 11. MCM 发布状态机

```text
SOURCE_FROZEN
-> GENERATION_INPUTS_LOCKED
-> CANDIDATES_READY
-> HUMAN_SELECTED
-> GATES_PASS | GATES_FAILED
-> RELEASE_READY
```

`select` 是人工裁决记录；脚本不从分数推断胜者。选稿时还要解析并冻结采用稿的完整编译资源树，包括图片、参考文献库、外部代码输入和候选目录内的本地类/样式文件；任何目录外资源或选择后资源漂移都会使账本审计失败。`run-gates` 还必须接收已完成人工选择的 `portfolio-plan.json`、已通过的 `style-retrieval-plan.json`、`section-authoring-brief.json`、`section-drafting-packets/packet-index.json`、候选生成后建立的 `section-drafting-usage.json`、`modeling-workbench.json`、`reasoning-preflight.json` 与两名队员填写的 `reasoning-review.json`。`portfolio-selection` 先重新计算角色回执、原生 Humanize 运行记录、证据、候选和人工决定的哈希，并确认采用 ID 与发布副本一致；`academic-style-release` 再实际执行 Humanize 词法扫描、受保护改写契约、段落角色、节奏和相对修订检查，并用同一 packet index 分别审计冻结源与候选。结构信号下降可计作一类收益；内容收益只在源稿的模型空降、依据/数学变化缺失、无记录比较、结果观察与解释脱节或检验动作与结论脱节被候选修复，且候选通过相同判断桥契约时成立。结果和检验类收益还要求工作台在起草前登记来源绑定的 `interpretations` 或 check `result_terms`；候选成稿中的新说法不能反向生成这类证据。只挂接 packet、只换词或候选本身仍缺判断桥不能进入 `GATES_PASS`。随后核对逐节底稿是否把发布稿的每个章节绑定到同一工作台和真人预审、语料是否仍只作语言观察，再用 usage receipt 检查源章节、packet 与候选章节哈希是否一一对应。发布器只复制已锁定资源树，以参数数组对副本运行已知本地门，不执行 manifest 中的任意命令字符串。每道门保存输入哈希、返回码及 stdout/stderr 哈希，实际 Python 质量门另存脚本快照；聚合门还逐项快照它实际调用的脚本和词库，避免“外层脚本未变、内部规则已漂移”破坏旧证据。编译成功还必须产生 PDF、AUX 和 TeX 主日志。日志中的未定义引用、缺文件、缺字形和 Overfull 阻断发布，Underfull 与字体警告保留给逐页裁决。`GATES_FAILED` 是可审计的诚实终态，但不能 `finalize`。

`judgment-ledger.json` 是 `run-gates` 的必填发布输入；发布器会在选定稿副本上实际执行 `audit_judgment_ledger.py --workbench modeling-workbench.json`。每条依据必须与当前问工作台锚点的 ID、类型、至少一个术语及冻结来源 ID 对齐，正文中带明确动作词的具体方法引入还必须逐项出现在 `methods.terms` 中，并锁定账本、工作台、门脚本和输出日志的哈希。缺失、漂移、借用锚点 ID 改写成无关依据、空降具体方法，或正文方法没有先行依据时，发布状态只能保持 `GATES_FAILED`。

工作台门分成两个不可互换的阶段。生成输入锁运行 `audit_modeling_workbench.py --phase preflight`，验证冻结来源、问题集合、锚点、数学目标、路线、结果解释记录和检查记录，但不要求初稿已经出现本轮待补的判断桥。发布门在采用稿副本上运行 `--phase release`，才验证这些记录已进入正文。生成前误用 release 会循环阻断直接跳模型的原稿；发布时误用 preflight 会放过只填工作台而未改正文的候选，两者均属门配置错误。

`finalize` 要求另一条人工记录，逐项确认标题、跨页表、公式、图注、参考文献、附录、溢出和乱码。脚本不会自动完成视觉复核；只有质量门全部通过、PDF 未漂移且页面检查完整时，才写出新的 append-only `RELEASE_READY` manifest。
选择和终审记录必须分别带有 `reviewer_kind: human`；缺失或写成 `model` 时只能保持 `HUMAN_REVIEW_PENDING` 或 `GATES_PASS`，不能进入 `RELEASE_READY`。

## 12. 完整角色证据

`role-contracts.json` 为 21 个包逐一规定 `deliverables`、`completion_evidence`、`fallback` 和 `must_not_claim`。路由阶段会附带这些字段。调用一个包不是只取其中一条提示或一个分数，而是完成它在当前场景中的交付物，并留下合同要求的证据。包内嵌套单元还须通过 `audit_folder_utilization.py`：当前目录包含 29 个嵌套清单，其中 AI_paper 的 16 个入口类必须实际存在并通过语法/类名探针；工作台计划从同一份树哈希目录读取它们，不能复制一份静态列表后宣称已调用。

组合器还对场景内容 Skill 使用 `references/content-role-contracts.json`，对
`deai-academic-writing`、`mcm-cup-standard-write`、`deai-modeling-writing`、
`deai-research-writing` 和 `deai-course-notes` 列出必须交接的工作台、台账和门结果。
所有角色统一提交 `aigc-role-receipt/v1`：

```json
{
  "schema": "aigc-role-receipt/v1",
  "provider": "deai-modeling-writing",
  "role": "content-owner",
  "status": "pass",
  "authority_source_sha256": "<frozen source sha256>",
  "execution": {
    "mode": "manual_skill",
    "run_id": "mcm-2026-08-16-r01",
    "references_read": ["rules.md", "validation-gates.md"],
    "pass_count": 1
  },
  "evidence": {
    "claim-ledger": {"path": "claim-ledger.json", "sha256": "<sha256>"},
    "parameter-ledger": {"path": "parameter-ledger.json", "sha256": "<sha256>"}
  },
  "unresolved": []
}
```

回执只是一层索引，证据本身还要通过：

```powershell
python scripts/validate_role_evidence.py claim-ledger.json `
  --evidence-type claim-ledger --provider deai-modeling-writing `
  --role content-owner --source-sha256 <frozen-source-sha256> --format text
```

提示词型内容 Skill 使用 `aigc-role-evidence/v1`。统一字段为 `evidence_type`、`provider`、
`role`、`status`、`authority_source_sha256`、`execution` 和 `inputs`；`inputs` 中每个真实
文件都要给出路径与 SHA-256，且至少包含当前冻结源。正文数据按证据类型使用不同集合，
例如 `claim-ledger` 使用非空 `claims`，每条含 `id`、`statement`、`status` 与
`source_refs`；`parameter-ledger` 使用 `parameters`；`document-map` 使用 `documents`。
因此同一份泛化笔记不能靠改文件名同时充当六种台账。普通 TXT、空集合、未绑定输入、
错误提供者、错误角色、未决项或 `template/pending/detector_only` 执行模式均阻断。

MCM 内容角色不把原生门降格为手填 envelope。`modeling-workbench`、
`reasoning-preflight`、`style-retrieval-plan`、`section-authoring-brief`、`section-drafting-packets`、`judgment-ledger`、`content-density-report` 和
`manuscript-audit` 必须分别提交原生审计 JSON。报告要写入实际输入路径和哈希；主稿哈希
必须等于冻结源，工作台审计与预审还必须引用同一份工作台。复核器的 audit/native report
绑定被审候选，带 `candidate-verification` 的工作台回执同时绑定候选 ID、候选哈希、导出件
和核验报告。

候选回执另填 `candidate_id` 和 `candidate_sha256`。候选阶段只执行可在选稿前完成的本地门，
不能预填内容密度、结果同步、编译等采用稿发布门；后者只在 `HUMAN_SELECTED` 后运行。
Humanize 候选登记时由组合器实际生成 `academic-style-audit.json`，回执还要提交可重新验证的
`native-run-report` 与 `change-report`。inline 运行会重跑 `emit` 并绑定 before/after 哈希；
长文运行会核对 `finalization_metadata.json` 与 `rendered_manifest.csv` 的源快照—候选关系。
复核回执必须绑定被审候选的哈希；工作台回执必须绑定其导出、映射或 Diff 文件。组合器
重新计算每个证据文件的 SHA-256，解析关键报告的 schema、状态和源/候选哈希；缺项、哈希漂移、
错误角色或 `status != pass` 均阻断。准备任务、适配器语法通过、“已读 Skill”或手填
`gate_results: pass` 都不属于完整角色证据。
组合器在成功挂接时记录证据契约版本、验证器路径和验证器 SHA-256；缺少该记录的旧回执，
或验证器发生变化后的历史回执，会在 freshness 检查中失效并要求重新挂接。
能力不可用时只能写入 `waive-role` 的人工回退记录；这会产生
`COMPLETE_WITH_FALLBACKS`，不会冒充 `COMPLETE`。

角色契约审计还检查：

1. 登记包与契约包一一对应；
2. 每个 Skill 名称和应用别名只归属一个包；
3. 声明接口确实由统一适配器实现；
4. 每个包至少进入一个合法场景；
5. 默认链、备选编辑器、复核器和工作台均能被路由器真实生成；
6. 应用不能越过场景边界，例如中文普通文案诊断台不能进入 CUMCM 主链。

正式 MCM `run-gates` 还必须独立执行 `audit_reasoning_scaffold.py`。它检查多处分问是否重复同一组可见论证动作；该结果与 `academic-style-release` 内部检查分别留账，避免聚合门只记录外层脚本而漏掉结构性机械腔。

## 13. 组合级评测

完成候选后，使用 `aigc-stack-evaluation/v1` 清单锁定源稿、候选、内容阶段报告、候选回验、盲评与人工决定。运行：

```powershell
python scripts/run_stack_evaluation.py evaluation.json --format text
```

没有人工盲评时，最高只能得到 `MECHANICAL_PASS_HUMAN_PENDING`。正式人工接受还要求 `aigc-blind-scoring/v2` 覆盖当前候选和源稿，每对每个维度至少两张有效真人票、形成严格多数，并由 merge report 绑定各单人 CSV；另写具体人工裁决。检测分数、作者身份概率和所谓 human score 会被组合级评测直接拒绝。完整格式见 [stack-evaluation.md](stack-evaluation.md)。

## 14. 未见文本盲测

局部候选的盲评不能证明升级在下一批文本上仍有效。对于文风资料、编辑器路由或候选策略的升级，建立单独的 `aigc-style-benchmark-suite/v1`：每个案例、每个候选提供者均登记三次独立候选；源码、候选、验证报告、匿名 packet、评审表和评分报告均锁定哈希。

开发集只用于诊断和下一版规则；保留集必须在规则冻结后使用，且评分后进入 `SCORED_HOLDOUT_SEALED`。聚合报告拒绝两类集合复用同一源文本。失败条目记录到案例和维度，不自动修正文稿。详见 [style-benchmark.md](style-benchmark.md)。
