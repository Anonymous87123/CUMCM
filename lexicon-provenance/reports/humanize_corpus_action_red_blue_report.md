# 来源锚定 Humanize 迭代红蓝队报告（历史 profile 与 v27 现行边界）

## 结论

本轮没有把 MD/TeX 当作句库，也没有凭空扩写“更像人”的词表。新增闭环把此前人工阅读过的 GPT 生成材料压缩为可审计的“表达动作卡”：动作卡记录场景、用途、禁止迁移项和来源行范围，但不保存源文节选、事实、公式、数字、引文或结论。

该闭环已经在真实 `main.tex` 片段上进行前向实测。候选没有获得自动发布资格，并在不同轮次分别被以下门拦截：

- 来源行范围中的连续汉字复制；
- 数字/单位不变量变化；
- 条件、模态和言语行为漂移；
- 候选正文修改后未同步 `anchors.after_text`；
- 来源复制检查或锚点合同未完成时，不继续假装执行后续门。
- 未选中的已登记来源复制也会被全局 copy gate 捕获；队列并发写入由 queue 级锁序列化，文件系统竞争转为可审计错误。
- 黑盒发现的长文 P0 已修复：prepare 现在生成 `prepare_integrity.json`，finalize 会校验全部快照、账本、保护区和 chunk；篡改 `units.jsonl` 不能伪造 DONE 或全文 PASS。

因此，本轮可确认的是“来源动作约束和拒绝错误候选的确定性工具链可用”，不能确认“生成模型已经具备稳定的科研全文改写能力”。候选门输出 `semantic_requirements=NOT_EVALUATED`，事实、引文、因果、计算和学术正确性仍需独立人工门禁。

v27 没有放宽该来源边界。新增的 paired-quality verifier、challenge、keyset 和 review record 全部属于
安装版审计面，被 generator projection 明确排除；外部复核结果也不能把 GPT 负例升级为正向范文、
PERSONAL Voice 或 production action card。

## 语料边界

动作索引位于 `C:\Users\Lenovo\.codex\skills\humanize-academic-chinese\references\corpus-action-sources.json`。本报告第 3 节记录的是 2026-07-13 的历史 profile 运行（26 个来源、50 张可用卡）；当前 canonical catalog 已收窄为 26 个来源、27 张抽象动作卡，且没有任何 `production_positive` 卡。源文仍不导出，动作卡不构成句库，也不进入普通生产改写的正向声线。

| 场景 | 来源动作 | 依据 | 禁止迁移 |
|---|---|---|---|
| `RESEARCH` | 事实/对象到分析角色映射；校准、一致性检查和独立验证分层；内部代理与外部观测分离；结果连接到已有机制并绑定条件；描述轨迹与最终分类分开；条件依赖的范围表达 | 微信 `main.tex` 指定行范围 | 生态事实、模型变量、数值、引文、政策结论和新的因果解释 |
| `COURSE` | 对象 -> 条件 -> 工具 -> 领域检查；具体误读与局部纠正；按条件依赖顺序解释推导；公式后的物理意义、方向和量纲检查 | `physics2.tex`、`physics1.tex` | 连续反问、教练腔、教学口头禅迁移到研究正文 |
| `REPORT` | 样本/输入边界先行；发现 -> 动作；证据无法区分时保留候选并指向可区分观察 | CET Section B 报告 | 标题/列表堆叠、无主语命令句迁移到论文正文 |
| `ALL` 负例 | 拦截表层解释 -> 深层机制 -> 限制 -> 愿景收束、强制对照和自动未来桥接 | CET `test.tex` | 不作为正向范文 |

其中 `GENERAL` 正向卡数量为 0。profile 明确返回 `CORPUS_INSUFFICIENT`，所以普通学术、人文、法学文本继续依赖原稿和 Voice Profile；工程治理报告、第三方评论、产品稿、API 文档与 OCR 教材只作负例来源，不能冒充 GPT 正向语料。

明确排除：乱码备份、用户明确排除的 `cet6.tex`、CET 报告近重复版本 `v2`。乱码只记录排除状态，不修复、不猜字、不生成动作卡。版本族只保留 canonical 成员，避免重复加权。

## 新增工具

### `build_humanize_action_profile.py`

该脚本校验动作索引、来源路径、场景匹配、行范围、编码和排除理由。读取来源只用于验证行范围是否仍然存在，输出为来源哈希、行范围、状态和动作卡；`source_text_exported=false` 是固定结果字段。

历史 profile 真实运行结果（非 v26 生产准入）：

```text
PASS: 50 available, 0 unavailable
READABLE=23, EXCLUDED_CONFIG=3
source_text_exported=false
```

### `validate_humanize_candidate_queue.py`

候选包必须声明：

- `candidate_id`、场景、改前/改后路径；
- `corpus_action_support`（GENERAL 无正向语料时必须为 `NONE`）；
- 使用的动作卡；
- 每张动作卡对应的锚点 ID；
- 每个锚点的 `before_text`、`after_text` 和作用；
- 已接受的 high finding 或 warning 理由。

验证顺序是：候选合同 -> 动作卡可用性与 required anchor roles -> 改前/改后锚点 -> 统一不变量/词项验证 -> 全 catalog 来源连续汉字复制 -> 当前场景所有 negative guard -> 负例模板检查。候选哈希绑定候选包和改前/改后正文，修订必须声明血缘；队列级锁覆盖状态读取到发布，顶层状态按三态进入 `accepted/`（PASS）、`review/`（REVIEW）或 `rejected/`（FAIL），机械门通过但 paired-quality pending 的候选只能进入 `review/`，不会覆盖原稿。

负例 guard 不是正向范文。即使候选没有选择 guard，运行时仍会扫描改后正文；命中返回 `REVIEW`，并记录 guard ID、命中组和次数。来源复制门也扫描未被候选选择的已登记来源。队列对非法 ID 使用隔离存储名，history 保留原始结果，事务 staging 或并发冲突时不清空旧 head，裸文件系统异常会转成可审计错误。

该验证器明确不承担：内容正确性、事实核验、引文真实性、数学推导、实验复现、因果充分性或作者身份判断。

## 真实前向实测

独立代理只获得 Skill、真实 `main.tex` 的指定行范围和通用改写任务，没有获得预期答案、旧测试夹具或红队结论。它使用 `RESEARCH-SCOPE-01` 构造候选，并运行真实 profile 与候选门。

### 第一次候选

状态：`FAIL`。

拦截内容：

1. 5 处来源范围连续 8 字复制；
2. 将已有对象改写为“两项”，触发 `NUMBER_OR_UNIT_CHANGED`；
3. 条件/言语行为 warning 未被逐项解释。

### 第二次候选

状态：`REVIEW`。

改写已通过硬不变量，但仍有一处来源连续复制（“江豚和长江鲟分别”），并新增条件语气 warning。门禁没有因为“整体读起来更顺”而放行。

### 第三次候选

状态：`FAIL`。

候选正文已经变化，但 `candidate.json` 中的 `anchors.after_text` 未同步，命中：

```text
anchor_after_missing:scope-anchor
```

由于锚点合同失败，来源复制检查和模板检查被标记为未运行，候选没有被伪造为 `PASS`。该错误展示了候选包必须和正文一起更新，不能只改正文文件。

### 资格解释

这次前向实测不是生成资格通过证据，而是门禁拒绝能力证据。历史 profile 曾扩展到 50 张可用卡，但当前 canonical catalog 已收窄为 27 张抽象卡，且不提供生产级正向 action；这仍不改变以下边界：

- `GENERAL` 正向语料支持状态仍为 `CORPUS_INSUFFICIENT`；
- 真实 `main.tex` prepare 只生成 36 个单元，其中 28 个仍为 `PENDING`、8 个为 `SKIPPED_PROTECTED`，`completion_claim_allowed=false`；新生成的 `prepare_integrity.json` 含 42 个 prepare 产物哈希（36 个 chunk 加 6 个清单/状态文件）。
- 负例 guard 已进入运行时门，但命中只表示需要复核，不是对文风质量的统计评分。

当前仍不能宣称：

- 科研自动改写已经稳定；
- 50 张动作卡也不能替代人工阅读；
- 语料来源能证明任何事实或结论；
- 候选 `PASS` 等于学术正确；
- Skill 能自动完成任意长文全文。

## 真实长文快照验收

对用户指定的微信 `main.tex` 做了不修改源文件的真实 prepare：

```text
units_total=36
PENDING=28
SKIPPED_PROTECTED=8
protected_spans_total=821
completion_claim_allowed=false
```

快照目录为 `build/real-main-prepare-v2/`。它证明了单文件 TeX 能被切成可追踪单元、
数学/命令/引用等保护区会被掩码，且乱码或保护单元不会被强行交给改写器；它不证明
全文已经改写。由于仍有 28 个 `PENDING`，本轮没有制造伪造的 `rewrites/` 或
`rendered/`，也没有声称编译或幂等通过。

## 测试结果

本轮新增测试：

- `tests/test_humanize_corpus_action_profile.py`：5 项；
- `tests/test_validate_humanize_candidate_queue.py`：5 项。

结果：

```text
新增聚焦测试：23/23 OK（动作 profile、候选队列、修订血缘）
Skill 完整测试：当前全仓回归覆盖
全仓测试：当前回归 193/193 OK
quick_validate.py：Skill is valid!
```

全仓测试仍只证明既有工具和新增工具的可观察行为，不等同于前向生成模型资格。文中 `193/193 OK` 是当时快照的历史计数；根据 `evaluation-contract.md`，完整模式/场景/角色/长文/盲评矩阵尚未完成时，总体资格状态必须保持 `NOT_EVALUATED`。单次运行的 `REVIEW/2` 不能上浮成总体资格状态。

## 后续使用规则

实际改写时，先运行来源 profile，再为每个候选单元创建候选包；不要把整篇 MD/TeX 拼进提示词要求“模仿”。候选若触发复制检查，应重写表达动作而不是换几个同义词；若触发数字、公式、条件或归因警告，应回到原稿确认，不得用“人工确认”四字清空门禁。无法确认时保留原文并标 `UNRESOLVED`。
