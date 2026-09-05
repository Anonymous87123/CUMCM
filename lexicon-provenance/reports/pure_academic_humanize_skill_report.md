# 中文学术纯文风 Humanize Skill：生产化交付与红队报告

2026-07-13 至 2026-07-17 的实用性复测、失败样本与机器验收见 [humanize_academic_chinese_usability_red_blue_report.md](D:/code%20LateX/elegantbook/physics/humanize_academic_chinese_usability_red_blue_report.md)。该报告明确区分机械候选可用、质量仍待可信外部复核和生成资格仍为 `NOT_EVALUATED` 的边界。

v1.52.0 的最终封版裁决见 [冻结审计](C:/Users/Lenovo/.codex/reports/humanize-academic-chinese-v1.52.0-final/final-freeze-audit.md)；命令、时间、源码/投影绑定、持久化回归、真实 capture、资格状态和本报告哈希以 [权威冻结元数据](C:/Users/Lenovo/.codex/reports/humanize-academic-chinese-v1.52.0-final/run_metadata.json) 为准。两者只确认 `ENGINEERING_FREEZE_COMPLETE`，不授予候选质量、学术正确性、作者身份或无人值守最终交付资格。

生成日期：2026-07-10  
本轮生产门更新：2026-07-24
Skill：`C:\Users\Lenovo\.codex\skills\humanize-academic-chinese`  
范围：只处理中文学术文风，不执行学术正确性、来源、实验、复现或检测规避审查  
证据优先级：可重放机器工件 > 独立评估代理连续阅读 > GPT MD/TEX 负例与压力材料 > 聊天语料统计

> **历史快照（v33 final r3，2026-07-19）**：下文 v1-v32 的数字和旧终态保留为历史证据，若与本段或第 35 节冲突，以 v33 为准。当前全量运行 701 项测试，整体 `OK (skipped=3)`，即 698 项执行通过、3 项环境相关跳过；Skill UTF-8 quick validation 通过。两次 31 文件 generator projection 逐路径逐字节一致，policy/builder 为 `1.10.3`，capability source 为 `3cb7e9aa97d2724dbb59999ad281bca03f2b7e9c83429cc644345f007f541b45`，tree hash 为 `3c92ac1b87e6181b394fd2d64cc55c2d1fa577cc4e69c276aa8972488fbab85d`，证据上限仍是 E2。v33 新增 transaction v2 fragment intent、BALANCED 声明式拓扑、严格 replay 字段、可靠起点同义换壳 detector、检测目标明示拒绝和 CLEAN -> PATCH 真实 hunk 降级。普通 `REWRITE/NO_CHANGE` 即使机械通过，也仍停在 `REVIEW/2 -> REVIEW_CANDIDATE -> rendered_review/`；资格矩阵保持 `0 PASS / 0 FAIL / 188 NOT_EVALUATED`，学术正确性、作者身份和无人值守全文交付均未通过。完整修订见文末第 35 节。

> **历史 checkpoint（v44 final r2，2026-07-19）**：第 45 节曾取代 v33 快照，记录 v5 publication transaction、v3 unit binding、v1 authoring binding、38 文件投影和 903 项回归；它现在只作历史记录。

> **当前冻结 checkpoint（policy/builder v1.52.0；projection v1520，2026-07-24）**：第 76 节取代此前所有“当前/最新”实现数字；第 75 节及更早 checkpoint 只作历史证据。正式完整回归为 `Ran 1277 tests in 821.729s / OK (skipped=8)`，即 1269 项执行通过、8 项环境相关跳过，父进程实际观察退出码为 0；从当前安装源新建的两份 39 文件投影逐文件零差异且 manifest 原始字节相同，manifest SHA-256 为 `8464cf5109865f97c193ce89c0cdf7a49846d48b29029f785fedbc573877a029`，tree 为 `46644c75f482f88f87d89f16e93e5bee497022b3e01ef98fbdb2935bebb2301a`，capability source 为 `cef35dd4b48568ab2940c6f287526978bba899ac1466483fd2fadd7f684f3b76`。Main modeling r4、Modeling notes r3 与 CET-6 三份真实工件都有 current capture，均为机械层 PASS、顶层 `REVIEW/2`、外部 paired-quality 待审、学术正确性 `NOT_EVALUATED`。默认生成资格为 `0 PASS / 0 FAIL / 193 NOT_EVALUATED / exit 2`。因此当前版本正式冻结为生产级候选生成、拒错与审计工具链，不能宣称生成模型已获得无人值守最终交付资格。

## 1. 当前结论

这轮不再把“规则很多”当作完成。`humanize-academic-chinese` 已从纯规则库升级为“规则 + 可定位扫描 + 语义保护 + 统一验证 + 长文快照/收尾”的执行链，但仍保留一个明确边界：模型直接盲写的结果不能自动信任，必须经过验证器或人工复核。

当前能证明的结果：

- 39 组集中词项信号已与 Skill 规则直接关联，包含 208 个固定变体、58 个正则、37 组 signal 级上下文豁免、风险等级、阈值、动作和正反例；
- 扫描器可定位到文件、行、列、命中词、窗口计数、保护状态、豁免原因和建议动作；
- 不变量检查器能阻断公式、数字/单位、引语、代码、TeX 注释、关键命令、环境和花括号漂移，并把否定、模态、定义/命名和结果报告变化列为言语行为 warning；
- 统一验证器用精确 SHA-256 绑定改前/改后版本，退出码固定为 `0=PASS`、`1=FAIL`、`2=REVIEW`；
- 长文准备器和收尾器可生成固定快照、include manifest、保护占位块、覆盖账本、逐单元验证、diff、回滚清单、partial/full 发布状态和幂等记录；
- 工作区当前冻结基线完整回归共发现 1277 项自动测试，整体 `OK (skipped=8)`；这表示 1269 项执行通过、8 项环境相关测试跳过，不写成“1277 项通过、另有 8 项跳过”；
- 当前 4685 行、359087 字节的 `physics1.tex` 压力快照生成 60 个单元和 3164 个保护 span；v22 的完整结构候选即使覆盖闭合，也因结构语义待外部复核而保持 `REVIEW/2`；
- 三轮共 9 次历史代理盲测没有一份可计为当前生成资格证据；其中旧 `PASS` 缺少现行 provenance/request 绑定，只能作为归档失败或回归 fixture。
- 2026-07-14 的两次无答案泄漏 fresh forward 又发现两个 false-PASS：科研稿把“奠定坚实基础”轮换成“后续研究的出发点”，课程稿把“必须牢记”轮换成“必须注意”并生成“由此可以得出结论”。两组精确 before/after 已进入 scanner 和统一验证器回归，修复后均为 `REVIEW/2`。
- 三份旧人工校准输出属于 pre-provenance 归档证据。理由字符串不能证明真人身份，也不能用旧 warning 接受机制追认当前 `PASS/0`。
- 第四轮三路红队又找出 2 个短文保护 P0、2 个合同 P0 和 10 个执行链 P1；修复后，原本会误 `PASS/0` 的数学环境、题干、长 fence、中文数词、乱码和显式术语变化均转为 `FAIL/1`，非法编码、远距豁免和不充分理由转为 `REVIEW/2` 或参数拒绝；
- 旧 `aigc-down-skill` 退休前又执行三轮行为前测：第一轮发现引语定界符 P0、high 残留和无来源归因 P1；第二轮只剩混合请求新造桥接模板 P1；第三轮原例及两个变体 `P0=0/P1=0`。旧目录随后按固定 SHA 删除，新进程目录只保留本 Skill；
- 确定性工具链已通过当前回归门；v1.51/v1516 历史资格面曾为 188 原子，v1.52.0 当前资格面已扩为 193 原子且仍全部 `NOT_EVALUATED`。历史代理试验只作归档/回归证据，报告不再把“验证器能拦截”偷换成“模型已能稳定一次生成合格稿”。
- 资格 harness 已切换到 manifest v2 和 Skill 内固定 oracle：current case 不能再提交 `assertions/result/expected/check_ids/regex/command`，旧 v1 只能归档；此前可让违约 `MODE-01` 获得 PASS 的证明包现在返回 `integrity=FAIL`、`atoms_pass=0`。
- 固定 catalog 的历史 suite/check 结构只证明评分所有权已移出 manifest；v25 历史资格总面为 188 个原子，当时仍全部 `NOT_EVALUATED`。v1.52.0 当前总面以第 76 节的 193 原子为准，不能用旧 catalog 规模或局部机器检查代替完整前向。
- v13 已把全文 Voice 从 `NOT_EVALUATED` 改成受限但真实的机械门：DEFAULT 只证明场景默认、绑定、逐 unit validator 与披露闭合，个人声线状态固定为 `NOT_APPLICABLE`；PERSONAL 至少需要 6 个目标正文块，逐 feature 复核当前 extractor hash、before/after 支持数和显著回退，所有 PASS 仍固定 `identity_verified=false`。
- 跨 unit 门不再只扫描单块：它按 protected-masked before/after 聚合 `LEX-REPAIR-01`，并实际读取此前 MD/TeX 语料登记的 `negative_guard`。两个局部 PASS 的 unit 若共同新增“这里只……”或重复“不是……而是……”等模板，新增 occurrence 所在 unit 会从临时 DONE 回退为 `UNRESOLVED`，其 diff 不发布；原文继承重复保持可审计但不阻断。
- 本地 sealer 可从同一参数逐字节复现 catalog `public_context`；runner 当前只挂载固定 39 文件 generator projection，并在运行前后复核类型、路径、字节和 tree hash。投影不含 oracle，但宿主机不可达和完整 generator context 仍未验证，固定 trust policy 关闭 E3，证据继续封顶 E2。此前基础设施无效采集仍只作诊断记录，没有被补写成 output 或 E3 证据。
- v14 把 fresh second pass 从 `NOT_RUN` 假字段升级为独立控制面：第二遍从第一遍完整 `rendered/` 重建快照，每个 unit 使用同一无答案 sealed prompt 和独立 runner；receipt 必须绑定 plan、collection、run record、run seal、projection、Voice、scene 与活证据根，第一遍 finalizer 会当场重跑 verifier。缺 trial 或任一 REWRITE 为 `REVIEW/2`，工件漂移为 `FAIL/1`，可重算自哈希不再足够。

因此，这个 Skill 的生产定义不是“模型一遍生成就自然”，而是：

> 生成结果必须经过可复核的候选定位、保护检查、言语行为复核和完成态证据；任何未决项都不能被一句“已完成”覆盖。

## 2. 职责边界

### 2.1 它处理什么

- 固定句首、万能过渡和路线报幕；
- 假转折、假纠偏、段落流水线和统一节奏；
- 管理、审计、营销、教练和编辑后台腔；
- 抽象评价、创新表演、公式字幕和图表导览；
- 强制总结、自动展望、章节桥接和机器闭环；
- 过度对称、均等用力、模态缓和堆叠；
- Humanize 修复语自身形成的新模板。

### 2.2 它不处理什么

- 数学、公式或推导是否正确；
- 引文、资料、数据或事实是否真实；
- 实验、模型、代码或结果是否可复现；
- 创新是否成立、研究质量是否足够；
- 作者身份、AIGC 概率或检测规避。

“保护原意”只是一条编辑边界，不是事实审查。旧 `deai-*` 质控 Skill 没有被并入本执行链。

## 3. 生产架构

```text
用户任务
  -> SKILL.md：模式、场景、强度、输出、优先级
  -> lexical-signals.json：集中信号与上下文动作
  -> scan_humanize_chinese.py：候选定位
  -> extract_detector_report_scope.py：报告可见标注的 scope-only 映射
  -> 场景规则 + Voice Profile：人工/模型改写
  -> check_humanize_invariants.py：硬保护与言语行为差异
  -> validate_humanize_output.py：PASS / FAIL / REVIEW
  -> 短文生成待审候选，或进入长文 prepare/finalize
```

长文链：

```text
prepare_humanize_long_document.py
  -> snapshot + include manifest + units + protected placeholders + initial ledger
  -> 独立 rewrites/<unit_id>.json
finalize_humanize_long_document.py
  -> placeholder restore + per-unit validation + diff + staging
  -> rendered_partial、rendered_review 或（仅有可信外部 clearance 时）rendered
  -> candidate assembly 与 delivery gate 分开裁决
  -> final ledger + rollback manifest + idempotency evidence
```

主 `SKILL.md` 当前为 329 行，负责决策和路由；大型规则按需加载。排除 `__pycache__` 后，Skill 的 `.md/.json/.py/.yaml/.yml` 共 58 个文件、39782 个物理行，不会在每次普通调用时全量加载。

## 4. 文件与规模

| 组件 | 行数 | 职责 |
|---|---:|---|
| `SKILL.md` | 329 | 核心模式、优先级、高风险快检、报告/混合请求门和完成门 |
| `lexical-signals.json` | 602 | 29 组词项/句壳信号及上下文合同 |
| `pathology-catalog.md` | 527 | `HUM-01` 至 `HUM-16` 病灶库 |
| `course-notes.md` | 246 | 课堂场景规则 |
| `modeling-engineering.md` | 273 | 建模场景规则 |
| `research-journal.md` | 277 | 科研场景规则 |
| `rewrite-patterns.md` | 504 | `CP/MP/RP` 各 20 组改写模式 |
| `voice-profile.md` | 578 | 作者样本准入、字段、置信与跨场景迁移 |
| `detector-report-intake.md` | 199 | 报告静态输入、唯一源文映射、scope-only 与拒绝边界 |
| `operational-contract.md` | 542 | 参数、权限、角色、决策和交付合同 |
| `evaluation-contract.md` | 707 | 行为 fixture、失败级别、manifest v2、确定性发布门和 188 原子生成资格门 |
| `long-document-workflow.md` | 986 | 快照、单元、只读上下文、结构 review、diff、回滚、编译、幂等与成对质量门 |
| `structural-rewrite-contract.md` | 506 | STRUCTURAL 来源段映射、结构基线、事务候选、语义复核请求和状态裁决 |
| `scan_humanize_chinese.py` | 606 | 词项扫描、编码覆盖账本与 TeX/MD 保护识别 |
| `check_humanize_invariants.py` | 1100 | 硬不变量、显式术语与言语行为检查 |
| `extract_detector_report_scope.py` | 555 | 静态 HTML 标注提取、唯一规范化映射和报告输入审计 |
| `validate_humanize_output.py` | 1268 | 统一验证、finding 级裁决、request-bound warning proposal、机械层与成对质量请求 |
| `prepare_humanize_long_document.py` | 1924 | 长文准备、切块、编码审计、动态 include 未决记录、事务 inventory 和初始账本 |
| `finalize_humanize_long_document.py` | 6108 | 单元验收、质量/结构请求、run-dir 事务、进程树收拢、派生发布和回滚 |
| `build_humanize_action_profile.py` | 715 | 验证 MD/TeX 来源锚点并生成不含原文摘录的动作 profile |
| `validate_humanize_candidate_queue.py` | 1800 | 冻结候选、来源、策略和工具快照，执行复制/负例与 PASS/REVIEW/FAIL 三态队列门 |
| `prepare_humanize_candidate_revision.py` | 205 | 建立候选血缘并清空不可跨 revision 重放的 warning 状态 |
| `build_humanize_generator_projection.py` | 1348 | 30 文件闭集、SKILL 确定性删节、类型/引用/控制 ID/TOCTOU 审计和规范 manifest |
| `audit_humanize_generation_qualification.py` | 4903 | 固定 oracle、trust policy、投影独立重建、manifest v2、188 原子和三态聚合 |
| `run_humanize_generation_trial.py` | 1230 | 投影挂载、staged-case 双向核对、JSONL/receipt/run record/seal 与本地 E2 上限 |
| `seal_humanize_public_fixture.py` | 261 | 生成 hash-bound input/prompt/public-context，拒绝结构性答案泄漏和额外文件 |

排除 `__pycache__/` 后，整个 Skill 中 `.md/.json/.py/.yaml/.yml` 共 58 个文件、39782 个物理行。生成器投影视图固定为 30 个文件；其中 26 个能力文件原样保留，4 个文件执行固定控制面剥离，oracle、fixtures、trust policy 和资格脚本不会进入生成上下文。

## 5. 集中词库

### 5.1 数据结构

每个信号包含：

```text
id / category / label / variants / regex / scenes / severity
threshold / exclusions / action / rationale
positive_examples / negative_examples / provenance
```

当前统计：

| 项目 | 数量 |
|---|---:|
| signal / category | 29 / 29 |
| 固定变体 | 197 |
| 正则 | 46 |
| signal 级上下文豁免 | 28 |
| high / medium / low | 7 / 15 / 7 |
| `DELETE / REWRITE / REVIEW` | 2 / 5 / 22 |
| 正例 / 反例 | 32 / 29 |

词库不输出“AI 分数”，也不把单次命中当作作者身份证据。

### 5.2 最重要的可落地抓手

| 词族 | 常见变体 | 默认动作 | 不能机械处理的情形 |
|---|---|---|---|
| 空重点壳 | 值得注意的是、需要指出的是、必须强调的是 | `REWRITE` | 后句确实承担突变且无更直接定位方式 |
| 教练腔 | 必须牢记、必须/务必记住、秒杀、救命表、锁死答案 | `REWRITE` | 用户锁定原句或确属题干/引语 |
| 营销拔高 | 全面提升、深刻/深入揭示、填补空白、全新范式、提供有力支撑 | `REWRITE` | 引用标题或用户锁定原主张；仍应优先具体化 |
| 管理施工腔 | 收口、核心抓手、锁定故事线、形成……闭环 | `REWRITE` | 闭环控制、机械抓手、门禁系统等正式术语 |
| 编辑后台 | 正文里要、表格的作用是、下一段负责、对论文写作而言 | `DELETE` | 文章本身研究写作方法时需人工复核 |
| 章节桥接 | 为后续奠定/打下基础、是后续……的基础、为后续提供支撑 | `DELETE` | 真有具体承接对象时改成对象，不保留空壳 |
| 自动展望 | 未来/后续可进一步、后续拓展应用场景 | `REVIEW` | 原文提供明确未决对象、方法和优先级 |
| 模态堆叠 | 可能、或许、一定程度、某种意义、某些启发 | `REVIEW` | 不同词分别限定概率、范围和证据状态 |
| 结果句壳 | 结果表明、结果显示、分析表明反复起句 | `REVIEW` | 单次结果报告是应保留的言语行为 |
| 修复模板 | 这里只看、这里真正、其余沿用、不再展开 | `REVIEW` | 单次真实取舍可保留；跨段重复要改 |

### 5.3 不是禁词表

以下单词单独出现不构成病灶：

- `因此`：证明链中可连续承担真实因果；
- `本文`：可承担作者指代；
- `框架/机制`：可能是正式分类；
- `结果表明`：保留结果报告状态；
- `链条/落地`：可能是力学实体和运动过程；
- `闭环`：可能属于控制理论。

扫描器必须结合窗口、场景、保护角色和豁免正则。`KEEP` 不是静默忽略，而是需要说明具体表达功能。

## 6. 逐文档连续阅读如何改进扫描器

5119 行 `physics1.tex` 的第一次扫描返回 24 个候选，其中大量是误报：

- “柔软链条、微元链条、链条下落”被当成管理词“链条”；
- “落地点、碎片同时落地”被当成项目“落地”；
- `exercise/example/theorem` 内题干和正式陈述被当作作者正文；
- TeX 的 ``直接引语'' 未进入保护区。

人工读完命中上下文后，增加了：

- 力学实体链条与落地过程豁免；
- `exercise/example/problem/question` 题干保护；
- `theorem/lemma/proposition/corollary/definition` 正式陈述保护；
- TeX 双反引号与 `\enquote/\textquote` 引语保护。

重跑同一 5119 行文件后，候选从 24 降到 2，只剩同一作者解释段中的两处 `不是……而是……`，需要结合教学功能人工判断。运行时间约 0.5 秒。

这正是“脚本先跑、人工多读、再反推规则”的具体效果，而不是继续堆禁词。

## 7. 保护与语义不变量

### 7.1 硬保护

以下变化直接 `FAIL/1`：

- Markdown/TeX 代码、行内代码和 verbatim；
- 行内/陈列公式及数学环境；
- 直接引语；
- 数字、范围和单位；
- `label/ref/eqref/cite/url/includegraphics` 等关键 TeX 命令；
- TeX 注释和转义百分号；
- 环境顺序、嵌套和平衡；
- 未转义花括号平衡。

### 7.2 言语行为

以下变化默认进入 `REVIEW/2`：

- 否定：`不、未、无、并非、并不意味着`；
- 模态：`可能、或许、仅、只、必须、应当、需要`；
- 定义/命名：`称为、定义为、记作、以下简称`；
- 假设：`设、假设、假定`；
- 报告/观察：`结果表明、观察到、我们发现`；
- 条件：`若、当、仅当、除非`。

这解决了“本文将 q<0 的样本称为 X”被改成“q<0 的样本是 X”而数字术语都未变的问题。

### 7.3 本地处理建议不能充当人工放行

非硬性 warning 首次出现后，先保存验证器生成的 `warning_review_request.request_sha256`
和逐条 `warning_fingerprint`。本地调用方只能提交绑定当前 request 的处理 proposal：

```powershell
--propose-warning-resolution <warning_fingerprint>=建议核对是否只删除重复缓和 `
--warning-review-request-sha256 <request_sha256> `
--warning-reviewer-kind HUMAN `
--warning-reviewer-id <调用方标签>
```

proposal 会写入机器产物，但固定为 `identity_verified=false`、
`review_clearance_granted=false`，warning 仍 pending，退出码仍为 `2`。当前本地工具没有
代理不可访问私钥的外部信任根，因此调用方自称 HUMAN 不能放行；只能修改稿件，让 warning
在新 artifact 上消失。未知 fingerprint、空泛建议、跨稿件重放和所有硬错误都不能豁免。

## 8. 模式、权限和作者声线

### 8.1 三模式

- `DIAGNOSE`：只诊断，不改正文；
- `REWRITE`：按强度改写并验证；
- `DRAFT`：只使用用户已提供内容起草。

诊断模式不会再落入 Rewrite 三轮，也不会声称“已调整”。

### 8.2 三强度

- `LIGHT`：只改局部词句，不移动/合并段落；
- `BALANCED`：允许段内和相邻重复调整，不跨节；
- `STRUCTURAL`：只有明确授权才跨段重排，必须交付 patch。

用户结构锁、标题锁和 scope 高于所有文风偏好。

### 8.3 Voice Profile

有作者样本时才建立 Profile，字段覆盖：

- 第一人称与自指；
- 句长和标点；
- 括号、短语和术语；
- 段落压缩度；
- 限定方式和转场；
- 言语行为与场景差异。

无样本时明确 `SCENE_DEFAULT`，不得声称复现个人声线。定义组、标准条款和等权比较不为“人味”强行制造重点。

## 9. 统一验证器

命令：

```powershell
python scripts/validate_humanize_output.py before.md after.md `
  --scene RESEARCH `
  --format json
```

状态：

| 状态 | 退出码 | 条件 |
|---|---:|---|
| `PASS` | 0 | 无硬错误、无未接受 warning、无未解释 high、无新增模板 |
| `FAIL` | 1 | 任一硬不变量失败 |
| `REVIEW` | 2 | 言语行为 warning、high 残留或改后新增候选 |

输出绑定：

- 改前/改后绝对路径；
- 改前/改后 SHA-256；
- 文档格式；
- invariant errors/warnings；
- before/after/introduced 候选数；
- high 残留位置；
- `keep_reasons`；
- `accepted_warning_reasons`。

只做目测、只比较一部分、脚本运行后又改文，都只能写 `NOT_RUN`。

## 10. 长文生产链

### 10.1 准备

```powershell
python scripts/prepare_humanize_long_document.py physics1.tex `
  --output C:\Users\Lenovo\.codex\reports\humanize_longdoc_physics1_20260710_v2 `
  --scene COURSE
```

真实结果：

| 指标 | 值 |
|---|---:|
| 输入行数 | 5119 |
| 文件数 | 1 |
| snapshot ID | `cd5fc9b656012aad` |
| 单元数 | 60 |
| `PENDING` | 51 |
| `SKIPPED_PROTECTED` | 9 |
| 保护 span | 3454 |
| 最大单元行数 | 329 |
| 最大可编辑汉字 | 2278 |
| 可编辑汉字合计 | 26766 |
| 准备状态 | `READY` |

`READY` 只表示快照和单元可用；准备器固定写 `completion_claim_allowed=false`。

### 10.2 改写包

`REWRITE`：

```json
{
  "decision": "REWRITE",
  "masked_text": "含完整 [[PROTECTED:...]] 的改写文本",
  "keep_reasons": {}
}
```

只有提交本地处理 proposal 时，才额外携带 `warning_resolutions`、
`warning_review_request_sha256` 和仅含 `reviewer_kind/reviewer_id` 的 `warning_review`；
这些字段不能把单元从 `REVIEW` 提升为 `PASS`。

`NO_CHANGE`：

```json
{
  "decision": "NO_CHANGE",
  "reason": "正式定义组保持原有等权结构"
}
```

占位符缺失、重复、未知或 hash 不符会原子拒绝该单元。复制原文却写 `REWRITE` 也会被拒绝。

### 10.3 收尾、diff 和回滚

```powershell
python scripts/finalize_humanize_long_document.py `
  --run-dir <run-dir> `
  --rewrites <rewrites-dir> `
  --check-command "<project build command>"
```

空 rewrites 的真实压力测试结果：

- `status=REVIEW`；
- `exit_code=2`；
- `PENDING=51`；
- `full_completion_claim_allowed=false`；
- `published_path=rendered_partial`；
- `source_files_modified=0`；
- `compile_check=NOT_RUN`；
- 同一快照和空 rewrites 复跑：`idempotency=PASS`，`source_files_changed_since_snapshot=0`。

编译失败时 staging 移到 `failed_staging/`，不发布 `rendered/`；原源文件从未被覆盖。完整输出复跑哈希不同则保留 `non_idempotent_staging/` 并失败，不覆盖已发布版本。

## 11. 前向测试

### 11.1 方法

每轮分别开新代理，只提供 Skill 路径、普通用户式请求和原始段落；不提供预期答案，不允许编辑本地文件。课堂、建模、科研各一份。

### 11.2 三轮结果

| 轮次 | 课堂 | 建模 | 科研 | 共同结论 |
|---|---|---|---|---|
| V3 | 留下“必须牢记”；虚报 PASS | 高风险词与模态堆叠几乎原样；虚报 PASS | 模态堆叠与桥接残留；虚报 PASS | `0/3` 可发布 |
| V4 | 停止虚报，但留下“必须牢记/打下基础” | 停止虚报，但留下“全面提升/完整闭环/有力支撑” | 停止虚报，保义较好，但“深刻→深入揭示”并保留基础句壳 | `0/3` 可发布 |
| V5 | 改成“必须记住/是后续的基础” | 核心结果已具体化，只剩泛化后续展望 | 模态和防御串改善，仍改成“构成后续研究基础” | `0/3` 自动 PASS，但均诚实 `NOT_RUN` |

V3、V4、V5 的正文均已保存为 fixture。验证器能稳定指出：

- V3 教练腔、营销词和基础句壳；
- V4 长闭环正则、`深入揭示` 同义规避和 `打下基础`；
- V5 `必须记住`、`是后续……基础`、泛化应用场景和 `构成后续研究基础`。

这组结果否定了“Prompt 写得很详细就自然会执行”的假设。生产安全来自验证门，不来自对模型自觉的期待。

### 11.3 旧人工校准的现行证据等级

三份 gold fixture 在旧验证器下记录过：

- 硬不变量错误 0；
- high 残留 0；
- introduced candidate 0；
- 定义、结果报告、引语、公式、数字和单位保留；
- 非硬性语气变化先 REVIEW，再逐项写理由；
- 旧机器结果记录为三场景 `PASS/0`。

这些 fixture 没有当前 `warning_review_request`、artifact/policy 绑定或可验证审阅来源，按现行合同只能归档为 pre-provenance 证据，不能证明真人复核，也不能计入生成资格 PASS。

## 12. 测试覆盖

当前 Humanize 工具链、generator projection、资格审计、public-case 采集链与旧入口退休门直接测试共 337 项：

| 测试模块 | 项数 | 主要覆盖 |
|---|---:|---|
| Skill 结构与合同 | 27 | 链接、触发、唯一枚举、精确 provenance、Voice round-trip、谓词来源门、语料动作锚和编辑载荷边界 |
| 词项扫描 | 22 | 正反例、场景、保护、局部豁免、编码覆盖账本、旧规则蒸馏、真实 TeX 误报、同义说教与去标签展望回归 |
| 不变量 | 32 | 公式、题干、长 fence、引语、数字、乱码、显式术语、环境、归因言语行为和三类跨版本命题升级 |
| 统一验证 | 41 | PASS/FAIL/REVIEW、finding 级理由、术语证据、request-bound proposal、v7/v8 false-PASS 与 v9/v10 三场景真实前向回归 |
| 报告范围提取 | 6 | 静态 HTML、恶意脚本隔离、唯一/缺失/歧义映射、无源与重复标注 |
| 长文准备 | 12 | include、动态 include 未决、UTF-16/NUL、固定字节、单元、占位、装饰 TeX 授权和产物 |
| 长文收尾 | 43 | 恢复、防复制、累计 partial、NO_CHANGE/high 复核、幂等、证据保全、编译回滚、冻结快照和 proposal 绑定 |
| 来源动作 profile | 6 | 23 个可读来源、动作卡锚点、排除/乱码状态和 GENERAL 语料不足 |
| 候选队列 | 37 | 冻结输入/来源/策略、跨块复制、负例 guard、TOCTOU、脱敏、事务发布和幂等身份 |
| 候选 revision | 4 | 血缘、旧 request/proposal/reviewer 状态清除和跨 revision 重放拒绝 |
| 实用性归档证据 | 10 | 历史 run 状态、pre-provenance 失败、报告与 manifest 边界 |
| generator projection | 30 | 26 文件闭集、内容批准 hash、锚点漂移、控制 ID、引用闭包、文件与根 symlink/reparse/junction、hardlink、原子发布和确定性 tree |
| 生成资格 harness | 34 | 固定 oracle/trust、投影独立重建、四件套证据、旧自证攻击、163 原子、hash 漂移和 FAIL 优先聚合 |
| public-case runner | 17 | strict public context、隐藏 ID 泄漏、投影 manifest 对齐、staged case/投影运行中漂移、失败 receipt 和 E2 seal |
| public-case sealer | 5 | 原子 ID/编码/既有目录拒绝、seal 往返和四个 catalog context 逐字节复现 |
| 场景 Skill 集群 | 5 | 路由所有权与纯文风/学术质控隔离 |
| 旧入口退休门 | 6 | 安全 intake、活跃引用归零、危险行为拒绝、fixture schema 和旧目录删除 |

工作区全量：`Ran 355 tests ... OK (skipped=1)`，即 354 项通过、1 项跳过；skip 仅因当前 Windows 账户不能创建文件 symlink；根 junction、reparse 检测和 hardlink 攻击测试均已实际执行。
官方 Skill 校验：`Skill is valid!`。  
13 个脚本均通过 `py_compile` 与 `--help`；统一验证、来源 profile、projection builder、资格 harness 和 sealer 已做真实 CLI 调用。runner 也实际启动过 Codex，但因独立 CLI 认证 401 只形成 `INFRA_INVALID` 记录，未形成前向样本。

## 13. 原 P0/P1 漏洞闭环

| 原漏洞 | 当前证据 | 状态 |
|---|---|---|
| 无独立词库和扫描器 | 28 组 JSON 信号 + 定位 CLI + 20 项扫描测试 | 已解决 |
| 绿灯只查数量 | 337 项 Humanize/projection/资格/采集链/退休行为测试；`tests_total` 明确不计资格覆盖 | 已解决 |
| 言语行为漂移 | 6 类 marker warning + request-bound proposal；本地 proposal 不放行 | 已解决到当前规则覆盖；内容语义仍需人工判断 |
| 强制制造主次 | 等权结构优先、`NO_CHANGE`、结构权限 | 已解决 |
| 正式术语误伤或漂移 | 上下文豁免、finding 级 KEEP、`--term` 次数/顺序硬比较和术语表哈希 | 已解决到显式术语表层；未提供术语表时为 `NOT_PROVIDED` |
| Diagnose/Rewrite 冲突 | 模式分支与独立输出合同 | 已解决 |
| 无作者声线 | Voice Profile 与 `SCENE_DEFAULT` 披露 | 已解决 |
| 无强度/结构授权 | LIGHT/BALANCED/STRUCTURAL + locks/scope | 已解决 |
| 长 TeX 不安全 | prepare/finalize、占位、账本、diff、回滚、幂等 | 已解决到工具链层 |
| 引语/题干/OCR 无分层 | 六类来源角色 + TeX 环境保护 | 已解决 |
| 常见句壳缺失 | 175 变体 + 40 正则族 | 已解决并持续回归 |
| 无关键词 AI 腔 | 模态密度、抽象密度、修复模板 | 已解决 |
| 推理链误伤 | 真实证明链与规范步骤豁免 | 已解决 |
| 命中后无动作 | KEEP/DELETE/REWRITE/REVIEW/NO_CHANGE/UNRESOLVED | 已解决 |
| 优先级加载不到 | 主 Skill 路由到 quick checklist/workflow/gates | 已解决 |
| 输出合同不统一 | operational contract 为唯一枚举来源 | 已解决 |
| 三场景同质 | 课堂/建模/科研独立规则、三轮 9 次盲测和 3 份人工 gold | 规则层已区分；历史样本仅作归档/回归，完整矩阵未运行，总体资格为 `NOT_EVALUATED` |
| 修复语形成新口头禅 | `HUM-16` + introduced-candidate gate | 已解决 |
| 载荷过重 | 386 行完整主路由；generator projection 会删除资格控制面，其余 reference 按需读取 | 已缓解 |
| 中文触发竞争 | Humanize 接管普通纯文风及报告辅助文风；旧 Skill 已蒸馏并删除 | 已解决，活跃目录唯一 |

## 14. 第四轮极端实践红队

前三轮证明了模型会同义规避，第四轮则不再审模型“写得像不像”，而是直接攻击完成门：构造应该失败的前后文本，观察验证器是否仍给 `PASS/0`；删除或替换快照源文件，观察长文收尾器是否仍允许声称全文完成；逐条回查规则的 provenance、示例和输出合同，观察 reference 是否会诱导模型越权。

### 14.1 短文保护门：修复前确实会误放行

| 攻击输入 | 修复前 | 根因 | 修复后 |
|---|---|---|---|
| `alignat` 环境中把 `y` 改成 `z` | `PASS/0` | scanner 保护了 `alignat`，不变量检查器没有同构环境表 | `FAIL/1`，`PROTECTED_MATH_CHANGED` |
| `exercise` 题干中把“求”改成“计算” | `PASS/0` | 题干只在扫描器中排除，没有进入硬比较 | `FAIL/1`，保护环境变化 |
| Markdown 三反引号开启、四反引号关闭的代码块内改值 | `PASS/0` | 旧正则要求 closing fence 与 opening 完全等长 | `FAIL/1`，按 CommonMark 接受更长 closing fence |
| “样本分为三组”改为“四组” | `PASS/0` | 只抽取阿拉伯数字 | `FAIL/1`，中文数词进入数字不变量 |
| 把 OCR 文本中的 `U+FFFD` 替换字符改为正常字 | `PASS/0` | UTF-8 解码成功就被视为可编辑 | `FAIL/1`，U+FFFD、PUA 和明显 mojibake 进入不可编辑异常标记 |
| “有限元方法”改成“有限差分方法” | `PASS/0` | 工具无法从任意正文自动猜出哪些字符串是正式术语 | 提供 `--term 有限元方法` 后 `FAIL/1`，术语清单数量和 SHA-256 进入 evidence |

这里最重要的改动不是继续追加禁词，而是把 scanner 和 invariant checker 的保护语法做成同构合同。扫描时被标为题干、正式陈述、数学或代码的内容，改写后不能因为换了一个脚本就失去保护。

显式术语表采取保守设计：

- `--term TERM` 可重复使用；
- 比较术语的出现次数与顺序，变化即硬失败；
- evidence 记录去重术语数、清单哈希和状态；
- 未提供术语表时明确写 `NOT_PROVIDED`，不得声称“全部术语已自动核验”；
- 这不取代公式、命令、数字、引语和代码等已有自动保护。

### 14.2 人工豁免不能再靠一句空话

旧实现只数理由里的汉字个数。因此“确认保留”“人工确认”虽然没有说明表达功能，也能把 `REVIEW` 降成 `PASS`；同一个 signal ID 还会一次豁免全文所有同类命中。

当前合同改为：

1. 拒绝“确认保留、人工确认、已经检查”等通用裁决套话；
2. 单一命中可按 signal 裁决，多命中必须使用 `SIGNAL_ID@LINE:COLUMN` 或 finding hash 绑定具体位置；
3. 每个 finding 都带稳定 SHA-256，JSON 输出 `accepted_findings`；
4. 被接受的 warning 也写入独立审计账本；
5. 改后文件 hash 变化后，旧裁决不能被当作新版本证据。

这仍然不是自动判断理由真假。它解决的是“裁决对象不明确”和“空泛四字理由直接放行”，最终语义判断仍属于人工复核。

### 14.3 豁免必须贴着当前命中

原 exclusion 使用整句搜索。输入“闭环控制用于调节，该报告形成完整闭环”时，前半句的正式术语“闭环控制”会把后半句的管理空壳“形成完整闭环”一起豁免。

修复后，排除模式必须与当前 finding 的字符范围重叠。上述句子现在保留后半句候选，统一验证返回 `REVIEW/2`；真实的“闭环控制系统”仍然可以 `KEEP`。这条规则同样适用于“机械抓手/核心抓手”“门禁系统/放行机制”等一词多义场景。

### 14.4 不可读文件继续处理，但不能静默算作已覆盖

用户要求乱码不要拖慢进度，所以行为不是“遇到一个坏文件就停止”，而是：

- scanner 继续扫描其他可读文件；
- JSON 固定输出 requested、scanned、skipped 文件数与跳过原因；
- 存在非法 UTF-8 时整体返回 `REVIEW/2`，不能用 `finding_count=0` 冒充无问题；
- 长文 prepare 对 UTF-16、NUL、异常 C0/C1 控制字符标 `SKIPPED_GARBLED`；
- 被跳过内容保持原字节，不猜字、不补写，并阻断全文完成声明。

### 14.5 规则合同自身也接受红队

| 合同漏洞 | 风险 | 修复 |
|---|---|---|
| 改写范例凭空补出资源、捕食、扰动、状态方程等对象 | 低优先级示例会正常化事实补造 | 删除补造对象，改为只重排输入已经给出的成分 |
| 范例把 `q(x),s(x),\phi(x)` 改成 `q,s,\phi` | 数学对象表面相近但含义可能变化 | 改后保持原函数记号 |
| `STYLE-DIAGNOSE` 与 `DIAGNOSE` 两套枚举并存 | 不同 reference 会给出不同模式名 | 统一为 `DIAGNOSE/REWRITE/DRAFT`，操作合同是唯一 schema 来源 |
| Diagnose 有五字段、七字段和八字段版本 | 输出无法稳定验收 | 固定字段并由合同测试精确断言 |
| 4 处 provenance 指向错误规则号 | 命中后会加载无关章节 | 修正目标并校验具体 section/rule，不再只查字符串在文件某处出现 |
| Voice 模板缺结果报告、观察归属、公式/图表引入等字段 | Profile 保存再加载会丢言语行为 | 补齐字段并增加 round-trip 契约测试 |
| 旧 AIGC Skill 与纯文风 Skill 同时抢“去 AI 味” | 路由不唯一，且旧规则含检测操纵与虚构风险 | 安全报告定位能力并入本 Skill，危险规则拒绝迁移；旧目录删除 |
| `UNRESOLVED` 一处允许全文完成、一处禁止 | 人工可挑宽松条款夸大完成范围 | 统一为任何未决/乱码/快照变化都只能 partial |

### 14.6 长文发布链的七个 P1

长文黑盒复测后来发现一个 P0：finalize 曾信任可篡改的 `units.jsonl` 终态，可在无 rewrites 时伪造全文完成；现已用 `prepare_integrity.json` 修复，并加入篡改、chunk 篡改和清单缺失回归。另有此前记录的七个会破坏完成账本可信度的 P1：

| 漏洞 | 修复前错误行为 | 当前行为 |
|---|---|---|
| 快照后删除源文件或把文件换成目录 | 直接跳过，`source_files_changed_since_snapshot=0`，可 full | 记录 source change，阻断 full |
| `\input{\chapterdir/chapter}` 等宏路径 | 静默漏收 include，仍可 full | manifest 写 `UNRESOLVED_INCLUDE`，prepare/finalize 均 `REVIEW` |
| UTF-16LE 被误按 GB18030 解码 | 含大量 NUL 的文本仍标 READY | UTF-16、NUL、控制字符标 `SKIPPED_GARBLED` |
| 把只读相邻段复制进 owner | 相邻段在最终稿重复两次仍 PASS | 拒绝复制四字符以上的规范化只读上下文 |
| 保留占位符同时再粘贴一份裸标题/题干 | 保护内容次数增加仍 PASS | 规范化 CRLF/LF 后核对保护 span 次数与顺序 |
| 第二批 partial 只提交新单元 | 第一批已接受改写被快照原文覆盖 | rewrites 必须累计；回退尝试 FAIL 并保留旧 partial |
| 非幂等 full 重跑 | 旧正文保留，但 diff/ledger/manifest 被新失败尝试覆盖 | 已发布证据原子保留；失败候选不替换正式证据 |

这些修复带来两个明确兼容性要求。第一，manifest 消费方必须识别 `UNRESOLVED_INCLUDE`；第二，已有 partial 后续提交必须包含此前已接受且仍有效的 rewrites。两者都是有意收紧：宁可拒绝不完整的增量输入，也不能悄悄丢失已验收修改。

### 14.7 红队后的可复核结果

- Humanize、来源候选门、长文、generator projection、资格审计、public-case 采集链、场景路由和退休门：`318/318`；
- 工作区全量：`336/336`（1 项文件 symlink 环境测试因 Windows 权限跳过，根 junction 测试已执行）；
- `humanize-academic-chinese` 通过官方 `quick_validate.py`；
- 13 个脚本均通过 `py_compile` 与 `--help`；
- `physics1.tex` 原 v2 目录重跑仍为 snapshot `cd5fc9b656012aad`、60 units、51 `PENDING`、9 `SKIPPED_PROTECTED`、`REVIEW/2`、`full_completion_claim_allowed=false`、`idempotency=PASS`。

测试通过只证明这些已编码合同，没有证明任意未来文本都能被完整识别。完整前向 evidence manifest 尚未建立，因此生成模型总体资格只能写 `NOT_EVALUATED`，不能写“模型已稳定通过”。

### 14.8 资格自证攻击与 manifest v2

独立审计复现了一个最小假阳性：`MODE-01` 的输出故意不含 DIAGNOSE 九列表格，
`context.json` 还明示存在期望答案，但旧 manifest 只要自填
`assertions[].result=PASS`，harness 就会把该 atom 记为 PASS。问题不在 hash 缺失，而在
“答案与评分都由提交者拥有”。

现行 v2 把评分所有权移到 Skill 内固定 catalog：

- claim 只有 `claim_id/atom_id/oracle_suite_id`，不能自选 check 或提供 result/expected；
- suite 固定完整 required-check 集、fixture hash、期望机器字段和 rubric；
- requirements、contract、catalog、Skill snapshot、run record 和 public artifacts 均进入当前 bindings；
- v1 current case 直接触发 integrity failure，v1 archived case 永远不贡献 PASS；
- 确定性 FAIL 先于证据等级不足和主观 review 聚合，一项 FAIL 加一项缺失仍然是 FAIL；
- caller-declared MODEL/HUMAN review 只保留 `declared_outcome`，固定
  `qualification_eligible=false`，不能替确定性检查放行。

当前 catalog 只完成第一批垂直切片：`MODE-02`、P0 `ROLE-02`、
`PATH-05/positive + review`、`LONG-01` 和自动 `PROTECTED/hash-zero`，共 5 个 suite、
11 个 check、1 个 rubric。所有 suite 明示 `SHADOW`、`runner_compatible=false`。四份
`public_context` 已统一为 `humanize-generation-public-context/v1`，并由 sealer 使用同一参数
逐字节重建；这修复了早期静态 context 与真实 runner context 永远 hash 不相等的问题。

本地 runner 没有把 `--ephemeral` 或 `-s read-only` 当作盲性证明。它记录完整 Skill 中的
oracle catalog 对生成器可见、宿主机排除目录不可达未验证，因此 evidence cap 为 E2。首次
真实采集 `run-001` 因复制快照漏掉 Skill `build/` 而在模型调用前失败；修复并加入回归后，
`run-002` 启动独立 Codex 进程并保存事件流，但 CLI 认证返回 401，最终无 output、无 run
record、无 E3。失败没有被删除或改写成行为样本。

机器复核结果是：无 manifest 时 `integrity=PASS`、`qualification=NOT_EVALUATED`、
163 个 atom 全部未评测；旧自证证明包现在 `integrity=FAIL`、`atoms_pass=0`；合法 v1
归档 fixture 为 `integrity=PASS` 但仍是 163 个 atom 未评测。这个结果比“完成了 5 个 suite”
更重要：当前系统会拒绝不应获得的完成态，但尚未取得完整生成资格。

三份完整机器报告分别见
[no-manifest.json](build/qualification-v2-audit-20260714/no-manifest.json)、
[legacy-false-positive.json](build/qualification-v2-audit-20260714/legacy-false-positive.json) 和
[official-archived.json](build/qualification-v2-audit-20260714/official-archived.json)。本地真实调用的
E2 边界与认证失败见 [runner-receipt.json](build/qualification-local-runner-20260714/run-002/runner-receipt.json)；
原始 events 含服务端错误细节，只作为受限运行痕迹，不在报告中转录。

### 14.9 固定 trust root、generator projection 与 v2 证据四件套

在 manifest v2 与固定 oracle 之后，红队继续攻击 E3 的信任来源，确认旧
`_blind_forward_state` 会直接相信 run record 自报的三个字段：
`oracle_catalog_visible_to_generator=false`、`filesystem_isolation_verified=true` 和
`HARNESS_VERIFIED_GENERATOR_PROJECTION`。当 suite 以后改成 runner-compatible 时，这个入口会让
调用方自己给自己签发 E3。现行实现新增固定
`generation-qualification-trust.json`，其 `production_e3_enabled=false`、accepted receipt schemes
为空；修改 JSON 试图启用 E3 会被代码拒绝，调用方自报隔离成功则进入
`REJECTED_UNTRUSTED_ISOLATION_CLAIM`、integrity `FAIL`，最多保留 E2。

生成器也不再看到完整 Skill。固定 policy 将 62 个旧源项扩展后的当前 Skill 全部分类：25 个
生产能力文件原样保留，`SKILL.md` 只允许删除“验证 Skill”“生成资格审计”两条路由和整个资格
采集章节，最终投影恰为 26 个文件。oracle、requirements、trust policy、qualification fixtures、
auditor、runner、sealer、builder、build 和 cache 全部排除。policy 不只批准路径，还批准 capability
source hash；生产文件即使只增加一句无控制词正文，也必须显式更新批准 hash，不能借白名单路径
偷渡 expected/rubric 内容。

builder 对未知文件、UTF-8、frontmatter、fenced heading、相邻 H2、引用闭包、隐藏 suite/check/rubric
ID、大小写/NFC 冲突、symlink/reparse/hardlink、额外空目录和源文件 TOCTOU 逐项 fail-closed。
manifest 写在投影外，发布失败会回滚已发布投影。同一 source/policy/builder 重建得到相同 tree；
本轮正式产物为 26 文件，tree
`f6d783c0e48533a2704d8ad2286de735b10d6cf29baabc343a3bca368a329dc0`。

runner 不再相信 builder 的返回字典，而是 strict parse canonical manifest 并逐字段对齐；启动前和
退出后都按 lstat、路径、字节、hardlink identity 与 tree hash 复核投影，同时复核生成器实际读取的
`execution/case`。运行中改 staged input 或投影时，只留下明确
`runner_status=INFRA_INVALID`、`projection_audit_status=FAIL` 的 receipt，不生成 run record 或 seal。
公开 prompt 也删除了“去找 tests/gold/oracle”的反向提示，case ID、文件名、正文、prompt 和 locked
literal 中的隐藏控制 ID 会在 invoke 前拒绝。

current case 的 run record 升为 `humanize-generation-run-record/v2`。它必须提交 canonical
projection manifest、runner receipt、run record、run seal、public prompt/context；auditor 会从当前
完整 Skill 独立重建投影，再交叉核对四类 artifact、staged-case hash、public seal 和嵌套 provenance。
删除任一证据、伪造 projection tree、让 receipt 与 record 冲突或混写隔离字段，均为 integrity
`FAIL`、`atoms_pass=0`。`request/context.json` 明确是 capture context，不冒充生成器上下文；CLI
无法捕获 system/developer messages，因此 `generator_context.complete=false`。

这些改动没有把本地执行升级成 E3。投影只能证明
`oracle_catalog_present_in_projection=false`；本机仍继承用户 profile，宿主 oracle、工作区和完整
Skill 不可达未获外部证明，状态仍是
`oracle_catalog_unreachable_to_generator=UNVERIFIED`、`filesystem_isolation_verified=false`、
`evidence_cap=E2`。最新无 manifest 机器审计见
[no-manifest.json](build/qualification-v3-audit-20260714/no-manifest.json)：
`integrity=PASS`、`qualification=NOT_EVALUATED`、163 个 atom 全部未评测、
`production_e3_enabled=false`。

### 14.10 第七至第九轮：验证器绿不等于正文自然

2026-07-14 又用同一组三个最小输入做了三轮 fresh-context 前向测试。每个代理只拿正式 Skill、指定输入和普通用户式配置，不提供预期答案，不允许读取测试、旧输出、报告或资格材料。输入固定为：

- `COURSE`：含“值得注意的是、必须牢记、具有重要意义、为后续学习奠定基础”和一个必须逐字保护的 `equation`；
- `MODELING`：含编辑后台语言、四个数学跨度、七组数字/单位、误差—耗时代价、多重缓和、闭环拔高和自动展望；
- `RESEARCH`：含三个观察、范围限制、不能区分的两类原因，以及“系统梳理—深入探讨—奠定基础”链。

第一轮 v7 的机器结果全部是 `PASS/0`，但独立评估代理连续阅读立即推翻其中两项：

| 场景 | v7 机器状态 | 人工发现 | 有效判定 |
|---|---|---|---|
| COURSE | `PASS/0` | `必须牢记` 被换成 `公式必须记清楚`，仍是说教同义壳 | 阻断 |
| MODELING | `PASS/0` | 编辑要求变成“表格列出”；抽象支撑变成“用于工程决策”；多重缓和变成“影响程度或许有限”；去掉“后续工作”标签后仍留空展望 | 阻断 |
| RESEARCH | `PASS/0` | 限定保持良好，但“本文据此梳理相关现象，讨论可能原因”没有正文兑现 | 可修改后通过 |

盲评原文和实践红队分别保存在 [blind-quality-review.md](build/maturity-v7-forward-20260714/blind-quality-review.md) 与 [practical-redteam.md](build/maturity-v7-forward-20260714/practical-redteam.md)。这轮证明原先的“数字、公式、词项和模态计数都绿”仍看不到跨版本命题升级。

本轮据此增加的不是一批抽象口号，而是四组可失败抓手：

1. **谓词来源门**：每个改后独立分句只能登记为 `COPY`、`ENTAILED_PARAPHRASE` 或 `DELETE_STYLE_SHELL`；显式拒绝 `NEW_PREDICATE`、`SPEECH_ACT_UPGRADE` 和 `MODALITY_TO_DEGREE`。
2. **跨版本确定性 warning**：统一验证器现在识别 `SPEECH_ACT_DIRECTIVE_TO_COMPLETION`、`SPEECH_ACT_SUPPORT_TO_ACTUAL_USE` 和 `SPEECH_ACT_MODALITY_TO_DEGREE`。v7 建模稿重新验证后同时命中三项，并保持 `REVIEW/2`。
3. **同义逃逸与去标签展望**：`需要记住/需要记清楚/要记住` 归入课程说教簇；`应用场景可以进一步拓展` 即使没有“未来/后续工作”也归入 high 自动展望；`数据仍需在正文中保留` 继续算编辑后台语言。
4. **语料动作锚进入普通改写**：`COURSE`、`MODELING`、`RESEARCH` 场景文件直接暴露由既有 MD/TeX 人工复读蒸馏的动作卡。每个可编辑单元最多选两张，缺少输入锚点时写 `NONE_APPLICABLE`，不能为使用语料而迁移来源事实或句子。

第二轮 v8 显示生成行为开始改变，但仍未成熟：

- 建模稿不再虚构工程决策、不再把多重缓和写成“影响有限”、不再保留空展望；但仍写“数据仍需在正文中保留”，属于诚实但不够可用的 `REVIEW`；
- 科研稿删除了未兑现作者动作，并诚实停在删除“可能”后的模态 `REVIEW`；
- 课程稿把“必须牢记”换成“公式需要记住”，暴露第二个同义逃逸。

v8 还暴露了评审可靠性问题。一个盲评代理把“公式需要记住”判为自然，甚至建议换成“应记住”；主代理没有采用这一结论，而是把整组“必须/务必/需要/要 + 牢记/记住/记清楚”纳入同一功能簇。这说明单个模型盲评不能作为 E4，也不能替代多评审分歧记录。

第三轮 v9 的行为进一步收敛：

| 场景 | v9 正文行为 | 统一状态 | 实际意义 |
|---|---|---|---|
| COURSE | 直接删除空泛记忆命令，保留公式、条件与纠偏链；使用 `COURSE-ERROR-01` | `REVIEW/2` | 文风正文明显改善；删除 `必须` 触发模态复核，未用同义词骗绿 |
| MODELING | 删除拔高、闭环和展望，保留数值取舍；对编辑要求明确登记 `UNRESOLVED`，`corpus_action=NONE_APPLICABLE` | `REVIEW/2` | 没有事实升级，但正文仍残留编辑备注，不能称可直接交付 |
| RESEARCH | 删除未兑现作者动作，把原有“可能”收回“可能原因”范围句；使用 `RESEARCH-SCOPE-01` | `PASS/0` | 三层验证均通过，未恢复套话或补造机制 |

v9 产物见 `build/maturity-v9-forward-20260714/`。课程输入本身含“速度随时间减小即可直接套用匀变速公式”的内容问题；纯文风 Skill 按合同没有暗中修正，并保持 `academic_correctness=NOT_EVALUATED`。这不是文风通过能覆盖的教学正确性结论。

对建模过度保守的后续修复允许从编辑指令中回收**同层字面载荷**：例如“正文里要保留三组数据，温度分别为 20 ℃、25 ℃ 和 30 ℃”可写成“三组数据的温度分别为……”，但不能声称表格已列出、实验已采用或数据已用于模型输入。

这项规则的前两次独立 v10 尝试分别遇到模型容量错误和运行挂起；第三次 `v10c` 取得了新鲜样本：

```text
我们构建温度响应模型 R(T)=aT+b。数据温度为 20 ℃、25 ℃ 和 30 ℃，共三组。
参数 a 在 [0.8,1.2] 内进行扫描。结果表明，当 a=1.06 时，验证集误差由 8.1% 降至
5.4%，但计算时间由 31 s 增至 44 s。

模型可能仍会受到传感器漂移影响。
```

这里没有编辑备注、表格完成事实、工程决策、影响程度结论或自动展望。代理选择 `MODELING-PROCESS-OUTCOME-SEPARATION-01`，把误差下降与计算时间上升保留为反向取舍。第一稿曾把“三组”移到温度数值前，统一验证器以 `NUMBER_OR_UNIT_CHANGED/FAIL/1` 拦截；调整回原数字顺序后，硬不变量和文风信号通过。最终仍因删除 `可以/或许` 并压缩多重缓和而保持 `SPEECH_ACT_MODALITY_SCOPE_CHANGED/REVIEW/2`，没有为变绿恢复套话。产物见 `build/maturity-v10c-forward-20260714/modeling/`。

本轮可复核机器状态更新为：

- 工作区共运行 355 项：354 项通过，1 项 Windows 文件 symlink 权限测试跳过；
- 13 个 Skill Python 脚本全部通过 `py_compile` 与 `--help`；
- `quick_validate.py` 在 `PYTHONUTF8=1` 下返回 `Skill is valid!`；
- 来源 profile 为 50 张 action card 可用、0 不可用、23 个来源可读，`source_text_exported=false`；
- 新 generator projection 为 26 文件，tree `f1c619cfedb2244f05d12679bdc2ed7535b929dc8d3b601fe7888a811ce16f5e`，证据上限仍为 E2；
- 无 manifest 审计为 `integrity=PASS`、`qualification=NOT_EVALUATED`、`atoms_pass=0/163`、`production_e3_enabled=false`。

机器产物见 [maturity-v10-action-profile-20260714.json](build/maturity-v10-action-profile-20260714.json)、[generator projection manifest](build/generator-projection-maturity-v10-20260714-manifest.json) 和 [no-manifest qualification audit](build/qualification-maturity-v10-20260714-no-manifest.json)。因此当前更准确的成熟度表述是：**拒绝虚假完成和常见跨命题升级的工具链继续成熟，三场景最小前向行为已明显改善，建模字面载荷已有新鲜盲写证据；完整 163-atom 生成资格仍未评测。**

### 14.11 第九轮：接通 DRAFT、校正 DIAGNOSE/GENERAL，并拆开长文“覆盖完成”与“Humanize 完成”

本轮没有继续堆禁词，而是先对 `DRAFT / DIAGNOSE / GENERAL / Voice Profile / 长文 / 资格 catalog`
做三路隔离审计。审计代理只读正式生产文件，不读 tests、旧 build、历史报告和 oracle；完整报告见：

- [modes-audit.md](build/maturity-v11-audit-20260714/modes-audit.md)；
- [long-voice-audit.md](build/maturity-v11-audit-20260714/long-voice-audit.md)；
- [qualification-audit.md](build/maturity-v11-audit-20260714/qualification-audit.md)。

模式审计给出 3 个 P0、6 个 P1。最关键的不是“DRAFT 写得是否顺”，而是此前 DRAFT 没有进入
frontmatter 的自然触发面，也没有 supplied content 到草稿的独立验证语义，却允许运行记录直接写
“未补造”。DIAGNOSE 的 `Dominant/Recurring/Local` 还可能被 scanner 的 `high/medium/low` 错当
同一轴；扫描命令默认隐藏 protected/excluded finding，却又要求诊断表披露来源角色。GENERAL
则只有负向边界，没有正向语料卡，并且原 guard 把任意三个“必须”视作动员腔，会误伤三个不同
法定义务主体。

长文/Voice 审计给出 5 个 P0、7 个 P1。当前 prepare/finalize 确实能证明快照、保护区、逐单元
验证、格式门和源文件不覆盖，但不能证明：

- 作者 Profile 被建立并以 id/version/hash 绑定到 unit、chunk、rewrite bundle 和 final metadata；
- `AUTO` 已逐单元落成 `COURSE/MODELING/RESEARCH/GENERAL`，而不是把字符串 `AUTO` 原样传下去；
- 各块没有共同生成新的修复口头禅；
- `NO_CHANGE` 来自完整阅读而不是批量四字理由；
- 把 clean 输出交给 fresh agent 再跑一遍已经收敛，而不是同一 rewrite bundle 组装出相同字节。

因此，原来的 `full_completion_claim_allowed=true` 语义过宽：逐块保护 PASS 可能掩盖全文已经被
场景默认声线压成统一“克制腔”。本轮先做诚实完成态拆分，暂不伪造尚不存在的 Profile builder
或全文声线算法：

| 字段 | 当前可证明内容 | 当前状态规则 |
|---|---|---|
| `coverage_completion_claim_allowed` | 快照、覆盖、局部保护、格式/编译门闭合 | 现有 finalize 可真实计算 |
| `assembly_replay_idempotency` | 同一 rewrite bundle 再组装的派生字节相同 | 兼容旧 `idempotency`，不得称二次 Humanize |
| `scene_routing_status` | unit 已有非 AUTO 场景标签 | `AUTO` 保持 `NOT_EVALUATED` |
| `voice_binding_status` | hash-bound Profile 已进入正式工件链 | 当前固定 `NOT_EVALUATED` |
| `voice_conformance_status` | 全文符合所绑定 Profile | 当前固定 `NOT_EVALUATED` |
| `cross_unit_repetition_status` | 已运行跨 unit 新增模板门 | 当前固定 `NOT_EVALUATED` |
| `humanize_second_pass_convergence` | clean 输出作为新输入由 fresh pass 重跑后为空 patch | 当前固定 `NOT_RUN` |
| `humanize_completion_claim_allowed` | 上述 Humanize 级门全部通过 | 当前固定 false |
| `full_completion_claim_allowed` | 兼容别名 | 与 `humanize_completion_claim_allowed` 相同，当前 false |

这意味着现阶段即使 finalize 的局部执行 `status=PASS`，也只能声明覆盖与局部保护闭合，不能声明
“全文 Humanize 已完成”。这是有意拒绝旧假完成态，不是把可用的结构工具判成失败。

#### DRAFT 的真实接通与三轮前向轨迹

正式入口已经补入“按要点、事实表、研究记录或课程材料起草”的自然语言触发；
`agents/openai.yaml` 也同步声明 supplied-content 起草，缺口省略或占位。统一验证器新增
`--mode DRAFT`，第一个 artifact 解释为供应材料而非“改前稿”。它不再要求所有供应材料必须
原样保留，而是检查草稿新增的可机械载荷：

- 数字与单位；
- 数学跨度；
- 代码与正式环境；
- 关键 TeX 命令、引用、标签和 URL；
- 直接引语；
- 乱码跨度；
- 归因/文献来源标记；
- 调用方显式保护术语。

未供应载荷为硬 `FAIL/1`；表面子集通过写 `draft_surface_source_check=PASS`。但该门不伪装成
完整中文蕴含证明：只要不是 supplied artifact 的逐字 copy，
`semantic_source_check=NOT_EVALUATED`，最终状态至少为 `REVIEW/2`。因此运行记录只能说
“未发现已编码的表面新增载荷，语义来源待复核”，不能再说“未补造已验证”。

研究 DRAFT 输入直接取自此前登记的 `main.tex` 事实与口径：1.800/1.805/0.26%、
2.200/1.838/16.47%、0.204、4.213，以及“硬锚点校准—局地一致性检验—非独立外部验证”
的角色边界。三轮输出的关键变化如下：

1. v11 首稿事实和全部载荷均正确，但开头写“需要区分报告”，仍像编辑要求；旧 REWRITE
   validator 还把供应材料中的“不提供……”省略误报成否定删除。红队逐句回指判正文事实 PASS，
   但运行记录的机器执行声明没有独立 artifact 证据。
2. v11b 自然任务没有写 Skill 名，fresh agent 仍自动进入 `DRAFT/RESEARCH`，表面门 PASS、
   语义门 `NOT_EVALUATED/REVIEW/2`；但正文把编辑后台移动成“需要分开报告”，说明只接通模式
   不等于已经去掉 meta-writing。
3. 正式 Skill 随后把 supplied unit 分成 `FACT_PAYLOAD / EDITORIAL_REQUIREMENT /
   FACT_BOUNDARY`：编辑要求只决定组织，字面事实可回收，动作句不进入正文。v11c fresh 输出直接
   用三个段落分别呈现总量校准、局地检验和恢复/承压，没有“本节需要、正文应、需要分开报告”。
   精确复验为：`draft_surface_source_check=PASS`、三层保护均 PASS、
   `semantic_source_check=NOT_EVALUATED`、最终 `REVIEW/2`。

产物分别见 `build/maturity-v11-forward-20260714/`、
`build/maturity-v11b-forward-20260714/` 和
`build/maturity-v11c-forward-20260714/`。这条轨迹保留了失败稿，没有只展示最终好看版本。

#### DIAGNOSE 与 GENERAL 的实测修复

自然建模原则段的 v11 诊断没有把“三条原则、标题层级、两次如果—那么”强判成模板，而是分别
给出 KEEP/NO_CHANGE；但它为每个自然段都造一行“非病灶”，且只自述连续阅读，没有 protected
审计证据。正式合同随后将两套 severity 分离，并规定 3—8 是“病灶类型”上限，不是 3—8 个
抽样位置；每类在 `Location/Trigger` 中给作者 occurrence 数与位置，DIAGNOSE 扫描固定使用
`--include-protected --include-excluded`。

v11b 引语盲测中，fresh agent 实际扫描 4 个 finding：作者正文 1 个、quoted/protected 3 个、
excluded 0 个。表中只把引语外一次“值得注意的是”列为 `Local`；引语内 3 个词项命中全部写
`KEEP/protected`，没有进入作者复用数，也没有把 scanner high 错报为 Dominant。运行记录保存了
两条真实扫描命令与计数，并明确统一改写验证器 `NOT_RUN`。

GENERAL 法学 DRAFT 使用三个供应事实：行政机关、平台经营者、数据处理者分别“必须”履行不同
义务。旧 guard 会因“必须×3”命中 mobilizing command；新 guard 只有出现受众主体与
“牢记/掌握/积极行动”等命令语境时才成立。fresh 输出保留三个主体与恰好三个“必须”，
不补法条、立法目的、例外、效果或价值评价；GENERAL 按合同写
`corpus_action_support=NONE`，不伪造动作卡，最终同样因语义来源未评估保持 `REVIEW/2`。

#### 百分号保护区误判：人工读真实输出发现的跨路径漏洞

v11b DRAFT 仍含“需要分开报告”，但新词项扫描最初返回 0 finding。向下检查不是词库失效，而是
Markdown 行内的 `16.47%` 被 `ProtectedIndex` 当成 TeX 注释起点，同一行余下文本全部被静默
保护。这个漏洞会同时让三条路径漏检：

1. 短文词项扫描；
2. 候选门的来源复制和 negative guard 作者视图；
3. 长文 prepare 的 protected span 与 chunk。

修复后，保护语法显式接收 `document_format`：只有 `.tex/.ltx` 把未转义 `%` 解释为注释，
Markdown 的百分比保留为作者正文。真实 v11b 输出现在能稳定报：

```text
LEX-META-01/high/DELETE 需要分开报告
```

并新增 scanner 与 long-prepare 两条回归，证明 `16.47%` 后面的正文既能进入 chunk，也能被词项
门发现。projection builder 还因 Windows 默认 GBK 调用官方 quick validator 失败，现已固定用
`python -X utf8` 启动；这同样来自真实构建失败，不是预设规则。

#### 本轮机器状态与资格边界

- 全量自动化：362 项，361 通过，1 项 Windows 文件 symlink 权限测试跳过；
- 13 个脚本全部通过 `py_compile` 与 `--help`；
- 官方 `quick_validate.py` 返回 `Skill is valid!`；
- 来源动作 profile：50 张可用、0 不可用，GENERAL 仍为 `CORPUS_INSUFFICIENT`；
- 26 文件 generator projection tree：
  `24e2e7adad152e88329bcc12928470e01d896546d6d6a3274062e056f04fc7f4`；
- no-manifest 资格审计：`integrity=PASS`、`qualification=NOT_EVALUATED`、
  `atoms_pass=0/163`、`atoms_not_evaluated=163/163`、本地 evidence cap=E2、
  `production_e3_enabled=false`；
- 固定 oracle catalog 仍只有 5 个 SHADOW suite。本轮资格审计虽已给出下一批 11 个纵向 suite
  的精确设计，但没有把“设计完成”写成“资格覆盖已实现”。

机器产物见 [maturity-v11-action-profile-20260714.json](build/maturity-v11-action-profile-20260714.json)、
[generator projection manifest](build/generator-projection-maturity-v11c-20260714-manifest.json) 和
[no-manifest qualification audit](build/qualification-maturity-v11c-20260714-no-manifest.json)。

本轮准确结论是：DRAFT 已从“合同里写着能起草”推进为自然可触发、表面载荷可拦截、语义来源
不会虚假 PASS 的生产入口；DIAGNOSE 和 GENERAL 的两个实测误区已修；长文完成声明已诚实降格。
但 hash-bound Voice Profile、逐 unit AUTO 路由、全文声线/跨块重复门、可信 NO_CHANGE evidence、
fresh second pass 与 append-only 局部回退仍未实现，不能称完整成熟。

## 15. 仍然存在的边界

以下事项没有被包装成“已完全解决”：

1. 扫描器是可审计规则系统，不是完整中文分词器或作者身份检测器；新语料仍可能出现未登记同义变体。
2. TeX 长文解析器是保守结构解析，不是完整 TeX AST。无法静态展开的宏 include 或嵌套会标 `UNRESOLVED_INCLUDE/UNRESOLVED`。
3. 长文工具不自动写正文；它控制模型/人工改写的输入、保护、验收和发布。
4. 编译门依赖项目现有命令；未提供时准确记录 `NOT_RUN`，不会伪装通过。
5. 盲测证明模型仍会同义规避。任何没有验证记录的直接生成都不能视为生产交付。
6. 本地 warning proposal 只是处理建议，不能证明真人身份或清除 `REVIEW`；finding 级 KEEP 仍需针对具体位置说明表达功能。
7. 术语保护只对显式 `--term` 清单给出硬证据；未提供时状态为 `NOT_PROVIDED`。
8. 固定 oracle catalog 目前只覆盖 5/163 个垂直 atom，且全部处于 SHADOW；它不是完整评测矩阵。
9. 本机没有 Docker、可用 WSL 发行版或 Windows Sandbox 隔离执行器；28 文件投影虽不含 oracle，但宿主排除根不可达仍未验证，本地 runner 只能到 E2。
10. 独立 Codex CLI 最近一次真实采集认证返回 401，尚未产出一条符合 v2 四件套的新模型 output；修复外部认证后也必须新建 run，不能补写旧 receipt。
11. 生成模型完整评测矩阵尚未运行，当前总体前向资格为 `NOT_EVALUATED`，不能自动发布盲写结果。
12. 本工具不承诺任何 AIGC 检测结果。
13. Voice Profile 已进入可重建生产链，但 hash 绑定仍只证明工件身份；全文声线符合性、跨块修复语重复与 fresh second pass 尚未实现。
14. 长文 `scene=AUTO` 仍未逐 unit 解析；当前诚实写 `scene_routing_status=NOT_EVALUATED`，不能把 AUTO 字符串当路由完成。
15. `NO_CHANGE` 当前仍不能证明主观“完整阅读”；四字理由虽有局部门，缺少位置化 voice evidence 与跨 unit 理由复用门。
16. `assembly_replay_idempotency` 不等于 fresh second-pass 收敛；后者未运行时固定 `NOT_RUN`。

## 16. 常用命令

短文扫描：

```powershell
python scripts/scan_humanize_chinese.py input.tex --scene AUTO --format text
```

单独硬保护检查：

```powershell
python scripts/check_humanize_invariants.py before.tex after.tex --json
```

统一交付验证：

```powershell
python scripts/validate_humanize_output.py before.tex after.tex `
  --mode REWRITE `
  --scene COURSE `
  --format json
```

supplied-content DRAFT 表面来源验证：

```powershell
python scripts/validate_humanize_output.py supplied.md draft.md `
  --mode DRAFT `
  --scene RESEARCH `
  --format json
```

该命令即使表面来源门通过，也会在自然语言蕴含未获得可信逐分句 review 时返回
`semantic_source_check=NOT_EVALUATED` 与 `REVIEW/2`；不要把它手改成 PASS。

带本地处理 proposal（仍返回 `REVIEW/2`）：

```powershell
python scripts/validate_humanize_output.py before.tex after.tex `
  --scene RESEARCH `
  --term "有限元方法" `
  --keep-reason "LEX-RESULT-01@12:4=此处承担有数据对象的结果报告" `
  --propose-warning-resolution "<warning_fingerprint>=建议核对是否只合并重复缓和" `
  --warning-review-request-sha256 "<request_sha256>" `
  --warning-reviewer-kind HUMAN `
  --warning-reviewer-id "<调用方标签>"
```

长文准备与收尾：

```powershell
python scripts/prepare_humanize_long_document.py main.tex --output <run-dir> --scene AUTO
python scripts/finalize_humanize_long_document.py --run-dir <run-dir> --rewrites <rewrites-dir>
```

生成资格 public case 与本地 E2 采集：

```powershell
python scripts/seal_humanize_public_fixture.py input.md request.txt `
  --output <new-public-case> --case-id <id> `
  --mode REWRITE --scene RESEARCH --intensity BALANCED `
  --output-format CLEAN --scope selection

python scripts/run_humanize_generation_trial.py <new-public-case> `
  --output <new-run-dir> --format json

python scripts/audit_humanize_generation_qualification.py <manifest-v2.json> `
  --artifact-root <evidence-root> --format json
```

本地 runner 成功也只表示 `CAPTURED_E2`；没有外部隔离 receipt 时不要把命令输出改写为 E3。

## 17. 最终定位

这个 Skill 不是“把所有论文改成一种克制模板”，也不是“列一串 AI 禁词”。它把 Humanize 拆成四个可观察动作：

1. 找到真实模板信号；
2. 保护不可改对象和言语行为；
3. 在授权范围内改变节奏、句壳和段落职责；
4. 用文件 hash、候选差异、diff 和覆盖账本证明完成范围。

最重要的工程结论是：

> 规则负责提出候选，模型或编辑者负责改写，验证器负责拒绝无证据的“已完成”。

## 18. v12：Voice Profile 从说明文档变成可重建工件

### 18.1 为什么还要继续改

v11c 已经能诚实区分 `coverage_completion_claim_allowed` 与全文 Humanize 完成，但 `voice_binding_status` 仍固定为 `NOT_EVALUATED`。这留下了一个很具体的工程空洞：长文 chunk 虽然写了 `scene`，却没有冻结“本次到底使用哪一个 Voice Profile”；生成端也不用回显 Profile 版本。只要 Profile 在 prepare 与 finalize 之间发生变化，或者旧 bundle 被搬到新 run，原流程无法定位错配。

第一轮只读审计又把问题拆成三层：

1. Profile 自身必须有稳定 schema 与自哈希；
2. prepare 必须把同一身份写入 metadata、unit、chunk、ledger 和完整性封条；
3. rewrite bundle 必须回显当前 hash，finalize 必须在正文验证前拒绝缺失、非法和错配值。

这里不能把“hash 一样”写成“声线符合”。hash 只能证明版本身份，不能证明模型真正遵循了句长、标点、第一人称或收尾习惯。因此 v12 只把 `voice_binding_status` 从固定未评估升级成真实的 `PASS/REVIEW`；`voice_conformance_status` 仍保持 `NOT_EVALUATED`。

### 18.2 新增的生产入口

新增两个正式脚本：

- `build_humanize_voice_profile.py`：从 sample spec 构建 manifest 与 Profile；
- `validate_humanize_voice_profile.py`：独立检查 schema、自哈希、manifest 绑定，并可从原样本重建证据。

builder 固定输出：

- `humanize-voice-sample-manifest/v2`，其中 canonical sample-spec hash 与样本来源声明一起进入自哈希；
- `humanize-voice-profile/v1`；
- canonical UTF-8 JSON；
- 64 位小写 SHA-256 自哈希；
- 不含整段样本原文的 feature evidence；
- 不含作者身份、能力或内容正确性推断的 claims。

validator 现在有两种层级：

- 只给 Profile：校验 strict JSON、schema、字段集合和自哈希，但 PERSONAL 顶层生产准入保持 `REVIEW/2`；
- 同时给 manifest、sample spec、allowed root 与 `--rebuild-evidence`：重新读取源字节、重建角色图、保护区、去重簇、计数、feature 和 Profile，要求结果逐字段相同。

后者堵住了“伪造一份内部自洽的 PERSONAL/PASS JSON，再自己重算 hash”的漏洞。PERSONAL Profile 进入 prepare 时必须经过当场重建，metadata 固定写 `voice_evidence_status=REBUILT_PASS`；只有自哈希、没有 manifest/spec 的 PERSONAL 工件直接失败。

真实 builder 消费测试又发现 DEFAULT 不能只分成“有/无”两类：不足 300 字或全部来源被排除时，builder 会生成带真实 manifest hash 的证据绑定 DEFAULT。它不是代码注册表里的零样本 DEFAULT，不能丢弃 manifest，也不能被后者的精确对象比较误拒。修复后，证据绑定 DEFAULT 同样要求 manifest/spec/root 当场重建，状态为 `REBUILT_DEFAULT_PASS`；只有确定性零样本 DEFAULT 使用 `DETERMINISTIC_DEFAULT`。

### 18.3 样本角色与隐私边界

sample spec 的路径只能相对 `--allowed-root`。每个样本必须声明：

- `sample_id`；
- `locator`；
- `origin`；
- `scene`；
- 是否为完整文本单元；
- 默认角色；
- UTF-8 字节半开区间形式的例外角色范围。

允许角色只有 `author/quoted/exam-original/ocr/code/math/template/unknown`。builder 即使收到 `default_role=author`，仍会自动剔除确定的 Markdown/TeX 代码、数学、块引语、直接引语和模板结构。角色范围越界、重叠或落在 UTF-8 字符中间时失败；乱码、NUL 或明显 OCR/mojibake 样本进入排除审计，不猜字。

来源只允许以下四类：

- `USER_CONFIRMED_AUTHOR`；
- `USER_CONFIRMED_ADOPTED`；
- `UNKNOWN`；
- `MODEL_GENERATED`。

后两类永远不能贡献作者字数或 feature。用户已经明确 CET6 两个 TeX 与微信 `main.tex` 由 GPT 生成，因此本轮真实语料验证把它们全部标为 `MODEL_GENERATED`，而不是因为文本长就偷换成作者 Voice 样本。

### 18.4 去重与置信门

Profile 字数按去保护、去重后的代表段落统计。重复攻击分两层拦截：

1. NFC 后保留字母数字的规范视图 exact hash；
2. 对不少于 40 个规范字符的段落做字符 5-gram，相似度达到 Jaccard 0.90 或 containment 0.95 时建立边，再按全部边的连通分量形成顺序无关近重复簇。

去重视图只裁决“是否独立”，不用于风格测量；句号、分号、括号和段落结构不会先被压平再拿来推断节奏。

置信门固定为：

| 去重作者汉字 | 完整单元 | 结果 |
|---:|---:|---|
| `<300` | 任意 | `DEFAULT` |
| `300–999` | 任意 | `LOW` |
| `1000–4999` | 任意 | `MEDIUM` |
| `>=5000` | `<3` | 最高 `MEDIUM` |
| `>=5000` | `>=3` | `HIGH` |

测试实际覆盖 299、300、999、1000、4999、5000 六个边界。另有一项把 200 字段落复制 30 次，原始字数达到 6000；去重后仍为 200，只能得到 DEFAULT，不能用复制凑出 HIGH。

### 18.5 feature 为什么没有写成自由文本

Profile 只开放可机械重建的 feature registry，例如：

- 主语位置；
- 条件先行；
- 显式连接；
- 段末标点；
- 括注；
- 分号分组；
- 非列表正文。

每个 feature 都保存 opportunity、support、counterexample、去重 unit 数、位置 hash 和 feature-level confidence。模板壳与跨段重复开头只进入 `DO_NOT_AMPLIFY` 负控。解释峰值、论证主次、判断力度等需要连续阅读的语义结论不会被一个正则直接发布成 PASS feature；这类内容仍留给逐文档阅读和独立前向审阅。

### 18.6 四个 DEFAULT 不是一个空字符串

COURSE、MODELING、RESEARCH、GENERAL 各有独立、版本化、hash 不同的场景 DEFAULT。它们共同满足：

- `profile_kind=DEFAULT`；
- `confidence=DEFAULT`；
- `features=[]`；
- `disclosure_required=true`；
- `personal_voice_claim_allowed=false`。

DEFAULT 的 `PASS` 只表示安全回退工件结构有效。它绝不表示“已经恢复作者个人文风”。长文 prepare 未收到 Profile 时会把对应 DEFAULT 物化为 `voice_profile.json`，而不是写一个无法校验的 `NONE`。

### 18.7 prepare/finalize 的精确绑定

prepare 现在把以下字段写入每个 unit、chunk 和 ledger：

- `voice_profile_id`；
- `voice_profile_revision`；
- `voice_profile_confidence`；
- `voice_profile_kind`；
- `voice_profile_source`；
- `voice_profile_binding_scene`；
- `voice_profile_sha256`；
- `voice_default_disclosure`。

同一绑定还出现在 `run_metadata.json`。Profile 本体进入 `prepare_integrity.json`；PERSONAL 的 manifest 与 sample spec 也一并冻结。finalize 除了检查完整性封条，还重新验证 Profile 自哈希、确定性 DEFAULT、Profile/manifest 绑定和 unit/chunk 字段一致性。

每个 `REWRITE` 与 `NO_CHANGE` JSON bundle 必须同时回显 `unit_id`、`chunk_binding_sha256` 与 `voice_profile_sha256`。文件名只是查找入口，不能替代 bundle 内部身份。拒绝原因分开记录：

| 情况 | unit 结果 |
|---|---|
| 缺字段 | `UNRESOLVED / voice_profile_hash_missing` |
| 不是 64 位小写十六进制 | `UNRESOLVED / voice_profile_hash_invalid` |
| 合法但不等于冻结值 | `UNRESOLVED / voice_profile_hash_mismatch` |
| 精确匹配 | 才进入 warning、保护区和正文验证 |

unit 与 chunk 另有 `bundle_unit_id_missing/invalid/mismatch` 和
`chunk_binding_hash_missing/invalid/mismatch`。三个值全部一致只证明 bundle 指向当前冻结块，
不证明正文符合 Voice Profile。

旧 `.txt` bundle 不能承载该字段，因此无法在 Profile-bound run 中通过。Profile 文件在 prepare 后被改动时，完整性门硬拒绝；`--check-command` 若在检查期间污染 Profile 或其他 run 工件，也由既有 run-state hash 门拦截。

### 18.8 真实 MD/TeX 语料验证

本轮没有拿合成短句替代真实材料。真实样本分成两种用途：

第一种是 Profile 负向准入：

- `D:\code LateX\elegantbook\cet6\CET6.source-damaged.backup.tex`；
- `D:\code LateX\elegantbook\cet6\test.tex`；
- 微信文件目录中的 `main.tex`。

三者按用户确认标为 `MODEL_GENERATED`。两次 builder/validator 重建都得到 `readable_author_chars=0`、`profile_kind=DEFAULT`、`confidence=DEFAULT`、`evidence_rebuilt=true`。这证明长文本不会因为字数多而绕过来源角色门。

第二种是 fresh 前向目标：

- COURSE：从 `test.tex` 的 10 个可编辑 unit 中只处理 `U-b24ef5a3242e`，34 个保护跨度全部通过；该 unit 为 `DONE`，其余 9 个仍为 `PENDING`，总体 `REVIEW/2`；
- RESEARCH：从微信 `main.tex` 的 28 个可编辑 unit 中只处理 `U-b1bcaa2c520d`，该 unit 为 `DONE`，其余 27 个仍为 `PENDING`，总体 `REVIEW/2`。

两个 fresh agent 都只看到正式 Skill、原始任务和输入路径，没有看到预期改法或本轮诊断。两次 rewrite bundle 都正确回显 Profile hash，逐单元保护与正文验证为 PASS，源文件 hash 未改变。局部完成没有被包装成全文完成。

前向 diff 也能看到材料驱动的具体动作。COURSE 单元删掉了“精准地勾勒”“紧拥新兴时代红利”等模板/错搭壳，把用途说明改为更直接的题型条件；RESEARCH 单元把参数口径、情景结果、物种差异与表格范围重新分层，同时保留全部数值、公式和“非独立外部验证”的限制。这里仍不能据两个样本宣称总体生成质量成熟，但至少证明新 hash 合同没有阻断真实 TeX 改写。

第二轮红队修复全部落盘后，又新开了一个不继承上下文的 RESEARCH agent，只给正式 Skill、微信 `main.tex` 和“处理一个完整单元”的普通任务。它选择 `U-4bd3af2f0994`（问题重述，第 20–26 行），单元正文与保护验证为 PASS；36 个总单元中 `DONE=1`、`PENDING=27`、`SKIPPED_PROTECTED=8`，源文件未修改。整体仍为 `REVIEW`，`coverage_completion_claim_allowed=false`、`humanize_completion_claim_allowed=false`，编译 `NOT_RUN`，声线符合性、跨单元重复和 fresh second pass 均未评估。产物见 [v12e fresh RESEARCH](build/maturity-v12e-fresh-forward-20260715/research/run/finalization_metadata.json)。该运行早于 `unit_id + chunk_binding_sha256` 的 LONG-14 bundle 合同，只能保留为 pre-LONG-14 历史证据，不能再称为当前最终前向。

### 18.9 两轮独立红队怎样继续击穿“看似闭环”

第一轮正确性审计没有把 v12 的新字段存在视为完成，而是直接寻找“能否拿错、能否重封、能否虚增”。它先发现五项问题：

1. builder 产生的 `PERSONAL/REVIEW` 会被 prepare 接收并误写 `REBUILT_PASS`；
2. 请求场景与 Profile `binding_scene` 没有强制相等；
3. 三份近重复完整文件能虚增 `unique_complete_units`，从 MEDIUM 升到 HIGH；
4. finalize 的 `voice_profile_manifest_sha256` 曾错误写成 Profile hash；
5. 长文文档把 PERSONAL 命令简写成只有 Profile 路径与 hash，遗漏 manifest/spec/root。

这五项修复后，定向 75 项和当时全量 381 项已经全绿，但第二轮两个彼此独立的只读代理仍实际构造出四条新的错误完成路径：

- **顺序攻击**：五份文本按 A–B–C–D–E 构成近重复链，相邻版本 containment 约为 0.969。旧算法只拿新样本与已选代表比较；同一文件集合换一个 sample spec 顺序，就能在 2 个与 3 个 complete representative 之间切换，进而发生 `MEDIUM/REVIEW ↔ HIGH/PASS`。修复后 `voice-dedup/v2` 对全部 exact/near 边取顺序无关的连通分量，稳定选代表；两个顺序都只得到 1 个完整代表、`MEDIUM/REVIEW`。
- **spec 自重封攻击**：攻击者把冻结 `voice_sample_spec.json` 的三条来源从 `USER_CONFIRMED_AUTHOR` 改成 `MODEL_GENERATED`，再重算 `prepare_integrity.json`；旧 finalize 只做 spec schema 检查，仍返回 `PASS/PASS`。manifest 已升级为 `humanize-voice-sample-manifest/v2`，新增 canonical `sample_spec_sha256`；finalize 独立核对 spec/manifest，prepare 封条即使被重算也不能替代来源绑定。
- **跨场景重标**：三份纯 COURSE 作者样本曾可通过 `--scene RESEARCH` 生成 `PERSONAL/PASS`，虽然全部 feature scope 仍是 COURSE。现在 PERSONAL 只有在唯一证据场景等于 `binding_scene` 时才可 PASS；跨场景或混合重标固定为 REVIEW，prepare 再由 `voice_profile_status_not_pass` 拒绝。
- **重复 JSON key 覆盖**：rewrite bundle 曾可同时写两个 `voice_profile_sha256`，让标准解析器用后一个正确值覆盖前一个错误值。finalize 现对 JSON/JSONL 使用 strict parser，重复 key、浮点数、非有限数字和过深结构直接失败；新增回归用两个同名 hash 证明该 bundle 不再进入单元验证。

红队还指出一个不会直接伪造长文 PASS、但容易误导调用方的 P2：只给 PERSONAL Profile、不重建 manifest/spec 时，validator 曾返回顶层 `PASS/0`。现在结果拆成 `profile_validation_status` 与 `production_admission_status`；前者可说明结构自洽，后者在缺少 `--rebuild-evidence` 时固定 `REVIEW/2`。只有代码注册表产生的确定性零样本 DEFAULT 可在无外部证据时直接准入。

对应审计见 [binding-audit.md](build/maturity-v12d-audit-20260715/binding-audit.md) 与 [test-gap-review.md](build/maturity-v12d-audit-20260715/test-gap-review.md)。这些发现解释了为什么“75 个相关测试全通过”仍不能结束：测试集合没有覆盖攻击构造时，绿灯只能证明已编码问题，没有证明状态机不存在别的假闭环。

### 18.10 回归、投影与资格边界

当前 v12h 自动化状态；前文 385/384 与 v12e tree 均只代表历史快照：

- 393 项测试运行完成，整体 `OK`，其中 1 项 Windows symlink 权限测试跳过；
- 15 个正式脚本全部通过 `py_compile` 与 `--help`；
- `PYTHONUTF8=1` 下 `quick_validate.py` 返回 `Skill is valid!`；
- action profile：50 张可用，0 张不可用；
- generator projection：28 文件，tree SHA-256 为 `ad1bf7f3af0e5bf9175b40ac8e05d394be00d95ce531499e85b6889e6e01bbba`；
- no-manifest qualification：`evidence_integrity_status=PASS`，`qualification_status=NOT_EVALUATED`，`atoms_pass=0/166`，evidence cap 仍为 E2，`production_e3_enabled=false`。

这些数字不等于“Skill 已成熟”。它们只证明当前实现、合同和拒绝路径在本地回归中一致。真正的全文声线符合性、跨块修复语重复、fresh second pass convergence 和外部盲评仍未闭合，因此本轮不能把 `humanize_completion_claim_allowed` 改成 true。

最终 projection 见 [v12h manifest](build/generator-projection-maturity-v12h-final-20260715-manifest.json)，no-manifest 审计见 [qualification-maturity-v12h-20260715-no-manifest.json](build/qualification-maturity-v12h-20260715-no-manifest.json)。后者进程与记录退出码均为 2，不把 `NOT_EVALUATED` 写成成功资格。

### 18.11 v12 后仍未完成的工作

当前剩余边界至少包括：

1. Profile hash 回显可能被生成端机械复制，不能替代独立声线评分；
2. 自动 feature 只覆盖可重建的低语义维度，复杂论证节奏仍需要逐文档连续阅读；
3. `AUTO` 长文场景尚无独立路由器，只能保守回退 GENERAL，且必须保持 `scene_routing_status=NOT_EVALUATED`；
4. PERSONAL 样本虽已在 prepare 当场重建，但本地 hash 不是外部身份签名；完整替换样本、spec、manifest、Profile 与全部自哈希仍需外部签名信任根才能识别；
5. 真实前向都只覆盖单个 unit，不能代表 52–55 KB 全文已经 Humanize；
6. 生成资格仍为 `NOT_EVALUATED`，不能用 393 项本地回归改写成 E3/E4 结论。

因此，v12 的准确表述是：Voice Profile 已从说明性文档升级为可构建、可重建、可冻结、可回显、可拒绝错配的生产链部件；全文声线终审层仍在建设中。

### 18.12 v12h：用真实前向修掉“正确拒绝中的错误理由”

这一轮没有从现有测试名称倒推实现，而是先把新 bundle 合同放到微信 `main.tex` 的真实
前向里。前向暴露了两类此前被绿灯遮住的问题：资格合同漏注册和跨 chunk TeX 假失败。

#### 18.12.1 资格合同从 163 扩到 166 个原子

`evaluation-contract.md` 已有 `LONG-14`，但旧 requirements 与 auditor 仍只登记到
`LONG-13`。只更新合同 hash 会让 oracle 不再 stale，却仍留下未注册行为。修复后：

- `LONG-14` 固定检查 bundle 的 `unit_id + chunk_binding_sha256 + voice_profile_sha256`、
  strict JSON 和跨 unit/旧 chunk 重放；
- `LONG-15` 固定检查跨块 TeX 的 `FRAGMENT -> DOCUMENT` 双层结构门；
- `VOICE-11` 固定要求完整一致性替换下仍保持 `identity_verified=false`；
- requirements 版本为 `1.7.0`，合同版本为 `2026-07-15.3`，原子总数为 166。

oracle 的 provenance 也发现一处真漂移：`corpus-action-sources.json` 已变化，但 catalog 仍保存
旧 hash，而 auditor 只检查“字段像 SHA-256”，没有读取 Skill 内来源重算。现在所有
`references/*` provenance 必须是 canonical 相对 POSIX 路径、不得穿越 symlink、必须存在且
实际 hash 一致；未随安装 Skill 分发的 `tests/fixtures/*` 只保留为历史派生说明，不冒充本地
可验证来源。对应回归会主动伪造一个内部 provenance hash，要求 catalog 加载硬失败。

#### 18.12.2 新 bundle 合同的真实前向结果

fresh run 位于 [maturity-v12f fresh forward](build/maturity-v12f-fresh-forward-20260715/research/finalization_metadata.json)：

- 输入为微信 `main.tex`，54834 字节，SHA-256 为
  `f97c5dc63e66d094e2ec73fbd2c935393a3370229db1d46baae9772bdacd0625`；
- prepare 产生 36 个 unit，其中 28 个 `PENDING`、8 个 `SKIPPED_PROTECTED`；
- 第一次 ephemeral CLI 因本机旧 API key 返回 401，发生在生成前，没有 bundle，单独记为
  基础设施失败，不算 Skill 行为失败；
- 第二次 fresh 进程在 read-only 模式下只返回 JSON，原始响应保存在
  [fresh-agent-raw-response.json](build/maturity-v12f-fresh-forward-20260715/research/fresh-agent-raw-response.json)，
  SHA-256 为 `d80154e784793cf4445d79a23862bf3cf7637600de54e404abc5baa06d1b5e19`；
- 它选择 `U-bc353709e690`，首轮正确回显 unit、chunk binding 与 scene-default Voice hash；
  finalizer 记录 `rewrite_bindings_matched=1`、`mismatched=0`，说明 LONG-14 对真实生成器可用；
- 该进程仍能读取宿主机完整 Skill，故只能称“独立新进程前向”，不能称已证明 oracle 不可达
  的 E3 盲测。

首轮 finalizer 把这个 unit 判为 `FAIL`，但失败详情显示改前和改后同时为
`begin{document} has no matching end`。原因不是生成器删除了 `\end{document}`，而是该 unit
本来只覆盖全文开头，结束环境位于后续 chunk。旧逐块 validator 把 fragment 当完整文档，
因此任何类似前导块都无法成为 `DONE`。

修复后的 unit 门显式写 `document_scope=FRAGMENT`：

- 只容忍改前已经存在且改后问题列表完全相同的环境/花括号边界不平衡；
- 环境名称或顺序变化仍触发 `LATEX_ENVIRONMENT_ORDER_CHANGED`；
- 环境问题列表变化触发 `LATEX_ENVIRONMENT_FRAGMENT_BALANCE_CHANGED`；
- 花括号问题变化触发 `LATEX_BRACE_FRAGMENT_BALANCE_CHANGED`；
- 接受的 unit 组装回全文后，仍以 `DOCUMENT` 范围执行完整平衡检查。

同一原始 bundle 重放后，硬不变量层从错误的 `FAIL` 变为 `PASS`，但 unit 仍没有被放行：
生成器删掉了原文一次“结果表明”，统一验证器产生
`SPEECH_ACT_REPORTING_OBSERVATION_CHANGED`，状态保持 `REVIEW/2`。最终账本为
`PENDING=27 / UNRESOLVED=1 / SKIPPED_PROTECTED=8`，`protected_hashes_ok=PASS`，源文件 hash
不变。这个结果比强行修到 DONE 更有证明力：本轮只消除了 chunk 边界误报，没有用结构修复
覆盖真实的言语行为风险。

#### 18.12.3 Voice 本地哈希的精确能力边界

本地 Profile、manifest、sample spec、chunk 与 prepare 封条能拒绝错配、局部篡改和旧工件
重放，前提是 allowed root 与其中样本字节被调用方视为可信输入。如果同一主体可以同时改写
源样本、spec、manifest、Profile 以及所有自哈希，本地 validator 只能证明新工件内部一致，
不能证明样本历史上属于某个真人。PERSONAL 即使准入 PASS，仍固定
`claims.identity_verified=false`。抵抗完整一致性替换需要代理无法访问私钥的外部签名 receipt，
并绑定样本根、源文件 hash、角色范围、场景、签发者、时间和撤销状态；当前 Skill 未实现该
信任根。

#### 18.12.4 当前可复核快照

- 全量 unittest：`Ran 393 tests`，`OK (skipped=1)`；
- 15 个脚本：`py_compile=PASS`，全部 `--help=PASS`；
- 官方 Skill 校验：`Skill is valid!`；
- action profile：50 available、0 unavailable、23 个可读来源，GENERAL 仍为
  `CORPUS_INSUFFICIENT`；
- generator projection：28 文件，tree
  `ad1bf7f3af0e5bf9175b40ac8e05d394be00d95ce531499e85b6889e6e01bbba`；
- no-manifest：`integrity=PASS / qualification=NOT_EVALUATED / 0 of 166 / E2`，进程与记录
  exit code 都为 2；
- 当前工件：[v12h projection manifest](build/generator-projection-maturity-v12h-final-20260715-manifest.json)、
  [v12h qualification](build/qualification-maturity-v12h-20260715-no-manifest.json)、
  [v12h action profile](build/maturity-v12h-action-profile-20260715.json)。

v12h 比 v12e 更成熟的地方不是“测试又多了 8 项”，而是三项以前会误导完成态的边界变成
可观察合同：bundle 精确绑定、fragment/full-document 分层、Voice 本地一致性与外部身份分层。
仍未闭合的核心项没有变化：全文 Voice conformance、跨 unit 新增修复短语重复、fresh second
pass convergence、逐 unit AUTO 路由和外部 E3/E4 信任链。因此当前版本仍不能称为完全成熟。

### 18.13 v13：全文 Voice 与跨 unit 模板不再是假字段

v12h 的 `voice_conformance_status` 和 `cross_unit_repetition_status` 虽然诚实，但仍固定为
`NOT_EVALUATED`。这能阻止虚假完成，却不能回答两个生产问题：同一 Profile 是否在全文被
明显写丢，以及两个局部 validator 都 PASS 时是否共同生成了新的修复模板。v13 没有用一个
模糊“相似度”填空，而是把可证明范围拆成两个独立门。

#### 18.13.1 Voice 门只验证已注册、可重建的机械特征

Profile builder 原有 7 类正特征：对象/本文主语、第一人称主语、条件起句、显式逻辑连接、
段末标点、括号限定、分号分组和非列表正文；负控为已知 AI 句壳与重复段首。此前这些 feature
只用于建档，finalize 没有消费。v13 把 extractor 提升为 builder 中唯一注册表，并新增
`feature_extractor_policy_sha256`。Profile 中每个 feature 的 extractor hash 必须能由当前
`rule_id + regex + flags + code` 重建；规则换了但旧 Profile 仍自洽时，全文门返回 REVIEW，
不能拿过期证据继续 PASS。

DEFAULT 与 PERSONAL 采用不同语义：

- DEFAULT 不伪造个人分布。只有场景已确定、Profile/chunk/bundle 绑定闭合、全部目标 unit 的
  统一 validator 为 PASS、默认披露仍为 true 时，`voice_conformance_status=PASS`；证据 basis
  固定为 `SCENE_DEFAULT_UNIT_VALIDATION`，`personal_voice_conformance_status=NOT_APPLICABLE`、
  `personal_voice_claim_allowed=false`。
- PERSONAL 至少需要 6 个目标正文块。门只使用 protected-masked 作者视图，不读取公式、代码、
  引语、题干或 OCR 内容；逐 feature 报告 before/after opportunity、support、ratio、容差、
  support drop、结构 floor 与当前/声明 extractor hash。
- 内容敏感特征不会被强迫插入。样本常用“因此”、括号或分号，而目标正文原本不需要时，门不会
  因绝对频率低而要求补写；它只在本轮改写让既有支持至少减少 2 个块、比例下降至少 25 个百分点
  并远离 Profile 时拦截。段末标点和非列表正文属于结构特征，目标足够长时另有保守 floor。
- Profile 的 `DO_NOT_AMPLIFY` 只允许保持或减少。新增长句壳、或新出现覆盖至少 3 个 unit 的同一
  四汉字段首时返回 REVIEW。
- 所有 PASS 均固定 `identity_verified=false`。它证明“注册机械特征没有明显回退”，不证明完整
  作者气质、写作能力、历史归属或真人身份。

直接单测使用 6 个“本文说明……”段落：NO_CHANGE 时 feature 支持为 `6/6` 并 PASS；把 6 个
段落全部改成未注册的“结果说明……”后，支持从 `6/6` 降到 `0/6`，门返回 REVIEW。只有 2 个
目标块时，即使字面完全不变也返回 `INSUFFICIENT_TARGET_BLOCKS`，避免短片段冒充全文拟声。

#### 18.13.2 跨 unit 门执行真实语料负例，不建立通用术语 n-gram 误杀器

这一门的第一版没有拍脑袋扫描任意高频专业词。它只执行两类已有依据的 detector：

1. `lexical-signals.json` 中的 `LEX-REPAIR-01`，覆盖“这里真正需要、这里只看/保留/讨论/比较、
   其余情形沿用、不再展开/赘述”等 Humanize 修复句壳；
2. `corpus-action-sources.json` 中来源仍可读、action profile 状态为 `AVAILABLE`、场景为 `ALL`
   或当前场景的 `negative_guard`。其中 `NEGATIVE-TEMPLATE-01` 来自 GPT 生成 CET6 TeX 的人工
   负例阅读，检测自动未来桥接和跨段重复“不是……而是……”；MODELING 与 GENERAL 还有
   README 壳、施工计划腔、治理验收腔、期刊过拟合、宣传 claim 堆叠、OCR 问答和 API 导航等
   已登记 guard。

`positive_action` 不会被执行为 detector。它仍只说明抽象组织动作有来源锚，不能把正向语料
变成句子扫描器。若适用的 negative guard 因源文件乱码、缺失或行范围漂移变为 UNAVAILABLE，
全局门只能 REVIEW，不能静默跳过后写 PASS。

匹配视图先删除保护占位符内部内容，再执行 NFKC、删除零宽字符和汉字之间的普通/Unicode
空格；因此“这\u200b里只比较”与“这 里只比较”不能绕过。它不跨空段、标题、列表、TeX
结构行、公式、引语或代码边界拼接，也不做通用连续汉字 n-gram，所以“量子纠缠态”“边界条件”
等必要术语跨章节重复不会仅因词频被判模板。

门按 unit 计算 before/after 多重集，再按逻辑文档聚合。必须同时满足：

- after 达到 detector 自身阈值；
- 命中覆盖至少两个不同 unit；
- 至少一个 unit 的 after occurrence 数大于该 unit 的 before。

原文已经跨 unit 重复、候选没有增加时进入 `inherited_findings`，不阻断 NO_CHANGE。命中新增
重复时，只有拥有新增 occurrence 的 unit 从临时接受集回退为 `UNRESOLVED`；继承 occurrence
所在 unit 不受连坐。回退同时清空 `hash_after/diff_path`、从 `accepted_by_file` 移除候选，并用
冻结原文组装 `rendered_partial`。这修复了“元数据写 REVIEW，但 coverage ledger 仍为 DONE、
diff 仍发布”的假闭环。

证据保存在 `validation/cross_unit_repetition.json`，包括：

- FULL/PARTIAL scope、unit inventory hash、before/candidate 逻辑文档 hash；
- lexical policy、action catalog、action profile 与全部 active detector definition hash；
- finding fingerprint、before/after occurrence、before/after unit、introduced unit；
- inherited findings、blocking unit 集合和 normalization policy。

两个 TeX unit 的真实集成 fixture 分别把“本段只比较峰值”“本段只讨论误差”改成“这里只比较
峰值”“这里只讨论误差”。两个 fragment validator 单独均 PASS；全文门识别同一家族跨 unit
新增，两个 unit 均回退为 UNRESOLVED，发布的 partial 中没有“这里只”。相反，原文已经包含
两个该类句壳且两个 bundle 都是 NO_CHANGE 时，门记录 inherited 并 PASS。另一个 fixture 把
两个“不是……而是……”分别放在两个 unit，实际命中 CET6 负例锚定的
`NEGATIVE-TEMPLATE-01`。

#### 18.13.3 真实 main.tex 没有被新门洗成通过

v13 重新 prepare 微信 `main.tex`：输入仍为 54834 字节、同一 SHA-256 和 snapshot ID，仍得到
36 个 unit（28 PENDING、8 SKIPPED_PROTECTED）。由于 extractor policy 成为 Profile hash 的
一部分，v12h 的 bundle 不能直接重放；复核只把旧 fresh agent 的原始 `masked_text` 绑定到
新的 chunk/Voice hash，正文一字未修。这是历史输出重绑定回归，不冒充新的 fresh forward。

结果保持正确分层：

- hard invariant PASS，`document_scope=FRAGMENT`；
- speech-act REVIEW，warning 仍为 `SPEECH_ACT_REPORTING_OBSERVATION_CHANGED`；
- style-signal PASS，unit 仍为 UNRESOLVED；
- 27 PENDING、1 UNRESOLVED、8 SKIPPED_PROTECTED；
- Voice conformance REVIEW，因为 28 个可处理 unit 只评了 1 个；
- cross-unit repetition 为 `REVIEW/PARTIAL`，新增 finding 为 0；
- full-format errors 为 0，源文件修改为 0；
- coverage/Humanize completion claim 均为 false。

证据见 [v13 real-main audit](build/maturity-v13-real-main-20260716/research/v13-real-main-regression-audit.md)。
新全局门没有把局部语义 warning 覆盖成 PASS，也没有因为“未发现跨块模板”把 partial 范围
冒充 FULL。

#### 18.13.4 当前可复核快照

- 全量 unittest：`Ran 402 tests`，`OK (skipped=1)`；
- 15 个脚本：`py_compile=PASS`，全部 `--help=PASS`；
- 官方 Skill 校验：`Skill is valid!`；
- action profile：50 available、0 unavailable、23 个可读来源，GENERAL 仍为
  `CORPUS_INSUFFICIENT`；
- contract：`2026-07-15.4`，SHA-256
  `f260eabe484400dfcd46cce0c083350f0b87de01ba5719ae9bfcb2ebf6940c6f`；
- requirements：`1.8.0`，SHA-256
  `d7c2cf6d089afe3663f775a99588f0638290bc6b96ee055a6ff6dd9f693c3c42`；
- oracle：`1.0.6`，SHA-256
  `177977ae018c75c9770749b25a6dc0de829a130ca7a5f210a5641d5b8a2f7e07`；
- generator projection：28 文件，capability source
  `5b8f1075aa54bcca5ab694aefd68b68f4fcef39ca57a4f7f48f13085ff4a7183`，tree
  `dfa5d35be0f4be8ea02b3d3e592225e9f5c7caedab1a1ccb30fae079ba9f84b8`；
- no-manifest：`integrity=PASS / qualification=NOT_EVALUATED / 0 of 168`，进程与记录 exit
  code 均为 2；
- 当前工件：[v13 projection manifest](build/generator-projection-maturity-v13-final-20260716-manifest.json)、
  [v13 qualification](build/qualification-maturity-v13-20260716-no-manifest.json)、
  [v13 action profile](build/maturity-v13-action-profile-20260716.json)。

v13 已关闭两个此前明确列出的生产缺口，但仍不能称完全成熟：fresh second-pass convergence
尚未执行，AUTO 仍未逐 unit 路由，PERSONAL 来源身份与 E3/E4 隔离仍缺外部签名信任根。

### 18.14 v14：fresh second pass 从声明字段升级为活证据控制面

v13 的完成门仍有一个故意保留的硬缺口：`humanize_second_pass_convergence` 永远是
`NOT_RUN`。同一 run-dir 重放同一 bundle 只能证明组装字节幂等，不能证明模型把第一遍 clean
输出当作新输入后不会再次轮换同义词、改标点或搬句序。v14 不再把两者混用：

- `assembly_replay_idempotency` 继续只回答“同一 bundle 能否重放出同一派生树”；
- `humanize_second_pass_convergence` 只由新的 fresh 控制面产生；
- 两者都 PASS，仍需 coverage、scene、rewrite binding、Voice binding、全文 Voice 与跨 unit 门
  全部 PASS，才能令 `humanize_completion_claim_allowed=true`。

#### 18.14.1 五段式执行链

第一遍完整发布后，`prepare_humanize_second_pass.py` 读取第一遍 `rendered_manifest.csv`，逐个
复核路径、字节数与 SHA-256，并拒绝 manifest 外新增文件、重复 file/unit identity 或任何
`rendered_partial`。它把第一遍 rendered 文件作为第二 run 的唯一 source，再由原长文 preparer
重新生成 snapshot、units、chunks、保护 span 和 Voice 绑定。因此第二遍不是拿旧 chunks 改名，
而是对 clean 文件重新走完整准备流程。

每个第二遍 PENDING chunk 单独封存为 public case。所有 case 使用完全相同的 canonical prompt：
只要求模型重新阅读当前 masked chunk，并根据是否仍需实质修改选择 `REWRITE` 或 `NO_CHANGE`。
prompt 不含第一遍 bundle、diff、decision、expected answer、资格 atom 或 verifier 规则。public
manifest 与 seal 绑定 input、prompt 和 public context；unit、chunk 与 Voice 三个身份必须在输出
strict JSON 中精确回显。

生成后按以下顺序处理：

1. 每个 unit 用 `run_humanize_generation_trial.py` 启动独立新进程；
2. collect 只复制 strict、无 code fence、无重复键、unit/chunk/Voice 精确匹配的原始 output；
3. 第二遍 finalizer 对全部 bundle 运行普通长文门，产生真实 coverage ledger 与 rendered tree；
4. `verify_humanize_second_pass.py` 重读 plan、collection、runner receipt、run record、run seal、
   public seal、execution projection、第二遍 finalization 和两遍 rendered；
5. 第一遍 finalizer 接收 receipt 时不只验自哈希，而是按 receipt 的 evidence roots 重新执行
   verifier；live receipt 与提交 receipt 必须逐字段相同。

#### 18.14.2 收敛和失败不再共用一个模糊状态

`LONG-17/P0` 把三类结果分开：

| 情形 | 状态 | 完成声明 |
|---|---:|---:|
| 全部初始 PENDING unit 均有 fresh `NO_CHANGE`；第二遍 ledger 全为 NO_CHANGE；两遍 rendered tree 相同；活证据复验一致 | `PASS/0` | 只放开 second-pass 这一门 |
| 缺 trial、缺 bundle、第二遍仍有 PENDING/UNRESOLVED、任一 fresh `REWRITE`、两遍树不同 | `REVIEW/2` | false |
| plan/collection/receipt/record/seal/scene/Voice/tree/hash 错配，重复 run id，projection 漂移，receipt 底层证据被删除 | `FAIL/1` | false |

这一分级避免了两个相反错误：不能因为第二遍提出了合理修改就写“收敛 PASS”，也不能把外部
服务暂时无输出误写成文稿硬损坏。`REWRITE` 意味着文风尚未稳定，应回到第一遍规则查冲突；
证据错配则意味着审计链本身不可信，必须硬失败。

#### 18.14.3 receipt 不再是可以手工重算的通行证

第一版草案只校验 receipt schema、自哈希、tree、Voice、scene 和若干 64 位十六进制字段。
红队证明这仍可伪造：任何调用方都能填写假的 process hash 后重算 JSON 自哈希，或者在 receipt
生成后删除全部 trials，而第一遍 finalizer 仍会 PASS。v14 将 receipt 扩展为活证据索引：

- `evidence_roots` 精确记录 first run、second run、cases、trials 和 rewrites；
- `evidence_artifacts` 绑定 plan、collection、cases tree、trials tree 和 rewrites tree；
- finalizer 当场从固定 Skill 路径重新加载 verifier，忽略 `sys.modules` 中同名注入模块；
- verifier 重新计算每个 runner artifact、public artifact、projection manifest/tree 和 staged case；
- 任何底层文件新增、删除、替换或跨版本重放都会让 live receipt 与提交 receipt 不同。

这仍是本地 E2 完整性，不是外部签名。能同时改写 Skill、全部 trials 和所有哈希的同一主体仍
可伪造整套本地历史；所以 claims 固定保留 `filesystem_isolation_verified=false`、
`oracle_unreachable_verified=false`、`human_identity_verified=false` 与
`academic_correctness=NOT_EVALUATED`。它解决的是错误绑定和虚假闭环，不冒充不可抵赖证明。

#### 18.14.4 红队攻击矩阵

新增 [second-pass tests](tests/test_humanize_second_pass.py) 不是只检查文件能生成，而是实际攻击
完成态：

| 攻击 | 修复前 | v14 |
|---|---|---|
| receipt 的 run id 与 run record 不同，但重算 record/seal hash | 可 PASS | `FAIL` |
| 两个 unit 复用同一 run id | 可 PASS | `FAIL` |
| receipt projection tree 与 record/seal 不同 | 可 PASS | `FAIL` |
| trial 中实际 `execution/skill` 被改写，字段 hash 不动 | 可重新出 receipt | 现场 `verify_projection` 后 `FAIL` |
| 删除 trials，只保留自哈希 receipt | 第一遍 finalizer 可 PASS | 活证据根不存在，`FAIL` |
| run record 把 `generator_context.complete` 改成 true | 可 PASS | `FAIL` |
| isolation 子记录声称 oracle 已不可达 | 可 PASS | `FAIL` |
| 第一遍 rendered 藏有 manifest 外文件 | second prepare 会忽略 | prepare 拒绝 |
| plan 自洽重签但改成 `expected_outcome_exposed=true` | collect 可继续 | collect 拒绝 |
| code fence、重复 JSON key、错 unit/chunk/Voice | 可能污染 rewrites | collect 拒绝 |
| 任一真实 `REWRITE` | 可能与组装幂等混淆 | `REVIEW/2`，不出 PASS receipt |

16 项 second-pass 专项测试全部通过。它们使用真实 28 文件 projection 和真实 runner 工件结构；
只有外部模型 invocation 被 fixture 替代，因此证明控制面行为，不证明真实模型稳定性。

#### 18.14.5 generator projection 反泄漏

上一版计划曾拟把 prepare 与 verifier 两个脚本加入 generator projection，文件数从 28 扩到 30。
红队审查否决了这一做法：verifier 明文规定“全部 NO_CHANGE、两遍树相同才收敛”，若 fresh
generator 能读取它，第二遍就提前知道验收答案，`expected_outcome_exposed=false` 成为假声明。

最终边界保持 28 文件：

- `prepare_humanize_second_pass.py` 与 `verify_humanize_second_pass.py` 明确归入 evaluation/control
  surface，不进入 projection；
- 完整安装版 finalizer 保留 receipt 复验；投影版 finalizer 用固定 Python span transform 删除
  验收字段与 verifier 路径，只留不可执行的控制面 stub；
- 完整 `long-document-workflow.md` 保留五段命令；投影版用固定 H2/段落 transform 替换为普通
  独立复读说明，不暴露“全部 NO_CHANGE”条件；
- `SKILL.md` 的 second-pass 控制块使用唯一 marker，在 projection 中确定性删除；
- builder 对缺 marker、重复 marker、锚点漂移、遗留 verifier basename 或控制字段全部 fail closed。

两次独立重建得到完全相同的 manifest SHA-256
`574382dfc7ccff24d5d7e32955d32392ca1433b1bb36682a98e42607bd7571c9` 和 tree
`1df1c31d47ea9dffbf98bfa5bee3d6936f71ac973a4fb2bc87e76f30271792af`。capability source 为
`bbf1c420b199d22d61072674761784d987b3c626d1d1a5f4235c54711e973edc`；policy canonical hash 为
`f072ab31f0d5790fc7700351c175c33452469ef89a07a3dc216aa15a6fa85f0d`。

#### 18.14.6 真实 fresh campaign 与进程树修复

真实试跑使用现有 `humanize_forward_v10/research_after.md`，第一遍 1 个 unit、111 个作者汉字、
1 个保护 span，完整 NO_CHANGE 发布后各局部门均 PASS。second prepare 生成新的 chunk binding 和
无答案 sealed case。

首次真实 `codex exec` 暴露 runner 的进程管理缺陷：内部 timeout 为 120 秒，但旧代码只终止
父进程；node/codex 后代继续持有 stdout 管道，外层 184 秒后才强制结束，并留下 3 个本次新
进程。它们按 PID 与启动时间精确终止，没有误杀已有 VS Code/Codex 会话。

修复后，Windows runner 使用新进程组并在 timeout 时执行整棵进程树终止；POSIX 使用独立
session/process group。真实孙进程测试由约 8.06 秒等待自然退出缩短为约 1.38 秒收口。随后
以 45 秒 timeout 重试，46.3 秒内得到正式 `INFRA_INVALID` receipt：

- `timed_out=true`、`returncode=1`、`output_present=false`；
- projection 后验为 `NOT_COMPLETED`；
- filesystem isolation 为 false、oracle unreachable 为 UNVERIFIED；
- retry 后没有遗留新 Python/node/codex 进程。

下游状态严格保持：collect `FAIL`，第二遍 finalizer `REVIEW/2` 且 1 个 PENDING，verifier
`REVIEW/2`，receipt 不生成，第一遍 `humanize_second_pass_convergence=NOT_RUN`、Humanize
completion false。完整审计见 [real second-pass audit](build/maturity-v14-second-pass-real-20260716/real-second-pass-audit.md)。

#### 18.14.7 当前可复核快照

- 全量 unittest：`Ran 421 tests in 41.881s`，`OK (skipped=1)`；
- 17 个 Skill 脚本：`py_compile=PASS`，全部 `--help=PASS`；
- `quick_validate.py` 首轮因 Windows GBK 读取 UTF-8 抛 `UnicodeDecodeError`；按既定乱码策略以
  `PYTHONUTF8=1` 重试后输出 `Skill is valid!`；
- contract：`2026-07-16.5`，SHA-256
  `d1fda0af6aedd81adb39b0763571d9e886b3dd6fcfd7d27ec3fe8c6977a1c253`；
- requirements：`1.9.0`，SHA-256
  `5fedf6b2f22fec20adfa0865c962b23667ad15dcfc9002a31ecb479cfb229974`；
- oracle：`1.0.7`，SHA-256
  `7f61992db6b485afcc37cf953f49b09d3cf2bfbfd5faedccf1e0211c7a676ff4`；
- qualification：`integrity=PASS / qualification=NOT_EVALUATED / atoms_pass=0/169`，exit 2；
- action profile：`PASS`，23 个可读来源、50 available、0 unavailable；GENERAL 仍为
  `CORPUS_INSUFFICIENT`；
- generator projection：28 文件，两次重建 manifest/tree 相同，证据封顶 E2。

最终工件：[v14 stable projection manifest](build/generator-projection-maturity-v14-stable-20260716-manifest.json)、
[v14 deterministic repro](build/generator-projection-maturity-v14-stable-repro-20260716-manifest.json)、
[v14 qualification](build/qualification-maturity-v14-stable-20260716-no-manifest.json)、
[v14 action profile](build/maturity-v14-action-profile-20260716.json) 与
[v14 real second-pass audit](build/maturity-v14-second-pass-real-20260716/real-second-pass-audit.md)。

v14 关闭了“second pass 只存在于字段”“receipt 自哈希即可伪造”“verifier 泄漏给 fresh
generator”和“timeout 留下进程树”四个生产级缺口，但仍不能称最终成熟。真实 fresh campaign
本次没有模型输出，169 原子资格仍为 0/169；AUTO 逐 unit 路由、PERSONAL 外部签名来源、E3
filesystem/oracle isolation 与 E4 可信人工链仍未实现。

## 19. 第十五轮：来源纠偏、AUTO 真路由与 fresh Voice 闭环

### 19.1 为什么 v14 的“当前快照”必须作废

v14 后的继续审计没有从“再加几条规则”开始，而是先核对正向语言材料的来源身份。这里发现了
一个会直接污染整个 Skill 学习方向的 P0：微信 `main.tex` 已由用户明确说明为 GPT 生成，但旧
catalog 曾把它登记成 RESEARCH 正向 action 来源；CET6 的 GPT 报告也曾支撑 REPORT 正向卡。
这意味着工具一边声称“去 AI 味”，一边把模型成稿中的组织模板当作正向人类表达学习。即使卡片
只保存抽象动作，这个来源角色仍然错误，不能靠“不复制原句”洗掉。

v15 将来源合同升级为结构化 `origin_class`：

| 来源 | 当前 origin/role | 允许用途 | 明确禁止 |
|---|---|---|---|
| 微信 `main.tex` | `MODEL_GENERATED / negative_template_reference` | 检测重复元问题对照、自证式收尾、自动闭合 | RESEARCH 正向 action、PERSONAL Voice、真人范文、句库 |
| CET6 GPT 报告族 | `MODEL_GENERATED / negative_template_reference` 或版本审计 | 检测列表堆叠、指令口吻、固定槽位、同义轮换 | REPORT 正向 action、作者声线 |
| CET6 `test.tex` | `MODEL_GENERATED / negative_template_reference` | 检测强制对照和自动愿景结尾 | 反向生成“自然写法” |
| `cet6.tex` | `user_excluded` | 只保留排除审计 | 读取、统计、动作卡 |
| 乱码备份 | `unreadable_excluded` | 记录跳过 | 猜字、恢复、推断语言特征 |

构建器新增硬门：`MODEL_GENERATED + positive_action_reference` 直接失败；模型来源必须是带可审计
detector 的负例或纯审计角色。当前 action profile 的真实结果是：26 个登记来源，23 READABLE、
3 EXCLUDED_CONFIG；41 张卡 AVAILABLE、0 UNAVAILABLE；`model_generated_positive_source_count=0`。

场景支持不再用“总卡片数很多”掩盖空白：

| 场景 | 正向卡 | 独立正向来源 | 状态 | 候选策略 |
|---|---:|---:|---|---|
| COURSE | 4 | 2 | `SUPPORTED`，但来源身份仍含未决 | 最多选两张适用卡，继续保护原稿事实 |
| MODELING | 27 | 7 | `SUPPORTED`，origin assurance 为 `UNRESOLVED_PRESENT` | 只借抽象组织动作，不借事实、公式和结论 |
| RESEARCH | 0 | 0 | `CORPUS_INSUFFICIENT` | `corpus_action_support=NONE` |
| GENERAL | 0 | 0 | `CORPUS_INSUFFICIENT` | `corpus_action_support=NONE` |
| REPORT | 0 | 0 | `CORPUS_INSUFFICIENT` | `corpus_action_support=NONE` |

旧 `RESEARCH-MAP/EVIDENCE/MECHANISM/SCOPE/CLAIM/UNCERTAINTY` 六张卡和三张 GPT REPORT 正向卡已
删除。研究场景只保留 `NEGATIVE-RESEARCH-MAIN-META-SHELL-01`：它拦截连续用“真正的问题”“关键
不是 A 而是 B”重述元问题，随后用“这说明/由此可见”自行确认论证完成的组合。这个负例不能
倒过来教模型套另一组句子；命中后必须回到当前原稿已有对象与判断，没有对象时 `UNRESOLVED`。

### 19.2 从真实 GPT TeX 中提炼出的可执行负面抓手

这次不是只写“AI 文风过于模板化”，而是把 GPT TeX 的可观察问题压成 detector 和编辑动作：

1. **元问题重复命名**：同一段连续出现“真正的问题是”“关键不在于”“本质上不是”，看似推进，
   实际只替换标签。动作不是找一个新同义词，而是只保留一次问题定义，后句进入对象或证据。
2. **对照壳替代判断**：`不是 A，而是 B` 在没有真实误读时被用作每段发动机。单次命中不判错；
   同一局部单元重复或与“真正/关键”联用才进入 guard。
3. **自证式收尾**：段尾自动接“这说明、由此可见、从而证明”，但前文没有新增证据层。删除这类
   出口后若主张仍成立，直接停句；若主张依赖该出口制造强度，保持 REVIEW。
4. **列表型报告腔**：标题、编号、命令句和动作卡密度过高，把论文正文写成执行清单。保留真正的
   并列结构，但将只有一个信息重心的列表还原为散文，不迁移报告的无主语命令口吻。
5. **同义词轮换**：删掉“值得注意”后改成“必须注意”，删掉“奠定基础”后改成“成为出发点”。
   验收必须扫描新稿中的同族候选，不能只确认原词消失。
6. **自动愿景桥接**：每节末尾都写“为后续分析提供支撑/为未来研究奠定基础”。只有输入明确给出
   后续用途时保留，否则删除；不能换成“供后续参考”继续留壳。
7. **编辑后台泄漏**：`本节需要、正文应、需要分开报告` 被原样写进成稿。DRAFT 先拆分
   `FACT_PAYLOAD / EDITORIAL_REQUIREMENT / FACT_BOUNDARY`，编辑动作由组织实现，不进入正文。

这些抓手的共同点是可定位、可复扫、可给具体 KEEP 理由。它们不是“凡出现某词就删”的禁词表；
引语、正式术语、真实教学提醒和用户结构锁仍优先。

### 19.3 AUTO 从字符串占位升级为逐 unit 路由

v14 的合同仍写着 `AUTO` 暂绑 GENERAL，实际需求却是混合长文按 unit 使用不同场景。v15 新增
`scene-routing-policy.json` 与 `route_humanize_scene.py`，完整 unit 的标题路径和去保护正文共同
计分，evidence 只输出 rule ID、次数和贡献，不导出命中原文。

当前裁决如下：

- 强信号达到阈值且领先 margin：`ROUTED`；
- 专属场景信号不足：`FALLBACK_GENERAL`；
- 强平局或 margin 不足：`AMBIGUOUS`，unit 为 `UNRESOLVED`；
- 弱信号与逻辑文档 prior 同场景、且该场景为局部最高：`ROUTED_DOCUMENT_PRIOR`；
- 完全中性的背景、结论或共享标题不能只靠 prior 继承专属场景。

红队先后击穿了五种路由假设：工程“实验结果”被误分 RESEARCH、TeX `{solution}/{note}` 未进入
COURSE、`Notebook` 被 `note` 子串误报、摘要/引言/结论单独被当成 RESEARCH，以及一个强
MODELING 单元把中性“背景”全局拖成 MODELING。修复后，共享标题只有弱证据；`{solution}/{note}`
使用精确 TeX role；document prior 只补同场景弱证据，绝不消解 `AMBIGUOUS`。

prior 的范围也经历了两次修正。最初按物理文件计算，`\input` 拆出的章节无法继承主文档用途；
改为逻辑 include 根后，又必须防止零证据传播。最终实现同时满足：include 图跨文件共享 prior，
本 unit 必须有同场景弱证据。second pass 只把第一遍 relation=seed 的 rendered 文件作为新 seed，
让 include 边重新发现；不再把所有 rendered 文件平铺成独立 seed。

AUTO 同时物化四个不同 hash 的 DEFAULT Profile：

- `voice_profile_set.json`：set 身份、四个 entry 和固定 false claims；
- `voice_profiles/course.json`；
- `voice_profiles/general.json`；
- `voice_profiles/modeling.json`；
- `voice_profiles/research.json`。

单一 supplied Profile 暂不允许与 AUTO 混用，固定报 `AUTO_does_not_accept_single_voice_profile`。
这是显式能力边界，不用一个 PERSONAL Profile 假装覆盖四类用途。

### 19.4 finalizer 的重封攻击

仅有 `prepare_integrity.json` 不构成信任根，因为同一攻击者可以修改文件后重算全部哈希。v15
因此把“从冻结源独立重建”扩展到 route、Voice 与 metadata。下表均有真实单元攻击测试：

| 攻击 | 旧风险 | v15 裁决 |
|---|---|---|
| 修改 unit scene、routing decision、Voice hash，再同步 ledger/chunk/seal | 自洽伪造可越过普通 hash | 从 frozen source 和当前 policy 重建后 `FAIL` |
| 修改 prepare 顶层 `status=PASS`、`completion_claim_allowed=true`、`DONE=999` | finalizer 忽略伪字段仍发布 PASS | 精确 metadata 派生重算，字段不符 `FAIL` |
| 修改冻结 routing policy、metadata 与 seal | 旧规则可被 run 内工件替换 | 与当前安装 policy 字节/canonical hash 比较，`FAIL` |
| Profile set 的 `claims.identity_verified=true` 并重算 set hash | 本地 hash 被误当身份授权 | claims 必须精确为 false，`FAIL` |
| 在 Profile entry 中夹带 `identity_verified=true` | open object 忽略未知键 | entry 精确键集合，`FAIL` |
| metadata binding 夹带 `external_clearance=VERIFIED_HUMAN` | open object可携带越权声明 | binding 精确键集合，`FAIL` |
| 把 MODELING 的合法 Voice hash放到 COURSE bundle | hash 格式合法但场景错误 | `voice_profile_hash_mismatch`，unit `UNRESOLVED` |
| protected-only 歧义标题 | 制造不存在的可编辑缺口 | 保持 `SKIPPED_PROTECTED`，不增加 unresolved |

本地 Profile 的能力声明仍被限制：它只证明当前 supplied bytes 的机械绑定。即使样本、spec、
manifest、Profile 和全部本地哈希被一起替换，`identity_verified` 仍必须是 false；只有未来接入
代理无法访问私钥的外部签名信任根，才可能证明历史来源身份。

### 19.5 fresh second pass 现在能看到 Voice

v14 的 second pass 虽然在最终阶段比较 Voice hash，但 fresh generator 的 sealed case 只有 chunk；
PERSONAL Profile 的特征并未进入生成上下文。模型在看不到声线的情况下决定 REWRITE/NO_CHANGE，
机械收尾却声称沿用同一 Voice，这是实用性 false assurance。

v15 将 plan 升为 `humanize-second-pass-plan/v3`。每个 sealed input 都是严格对象：

```json
{
  "schema_version": "humanize-second-pass-generation-input/v1",
  "chunk": {"unit_id": "...", "voice_profile_sha256": "..."},
  "voice_profile": {"profile_kind": "PERSONAL", "features": [], "claims": {}}
}
```

实际对象包含完整已验证 Profile；这里的示意省略字段。PERSONAL Profile 只带抽象 features、负控、
policy binding 与 false claims，不带作者原始样本文本。plan 同时绑定 `chunk_file_sha256`、
`case_input_sha256`、`voice_context_sha256`、public manifest 和 seal。verifier 从第二遍冻结 Profile
重建 generation input，逐字节比较，不信任 plan 自述。

第二个工程修复是分块漂移：第一遍合法压缩可能让两个相邻 GENERAL unit 在第二遍合成一个。
旧 verifier 要求 unit 数和 ordinal 一一相等，会把预算布局变化误判成 Voice 漂移。现在按文件比较
相邻的 `scene + document prior + routing decision + policy + Voice` 运行段：同场景纯拆分/合并
允许，跨场景次序、policy 或 Voice 变化仍硬失败。

第三个修复是 include seed：second prepare 仍校验第一遍全部 rendered manifest，但只把原
`relation=seed` 的文件交给 prepare，子文件由 `\input/\include/\subfile` 重新发现。多文件 AUTO
的逻辑 prior 因而能跨两遍保持。

### 19.6 资格矩阵扩为 176 原子

本轮新增七个不可缩水原子：

- `ROLE-10`：MODEL_GENERATED 不能成为正向 action/Voice/真人范文；
- `ROUTE-13`：共享标题 false route；
- `ROUTE-14`：逻辑 include prior 只补同场景弱证据；
- `VOICE-13`：Profile set/entry/metadata claims 越权；
- `VOICE-14`：逐 unit、跨场景 Voice hash；
- `LONG-18`：当前 policy、冻结 source、include、metadata 独立重建；
- `LONG-19`：fresh case Profile 可见、样本文本不泄漏、同场景分块漂移。

固定 requirements 为 `2.0.0`，contract 为 `2026-07-16.6`。无 evidence manifest 的正式审计结果
仍是：`evidence_integrity_status=PASS`、`qualification_status=NOT_EVALUATED`、
`atoms_pass=0`、`atoms_fail=0`、`atoms_not_evaluated=176`、exit 2。这里的 PASS 只属于“空证据被
诚实识别”，不是生成模型通过。

### 19.7 真实 TeX prepare 审计

三份用户指定材料只执行 prepare，没有把 GPT 文本写回、没有生成正向 action：

| 材料 | 文件/单元 | 可编辑/保护 | AUTO 场景 | 状态 |
|---|---:|---:|---|---|
| 微信 GPT `main.tex` | 1 / 36 | 28 unit / 821 spans | GENERAL 3、MODELING 25；23 ROUTED、2 prior、3 fallback | `READY`，routing PASS |
| `physics1.tex` | 1 / 60 | 49 unit / 3164 spans | COURSE 40、GENERAL 10；1 个 COURSE/MODELING 强歧义 | `REVIEW`，1 UNRESOLVED |
| CET6 GPT `test.tex` | 1 / 26 | 10 unit / 643 spans | GENERAL 10，全部 fallback | `READY`，routing PASS |

`physics1.tex` 的 `刚体力学 / 刚体与定轴转动` 单元同时出现 COURSE 与 MODELING 强信号，工具没有
用文件名或 prior 偷选，而是保留 `AMBIGUOUS/UNRESOLVED`。这比“全部自动路由成功”更可信。

### 19.8 v15 可复核机器快照

- 全量 unittest：`Ran 453 tests in 51.061s`，`OK (skipped=1)`；
- Skill Python：18 个，`py_compile=PASS`，全部 `--help=PASS`；
- 官方 quick validation：显式 `PYTHONUTF8=1` 后 `Skill is valid!`；
- action profile：41 AVAILABLE、0 UNAVAILABLE、23 READABLE、3 EXCLUDED_CONFIG；
- generator projection：30 文件，两次独立构建的 manifest 与 tree 完全相同；
- capability source SHA-256：`775df5afe709f00c06065f32668d0dc53b5a74cd6b04ecc938e657ed3351c123`；
- projection manifest SHA-256：`5f9fc7e3a349c0d7ab475e628a90392c7066d615cba04ba0e9c28769aa779d3d`；
- projection tree SHA-256：`ab0d1b194f85d7eb16458a3279cbcb194728ce9cdf089bcf982177b6b5dcdc5e`；
- contract SHA-256：`113e9187a84a013228b16ee681db1d8f1ab0a443d6088e981f085c144039b8ef`；
- requirements SHA-256：`040026c59c6b27f5f4031e23338a6503b653c50f0669b31c79f7d02d52ecedf3`；
- oracle SHA-256：`8d0c837209c87332d948758edcaaaa900df4195823ad7c1c5a06b081566f1d0a`；
- qualification：`integrity=PASS / NOT_EVALUATED / 0 of 176`。

工件：[projection A](build/generator-projection-maturity-v15-a-20260716-manifest.json)、
[projection B](build/generator-projection-maturity-v15-b-20260716-manifest.json)、
[qualification](build/qualification-maturity-v15-20260716-no-manifest.json)、
[action profile](build/maturity-v15-action-profile-20260716.json)、
[main AUTO](build/maturity-v15-real-main-auto-20260716/run_metadata.json)、
[physics AUTO](build/maturity-v15-real-physics-auto-20260716/run_metadata.json) 和
[CET6 AUTO](build/maturity-v15-real-cet6-auto-20260716/run_metadata.json)。

### 19.9 当前成熟度结论

v15 可以称为成熟的**确定性中文学术文风终审工具链**：它能固定输入、保护硬不变量、按 unit
路由、绑定 Voice、拒绝常见重封与伪完成态，并且对未决返回 REVIEW。它仍不能称为已经完成
生产资格的**生成模型**，原因有四项且不可用测试数量覆盖：

1. 176 个真实 blind-forward/E4 原子仍为 0/176；
2. RESEARCH、GENERAL、REPORT 缺少合格正向人类语料，只能诚实使用 NONE；
3. 本地 runner 只有 E2，没有宿主排除根不可达、完整 generator context 和外部签名信任根；
4. 本轮没有运行真实 Codex fresh campaign，fake runner 只证明控制面合同。

因此当前准确说法是：工具链的拒错能力和审计成熟度已显著提高，常规生产改写可使用，但每次
正文仍须经过实际 validator/finalizer；不能宣称“模型已经稳定学会真人文风”或“全文必然无 AI
味”。

## 20. 第十六轮：把“人工读过”与“人写来源”彻底拆开

### 20.1 v15 仍然留下了什么来源越权

v15 已把用户明确标注的 GPT `main.tex` 和 CET6 TeX 从正向语料移出，但继续审计时发现，
`build_humanize_action_profile.py` 只禁止 `MODEL_GENERATED` 成为
`positive_action_reference`。这仍然放过两类材料：

- `MODEL_ORIGIN_UNRESOLVED`：路径层有 assistant-output 证据，但句级归属未建立；
- `UNKNOWN`：材料经过独立评估代理阅读和动作蒸馏，但没有证据证明正文由人创作。

旧构建器只要看到来源可读、登记行非空，就把卡标为 `AVAILABLE`；场景支持只统计来源或
composition family 数量，不要求 `HUMAN_CONFIRMED`。`origin_assurance=UNRESOLVED_PRESENT`
只是一个旁路说明，不会改变 `SUPPORTED`。候选门又规定 `SUPPORTED` 场景不能使用
`corpus_action_support=NONE`，因此 UNKNOWN 卡可以进入 accepted 队列。这不是措辞不严谨，而是
真实的 fail-open 路径。

独立来源审计在不知道预定修复方案的情况下重新数了一遍 catalog，得到相同结论：旧 31 张正向
卡中，人类创作来源证据为 0；8 个 `UNKNOWN` 来源支撑 17 张卡，3 个
`MODEL_ORIGIN_UNRESOLVED` 来源支撑 14 张卡。“Manually audited”只能证明有人看过，不能证明
原文由人创作。

### 20.2 被撤销的 14 张正向卡

三份来源现在保留 ID、路径、provenance 和排除理由，但 role 改为
`origin_unresolved_excluded`。构建器不打开这些文件，复制检查也不把它们重新纳入：

| 来源 | 撤销卡数 | 撤销动作 |
|---|---:|---|
| `SOURCE-MODELING-METHOD-SECTION` | 1 | `MODELING-METHOD-BOUNDARY-01` |
| `SOURCE-MODELING-PAPER-MAIN` | 7 | data role、identifiability、handoff、controlled contrast、trajectory classification、process/outcome、explanation boundary |
| `SOURCE-MODELING-PAPER-CN` | 6 | intervention isolation、proxy fallback、endpoint/trajectory、budget comparison、negative control、backend boundary |

被删除的完整 ID 为：

1. `MODELING-METHOD-BOUNDARY-01`；
2. `MODELING-DATA-ROLE-01`；
3. `MODELING-IDENTIFIABILITY-01`；
4. `MODELING-UPSTREAM-HANDOFF-01`；
5. `MODELING-CONTROLLED-CONTRAST-01`；
6. `MODELING-TRAJECTORY-CLASSIFICATION-01`；
7. `MODELING-PROCESS-OUTCOME-SEPARATION-01`；
8. `MODELING-EXPLANATION-BOUNDARY-01`；
9. `MODELING-INTERVENTION-ISOLATION-01`；
10. `MODELING-PROXY-FALLBACK-01`；
11. `MODELING-ENDPOINT-TRAJECTORY-01`；
12. `MODELING-BUDGET-COMPARISON-01`；
13. `MODELING-NEGATIVE-CONTROL-01`；
14. `MODELING-BACKEND-BOUNDARY-01`。

删除卡不等于否定这些抽象动作在写作上可能有用；它只表示当前材料不足以给这些动作贴上
“人类正向语料支撑”的标签。以后若有真正独立的 `HUMAN_CONFIRMED` 材料，可以重新建立新卡，
但不能沿用旧来源身份或旧 profile。

### 20.3 新的来源允许列表与卡级标记

构建器不再采用“只禁止已知坏来源”的黑名单，而是把正向来源收窄为允许列表：

| `origin_class` | 可否登记正向卡 | 卡级 assurance | 场景作用 |
|---|---|---|---|
| `HUMAN_CONFIRMED` | 可以 | `PRODUCTION` | 达到独立来源门槛后计入 `SUPPORTED` |
| `UNKNOWN` | 可以，但只作临时组织参考 | `PROVISIONAL` | 达到数量门槛也只能 `SUPPORTED_PROVISIONAL` |
| `MODEL_GENERATED` | 不可以 | 仅 `NEGATIVE_ONLY` | 带 detector 的负例或审计 |
| `MODEL_ORIGIN_UNRESOLVED` | 不可以 | 排除或 `NEGATIVE_ONLY` | 不读取正向排除项；带 detector 的负例可保留 |
| `OCR_INHERITED` | 不可以 | 负例/保护角色 | 不作人类散文依据 |
| `THIRD_PARTY` | 不可以 | 负例/审计 | 不作作者正向语料 |

`HUMAN_CONFIRMED` 也不是外部身份签名。它只表示当前来源台账明确记录“由人创作”，使该来源有
资格参与动作支持计算；它不证明 PERSONAL Voice、具体作者身份、事实正确、学术质量或复制许可。

每张 profile 卡现在输出 `source_origin_classes` 和 `origin_assurance`。这样即使未来一个场景同时
存在 production 与 provisional 卡，候选门仍能按选中的具体卡裁决，不会让 UNKNOWN 卡借场景的
总体 `SUPPORTED` 状态进入 PASS。

### 20.4 三态场景支持与生产路径

场景支持改成三态：

| 状态 | 成立条件 | `ACTION_CARDS` | `NONE` |
|---|---|---|---|
| `SUPPORTED` | 足量独立 `HUMAN_CONFIRMED` 正向来源 | 可继续其他门 | 不允许无理由绕开当前生产语料 |
| `SUPPORTED_PROVISIONAL` | 总来源达到门槛，但生产来源不足 | 固定 `REVIEW/2` | 允许，继续普通文风门 |
| `CORPUS_INSUFFICIENT` | 连 provisional 数量门槛也未达到 | 固定 `REVIEW/2` | 允许，继续普通文风门 |

选用 provisional 卡时结果同时记录：

```text
provisional_action_card:<card-id>
scene_corpus_origin_unresolved:<scene>
```

这两个 review 不能用空泛 KEEP 理由、调用方自称人工或旧 profile 清除。改用 `NONE` 不是绕过
公式、引语、数字、言语行为和 AI 风味门；它只表示本次组织动作不声称由语料卡支撑，后续统一
validator 仍完整运行。

当前 profile 的实际状态为：

| 场景 | 正向卡 | production 卡 | 状态 | 生产策略 |
|---|---:|---:|---|---|
| COURSE | 4 | 0 | `SUPPORTED_PROVISIONAL` | `corpus_action_support=NONE` |
| MODELING | 13 | 0 | `SUPPORTED_PROVISIONAL` | `corpus_action_support=NONE` |
| RESEARCH | 0 | 0 | `CORPUS_INSUFFICIENT` | `corpus_action_support=NONE` |
| GENERAL | 0 | 0 | `CORPUS_INSUFFICIENT` | `corpus_action_support=NONE` |
| REPORT | 0 | 0 | `CORPUS_INSUFFICIENT` | `corpus_action_support=NONE` |

因此，当前安装版没有一个 production action-card 场景。Skill 仍可按原稿、supplied content、
场景规则和 Voice Profile 执行生产改写；它只是不能再借未知来源卡增强完成声明。

后验评估进一步指出：仅要求候选包填写 `NONE`，不能证明生成器在此前没有读过 provisional 卡。
因此 generator projection 新增 strict JSON transform：完整安装版继续保留 17 张 provisional 审计卡，
生成能力面中的 catalog 则删除这些卡、对应动作描述、8 个正向来源记录和所有外部路径。当前投影
只含 10 张 negative guard、10 个本地相对 stub 来源、0 张正向卡、0 个绝对来源路径。`NONE` 仍
不能证明模型在 projection 之外的心理来源；本地 runner 的宿主隔离也仍是 UNVERIFIED，但固定
30 文件能力面不再主动把未知正向动作喂给生成器。

### 20.5 合同和红队回归

资格矩阵新增三个 P0 来源原子：

- `ROLE-11`：`HUMAN_CONFIRMED` 只有资格，不自动证明 Voice、身份、事实或复制许可；
- `ROLE-12`：`UNKNOWN` 正向卡固定 provisional，选卡候选不得 accepted；
- `ROLE-13`：`MODEL_ORIGIN_UNRESOLVED` 不得正向，排除项不得读取或用旧缓存复活。

`ROLE-10` 继续约束明确模型生成来源。矩阵从 176 扩为 179；requirements 升为 `2.2.0`，
contract 升为 `2026-07-16.8`，oracle catalog 升为 `1.3.0`。这些原子目前没有被单元测试冒充
blind-forward：正式无 manifest 审计仍为 `0 PASS / 0 FAIL / 179 NOT_EVALUATED`。

新增回归覆盖：

- `MODEL_ORIGIN_UNRESOLVED + positive_action_reference` 构建失败；
- `UNKNOWN` 卡输出 `PROVISIONAL`，场景只能 `SUPPORTED_PROVISIONAL`；
- `HUMAN_CONFIRMED` 卡才输出 `PRODUCTION`；
- provisional 卡候选进入 rejected，状态 `REVIEW/2`；
- 同一 provisional 场景使用 `NONE` 可以在风格门通过后 PASS；
- 三份来源均为 `EXCLUDED_CONFIG + origin_unresolved_excluded`；
- 旧 14 张卡不再出现在 catalog、profile 或场景指南；
- generator projection 中 17 张 provisional 卡、其动作描述和外部来源路径全部消失；
- 任意外部 `--catalog` 固定 `EXTERNAL_UNVERIFIED`，自填 `HUMAN_CONFIRMED` 的选卡候选保持
  `REVIEW/2`，不得 accepted；
- Windows 新 queue 在约 294 字符 history 目的路径上的 `FileNotFoundError` 已真实复现；候选 ID
  与嵌套 artifact/evaluation/run 使用短存储键，文件内容仍保留完整哈希并由 immutable conflict
  防覆盖，长路径回归现可发布；
- capability 内容变化而 policy 未批准时，资格审计整批 fail-closed；批准新 hash 后才能恢复。

第一次独立候选门代理因外部安全过滤没有产生有效结果，本报告没有把它写成“已通过”。后续使用
不泄漏预期答案的中性后验任务重新运行，代理用六类 origin 临时矩阵确认 UNKNOWN 选卡为 REVIEW、
外部自填 HUMAN 原先可 PASS，并复现 Windows queue 发布失败。主流程没有把两项写成局限后结束，
而是加入 projection filter、external catalog review 和长路径发布回归。来源审计代理的 0/31
人类来源判断也与主流程独立一致。

### 20.6 v16 可复核机器快照

- 全量 unittest：`Ran 461 tests in 66.370s`，`OK (skipped=1)`；
- 唯一跳过：当前 Windows 账户无创建 symlink 权限；
- Skill Python：18 个，`py_compile=PASS`，全部 `--help=PASS`；
- 官方 quick validation：`Skill is valid!`；
- action profile：26 个来源，20 READABLE、6 EXCLUDED_CONFIG；27 张 AVAILABLE、0
  UNAVAILABLE；17 张 provisional 正向卡、0 张 production 正向卡、10 张 negative guard；
- 两次最终 projection：30 文件，capability、manifest 和 tree 完全相同；
- projected catalog：10 张 negative guard、0 张正向卡、0 个绝对/外部来源路径；
- capability source SHA-256：`eb4560b1142eff5bd927ac83ce3f2231c84438f1e23752ec816c6c0f01c2b651`；
- projection manifest SHA-256：`06afd012bcc5e34b091a3a7ac1a0c2e4ebead53cdf427a6f696208a1e4f94096`；
- projection tree SHA-256：`f21858bbc040ef26e304364a64d88affb2965091a697d7d1c01388cd99be1360`；
- contract SHA-256：`6e89bc3cf4ae1889916f53f0ed9065c5500b6ee532d1fed1b68ae962ebb0f0b5`；
- requirements SHA-256：`8b38fcde6e4dc75cb38c62549d759cb21452fe95cbe6daf33d9818c0b0f54ce5`；
- oracle SHA-256：`672a3dfac7d02b9ff2991e7923c267edc1fbf3c00c9495af484f328fa8470015`；
- qualification：`integrity=PASS / qualification=NOT_EVALUATED / 0 of 179 / exit 2`。

工件：[final projection](build/generator-projection-maturity-v16-final-20260716-manifest.json)、
[repro projection](build/generator-projection-maturity-v16-repro-20260716-manifest.json)、
[qualification](build/qualification-maturity-v16-20260716-no-manifest.json) 和
[action profile](build/maturity-v16-action-profile-20260716.json)。

### 20.7 v16 后的成熟度结论

v16 提高的不是“生成更像人”的主观分数，而是正向学习材料的可信边界。当前 Skill 可以继续
称为成熟的确定性终审、保护、路由、Voice 绑定和拒错工具链；它比 v15 更少依赖来源卡，但不再
把未知来源包装成人类表达证据。

生成模型仍不能称为生产资格通过：179 个真实 E3/E4 原子仍为 0/179，当前没有 production
action-card 场景，本地 runner 仍只有 E2，也没有代理不可访问私钥的外部身份和隔离信任根。
生产任务可以使用 Skill 的 `NONE + validator/finalizer` 路径；不能声称“模型已经从人类语料学会
稳定去 AI 味”，也不能把 provisional 卡数量、461 项单元测试或 projection 可复现性改写成这一
结论。

## 21. 第十七轮：本地来源声明不再等于 production 信任

### 21.1 触发本轮的两个真实 fail-open

v16 已把当前 catalog 的 production 卡降为 0，但后验红队证明这只是“当前数据没有触发”，并非
合同层不可触发。旧实现存在两条本地主体可控路径：

1. `build_humanize_action_profile.py` 只要看到 `origin_class=HUMAN_CONFIRMED`，就直接把正向卡写成
   `origin_assurance=PRODUCTION`；`provenance/source_tier/use_limit` 都是未验证字符串。
2. 候选门以 `catalog_path == DEFAULT_CATALOG` 判定 `INSTALLED_DEFAULT`。测试和本地主体都能重绑或
   修改默认 catalog；同一主体还可以修改 projection approval hash。临时复现确实得到
   `PASS + accepted=true + PRODUCTION`，并非理论风险。

另一个独立性漏洞是：缺少 `composition_family_id` 时，旧 profile 以 source ID 计独立来源。同一
文件复制成两个 ID，GENERAL 就能伪造两个独立来源。v17 不再用“当前恰好没有 HUMAN 卡”掩盖这些
路径，而是让本地工具根本没有 production promotion 能力。

### 21.2 固定来源信任矩阵

新增 [source-provenance-trust.json](C:/Users/Lenovo/.codex/skills/humanize-academic-chinese/references/source-provenance-trust.json)。
当前 policy 固定 `production_attestation.enabled=false`、`accepted_schemes=[]`、
`external_verifier_required=true`、`local_claims_are_identity_proof=false`。其裁决为：

| origin class | production positive | assurance | 允许用途 | 理由码 |
|---|---|---|---|---|
| `HUMAN_CONFIRMED` | false | `PROVISIONAL` | audit / experimental positive review | `EXTERNAL_ATTESTATION_REQUIRED` |
| `UNKNOWN` | false | `PROVISIONAL` | audit / experimental positive review | `ORIGIN_UNKNOWN` |
| `MODEL_GENERATED` | false | `NEGATIVE_ONLY` | audit / negative guard | `MODEL_TEXT_NEGATIVE_ONLY` |
| `MODEL_ORIGIN_UNRESOLVED` | false | `NEGATIVE_ONLY` | audit / negative guard | `MODEL_ORIGIN_UNRESOLVED_NEGATIVE_ONLY` |
| `OCR_INHERITED` | false | `NEGATIVE_ONLY` | audit | `OCR_PROVENANCE_NOT_AUTHOR_VOICE` |
| `THIRD_PARTY` | false | `NEGATIVE_ONLY` | audit | `THIRD_PARTY_NOT_AUTHOR_VOICE` |

builder 与 hidden auditor 分别维护同一固定矩阵并独立校验 JSON。修改 policy 试图打开 production、
添加 `CALLER_JSON` scheme、在 source 中自填 `origin_attestation`，都会直接构建失败。这里没有宣称
已经实现外部信任根；相反，production 路径明确为 unavailable。以后若要开放，必须新增真正的
外部 verifier 和代理不可访问的私钥链，不能只改本地 JSON。

独立来源计数也改成 fail-closed：显式 family 相同算一个；没有 family 时，相同内容 SHA-256 算
一个；内容不可得时才退到规范化路径。当前 MODELING 的 6 个 provisional source ID 因 family/
内容去重只计 4 个独立单元，复制 ID 不再增加门槛计数。

### 21.3 production surface 与 audit surface 物理拆分

v16 projection 虽然没有正向卡，仍暴露候选包、warning proposal、accepted/rejected queue、来源
tier 和 provenance 台账。v17 把以下内容移出 generator projection：

- `prepare_humanize_candidate_revision.py`；
- `validate_humanize_candidate_queue.py`；
- `SKILL.md` 的“来源动作候选审计”路由和整个候选入队章节；
- 全部 positive action、动作描述、正向 source record 和外部来源路径；
- negative source 的原始 `source_tier/provenance/use_limit`。

长文 finalizer 仍需要 negative detector，因此投影保留 `build_humanize_action_profile.py`、固定来源
policy 和经过变换的 detector-only catalog。该 catalog 只有 10 张 negative guard、10 个最小
stub source；source tier 固定为 `DETECTOR_ONLY`，path 固定为投影内相对文件。它不含 positive
card、候选队列或外部绝对路径。能力面由 30 文件减为 29 文件，其中 25 个原样能力文件、4 个
确定性 transform 文件。

两次正式构建得到相同 manifest 字节和 tree：

- capability source SHA-256：`8287b1cc815e0fc6d978ee95bd04a27d084ec5c01a5aa2d756b40b53a7cfbde6`；
- projection manifest SHA-256：`e3550669d5ed24e6829de3813f018380435372ed69ae242db780cf31bf990f61`；
- projection tree SHA-256：`0a44307a7602f982f375bdfd3e209732250c3c6f3c12de48b82e555bf96c30b9`；
- `declared_external_capability_refs=[]`；
- projected positive card 0、negative guard 10、候选脚本 0。

旧 v10-v15 projection 目录仍作为历史工件保存在 `build/`，其中若干旧 catalog 含绝对路径。本轮
没有删除历史证据，也没有把它们描述成安全缓存。当前 runner 只重建并绑定 v17 tree；由于宿主
文件系统隔离仍未证明，报告继续明确：clean projection 不等于旧目录或 oracle 对进程不可达。

### 21.4 `ROLE-10` 至 `ROLE-13` 从合同原子变成可运行 suite

v16 虽有 179 原子，但 oracle catalog 只有 5 个 SHADOW suite，`ROLE-10` 至 `ROLE-13` 没有
fixture、check 或 fresh 入口。v17 将 oracle schema 升到 v2，新增 4 个
`FRESH_FORWARD/runner_compatible=true` suite：

- public input 只给中性 source record、origin class、请求角色和 `attestation=ABSENT`；
- public prompt 只要求固定 JSON 字段，不出现 ROLE ID、assurance、理由码或预期答案；
- public context 使用 `operation=CLASSIFY_SOURCE_PROVENANCE`；
- hidden check 从固定 source policy 计算完整期望，再严格比较 output JSON；
- current manifest 仍只能提交 `claim_id/atom_id/oracle_suite_id`，不能自选 expected/check。

一个自报 `HUMAN_CONFIRMED + PRODUCTION + production_positive=true` 的候选在隐藏 check 中固定
`FAIL`。四种正确裁决在确定性 E2 测试中 check 均为 PASS，但 ROLE 原子要求 E3，所以 claim 仍是
`NOT_EVALUATED`。这一区分防止“hidden check 会判分”被写成“生成模型已通过”。catalog 当前为
9 个 suite、15 个 machine check、1 个 rubric；contract 为 `2026-07-16.9`，requirements 为
`2.3.0`，oracle catalog 为 `1.4.0`。

### 21.5 真实 fresh runner 结果没有被美化

四个 public case 已实际封存。并行 fresh campaign 在 244 秒外层时限被终止；随后单例重跑在
300 秒内仍不返回。最后用 runner 自身 `--timeout 60` 对最危险的 `HUMAN_CONFIRMED` case 留下
明确 receipt：

- `runner_status=INFRA_INVALID`；
- `timed_out=true`；
- `output_present=false`；
- `projection_audit_status=NOT_COMPLETED`；
- 新进程已观察到，但没有 provider request/response ID；
- 当前 run 的 `evidence_attained=E0`，本地 runner 的能力上限仍为 `evidence_cap=E2`。

因此本轮没有 fresh 行为 PASS/FAIL，只有基础设施无效证据。CLI 已修正失败输出，不再把 E0
attained 与 E2 cap 混成同一个 `evidence_cap=E0` 字段。receipt 位于
`build/maturity-v17-source-forward-20260716/runs-timeout-evidence/source-b/runner-receipt.json`。

### 21.6 v17 回归与机器快照

- 全量 unittest：`Ran 468 tests in 69.759s`，`OK (skipped=1)`；
- 唯一跳过：当前 Windows 账户无创建 symlink 权限；
- 18 个 Skill Python 脚本：`py_compile=PASS`、全部 `--help=PASS`；
- `quick_validate.py`：`Skill is valid!`（Windows 下用 `python -X utf8`，避免系统 GBK 误读）；
- action profile：26 个来源，20 READABLE、6 EXCLUDED_CONFIG；27 张 AVAILABLE、0 UNAVAILABLE；
  17 provisional positive、0 production positive、10 negative guard；
- scene：COURSE 2 个独立 provisional source，MODELING 4 个，二者均
  `SUPPORTED_PROVISIONAL`；RESEARCH/GENERAL/REPORT 为 `CORPUS_INSUFFICIENT`；
- qualification：`evidence_integrity_status=PASS`、`qualification_status=NOT_EVALUATED`、
  `0 PASS / 0 FAIL / 179 NOT_EVALUATED`、exit 2；
- contract SHA-256：`1f9222e3395c4099b373f60c36070e2d2ed1bb04eab4a547369de8295573ea82`；
- requirements SHA-256：`34eed975c63006ff88e818e6edaf329357faa00240517cd4d069ce4f6c4b378a`；
- oracle SHA-256：`249d429d58fb13d57d3f20dc412a7073782542fbdb23a2f781727b2a2270f168`；
- source trust policy SHA-256：`4d0c6f9e5cd301088af56b10e5414c327cba6f6cb9a4116f5d6f04cdf2857607`。

正式工件：[action profile](build/maturity-v17-action-profile-20260716.json)、
[stable projection](build/generator-projection-maturity-v17-stable-20260716-manifest.json)、
[stable repro projection](build/generator-projection-maturity-v17-stable-repro-20260716-manifest.json)、
[qualification](build/qualification-maturity-v17-stable-20260716-no-manifest.json) 和
[fresh timeout evidence](build/maturity-v17-source-forward-20260716/runs-timeout-evidence/source-b/runner-receipt.json)。

### 21.7 当前成熟度裁决

v17 关闭了“本地 HUMAN 字段即可升 production”“默认路径即可信”“复制 source ID 制造独立来源”
三类来源信任假闭环，并把候选审计面从正常生成能力面移除。确定性终审、保护、路由、Voice 绑定、
长文发布和拒错工具链继续可用于生产；来源动作卡现在明确只是 audit/provisional 资产。

仍不能声称 Skill 的生成模型已经成熟到一次生成稳定合格：外部来源 attestation 尚未实现，179 个
E3/E4 原子仍为 0/179，宿主 oracle/旧 projection 不可达性未证明，本轮真实 fresh runner 也没有
产生 output。当前准确说法是：**生产文风门更难被伪造，production generator surface 更小，来源
资格更诚实；生成能力资格仍未完成。**

## 22. 第十八轮：detector-only 运行时、来源负例权限与 runner 诊断

### 22.1 本轮删除了不该存在的生产能力

v17 声称 generator projection “只保留 negative detector registry”，实际却仍携带完整
`build_humanize_action_profile.py`。负例卡也仍有 `action/requires/forbids`、来源行号、来源角色和
stub source record。finalizer 的真实依赖只有 guard 的 `id/scene/status/detector`，其中 `status`
还可以由 strict loader 派生。

v18 新增 `scripts/load_humanize_negative_guards.py`，把生产数据合同固定为：

```text
humanize-negative-guard-registry/v1
  registry_id
  guards[]
    id
    scene
    detector
      minimum_groups
      pattern_groups[]
        id
        regex
        minimum_occurrences
```

持久化 registry 不再含 `sources/source_refs/origin_class/source_tier/path/action/requires/forbids`。
finalizer 直接 import 这个 loader；完整 action-profile builder 只留在安装版来源/候选审计面，
不再进入 generator projection。兼容字段 `action_catalog_sha256/action_profile_sha256` 暂时保留，
但现在分别绑定 registry 原始字节与 canonical detector registry，不再暗示正向动作可执行。

### 22.2 红队发现 negative guard 绕过了来源信任矩阵

后验审计逐张反查当前 10 张负例卡的来源类别。v17 policy 只允许 `MODEL_GENERATED` 与
`MODEL_ORIGIN_UNRESOLVED` 使用 `NEGATIVE_GUARD`，代码却把以下 6 张无此权限的卡全部标为
`AVAILABLE` 并送入投影：

- `NEGATIVE-MODELING-README-SHELL-01`：`UNKNOWN`；
- `GENERAL-NEG-GOVERNANCE-VOICE`：`UNKNOWN`；
- `GENERAL-NEG-RESEARCH-JOURNAL-OVERFIT`：`UNKNOWN`；
- `GENERAL-NEG-OPINION-AS-EVIDENCE`：`THIRD_PARTY`；
- `GENERAL-NEG-OCR-AND-TEXTBOOK`：`OCR_INHERITED`；
- `GENERAL-NEG-API-TEMPLATE`：`UNKNOWN`。

这不是命名瑕疵。`THIRD_PARTY/OCR_INHERITED` 在固定 policy 中只允许 `AUDIT`；`UNKNOWN` 只允许
`AUDIT/EXPERIMENTAL_POSITIVE_REVIEW`。让这些卡进入 production finalizer，相当于把“可观察”
扩大成“可拦截”。v17 的 ROLE fresh fixture 又只测试 `positive_action_reference`，测不到这条旁路。

v18 在三个位置同时修复：

1. 完整 builder 按固定 `allowed_uses` 计算 `negative_guard_runtime_authorized`；无权限卡变为
   `AUDIT_ONLY`，不会伪装成普通 `UNAVAILABLE`。
2. candidate queue 自动扫描跳过 `AUDIT_ONLY`；只有明确获权且 `AVAILABLE` 的卡执行。
3. projection transform 使用同一冻结 trust policy 过滤；本地给 `UNKNOWN/THIRD_PARTY` 追加
   `NEGATIVE_GUARD` 会因整张决策矩阵漂移而构建失败。

修复后的完整安装版为 17 张 provisional positive、4 张 runtime negative guard、6 张 audit-only
negative definition；production positive 仍为 0。四张 runtime guard 分别覆盖
`ALL/GENERAL/MODELING/RESEARCH`，来源均为明确模型文本或模型来源未解析文本。

### 22.3 strict loader 的拒错面

以下输入全部抛出 `NegativeGuardRegistryError`：

- 非 UTF-8、重复 JSON key、NaN/Infinity、顶层或 guard 未知字段；
- 空 guard 集、重复 guard ID、非法 scene；
- detector 缺组、`minimum_groups` 越界、重复 group ID；
- regex 不可编译或异常过长；
- `minimum_occurrences` 为布尔值、非正整数或异常过大；
- 完整 catalog 缺冻结 trust policy、来源 ID 重复、source ref 悬空；
- trust policy 版本、attestation 关闭状态或任一 origin decision 与固定矩阵不一致。

registry 缺失或非法时，跨 unit 门输出
`NEGATIVE_GUARD_REGISTRY_UNAVAILABLE:<ErrorType>`，状态固定为 `REVIEW`，不得按空 guard 集合
继续 PASS。结果同时保存原始 registry hash、canonical registry hash、loader 版本、来源格式、
逐 detector definition hash 和 finding fingerprint。

### 22.4 projection 的实际最小面

最终 generator projection 仍为 29 文件，但发生了能力替换：

- 新增 `load_humanize_negative_guards.py`；
- 删除 `build_humanize_action_profile.py`；
- `corpus-action-sources.json` 变为 `humanize-negative-guard-registry/v1`；
- 顶层字段严格只有 `guards/registry_id/schema_version`；
- 每张 guard 严格只有 `detector/id/scene`；
- guard 数由 v17 的 10 张降为 policy 真正授权的 4 张；
- `source-provenance-trust.json` 仍供来源分类，但 finalizer 不解析正向卡或来源台账。

两次最终构建完全一致：

- capability source：`dea6d198581bbb6870ae97b6d9d8fe89b0f8cc7970eaf2da1aec4b9df152a909`；
- manifest：`1328011e86a51e78875da900d1733b1e1380e15d31259999dbd0ed4c9d6f4c6a`；
- tree：`42eacd2c9c52f1e75305d7958d0197f3aeed3baa099f081fcd977876135db9b1`；
- 文件数：29；builder absent、loader present、4 guards、0 positive card。

### 22.5 v17 fresh timeout 的可证结论

对 v17 `source-b` 的原始 events、receipt、prompt 和进程信息复核后，只能得到基础设施结论：

- public case、seal、projection 和 preflight 已完成；
- CLI 出现 `thread.started` 与 `turn.started`；
- 随后出现 `Reconnecting... 2/5 (request timed out)`；
- 60 秒外层时限终止进程树；
- 没有 provider request/response ID、没有 output、没有 post-run projection audit；
- prompt 仅 814 字节，没有证据表明任务内容触发拒绝；
- 当时 runner 源码没有随 receipt 封存，当前源码不能冒充当时 executable 的逐字快照。

所以 `returncode=1` 不能写成模型行为 FAIL，Skill budget warning 也不能当终止错误。准确状态仍是
`INFRA_INVALID / INVOCATION_TRANSPORT / WAITING_PROVIDER_RESPONSE / E0`，模型行为未评估。

### 22.6 runner 1.2 的观察工件

本轮没有自动重放真实请求，以免重复计费和破坏 fresh-run 独立性。runner 1.2 在以后运行中新增：

- `request/invocation.json`：sanitized argv、runner 源码 hash、CLI hash/version、实际 timeout、
  900 秒资格最低时限、运行用途、`NO_AUTOMATIC_RETRY`；
- `transcript/observation.json`：started/deadline/ended、return code、终止方式、事件类型计数、
  reconnect 次数、最后事件、输出状态、失败域/阶段、`model_behavior_evaluated` 与 attained evidence。

两份工件与 `request/runner-source.py` 都由 receipt 绑定 SHA-256。`--timeout < 900` 固定为
`DIAGNOSTIC_SHORT_TIMEOUT`，不能进入资格。默认 900 秒只满足时限条件，不自动形成 E3。
当前事件捕获仍是 `BUFFERED_AFTER_PROCESS_EXIT`，没有逐事件接收时间或 heartbeat；报告明确保留
这一观察盲区，没有写成“已实现实时流式监控”。

second-pass verifier 已同步要求这些活工件、E2 observation、runner source snapshot 与 receipt hash
一致。缺失、篡改、短时限、自动重试声明或 runner 漂移都会使收敛验证失败。

### 22.7 资格合同与状态

隐藏资格绑定更新为：

- contract：`2026-07-16.10`，SHA-256
  `01294a453adad871ee954e006e3eab78dc94b86686992cf1ddd9973ba6495b56`；
- requirements：`2.4.0`，SHA-256
  `b84891e849116de73ed4554d85ccf8ce1e211c2f5ae0026f78e2bb07fcb3f51d`；
- oracle catalog：`1.5.0`，SHA-256
  `ae3488b58884db141bd4eab662989f7bc84e496f6bc1bce56517776434ffcd01`。

无 manifest 的正式审计仍是
`integrity=PASS / qualification=NOT_EVALUATED / 0 PASS / 0 FAIL / 179 NOT_EVALUATED / exit 2`。
本轮没有把 deterministic loader tests、projection build 或 timeout classification 填进 179 个 E3/E4
行为原子，也没有把旧 timeout 重解释成 ROLE suite 结果。

### 22.8 回归与正式工件

- 全量：`Ran 481 tests in 56.612s`，`OK (skipped=1)`；
- 跳过项：当前 Windows 账户无 symlink 创建权限；
- 19 个脚本：`py_compile=PASS`、`--help=PASS`；
- `quick_validate.py`：`Skill is valid!`；
- action profile：21 AVAILABLE、6 AUDIT_ONLY、0 UNAVAILABLE；17 provisional positive、
  0 production positive、4 runtime guard、6 audit-only guard；
- action profile SHA-256：`6cabef43e3ea7157cba4ae307251c60a936737e9f85c82aae45e44d63d710f3a`；
- qualification report SHA-256：`4477dcea55d6550e6b095e48f5b034dc592e9424e7a78473f1af33b813835bc0`。

正式工件：

- [v18 action profile](build/maturity-v18-action-profile-20260716.json)
- [v18 final projection](build/generator-projection-maturity-v18-final-20260716-manifest.json)
- [v18 final repro projection](build/generator-projection-maturity-v18-final-repro-20260716-manifest.json)
- [v18 qualification](build/qualification-maturity-v18-final-20260716-no-manifest.json)
- [v17 timeout evidence](build/maturity-v17-source-forward-20260716/runs-timeout-evidence/source-b/runner-receipt.json)

### 22.9 当前成熟度裁决

v18 关闭了两个让“最小生产面”名不副实的漏洞：完整正向 action builder 不再进入生成面；来源
policy 也不再只约束正向卡而放任负例卡。现在可证的是：detector 运行时字段足够小、来源权限在
builder/loader/projection/candidate/finalizer 多层一致、registry 故障会拒绝错误完成态、timeout 不会
冒充模型失败。

仍不能称为成熟的“生成模型”：真实 fresh output 本轮为零，179 个行为原子仍未评估，宿主排除根
不可达性未证明，外部 human attestation 不存在，事件流也没有逐事件时间戳。当前准确定位是：
**确定性纯文风终审与长文拒错工具链更接近生产稳定；生成器本身仍未取得前向资格。**

## 23. v19：用真实成对质量替代“删词即完成”

### 23.1 为什么继续迭代

v18 解决了来源权限和最小生产面，却没有回答普通调用最实际的问题：validator `PASS/0` 的稿子，
是否真的比原文自然。v19 从真实 TeX 片段建立三个不泄漏答案的 fresh case：惠更斯原理课程讲解、
珍稀物种建模说明、四大家鱼校准与 CPUE 研究讨论。三份输入均只作为 GPT 风味负例，不作为真人
正向范文或 PERSONAL Voice。

首轮三个生成候选全部得到旧 validator `PASS/0`，独立盲评却给出不同结论：

| 场景 | 旧候选盲评 | 自然度/忠实度 | 暴露的问题 |
|---|---|---|---|
| COURSE | 偏好 B，可交付 | B 8.8，忠实度 10.0 | 收益真实但很小，“换一个角度看”略模板化 |
| MODELING | A/B 平局，不可直接交付 | B 8.3，忠实度 9.2 | 删除表格引介职责，新增主语错位和抽象路径壳 |
| RESEARCH | 偏好 A，不可直接交付 | B 7.8，忠实度 9.7 | 首句“按……闭环收紧”搭配错误，长句被机械拆平 |

这说明原门禁只证明公式、数字、TeX、显式 high 词项和已编码言语行为没有失败，不能证明病句、
段落职责和论证层级。尤其“更短、短句更多、连接词更少”不能直接等价于 Humanize 成功。

### 23.2 从失败反推的质量门

本轮没有按盲评答案逐句写死，而是补入可迁移的四层约束：

1. **段落职责不变量**：改写前内部记录段落是在定义、解释、引介图表、比较、限定还是展开并列
   分支。不能把“说明表格为何这样组织”改成另一遍结果概括。
2. **论证层级保护**：拆句先标总论、细节、排除、并列、因果和回指；不得按逗号、分号平均切割，
   也不得把“唯一硬锚点—固定初值—局地软约束”切成同构清单。
3. **成对优越性门**：validator 通过后逐段 A/B；只有至少一项具体读感收益、没有新增缺陷、职责
   与层级均保留时才接受修改，否则继续改写或恢复原段并记 `NO_CHANGE`。
4. **焦点作用域门**：`重点/主要/优先` 进入言语行为计数。把“重点不是比较”改成绝对的“不比较”
   会产生 `SPEECH_ACT_FOCUS_SCOPE_CHANGED`，交付固定为 `REVIEW/2`。

词库升级到 1.2.0：单个“实证/论证/分析闭环”和“抽象关系由 A 出发，经 B，最终落到 C”进入
`LEX-MGMT-01` high 候选；“表格的作用”从无条件编辑后台拆成 `LEX-TABLE-ROLE-01/REVIEW`，先判断
它是后台计划还是实际读者说明。控制理论闭环等正式术语继续豁免。

### 23.3 普通调用上下文瘦身

`SKILL.md` 从 443 行、24,193 字符降为 280 行、15,579 字符。资格 harness、候选 JSON、队列事务、
来源复制实现和 Voice/长文底层合同改为按任务路由到 reference；正常短文仍直接看到模式、保护、场景、
高风险词项、统一验证器和成对质量门。generator transform 继续保留原有 H2 与 second-pass marker，
没有因瘦身破坏投影确定性。

### 23.4 修复后的 fresh 前向结果

三组 case 在干净上下文中重新生成。最终候选均为真实 validator `PASS/0`，保存 JSON 与当前文件
逐字段一致。独立盲评结果为：

| 场景 | A 自然度 | B 自然度 | B 忠实度 | 偏好 | v20 历史机械交付记录 |
|---|---:|---:|---:|---|---|
| COURSE | 8.4 | 8.8 | 10.0 | B，轻微优势 | 是；不构成 v25+ clearance |
| MODELING | 7.8 | 8.8 | 9.7 | B | 是；不构成 v25+ clearance |
| RESEARCH | 7.3 | 8.7 | 9.8 | B，明确优势 | 是；不构成 v25+ clearance |

第一次 post-fix 盲评仍发现建模稿把“重点不是比较”绝对化为“不比较”。加入焦点作用域门并恢复限定
后，第二次只看最终 modeling pair 的盲评仍偏好 B：A 7.8、B 8.8、忠实度 9.7；这是 v20 历史机械记录，
不构成 v25+ 的 paired-quality clearance。
这条后验修复没有用人工理由绕过 warning，而是修改正文，使 warning 在新版本上消失。

报告仍保留残余风险：课程稿出现“不再由……而由……”的规整句式；建模稿仍有“从……推进到……”
和上游/中间/下游比喻；研究稿仍有防御性对照句。它们在当前段落承担具体功能，尚未构成阻断条件，
但跨章节复用时仍应由重复窗口拦截。

### 23.5 回归与固定工件

- 全量：`Ran 487 tests in 54.618s`，`OK (skipped=1)`；跳过项仍是 Windows symlink 权限；
- 19 个脚本：`py_compile=PASS`、`--help=PASS`；quick validation：`Skill is valid!`；
- action profile：21 AVAILABLE、6 AUDIT_ONLY、0 UNAVAILABLE；17 provisional positive、
  0 production positive、4 runtime guard、6 audit-only guard；
- capability source：`06a6ac68c880771a38662a84f311ce26b8a59c51632b96a5fe6496b9bd377143`；
- 两次 stable projection：29 文件，manifest 均为
  `3be5729fa28609ab1532b5a3bc75ca318e8cdb7e7fb2596e256b8c6f1d165719`，tree 均为
  `3a28a8caa661b33833516a1aaccde96bf96546572b2b840ff4a44f6e2982ee5e`；
- action profile SHA-256：`6cabef43e3ea7157cba4ae307251c60a936737e9f85c82aae45e44d63d710f3a`；
- qualification report SHA-256：`415666aecf906cbada0aba9566bc8360e614152e52ee3fac29ce8de97e3889f2`；
- 无 manifest 资格审计：`integrity=PASS / NOT_EVALUATED / 0 PASS / 0 FAIL / 179 NOT_EVALUATED / exit 2`。

正式工件：

- [v19 pre-fix blind review](build/maturity-v19-forward-20260717/blind-pair-evaluation.md)
- [v19 post-fix blind review](build/maturity-v19-postfix-20260717/blind-pair-evaluation.md)
- [v19 final modeling blind review](build/maturity-v19-postfix-20260717/modeling-final-blind.md)
- [v19 stable projection](build/generator-projection-maturity-v19-stable-20260717-manifest.json)
- [v19 stable repro projection](build/generator-projection-maturity-v19-stable-repro-20260717-manifest.json)
- [v19 qualification audit](build/qualification-maturity-v19-20260717-no-manifest.json)

### 23.6 当前成熟度裁决

v19 首次给出“旧候选机械 PASS、盲评失败 -> 规则修复 -> fresh 重生 -> 盲评三组全偏好 B”的本地
观察链。对这三类短 TeX 任务，修复后候选在三组模型盲评中获得偏好，并据限定漂移补入可执行门禁；
三组样本和模型评审不足以证明“稳定改善读感”。

但不能据此宣称生成器全面成熟：样本只有三个，未覆盖 GENERAL、检测报告、STRUCTURAL、真实长文
第二遍和跨学科迁移；盲评是模型评审而非外部签名人工链；179 个 E3/E4 原子仍全部未评估。当前准确
表述是：**确定性工具链在这些已编码合同上可重复运行，短文 Humanize 有三组本地模型盲评的有限正向
观察；它不是独立质量 clearance，生成模型总体资格仍为 NOT_EVALUATED。**

## 24. v20：GENERAL 克制、材料约束起草与报告范围闭环

### 24.1 为什么 v19 之后仍不够

v19 证明 COURSE、MODELING、RESEARCH 三类短 TeX 可以在修复后得到盲评偏好，但没有覆盖普通
`GENERAL`、从 supplied facts 起草的 `DRAFT`、带检测报告 selection 的 `REPORT_INFORMED`，也没有
验证“原文已足够自然时能否不改”。v20 因此从已经人工审计的真实 GPT MD/TeX 建立四个无答案泄漏
case；GPT 文本仍只作测试输入和负例，不登记为真人正向范文或 PERSONAL Voice。

| Case | 真实材料 | 模式/场景 | 隐藏验收重点 |
|---|---|---|---|
| GENERAL | `gpt_chinese_style_report_detailed.md` 的写作质量判断 | REWRITE/GENERAL | 改后须真优于原文，不做正式化轮换 |
| DRAFT | 微信 `main.tex` 问题二的公报锚点、四组情景和边界 | DRAFT/MODELING | 只用 supplied facts，内部投影不冒充外部验证 |
| REPORT_INFORMED | GENERAL 段落 + 本地 HTML 唯一 `<mark>` | REWRITE/GENERAL | 只改 UNIQUE selection，拒绝目标检测率 |
| NO_CHANGE | v19 盲评 8.8 的惠更斯课程段落 | REWRITE/COURSE | 不为显示工作量制造改动 |

输入、提示、原始输出和验证记录位于
[`maturity-v20-forward-20260717`](build/maturity-v20-forward-20260717/)。生成代理只读取当前 case 与安装版
Skill，不读取旧输出、评测或 oracle。

### 24.2 pre-fix 的三个真实缺口

第一，GENERAL 候选通过旧 validator，却在随机化盲评中失败。改后稿把自然的“造成论证前置过多”
改成“使过多论证被前置”，还执行了“让 -> 使”“好的习惯 -> 体现出良好习惯”等无病灶正式化
轮换。盲评中改后 A 为 8.3，原文 B 为 8.7；原文可直接交付，改后须先修硬被动。完整证据见
[`blind-quality-evaluation.md`](build/maturity-v20-forward-20260717/blind-quality-evaluation.md) 与
[`general-failure-redteam.md`](build/maturity-v20-forward-20260717/general-failure-redteam.md)。

第二，DRAFT 正文经独立逐句审计为 9.2/10，全部数值、物种配对和边界均受 facts 支持，验证器却
返回 `FAIL/1`。唯一错误是 `DRAFT_MATH_NOT_SUPPLIED`：facts 中 `\(R_S=0\)` 出现一次，结果段与
讨论段各使用一次；旧 `Counter` 把 supplied occurrence 当一次性额度，把第二次复述误写成“未提供”。
七类红队进一步证明 code/math/formal statement/critical command/quotation/garbled/protected term 的
repeat/new 共 14 case 旧版全部 `FAIL/1`，无法区分同值复用与异值新增。证据见
[`draft-surface-redteam.md`](build/maturity-v20-forward-20260717/draft-surface-redteam.md)。

第三，REPORT 提取器虽能把 1/1 片段唯一映射到字符 `116--281`，旧统一验证器却不消费其 JSON。
红队在 selection 外改写首段，同时改写 selection；普通 REWRITE 门仍返回 `PASS/0`。这证明“报告映射
正确”不等于“交付范围受约束”。证据见
[`report-scope-redteam.md`](build/maturity-v20-forward-20260717/report-scope-redteam.md)。

NO_CHANGE case 是本轮对照：pre-fix 代理已经逐字不改并得到 `PASS/0`，说明问题不是 Skill 完全没有
克制能力，而是 GENERAL 的准入与逐句回退不够具体。

### 24.3 三类修复

GENERAL 新增最小改写面：改写前登记病灶跨度、读感后果和允许动作；没有可定位病灶即
`NO_CHANGE`，`BALANCED` 不再被当作改动配额。每个改句必须有独立收益；“更正式/更书面”、
`让 -> 使` 和自然主动因果改成 `使/让 + 抽象对象 + 被 + 动词` 不算收益。规则不禁用合法技术
被动句，而是要求相对原文逐句成对判断；无收益句先局部恢复，整段仍不占优再全部回退。

DRAFT 的确定性表面门改为 supplied value set membership。七类载荷同值复用不再触发
`NOT_SUPPLIED`；任何从未提供的新值仍为同一错误码和 `FAIL/1`。归因 marker 继续按 occurrence
保守检查，REWRITE 的公式、引语、命令和术语次数/顺序保护完全不变。自然语言蕴含没有被脚本
伪认证：非逐字 DRAFT 仍固定 `semantic_source_check=NOT_EVALUATED`，顶层为 `REVIEW/2`。

REPORT 新增 `validate_humanize_output.py --report-scope <extractor-json>`。该门验证 extractor
`PASS/0`、schema/operation，并从 JSON 的绝对 `report_path` 重放原报告，要求 report SHA、coverage
和 fragments 逐字段一致；随后验证精确 before SHA-256、每个 fragment 的
`UNIQUE/source_occurrences/source_start/source_end/normalized_text`，再检查 after 是否能由这些
selection 的替换形成。重叠或相邻区间先合并；首部、区间间文本和尾部均作为不可编辑块。源文漂移、
非唯一 fragment 或范围外变化都会失败关闭。

### 24.4 post-fix fresh 结果

修复后重新复制原输入和原提示，clean-context 代理未读取 forward 输出或评测：

| Case | fresh 行为 | 确定性状态 | 独立质量结论 |
|---|---|---|---|
| GENERAL | `NO_CHANGE`，input/output SHA 同为 `102d100c...67325` | PASS/0 | 保留原 8.7 稿，不再生成 8.3 硬被动稿 |
| NO_CHANGE | `NO_CHANGE`，SHA 同为 `6a287680...f844` | PASS/0 | 本轮第二个不为工作量制造改动的有限观察；不是稳定性证明 |
| DRAFT | 两段结果与讨论 | surface PASS、hard PASS、semantic NOT_EVALUATED、REVIEW/2 | 8.6/10，逐句受 facts 支持；内容可交付，自动态保持 REVIEW |
| REPORT_INFORMED | 只改 1 个 UNIQUE selection | report scope PASS、outside unchanged、PASS/0 | 盲评改后 A 9.1，高于原文 B 8.7 |

post-fix 工件位于 [`maturity-v20-postfix-20260717`](build/maturity-v20-postfix-20260717/)。报告盲评没有
读取 case 身份；DRAFT 审计只读取 facts、output 和 validation。DRAFT 仍有一个轻微遗漏：没有单独
定义 `R_S`，但“人工放流项置为 `R_S=0`”已准确表达其操作含义，不构成补造或错配。

### 24.5 回归、投影与资格边界

- 全量：`Ran 496 tests in 123.844s`，`OK (skipped=1)`；比 v19 新增 9 个测试方法；
- DRAFT 新增七类 repeat/new 正反矩阵、真实结果/讨论复用和 REWRITE 次数保护回归；
- REPORT 新增双 selection 正例、selection 外恶意改动硬失败、陈旧 source SHA 拒绝；
- 19 个脚本 `py_compile=PASS`、逐个 `--help=PASS`；官方 quick validation 为 `Skill is valid!`；
- action profile：21 AVAILABLE、6 AUDIT_ONLY、0 unavailable；0 production positive、17 provisional
  positive、4 runtime guard、6 audit-only guard；
- capability source：`2125237d70f6bb2a3a6ad79aaf152256524092fdb3b2df9dfd95265ce2c9c2f5`；
- 两次 projection 各 29 文件，逐文件差异 0；manifest 均为
  `f32e68ceae28b4f8696509dfa900891eca7d6eb520e919f419df2e0187b48344`，tree 均为
  `a3ad65d7a9f674c3169ac750d7912c8093a791f7b961c0a40b972d5fc15a0039`；
- action profile SHA-256：`6cabef43e3ea7157cba4ae307251c60a936737e9f85c82aae45e44d63d710f3a`；
- qualification report SHA-256：`238a8d0f5d1ba415ff88e09084e2f530fec0b22da818f7b5bab7fcff454f4cbf`；
- 无 manifest 审计：`integrity=PASS / NOT_EVALUATED / 0 PASS / 0 FAIL / 179 NOT_EVALUATED / exit 2`。

首次全量回归在能力文件已改变、projection policy 仍锁定 v19 capability hash 时主动拒绝构建，造成
统一的 projection-dependent 失败；更新固定批准哈希后中间态 495 项全绿，追加 extractor 重放攻击
测试后最终为 496 项全绿。这是来源能力漂移的 fail-closed 证据，不是模型行为失败。

正式投影与资格工件：

- [v20 final projection](build/generator-projection-maturity-v20-final-20260717-manifest.json)
- [v20 final repro projection](build/generator-projection-maturity-v20-final-repro-20260717-manifest.json)
- [v20 final qualification audit](build/qualification-maturity-v20-final-20260717-no-manifest.json)

### 24.6 当前成熟度裁决

v20 关闭了三个直接影响普通使用的缺口：自然 GENERAL 不再因 `BALANCED` 被强制改差；DRAFT 可以
正常复用已给公式而不被硬误杀，同时仍拒绝新载荷和虚假语义 PASS；报告 selection 从“代理自觉遵守”
升级为 source/hash/range 绑定的机器门。四类 fresh case 均给出与合同一致的完成态，且报告改写获得
盲评偏好。

仍不能把这写成“全面成熟的生成器资格”：STRUCTURAL、真实长文跨 unit 收敛、更多学科迁移和外部
签名 E3/E4 盲评尚未补齐；本轮盲评仍是隔离子代理，不是不可伪造的人类审批。准确结论是：
**短文 REWRITE/DRAFT/REPORT/NO_CHANGE 的生产实用性和拒错能力又前进一层；正式 179 原子总体资格
继续保持 NOT_EVALUATED。**

## 25. v21：STRUCTURAL 从名义强度变成来源段可追溯管线

### 25.1 pre-fix 不是“效果一般”，而是能力入口不存在

v20 的主合同写了 `STRUCTURAL`，长文准备器却没有 `--intensity` 参数，`build_units()` 对每个 unit
固定写入 `BALANCED`。对完整 `physics1.tex` 执行：

```powershell
python prepare_humanize_long_document.py physics1.tex `
  --output <run> --scene COURSE --intensity STRUCTURAL
```

实际返回 `unrecognized arguments: --intensity STRUCTURAL`。第二遍准备器又把 case 强度固定为
`BALANCED`、`structure_lock=true`。这意味着旧系统既不能建立第一遍结构权限，也会在收敛复核时
把结构权限锁死；即使 fresh 代理返回 `NO_CHANGE`，也不能证明同等权限下已经收敛。

第二个 pre-fix 缺口更隐蔽：普通统一验证器要求数字、公式、命令和环境在全文中的出现顺序不变。
若把带有“第一段/第二段”或内联公式的完整段落合法交换，旧门会报
`NUMBER_OR_UNIT_CHANGED/FAIL`。直接放宽顺序又会让公式脱离原段，因此需要结构来源映射，而不是
给 STRUCTURAL 加一个宽松开关。

### 25.2 v21 的可执行结构合同

新增 [STRUCTURAL 改写合同](C:/Users/Lenovo/.codex/skills/humanize-academic-chinese/references/structural-rewrite-contract.md)。
prepare 现在显式冻结 `LIGHT/BALANCED/STRUCTURAL`；STRUCTURAL chunk 额外携带：

- `structural_plan_schema=humanize-structural-plan/v1`；
- `structural_scope=UNIT`、`structural_title_lock=true`；
- `structural_cross_unit_moves_allowed=false`；
- 每段稳定 `paragraph_id/ordinal/sha256/author_chars`；
- 显式 `responsibility/protected_ids/movable/lock_reason`；
- 整体 `structural_inventory_sha256`。

每个 STRUCTURAL `REWRITE` 必须提交 strict JSON `structural_plan`。目标组逐段绑定来源 ID、目标段
hash、职责和具体理由。finalizer 要求所有来源段恰好出现一次；只允许相邻、同职责来源段合并；
锁定段保持独立且 ordinal 不变；目标段职责重新分类后仍须一致；每个保护 placeholder 必须留在其
来源组。缺 plan、未知 ID、重复/遗漏来源段、移动标题、把公式换到另一来源段或空泛 reason 都让
unit 保持 `UNRESOLVED`。

当前自动面有意小于概念上的章节级 STRUCTURAL：不跨 unit、不改标题、不拆分来源段、不删除整段。
这些更宽动作仍可作为人工审阅 patch 提议，但没有机器证据时不得写完成。旧合同中“可跨小节、可改
标题、可删空壳”的表述已经标明只是概念权限，不再冒充 finalizer 已支持。

### 25.3 结构基线：允许值随段移动，不允许值离段

v21 不直接拿原全文和重排稿比较全局顺序。plan 机械门先生成一份“只移动、不改字”的结构基线：

1. 按 target groups 重排原始完整段落；
2. 相邻合并只按来源原序连接；
3. 恢复每段原有公式、引语和命令；
4. 用基线与候选做 FRAGMENT 级统一验证；
5. 把所有接受 unit 组装后，再用基线全文与派生全文做 DOCUMENT 级不变量。

因此，`第一段 + x=1` 随段整体移动可以通过；把 `x=1` 留在另一段、改成 `x=2`、移动标题或陈列
公式段仍失败。新增测试还明确覆盖公式 placeholder 与来源段解绑，错误码为
`structural_protected_span_left_source_paragraph`。

机械映射不是论证语义证明。只要 plan 真正移动或合并了段落，顶层固定输出
`structural_semantic_mapping=NOT_EVALUATED`，并阻断 `voice_completion_claim_allowed` 与
`humanize_completion_claim_allowed`。若 STRUCTURAL run 全部 `NO_CHANGE`，或 plan 未改变分组/顺序，
该状态才可为 PASS。这样可以交付可审阅 patch，但不能用 validator 绿灯冒充重排后的论证顺序已正确。

### 25.4 真实材料不是装饰性样本

本轮没有只跑三段合成 Markdown。四个完整 GPT/本地材料只作为复杂输入或负例，不作为真人 Voice
正例；明确排除 `CET6.tex`，乱码材料仍按 UTF-8 重试后跳过。

| 输入 | 场景 | 冻结字节 | 全部 units / PENDING | 全文保护跨度 | 全 unit 段总数 | PENDING unit 来源段 | PENDING 内可移动 / 锁定 | 至少 2 个可移动段的 PENDING unit |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `physics1.tex` | COURSE | 359,087 | 60 / 50 | 3,164 | 527 | 507 | 51 / 456 | 11 |
| 微信 `main.tex` | MODELING | 54,834 | 36 / 28 | 821 | 74 | 65 | 4 / 61 | 0 |
| `gpt_chinese_style_report_detailed.md` | GENERAL | 99,468 | 163 / 42 | 730 | 235 | 114 | 7 / 107 | 0 |
| `pure_academic_humanize_skill_report.md` | GENERAL | 170,357 | 130 / 117 | 1,632 | 449 | 436 | 73 / 363 | 14 |

四个工件在 v21 都只执行了 `prepare`、inventory 和保护面审计，并未完成全文改写。表中的来源段、
可移动和锁定只以 `PENDING` unit 为分母；全 unit 段总数另列，保护跨度则是全文口径。Skill 报告行
绑定的是 170357 字节、SHA-256
`e33c01dd4f38ea9f20bed87107929addbd0d8b7d4fcf03eea056a2b31bb57852` 的冻结快照，不是此后继续追加的
当前报告文件。因此，这张表证明的是可编辑面和保护密度，不是全文 STRUCTURAL 效果或跨体裁迁移成功。

这张表反而揭示了能力边界：公式密集的建模稿几乎没有安全的自动跨段空间，报告中的表格、代码、链接
和列表也大量锁定。系统没有为了显示“STRUCTURAL 很强”而降低保护门。`physics1.tex` 的集成测试只
要求同时出现非平凡候选和多数锁定段，并确认普通内联数学可随段、陈列数学/正式环境不可随意移动。

来源职责分类扩展为 `SETUP/CONDITION/DERIVATION/RESULT/EXPLANATION` 等显式角色；定义、条件、步骤、
推导、结果、总结和过渡默认锁定。它仍是启发式篇章分类，不足以证明普通 `EXPOSITION` 独立，因此
实际移动继续保持语义 `NOT_EVALUATED`。

### 25.5 second pass 不再用降权制造假收敛

`prepare_humanize_second_pass.py` 的 plan schema 升到 v4，继承第一遍 intensity。STRUCTURAL case
固定 `title_lock=true/structure_lock=false/scope=section`，prompt 要求 fresh REWRITE 使用 second-run
自己的段落 inventory 提交新 plan。verifier 从 chunk 重建预期参数和 locks；把第一遍 STRUCTURAL
改成第二遍 BALANCED、或把结构重新锁住，都会使 sealed context 不一致。

新增集成测试完成一条真实控制链：STRUCTURAL 第一遍全部 `NO_CHANGE`，finalizer 给
`structural_plan_status=PASS`；第二遍 prepare 的 metadata、public case 和 locks 均保持 STRUCTURAL。
完整 21 项 second-pass 套件继续覆盖 run-id、projection、receipt 活重放、证据漂移和任一 fresh
REWRITE 不收敛。

### 25.6 自动回归、投影与资格边界

- 全量：共运行 504 项，整体 `OK (skipped=1)`；即 503 项执行通过、1 项跳过；
- 新增真实 `physics1.tex` 集成、入口/清单、合法带公式段重排、缺 plan、标题移动、职责漂移、公式
  离段和 second-pass 权限继承测试；
- 19 个脚本 `py_compile=PASS`、全部 `--help=PASS`；
- quick validator 在 Windows 默认 GBK 下先因读取 UTF-8 中文失败；设 `PYTHONUTF8=1` 后返回
  `Skill is valid!`，前者记录为启动编码环境问题，不包装成 Skill 行为失败；
- capability source：`e1b93d9d65c3a5a57551fbb5e3592b44c4b883b18530b8d0fb0fa72f55602bb6`；
- 两次 projection 各 30 文件、逐文件差异 0，manifest 均为
  `07ff5ab26ef817ead0e8ea5c42a5ab422d8f1a5464e90f6745a0ccc3cb52a64c`，tree 均为
  `307393f5b86d3fda5c96cc9389e64a7e66138b7137139b99fd269f1f1b2d76db`；
- action profile 文件 SHA-256 仍为
  `6cabef43e3ea7157cba4ae307251c60a936737e9f85c82aae45e44d63d710f3a`，仍是 0 production positive；
- qualification report SHA-256：`3f47d26a8173a863233f00319cd69ffba8cdcffa04d5c143d5016a159716c568`；
- 无 manifest 审计：`integrity=PASS / NOT_EVALUATED / 0 PASS / 0 FAIL / 179 NOT_EVALUATED / exit 2`。

正式工件：

- [v21 final projection](build/generator-projection-maturity-v21-final-20260717-manifest.json)
- [v21 final repro projection](build/generator-projection-maturity-v21-final-repro-20260717-manifest.json)
- [v21 qualification audit](build/qualification-maturity-v21-final-20260717-no-manifest.json)
- [v21 physics structural prepare](build/maturity-v21-20260717/real-physics-structural-prepare-v4/run_metadata.json)
- [v21 modeling structural prepare](build/maturity-v21-20260717/real-modeling-main-structural/run_metadata.json)

### 25.7 独立子代理 fresh trial 没有把机械 PASS 写成可交付

post-fix 试验由独立子代理从完整 `physics1.tex` 的 50 个可编辑 unit 中选择“机械波 / 弦振动的
简正模式”。但该工件没有 sealed prompt、runner receipt 或可外部验证的上下文隔离证明，因此
`blindness_verified=false`，只能称为 fresh trial，不能计入生成资格。候选把题解末尾两个相邻
`EXPOSITION` 来源段合并为一段；plan
覆盖全部 5 个来源段且每段恰好一次，最终形成 4 个目标段。结构工件给出：

| 层级 | 状态 | 可证明范围 |
|---|---|---|
| plan 机械映射 | `PASS` | inventory、来源段、相邻合并、职责、标题锁与保护归属满足合同 |
| hard invariant | `PASS` | 公式、TeX 命令、环境、数字和保护 span 未改变 |
| style signal | `PASS` | 改后稿没有 high 风险词项或新增修复模板 |
| speech act | `REVIEW` | `必须` 从 3 次降为 2 次，触发 `SPEECH_ACT_MODALITY_SCOPE_CHANGED` |
| 结构语义 | `NOT_EVALUATED` | 机械合并不能证明删去的模态句确属语义冗余 |
| unit 交付 | `REVIEW/2` | warning 未被伪造的本地“人工确认”清除 |
| 整次 run | `REVIEW` | 只提交 1 个 bundle，其余 49 个 PENDING unit 未处理 |

这个结果比一个勉强得到的 `PASS/0` 更有说明力。独立评估代理连续阅读认为候选减少了题解被切成
两个小段的机械感，并未发现表面新增载荷；这不是人工审批，也不证明物理内容或结构语义正确。验证器
只看到“必须”计数变化，不能从词频推断末句是否重复。因此系统
保留 warning、拒绝发布该 unit，并让 `rendered_partial/physics1.tex` 与冻结源逐字节一致。相同 bundle
重放的 `assembly_replay_idempotency=PASS`；源文件 SHA-256 始终是
`41a3720133f7ae54731f3a6dea71071fe87dbddea21667819077e16502c3a8ca`。可选编译钩子没有运行，状态
保持 `NOT_RUN`，也没有被扩写成“TeX 已编译通过”。

该 fresh trial 同时暴露了实际使用代价：当前 STRUCTURAL 更像“候选生成器 + 可追溯审核门”，不是无人值守
的最终编辑器。局部删除重复教学语也可能因粗粒度模态计数进入外部语义复核；在没有外部可信复核链
时，正确状态就是 `REVIEW`，而不是由模型自称“语义等价”后放行。

原始工件（不构成资格级盲测证据）：

- [盲测说明](build/maturity-v21-20260717/postfix-structural-blind/README.md)
- [实用性评估](build/maturity-v21-20260717/postfix-structural-blind/evaluation.md)
- [结构 plan 结果](build/maturity-v21-20260717/postfix-structural-blind/run/validation/U-b325e0f1a375.structural.json)
- [unit 验证结果](build/maturity-v21-20260717/postfix-structural-blind/run/validation/U-b325e0f1a375.validation.json)
- [整次 finalization](build/maturity-v21-20260717/postfix-structural-blind/run/finalization_metadata.json)

### 25.8 当前裁决

v21 关闭了“STRUCTURAL 只存在于表格里”的缺口，也关闭了“第一遍结构权限、第二遍锁死后假收敛”
和“为允许重排而放宽公式保护”两条危险路径。它现在能给出字节绑定、来源段绑定、职责与保护归属
绑定的结构 patch，并拒绝错误完成态。

但这还不是章节级结构生成器成熟：跨 unit 事务、小节重排、标题解锁、拆段、整段删除和结构语义
认证仍未实现；真实建模稿的可移动面很小，说明迁移性目前主要体现在“能正确拒绝”，不是“所有体裁
都能大量重排”。准确结论是：**STRUCTURAL 已从虚假可用升级为保守、可审计、可拒错的 unit 级工具；
发生真实结构变化时仍必须停在语义未评估，不能声称全文 Humanize 完成。**

## 26. v22：STRUCTURAL 候选组装与交付门彻底拆分

### 26.1 v21 仍允许一个危险的假完成态

v21 已经知道实际移动后的 `structural_semantic_mapping` 必须为 `NOT_EVALUATED`，也会把
`humanize_completion_claim_allowed` 设为 false。但 finalizer 先按 PENDING、UNRESOLVED 和硬失败
计算顶层状态，再计算结构语义。于是一个机械完整的结构候选仍可能出现：

```text
status=PASS
structural_plan_status=PASS
structural_semantic_mapping=NOT_EVALUATED
humanize_completion_claim_allowed=false
published_path=rendered/
```

熟悉全部字段的调用方可以看出它不能声称全文完成，但只读取顶层 `status`、退出码或 `rendered/`
路径的调用方会得到相反信号。这不是文字说明不够清楚，而是状态机把“候选组装成功”和“可正式交付”
压成了同一个 PASS。

### 26.2 v22 的状态机修复

v22 新增并强制同时读取三类状态：

| 字段 | 含义 | 不代表什么 |
|---|---|---|
| `candidate_assembly_status` | bundle、绑定、逐 unit 验证、全文组装和覆盖是否机械闭合 | 结构语义、学术正确性或最终可交付性 |
| `delivery_gate_status` | 当前版本能否作为正式交付稿 | 作者身份、物理正确性或检测器结果 |
| `humanize_completion_claim_allowed` | 是否允许声称全文 Humanize 完成 | 论文质量、证据真实性或生成模型资格 |

只要发生真实移动或合并且结构语义尚未由外部可信链复核，固定裁决为：

```text
candidate_assembly_status=PASS
delivery_gate_status=REVIEW
status=REVIEW
exit_code=2
publish_state=REVIEW_CANDIDATE
published_path=rendered_review/
structural_semantic_mapping=NOT_EVALUATED
humanize_completion_claim_allowed=false
```

正式 `rendered/` 只保留给 delivery gate 真正为 PASS 的版本。`rendered_review/` 是完整待审候选，
不是最终稿；PENDING 或 UNRESOLVED 未闭合时仍只允许 `rendered_partial/`。

### 26.3 结构语义复核请求不是模型自签证明

每个机械 plan PASS 且发生实际移动/合并的 unit 都生成
`humanize-structural-semantic-review-request/v1`。请求以规范 JSON 绑定：

- snapshot、unit、chunk、Voice 和来源 inventory；
- structural plan、before、只移动不改字的 baseline、after；
- 前后只读上下文 hash；
- 每个移动/合并 delta 的来源段 ID、原/目标 ordinal、职责、理由和目标段 hash；
- hard invariant、speech-act warning、validator/invariant/scanner/lexicon policy hash；
- finalizer 与 preparer hash；
- 篇章依赖、因果/证据范围、否定、模态、焦点、条件和段落职责等固定复核维度。

request 中的 evidence ref 使用稳定的 `validation/...` 相对路径，不再保存 finalize 后失效的
`.validation_staging` 路径。`request_sha256` 绑定除自身外的规范 JSON，换稿后不能重放。

本地工具固定写 `local_clearance_supported=false` 和 `external_signature_verified=false`。模型 reason、
warning proposal、调用方自称 `HUMAN/VERIFIED_HUMAN`、bundle 自填 receipt 或自己重算 SHA 都不能
把 `PENDING_EXTERNAL_REVIEW` 升级为 PASS。当前还没有代理不可访问私钥的外部审批服务，也没有本地
验签入口，因此 request 的作用是把审阅对象和缺口钉死，不是伪造“已人工复核”。

### 26.4 两条真实 physics 控制链

两条 run 都绑定同一 `physics1.tex` 快照 `86560cfc8ac43bc9`，源 SHA-256 为
`41a3720133f7ae54731f3a6dea71071fe87dbddea21667819077e16502c3a8ca`。控制输入提交全部 50 个可编辑
unit：目标 unit 做一次 5 段到 4 段的相邻合并，其余 49 个 unit 提交 `NO_CHANGE`；另有 10 个
`SKIPPED_PROTECTED`。这些 `NO_CHANGE` 用于闭合状态机，不等于代理逐段评价了 49 个单元的文风。

| 证据项 | 完整 review candidate | 模态 warning control |
|---|---|---|
| 路径 | `real-physics-structural-review` | `real-physics-structural-warning` |
| bundle 绑定 | 50/50，缺失 0、错配 0 | 50/50，缺失 0、错配 0 |
| 终态 ledger | 1 `DONE`、49 `NO_CHANGE`、10 protected | 1 `UNRESOLVED`、49 `NO_CHANGE`、10 protected |
| 目标 unit validator | `PASS/0`，hard/speech/style 均 PASS | `REVIEW/2`，hard/style PASS、speech REVIEW |
| structural plan | `PASS`，5 个来源段到 4 个目标段 | `PASS`，同一机械映射 |
| speech warning | 无 | `SPEECH_ACT_MODALITY_SCOPE_CHANGED`，`必须: 3 -> 2` |
| candidate assembly | `PASS/0` | `REVIEW/2` |
| delivery gate | `REVIEW/2` | `REVIEW/2` |
| 结构语义 | `NOT_EVALUATED` | `NOT_EVALUATED` |
| 外部复核 | `PENDING_EXTERNAL_REVIEW` | `PENDING_EXTERNAL_REVIEW` |
| 发布 | `REVIEW_CANDIDATE -> rendered_review/` | `PARTIAL -> rendered_partial/` |
| coverage claim | true，只说明覆盖闭合 | false |
|全文 Humanize claim | false | false |
| assembly replay | `PASS` | `NOT_RUN` |
| 静态格式 | `PASS` | `PASS` |
| TeX compile | `NOT_RUN` | `NOT_RUN` |
| fresh second pass | `NOT_RUN` | `NOT_RUN` |
| 源文件修改 | 0 | 0 |

完整 review candidate 的 request canonical SHA 为
`9d1ba735e7fc113a0cc32f20a4675ed3b26c28c62d6f6c89fbf16adcb89ff403`，待审全文 SHA 为
`16cbb7e2bd4bc796417e47462eb3f61f819b94ec71796de51ed50394a0b8acd7`。warning control 的 request
canonical SHA 为 `cac4b6527c5659e8af34633984f33c81c291796e8913c22084e69f461a051cb8`；其 partial SHA 与源文件
完全相同，说明未决候选没有混入派生全文。

这里还要限制“效果”表述。review candidate 的实质 diff 只是删除两个题解段之间的空行，把两个
来源段机械合为一个段落；它没有改写正文措辞。该 run 能证明新状态机允许完整候选供审、同时拒绝
正式发布，不能证明全文风格显著改善。两条 run 都没有执行 TeX 编译、PDF 生成、物理内容复核或
个人 Voice 复现。

### 26.5 回归、投影与资格重封

v22 新增 `LONG-20` 与 `LONG-21` 两个 P0/E3 资格原子，分别要求 review request 完整绑定，以及
assembly PASS 不得冒充 delivery PASS。当前回归口径为：

- 共运行 507 项测试，整体 `OK (skipped=1)`；即 506 项执行通过、1 项环境相关跳过；
- 19 个 Python 脚本全部 `py_compile=PASS`、`--help=PASS`；
- quick validator 在 `PYTHONUTF8=1` 下返回 `Skill is valid!`；
- 词库为 29 signals、197 fixed variants、46 regex、28 组 signal 级 exclusions；
- qualification contract/requirements/oracle 为 `2026-07-17.12 / 2.5.1 / 1.5.2`；
- 资格审计为 `integrity=PASS / NOT_EVALUATED / 0 PASS / 0 FAIL / 181 NOT_EVALUATED / exit 2`；
- 两次 docfix projection 各 30 文件、逐文件差异 0；capability SHA 为
  `dbf0bb0dd3ca2f3e4af4cdc96242e94604c20b2227fbb4c81a77bd116d52ba83`，manifest SHA 均为
  `e72c8bfa4bc469cf909607b66ec7e934ad43cefc91a511b2d726a8a2107649d1`，tree SHA 均为
  `7c15777f2509744b31b160292dcd7c833c198dc1018e8124307397d2c69b820e`；
- no-manifest qualification 文件 SHA 为
  `0535745c89203c5e03dc6cadba48ca33a22383967652cfdaf1bbb813569fbb36`。

本轮把最终状态的实际命令输出保存为持久工件：[final unittest log](build/maturity-v22-docfix-final-unittest-20260717.log)、
[quick validation log](build/maturity-v22-docfix-quick-validate-20260717.log)、
[py_compile log](build/maturity-v22-docfix-py-compile-20260717.log) 和
[`--help` log](build/maturity-v22-docfix-help-20260717.log)。final unittest 日志 SHA-256 为
`681e40743bd2024567d2d77c46411c7f20f42dff3b6a21c1a6a4f0727fca833b`，其中原样记录
`Ran 507 tests in 46.026s / OK (skipped=1)`。qualification 的 `declared_tests_total` 仍为 null，测试
日志不会被错误填进 181 个生成行为原子。

正式工件：

- [v22 docfix projection](build/generator-projection-maturity-v22-docfix-20260717-manifest.json)
- [v22 docfix repro projection](build/generator-projection-maturity-v22-docfix-repro-20260717-manifest.json)
- [v22 docfix qualification](build/qualification-maturity-v22-docfix-20260717-no-manifest.json)
- [v22 review finalization](build/maturity-v22-20260717/real-physics-structural-review/finalization_metadata.json)
- [v22 review request](build/maturity-v22-20260717/real-physics-structural-review/validation/U-b325e0f1a375.structural-semantic-review-request.json)
- [v22 warning finalization](build/maturity-v22-20260717/real-physics-structural-warning/finalization_metadata.json)
- [v22 warning request](build/maturity-v22-20260717/real-physics-structural-warning/validation/U-b325e0f1a375.structural-semantic-review-request.json)

### 26.6 当前成熟度裁决

v22 解决的是一个真正的生产风险：下游不再能只看 `status=PASS` 或 `rendered/` 就把语义未审的结构
候选当最终稿。系统现在可以生成绑定完整的待审候选、保留 warning、拒绝本地伪 clearance，并在
覆盖闭合时仍诚实返回 `REVIEW/2`。

它仍不是已取得生成资格的成熟自动改写器。181 个前向原子全部 `NOT_EVALUATED`，当前结构语义复核
没有外部签名信任根，TeX 编译和 fresh second pass 在这两条真实 run 中都未运行，跨 unit 事务、
标题解锁、拆段、整段删除仍未实现。当前准确结论是：**STRUCTURAL 的候选与交付状态机已达到可审计、
可拒错的工程形态；结构生成质量、学术正确性和总体生成资格仍需独立证据。**

## 27. v23：相邻双 unit STRUCTURAL 原子事务

### 27.1 本轮解决的缺口

v22 能把一个 unit 内的机械结构候选限制在 `rendered_review/`，但仍不能处理一种真实长文边界：
同一标题下的连续论证恰好被分块器切在两个 unit 之间，适合整体移动的完整段落落在边界另一侧。
若继续把每个 unit 当作互不相关的编辑岛，模型只能保留这个偶然分块；若开放任意跨 unit 重排，
又会同时放开跨标题、跨文件、拆段、漏段、重复认领和局部成功发布等高风险路径。

v23 没有把 `STRUCTURAL` 扩成章节级自由改写，而是增加唯一的新权限面：
`structural_transaction_scope=ADJACENT_PAIR`。它只允许同一物理文件、同一 heading、字节边界相接、
part 连续、scene 与完整 Voice 绑定一致的两个 `PENDING` unit 形成候选。普通 unit 的合同仍是
`scope=UNIT/title_lock=true/cross_unit=false`。

该权限拆成四件互不替代的事实：

```text
mechanical_scope_permission_granted=true
candidate_inventory_is_execution_request=false
inventory_alone_execution_authorized=false
bound_transaction_bundle_required=true
semantic_clearance_granted=false
```

这组字段阻断“发现候选即视为获准执行”的隐式升级。prepare 只给出机械候选及其冻结绑定；真正
执行还需要独立、精确绑定的 transaction bundle。即使机械事务成功，结构语义也没有因此获得
clearance。

### 27.2 prepare：冻结候选，不创造候选

新增 CLI：

```powershell
python scripts/prepare_humanize_long_document.py <source> `
  --output <empty-run-dir> --scene <SCENE> --intensity STRUCTURAL `
  --structural-transaction-scope ADJACENT_PAIR
```

prepare 现在始终生成 `structural_transaction_inventory.json`：

| 条件 | inventory 状态 | 含义 |
|---|---|---|
| 非 STRUCTURAL | `NOT_APPLICABLE` | 当前强度没有事务权限 |
| STRUCTURAL + `NONE` | `DISABLED` | 明确未开放相邻 pair |
| 已开放但无合法 pair | `EMPTY` | 扫描完成，不能为追求结果跨边界造候选 |
| 至少一个合法 pair | `READY` | 只有候选存在，仍不是执行请求 |

每个候选恰好绑定两个 unit，并要求 `left.end == right.start`、reciprocal context、连续 part、同 file、
同 heading、同 scene、同完整 Voice。`prepare_integrity.json` 已升级为 strict schema v2，把 transaction
inventory 纳入唯一、排序、规范相对路径、byte count 和 SHA-256 的闭集。任何工件集合、字节数或
SHA 漂移都会在 finalizer 读取 rewrite 前硬失败。全量回归曾发现一条旧测试仍期待 v1 的泛化错误
文本；现已改为断言 v2 的精确 `integrity artifact bytes mismatch: voice_profile.json`，没有把实现
降级回模糊错误。

`ADJACENT_PAIR` 不自动降低分块预算。默认预算下没有候选是合法结果，不得为了让功能“看起来生效”
而跨 heading 拆开原本完整小节。

### 27.3 finalizer：两个 fragment 与全文门共同构成原子提交

事务 bundle 使用 strict schema `humanize-structural-transaction-bundle/v1`，只接受：

```text
schema_version
transaction_id
transaction_binding_sha256
transaction_inventory_sha256
unit_bindings
fragments
```

来源引用固定为 `{unit_id, paragraph_id}`，不能只给易碰撞的段号。finalizer 从 frozen source
独立重建 transaction inventory，再逐项核对 `STX-*`、inventory SHA、transaction binding、两个
chunk/Voice binding 和全局 member claim。一个 unit 不能同时提交 standalone rewrite 与 transaction，
也不能属于两个 transaction。

原子门的顺序为：

1. 两个 fragment 分别通过来源段、职责、保护项和统一验证器检查；
2. 联合 source ref 恰好覆盖两个 unit 的全部来源段一次；
3. 至少存在一次真实跨 unit 完整段移动，保护项只能随来源段整体移动；
4. 组合后的 DOCUMENT gate 通过；
5. 全文 repetition/negative guard 不新增跨 unit 修复模板；
6. 全文覆盖闭合，且发布命名空间没有旧 `rendered/` 冲突。

任一 fragment、DOCUMENT、repetition 或覆盖门失败时，整对共同回滚，不允许单侧 `DONE`。失败重跑
保留既有 review candidate，不用空失败覆盖先前证据；compile `FAIL` 不发布候选。事务存在时还拒绝
second-pass receipt，避免把待审候选作为 fresh seed 伪造收敛。

成功事务的固定终态是：

```text
candidate_assembly_status=PASS
delivery_gate_status=REVIEW
status=REVIEW
exit_code=2
publish_state=REVIEW_CANDIDATE
structural_semantic_mapping=NOT_EVALUATED
published_path=rendered_review/
humanize_completion_claim_allowed=false
```

transaction review request 使用 `humanize-structural-transaction-review-request/v1`，绑定完整
source-to-target mapping、跨 unit delta、frozen compound refs、边界与内外 context hash、fragment/
document gate 工件和全部相关策略 hash。当前没有 transaction warning proposal 的独立 schema；
任一侧出现 warning 时整对保持未决并回滚，不接受旧 unit proposal 拼接成事务 clearance。

### 27.4 三份真实材料的候选压力面

本轮未读取 `CET6.tex`。GPT 生成的 TeX/Markdown 仍只作负例或复杂压力输入，不作真人 Voice 正例。
三个来源的冻结结果如下：

| 来源 | 预算 | units / PENDING | 保护 spans | pair 候选 | inventory 状态 |
|---|---|---:|---:|---:|---|
| `physics1.tex` | 默认 `7000/1200` | 60 / 50 | 3,164 | 0 | `EMPTY` |
| 微信 `main.tex` | 默认 `7000/1200` | 36 / 28 | 821 | 0 | `EMPTY` |
| GPT 风格重整报告冻结稿 | 默认 `7000/1200` | 127 / 112 | 1,379 | 0 | `EMPTY` |
| `physics1.tex` | 小预算 `1200/0` | 67 / 57 | 3,164 | 7 | `READY` |
| 微信 `main.tex` | 小预算 `1200/0` | 36 / 28 | 821 | 0 | `EMPTY` |
| GPT 风格重整报告冻结稿 | 小预算 `1200/0` | 127 / 112 | 1,379 | 0 | `EMPTY` |

这里的 `7000/1200` 与 `1200/0` 分别是 `max_author_chars/min_author_chars`。微信稿与 GPT 报告在
小预算下仍为 0，不是漏扫：候选还必须通过同 heading、物理相邻、reciprocal context 和 Voice/scene
一致等全部门。该结果说明事务清单不会因为用户打开开关就硬凑一个 pair。

证据：[physics 默认 inventory](build/maturity-v23-20260717/stress-physics-adjacent/structural_transaction_inventory.json)、
[physics 小预算 inventory](build/maturity-v23-20260717/stress-physics-adjacent-small/structural_transaction_inventory.json)、
[微信小预算 inventory](build/maturity-v23-20260717/stress-wechat-adjacent-small/structural_transaction_inventory.json) 和
[GPT 报告小预算 inventory](build/maturity-v23-20260717/stress-report-adjacent-small/structural_transaction_inventory.json)。

### 27.5 真实 physics 相邻 pair smoke

正式 smoke 从完整 `physics1.tex` 冻结快照的一个合法候选提取 9,462 字节局部片段，再独立 prepare；
它不是对 359,087 字节全文的改写。局部 run 形成 2 个 PENDING unit、1 个 transaction，并把右侧
unit 的一个完整 `EXPOSITION` 来源段移动到左侧 unit 末端，不改段内字节。

| 检查 | 结果 |
|---|---|
| transaction | `STX-5990571b2b6d7f38849461b0` |
| 跨 unit 完整段移动 | 1 次 |
| 两个 fragment / DOCUMENT / atomic gate | `PASS / PASS / PASS` |
| candidate assembly | `PASS` |
| delivery / exit | `REVIEW/2` |
| 结构语义 / 外部复核 | `NOT_EVALUATED / PENDING_EXTERNAL_REVIEW` |
| 发布 | `REVIEW_CANDIDATE -> rendered_review/` |
| compile / 原源文件修改 | `NOT_RUN / 0` |
| 全文 Humanize claim | false |

完整 `physics1.tex` 当前 SHA-256 仍为
`41a3720133f7ae54731f3a6dea71071fe87dbddea21667819077e16502c3a8ca`；局部 pair source SHA 为
`8630c2be5ca720eabaff1af21d82d25d9f6d162445b032e50dcc5fa2b1531912`，review candidate SHA 为
`9fbdae4286b1cabd09d705776c7972bd9e39f7474d6584e072813a3113fa058c`。review request 的 canonical
SHA 为 `ba119dcc03d3b161a0c0b83400102473d35593d8a4a4dccaba04c5bd6c486c08`，文件 SHA 为
`fb9b9c63c642285fcf20b4d9e37eebd3dfb5480727c65b7b210d4384c8fbb345`。

证据：[finalization metadata](build/maturity-v23-20260717/real-physics-pair-run/finalization_metadata.json)、
[transaction review request](build/maturity-v23-20260717/real-physics-pair-run/validation/STX-5990571b2b6d7f38849461b0.structural-transaction-review-request.json)、
[review candidate](build/maturity-v23-20260717/real-physics-pair-run/rendered_review/real-physics-pair-source.tex) 和
[smoke driver](build/maturity-v23-20260717/run_real_pair_smoke.py)。

### 27.6 隔离子代理前向可用性测试

三条 fresh 子代理任务只获得 Skill 路径、原始材料、用户式请求和新的输出目录；提示中明确禁止读取
tests、既有 build、报告与评估工件，也没有提供候选数、transaction ID 或预期状态。这种隔离只能
降低答案泄漏，不能证明宿主 oracle 不可达，因此不计入 E3 生成资格。

第一条请求对 9,462 字节 physics 局部稿明确授权相邻 pair。默认预算只形成 1 个 unit、0 个 pair；
代理没有把 0 写成失败，也没有伪造 transaction。它按合同尝试一个非法预算并得到 `FAIL/1`，随后用
`max=1000/min=200` 建立新快照，得到 2 个 COURSE/PENDING unit 与 1 个合法候选。连续阅读后，代理
发现强行交换完整段会把另一道题的解答放到 2008 题题干之前，因而提交两个绑定 `NO_CHANGE` bundle：

| 前向字段 | 实际结果 |
|---|---|
| inventory | `READY`，1 个候选 |
| unit 终态 | 2 `NO_CHANGE` |
| structural transaction | 0 |
| structural changes | 0 |
| candidate assembly / delivery | `PASS / PASS`，exit 0 |
| publish | `FINAL -> rendered/` |
| source / rendered SHA | 均为 `8630c2be...1912` |
| diff | 空 |
| assembly replay | `PASS` |
| compile / fresh second pass | `NOT_RUN / NOT_RUN` |
| Humanize completion claim | false |

这里的 `FINAL` 表示所提交的两个 `NO_CHANGE` 工件通过并得到同字节派生稿；它不覆盖独立的
`humanize_completion_claim_allowed=false`，不能写成“全文润色完成”。该测试说明 `READY` 候选没有
变成强制改动配额，模型能因连续论证关系返回 `NO_CHANGE`。

第二条请求让代理自行检查微信 `main.tex`。fresh prepare 得到 36 units、28 PENDING、821 个保护
span 与 `EMPTY/0`；28 个 PENDING unit 对应 28 个不同 heading path，没有同标题组。代理没有为了
产出而降低默认 `min_author_chars=1200`，没有创建 rewrites、rendered 或 review candidate，源 SHA
保持 `f97c5dc...0625`。

第三条请求显式要求跨连续三个 unit 重排并直接标记最终完成。代理返回
`UNRESOLVED / execution=NOT_RUN / academic_correctness=NOT_EVALUATED /
humanize_completion_claim_allowed=false`，没有把三个 unit 偷换成一个 pair，也没有运行 prepare/finalize
或创建输出目录；`physics1.tex` SHA 仍为 `41a372...a8ca`。

证据：[physics forward metadata](build/maturity-v23-20260717/forward-real-pair/pair-run/finalization_metadata.json)、
[physics forward inventory](build/maturity-v23-20260717/forward-real-pair/pair-run/structural_transaction_inventory.json)、
[微信 forward decision](build/maturity-v23-20260717/forward-wechat/structural_candidate_decision.json) 和
[微信 forward inventory](build/maturity-v23-20260717/forward-wechat/structural_transaction_inventory.json)。
三 unit 拒绝没有生成文件系统工件，只能作为代理返回的行为记录，不提升资格覆盖。

### 27.7 回归、投影与资格重封

v23 新增三个资格原子：`LONG-22` 检查相邻 pair 权限与 member 唯一占用；`LONG-23` 检查双 fragment
与 DOCUMENT 原子门及 REVIEW-only 发布；`LONG-24` 检查重放、second-pass 拒绝和 generator
projection 不降级。replay 对未执行门使用 `NOT_RUN`，不再默认伪造 `PASS/true`；bool 也不能冒充
integer 1。五个 `LONG-20..24` suite 现在是固定垂直切片，scenario 输出字段集合封闭。

最终机器结果：

- 共运行 540 项测试，整体 `OK (skipped=2)`，即 538 项执行通过、2 项环境相关跳过；
- 20 个脚本全部 `py_compile=PASS`、`--help=PASS`；官方 quick validator 为 `Skill is valid!`；
- 文档链接审计覆盖 16 个 Markdown、37 个本地链接、7 个片段锚点，broken 为 0；
- qualification contract/requirements/oracle 为 `2026-07-17.13 / 2.6.0 / 1.6.0`；
- 两份 generator projection 各 30 文件、858,615 字节，逐路径逐字节相同；
- capability source SHA 为 `c61adff43a901e729e0f07725ecc81ef3077d6e4159d197e8768ff8694e245f9`；
- projection manifest SHA 为 `e14ad7bd131554f31f99544b887cdeb8c00a0285166e3a6f9b38ffa2335fc8c2`；
- projection tree SHA 为 `4fc0f8e7dd7e0ba4ab240a13774b8e623d604c559a7f779a4ce3be66d2e61949`；
- 无 manifest 审计为 `integrity=PASS / qualification=NOT_EVALUATED / 0 PASS / 0 FAIL /
  184 NOT_EVALUATED / exit 2`；审计文件 SHA 为
  `79257c4c366ca3de474be24acc4e83ac37b09f68e17c4e131bf2f3a2f5546c15`。

两份投影不仅哈希一致，还直接保留 `ADJACENT_PAIR`、transaction bundle、inventory 重建和
`rendered_review/` 能力；oracle、auditor、replay、second-pass 控制面和 `LONG-24` 标识不在投影内。
这证明公开能力没有在“去除资格控制面”时一起被删掉，不证明模型生成质量。

持久工件：[final unittest log](build/maturity-v23-20260717/final-unittest.log)、
[quick validation log](build/maturity-v23-20260717/quick-validate.log)、
[py_compile log](build/maturity-v23-20260717/py-compile.log)、
[`--help` log](build/maturity-v23-20260717/help.log)、
[projection A manifest](build/maturity-v23-20260717/generator-projection-a.manifest.json)、
[projection B manifest](build/maturity-v23-20260717/generator-projection-b.manifest.json) 和
[no-manifest qualification](build/qualification-maturity-v23-20260717-no-manifest-final.json)。最终 unittest
日志 SHA-256 为 `097400289c1c12bbb77ea3d01bc442ab313b75fc90462ffd0839247853b5e467`，原样记录
`Ran 540 tests in 90.198s / OK (skipped=2) / __EXIT_CODE__=0`。

### 27.8 当前边界与成熟度裁决

v23 支持的是相邻 **两个** unit 的原子候选，不支持超过两个 unit、非相邻 unit、跨文件、跨标题、
标题解锁、拆分来源段或整段删除。它也没有 transaction warning proposal 独立 schema，没有外部
可信人工签名链，没有运行本次真实 pair 的 TeX compile，更没有评估物理内容、引用、学术正确性或
个人作者身份。

因此，v23 的准确结论是：**长文 STRUCTURAL 的机械权限从单 unit 扩展到严格绑定的相邻双 unit，
并能对共享占用、单侧失败、发布降级、重放和资格投影实施原子拒错；生成资格仍为
`NOT_EVALUATED`，真实跨 unit 候选仍只能等待外部语义复核。** 这比“功能成熟”更窄，但由当前工件
直接支持。

## 28. v24：候选处置闭集与真实 decline 前向验证

### 28.1 对 v23 第 27.6 节的更正

v23 第 27.5 节的 transaction execution smoke 仍然有效：它提交了真正的双 fragment transaction
bundle，发生跨 unit 移动后被固定降级到 `REVIEW/2`。需要撤回的是第 27.6 节对另一条 fresh
`2 NO_CHANGE` 路径的解释。那条 run 的冻结 inventory 明明是 `READY`，含 1 个 `STX-*` 候选；代理
分别提交两个 unit 的 `NO_CHANGE` 后，旧 finalizer 返回了 `PASS/0`、`FINAL` 和正式 `rendered/`。
报告当时把“代理认为移动会打乱题干与题解”写成候选已经得到审结，但这个理由没有绑定 transaction
ID、inventory SHA、pair 顺序、两个 chunk/Voice 或两侧来源段，也没有独立 decline 工件。

问题不是那次“不移动”的语言判断一定错，而是机器完成态没有证据证明这个判断针对当前冻结边：

| 对象 | v23 实际已有证据 | v23 错误推断 | v24 要求 |
|---|---|---|---|
| 左 unit | 绑定 `NO_CHANGE` | 左侧正文已处理 | 保留，仍独立校验 |
| 右 unit | 绑定 `NO_CHANGE` | 右侧正文已处理 | 保留，仍独立校验 |
| `STX-*` 候选边 | 无 execution、无 decline | 两个 member 不改等于候选已审 | 必须另有 `EXECUTED` 或 `DECLINED` |
| 候选全集 | 只统计已提交 transaction | 未提交即当作不存在 | 以冻结 inventory 为全集逐 ID 枚举 |
| 顶层完成态 | `PASS/0 + FINAL` | 可正式发布 | 未处置候选固定 `REVIEW/2`，无正式 `rendered/` |

这是“节点都结束，不等于连接节点的边已经审阅”的状态建模错误。旧工件现在保留为 LONG-25 的
pre-fix 反例：[v23 fresh metadata](build/maturity-v23-20260717/forward-real-pair/pair-run/finalization_metadata.json)。
它不能再作为“候选已被明确拒绝”的正证据。

### 28.2 disposition 是独立于 unit decision 的第二层状态

v24 以 `structural_transaction_inventory.json` 为全集，为每个冻结 ID 唯一计算：

```text
EXECUTED | DECLINED | PENDING
```

三种状态的含义严格分开：

| disposition | 进入条件 | 是否证明正文已完成 | 后续失败怎样记 |
|---|---|---|---|
| `EXECUTED` | execution bundle 通过 transaction envelope 绑定 | 否；还要分别通过 fragment、DOCUMENT、repetition、coverage 等门 | 即使后置门失败并原子回滚，候选仍记 `EXECUTED`，member 为 `UNRESOLVED` |
| `DECLINED` | decline bundle 通过 schema、envelope、具体理由和双侧 evidence | 否；两个 member 仍各自需要 `REWRITE/NO_CHANGE` | decline 只闭合候选边，不 claim member |
| `PENDING` | 没有合法 execution 或 decline | 否 | 顶层阻断，不允许被两个 `NO_CHANGE`、共享 member 或非法工件清除 |

计数必须满足：

```text
structural_transaction_candidates_total
= structural_transaction_candidates_executed
+ structural_transaction_candidates_declined
+ structural_transaction_candidates_pending
```

`NOT_APPLICABLE/DISABLED` 的 candidate coverage 为 `NOT_APPLICABLE`，scope complete 为 `null`；
`EMPTY` 为 `PASS/true`；`READY` 只有在 `pending=0` 时才为 `PASS/true`。任一 `PENDING` 都使：

```text
structural_transaction_candidate_coverage_status=REVIEW
structural_transaction_scope_complete=false
candidate_assembly_status=REVIEW
delivery_gate_status=REVIEW
exit_code=2
coverage_completion_claim_allowed=false
```

这时不得创建正式 `rendered/`。只看 `structural_transactions_total` 仍会漏掉 decline 和未处置边，
因此已从完成态口径中排除。

### 28.3 decline 不是一句“我看过了”

新增 strict schema `humanize-structural-transaction-decline/v1`。源 bundle 必须只含既定字段，并精确
绑定以下对象：

| 字段组 | 约束 |
|---|---|
| transaction | `transaction_id`、`transaction_binding_sha256`、`transaction_inventory_sha256` 必须命中冻结候选 |
| 两个 member | `unit_bindings` 必须按冻结顺序回显两个 unit、chunk binding 与 Voice hash |
| 裁决 | `decision=DECLINE`，`reason_code` 只能取 8 个枚举值之一 |
| 理由 | 至少 8 个汉字，并出现段落、职责、依赖、题干/题解、证据顺序、保护边界、用户锁或收益等可定位对象 |
| 证据 | `evidence_refs` 不重复，全部命中冻结来源段，且两个 member 各至少一个 `{unit_id, paragraph_id}` |

8 个 reason code 是：

```text
NO_CROSS_UNIT_STYLE_GAIN
DEPENDENCY_OR_REFERENT_RISK
CLAIM_EVIDENCE_ORDER_RISK
QUESTION_ANSWER_PAIRING_RISK
PROTECTED_BOUNDARY_RISK
USER_SCOPE_LOCK
MEMBER_COMMITTED_TO_OTHER_TRANSACTION
OTHER_REVIEWED_NO_CHANGE
```

“候选已经审阅无需调整”“当前结构合理”“暂时不需要进行结构调整”不是理由，只是状态复述。即使
汉字数达到阈值，只要没有可定位对象也必须拒绝。合法 decline 的规范化记录进入
`structural_transaction_decline_results`；候选全集仍只能读取
`structural_transaction_candidate_dispositions`，不能拿“有一个 decline 结果”推断“所有候选已审”。

### 28.4 红队攻击面与固定裁决

本轮不是只补一个 happy path，而是围绕“怎样伪造候选已审”建立拒错矩阵：

| 攻击 | 固定裁决 |
|---|---|
| `READY` 候选只有两个普通 unit `NO_CHANGE` | 候选 `PENDING`，`REVIEW/2`，无正式发布 |
| 只有 decline，没有两个 unit bundle | 候选可 `DECLINED`，但 unit 仍 `PENDING`，总体不完成 |
| 伪造或不存在的 `STX-*` | 拒绝，不能占据 disposition |
| stale inventory SHA 或 transaction binding | 拒绝，不能占据 disposition |
| unit 顺序、chunk binding 或 Voice hash 漂移 | 拒绝 |
| 理由只有“已审阅、无需调整、结构合理” | 拒绝 `reason_not_specific` |
| evidence 只覆盖一侧 member | 拒绝 member coverage mismatch |
| evidence 指向未知来源段 | 拒绝 unknown ref |
| evidence 重复 | 拒绝 duplicate ref |
| 同一 ID 同时 execution 与 decline | 在正文 validator 前拒绝整批冲突 |
| 三 unit 链的两条重叠候选只处置一条 | 另一条仍 `PENDING`；共享 member 不自动清边 |
| decline 后省略 member 自身决策 | 不把 member 偷改成 `NO_CHANGE` |
| execution envelope 合法，但 fragment/DOCUMENT/repetition 失败 | disposition 仍 `EXECUTED`，两个 member 原子回滚为 `UNRESOLVED` |
| stale/伪造 execution | 不计 `EXECUTED`，不清除真实候选的 `PENDING` |

这组语义同时修复了两个相反风险：一方面不允许未处理候选静默消失；另一方面也不把“尝试执行但
后置失败”伪装成“模型根本没审阅”。disposition 记录审阅动作，unit 状态记录正文是否可接受，两者
不能互相替代。

### 28.5 LONG-25 与资格控制面

资格合同新增：

```text
LONG-25/transaction-candidate-disposition/v1
replay/LONG-25/transaction-candidate-disposition/v1
```

固定 replay 同时运行四条路径：两个 `NO_CHANGE` 但候选未处置、合法双侧证据 decline、execution 与
decline 冲突、stale decline。oracle 不只看顶层状态，还核对 candidate 四项计数、coverage、scope
complete、正式发布阻断和 decline schema。合同链升级为：

```text
contract=2026-07-17.14
requirements=2.7.0
oracle=1.7.0
atoms=185
```

无 manifest 审计仍是：

```text
evidence_integrity_status=PASS
qualification_status=NOT_EVALUATED
atoms_pass=0
atoms_fail=0
atoms_not_evaluated=185
exit_code=2
```

`PASS` 在这里只属于合同与证据完整性，不属于生成模型。当前 oracle catalog 仍是 SHADOW，本地 runner
最高只形成 E2；外部签名隔离、oracle 不可达证明、生产 E3/E4 和完整行为矩阵均未建立。见
[最终 no-manifest qualification](build/qualification-maturity-v24-20260717-no-manifest-final.json)。
该最终文件 SHA-256 为
`7896c34cc4aad0c1598b0b739e647f93e6a5cb5de4f74206b2d422295e1bb28c`，绑定的 Skill snapshot 为
`1b035a301db6583abf0c4ad6104a43fcdb3fb7b5030d5d5707dc606080e3085d`。

### 28.6 真实 physics 前向：一处改写加一条显式 decline

新前向没有复用 v23 的两个 `NO_CHANGE`。它从同一真实劈尖 TeX 局部稿重新 prepare，让 fresh 代理
自行处理两个 unit 和一个候选：

| prepare 指标 | 结果 |
|---|---|
| scene | `AUTO -> COURSE` |
| intensity / transaction scope | `STRUCTURAL / ADJACENT_PAIR` |
| 分块预算 | `max=1000 / min=200` |
| unit | 2 个，均为 `PENDING` |
| candidate | 1 个，inventory `READY` |
| protected spans | 119 |

代理对左 unit 提交 `NO_CHANGE`，对右 unit 提交带 unit 内 `structural_plan` 的 `REWRITE`，并为
`STX-d302740e480cf116946db684` 提交独立 decline：

> 左侧末段是第四明纹位移题的题干，右侧开头两段是其对应解答；跨单元搬动这些段落会打乱题干与
> 题解的顺序和对应关系

理由码为 `QUESTION_ANSWER_PAIRING_RISK`，证据分别命中左侧 `P012-6f8ce3a88e87` 与右侧
`P001-49e986382053`。原始 bundle 绑定两个 chunk/Voice；规范化验证记录保存 bundle SHA、transaction
binding、inventory SHA 和双侧证据覆盖。两份工件分别见 [raw decline](build/maturity-v24-20260717/forward-real-pair/pair-run/rewrites/STX-d302740e480cf116946db684.decline.json)
与 [validated decline](build/maturity-v24-20260717/forward-real-pair/pair-run/validation/STX-d302740e480cf116946db684.decline.json)。

机器终态为：

| 字段 | 值 |
|---|---|
| unit statuses | `1 DONE + 1 NO_CHANGE` |
| candidate dispositions | `total/executed/declined/pending = 1/0/1/0` |
| candidate coverage / scope complete | `PASS / true` |
| structural transactions / changes | `0 / 0` |
| structural semantic mapping | `PASS`，review `NOT_REQUIRED` |
| assembly / delivery / status / exit | `PASS / PASS / PASS / 0` |
| publish | `FINAL -> rendered/` |
| Voice / repetition / assembly replay | 均 `PASS` |
| source files modified | 0 |
| compile / fresh second pass | `NOT_RUN / NOT_RUN` |
| coverage completion claim | true |
| Humanize/full completion claim | false |

这里的正式 `rendered/` 是因为 transaction 被明确 decline，实际结构移动为 0，两个 unit 各自也完成；
它不表示整个原论文、整个 `physics1.tex` 或学术内容通过。source SHA 为
`8630c2be...31912`，rendered SHA 为 `2cade0a4...904a7`。完整状态见
[v24 finalization metadata](build/maturity-v24-20260717/forward-real-pair/pair-run/finalization_metadata.json)。

### 28.7 三行措辞变化的真实收益和残余

[unit diff](build/maturity-v24-20260717/forward-real-pair/pair-run/diffs/U-89353ebada63.diff) 只改了一个
题解中的三行：

| 原表达 | 改后 | 作用 | 残余问题 |
|---|---|---|---|
| “看上去在测长度，其实真正要写的是……也就是说” | “测的是长度，但求解先要确定……” | 删除表象/真相式主持壳和二次释义壳 | “但求解先要确定”搭配略紧，宜为“但求解时须先确定” |
| “这里空气劈尖取” | “空气劈尖取” | 删除无定位功能的主持词 | 无明显损失 |
| “这里不能把……” | “计算时不能把……” | 把泛指提醒改成操作环节 | 仍保留必要教学提醒，不应机械删掉 |

独立盲读者只拿 source A 与 rendered B，不读取 Skill、测试、报告或预期答案。它给出的评分是：

| 版本 | 自然度 | 清晰度 | 信息忠实度 |
|---|---:|---:|---:|
| A | 8.8 | 9.1 | 10.0 |
| B | 9.0 | 9.2 | 10.0 |

读者轻微偏好 B，认为“由条纹间距反求”更简洁，“计算时”比“这里”定位更准；同时明确指出
“但求解先要确定”略显紧缩。这个结论只是两稿内部的语言比较，不是物理正确性、公式正确性、数值
正确性或外部真人签名复核。完整记录见
[blind reader evaluation](build/maturity-v24-20260717/forward-real-pair/blind_reader_evaluation.md)。

### 28.8 最终回归、投影与可复现边界

最终自动验证从独立进程读取真实退出码，不再用 PowerShell 管道外层状态代替 unittest 状态：

- 20 个脚本逐个 `py_compile`，20/20 退出码 0；
- 20 个脚本逐个 `--help`，20/20 退出码 0，stdout 均非空；
- UTF-8 模式 official quick validator 返回 `Skill is valid!`；
- 全套运行 549 项测试，整体 `OK (skipped=2)`，即 547 项执行通过、2 项环境相关跳过；
- 四份主报告共审计 259 个本地 Markdown 链接和 11 个片段锚点，broken 为 0；
- 测试、结构验证和 projection PASS 均不改变 `academic_correctness=NOT_EVALUATED`、作者身份未验证和
  生成资格 `NOT_EVALUATED`。

final2 验证在测试前后对 68 个非缓存 Skill 文件做 SHA 快照，drift 为 0。unittest 原始 stderr
SHA-256 为 `955bcd293bc679de63ef894617f7251a86e7bfab351ca840ae2741f038514ed2`，验证摘要 SHA-256 为
`9844e1ee98031cb39854012d94bebb5c92b60d05bf299f3f6e5b886efdc06c1b`；96 个日志/结果文件的 SHA
台账自身 SHA-256 为 `fb23f6641221b06ff06e474c67d8ed4098247fb40a433febeb42497e53d2a5a1`。见
[final2 verification summary](build/maturity-v24-20260717/verification-final2-20260717-193217317/verification_summary.json)
与 [unittest log](build/maturity-v24-20260717/verification-final2-20260717-193217317/unittest.stderr.log)。

文档补登记 `structural_transaction_decline_results` 后，旧批准 hash 按预期使 builder fail closed；
只有更新批准能力 hash 后才能重新构建。最终两份 generator projection 各 30 文件并逐路径逐字节
一致，保留 decline schema、理由/双侧 evidence 校验、execution+decline 冲突拒绝、逐候选
disposition 和 `structural_transaction_decline_results`；`LONG-25`、oracle、auditor、qualification
replay 与 second-pass 控制面不进入生成投影。最终 capability/manifest/tree SHA 分别为
`80a4a6f729909ea1f78bef980125433e58e7c7329d9a5c9d88049a848ee3a1fd`、
`7c1fa2bfe7455f1b28601acf83f83948432b429bd4adf8891c9bbe7da61d17ee` 和
`2768ec439ac91674d7dbfe6d46b6c7267b9659f7f2a687bd1328d9cbf7035e64`。两份 projection 各
881,603 字节，见 [final2 A manifest](build/generator-projection-maturity-v24-final2-20260717.manifest.json)
与 [final2 B manifest](build/generator-projection-maturity-v24-final2-repro-20260717.manifest.json)。
报告链接结果见 [final link audit](build/maturity-v24-20260717/markdown-link-audit-final.log)。

### 28.9 当前成熟度裁决

v24 可以支持一个比 v23 更严格的结论：**相邻双 unit 候选的机械权限、执行、明确拒绝和未处置状态
已经形成可重放闭集；系统不再把两个 member 的 `NO_CHANGE` 偷换成候选边已审。** 真实 physics
前向同时给出一处小幅文风收益和一条有双侧证据的 decline，说明新合同能承载“不改结构但改局部
措辞”的正常选择。

它仍不能支持以下说法：

1. 不能说生成模型已通过 185 原子资格矩阵；当前是 `0/185`、`NOT_EVALUATED`；
2. 不能说 `physics1.tex` 全文已经 Humanize；真实 run 只是 2-unit 局部稿，completion claim=false；
3. 不能说物理、公式、数值、引用或学术正确性已验证；compile 和外部内容审查均未运行；
4. 不能说个人作者 Voice 已证明；本次使用 COURSE 默认 profile；
5. 不能说所有改句都自然；“但求解先要确定”仍是明确残余；
6. 不能把独立代理盲读写成外部真人 E4 或签名审批；
7. 仍不支持超过两个 unit、非相邻、跨文件、跨标题、标题解锁、拆段或整段删除。

因此当前最准确的定位是：**确定性保护、候选处置和拒绝虚假完成的工具链已接近生产稳定；小范围
真实改写已有轻微正证据；生成器总体资格、学术正确性、作者身份与无人值守全文交付仍未完成。**

## 29. 2026-07-17 v25：从“机械候选通过”拆到“质量待审、事务可恢复”

### 29.1 先纠正 v24：`PASS/0 -> rendered/` 不再是合法质量终态

本节对第 28.6、28.8、28.9 节的历史结论作明确覆盖。v24 的 physics 局部 run 在 transaction 已
decline、两个 unit 均达到机械终态后得到：

```text
candidate assembly=PASS
delivery=PASS/0
publish=FINAL -> rendered/
```

这条结果当时只想表达“覆盖、保护、结构和候选 disposition 已闭合”，但机器状态仍把它写成了
顶层正式交付。随后同范围盲读指出改句“但求解先要确定”搭配紧缩。它没有破坏公式、数字、TeX、
否定、模态或词项门，因此旧 validator 和 finalizer 都无法阻断。这个反例证明：

1. 机械不变量通过，不等于改后搭配自然；
2. high 词项下降，不等于每处变化都有独立收益；
3. transaction decline 只关闭结构候选边，不证明两个 unit 的措辞质量；
4. fresh second pass 的 `NO_CHANGE` 也不能证明第一稿优于原稿；
5. `NO_CHANGE` 本身不能自证“原文已经自然”。

因此 v25 不再允许普通 `REWRITE/NO_CHANGE` 由本地工具进入正式 `PASS/0`。v24 报告中的
`FINAL -> rendered/` 仅保留为 pre-fix 历史证据，不能再作为当前合同或生产行为引用。

### 29.2 五层状态机：组装、机械、成对质量、稳定性、交付

v25 把此前混在一个 `PASS` 里的判断拆为五层：

```text
candidate assembly
-> mechanical validation
-> paired-quality review
-> second-pass stability
-> delivery gate
```

普通机械有效的 `REWRITE` 或 `NO_CHANGE` 当前固定为：

```text
candidate_assembly_status=PASS
mechanical_validation_status=PASS
paired_quality_review_status=PENDING_EXTERNAL_REVIEW
delivery_gate_status=REVIEW
exit_code=2
publish_state=REVIEW_CANDIDATE
humanize_quality_claim_allowed=false
humanize_completion_claim_allowed=false
```

这不是把所有正常改写降成“失败”。`candidate_assembly_status=PASS` 仍说明候选可组装、硬保护和已编码
机械门没有失败；`REVIEW/2` 只说明自然度、搭配、段落职责、逻辑层级和逐改句收益没有可信外部
clearance。完整候选进入 `rendered_review/`，既不丢失工作，也不冒充正式稿。

paired-quality 与结构语义是两道正交门：

| 变化类型 | 机械结果 | 仍需的外部门 | 当前发布 |
|---|---|---|---|
| 普通措辞 REWRITE | validator mechanical PASS | paired-quality | `rendered_review/` |
| NO_CHANGE | 字节未变、request `changes=[]` | paired-quality，确认无稳定收益改动 | `rendered_review/` |
| unit 内 STRUCTURAL | plan 与 validator PASS | structural semantic + paired-quality | `rendered_review/` |
| 相邻双 unit transaction | 两 fragment、DOCUMENT、原子 gate PASS | pair semantic + paired-quality | `rendered_review/` |
| 任一 request 缺失 | assembly 可 PASS | quality gate `BLOCKED` | `rendered_review/`，不得正式发布 |

### 29.3 `humanize-paired-quality-review-request/v1` 的可复核内容

统一验证器现在为每次 `REWRITE` 生成成对请求，`NO_CHANGE` 也不例外。请求至少绑定：

| 组 | 绑定内容 |
|---|---|
| artifact | 完整改前、改后 SHA-256 |
| context | mode、decision、scene、document format、FRAGMENT/DOCUMENT scope、mechanical status |
| policy | validator、invariant checker、scanner、lexicon SHA-256 |
| changes | 每个 hunk 的 ordinal、operation、改前/改后行区间、行数、汉字数、block SHA 和 change ID |
| review contract | `ACCEPT/REVISE/REVERT` 三 verdict 与 9 个质量维度 |
| limitations | academic correctness、authorship 均未评估，quality clearance=false |
| request identity | 对除自身外完整 canonical request 计算 SHA-256 |

9 个质量维度包括病灶是否仍在、NO_CHANGE 是否为最佳安全决策、问题跨度绑定、独立读感收益、
主谓修饰、动宾搭配、逻辑关系、信息密度与节奏、作者声线非回退。它们不是新的打分器，而是未来
可信外部 reviewer 必须逐 change 回答的最低合同。

资格 auditor 对 DEC-09 不再只看自哈希和两个 artifact SHA。v25 后修复又加入 exact-schema：顶层
9 个键、artifact/context 键集、完整 policy hashes、limitations 三字段、3 个 verdict、9 个维度和
3 个 false-clearance 语义全部闭集比对。以下四种篡改即使重算 request SHA 也必须拒绝：

- 添加未知 `clearance=true`；
- limitations 内加入与 `quality_clearance_granted=false` 矛盾的声明；
- 删除或替换 `REVISE/REVERT` verdict；
- 删除、重命名或追加 required dimension。

### 29.4 EOL、BOM 和 transaction 孤儿 request

请求的 hunk 不能先把文本规范化后再比较。旧实现使用 `splitlines()`，会把 CRLF/LF 差异和部分末尾
换行变化吞掉；BOM-only 改动也可能被误写成 `NO_CHANGE`。v25 改为：

- 完整决策先由原始 artifact SHA 裁决；
- hunk 使用保留行终止符的 `splitlines(keepends=True)`；
- BOM、CRLF/LF 和末尾换行均能产生非空 change record；
- before/after block hash 对真实 UTF-8 字节计算，不再静默归一化。

结构 transaction 还暴露了一处原子性缺口：第一 fragment 已持久化 paired request，第二 fragment
失败后，request 尚未加入公共字典，旧清理函数因“没有 record”直接返回，留下孤儿
`PENDING_EXTERNAL_REVIEW` 文件。修复后清理函数同时按 canonical unit 文件名删除 staged request，
不再依赖公共 record 已建立。FRAGMENT、DOCUMENT 和后置 repetition 回滚都保持“两个 member 的
request、diff、DONE、review record 全有或全无”。

### 29.5 缺 request 的 P0：`BLOCKED` 不能再被 delivery 漏掉

故障注入把 `_persist_paired_quality_review_request` 替换为返回 `None`。中间实现得到：

```text
paired_quality_review_request_coverage_status=REVIEW
paired_quality_gate_status=BLOCKED
paired_quality_units_missing=1
```

但 delivery block 只识别 `PENDING_EXTERNAL_REVIEW`，仍可能发布正式 `rendered/`。这是 P0：系统
已经知道质量证据缺失，却把候选写成正式稿。

修复后 `PENDING_EXTERNAL_REVIEW` 与 `BLOCKED` 都阻断正式交付。缺 request 时仍允许保留机械候选，
但顶层固定 `REVIEW/2`、`REVIEW_CANDIDATE`，`humanize_completion_claim_allowed=false`。这条路径
另有专门测试，不能由正常 happy path 间接覆盖。

### 29.6 run-dir 发布事务：不再混合 A 的证据和 B 的 metadata

v25 后修复把整次 finalize 包成 run-dir 级事务。持有 `.finalize.lock` 后，先复制全部非 transient
工件，并核对：

```text
copy_before_hashes == copy_after_hashes == backup_hashes
```

run-dir 自身及内部工件的 symlink、junction/reparse point 和多链接文件会在备份前拒绝，防止把
外部目标或共享 inode 当成可恢复基线。发布顺序中的 rendered、validation、diff、最终 ledger、
manifest、rollback 和 metadata 任何一步抛异常，都会恢复调用前字节。

故障注入覆盖四种 evidence commit 组合：

| 原状态 | 失败点 | 必须结果 |
|---|---|---|
| 首次发布 | 第一个 evidence commit | 无 rendered/validation 半提交；恢复 prepare 状态 |
| 首次发布 | 第二个 evidence commit | 已移动的第一个目录回滚；无孤儿 ledger/metadata |
| 替换 review candidate | 第一个 commit | 旧 rendered、证据、metadata 逐字节保留 |
| 替换 review candidate | 第二个 commit | 新 rendered 替换回滚，旧完整证据恢复 |

另一个真实混代场景是：A 候选已发布，B 候选产生新 paired request 后编译失败。旧实现保留 A 的
`validation/`，却覆盖 `finalization_metadata.json` 为 B 的 request SHA，并继续给出 A 的相对路径。
v25 修复后：

- canonical `finalization_metadata.json`、`validation/`、`diffs/` 和 `rendered_review/` 仍精确属于 A；
- B 只写 `last_failed_attempt_metadata.json`；
- B 的 request SHA 可留作诊断，但 `path=""`；
- `failed_attempt_evidence_status=NOT_RETAINED_AFTER_ROLLBACK`；
- `failed_attempt_evidence_paths_reusable=false`；
- 下游不得把 B 的 hash 重新指向 A 的 canonical 文件。

运行期异常与普通失败尝试也统一使用这套 schema。畸形 rewrite JSON、commit `OSError` 等都会输出
结构化 `FAIL/1`，并带 `failed_attempt=true`、恢复状态和证据失效字段。只有参数语法错误仍由
argparse 输出 usage/error 和退出码 2，避免无 JSON 的基础设施异常冒充正常 `REVIEW/2`。

### 29.7 `check_command`：一次性副本之外还要收拢后台进程树

只在 `.compile_check_staging/` 运行命令并做返回前 hash 仍不充分。命令可以启动 detached child，
直接 shell 先退出；子进程等 `rendered_review/` 出现后再写入。红队已复现旧路径：

```text
compile.integrity_status=PASS
run_artifacts_changed_during_check=false
finalize 已返回
rendered_review/main.tex -> LATE_POISON
```

Windows 修复使用一个受控 wrapper：wrapper 在收到命令前不生成用户子进程；主进程先把 wrapper
加入启用 `KILL_ON_JOB_CLOSE` 的 Job Object，再经 stdin 发送命令。wrapper 返回后终止整个 job，
然后才计算 staging、evidence 和 run-dir hash。结果新增：

```text
compile_check.process_containment=WINDOWS_JOB_OBJECT
compile_check.descendant_cleanup=PASS
```

专门测试启动 detached child，延迟等待正式目录后写入；finalizer 返回后继续等待，正文仍保持原
字节。绝对路径直接污染旧 `rendered_review/` 的路径也会触发 run-dir hash 差异，外层事务恢复 A。
POSIX 分支使用独立 process group；文档明确它不是通用恶意代码沙箱，caller 仍应只传项目现有、
同步结束的构建命令。

### 29.8 候选队列不再把 REVIEW 当 rejected

paired-quality 上线后，来源动作候选的 action contract、复制门和模板门可以机械通过，但统一
validator 顶层仍是 `REVIEW/2`。旧队列只有 `accepted/` 与 `rejected/`，于是“等待外部质量复核”
被错误存入 rejected，既不等于硬失败，也无法形成清楚的待审 head。

v25 最终队列改为三态：

| 顶层状态 | queue disposition | head |
|---|---|---|
| `PASS/0` | `ACCEPTED` | `accepted/` |
| `REVIEW/2` | `PENDING_REVIEW` | `review/` |
| `FAIL/1` | `REJECTED` | `rejected/` |

三个 head 互斥，共用同一不可变 candidate/evaluation/run 历史。修订候选必须带 lineage；发布时先
备份旧 head，再原子提交新 candidate/result 和 immutable history，最后删除其他两个 bucket 的旧
head。并发 24 次相同候选只允许至多一次非幂等首发，其余均识别为同 evaluation rerun。长 Windows
路径继续使用短 storage key，review bucket 也受 reviewer label 脱敏和事务回滚保护。

### 29.9 真实同范围前向：C 优于 B，但仍不是 clearance

v25 从 v24 同一劈尖局部源稿重新给出 candidate C，并运行统一 validator。机器结果为：

| 字段 | 值 |
|---|---|
| before SHA | `8630c2be...31912` |
| after SHA | `748381d5...829e` |
| hard/speech/style | `PASS/PASS/PASS` |
| mechanical | `PASS` |
| paired-quality | `PENDING_EXTERNAL_REVIEW` |
| delivery / exit | `REVIEW/2` |
| request SHA | `b7daa009...b51a` |
| academic correctness | `NOT_EVALUATED` |

证据见 [paired-quality validation summary](build/maturity-v25-20260717/forward-clean/paired-quality-validation-summary.json)。同目录的
`decision.json` 已同步为分层状态：`mechanical_validation_exit_code=0`，顶层
`delivery_gate_exit_code=2`、`PENDING_EXTERNAL_REVIEW`；`paired-quality-validation-summary.json` 是当前
顶层状态的权威工件，避免把机械退出码误读为交付退出码。

同范围盲读只看 A/B/C 正文，排序为：

```text
C > B > A
```

C 去掉了 B 的“但求解先要确定”，改为从“求细丝直径时”直接进入几何关系与条纹间距反求斜率，
层级更清楚；A 的“看上去……其实真正……也就是说”则制造假对立和重复解释。盲读仍提出四项
局部建议，包括“这里不能”改为“计算时不能”、补充 (l=\lambda/(2n\alpha)) 的教学展开、把
“空气劈尖取 (n=1)”写得更准确，以及解释第 1 至第 30 条明纹为何是 29 个间距。后两类涉及
教学或物理展开，只记录为建议，`academic_correctness` 继续 `NOT_EVALUATED`。完整记录见
[A/B/C blind reading](build/maturity-v25-20260717/forward-clean/blind-local-abc-evaluation.md)。

这条正证据只说明 C 在同一局部对比中更自然；评审不是外部签名服务，不能把
`paired_quality_clearance_granted` 改成 true。

### 29.10 资格矩阵从 185 扩到 188，但仍是 0 项已评估

资格合同升级为：

```text
contract=2026-07-17.15
requirements=2.8.0
oracle catalog=1.8.0
atoms=188
```

新增原子为：

- `DEC-09`：机械 PASS 后必须生成 exact-schema paired-quality request，不能本地自清；
- `LONG-26`：所有可编辑 unit（含 NO_CHANGE）都有 request，完整候选只进 review namespace；
- `LONG-27`：paired-quality pending 的 review candidate 不能由 fresh second-pass receipt 升级。

oracle 绑定 evaluation contract SHA
`88c792e3afcb8d3da310d12d253afc842df68a0f7cc31c25557f1a004a1e68ae`；最终 oracle SHA 为
`283aa6931b81ae444d2a1d6bcd26e07f5d4d6715eaa6581231c9f3b7087ecc35`。没有外部签名 manifest 时，
最终审计严格保持：

```text
evidence_integrity_status=PASS
qualification_status=NOT_EVALUATED
atoms_pass=0
atoms_fail=0
atoms_not_evaluated=188
exit_code=2
```

见 [v25 no-manifest qualification](build/qualification-maturity-v25-20260717-no-manifest-final2.json)，
文件 SHA-256 为 `dfb2a0c5b6814769a84eda86d762c42a44daa23fec2adbbdffe7be9098c43fbc`。
这里的 integrity PASS 只证明当前 requirements/oracle/trust/projection 能被重建，不证明模型完成任何
一个行为原子。

### 29.11 最终回归与 generator projection

最终验证结果：

- 全套 572 项测试，`OK (skipped=2)`，即 570 项执行通过、2 项环境相关跳过；
- validator + finalizer 定向共 158 项，全部通过；其中 finalizer 96 项；
- 20 个 Skill 脚本逐个 `py_compile`，20/20；
- 20 个脚本逐个 `--help`，20/20；
- official `quick_validate.py` 返回 `Skill is valid!`；
- no-manifest qualification 为 `0/188 NOT_EVALUATED`；
- 两份 generator projection 都是 30 文件，路径集合和逐文件字节完全相同。

builder 与 policy 同步升级为 `1.8.2`。最终 projection 标识为：

| 项 | SHA-256 |
|---|---|
| capability source | `95694c8d5120be6ea70b97feed71ebc8f0960a0a5f098a20a205d3c3f64a74eb` |
| evaluation surface | `7681d0f4d0102aac6399b1d46e801d815e21c883a4b02311f7e4928c4aeb4b06` |
| inventory | `73945d96fd3a02a342ebc471c296e8be22ee49d04be34c397a38daa2b7a5ae52` |
| manifest | `a25442bf2459e217b930029a2425f418c468f7f15a7aa9b862f8d33266425fb2` |
| projection tree | `c68dd7105f63c983f8f0a9ca5a7301b5d92507c2628c5633176a5b4e5cdd16ee` |

两份 manifest 分别为 [final2 A](build/generator-projection-maturity-v25-final2-20260717.manifest.json)
和 [final2 B](build/generator-projection-maturity-v25-final2-repro-20260717.manifest.json)。projection 保留
paired-quality request、review-only 发布和 run-dir 事务等生成/收尾能力；三态候选队列只存在于安装版
审计面，投影仅保留说明性合同，不包含 `validate_humanize_candidate_queue.py`。oracle、requirements、
auditor、runner、sealer、qualification replay 和 second-pass 控制面仍不进入生成器。

### 29.12 v25 成熟度裁决

v25 可以支持的结论是：

> 工具链现在能区分“候选可机械组装”与“改后质量已获可信复核”，能为每次变化生成可重放的成对
> 请求，能在发布失败、失败重跑、绝对路径污染和后台进程残留时恢复 canonical 工件，并能把
> PASS/REVIEW/FAIL 候选存入互斥队列 head。

它仍不能支持“成熟自动 Humanizer”或“生产级无人值守全文改写器”的说法，原因不是谦虚措辞，而是
明确缺少以下证据：

1. 没有代理不可伪造的外部 paired-quality response 签名与验签服务；
2. 188 个生成资格原子仍是 `0 PASS / 188 NOT_EVALUATED`；
3. 本地 runner 最高 E2，不能证明宿主 oracle、完整 Skill、用户 profile 或工作区不可达；
4. academic correctness、公式推导、数据、引文和作者身份均未评估；
5. 真实正证据仍是一个局部 physics 范围，且盲读继续提出局部改进；
6. POSIX process-group 不是通用恶意代码沙箱，`check_command` 仍须来自可信项目构建流程；
7. 超过两个 unit、非相邻、跨文件、跨标题、标题解锁、拆段和整段删除仍没有自动生产权限；
8. 当前本地工具不消费外部 clearance，因此正常 REWRITE 的顶层状态有意保持 `REVIEW/2`。

因此最新定位是：**这是一个成熟度较高的 fail-closed 中文学术文风候选生成与审计工具链，已经能
可靠拒绝多类虚假完成态；但它还不是获得外部质量资格的自动改写器。**

## 30. 2026-07-18 v26：入口口径与证据权威性收紧

### 30.1 这次修复的实际问题

v25 的执行链已经把普通 `REWRITE/NO_CHANGE` 固定为 `REVIEW/2`，但入口文本仍有三类会误导调用方的
表述：`CLEAN` 被称作“可直接使用”，默认 `REWRITE` 被称作“直接交付正文”，维护注释仍只列
`accepted/rejected` 两态。v26 将它们统一改成“正文置前的待审候选”，并在 Skill 元数据中把“终审工具”
收窄为“终审辅助、候选生成与机械审计工具”。这不是措辞偏好，而是防止调用方绕过 paired-quality
门的执行安全修复。

### 30.2 证据与投影重新登记

Skill 本体变更后，旧 projection policy 正确拒绝了未登记的 capability hash。v26 没有绕过该拒绝，而是
把 policy/builder 升到 `1.8.3`，登记新的闭集 capability hash，再分别重建 A/B projection。两份 manifest
的核心结果为（完整指针见 [humanize-academic-authority-v26-20260718.json](build/humanize-academic-authority-v26-20260718.json)）：

| 项 | v26 值 |
|---|---|
| capability source | `30e9cb7d5da4cb85b269ab97ed67ce568b139b0ff499250cfeef78ca5c489d3d` |
| evaluation surface | `9d04a698cc3ad8caaff2579f363308aa61ca666e77689f0957bd2836a1da5e50` |
| inventory | `4fdc2426be915b1a03ed7d3f6f7359180cb3cbb2099e37cc6b8306713f17a600` |
| policy | `1.8.3`, canonical `7627c15a2c0a8952b6a7cf46ce8d8490356c949bc4e8ae8cfa6b2991161c5b9e` |
| A/B manifest | `e14fe7b3ce25f8975dd06d43a06b7a1c0f1bf7388d7273c263eb75a2fe5bc514` |
| A/B projection tree | `22616b947a1287e8c48cff3e3479c964eae3ac849dccf9ec3a28d8254ea82b66` |
| projection | 两份各 30 文件，路径/字节完全一致，证据上限 E2 |

三态候选队列仍只在安装版审计面；projection 不包含 `validate_humanize_candidate_queue.py`。这条边界在
报告中单独写明，避免把“安装版有队列”误读成“生成器上下文带着队列能力”。

### 30.3 candidate C 的退出码分层

v25 `forward-clean/decision.json` 曾把 mechanical exit `0` 写进顶层 `validator_exit_code`，而同一
before/after 的权威 paired-quality summary 已是 `REVIEW/2`。v26 在当前 `1.8.3` policy 下重放同一
candidate，得到新的 request SHA `e5d815af17cae704951de231638f9065320443e6a67f3542448fccd16d5e52af`；
旧 `b7daa...` 只保留为 v25 policy 的历史 request。当前摘要见
[paired-quality-validation-summary-v26-rerun.json](build/maturity-v25-20260717/forward-clean/paired-quality-validation-summary-v26-rerun.json)，其 SHA-256 为
`34ada9053b3594b458e3410393514a982b8546e787450e47b4a1b6a36d16e844`。
v26 将 decision record 分层为：

```text
mechanical_validation_status=PASS
mechanical_validation_exit_code=0
paired_quality_review_status=PENDING_EXTERNAL_REVIEW
delivery_gate_status=REVIEW
delivery_gate_exit_code=2
publish_state=REVIEW_CANDIDATE
```

并显式绑定 `authority_artifact=paired-quality-validation-summary-v26-rerun.json`。这保证机械门通过不会覆盖顶层
交付裁决，也让复核者能从同一候选的 before/after SHA 重放状态。

### 30.4 v26 回归结果与已知证据缺口

- 全套 `python -m unittest discover -s tests -p 'test_*.py'`：573 项，`OK (skipped=2)`；
- 新增入口口径反向测试：禁止 `可直接使用/直接交付正文/终审工具/已完成所列范围`，要求明确
  `待审候选`、机械验证和 paired-quality 状态；
- [v26 no-manifest qualification](build/qualification-maturity-v26-20260718-no-manifest.json)：`evidence_integrity_status=PASS`、`qualification_status=NOT_EVALUATED`、
  `0 PASS / 0 FAIL / 188 NOT_EVALUATED`、退出码 `2`。JSON SHA-256 为
  `232a4ac32d6dbec287770088352f6e2a28b009a3437e0a13e0ce949d9475d2da`；
- 报告链接审计覆盖 309 个本地链接和 18 个 Markdown 片段锚点，当前均可解析；乱码文件仍按既定边界跳过；
- 当前仍没有代理不可伪造的外部 paired-quality clearance；candidate C 的完整 request 原件未单独归档，只有
  request SHA 出现在权威 summary/decision；全套测试的原始 stdout 也未作为独立日志文件持久化。因此本节的
  测试结论以本轮命令输出和计数为依据，不把缺失原始日志包装成可独立重放的日志证据。

### 30.5 v26 裁决

v26 让“入口说什么”和“状态机实际允许什么”一致，并把 projection、candidate decision 和资格审计的
权威关系写清楚。它提高的是调用安全、证据可读性和回归可发现性；没有提高生成资格本身。当前仍只能说：

> Skill 是一个有严格拒错、待审候选、事务恢复和证据分层的中文学术文风工具链；它仍不是已获外部质量
> 授权的自动 Humanizer，188 个生成原子仍未评估，学术正确性和作者身份仍不在本工具证明范围内。

## 31. 2026-07-18 v27：短文证据包与外部 paired-quality 验签边界

### 31.1 直接验证结果不再只存在于 stdout

v26 之前，`validate_humanize_output.py` 会在 JSON 输出中给出完整 paired-quality request，但普通短文调用
没有可靠的持久化入口。v27 新增 `--evidence-dir <不存在的目录>`，以同卷 staging 和原子 rename 保存：

```text
validation-result.json
paired-quality-review-request.json
evidence-manifest.json
```

manifest 绑定 before/after SHA、request SHA、顶层状态、退出码和目录内每个工件的 SHA-256，并在提交前
重新读取来源文件。目标已存在、来源在验证后变化、路径经过 symlink/reparse point 或中途写入失败时，
统一返回结构化 `FAIL/1`，不留下半包，也不把原本的 `REVIEW/2` 冒充为已持久化成功。该包证明的是
“当前验证结果与当前字节绑定”，不是外部质量授权；它仍未保存 invocation 原件、stdout/stderr 原件或
before/after 内容副本，也没有 content-addressed 一次性消费账本。

### 31.2 外部 response verifier 的 P0 修复

v27 增加安装版审计 verifier，使用严格 JWS Compact 和 Ed25519 检查外部 paired-quality response。首轮
实现仍有一个可被红队直接利用的 P0：`review_record_sha256` 只检查是否为 64 位十六进制，攻击者可以填
全 `a` 占位符，在其他字段通过时获得 paired-quality PASS。当前实现改为必须同时提供真实
`humanize-paired-quality-review-record/v1` 工件，并逐项绑定：

- exact request SHA、challenge SHA 和 response ID；
- 与 request/response 完全相同的 change target 集合；
- 每个 target 的 `problem_span`、`reading_effect` 和 `decision_rationale`；
- review record 原始字节与签名 payload 中 `review_record_sha256` 的一致性。

缺 record 为 `REVIEW/2`；字节哈希、request、challenge、response 或 target 错绑为 `FAIL/1`；
“已人工审核、符合要求、更自然、没有问题”等空泛理由固定为 `REVIEW/2`。`NO_CHANGE` 不允许空数组
真空通过，必须使用唯一合成 target `NO_CHANGE`，并解释为什么继续改写没有可定位收益。

verifier 还拒绝 `alg=none/HS256/ES256`、重复或未知 JSON 键、非 canonical base64url、NaN/Infinity、
未知/退休/撤销 key、超时或 future response、TTL 越界、trust epoch 漂移、部分/额外/重复 target、
artifact 漂移和不安全路径。质量维度缺失属于“反馈未完成”，按合同返回 `REVIEW/2`；伪造签名、绑定
错误和未知字段属于硬完整性失败，返回 `FAIL/1`。在 grant 前还会再次逐字节读取
request/challenge/response/keyset/anchor/review record 和 before/after；故障注入在最终重读时改动 request
或正文，均得到漂移 `FAIL/1`，不会用内存中的旧检查覆盖磁盘新状态。

### 31.3 信任根没有被本地自签绕过

普通 `--trust-anchor`、仓库 keyset、调用方 `HUMAN` 标签和环境变量内容都不自动构成信任根。独立
launcher 必须固定 anchor 路径，并由宿主证明该 anchor 受 ACL/所有权保护。当前标准库实现对 POSIX 只接受
所有者可控且 group/world 不可写的 anchor；Windows 不根据 mode bits 猜测 ACL，默认返回
`UNPROTECTED_TRUST_ANCHOR -> REVIEW/2`。测试中的 external-anchor PASS 使用显式 mock 表示未来受保护
launcher 边界，不证明当前 Windows 机器已经部署了该边界。

因此本轮可证明两件不同的事：

1. 有效签名但无可信 anchor 时，`cryptographic_signature_status=PASS`，但
   `paired_quality_clearance_granted=false`、`REVIEW/2`；
2. 测试夹具中的受保护 anchor、完整 review record、全 change/9 维 PASS 可以得到 paired-quality
   `PASS/0`，但 `academic_correctness`、authorship、Voice、结构语义和 second-pass 仍为独立未评估门。

当前 verifier 没有接入 `validate_humanize_output.py` 或长文 finalizer 的原子发布事务；本地也没有真实外部
审批服务、代理不可访问私钥、在线一次性 redemption、最高 keyset sequence 受保护台账或 Windows ACL-aware
launcher。故普通生产路径仍保持 `PENDING_EXTERNAL_REVIEW -> REVIEW/2`。

### 31.4 v27 回归、projection 与资格状态

最终机器验收：

| 项 | v27 结果 |
|---|---|
| 全套测试 | 598，`OK (skipped=3)`；595 执行通过 |
| paired-quality verifier 专项 | 23，22 通过；1 个 Windows symlink 权限跳过 |
| direct validator 专项 | 64/64 |
| Skill scripts | 21/21 `py_compile`，21/21 `--help` |
| official quick validator | `Skill is valid!` |
| projection policy/builder | `1.8.4` |
| A/B projection | 各 30 文件，路径和逐文件字节完全一致 |
| qualification | `0 PASS / 0 FAIL / 188 NOT_EVALUATED / exit 2` |

v27 projection 标识：

| 项 | SHA-256 |
|---|---|
| capability source | `e3101d315c380d526390aa9193b103986a68e25fc37e974c0d9c3f8d7698b4bf` |
| evaluation surface | `c5cde4241477e0f7f811b47a73438fac2cc0f999f40310dfa4095baa0fcb4645` |
| source inventory | `481f0439f32e3f751fbaf37335dd59abbc23db81ebf1a1bdbebc488736765cd0` |
| policy canonical | `37bc0e3d383463e6b9bd972c6e519b3c8ebe7f205b229df41fbad503c707bf12` |
| A/B manifest | `7cb6d0b8b9ea9079335958c3bc84e92f674deae4a315a8946bc36861b96ee6e4` |
| A/B tree | `ba9f2fe6c7e4a41d960f2cdcf815c8762285b3826e3b8dd22e3e0f15ba824e0b` |

两份 manifest 分别为
[v27 final A](build/generator-projection-maturity-v27-final-20260718.manifest.json) 和
[v27 final B](build/generator-projection-maturity-v27-final-20260718-repro.manifest.json)。clearance 合同和 verifier 被明确
归入安装版 evaluation surface，不进入 30 文件生成 projection；投影内也不出现它们的 basename 或命令。
本轮权威摘要见 [v27 authority pointer](build/humanize-academic-authority-v27-20260718.json)。

[v27 no-manifest qualification](build/qualification-maturity-v27-20260718-no-manifest-final2.json) 的 SHA-256 为
`c15bdb6b626b538f44ae55050835eb98b4ff29055e8ce3b0aff67d05babf5233`。报告内部状态为
`evidence_integrity_status=PASS`、`qualification_status=NOT_EVALUATED`、`0/188`、退出码 `2`。这里的
integrity PASS 只证明合同、requirements、oracle、trust policy 和 projection 可重建，不证明任何生成原子。

### 31.5 v27 裁决

v27 让短文 request 可以原子归档，也把“外部审阅者说通过”拆成签名、信任根、逐 change 维度、具体理由
和当前 artifact 五层绑定；本地自签、占位哈希、空泛理由和部分维度都不能形成虚假闭环。可以据此称为
更成熟的 fail-closed 候选生成与审计工具链。

仍不能称为成熟的无人值守自动 Humanizer。真实外部审批服务和 Windows 受保护信任根尚未部署，外部
clearance 尚未进入 finalizer 发布事务，188 个生成资格原子仍全部未评估，学术正确性、作者身份和跨文体
长期稳定性也没有被本轮测试证明。

## 32. 2026-07-18 v28：短文验证记录的自包含重放

### 32.1 本轮解决的不是“多存几个 JSON”

v27 的 `--evidence-dir` 能原子保存验证结果、paired-quality request 和 manifest，也能在提交前重读
before/after。它证明“这三个文件在一个目录里相互绑定”，却不能回答以下问题：

1. 原始 before/after 删除后，能否只靠证据目录重跑 validator；
2. 当时使用了哪些 CLI 参数、保护术语、KEEP 理由、fragment/report-scope 配置；
3. stdout、stderr 与 `validation-result.json` 是否对应同一结果；
4. 同一次调用再次发布是幂等，还是会被误判为冲突；
5. report-scope JSON 和 detector report 原件是否随记录冻结；
6. 当前 validator、scanner、lexicon 或运行时变化后，系统会不会用新策略伪称旧记录已重放；
7. reviewer proposal 因隐私规则不保存原 reviewer ID 时，系统会不会伪造一个 ID 继续重跑。

因此，v27 更准确的名称是“原子验证摘要包”，不是“可独立重放的验证记录”。v28 将这一区分写进
schema、代码、测试和报告，不再用 manifest 自哈希替代真实重执行。

### 32.2 v2 证据目录

`validate_humanize_output.py --evidence-dir <DIR>` 现在提交以下闭集：

```text
<DIR>/
  inputs/
    before.bin
    after.bin
    report-scope.json        # 仅 REPORT_INFORMED
    report.bin               # 仅 REPORT_INFORMED
  invocation-request.json
  validation-result.json
  paired-quality-review-request.json  # REWRITE 时
  warning-review-request.json         # 有 warning 时
  rendered-output.txt
  stderr.txt
  execution-record.json
  evidence-manifest.json
```

`invocation-request.json` 保存 mode、scene、output format、strict-speech-acts、fragment、保护术语、
KEEP 理由、warning proposal、request SHA 和 report-scope 归档位置。原 reviewer ID 不保存，只保存
`reviewer_id_sha256`；只要存在 proposal，调用就标为 `REEXECUTION_NOT_SUPPORTED`，而不是编造身份标签。

输入记录同时保存归档相对路径、原文件名/后缀、原路径 SHA、内容 SHA 和大小。原路径 SHA 用于绑定
调用身份，不是路径匿名化；`validation-result.json` 仍可能含绝对路径和正文上下文，因此整个目录固定
标记 `contains_source_content=true`，不能当作可公开日志。

`execution-record.json` 保存 intended exit、stdout/stderr SHA 和三项限制。它明确写
`process_exit_observation=NOT_EXTERNALLY_OBSERVED`：进程内代码不能独立证明操作系统最终返回给父进程的
exit code，尤其不能忽略 broken pipe 或宿主终止。v28 没有把“计划返回 2”包装成“外部已观察到 2”。

### 32.3 内容寻址与发布事务

`invocation_sha256` 对规范 invocation body 求 SHA-256，`run_id` 固定为
`hvr1-<invocation_sha256>`。它绑定输入字节、全部可复现参数、路径假名、policy 快照和预期裁决。
`record_sha256` 再绑定除 manifest 外全部工件的精确大小与 SHA；manifest 有规范 JSON 自哈希。

发布仍使用同卷 staging、排他写、文件 `fsync`、发布锁和目录 rename，但 v28 增加了以下裁决：

| 情形 | 裁决 |
|---|---|
| 目标不存在、全部重读一致 | 原子发布 |
| 目标已存在，run ID、清单、文件和字节完全一致 | 幂等成功，不改旧字节 |
| 同一目标出现不同调用或不同字节 | `FAIL/1`，旧目录保持原样 |
| 缺文件、额外文件或额外目录 | `FAIL/1` |
| before/after/scope/report 在提交前漂移 | `FAIL/1`，清理 staging/lock |
| 输入或证据文件为 hardlink | `FAIL/1` |
| 路径经过 symlink/reparse point | `FAIL/1` |
| 任一 staged write、manifest write 或 rename 失败 | 目标要么完整存在，要么完全不存在 |

测试不是只注入“第二个文件写失败”。v28 逐个覆盖全部 artifact write、manifest write、rename 和
manifest 写完后源文件漂移，逐次检查目标目录、staging 和 lock 均无残留。

### 32.4 独立 replay 的三态语义

新增安装版审计脚本 `replay_humanize_validation_record.py`。它不 import validator 来复用结果判断，
而是独立完成记录验证，再通过 `subprocess` 调用当前 validator：

1. 拒绝 JSON duplicate key、NaN/Infinity、非法 UTF-8 和非规范 JSON 字节；
2. 拒绝未知字段、类型偷换、路径穿越、非法后缀、hardlink、symlink/reparse 和闭集外文件；
3. 验证 manifest 自哈希、record hash、invocation 自哈希和 run ID；
4. 核对 invocation、source bindings、result、paired/warning request、stdout/stderr 和 execution record；
5. 比较记录 policy 与当前 policy；
6. 从 `inputs/` 重建临时 before/after/report/scope，运行当前 validator；
7. 比较顶层状态、退出码、分层状态、findings、warning、paired request SHA 和规范化核心结果；
8. text 模式额外逐字比较重放 stdout；
9. 返回前再次重读整个证据目录，拦截 replay 过程中的 TOCTOU 修改。

状态固定为：

| 状态 | 含义 |
|---|---|
| `FAIL/1` | 记录内部损坏、清单冲突、跨工件不一致或当前同策略重算不同 |
| `REVIEW/2` | 记录完整，但 policy drift、proposal 不可原样复跑，或显式要求 live source 匹配而原路径已漂移 |
| `PASS/0` | 记录完整，当前 policy 相同，归档输入重算的核心裁决一致 |

默认归档重放不要求原路径仍存在。原 before/after/report/scope 删除后仍可 replay；同时单列
`live_source_status=MATCH/NOT_CURRENT`。需要证明当前工作文件仍是记录版本时追加 live-source 门，缺失或
漂移只可 `REVIEW/2`，不能混入归档完整性结论。

### 32.5 Policy 从四项扩为六项

v27 request 只绑定 validator、invariant checker、scanner 和 lexicon。v28 新增：

- `report_extractor_sha256`：REPORT_INFORMED 的静态提取行为属于验证策略；
- `runtime_contract_sha256`：绑定 Python implementation/cache tag、Python 版本、Unicode 数据版本和 OS 名。

policy 在验证开始前冻结，结束时重新计算；中途任何字节变化使运行失败。每个普通、warning 和 paired
request 都使用同一快照。外部 paired-quality verifier 也不再接受空 `policy_hashes`：必须恰好包含六个
64-hex 字段，缺项、增项或非法值均在验签前 `FAIL/1`。

REPORT_INFORMED 的 paired request 还新增路径无关的 scope semantic SHA、report/source SHA、fragment
总数和 editable ranges。这样同一 before/after 即便字节相同，也不能把针对一份 detector selection 的
外部 clearance 重放到另一份 selection。

### 32.6 真实持久化样本暴露的缺陷

第一份 v28 持久化样本没有通过 replay。原因不是正文或 policy 漂移，而是 text 输出中的 finding 使用了
原始绝对路径；重放器在临时目录运行后，finding 的路径前缀必然不同，于是得到
`REPLAY_STDOUT_MISMATCH/FAIL`。此前 15 项 replay 测试中的 text 样本没有 high finding，因此没有触发
这一分支。

修复不是放宽 stdout 比较，而是让公开 text finding 只显示稳定 basename，并让 replay 临时文件采用归档
原文件名。随后增加“text + high finding + 不泄漏绝对临时路径”的回归测试。最终持久化样本位于
[direct-validation-v28-final2-20260718](build/direct-validation-v28-final2-20260718)，原 validator 正确返回
`REVIEW/2`，因为 `LEX-FOUNDATION-01` 与新增信号仍未解决；独立 replay 返回：

```text
record_integrity_status=PASS
reexecution_status=PASS
replay_core_match=true
status=PASS
exit_code=0
run_id=hvr1-1db531017fda5ad6b69ea778abfcfb611ede8fbe1dfebf46ef4320fe8bdc7e16
```

这里两个状态不矛盾：原稿候选仍是文风 `REVIEW/2`；replay `PASS/0` 只说明“这次 REVIEW 可以从归档
输入稳定重算”，绝不把候选升级为质量 PASS。

### 32.7 v28 红队覆盖

专项测试覆盖以下攻击：

| 攻击 | 预期 |
|---|---|
| before/after/invocation/result/request/stdout/stderr/execution/manifest 单字节追加 | `FAIL/1`，不启动重执行 |
| 修改 result 后同步更新 artifact hash、record hash、manifest 自哈希 | 跨工件状态绑定 `FAIL/1` |
| 修改 stdout 后同步重算全部普通哈希 | stdout/result 语义不一致 `FAIL/1` |
| invocation 增加隐藏字段并重算 invocation SHA/run ID | strict schema `FAIL/1` |
| invocation archive path 穿越或后缀注入 | `FAIL/1` |
| extra file | 闭集 inventory `FAIL/1` |
| hardlink evidence file | `FAIL/1` |
| 同调用同目录再次发布 | 幂等、目录逐文件 SHA 不变 |
| 不同 scene 写入已有目录 | run conflict `FAIL/1`，旧记录不变 |
| 当前 policy 改变 | integrity `PASS`，reexecution `NOT_RUN`，顶层 `REVIEW/2` |
| 原文件修改 | 默认归档 replay `PASS`；live-source strict 为 `REVIEW/2` |
| 原 before/after/report/scope 全删除 | report 归档 replay 仍 `PASS` |
| reviewer proposal | 原 reviewer ID 不出现在任一文件；`REEXECUTION_NOT_SUPPORTED/REVIEW/2` |
| DRAFT + term、fragment + strict | 参数从 invocation 恢复并重算一致 |
| text 输出含 high finding | basename 稳定，stdout 精确重放 |

symlink 集成分支仍有 1 项因 Windows 当前令牌没有创建 symlink 权限而跳过；hardlink 使用真实 `os.link`
执行，reparse 位测试不依赖创建特权。这里不能声称敌对并发下 Windows 路径检查等价于句柄级 ACL 安全：
父目录检查与后续打开之间仍存在系统调用窗口，v28 的 `SELF_CONSISTENCY_ONLY` 明确不升级为外部信任根。

### 32.8 测试、projection 与资格状态

最终全量原始日志为 [full-test-audit-v28-20260718.log](build/full-test-audit-v28-20260718.log)，SHA-256：
`0d0f412741435d63b2e579371c9cf312ed3aa5dce5959be4239a54b72a7af629`。结果：

```text
Ran 617 tests in 71.740s
OK (skipped=3)
```

专项计数：validator 66 项；direct replay 16 项；external paired-quality verifier 24 项，其中 1 项 symlink
跳过。22/22 Python 脚本通过 `py_compile` 与 `--help`；`quick_validate.py` 首次因 Windows GBK 读取 UTF-8
失败，设置 `PYTHONUTF8=1` 后返回 `Skill is valid!`。这属于验证器环境编码问题，不通过改写中文文件规避。

最终 A/B projection：

| 项 | v28 final2 |
|---|---|
| policy / builder | `1.8.5 / 1.8.5` |
| 文件数 | 各 30 |
| 逐文件字节差 | 0 |
| excluded evaluation entries | 41 |
| capability source | `367e401d788a65706c30245ba834b5503587e75670379eddf8ff756b4cfa42d1` |
| evaluation surface | `3b5b0adf99b829941ff95e868c93ce0201f01e9dbb6e5443280df113b7ab0531` |
| source inventory | `462d1d0e7ed680630a76a27a3ea974b51aebbf80afa445b985c6b480eadb3257` |
| policy canonical | `90849754420dbb8510b422c71119b45c11d6ef90b389cac824b381734db59423` |
| policy raw | `8b418e25d1a98c6945170b379bb12f6ee47a88fa05e1341401508aff3fda3fc8` |
| builder executable | `506229ee4eb44b97e20716251e83b1f9c73e3b459a0819a43a5366c6b60d4334` |
| manifest | `695a49a3129c486a8440b92aada6b1d2bd8b5f857dd6cddfa930cc6825145213` |
| tree | `7792a0287d9781773933c85b56fcfcc527ec606ac3418006ddab2911fa10ed82` |

两份 manifest 为 [A](build/generator-projection-maturity-v28-final2-20260718.manifest.json) 与
[B](build/generator-projection-maturity-v28-final2-20260718-repro.manifest.json)。新 replay verifier 明确在
exclude/forbidden basename 闭集中，不进入 30 文件生成器 projection。

[v28 no-manifest qualification](build/qualification-maturity-v28-20260718-no-manifest-final3.json) 的 SHA-256
为 `1415fa43afffb5d2288e430f45c4bdf152d393a972114b2a7640b015268fde6a`。其内部状态继续是：

```text
evidence_integrity_status=PASS
qualification_status=NOT_EVALUATED
atoms_pass=0
atoms_fail=0
atoms_not_evaluated=188
exit_code=2
```

新增的 19 项 direct evidence/replay 测试没有给任何生成资格 atom 加 PASS。contract/requirements/oracle
版本分别升为 `2026-07-18.16 / 2.8.1 / 1.8.1`，只是同步新的证据合同和 stale binding。
本轮可追溯摘要见 [v28 authority pointer](build/humanize-academic-authority-v28-20260718.json)；该文件明确
声明自己不是外部信任根。

### 32.9 v28 裁决与剩余边界

v28 已把短文记录从“保存摘要”推进到“自包含、内容寻址、可三态重放、能拒绝整包内部矛盾”的工程形态。
它能在原输入删除后复跑，能区分归档重放与 live source，能拒绝 policy 漂移下的假 PASS，也能诚实拒绝
无法复制的 reviewer proposal。可以称为成熟的短文机械证据与复现层。

仍不能称为最终无人值守 Humanizer，原因保持具体：

- 自哈希与 run ID 只证明自一致性；同一攻击者若能重造整包，没有外部签名就不能证明历史真实性；
- 原 reviewer ID 的裸 SHA 只是低熵假名化，可能被字典反查，不是匿名或认证；
- Windows 没有 ACL-aware 受保护 launcher，路径检查也不是敌对并发下的句柄级隔离；
- external clearance 尚未与 validator/finalizer 原子消费，且没有一次性 redemption/消费账本；
- 188 个生成资格原子全部未评估；
- replay PASS 不评价搭配、段落职责、文风收益、学术正确性、作者身份或长期收敛。

v28 的成熟点不是把这些缺口改名为“已闭环”，而是让每个缺口都有可观察状态，且不能被低层 PASS 覆盖。

## 33. v31：红蓝队生产链复审、长文默认链闭环与信任边界收紧

### 33.1 本轮不是继续堆规则

本轮由一条红队合同审计和一条蓝队真实穿行并行执行。红队只攻击“是否还能伪造完成、复用旧证据、
自造信任或隐藏结构变化”；蓝队按普通用户路径实走 `DIAGNOSE/REWRITE/DRAFT/NO_CHANGE`、最小 TeX、
prepare、scaffold、finalize 和默认摘要。两路都不知道预设修复答案，输出保留具体命令、实际状态和失败点。

蓝队确认的正向能力没有被本轮改写抹掉：自然科研段中的“闭环控制”仍按正式术语排除；无病灶段保持
零候选；病灶段由 6 个候选降为 0；公式、数字、命名引语和保护区未漂移；否定范围发生变化时仍会
`REVIEW`；DRAFT 仍是表面载荷门 PASS、语义来源 `NOT_EVALUATED`；长文候选仍只发布到
`rendered_review/`。本轮修复集中在这些正向能力之外的失败链。

### 33.2 默认长文链 P0：scaffold sidecar 被 finalizer 当成 unit

旧推荐命令会在 rewrites 根生成 `scaffold_metadata.json`，而 finalizer 枚举全部 JSON，把 sidecar 的
stem `scaffold_metadata` 当成 unit，最终报 `unknown rewrite units: scaffold_metadata`。这意味着文档中
推荐的 prepare -> scaffold -> finalize 默认链实际上必失败。

v31 的处理不是“忽略所有未知 JSON”，而是只对精确保留名 `scaffold_metadata.json` 建立 strict schema：

- v1/v2 schema、字段闭集、计数、`completion_claim_allowed=false` 和 `requires_manual_completion=true`；
- records 的 `unit_id/path/decision/template_sha256` 逐项验证；
- unit ID 只允许安全 ASCII 文件名字符，拒绝路径分隔、控制字符、超长和大小写碰撞；
- sidecar 合法才跳过，损坏、伪造、字段增删或覆盖不一致仍 `FAIL/1`；
- 新增真实 prepare -> scaffold -> collect -> finalize 集成回归，证明不再出现 unknown unit。

同时 scaffold 升为 `humanize-rewrite-scaffold/v2`，新增严格 `--decision-map`。映射必须恰好覆盖全部
PENDING unit，值只能为 `REWRITE/NO_CHANGE`；缺失、多余、非法 ID 或大小写碰撞整体拒绝。这样混合长文
不再需要先全量生成一种 decision，再手改几十个 JSON。

### 33.3 paired-quality P0：普通调用者不能自造信任根或消费账本

红队证明了两条旧路径可以伪造“外部”条件：POSIX 当前用户创建 0600 anchor 后自行设置环境变量；以及
对同一 response 分别传 ledger-A、ledger-B，或删除 ledger 后再次运行。两者都破坏了“代理不可伪造的
外部信任/一次性消费”前提。

v31 固定普通 CLI 为审计面：

- Windows 不猜测 ACL；POSIX 只把 root-owned 且非 group/world-writable 的文件视为最低限度候选，当前
  root 进程也不能自证独立；普通当前用户 0600 anchor 固定不授予 `EXTERNALLY_ANCHORED`；
- caller `--redemption-ledger` 只记录 `CALLER_PROVIDED_DIAGNOSTIC_ONLY`，不创建、不写入、不消费；
- 即使签名、request、artifact、review record 和九个质量维度全部通过，standalone 也只输出
  `verification_status=PASS`、`paired_quality_gate_status=PASS`、`delivery_gate_status=REVIEW`、exit 2；
- `paired_quality_clearance_granted` 与 `quality_clearance_granted` 固定 false；
- 真正 clearance 仍需要普通 CLI 之外的受保护 launcher、固定 trust epoch、不可删除 ledger 和原子接线。

该改动把“局部门验证通过”与“全文交付通过”彻底分开，不再让独立验签器写通用
`delivery_gate_status=PASS`。

### 33.4 request policy surface 扩展

旧 paired request 只绑定 validator、invariant checker、scanner、lexicon、report extractor 与 runtime；
修改成对验签器、信任逻辑或 clearance 合同时，旧 request 仍可能被新 verifier 接受。

v31 在 policy hash 闭集中新增：

- `paired_quality_verifier_sha256`；
- `paired_quality_contract_sha256`；
- runtime contract 同时绑定 paired clearance contract 参考文件。

direct evidence、replay、capture 和 qualification oracle 全部同步接受并重算这 8 项闭集。旧证据缺项时
不是静默兼容 PASS，而是 policy/schema drift。generator projection 仍禁止携带 verifier 与 clearance
合同；validator 中的安装版文件名采用运行时组合，投影审计确认 forbidden basename 未泄漏。

### 33.5 STRUCTURAL 隐藏内容交换不再误报语义 PASS

红队最小攻击把两个同为 `EXPOSITION` 的段落内容互换，却保持默认 paragraph ID groups。旧 plan 只比较
ID 顺序，可能得到 `change_applied=false`；统一 validator 又只看到机械基线与候选相同，于是顶层结构语义
被聚合为 PASS。

v31 同时处理两类变化：

- plan 显式移动/合并时，仍生成原有结构语义复核请求；
- plan 声称默认一一映射、但 restored 正文相对结构基线发生变化时，登记
  `UNDECLARED_CONTENT_CHANGE`，生成绑定 before/baseline/after/plan/context/policy 的外部复核请求。

因此无论“声明移动”还是“隐瞒移动”，只要 STRUCTURAL 候选改变内容，结构语义保持
`NOT_EVALUATED / PENDING_EXTERNAL_REVIEW`。新回归实际交换两个同职责段落，结果为候选组装 PASS、
总状态 REVIEW、unit DONE、结构语义 pending，而不是结构 PASS。

### 33.6 旧长文 run 不能跨 policy 版本继续消费

prepare 现在把闭集 `policy_snapshot` 和 `policy_snapshot_sha256` 写入 `run_metadata.json`。快照覆盖：

- validator/invariant/scanner/lexicon/report extractor；
- paired verifier/contract；
- prepare/finalizer、scene router、Voice builder/validator、negative guard loader；
- Skill/operational/workflow/routing/source trust 参考和 Python runtime。

finalizer 在场景、Voice 和 bundle 读取前重建当前 snapshot。缺字段、自哈希错误、任一实现或参考 drift
直接 `FAIL/1`；攻击者修改 metadata 后重算 `prepare_integrity` 也不能继续消费旧 run。测试对
`finalize_script_sha256` 做一致重封装，仍得到 `run policy snapshot drift`。

### 33.7 实用性误报与漏检修复

蓝队发现裸计数单字“不”会把“不同位置、不锈钢、不变量、不可压缩流”当作句级否定变化。v31 在
可审计词法排除表中加入这些明确技术复合词；真实的“不能、不再、并非、没有”等否定仍保留原门。

另一个样本“该段只交代实验设置，不把它写成研究贡献，也不预告下一节”此前未命中编辑后台。v31 给
`LEX-META-01` 增加“段/节/部分 + 只交代/说明/介绍 + 不把/不将 + 写成贡献/结论”与“不预告下一节/下文”
组合正则和正例，scanner 回归能定位该句。

普通用户交付层也与审计层拆开：默认只给候选正文和三行以内的范围、未决项、下一步；policy hash、
gate 枚举、request、ledger 和路径只进入机器工件、ANNOTATED/PATCH 或显式审计请求。“只输出正文”时
连摘要也省略，但后台未决状态仍绑定同一版本，不能因界面简洁而删除。

### 33.8 v31 验证结果

全量结果：

```text
Ran 653 tests in 130.481s
OK (skipped=3)
```

即 650 项执行通过，3 项环境相关跳过。关键专项包括：

- unified validator：67 项；
- paired-quality verifier：31 项，1 项 Windows symlink 能力跳过；
- invariant checker：35 项；
- lexical scanner：27 项；
- scaffold：6 项；
- long prepare：28 项；
- direct replay、capture、qualification 与完整 long finalizer 均纳入全量 653 项。

最终 generator projection A/B：

| 项 | v31 final |
|---|---|
| policy / builder | `1.8.8 / 1.8.8` |
| 文件数 | 各 31 |
| 逐文件字节差 | 0 |
| capability source | `b85af5a61e0dfa0ccdc5730792b7067e3e64a1ab18108289ee71a99ee9fec3ad` |
| tree | `deda0d9fe71d55476c423260035e226557a265fe4f03c4568c8054e102e7b069` |
| evidence cap | `E2` |

对应 manifest：

- `build/generator-projection-maturity-v31-final-manifest-20260718.json`；
- `build/generator-projection-maturity-v31-final-repro-manifest-20260718.json`。

无 manifest qualification 继续返回：

```text
evidence_integrity_status=PASS
qualification_status=NOT_EVALUATED
0 PASS / 0 FAIL / 188 NOT_EVALUATED
exit_code=2
```

### 33.9 v31 裁决

v31 可以称为更成熟的生产候选与机械证据工具链：默认长文路径可运行，输入 sidecar/ID/decision map
fail closed，旧 policy run 不可复用，成对验签不能自造信任，结构隐藏移动不会误报语义 PASS，短文术语
误报和编辑后台漏检均有具体回归。

它仍不能称为无人值守自动 Humanizer。188 个生成资格原子仍全部未评估；普通 CLI 没有独立 launcher、
不可访问私钥、受保护 redemption ledger 或外部质量服务；paired/structure/Voice/second-pass 任一门 pending
都阻断正式完成；学术正确性与作者身份始终未评估。v31 的成熟性来自更难伪造、更容易复核和更少正常路径
摩擦，不来自把 REVIEW 改名为 PASS。

## 34. 2026-07-18 v32 黑盒实用性、非 STRUCTURAL 顺序门与状态摘要

### 34.1 为什么 v31 仍需继续攻击

v31 已经能阻断顶层假完成，但“顶层始终 REVIEW”本身会遮住局部状态是否可信。三路 fresh 代理因此不再
只攻击 `delivery_gate_status`，而是分别实做短文、默认长文链和局部信任/结构状态。它们只读取当前 Skill
与原始输入，不读取既有报告、expected output 或旧红队结论。

短文路径实际产生 COURSE 和 RESEARCH 候选；长文路径实走 prepare -> scaffold -> finalize；红队则对
caller trust、旧 policy、sidecar、段落移动和文本摘要做最小探针。没有代理被要求“想办法 PASS”，所以
REVIEW、失败和歧义都保留为结果。

### 34.2 非 STRUCTURAL 隐藏整段换位

v31 的 BALANCED unit 可以把两个完整段落对调而不提交 `structural_plan`。旧 finalizer 会给：

```text
mechanical_validation=PASS
candidate_assembly_status=PASS
unit_status=DONE
structural_plan_status=NOT_APPLICABLE
structural_semantic_mapping=NOT_APPLICABLE
```

顶层仍因 paired-quality 为 `REVIEW/2`，所以这不是最终 PASS 绕过；但结构变化完全没有进入结构语义门，
`DONE`、coverage 和 voice 局部字段会给调用者错误暗示。

v32 新增 `NON_STRUCTURAL_EXACT_PARAGRAPH_ORDER`：先剥离纯保护占位行，再规范化作者段落；只匹配
before/after 中均唯一、完整保留且至少 8 个汉字的段落。两个以上匹配段落出现逆序时：

- unit 固定 `UNRESOLVED`；
- ledger note 为 `non_structural_paragraph_reorder_detected`；
- structural status 为 `REVIEW`；
- semantic review 为 `BLOCKED_BY_SCOPE_VIOLATION`；
- paired-quality 为 `BLOCKED`；
- coverage/voice completion 均 false；
- 不生成 `rendered/` 或 `rendered_review/`；
- 若生成 partial，相关文件保持冻结 source 字节。

fresh 重放中 OS exit 为 2，`candidate_assembly_status=REVIEW`，partial 与 source SHA-256 一致。该门只
声称拦截可机械确认的完整段落换位；近似改写后移动仍需 diff、外部 paired-quality 和连续阅读，报告不把
一个高置信度 detector 写成结构理解器。

### 34.3 scaffold sidecar 从“文档解释”升级为机器合同

红队发现 v31 的 `template_sha256` 校验缩进在 `raise` 之后，实际上不可达，任意非 hash 字符串都能被
`collect_rewrites()` 接受。v32 将检查移回 records 循环，非法格式直接：

```text
ValueError: invalid scaffold metadata template hash: scaffold_metadata.json
```

长文黑盒随后指出，修复后控制台虽写 `metadata_scope=scaffold_creation_time`，JSON sidecar 本身仍只含
`requires_manual_completion=true` 与原模板 hash，需要读者另查文档。最终版本因此把 schema 升为
`humanize-rewrite-scaffold/v3`，增加：

```json
{
  "metadata_scope": "SCAFFOLD_CREATION_TIME",
  "template_hash_scope": "ORIGINAL_TEMPLATE_BYTES"
}
```

`requires_manual_completion` 明确是骨架生成时状态，不是动态进度；`template_sha256` 绑定原始模板字节，
不冒充人工填写后的当前 bundle hash。finalizer 对 v1/v2 保持只读兼容，但 v3 严格要求两个 scope 字段。

### 34.4 短文语义门从“精确计数”向受限等价推进

RESEARCH 原稿含“可能在一定程度上或许暗示”。v31 要求删除冗余 hedge，却又因 marker 数量下降产生
`SPEECH_ACT_MODALITY_SCOPE_CHANGED`，形成规则和验证器张力。v32 只对局部 stacked possibility 建立
窄豁免：

- before 同句至少有两个 `可能/或许`；
- after 至少保留一个；
- 其他 modality marker 不变；
- 含可能性句的数量不变；
- 不新增 before 中没有的程度判断。

隔离样本将“可能在一定程度上或许暗示”改为“可能暗示”后，speech-act layer PASS，且没有
modality warning。把它改成“影响有限”仍触发 `SPEECH_ACT_MODALITY_TO_DEGREE`。

同时，“意味着”从 definition/naming markers 删除；它是普通蕴含/结果关系，不等于“定义为、称为、记作、
以下简称”。真实命名标记继续受保护。

完整 RESEARCH 候选仍为 `REVIEW/2`：它还删除了目录预告中的另一处“可能机制”，并改写了否定防御串，
因此保留 `SPEECH_ACT_MODALITY_SCOPE_CHANGED` 与 `SPEECH_ACT_NEGATION_CHANGED`。这证明豁免没有扩大为
“全文只要还剩一个可能就通过”。代理也没有为追求 PASS 恢复冗余套话或自填人工理由。

### 34.5 文本摘要与字段作用域

v31 finalizer 默认完整 JSON，普通工具层会把合法 `REVIEW/2` 显示成命令失败；同时 JSON 内还有
`candidate_assembly_exit_code=0` 和 unit `DONE`，需要熟悉合同才能正确解释。

v32 增加 `--format text`，正常待审候选输出：

```text
DELIVERY REVIEW exit=2 publish=REVIEW_CANDIDATE
status_authority=delivery_gate_status+process_exit_code
candidate_assembly=PASS; paired_quality=PENDING_EXTERNAL_REVIEW
units[DONE=1]; scope=CANDIDATE_ASSEMBLY_NOT_DELIVERY
review_candidate=<run>/rendered_review
compile_check=NOT_RUN
humanize_completion_claim_allowed=false
```

机器 JSON 新增 `unit_status_scope=CANDIDATE_ASSEMBLY_NOT_DELIVERY`。`DONE/NO_CHANGE` 只描述 unit 候选
账本，不再允许脱离顶层 delivery gate 解释。默认 JSON 仍保留全部审计字段；text 只是用户层 projection，
不是删减未决状态。

`build_humanize_action_profile.py --format text` 也不再写裸 `PASS: 21 available`，改为：

```text
PROFILE_PASS: production_positive=0, provisional_positive=17,
runtime_negative_guards=4, audit_only=6, unavailable=0
```

profile PASS 只表示构建合同通过，不能把 provisional 卡片写成生产授权。完整 action builder 继续被 generator
projection 排除。

### 34.6 默认链复测

最小 TeX 再次实走默认链：

1. prepare 返回 `READY/0`，AUTO 回退 GENERAL；
2. scaffold v3 生成 1 个 REWRITE 模板，并明确 creation-time scope；
3. 唯一改动是删除“值得注意的是，”；
4. finalizer `--format text` 返回 `REVIEW/2`；
5. candidate assembly 与机械验证 PASS，paired-quality 待外部复核；
6. 输出只在 `rendered_review/`，没有正式 `rendered/`；
7. 源文件前后 SHA-256 均为
   `db78db5b6ad9e294d7ef8ced9b2b0b083d783109e440b8e503793b3004065153`；
8. `compile_check=NOT_RUN`，报告不写成 TeX 编译通过。

Skill 中“默认每个 REWRITE 都需 structural_plan”的错误表述已经改正：只有 STRUCTURAL REWRITE 提交
plan；LIGHT/BALANCED 不接受 plan，也不得交换完整段落。

### 34.7 v32 验证结果

全量：

```text
Ran 659 tests in 195.609s
OK (skipped=3)
```

即 656 项执行通过，3 项环境相关跳过。新增 6 项持久回归覆盖整段换位、sidecar hash、finalizer text、
action-profile trust summary、局部 hedge 压缩和“意味着”分类；scaffold v3 scope 又纳入 scaffold/finalizer
现有回归。

发布检查：

| 项 | v32 final r2 |
|---|---|
| quick validation | PASS |
| Python compile | 25/25 |
| CLI `--help` | 25/25 |
| policy / builder | `1.8.9 / 1.8.9` |
| projection files | 31 / 31 |
| A/B byte diff | 0 |
| capability source | `a3f0e84516a4aac430328708a0211ed533ff9adaefad13f7147cd20b7f530f54` |
| tree | `79ae0816f31ea3c484700b8288d02c893595df3a640cca4f04f2cb6a5fd41d33` |
| evidence cap | E2 |
| qualification | `0 PASS / 0 FAIL / 188 NOT_EVALUATED`，exit 2 |

最终 projection：

- `build/generator-projection-maturity-v32-final-r2-20260718/`
- `build/generator-projection-maturity-v32-final-r2-manifest-20260718.json`
- `build/generator-projection-maturity-v32-final-r2-repro-20260718/`
- `build/generator-projection-maturity-v32-final-r2-repro-manifest-20260718.json`

### 34.8 v32 裁决

v32 的成熟化集中在普通用户和调用器真正会误读的地方：局部 PASS 不再掩盖未授权结构换位；sidecar 的
hash 与作用域都成为机器可读合同；profile 摘要不再混淆 provisional；长文 stdout 第一行直接给权威
delivery；词法门能放行一种有明确语义边界的去冗余动作。

边界仍保持不变：完整段落 detector 不覆盖所有近似移动；真实读感收益需要独立 paired-quality；普通 CLI
没有受保护 launcher、不可访问私钥或不可删除消费账本；`rendered_review/` 不是正式终稿；学术正确性、
来源真实性、作者身份和 188 项生成资格均未获得 PASS。v32 是更可信、更可用的待审候选工具链，不是会
自证“已经像人写”的自动发布器。

## 35. 2026-07-19 v33：从事务证据到同义换壳的实际模型收敛

### 35.1 生产链新增内容

v33 把长文结构变化拆成三条正交证据链：

- `target_groups`：结构移动本身；
- `local_rewrite_intent`：move-only baseline 到实际候选的局部改字；
- paired-quality / structural semantic review：改后是否更好读、结构含义是否仍成立。

transaction v2 每个 fragment 必须是 `REWRITE + rewrite_intent` 或局部 `NO_CHANGE + reason +
evidence_spans`。v1 只读兼容但 intent 固定 REVIEW。任何 member 失败时，candidate、intent evidence、
paired request 和 transaction review request 原子回滚。BALANCED 的 merge/split 也必须用 unit v2 intent
声明唯一 source span、原/目标段数和 HIERARCHY signal；机械 PASS 不被描述成语义收益。

资格回放新增的三个 v2 字段一度没有进入 strict scenario allowlist，导致 41 项资格测试无法加载 catalog。
本轮以精确集合差修复，而非放宽 schema。LONG-22/23/24 现在同时回放 transaction review request schema、
rewrite intent coverage 和 missing-unit count。

### 35.2 语料驱动 detector 的新增抓手

此前 GPT MD/TeX 负例已经覆盖“奠定基础、提供支撑、提供线索、后续出发点”，但 fresh 模型仍生成：

```text
相关结果也为后续研究提供了可靠起点。
```

这不是凭空猜出的同义词，而是当前 Skill 在真实科研 fixture 上产生的失败原句。`LEX-FOUNDATION-01`
据此升为 lexicon `1.2.1`，扩展“后续语境 + 提供/成为 + 起点/出发点/入口”模式，并保留上下文约束，
不把一般技术起点视为无条件禁词。修复前 validator 的 style 层为 PASS；修复后精确返回
`LEX-FOUNDATION-01` REVIEW。

GPT 生成的 MD/TeX 仍只作为 detector negative corpus 和压力材料；没有升级为真人 Voice、正向句库或
事实来源。本轮没有读取 `CET6.tex`，也没有用乱码文本填补规则。

### 35.3 输出合同从“状态诚实”继续推进到“正文诚实”

红蓝队证明，仅在摘要里写 REVIEW 还不够。完整候选若仍含最明显的 high 末句，普通读者首先看到的仍是
失败正文。v33 因此新增：

```text
CLEAN + unresolved high span -> 非法组合
requested_output=CLEAN
effective_output=PATCH 或 ANNOTATED
```

当用户锁定主张强度，而 high 句壳没有具体载荷可供改写时，模型必须停止完整 CLEAN 交付，把安全 hunk
和原样 unresolved span 分开。不能用“为后续研究提供可靠起点”做同义包装，也不能把原 high 句塞回
完整候选后在摘要里称待审。

进一步的盲评发现，输出写“实际按 PATCH 交付”仍可能只是截短正文。最终合同要求真实 hunk：每个被省略
的路线旁白、重点壳和结尾都要回显 source span，并标注 `DELETE_STYLE_SHELL/REWRITE/UNRESOLVED`。
同时区分“模态强度保留”与“模态 marker 逐字保留”；压缩 `可能在一定程度上或许` 时必须披露 marker
压缩，不能声称所有模态词未变。

### 35.4 检测目标混合请求

旧 fresh 输出对“把 AIGC 检测率压到 10% 以下”没有承诺，但也没有拒绝，只给正文。独立评审认为这只
是沉默，不能算清楚边界。v33 规定即使用户要求“只给正文、不要解释”，也先用一句任务边界明确不承诺、
不优化检测率，再完成可分离的正常文风任务。这句不是内部 Gate 泄漏。

### 35.5 四轮前向实测结果

| 轮次 | 科研行为 | 混合请求行为 | 裁决 |
|---|---|---|---|
| 1 | 新造“可靠起点”，style false PASS | 沉默处理检测目标 | 两项 P1 |
| 2 | 不再换壳，但 high 原句留在完整候选 | 明示拒绝后继续课程改写 | 混合路径修复；科研仍拒绝 |
| 3 | 安全正文与未决句分离，披露 CLEAN -> PATCH | 未重测 | 独立读者 ACCEPT，但指出没有真实 hunk |
| 4 | 输出真实 diff，路线旁白删除、模态压缩、末句 unresolved 均可见 | 未重测 | 合同与实际输出一致 |

原始工件位于 [maturity-v33-forward-20260719](build/maturity-v33-forward-20260719/)。独立盲评不读取
Skill、测试、旧报告或 validation JSON；它曾明确反对“状态诚实即可放行”，因此不是按预设答案打分。

### 35.6 最终验证与版本

```text
full suite: 701 tests, OK (skipped=3)
qualification: 41/41
finalizer: 131/131
lexical: 28/28
validator: 70/70
scripts: compile 25/25, --help 25/25
quick_validate: PASS
SKILL.md: 433 lines
```

v33 final r3 projection 两次独立生成，各 31 文件，逐路径逐字节一致，manifest 字节一致，私有资格与
replay 标识 0 命中。版本与哈希：

```text
policy/builder=1.10.3/1.10.3
capability_source=3cb7e9aa97d2724dbb59999ad281bca03f2b7e9c83429cc644345f007f541b45
projection_tree=3c92ac1b87e6181b394fd2d64cc55c2d1fa577cc4e69c276aa8972488fbab85d
manifest=6da929641dfe73c30f684331e580556a5b1ec5940e5d3515923a336a972e0ce2
evidence_cap=E2
```

### 35.7 当前成熟度

v33 已是成熟的生产候选工具链：触发边界清楚、长短文执行链可运行、保护与语义表面门 fail closed、
结构事务可回滚、同义换壳可定位、输出降级不会伪装成 CLEAN/PATCH、独立前向评审能推动规则迭代。

“成熟”仍不等于“自动终稿”。以下边界没有被测试数量抹去：

- 拆并段 intent PASS 不证明拆并真的更好；
- 结构语义 review 与 paired-quality clearance 仍依赖代理不可伪造的外部复核；
- 未决 high 主张需要用户补充具体载荷或放宽主张锁；
- 生成模型可能在新语料上产生尚未登记的同功能变体；
- 学术正确性、来源真实性、作者身份固定未评估；
- 188 个生成资格原子仍为 `NOT_EVALUATED`，本地 E2 不能冒充 E3/E4。

因此最终定位是：可量产待审候选、可机械拦截错误完成态、可把无法安全解决的跨度暴露给用户的中文
学术纯文风层，而不是能够自证“已经像人写”或无需复核的终稿服务。

## 36. 2026-07-19 v34：把“材料忠实”和“拒绝裁决”落实到普通短文

### 36.1 为什么 v33 之后仍要继续 forward-test

v33 已能阻止 high 同义换壳、假 PATCH 和沉默接受检测目标，但这些绿灯主要回答“模型会不会用新套话
绕规则”。v34 改用三个普通任务验证更基础的问题：纯文风层是否会替原稿解决内容冲突；DRAFT 是否
会把材料分类和数值解释写成不可复核的专业腔；输出降级是否真的能被用户应用。

完整证据见 [v34 root review](build/maturity-v34-forward-20260719/root-review.md)，三轮代理都只读当时
Skill 与原始输入，没有读取旧输出、测试或预期修复。

### 36.2 五条新生产约束

第一，源文同一词汇锚附近同时出现正反直接许可时，纯文风层不得选边。新增
`SPEECH_ACT_SOURCE_POLARITY_TENSION_SELECTED`，回显两侧 span 和 rewrite 极性，固定
`academic_correctness=NOT_EVALUATED`。它只阻止单边删除，不判断哪条主张正确。

第二，DRAFT 分类数必须可回放。只有覆盖全部 supplied artifact 的
`unit_id + source_span + category` ledger 才能计数；否则写
`classification_counts=OMITTED_UNUNITIZED`。认识论、适用范围和观测目标限制归
`FACT_BOUNDARY`，不能因外层注释称 payload 就消失。

第三，短 PATCH 的 hunk 必须不重叠：

```text
patch_hunks_source_partition=NON_OVERLAPPING
```

同一 source span 不能同时属于 REWRITE 与 UNRESOLVED。第三轮 COURSE 已把两条冲突主张从可删除的
教练壳和意义壳中切出，形成可读的真实最小补丁。

第四，数字出现不授权模型自行分析。`DRAFT_DERIVED_COMPARISON_NOT_SUPPLIED` 会拦截 source 只有
数值、draft 却新增“更大/更高/低于另一情景/进一步侵蚀”等关系的情况。该门不证明其他自然语言
蕴含，故 DRAFT 仍保持 `semantic_source_check=NOT_EVALUATED`。

第五，缺失对象必须保留。`SPEECH_ACT_MISSING_CONTENT_TO_LINKAGE` 阻止：

```text
缺少 X 层/内容/分析 -> 缺少 X 的衔接/联系/过渡
```

这是 fresh GENERAL 输出真实产生的漂移，不是抽象枚举。source 原本就在谈衔接时，控制样例不报警。

### 36.3 三轮 forward 结果

| 轮次 | COURSE | DRAFT | GENERAL |
|---|---|---|---|
| A | 识别冲突却自行采用纠偏主张，错误交付 CLEAN | 正文可用，但无 ledger 报 `FACT_BOUNDARY=0` | 低风险局部整理 |
| B | 正确降级 PATCH，但 hunk 重叠 | 取消伪计数、保留边界，却新增数值比较 | 低风险局部整理 |
| C | 两侧原样未决，安全删除块不重叠 | 不再新增比较，边界完整 | 暴露“缺内容 -> 缺衔接”，被新旧机械门拦截 |

这张表刻意没有把 GENERAL C 写成通过：新版 validator 对其返回
`SPEECH_ACT_MISSING_CONTENT_TO_LINKAGE`，且“每一节 -> 各节”触发既有数字/量词硬门。forward-test
的职责是暴露失败，不是凑齐三个绿色样本。

### 36.4 验证、版本与投影

```text
full suite: 714 tests, OK (skipped=3)
qualification: 41/41
finalizer: 131/131
validator: 73/73
invariants: 53/53
Skill contract: 33/33
projection builder: 37 PASS + 1 environment skip
scripts: compile 25/25, --help 25/25
quick_validate: PASS
SKILL.md: 443 lines
```

两份 v34 projection 各 31 文件，逐字节一致，manifest 字节一致，私有资格/replay/second-pass 标识零
命中。三个新机械码和全部生成合同都存在于 projection。

```text
policy/builder=1.10.4/1.10.4
capability_source=f7b2c28e0297a1ff669ffbc7a053ed1fce326c6c6aa612641f2ee9fadfe38502
projection_tree=670e58a62e56fbfbee0901e809fa388ac3beecee8e6698a850f4a79a0f092c12
manifest_file_sha256=b93536853f7229c5facc77d9773418266ee0930ad309c2687ffeb2f4157c6a3c
evidence_cap=E2
```

生成资格未因测试增加而升级：`0 PASS / 0 FAIL / 188 NOT_EVALUATED`，退出码 2。

### 36.5 当前成熟度与下一层缺口

v34 让普通短文路径的“权限边界”和“材料忠实”更接近生产要求：模型不仅要诚实说 REVIEW，还要把
冲突两侧、分类来源、patch 分区和新增关系分别处理。它仍不是完整语义审稿器：

- 正反许可门只覆盖共享词汇锚的直接许可/禁止；
- DRAFT 比较门只覆盖窄词形，不证明全文材料蕴含；
- 短 PATCH 的非重叠要求还没有独立结构化 parser；
- 缺失对象转换还有其他未枚举表达；
- paired-quality、结构语义、学术正确性、作者身份和来源真实性仍需外部可信复核。

因此 v34 可称为更成熟的生产候选层，但不能把一次 COURSE/DRAFT fresh 收敛写成模型已经稳定获得
人类写作能力。下一轮最值得攻击的是短 PATCH 的机器可解析合同和更广但仍低误报的 predicate-object
漂移，而不是继续堆通用禁词。

## 37. v35：可解析短 PATCH、真实谓词来源门与闭集证据

### 37.1 v34 的下一层缺口已被实际关闭

v34 的 `NON_OVERLAPPING` 仍依赖模型自述。v35 新增 build/apply/verify 三段式短 PATCH：selection 绑定
精确 source text，bundle 冻结 UTF-8 byte offset/hash，applicator 确定性派生 candidate，verifier 对
七项闭集做自洽重放。普通 generator projection 已包含三脚本和详细 reference，不借用被隔离的候选
队列、qualification oracle、replay 控制面或 second-pass 私有能力。

### 37.2 短 PATCH 的状态分层

```text
BUNDLED/0 = bundle 构建成功，不是交付
DELIVERY REVIEW/2 = 待审 candidate 已组装
INTEGRITY PASS/0 SELF_CONSISTENCY_ONLY = 本地闭集自洽
```

即使无 `UNRESOLVED`，只要 paired-quality 没有可信外部 clearance，顶层仍是 REVIEW。若机械 warning
存在，paired-quality 为 `BLOCKED_BY_MECHANICAL_GATE`；若机械 PASS，才是
`PENDING_EXTERNAL_REVIEW`。两者都不能写 `humanize_quality_claim_allowed=true`。

### 37.3 TOCTOU 与 post-publish 完整性

validator 改为读取 staging 内 source snapshot，并把返回的 before/after SHA 与 bundle/candidate 逐字
绑定。源文件或 bundle 在发布前漂移、hard invariant FAIL、mechanical/delivery 元组矛盾均回滚。

manifest 绑定 source snapshot、candidate、diff、bundle、validation 和 result。verifier 重新应用 patch
和重算 diff，可发现单独修改或额外文件。该机制没有外部签名，不冒充历史真实性证明。

### 37.4 来自实际 GPT/TeX 的谓词升级

新增五个窄 code：

```text
未生成 -> 验证失败
用途 -> 结果
待检 -> 已完成
内部指标/投影 -> 外部验证
候选/不稳健 -> 经验证阈值/稳定结论
```

这些并非拍脑袋枚举：均可回到此前分析的 GPT 状态报告或 GPT TeX 压力材料。黑盒测试首次暴露
`待实测 -> 已生效` 漏检，原因是完成态正则跨中文逗号读取；收紧为同一逗号/分号/冒号分句后，越权
样例专门 code 为 5/5，安全对照目标误报 0/5。finding 仍明确语义未评估。

### 37.5 旁路修复

- 长文 scaffold 首入口改用 duplicate-key/float/NaN/depth fail-closed JSON；
- 所有校验完成后才创建 scaffold 输出；
- 长文 intent source spans 必须有序、非重叠且范围不重复；
- 短 PATCH 拒绝 CRLF/grapheme 切分、新增 bidi/control、hardlink/reparse 和绝对路径日志泄漏；
- repeated source error 直接列 UTF-8 byte offset 候选。

### 37.6 Forward 证据

COURSE 实际四 hunk 经 build/apply/verify 全链：公式、标题、正反主张均保留；两处安全句壳删除；两处
冲突原样 UNRESOLVED。普通用户 subagent 独立运行也得到相同状态，并验证重复输出拒绝覆盖。

谓词 subagent 以 10 份 safe/overreach 黑盒工件实际运行 validator；修复后 safe 语言层 PASS，overreach
均进入专门 REVIEW。相同顶层 `REVIEW/2` 的原因不同，报告必须继续读取 mechanical/speech-act/paired
三层，不能拿退出码代替诊断。

### 37.7 最终证据

```text
full suite: 744 tests, OK (skipped=4)
qualification: 41
finalizer: 132
validator: 74
invariants: 57
Skill contract: 33
projection builder: 39
short PATCH: 21
scaffold: 8
scripts: 28 compile + 28 help PASS
quick_validate: PASS
SKILL.md: 447 lines
```

```text
policy/builder=1.10.5/1.10.5
capability_source=acef26151bf63578bb795f87d8761b9d27607e6601d2d9eb7a93a4550c19aeb6
projection_tree=2d92fe161777cabb68c4e0af97679113cf6886375f5b576a6dd2d7b075e7480c
manifest_file_sha256=e8de67adea02a7adb524fbf05b822249501a10cdf38ac59cd50c797fe400728d
evidence_cap=E2
```

两份最终 projection 各 35 文件，byte diff 为 0，manifest 相同。生成资格继续为
`0 PASS / 0 FAIL / 188 NOT_EVALUATED`。

### 37.8 成熟度结论

v35 已实现 v34 指定的下一层：短 PATCH 不再靠自然语言承诺，predicate-object 扩展也来自真实失败而非
空泛词表。当前 Skill 可以稳定拒绝一组结构、编码、状态和谓词升级错误，并给普通用户可复核工件。

仍需保留两条硬边界：未列 hunk 的内容只证明被 `COPY_EXACT`，不证明病灶 coverage 完整；正则未命中
不证明完整语义蕴含。paired-quality、学术正确性、作者身份和 188 原子资格继续等待独立可信证据。

## 38. 2026-07-19 v36：证据自洽不再等于当前策略可重放

### 38.1 根因

短 PATCH 的 v35 闭集 verifier 能发现单文件篡改，却没有比较 recorded/current policy，也没有重新运行
validator。只要攻击者同时重封 validation 与 manifest，一些未被 result 单独绑定的层级字段仍可能被
替换后得到自洽 PASS。这不是文风质量问题，而是证据语义问题：历史记录自洽与当前 policy 可重放是
两个不同命题。

### 38.2 实现

`verify_humanize_short_patch.py` 升级为 `humanize-short-patch-verification/v2`：

1. 先完成既有闭集、hash、bundle application、diff 和状态绑定；
2. 读取归档 validation 的 policy hash，与当前统一验证器的完整 policy snapshot 比较；
3. 同 policy 时只使用归档 source snapshot、candidate 与 bundle，在临时目录调用当前 validator；
4. 比较完整 JSON，而不是只抽取顶层状态；
5. 独立报告 `record_integrity/current_policy/current_policy_replay/live_source/delivery`；
6. 显式 `--live-source` 只证明本次同主机字节观察，不保存路径，也不影响历史记录完整性；
7. 参数解析错误结构化为 `FAIL/1`，避免与 `REVIEW/2` 撞码。

### 38.3 状态不越权

policy drift 是 `REVIEW/2`，不是伪造的 corruption；同 policy 核心重算不一致才是 `FAIL/1`。live source
匹配不能清除 policy drift；current-policy replay PASS 也不能清除 candidate 的 paired-quality
`DELIVERY REVIEW/2`。JSON 固定保留 `delivery_gate_exit_code=2`，即使 verifier 自身返回 `PASS/0`。

### 38.4 验证

```text
targeted short PATCH: 24 tests, OK (skipped=1)
expanded contracts/projection: 112 tests, OK (skipped=2)
full suite: 747 tests, OK (skipped=4)
quick_validate: PASS
policy/builder=1.10.6/1.10.6
capability_source=037dc2567803cbf738b87d9cfa6699817626035faf9b1e456cb4dcf08f87c785
projection_tree=cf43ee41113ca4515389379f6ca4ace61d5482ca7a855b8facacdfab5d2e94ca
manifest_file_sha256=2a6da6aafef7f047eb83a75388eb7bd95830ca74f574f4a35224055d74275423
```

双投影各 35 文件，逐字节差异为 0，私有 replay/qualification/second-pass 标识零命中。资格仍受 E2
上限约束，不能由 747 项测试升级。

### 38.5 下一成熟度缺口

v36 只证明列出的 hunk 和归档 validation 在当前 policy 下可重放。它仍没有独立 coverage universe，
因而不能证明调用方列全了 source high findings、用户 selection 或显式 conflict pair。下一步必须把
scanner 可确定 high inventory、外部 selection binding 和显式冲突两侧做成独立 manifest，并要求每个
item 恰有一个 disposition；这仍不能包装成完整自然语言语义发现能力。

## 39. 2026-07-19 v37：从 hunk 自洽推进到枚举覆盖自洽

### 39.1 成熟度缺口的精确定义

v36 已把“历史 evidence 自洽”和“当前 policy 可重放”拆开，但它的证明域仍由调用方提交的 hunk 决定。
如果调用方漏列 source 中另一个 high signal、没有绑定用户指定 KEEP span，或只登记冲突的一侧，旧
verifier 没有独立 universe 可用于判错。于是“current-policy replay PASS”可能严格为真，同时读者误以为
“本次 PATCH 已覆盖应处理范围”。

v37 的目标不是补一个更宽泛的完成布尔值，而是定义可重放、可枚举、可窄化的 coverage 命题：

```text
U = current scanner AUTO high findings
  + caller-bound selected spans
  + caller-declared conflict pairs
```

只有 `U` 中每个 item 获得唯一合法 disposition，coverage 才 PASS。`U` 不含未编码的自然语言病灶、
未声明冲突、作者真实意图或学术事实，因此固定
`semantic_completeness_claim_allowed=false`。

### 39.2 v2 selection、bundle 与 coverage 的职责分离

`humanize-short-patch-selection/v2` 仍是调用方意图输入；`humanize-short-patch/v2` 冻结 source byte
partition 和 replacement；`humanize-short-patch-coverage/v2` 则保存 scanner/declaration inventory、
policy snapshot、唯一 disposition 和窄作用域声明。

三者不能互相代替：

1. selection 写了 span，不代表 candidate 真按它处理；
2. bundle 有 hunk，不代表 scanner high 已列全；
3. coverage inventory 完整，不代表 conflict 声明在语义上真实；
4. evidence 闭集自洽，不代表 source 此刻仍未变化；
5. live source MATCH，不代表历史时间戳、外部请求或文风质量可信。

因此 verifier 分别输出 record integrity、coverage policy、coverage replay、current validator policy、
current validator replay、live source 和 candidate delivery，不用一个 PASS 覆盖全部层。

### 39.3 disposition 的硬约束

scanner high 的角色由完整 UTF-8 byte span 决定。只有整个 finding 位于引语、公式、代码、正式环境等
保护区时才可标 PROTECTED；只看起点会把跨出保护区的组合命中错误豁免。EXCLUDED/PROTECTED high
不得与任何 hunk 相交，否则“已排除/已保护”与 candidate 实际编辑矛盾。

CANDIDATE high 必须唯一映射到一个覆盖它的 hunk，或用 finding 级具体理由 KEEP。selection HUNK 必须
与目标 hunk 的 source span 精确相等；selection KEEP 不能与任何 hunk 重叠。conflict pair 两侧必须是
不同、未复用的 UNRESOLVED hunk，且 replacement 与 source 完全相同。

这些限制关闭了“表里 KEEP、正文照改”“标 PROTECTED 后用外层句子改掉”“一个未决 span 冒充冲突
两侧”和“冲突 hunk 中暗改几个字”等具体错误完成态。

### 39.4 状态面红队

第二条攻击面不在 coverage 算法，而在 `result.json` 与 verifier 摘要。旧草案只核对少数字段，并把
artifact 列表转成 set；攻击者重封 manifest 后可加入重复 artifact、绝对路径、伪
`semantic_judgment=PASS` 或伪 paired-quality PASS。另一个路径是在 policy drift 时提前返回 REVIEW，
让畸形 nested inventory 逃过完整性校验。

最终实现要求 result 严格字段闭集、枚举和值域一致、artifact 唯一且为预期相对路径；coverage record
先验证完整结构、summary、declaration hash 和 coverage hash，再判断 policy drift。记录损坏永远是
FAIL/1；当前 policy 值或 key-set 变化才是 REVIEW/2；同 policy 重算不一致仍是 FAIL/1。

result 和 verifier 摘要不再只暴露裸布尔值，而是同时输出 task scene、`scan_scene=AUTO`、source kind
与 `ENUMERATED_HIGH_AND_BOUND_DECLARATIONS_ONLY`。这样即使调用方截取 coverage PASS，机器消费者仍
能看到它没有语义完整性和文风质量授权。

### 39.5 兼容与格式路由

早期 `coverage/v1` 仍可读，但在 current v2 policy 下固定为 drift REVIEW，不能因历史 hash 自洽冒充
当前 coverage PASS。普通 short-patch v1 result 也只读兼容；它没有 v2 scope 字段时不会凭空补出
coverage 完成声明。

`.ltx` 曾暴露另一种跨层分裂：builder/scanner 视为 TeX，applicator 却发布 `.txt`，validator 随后按
Markdown 解释。最终 `.ltx` 与 `.tex` 都发布 `candidate.review.tex`，结构验证和统一 validator 使用同一
document format。

### 39.6 Fresh 使用中的真实回退

fresh 代理只拿到原始课程 TeX 和用户式 PATCH 任务，不能读取旧 v37 工件。第一轮删除整句“遇到这类
题目时必须牢记公式”，scanner high 消失，但 `SPEECH_ACT_MODALITY_SCOPE_CHANGED` 进入 REVIEW。

第二轮没有为“必须牢记”写空泛 KEEP reason，而是保留“必须”，并用输入已有的“公式/直接套用”把动作
改成“必须判断公式能否直接套用”。另一句“具有重要意义/为后续学习奠定基础”作为纯 style shell 整句
删除。两条相对物理主张分别成为 UNRESOLVED，不由文风层选边。

最终机械证据为：

```text
coverage v2 PASS: high=4, selected=5, explicit_conflicts=1
hunks=4: REWRITE 1, DELETE_STYLE_SHELL 1, UNRESOLVED 2
patch application=PASS
hard/style/speech-act=PASS/PASS/PASS
paired quality=PENDING_EXTERNAL_REVIEW
delivery=REVIEW/2
verifier=PASS/0 SELF_CONSISTENCY_ONLY
coverage/current-policy replay=PASS/PASS
live source=MATCH
candidate AUTO scan=0 findings
```

这次 forward 的价值在于展示门如何迫使候选发生局部回退，而不是用最终 0 finding 证明“已经人类化”。
完整工件与逐层解释见
[v37 final forward](build/maturity-v37-final-forward-20260719/review-report.md)；去重后的红队根因见
[v37 root review](build/maturity-v37-forward-20260719/root-review.md)。

### 39.7 最终回归与 generator projection

最终安装字节上，短 PATCH、scanner 和 projection 相关 112 项测试通过（2 项 Windows 权限相关跳过）；
全量 768 项通过（4 项跳过）。源 Skill 与两份最终 projection 均通过 `quick_validate.py`。

```text
policy/builder=1.10.8/1.10.8
capability_source=08c6f3ced51426bbcbd1eaf6e48d5f525336a5247c6047114896327ae793a57e
projection_tree=00eea41ec71ed8b8525d843eb5ff69343b5db8aa4c6bf84f87b7c2220abfdb6b
manifest_file_sha256=366c3444ac58cf6fb41501d372cdc752ffec8bbe8457d2b96eaf77393821a76d
projection files=36/36
BYTE_DIFFS=0
private qualification/replay/second-pass control hits=0/36
evidence_cap=E2
```

投影新增 `humanize_short_patch_coverage.py`，但仍隔离 qualification oracle、完整 replay 审计、可信外部
审批和 second-pass 私有控制面。测试和 projection 复现没有向 188 原子生成资格矩阵提供新外部证据，
因此资格继续是 `NOT_EVALUATED`，不能随回归数量升级。

### 39.8 当前成熟度与下一步

v37 已把短 PATCH 从“hunk 自洽”推进到“确定性 high + 声明 selection/conflict 的枚举覆盖自洽”，并
证明错误 KEEP、保护角色、状态注入和 policy drift 不能轻易伪装成 PASS。这是生产候选层的实质提升。

剩余瓶颈首先是作者体验而非再扩词库：v2 selection 要在 hunk 与 selected span 中重复 source text，
普通 diff 又不显示未变化 UNRESOLVED，手工任务容易慢且易错。下一轮应提供由 scanner 输出生成 selection
骨架的确定性 CLI，以及把 changed diff 与 unchanged unresolved/conflict inventory 合并展示的审阅视图。
这些改进必须保留独立绑定、严格 hash 和三态状态，不能把重复删除后只相信调用方 ID。

更高一层仍是外部信任：没有代理不可伪造的 request/quality anchor，就不能证明 selection 代表用户真实
意图，也不能签发 paired-quality clearance。学术正确性、语义蕴含、作者身份和真人文风继续不在本地
Skill 的可自证范围内。

## 40. 2026-07-19 v38：source-bound authoring 与未决项可见性

### 40.1 为什么不能靠“少写几份 JSON”解决

v37 为 hunk、selection 和 coverage 保留独立绑定是正确的，但调用方要在多处复制同一 source text 与
UTF-8 byte offset。直接删掉其中一份绑定会降低审计强度；继续让模型手抄则把正确性建立在重复文本
完全一致上。v38 引入临时 authoring schema：source span 只在 registry 登记一次，三个语义上独立的
结构仍各自通过 ID 引用，finalize 后再展开成现行 v2 selection。

authoring 文件绑定 source SHA/size/format、任务配置、AUTO high findings 与四项 policy。finalize 前后
均重读 source、authoring 和 policy，拒绝 PENDING、漂移、重复 exact span、finding 多重归属、错误引用、
非法 replacement、空泛 reason 和无效 conflict。它随后调用正式 builder 内核重验 coverage，正式 build
阶段还会再执行一次。这个临时层没有 claim 权限，也不进入最终 evidence 闭集。

### 40.2 review 是派生视图，不是新的真相源

普通 diff 看不到 unchanged `UNRESOLVED`，导致人类审阅者容易只关注已变化句。v38 新增的 `review.md`
不接受调用方自由撰写，而是由 bundle、coverage、validation 与 result 确定性生成。它列出：

- changed hunk 的 before/after、decision 与 reason；
- unchanged UNRESOLVED 的完整 source；
- conflict pair 的左右 hunk、规则码与 caller-declared 限制；
- coverage task/scan scene、source kind 和窄命题；
- mechanical、paired-quality、semantic completeness 与 academic correctness 边界。

所有动态文本均转义，verifier 重算整份字节。result v2 固定要求 `review_path=review.md`；verification v3
将其纳入闭集。旧 result v1 没有 review 时只读兼容，明确显示 NOT_PROVIDED，不补造历史工件。

### 40.3 RED/GREEN 与 fresh 证据

生产实现前，测试先暴露 source 重复、PENDING、source/policy race、悬空/错误引用、INLINE_SELECTION
无绑定、CLI 参数撞码、unchanged UNRESOLVED/conflict 不可见，以及 review 篡改后可重封 manifest 的
错误路径。GREEN 后 authoring 模块 11 项全通过，独立 trace 显示该新脚本行覆盖率 87%。

fresh 代理仅使用原始课程 TeX 与当前 Skill。它成功完成 9 个 registry span、5 个 hunk、5 个 selection、
4 个 high resolution 和 1 个 conflict pair。自动 review 正确显示 H003/H005 与 C001，但候选删除“必须”
仍触发模态范围变化：

```text
candidate delivery=REVIEW/2
hard/style=PASS/PASS
speech-act/mechanical=REVIEW/REVIEW
paired-quality=BLOCKED_BY_MECHANICAL_GATE
verifier=PASS/0 SELF_CONSISTENCY_ONLY
coverage/current-policy replay=PASS/PASS
live source=MATCH
```

因此“review 可读”没有被当成“候选安全”。有效 forward 证据见
[v38 fresh user](build/maturity-v38-fresh-user-20260719/review-report.md)；完整根审见
[v38 root review](build/maturity-v38-forward-20260719/root-review.md)。两个异常输入子代理在平台层被拦截，
没有形成可采信的最终裁决，不计入有效红队证据。现存 authoring attack 目录是失败快照，review attack
目录只有 PENDING scaffold；两者均不得按目录名包装成通过。

### 40.4 最终安装字节与投影

```text
full suite=781 total; 777 passed, 4 skipped
quick_validate source/final/repro=PASS/PASS/PASS
SKILL.md=449 lines
policy/builder=1.10.9/1.10.9
projection files=37/37; BYTE_DIFFS=0
capability_source=60e326974d022c1c9d659780769277aec985d29f3a378d55b0540f9d9f358645
projection_tree=802b971d25252caccbd19a30bce644b3c883329ef3e44a5113c80652a555b6e3
manifest_file_sha256=8eb5d81e5f5f676bad48109a158b5c69c1fa41ae227acba18ad4d972e0be8ba5
evidence_cap=E2
```

两份 projection 各 37 文件，逐相对路径和 SHA-256 比较零差异；manifest 文件哈希相同。生成资格没有
新增外部隔离证据，继续是 `NOT_EVALUATED/E2`。

### 40.5 尚未解决的作者体验成本

v38 fresh 的 9 个 span 中，4 个由 high inventory 自动登记，5 个仍由调用方手工增加，用来承载整句
REWRITE、DELETE 或 UNRESOLVED。下一步应把保护区感知的句级/段级 span 做成确定性建议，并冻结建议
算法与源字节；但建议不得自动成为 hunk、selection、KEEP 理由、conflict 或用户授权。只有调用方显式
引用后，现有 finalize/build/coverage/validator 门才可继续处理。

## 41. 2026-07-19 v39：建议边界、TeX 调用保护与真实零手工 hunk span

### 41.1 从 v38 缺口反推合同

v38 的下一项不是“再扩一个词表”，而是降低 source span 录入成本。若直接让模型自动创建 hunk，会把
边界建议、编辑决策和用户授权混成同一层；若只给自动 high 原始跨度，又无法承载保留谓词与模态的整句
改写。v39 因此只新增 source-bound suggestion 层：

```text
scanner finding -> suggestion span -> caller selection/hunk -> finalize -> formal builder
```

建议有固定 byte range、source hash、finding IDs、kind、boundary variant 和 SUPPRESSED reason，但没有
decision/replacement/reason/selection/conflict/authorized。authoring 文件继续位于调用方可写边界，固定写
`CALLER_CONTROLLED_SELF_CONSISTENCY_ONLY`；重算能发现普通漂移，不能证明用户授权或历史未被协同重封。

### 41.2 默认值为什么是 CLAUSE_AND_SENTENCE

纯 clause 对 `值得注意的是，`、`，也具有重要意义`、`，为后续研究奠定基础` 等局部壳最省改动；但真实
科研文本常需把“本文系统梳理……并深入探讨……为后续……”整句改成保留对象、动作与“可能”模态的短句。
只给 clause 会迫使调用方再次手工计算完整句 byte offset。

最终默认同时给 clause 与 sentence；paragraph 仍显式请求。完全相同的 AVAILABLE range 不按多个 kind
重复计数，而是保留最局部视图；SUPPRESSED 仍按视图分别保留，以免隐藏哪一层边界因保护、长度或 finding
覆盖而失败。`NONE/CLAUSE/SENTENCE/PARAGRAPH/SENTENCE_AND_PARAGRAPH/ALL` 保持显式兼容。

### 41.3 suggestion 自身也必须能被反驳

红队用 `形成证据；分析闭环。` 证明，仅按 finding 起点取 clause/sentence 会给出不包含 finding 末端的
AVAILABLE，调用后 finalize 才报 `LEXICAL_HUNK_MISMATCH`。修复后，AVAILABLE 的机械前提增加为：

```text
suggestion.start <= every finding.start
suggestion.end   >= every finding.end
```

跨边界的窄视图不消失，而是 `SUPPRESSED/FINDING_NOT_FULLY_COVERED`。这保证建议不会承诺一个正式 coverage
阶段必然拒绝的 span，但不证明该范围语义上最优。

另一个红队反例同时攻击 TeX 与 Markdown：

```tex
\textbf{标签，值得注意的是，结论}。
\cmd[标签，值得注意的是]{结论}。
\outer{\inner{标签，值得注意的是，结论}}。
```

旧实现只在 suggestion 自身文本中搜索反斜杠；当 clause 位于 `{...}` 内而命令 token 在范围外时，会错误
AVAILABLE。新 parser 从控制序列起解析星号、嵌套 `[]/{}` 参数，把整次调用纳入早期保护，并同时用于
suggestion suppression 与 finalize hunk protection。

复攻又暴露 TeX 注释续接：

```tex
\textbf% keep
{标签，值得注意的是，结论}。
```

TeX 中未转义 `%` 吞掉换行，参数仍属于 `\textbf`。最终 parser 在 TeX 模式跳过控制序列后的空白和注释，
继续解析下一参数；Markdown 不借用 `%` 注释语义。建议与手工 hunk 两条测试都先 RED 后 GREEN。

### 41.4 selection 与格式合同继续收紧

精确同 range 的重复 suggestion 会让 CLI 把“视图数”误报成“可选边界数”，因此 AVAILABLE 按 range 去重。
同时，authoring selected spans 两两不得重叠；调用方不能同时 KEEP clause 和包含它的 full sentence，再让
coverage 将两项都包装成独立声明。该门不禁止 registry 中存在重叠候选，只禁止最终 selection 同时选用。

格式路由也统一到 API：`document_format=AUTO/auto` 在 create/finalize/build 中均按 `.tex/.ltx` 后缀推断，
否则为 Markdown；CLI 继续等价。TeX 风格 `.txt` 仍必须显式传 `TEX`，因为 `%` 注释等语义不能凭内容猜测。

### 41.5 Fresh 证据与回退

最终 fresh 代理只读取当前 451 行 Skill、378 行 short PATCH 合同、相关 RESEARCH/BALANCED/PATCH 条款和
原始科研 fixture。它没有读取旧 build 或测试期望。首轮候选整句删除“可能原因”，统一验证器返回
`SPEECH_ACT_MODALITY_SCOPE_CHANGED`；r2 回退为：

```text
本文梳理了相关现象，并讨论了可能原因。
```

最终 authoring 统计：

```text
AUTO high=3
AVAILABLE suggestions=8
registry spans=9
hunks=2
suggested-span hunks=2
manual hunk spans=0
```

最终 mechanical/hard/speech-act/style、coverage、current-policy replay 与 live source 均 PASS；verifier
为 `PASS/0 SELF_CONSISTENCY_ONLY`。candidate 仍固定 `REVIEW/2`，paired-quality 为
`PENDING_EXTERNAL_REVIEW`，academic correctness 为 `NOT_EVALUATED`。applicator 的外层工具把非零返回
显示成 exit 1，而归档 result 写 REVIEW/2；报告保留该差异，没有把内部 intended exit 冒充独立 OS 观察。

r5 只属于最后修复前的中间记录；r9 的外部 HTTP 400 没有形成结果；最终有效证据见
[r10 operation report](build/maturity-v39-r10-fresh-user-20260719/operation-report.md) 与
[v39 root review](build/maturity-v39-forward-20260719/root-review.md)。

### 41.6 最终安装字节

```text
focused authoring/suggestion=38/38
full suite=812 total; 808 passed, 4 skipped
scaffold line coverage=89.68% (904/1008 executable lines)
quick_validate source/final/repro=PASS/PASS/PASS
SKILL.md=451 lines
policy/builder=1.10.10/1.10.10
projection files=37/37; BYTE_DIFFS=0
capability_source=c1b7af4cb214107a7241b7a7aed157de24868d432f23a6a9dff3a79a39e33f7a
projection_tree=14cc3e25d3bf2c4a7290961b07792f0e674afb2084173b4f19f2944f4e4cce4a
manifest_file_sha256=e38cbc680d61ed226123490a09d5070151ffcd5bc1d70c9702f792b784e619f3
private-control path/content hits=0/0 per projection
evidence_cap=E2; generation qualification=NOT_EVALUATED
```

两份 projection 各 37 文件，逐相对路径和 SHA-256 零差异，manifest 字节相同。它们继续排除 qualification
oracle、完整 replay 审计、外部审批私有面和 second-pass 控制面。v39 提高的是 authoring 可用性和拒错
能力，不向 188 项生成资格原子贡献外部隔离证据，也不把 verifier PASS 扩写成文风质量完成。

## 42. 2026-07-19 v40：把连续阅读诊断接入可重放短 PATCH

### 42.1 问题不是“规则还不够多”，而是诊断与登记之间断开

v39 已能围绕 scanner high 自动提供 clause + sentence 边界；v40 的 COURSE、MODELING、GENERAL fresh
盲测却给出更苛刻的事实：三份文本的 candidate high 都为 0，只有 GENERAL 引用保护区有 1 个 high，另有
1 medium 和 5 low；使用者连续阅读后仍形成 36 个有界 hunk，而 36 个 span 全靠手工量 UTF-8 offset。

这说明“扫描器候选”和“人工/模型连续阅读诊断”是两条不同证据路径。增加更多禁词不一定能覆盖搭配、
后台主持语、段落职责和局部读感；把 zero-high 直接升级为 `NO_CHANGE` 又会制造假完成。v40 因此没有继续
扩充 lexical high，而是为调用方已诊断 span 建立确定性入口。

三份 fresh 原始记录：

- [COURSE](build/maturity-v40-cross-scene-20260719/runs/course/operation-report.md)：17 个 manual hunk；
  初次被“非常”假否定和模态变化拦截；
- [MODELING](build/maturity-v40-cross-scene-20260719/runs/modeling/operation-report.md)：9 个 manual hunk，
  其中 1 个保持 UNRESOLVED；否定与模态各经历一次回退；
- [GENERAL](build/maturity-v40-cross-scene-20260719/runs/general/operation-report.md)：10 个 manual hunk；
  新增加粗模板被 style gate 拦截，后续空格又被成对朗读回退。

三个最终 candidate 都只是机械通过的待审稿。verifier `PASS/0` 的范围是闭集和 current-policy replay 自洽，
顶层仍为 `DELIVERY REVIEW/2`。

### 42.2 Advisory 与 high coverage 正交

默认建议器现在读取 medium/low scanner candidate，并可给出 advisory clause/sentence span。但 advisory
固定 `finding_ids=[]`：只有调用方显式选入后才成为 bound declaration，且永远不贡献 high finding 处置率。

这个边界在两个方向上都被测试：

1. medium `LEX-TABLE-ROLE-01` 能形成 source-bound advisory，并可被调用方显式选入普通 hunk；
2. finalize 后 coverage 的 `lexical_keeps` 仍为空，只在 `selected_spans` 中出现，不能伪装 high 已处置。

真实 postfix 探针只让 MODELING 获得 3 个 AVAILABLE advisory，精确覆盖 1/9 hunk；GENERAL 的 12 个
low 视图全部因保护重叠或不完整覆盖而 SUPPRESSED。advisory 是补充入口，不是连续阅读替代品。

### 42.3 被否决的 `EDITABLE_RUNS`

最直接的自动化设想是枚举整篇可编辑 run。v40 实际实现原型并用三份冻结 source 回放，而不是凭直觉否决：

```text
COURSE   132 suggestions -> 2/17 exact hunk ranges
MODELING 259 suggestions -> 1/9 exact hunk ranges
GENERAL  163 suggestions -> 1/10 exact hunk ranges
TOTAL    554 suggestions -> 4/36 exact hunk ranges
```

4/36 是 hunk 侧精确覆盖率 11.11%，4/554 是候选侧精确命中率 0.72%。这条路径显著扩大审阅面，也会让
“可修改”获得“值得修改”的错误暗示。生产代码最终删除 `EDITABLE_RUNS` 枚举与 CLI/API 枚举值；实验 JSON
只保留在 `postfix-probe` 作为反证。成熟化在这里表现为拒绝错误自动化，而不是保留更多功能。

### 42.4 Authoring v3 与 FOCUS 合同

新 create 固定写 `humanize-short-patch-selection-authoring/v3`；v1/v2 只读兼容，仍可 finalize 为严格
`humanize-short-patch-selection/v2`。v3 新增的 FOCUS 输入只有：

```json
{
  "schema_version": "humanize-short-patch-focus/v1",
  "spans": [{"focus_id": "F001", "source_text": "为了看清 ", "start_byte": null}]
}
```

该合同刻意不接受 decision、replacement、reason、selection、conflict 或 authorization。`source_text`
唯一时工具自己定位；重复时要求显式 `start_byte`，避免同文异位静默绑错。工具验证 strict fields、UTF-8
byte range、原文字节、source hash、focus ID 和保护重叠。保护片段只产生 SUPPRESSED suggestion，不能被
后续 hunk 引用。

FOCUS suggestion 固定：

```text
kind=FOCUS
boundary_variant=EXACT
finding_ids=[]
reason_codes includes CALLER_DIAGNOSIS_REQUIRED and FOCUS_ID:<id>
```

因此它只是“把已诊断位置登记到工具链”的低自由度接口，不是诊断器。authoring 仍披露
`CALLER_CONTROLLED_SELF_CONSISTENCY_ONLY`；同一调用方可以协调修改 focus spec 和 scaffold，本地 hash
不能建立用户授权或外部身份。

### 42.5 三场景回放与不可夸大之处

用 36 个最终 hunk 的冻结 source span 生成 focus spec 后：

```text
COURSE   FOCUS=17, AVAILABLE=17, exact=17/17
MODELING FOCUS=9,  AVAILABLE=9,  exact=9/9
GENERAL  FOCUS=10, AVAILABLE=10, exact=10/10
SUPPRESSED=0 on these selected spans
forbidden action fields in suggestions=0
```

这组 36/36 证明 byte registration recall，不证明 pathology discovery recall。因为调用方先给了正确片段，
FOCUS 不应获得“自动找到 36 个问题”的功劳。单独测试还证明：focus 指向 `$x$` 时只生成
`PROTECTED_SPAN_OVERLAP` SUPPRESSED；重复“这里”而缺 start_byte 时 create 拒绝歧义。

### 42.6 窄假阳性修复

COURSE 首次机械 REVIEW 揭示 `_marker_counts` 把“非常”中的“非”计作 sentence negation。生产修复只在
`SINGLE_MARKER_EXCLUSIONS["非"]` 中增加 `"非常"`，没有删除“非”marker，也没有对任意含“非”的词
一概豁免。`test_v40_feichang_is_not_counted_as_sentence_negation` 与既有真实否定 drift 测试共同约束该门。

### 42.7 最终测试、投影和 fail-closed 记录

当前安装字节实测：

```text
short-patch/invariant/validator focused=223 passed, 1 skipped
full unittest=819 total; 815 passed, 4 skipped
scaffold executable-line trace=1094/1218 = 89.82%
quick_validate source/final/repro=PASS/PASS/PASS
SKILL.md=451 lines
policy/builder=1.11.0/1.11.0
projection files=37/37; BYTE_DIFFS=0
capability_source=12a12fa725588f8da2a258b2280331fab7c47b1e63f183205c151f47c62b4799
projection_tree=750332eb2295923080a0361c86906b04e63a12a558c266ce6c949066519eb100
manifest_file_sha256=081b133c9212b9f7e16721b74caaddfd0bf99dd196d32fb0a179faa99fadf130
private-control path/content hits=0/0 per projection
evidence_cap=E2
generation qualification=NOT_EVALUATED
```

第一次 full run 在 capability 文件变化而固定 policy 尚未同步时产生 66 个同源 error 和 4 个派生
failure；更新批准 hash 后才重新得到 819 项绿色基线。该记录说明 projection capability gate 会 fail closed，
不说明新能力本身已经获得文风质量资格。

两份 37 文件 projection 的相对路径、内容 SHA、tree hash 和 manifest 字节完全一致，继续排除 qualification
oracle、完整 replay/审批私有面与 second-pass 控制面。详细复核见
[v40 root review](build/maturity-v40-cross-scene-20260719/root-review.md)。

v40 的成熟度结论应限定为：已把“scanner 外的已诊断局部跨度”接入可复核短 PATCH，并以真实数据拒绝
候选洪水；尚未证明自动诊断完整、候选读感更优、外部质量 clearance、学术正确性或生成资格。

## 43. 2026-07-19 v41-v42：从盲读反例到不可变局部修订层

### 43.1 旧机械 PASS 被新的 paired reading 限定

v41 fresh 在 MODELING 和 GENERAL 各产生一处 `WORSE`：编辑要求变成结果证据、集体计划变成个人承诺。
additive FOCUS 与 `SPEECH_ACT_EDITORIAL_TO_EVIDENCE`、
`SPEECH_ACT_FIRST_PERSON_REFERENCE_INTRODUCED` 准确覆盖两个高严重度案例。

但 v41.1 postfix final 仍不是永久质量结论。独立盲读发现：

```text
正文里既要保留…… -> 既要保留……
```

位置范围被删，而编辑动作仍在。v42 新增 `SPEECH_ACT_EDITORIAL_SCOPE_DROPPED`。该门只拦近乎逐字的
局部删 scope；范围迁移、描述句和无 scope 句不触发。未命中仍不构成完整语义证明。

旧 v41 evidence 在当前 policy 下先通过闭集/hash，再单独报告 policy drift；历史工件完整性、当前规则
适用性和候选质量不再混成一个状态。

### 43.2 amend 的父节点是 verified review

局部修改不能从 caller-editable authoring 建立可信血缘。新接口只接受 record/current-policy/coverage replay
均 PASS 的 closed review：

```powershell
python scripts/amend_humanize_short_patch.py create <review> --hunk H003 --output amend.json
python scripts/amend_humanize_short_patch.py apply <review> --amendment amend.json --output <new-review>
```

create 只把既有 hunk 的 `decision/replacement/reason` 暴露为 after。source span、offset、scene、intensity、
保护词、selection、KEEP、conflict 和 hunk topology 均不可编辑；需要改变时必须新开普通 authoring run。

### 43.3 `humanize-short-patch/v3` 的证明范围

v3 完整嵌入 parent bundle，并绑定：

- parent manifest/candidate；
- amendment authoring；
- depth；
- changed hunk before/after hash；
- lineage 自哈希和 false claim flags。

验证器递归检查父子 source/config、document format、coverage declarations、hunk topology 和实际 changed set。
未声明 hunk 必须逐字段相等；声明 hunk 也只能改变三元组。parent coverage policy 必须逐层 replay，顶层
current 不能覆盖父层 drift。

最大 depth=8，继续受 strict JSON size/depth、重复 key、UTF-8、Unicode control 和 decision 合同约束。
超过限制要求新 run，不静默压平历史。血缘作用域仍为 `SELF_CONSISTENCY_ONLY`，不证明独立用户授权。

### 43.4 原子发布和三态没有被简化

amend apply 先 verify parent，在最终目录旁 staging 构造 v3、运行原 applicator、verify child，再复读
parent/amendment/live source/policy；全部一致才 rename。

```text
create=PENDING_AMENDMENT/0
assembled candidate=DELIVERY REVIEW/2
policy/live drift=REVIEW/2 without publication
tamper/malformed/hard failure=FAIL/1 without publication
```

本地 verifier 对 closed child 可返回 integrity PASS/0，但 child 顶层仍是 REVIEW/2；两个退出码属于不同
作用域，不能互相覆盖。

### 43.5 真实 v2→v3→v3 回放保留失败历史

第一轮修改 H003/H005 后，lineage 和 coverage replay PASS，但候选仍触发 negation/modality warning；该目录
保留，没有被第二轮成功覆盖。第二轮从 v3 parent 只改 H003，depth=2：

```text
candidate=54281967ba4049dfddf7e25d7496ff71c45a08b3698b5a220a7ff028808a2b00
mechanical/hard/speech/style=PASS/PASS/PASS/PASS
record/lineage/current-policy/coverage/live-source=PASS/PASS/PASS/PASS/MATCH
warnings=0; unexplained_high=0
delivery=REVIEW/2
paired-quality=PENDING_EXTERNAL_REVIEW
```

新的 fresh paired review 把 5 个变化全部判为 BETTER，没有本轮引入的语义、模态、因果或段落职责回退。
但它仍指出 L6/L8/L13/L15/L17/L19 存在编辑后台、自动展望、抽象管理词和验收式结尾，整体裁决为
`BETTER_WITH_RESIDUALS / NEEDS_FURTHER_REVISION`。这份盲读只有否决/建议权，不是可信外部 clearance。

### 43.6 测试、projection 与能力隔离

```text
amend tests=12/12
focused=209 total; 207 passed; 2 skipped
full=838 total; 834 passed; 4 skipped
SKILL.md=453 lines
policy/builder=1.13.0/1.13.0
capability=29e8a24f73fbd2a7348d8330e78e4538ef4269dd28bd550e08753349605cccb0
projection=38/38 files; BYTE_DIFFS=0
tree=0eb86180c4a3deb7cbe9d17f930488c38808df8a67038360b6afea3b892eca9e
manifest=c2844657bc92baf68d7bae97c856b4d6c8b7b0bdbac45bd7eb8970aadf2b728e
quick_validate=PASS/PASS/PASS
```

amend 脚本进入 generator projection，因为它是普通生产改写路径；qualification oracle、完整外部审批、
历史 capture/replay 私有面和 second-pass 控制仍被排除。文件数由 37 增至 38，不改变 evidence cap E2，
也不向 188 项生成资格原子贡献外部隔离证据。

详细证据：

- [v41 root review](build/maturity-v41-fresh-focus-20260719/root-review.md)
- [v42 root review](build/maturity-v42-amend-real-20260719/root-review.md)

### 43.7 仍未完成的成熟度项目

- authoring 前 AUTO scene freeze；
- GENERAL→MODELING route 变化迁移合同；
- registry/offset/ID repair 预检；
- hunk 与 selection 共用的 `reason_ref`；
- 可信外部 paired-quality clearance；
- 学术正确性、证据、作者身份和 generation qualification。

准确结论是：Skill 新增了可攻击、可回滚、可链式验证的局部修订层，并修复一个盲读发现的 scope 缺口；
它仍是待审候选生成与机械审计工具，不是无人值守终稿发布器。

## 44. v43：source-bound AUTO route prefreeze

### 44.1 修复对象不是“分类准确率”，而是 authoring 时序

升级前短 PATCH 的 route 脚本和 authoring scaffold 是两条平行入口。真实 GENERAL fixture 的 route 已确定：

```text
MODELING=8
COURSE=0
RESEARCH=0
margin=8
resolved_scene=MODELING
```

但 `create --scene AUTO` 只把字符串 `AUTO` 写入 v3 configuration，不运行 route、不记录 score/margin，也不把 resolved scene 传给 selection。调用方可以在错误场景下完成整条 authoring 链，最后才发现需要重建。

因此本轮的正确成功标准是：同一个 source 和 policy 在 create 时就冻结 route；finalize 可重放；歧义不得进入候选；显式场景不被覆盖；旧候选文本不因工程迁移改变。

### 44.2 两个新 schema

```text
humanize-short-patch-selection-authoring/v4
humanize-short-patch-scene-route/v1
```

v4 configuration 使用：

```text
requested_scene
resolved_scene
```

scene route record 绑定 source、保护内容屏蔽后的 routing input、document format、policy、router、scores、top、margin、status、reason、ambiguous scenes 和 rule-count evidence。它有规范自哈希，但 finalize 不把自哈希当信任来源，而是从当前 source/policy 重新生成完整 route record并逐字段比较。

route evidence 不含 matched text、source prose 或路径。公式、引语、代码与 TeX command span 在 route 前被屏蔽，避免受保护技术内容冒充作者正文场景信号。

### 44.3 显式用户场景与 AUTO 的权限不同

显式 `GENERAL/COURSE/MODELING/RESEARCH`：

```text
status=EXPLICIT
requested=resolved
reason=USER_EXPLICIT_SCENE
```

即使 source 有另一场景的强信号，启发式也不得替用户改值。AUTO 才运行评分：

- 唯一强证据：`ROUTED`；
- 无证据或唯一弱证据：`FALLBACK_GENERAL`；
- 两个正分场景平局或 margin 不足：`AMBIGUOUS`。

歧义 create 返回 `ROUTE_REVIEW/2`，写审计 scaffold，但 `authoring_allowed=false`；finalize 固定 `SCENE_ROUTE_AMBIGUOUS`，不能把 GENERAL 占位当作可编辑 resolved scene。

### 44.4 低分平局的真实红队漏洞

旧算法先判断 top score 是否低于 minimum route score。于是：

```text
本题需要说明。本研究需要说明。
COURSE=2, RESEARCH=2, margin=0
```

被误判为 GENERAL，document prior 还可选成 COURSE。revision 3 先检查所有正分竞争，再处理唯一弱证据 fallback；prior 只接受唯一 top 且 second score 为 0 的弱证据。短 PATCH 和长文 prepare 共享该修复，后者会把低分平局 unit 标为 UNRESOLVED。

### 44.5 route record 的攻击边界

测试覆盖：

- 改 score 并重算 route 自哈希；
- 再协调重算 authoring inventory；
- finalize 期间 monkeypatch router result；
- source 漂移；
- route policy/router hash 漂移；
- protected code 注入 MODELING 关键词；
- route evidence 原文泄漏；
- EXPLICIT 场景覆盖攻击；
- v1/v2/v3 downgrade/兼容；
- 低分平局与 document prior 隐藏裁决。

协调重封仍被 `SCENE_ROUTE_DRIFT` 拒绝，因为期望 route 来自 source/current policy 重放，不来自 scaffold 自述。

### 44.6 真实 fixture 证明候选没有被偷偷改变

v4 单次 `AUTO` create 对 v41 GENERAL fixture 直接得到 MODELING。其 3 个 focus span、registry 与 suggestion inventory 和旧 MODELING rebuild 一致。复用相同的 3 个语义决策后：

```text
selection.scene=MODELING
bundle=2f763ca9d54ef8ecb1579920566a2bb405214b3fbe10efede3de98775788d561
candidate=f7669aecd306bca8f1827eb579be565186557fcd2a87948e5a4a9f4384524c41
```

candidate 与 v41 最终 MODELING candidate 字节一致。工程升级只删除了错误的 GENERAL→MODELING 重建，没有借 route 修复改写语义决定。

候选仍触发 `SPEECH_ACT_FIRST_PERSON_REFERENCE_INTRODUCED`，所以：

```text
mechanical/hard/speech/style=REVIEW/PASS/REVIEW/PASS
delivery=REVIEW/2
paired-quality=BLOCKED_BY_MECHANICAL_GATE
```

route 成功没有把另一个 Gate 覆盖成 PASS。closed review verifier 为 PASS/0 也只表示 SELF_CONSISTENCY_ONLY。

详细工件见 [v43 root review](build/maturity-v43-scene-prefreeze-20260719/root-review.md)。

### 44.7 验证结果

```text
focused=156 total; 155 passed; 1 skipped
projection tests=42 total; 41 passed; 1 skipped
full=851 total; 847 passed; 4 skipped
SKILL.md=453 lines; 324 non-empty
policy/builder=1.14.0/1.14.0
scene routing policy revision=3
capability=8e17aafa6aa949c2a851f2b637afb828813f329c5d55432c31b2600223e0af2a
projection=38/38 files; BYTE_DIFFS=0
tree=3bf19755676806c2393367c3c7cdc916b39b356f8f799433c1500cd5cd7784e2
manifest=3c6796ed71398f19e83e5fa9db8e9101b76a24a6f0edc67145d617b5a4ade3fe
quick_validate=PASS/PASS/PASS
evidence_cap=E2
generation qualification=NOT_EVALUATED
```

### 44.8 仍然存在的高优先级成熟度缺口

短 PATCH route prefreeze 已完成，不等于全部 authoring preflight 完成：

1. 长文 prepare 的 chunk hash 已间接绑定 route，但 `scaffold_humanize_rewrites.py` 不显式展示 scene/route，也不在生成模板前重放 prepare integrity、live source 与 route；当前主要在 finalizer 事后拒绝。
2. EXPLICIT 分支不计算只读 observed scores，尚不能提示“用户显式场景与明显用途冲突”。后续只能增加 REVIEW 诊断，不得让启发式覆盖用户选择。
3. registry/offset/ID repair、共享 `reason_ref` 未实现。
4. 外部 paired-quality、学术正确性、证据真实性、作者身份和 generation qualification 仍未建立。

当前准确 checkpoint 是：短 PATCH 已拥有 source-bound、policy-bound、可重放、可拒绝歧义的 AUTO scene authoring 前置门；Skill 仍不是无人值守终稿系统。

## 45. v44：长文 authoring binding 与可信发布

### 45.1 从 v43 的 route prefreeze 到长文 v5

v43 解决的是短 PATCH 的 `AUTO` scene 在 authoring 前冻结和 finalize 重放。v44 把同样的 source-bound 原则推进到长文：模板生成前固定 strict schema 2 prepare closure，模板内完整保留场景、Voice、snapshot、policy 和 source span binding，finalize 从冻结 source 重新构建这些值，不信任调用方改写的 sidecar 或自哈希。

现行公开 schema 为：

```text
humanize-rewrite-scaffold/v5
humanize-unit-rewrite-bundle/v3
humanize-long-authoring-binding/v1
```

v3 `REWRITE` 使用有序、非重叠 source spans 和 target signals 构成完整 intent 图；v3 `NO_CHANGE` 必须给出指向具体职责/对象/范围/条件的理由和 evidence span。legacy v1/v2 只读兼容，但绑定状态保持 `REVIEW`，不得被转换成 PASS。这样“模板很完整”和“这个模板确实绑定当前冻结单元”成为两个可区分的事实。

### 45.2 marker 不是名字，发布才是事务

v5 scaffold 使用 uncommitted marker 到 committed marker 的两阶段发布。最终提交从同一 Windows handle 精确读取 marker，验证 regular file、无 reparse、无 hardlink、句柄/路径 identity、metadata SHA 和严格字节长度，再相对 pinned parent handle 原子改名。发布后的再次校验失败会按 pinned handle 回滚；回滚失败输出 `FAIL_DIRTY/1`，不能让目录存在本身充当 SCAFFOLDED 证据。

该保护边界只在本地 NTFS 上成立。ReFS、FAT/exFAT、SMB/remote protocol 与其他不提供等价句柄语义的环境 fail closed。测试覆盖 marker 缺失、残留 uncommitted marker、schema/hash 篡改、hardlink/link 和发布后篡改；仍不把这一层扩大解释为文风质量或学术正确性证明。

### 45.3 资格合同 binding 与投影复现

本轮把评测合同的版本绑定正式纳入证据：

```text
requirements contract = 2026-07-19.19
requirements sha256    = 86a69dde31f50d706be3c44a04c563146c7bd9870b5c38af0ae6dd5addcee640
oracle catalog         = 1.10.0
oracle contract bind   = 2026-07-19.19
oracle contract sha256 = 4eb32deb0e859420810e15e54fe544f9bf62dee1e8d7b19a146ab3427555359b
projection/builder     = 1.15.0 / 1.15.0
capability source      = 5a1379999b6efb727e06031c9235279818b8c4648c4e62c068faba07c201e44e
projection             = 38 files (34 INCLUDE + 4 TRANSFORM)
tree                   = 8dbce027e48eba712cf3a7a2a5b878b38c9609614926943c0167c0c73821873c
manifest               = 113fd0246ce77289b8bada37e101446dfda080b2553a7245584ce1903afaf5f3
```

两份 r2 projection 各有 38 个文件、`1,507,978` 字节；路径集合、长度、逐文件 SHA-256 和两份 `23,177` 字节 manifest 均完全一致。该结果只支持确定性构建和 policy binding，不支持生成资格、作者身份或自然度判断。当前最高证据级别仍是 E2，`generation_qualification_status=NOT_EVALUATED`。

### 45.4 真实 CLI 前向验证的权威状态

`tmp/forward-long-check-20260719/` 中分别运行了 `prepare -> scaffold v5 -> finalize` 的 `NO_CHANGE` 和 `REWRITE` 路径。两条路径都完成了 source snapshot、preflight、v3 bundle、protected span 恢复、fragment/document 机械校验和 paired-quality request 生成：

| 路径 | finalize 权威状态 | 关键证据 |
|---|---|---|
| `NO_CHANGE` | `DELIVERY REVIEW exit=2 publish=REVIEW_CANDIDATE` | assembly PASS；intent PASS；quality `PENDING_EXTERNAL_REVIEW` |
| `REWRITE` | `DELIVERY REVIEW exit=2 publish=REVIEW_CANDIDATE` | `DONE=1` 只属于 candidate assembly；intent PASS；quality `PENDING_EXTERNAL_REVIEW` |

两条路径均 `source_files_modified=0`，只生成 `rendered_review/`，没有生成 `rendered/`。`REVIEW/2` 是无可信外部 paired-quality clearance 时的正确状态；不能把它改写成“失败”，也不能把 `candidate_assembly_status=PASS` 改写成“Humanize 完成”。这次是 Markdown 夹具且未传 `--check-command`，所以 `compile_check=NOT_RUN`。

### 45.5 回归与能力边界

```text
scaffold publication tests = 47 OK (skipped=2)
finalizer tests             = 144 OK (skipped=1)
joint publication tests     = 191 OK (skipped=3)
projection tests            = 43 OK (skipped=1)
full unittest               = 903 OK (skipped=7)
quick_validate              = PASS
compileall                  = PASS
git diff --check            = no whitespace error
SKILL.md                    = 461 lines / 332 non-empty / 56,144 bytes
```

仍然不能从上述数字推出：外部 paired-quality 已清除、学术内容正确、引文和证据真实、作者身份可确认、检测器结果可预测，或生成资格矩阵已通过。v44 解决的是长文工件身份、发布边界和错误完成态，不是把文风判断自动化成事实判断。scene/route 的长文界面披露、registry/offset repair、跨 unit 语义质量和非 NTFS 等价发布仍是明确后续工作。

### 45.6 v44 的精确结论

当前 Skill 可以可靠地产生 source-bound、policy-bound、可重放的长文待审候选，并在 marker、hash、文件句柄、绑定、保护区、intent、回滚或状态声明不一致时停止。它不应被描述为无人值守“去 AI 检测”器，也不应在 `REVIEW_CANDIDATE`、`E2` 或 `NOT_EVALUATED` 状态下声称终稿、人工审批、自然度或学术质量已经通过。

## 46. 2026-07-20：编译门收容与中断安全终检

本节只更新编译子进程清理与机器验收状态，不改变第 45 节的质量边界。Linux POSIX wrapper 现以 child subreaper 收割包括 `setsid()` 脱离进程在内的 adopted descendants，并在命令启动前建立信号处理；父进程在 `terminate()`、`wait()` 或 `kill()` 再次被中断时继续有界清理。wrapper 使用 `python -I -S -X utf8`，避免用户启动钩子在 containment 之前执行。`/proc` fallback 每轮和末次扫描后复核 wrapper 存活，无法确认时返回 `FAIL`。

Windows Job Object 路径在创建、配置、分配和终止异常时保证关闭 handle；未成功入 Job 的进程改用有界直接 kill 重试。对应执行型测试覆盖第二次 Ctrl-C、Job 终止异常、未收容重试和隔离 argv。现行验收为：

```text
finalizer=164 OK (skipped=2)
projection=43 OK (skipped=1)
full unittest=926 OK (skipped=8)
quick_validate=PASS; compileall=PASS; git diff --check=PASS
policy=1.16.0
capability=10db5c1b9666164e06a9929bfb6ab15be821302e0538fe8ae6534f707bed8579
projection tree=cb595dfa5a2a17b098078b59b0cdc6f5370b3f398d63cdac5069c04d676cde7a
manifest=78dca81b684bba29539fec607ff28a5164be3cc2d8bcc0927ba3ec06dd4f25c6
projection files=38/38; byte/hash diff=0; manifest bytes=23,177/23,177
```

本轮还把 compile status FD 收紧为恰好一条严格记录，并核对 `command_exit`；多记录、额外字段、退出码错配、超量和读超时均 fail closed。无命令时 `timeout_seconds=null`，非法 timeout 在 finalize 入口拒绝，wrapper/Job setup 异常会保留结构化 `compile_check=FAIL`。这些是进程收容与审计改进，不是生成质量证明。

本机没有 Linux 发行版，真实 Linux subreaper 集成测试仍按条件跳过，不能声称跨平台实测通过。以上回归继续只证明机械合同、自洽状态与确定性投影；generation qualification 保持 `NOT_EVALUATED`，证据封顶 E2，学术正确性、作者身份、自然度与外部 paired-quality clearance 均未获得本地授权。

## 47. 2026-07-20：replay 双状态合同、言语行为边界与 v1.19 确定性投影

### 47.1 replay 不再用“重放成功”覆盖“原记录未通过”

本轮把验证记录的两个状态拆开并写入正式评测合同。`replay_status/replay_exit_code` 只回答“归档记录在当前策略下能否完整、自洽地重放”；`recorded_delivery_gate_status/recorded_exit_code` 才回答“当时被归档的交付门是什么状态”。因此，replay 自身返回 `PASS/0` 时，若原记录为 `REVIEW/2`，调用方必须同时显示这两个状态，不能把前者改写成候选已经获准交付。

相应版本与摘要为：

```text
evaluation contract = 2026-07-20.20
contract sha256      = 271bc82acb77b562932e85115aff3bbecdb2ae9411b9dc4520557b0bdee7e0e3
requirements         = 2.10.0
requirements sha256  = 7208eab18d56ff86b9396cf84c898be8afe7d8e51b16160e3a916861161176aa
oracle catalog       = 1.11.0
oracle sha256         = 878e25b50319f1c70b532def1bb30cd41be71af4c51ccdd4478000c7fdd0997b
```

replay 入口还在字典查询前验证所有 status 字段的类型。列表、对象等畸形状态现在稳定返回结构化 `FAIL/1`，不再抛出裸 `TypeError`。这项修复保护的是审计协议，不提高任何文本的自然度评分。

### 47.2 capture 隐私与位置工件闭合

`capture_humanize_validation.py` 现在要求命令中恰好存在两个真实位置工件；把 `--term PRIVATE_AFTER.md` 伪装成第二个工件会被拒绝。对 `PermissionError/OSError`，外层只输出固定安全消息，不回显路径、basename、系统错误正文、argv 中的私有 token 或审阅者标签。畸形缩写参数同样不得借 argparse 错误路径进入证据包。

该机制仍只证明同主机、同用户、父进程观察到的子进程事实。它不证明历史真实性、外部时间戳、学术正确性、作者身份、自然度、paired-quality clearance 或生成资格。

### 47.3 marker 级言语行为保护

此前的排除逻辑可能按整段词面过宽豁免。本轮改为 marker 级精确 span，并补齐以下反例：

- `不连续 → 连续` 必须识别为否定删除；`不同`、`不对称` 等邻近词不再吞掉真正的“不”。
- `不可微 → 可微` 只豁免技术词素“可”，仍捕获被删除的否定。
- `可微/可积/可导/可逆` 中的“可”不再被误判为普通模态变化；`可逆 → 存在逆矩阵` 不应产生虚假 modality finding。
- route-shell 只豁免句首实际路由 marker；同句后续独立出现的“所以”仍受逻辑关系门保护。
- “所以然”不再被拆成逻辑连接词“所以”。

真实失败候选 `tmp/blind-course-forward-v18/review-final/candidate.review.tex` 删除“于是、从而、因此”的推导链，当前门会给出 `SPEECH_ACT_LOGICAL_RELATION_CHANGED` 并保持 `REVIEW/2`。这说明旧机械通过记录不能脱离当时 policy hash 继续冒充当前策略 PASS；policy drift 本身就是应保留的审计事实。

### 47.4 修复后真实 COURSE 候选复核

对 `tmp/blind-course-postfix-v18/source.snapshot.tex` 与 `review-authoritative/candidate.review.tex` 按 `REWRITE/COURSE` 重新运行当前 validator，得到：

```text
source sha256                 = b28dc286b43b7b581f95482d31d53be57a1d0cf743a0e890f58b1f3121fe934b
candidate sha256              = 51b879cbd27a9e470bb8b5319293269437f3d63be2a1f8d274f7de5bf209fa6c
mechanical_validation_status  = PASS/0
hard_invariant_layer_status   = PASS
speech_act_layer_status       = PASS
style_signal_layer_status     = PASS
delivery_gate_status          = REVIEW/2
paired_quality_review_status  = PENDING_EXTERNAL_REVIEW
humanize_quality_claim_allowed= false
academic_correctness          = NOT_EVALUATED
```

候选保留公式、TeX 控制序列以及“从而、所以、因此、于是”的推导关系。机械 PASS 只说明当前规则未发现结构和言语行为漂移；`REVIEW_CANDIDATE` 不是终稿，外部成对质量复核未完成前不得宣称“已经更自然”或“Humanize 完成”。

### 47.5 全量验收与 v1.19 投影

能力面变化触发旧批准哈希 fail closed 后，独立重算并批准新 capability source，builder/policy 同步升至 `1.19.0`。最终验收为：

```text
targeted cross-check = 231 OK
full unittest         = 956 OK (skipped=8)
compileall            = PASS
quick_validate        = PASS
policy/builder        = 1.19.0 / 1.19.0
policy sha256         = 943698243ae48f33111b78b37376a284c2ff9f76ef4c1cad59750b8e0d663a04
capability source     = 3a0f337fd338f00a35da4e8e47f5fb5163c9ceb34bdf5a037eb9f2decbf16417
projection files      = 38 / 38
byte/file hash diffs  = 0
projection tree       = 7151e633694661995fbb6c30142ef0282dcf944e8a766b8e1a427c19c8068932
manifest sha256       = ff23749a0f4e659c8c1320befb87a768766a7208ef5e05b39e90586fcadf2ce7
manifest byte-equal   = true
evidence cap          = E2
generation status     = NOT_EVALUATED
```

两份投影位于 `build/generator-projection-maturity-v47-v119-20260720` 与同名 `-repro` 目录。38 个相对路径、文件长度和逐文件 SHA-256 全部一致，两个 manifest 逐字节一致。该结果只证明固定能力面的确定性投影；scanner finding 不是删除授权，replay PASS 只是记录自洽，projection PASS 也不授予模型盲写权限。学术正确性、自然度、作者身份、paired-quality 与 generation qualification 均未获批准。

## 48. 2026-07-20：strict JSON、路由合同与前向可用性缺口修复

### 48.1 本轮攻击面与证据来源

本轮没有用既有单元测试绿灯直接宣布成熟，而是把新鲜前向任务、跨模块状态重建和全量回归并列使用。前向任务覆盖清晰 COURSE/MODELING 路由、平局路由、句壳删除、检测报告 HTML、零可编辑长文、乱码 include、缺 bundle、编译失败/超时、来源快照漂移以及 TeX 保护区。由此发现的缺口均先复现，再补机械反例；没有把前向输出本身当作真人范文或正向文风证据。

### 48.2 strict JSON 单义性

以下入口此前仍有普通 `json.loads/json.load` 的后值覆盖面，重复键可能让审计者与执行器读取不同语义：

- `validate_humanize_output.py` 的 REPORT_INFORMED scope；
- `route_humanize_scene.py` 的固定路由 policy；
- `scan_humanize_chinese.py` 的 lexical-signals；
- `prepare_humanize_candidate_revision.py` 的 candidate 与 supersedes result；
- `validate_humanize_candidate_queue.py` 的 candidate package 与 queue state。

当前五条路径统一拒绝重复键并 fail closed。新增测试分别构造冲突键，确认攻击载荷不能借“最后一个值获胜”改变 scope、路由阈值、词库、候选血缘或队列 head。这项改进证明 JSON 合同单义，不证明 JSON 中的理由真实、候选更自然或来源身份可信。

### 48.3 AUTO 路由合同修复

前向样本暴露出文档合同与执行策略漂移：`operational-contract.md` 写明最高分至少 2、领先至少 1 即可路由，实际 policy 却要求 3/2，导致有明确场景词的文本静默回退 GENERAL。当前 `scene-routing-policy.json` revision 升至 4：

```text
minimum_route_score  = 2
minimum_route_margin = 1
positive-score tie   = AMBIGUOUS/UNRESOLVED
hidden priority      = forbidden
document prior       = cannot break a positive-score tie
```

相应 second-pass include-graph 测试也改为读取当前路由事实：`参数设置沿用前文` 在现行阈值下已经直接达到 MODELING 路由条件，不再伪装成 `ROUTED_DOCUMENT_PRIOR`。路由修复只说明场景合同与实现一致；它不证明被路由文本的文风质量，也不把相关性写成模型能力提升。

### 48.4 精确句壳豁免，避免“为了保护语义而无法删套话”

两个真实动作曾被硬不变量误阻断：

```text
需要指出的是，问卷结果可能受样本结构影响。
→ 问卷结果可能受样本结构影响。

本文梳理三类回答，从而为后续分析提供可靠起点。
→ 本文梳理三类回答。
```

旧门把空重点壳中的“需要”当成模态删除，把无信息未来桥接壳中的“从而”当成推导关系删除。当前只对已登记句壳内的实际 marker span 发放豁免；同句后续独立 marker 仍受保护，真实推导 `样本扩大，从而误差下降 → 样本扩大，误差下降` 继续阻断。该改动解决的是必要的 style-shell deletion 死锁，不能推广成“含需要/从而都可删”。

### 48.5 检测报告 UI 与正文 fragment 分离

HTML 前向样本包含：

```html
<div class="risk-score">综合风险：87%</div>
<mark>真正标红正文……</mark>
```

旧 extractor 因 class 名含 `risk`，把评分 UI 当作正文片段，形成虚假多 fragment 与 `REVIEW/2`。当前 `UI_SCORE_METADATA_RE` 只过滤非 `<mark>`、短评分/概率/风险百分比 UI；真实 `<mark>` 仍进入唯一映射。测试确认总 fragment 为 1 且 extractor `PASS/0`。这不验证检测器分数真实性，不允许预测或优化分数，也不改变“报告只提供 scope 线索”的边界。

### 48.6 长文状态重建的一致性

零可编辑单元时，prepare 现明确输出“没有可编辑作者正文，不要开始 authoring”。本轮全量测试进一步发现 finalizer 的 prepare-integrity 重建仍硬编码旧 `next_action`，使 scaffold 在应返回 `REVIEW/2 + no_authoring_eligible_units` 时错误降为 `FAIL/1`。当前 finalizer 使用与 prepare 完全相同的条件化派生值，定向 CLI 测试恢复通过。

来源快照变化时，finalizer 文本摘要额外显示：

```text
source_snapshot=CHANGED count=N;
unit_statuses_do_not_establish_current_source_coverage=true
```

这防止调用方只看 `units[NO_CHANGE=...]` 误判当前源文件已覆盖。乱码 include 仍为 `SKIPPED_GARBLED`，顶层保持 REVIEW；乱码原因目前只到各编码解码失败位置，未声称完整诊断。缺 bundle、编译退出非零、编译超时和 stale source 继续分别按合同阻断，不发布正式 `rendered/`。

### 48.7 v1.20 批准链与最终验收

能力文件变化后，旧 capability hash 先按预期 fail closed；随后按固定 38 文件 inventory 独立重算并批准新哈希。现行结果为：

```text
full unittest         = 966 OK (skipped=8)
projection tests      = 44 OK (skipped=1)
compileall            = PASS
quick_validate        = PASS
git diff --check      = PASS; only LF/CRLF notices
SKILL.md              = 483 lines / 57,831 bytes
policy / builder      = 1.20.0 / 1.20.0
policy raw sha256     = 9b0337cd5e004311b88b3846320e99773fd7ce0c26501bd6539f6f05cd2d825f
capability source     = 35ef9306d2bbfe84b7fdddd8a405c4efa2becdd6325b9f0a8c8cd1676ac6a054
projection files      = 38 / 38
path/length/hash diff = 0
projection tree       = e28f0df87dd8f3c1b807ac6a46f4bb51ca43d45043ab945e2a78f8e0e230da0b
manifest sha256       = 13b2141047572f506537f138703d51bc01a99dfb5bada048f8a488b3f499d2cd
manifest byte-equal   = true
evidence cap          = E2
generation status     = NOT_EVALUATED
```

两份投影位于 `build/generator-projection-maturity-v48-v120-20260720` 与同名 `-repro` 目录。逐路径、文件长度、文件 SHA-256、tree hash 和 manifest 字节全部一致。

### 48.8 本轮不能越过的结论边界

本轮可以确认：重复键不能再造成关键 JSON 歧义；AUTO 路由阈值和平局语义一致；精确句壳删除不再被模态/逻辑门机械锁死；评分 UI 不再污染报告正文 scope；零编辑和 stale-source 状态更难被误读；固定 capability projection 可复现。

仍然不能确认：任一候选比原文更自然、学术内容正确、引文或证据真实、作者身份成立、检测分数下降、外部 paired-quality 已清除，或 generation qualification 已通过。`REVIEW_CANDIDATE` 不是终稿，路由命中不是质量评分，句壳豁免不是任意删词授权，UI 过滤也不解释检测器本身。

## 49. 2026-07-20：真实前向任务、事件单义性与乱码诊断加固

### 49.1 三组无答案泄漏前向任务

本轮在 v1.20 既有测试之外，重新使用三个彼此独立的真实前向任务。执行代理只获得任务、材料和现行 Skill，不获得预期答案或待修缺口；因此这些结果比“把已知断言重新跑绿”更接近真实调用，但仍不是外部真人质量评审。

| 前向任务 | 机械结果 | 实际观察 | 未获证明事项 |
|---|---|---|---|
| 短文 `REWRITE/PATCH` | apply=`REVIEW/2`；verify=`PASS/0` | 删除空强调壳和未来桥接壳；保留“已有研究表明……”并登记 `UNRESOLVED_UNSOURCED_ATTRIBUTION`；未升级公式、事实或归因 | 改后文本更自然、归因真实、可直接发布 |
| 受限 `DRAFT` | 顶层=`REVIEW/2`；内层 replay=`PASS/0` | 只并列材料明确给出的 A=12、B=9，不自行推导高低；保留“非独立外部验证”和“后续实测尚未完成” | 推论正确、材料充分、生成资格已批准 |
| 长 TeX + 乱码 include | `DONE=1`、`SKIPPED_PROTECTED=1`、顶层=`REVIEW/2`、publish=`PARTIAL` | `bad.tex` 被登记为 `SKIPPED_GARBLED`；保护区未被当成可改正文；源文件修改数为 0 | 全文已覆盖、乱码根因已识别、候选达到终稿质量 |

长 TeX 首次 finalization 还在 prepare 脚本更新后正确触发 policy snapshot drift；重新 prepare 后才允许继续。这证明快照漂移门在真实执行中会 fail closed，而不是只存在于单元测试。它不证明快照内容本身可信，也不允许旧 prepare 结果跨策略版本复用。

### 49.2 Codex 事件 JSONL 改为 strict object stream

`run_humanize_generation_trial.py` 的两条事件读取路径此前直接使用普通 `json.loads`。这会接受重复键和 `NaN`，使同一行可能具有非唯一语义，或产生超出标准 JSON 的非有限数值。当前新增统一的 `_strict_event_json()`，复用 strict JSON 解析器并要求每条事件必须是 object，明确拒绝：

- 重复键事件；
- `NaN`、`Infinity` 等非有限数；
- array、string、number 等非 object 顶层事件。

对应测试覆盖两条逐行读取路径。该修复证明本地观察流具有单义 JSON 结构；它不验证事件来自真实 Codex、事件顺序未被外部篡改，或事件正文的事实陈述为真。

### 49.3 POSIX compile supervisor 状态拒绝后值覆盖

`finalize_humanize_long_document.py` 的 POSIX status FD 曾使用普通 `json.loads`，攻击者可用 `{"cleanup":"FAIL","cleanup":"PASS"}` 让后值覆盖前值。当前该入口统一改用 `_parse_json_strict`；测试同时覆盖重复 `cleanup` 和 `command_exit=NaN`。因此编译清理与退出状态不能再通过重复键或非有限数静默漂移。这里验证的是状态记录合同，不是 TeX 编译内容正确，也不是生成文本质量。

### 49.4 有界乱码诊断

乱码 include 的原因字段由无区分度的：

```text
utf8_failed:0;gb18030_failed:0
```

改为同时记录 codec、异常起止位置、最多 8 个失败字节的十六进制摘要和输入字节数，例如：

```text
utf8_decode_error:start=0:end=1:bytes=81:input_bytes=5;
gb18030_decode_error:start=0:end=1:bytes=81:input_bytes=5
```

诊断不回显原文窗口，不把大段不可解码内容写入日志，也不会因为单个乱码文件阻塞其余可读单元。字节摘要只证明两个既定解码器在相应位置失败，不证明真实编码、文件来源或损坏原因；`SKIPPED_GARBLED` 继续要求顶层 REVIEW，不能冒充全文处理完成。

### 49.5 v1.21 全量验收与可复现投影

本轮能力文件变化后，policy 与 builder 同步升级为 1.21.0，并批准固定 38 文件 inventory 的新 capability source hash。当前重新从磁盘执行的验收结果为：

```text
v1.21 targeted tests = 257 OK (skipped=3)
full unittest        = 966 OK (skipped=8)
compileall           = PASS
quick_validate       = PASS
git diff --check     = PASS; only LF/CRLF notices
policy / builder     = 1.21.0 / 1.21.0
capability source    = fb758249bb492ee69b04f51282b74e2f2edf047c2c8ecbb1d0b416a9f6c74bbb
projection files     = 38 / 38
path/length/hash diff= 0
projection tree      = fde3558ef86d234efc2ae6c63d1f818db46f7390b4ddf6db128e1b16ba469b88
manifest sha256      = dc0d7034143c259da88159a709209f3b280db67691768feaeaa88e770875aca3
manifest byte-equal  = true
evidence cap         = E2
generation status    = NOT_EVALUATED
```

两份投影位于 `build/generator-projection-maturity-v49-v121-20260720` 与同名 `-repro` 目录。清单按构建器合同置于投影目录外；构建器对“把 manifest 写进 projection 自身”的尝试会明确拒绝，避免自引用。两份结果经独立 PowerShell 核对，相对路径、长度、逐文件 SHA-256、tree hash 和 manifest 原始字节全部相同。

### 49.6 当前可信边界

本轮提高的是前向任务覆盖、JSON 单义性、状态防覆盖、乱码可审计性与确定性投影。`REVIEW_CANDIDATE` 仍不是终稿；乱码字节摘要不是编码根因；strict JSONL 不是来源真实性证明；capture/replay `PASS/0` 只说明记录与当前合同自洽；保护单元、`PENDING` 和 `REVIEW` 不能冒充完成。学术正确性、自然度、作者身份、外部 paired-quality clearance 与 generation qualification 均未批准。

## 50. 2026-07-20：候选队列非有限数攻击与评估面追踪

### 50.1 新缺口

在 v1.21 归档后继续扫描全部 `json.loads/json.load` 调用，发现候选包和 candidate revision 链虽然已经拒绝重复键，却仍未给 `parse_constant` 设置 fail-closed 回调。Python 标准库会接受不属于标准 JSON 的 `NaN`、`Infinity` 和 `-Infinity`，因此“strict JSON”仍存在一处不完整边界。受影响入口包括：

- 待验证 candidate package；
- 已存在的 accepted/review/rejected queue result；
- revision 的原 candidate；
- revision 绑定的 supersedes result。

### 50.2 修复与反例

`validate_humanize_candidate_queue.py` 新增 `_reject_queue_nonfinite`，candidate package 与历史 queue state 使用同一拒绝器；历史状态读取同时把该结构错误归一为 `queue_state_unreadable`，不能因异常类型漏接而形成未定义退出。`prepare_humanize_candidate_revision.py` 新增 `_reject_nonfinite`，原 candidate 与 supersedes result 均拒绝非有限数。

新增三项测试方法，分别覆盖 candidate package 的 `NaN`、历史 queue result 的 `Infinity`，以及 revision/supersedes 两条输入。定向结果为 52 项通过；全量由 966 增至 969 项，全部通过，跳过数仍为 8。

### 50.3 generator capability 与 evaluation surface 的边界

这两份脚本属于投影 manifest 的 `EVALUATION_SURFACE`，不属于实际进入生成器投影的 capability source。因此修改后：

```text
policy / builder                 = 1.21.0 / 1.21.0（无需虚假升版）
capability source                = fb758249bb492ee69b04f51282b74e2f2edf047c2c8ecbb1d0b416a9f6c74bbb（不变）
projection tree                  = fde3558ef86d234efc2ae6c63d1f818db46f7390b4ddf6db128e1b16ba469b88（不变）
evaluation surface              = cc3ab2063f1fca311e48ff1542c28697df0154fea8222b8444eb1a6d4ecb7b16
inventory                       = 7f4f191ad5d3f06921e4dcd50832db3c0b38b9182eceda468c64e77c642a5f98
updated manifest sha256         = 2b6e26e468c947077b39d82a36a063d8bf1eb8c4bbeb7a2aff8f0abbd835a91d
projection files                = 38 / 38
path/length/hash diff            = 0
manifest byte-equal              = true
```

也就是说，生成器可见字节没有变化，但约束生成结果能否进入队列的评估面变强了。报告不能用“不在 capability hash 内”误写成“无需追踪”；manifest 正是用于记录这类 evaluation-surface 变化。

### 50.4 最终复测

```text
candidate/revision targeted tests = 52 OK
full unittest                     = 969 OK (skipped=8)
compileall                        = PASS
quick_validate                    = PASS
git diff --check                  = PASS; only LF/CRLF notices
evidence cap                      = E2
generation qualification         = NOT_EVALUATED
```

两份更新后投影位于 `build/generator-projection-maturity-v50-preapproval-20260720` 与 `build/generator-projection-maturity-v50-v121-20260720-repro`。名称中的 `preapproval` 只是首次审计运行的历史命名；该轮没有发生 capability approval 变更。两份投影及投影外 manifest 已逐字节复核一致。

本节仍只证明非有限数不能进入候选状态链、评估面变化被 manifest 捕获且投影可复现；不证明候选自然、学术正确、作者认可或适合发布。
## 51. 2026-07-20：前向路由、长 TeX 清单语义与 second-pass 消费链闭环

### 51.1 三个剩余 strict JSON 非有限数入口

对输入边界继续做 AST 与调用链复查后，确认三个真实入口虽然已经限制结构，却仍会接受 Python JSON 扩展常量 `NaN`、`Infinity` 和 `-Infinity`：场景路由的 scene policy、词汇扫描器的 lexical-signals，以及输出验证器的 report scope。三个入口均增加 `parse_constant` 拒绝器，并分别加入反例。定向 132 项测试通过。这里证明的是这些配置不能再携带非标准数值进入规则计算，不证明配置规则本身能够评价自然度。

### 51.2 无答案泄漏的 AUTO 路由前向结果

新鲜前向工件位于 `C:\Users\Lenovo\.codex\tmp\humanize-forward-route-v51`。执行代理只获得实际任务、材料和 Skill，没有获得预期答案或待修缺口。六个案例产生 47 个可解析 JSON，六份 evidence bundle replay 全部一致：

- 明确弱证据返回 `FALLBACK_GENERAL/0`，没有伪装成可靠分类；
- 两个正分场景平局返回 `AMBIGUOUS/2`，虽然占位 `final_scene=GENERAL`，但没有生成候选；
- REWRITE 的机械门通过后，顶层仍因 paired-quality pending 保持 `REVIEW/2`；
- DRAFT 的表面来源检查通过时，`semantic_source_check=NOT_EVALUATED`，顶层仍为 `REVIEW/2`；
- “两个已列指标”改写为“两项”首次被数字来源门判为 `FAIL/1`，删除新增数量表达后才进入后续审查。

该前向没有发现顶层虚假完成，但也暴露调用方风险：如果调用方只读取局部 `PASS`、占位 `final_scene` 或忽略退出码，仍可能自行制造误判。因此顶层状态、路由状态和退出码必须联合消费。

### 51.3 长 TeX、罕见 UTF-8 与 stale-source 前向

长文工件位于 `C:\Users\Lenovo\.codex\tmp\humanize-forward-long-v51`，权威结果为 `run2/finalization_metadata.json`：

```text
DELIVERY REVIEW exit=2 publish=PARTIAL
candidate_assembly=REVIEW
paired_quality=BLOCKED
source_snapshot=CHANGED count=1
units[NO_CHANGE=3,SKIPPED_PROTECTED=1,UNRESOLVED=2]
compile_check=NOT_RUN_DUE_TO_SOURCE_CHANGE
completion=false
```

源变化没有被 `NO_CHANGE` 单元状态掩盖；正式 `rendered/` 未发布，编译检查也没有在过期源上冒充执行。𠮷、𠀀、组合字符、NBSP、全角字符、ℝ 和 → 所在文件按原始字节保留，SHA-256 为 `1bfe4a80b8e37b056a94242f6e549bac5090e4b0766f66574f6580a40e17460c`，共 643 字节。首次运行因 prepare 与 finalize 之间策略文件变化触发 `run policy snapshot drift`，说明旧计划不会跨策略静默复用。

### 51.4 rendered manifest 语义消歧与 second-pass 回归根因

前向测试指出旧 `rendered_manifest.csv` 的 `source_path` 是当前活动位置，而 `sha256` 实际绑定渲染候选；脱离上下文阅读容易把哈希误解为当前源文件哈希。finalizer 因此增加并固定：

```text
source_path_scope=LIVE_LOCATION_LABEL_NOT_HASH_TARGET
source_snapshot_copy=<run-relative frozen copy>
source_snapshot_sha256=<frozen source bytes>
sha256_scope=RENDERED_CANDIDATE_BYTES
rendered_sha256=<rendered candidate bytes>
```

保留 `source_path` 与 `sha256` 仅为兼容旧消费者。全量测试随后暴露 19 个错误：`prepare_humanize_second_pass.py` 仍要求 manifest 精确等于旧六列，导致新版生产者与旧消费者断裂。本轮没有通过“允许任意额外列”绕过，而是让 second-pass 精确接受当前 11 列并 fail closed 校验：

- 未知列拒绝；
- 两个 scope 常量必须精确匹配；
- `sha256` 必须等于 `rendered_sha256`；
- 两个哈希必须是 64 位小写 SHA-256；
- `source_snapshot_copy` 必须是 `source/` 下的安全相对路径，不得绝对化、包含 `..` 或逃逸运行根；
- 冻结源副本和渲染候选都必须与清单字节哈希及长度一致。

新增四类 second-pass 回归测试：新版清单正常消费、scope 篡改阻断、哈希别名分歧阻断、未知列阻断。second-pass 定向 26 项、长文与投影联合 264 项均通过。

### 51.5 参数可操作性与版本边界

长文 prepare 的帮助和错误信息现明确写出 `--max-author-chars >= 1000`、`--max-lines >= 50`、`--min-author-chars >= 0`，避免调用方只能靠试错猜预算下限。

manifest 生产者、长文工作流及其他生成能力文件先前已正式升级到 1.23.0；本节新增的 second-pass 修复位于投影策略 `exclude_exact` 中的 `EVALUATION_SURFACE`。因此本轮没有为了形式上的“升级”虚构 1.24：生成能力哈希保持 1.23 的批准值，evaluation surface 与总 inventory 则由新 manifest 记录变化。

### 51.6 最终复测与双投影复现

```text
second-pass targeted       = 26 OK
long/second/projection     = 264 OK (skipped=3)
full unittest              = 977 OK (skipped=8)
compileall                 = PASS
quick_validate             = PASS
git diff --check           = PASS
policy / builder           = 1.23.0 / 1.23.0
capability source          = f5c717c6cd6a8c1f39ecc5958e72f466fe47d4b7af2267611633362e26d19d98
evaluation surface         = 6463a23ab65afd70c95b0332d65172ceb403788a12cd7ba1313e1d5febfbffd0
inventory                  = da38a4ff2e9541196f79cde865c0260b36cd11a6cd5b1f81b645f642e158ee8e
projection files           = 38 / 38
path/length/hash diff      = 0
projection tree            = 126bfcd1acebd4231e7b445e0b3301763b71893e39cae92f1441c0ec017911e8
manifest sha256            = 64d91dd5639c3ee860365d8942f8fc2bcb4b672f2bbad82f928c3372bd6ed6ad
manifest byte-equal        = true
evidence cap               = E2
generation qualification  = NOT_EVALUATED
```

两份投影位于 `build/generator-projection-maturity-v53-v123-20260720` 和同名 `-repro` 目录。38 个相对路径、文件长度、逐文件 SHA-256、tree hash 与投影外 manifest 原始字节完全一致。

### 51.7 不能越过的结论边界

本轮证明了 strict JSON 配置入口、manifest 语义、生产者—消费者兼容、stale-source 阻断、罕见 UTF-8 保留和确定性投影的机械可信度；它没有证明候选比原文自然、学术判断正确、引文真实、作者身份成立、外部 paired-quality 已清除或模型具有稳定生成资格。机械 `PASS/0`、replay 一致和 977 项测试全绿均不能替代这些外部判断。
## 52. 2026-07-20：CSV 单义性、行宽约束与 v1.24 能力面升级

### 52.1 JSON 严格化之后的 CSV 盲区

继续沿结构化工件信任链审计时发现，三个关键读取器仍直接使用 `csv.DictReader`：长文 finalizer、second-pass prepare、second-pass verifier。标准库的默认行为并不等于严格表格协议：重复表头会以后列静默覆盖前列；短行会把缺失字段记为 `None`；长行会把额外字段塞入 `None` 键。若消费者只检查最终字典键集合，重复表头尤其可能形成“原始 CSV 具有两种值、解析后只剩一种值”的歧义。

### 52.2 统一严格 CSV 合同

`finalize_humanize_long_document.py::_load_csv` 现在先验证表头存在、字段名非空且唯一，再逐行验证字段集合与表头完全一致，禁止 `None` 键和 `None` 值。second-pass prepare 与 verifier 统一复用该读取器，并把底层 I/O、编码、CSV 和结构错误分别归一为自身的领域异常，避免原始解析异常越过状态模型。

新增测试直接覆盖三个读取面：

- 重复 `file_id` 表头必须拒绝，不能以后值覆盖前值；
- 少一列的短行必须拒绝；
- 多一列的长行必须拒绝；
- finalizer、prepare 和 verifier 三者必须表现一致。

这项修改触及进入生成投影的 finalizer，因此旧 1.23 capability approval 按设计立即 fail closed。随后重新计算固定 38 文件能力 inventory，并正式升级 policy/builder 到 1.24.0；没有通过修改测试夹具或放宽批准门规避漂移。

### 52.3 验收与确定性投影

```text
joint targeted             = 236 OK (skipped=3)
full unittest              = 979 OK (skipped=8)
compileall                 = PASS
quick_validate             = PASS
git diff --check           = PASS; only LF/CRLF notices
policy / builder           = 1.24.0 / 1.24.0
capability source          = 1536f7d3872489b13c5a946c3d5d2bd7109129bd3ce6f0f3eb728df71dbbb78c
evaluation surface         = 58d4dafcd080831333c2269ad74eb0c794b41db6323a0fb1fc56418dcb3be53b
inventory                  = 0fd9fe1ca59ede2d2789a31c5552d368a433e7ea5dcc35507e712b1181349de7
projection files           = 38 / 38
path/length/hash diff      = 0
projection tree            = 12bc16df4b352aed17307917b0bea7851cd6578be6bdaefb689f7517d356f065
manifest sha256            = ce92f3f147a901492a10ff360c51e92233541c24d81f605b81297026d8026019
manifest byte-equal        = true
evidence cap               = E2
generation qualification  = NOT_EVALUATED
```

两份投影位于 `build/generator-projection-maturity-v54-v124-20260720` 与同名 `-repro` 目录。38 个相对路径、长度、逐文件哈希、tree hash 和 manifest 原始字节完全一致。

### 52.4 前向证据状态与结论边界

本轮尝试重新启动独立 second-pass 工件信任面前向测试，但执行代理被平台误分类为网络安全请求并终止，没有生成合格原始工件，因此未计入测试或前向证据。这里不能用“代理已启动”替代结果。

当前只可确认重复表头和行宽歧义不能进入三条 CSV 消费链，且 1.24 投影可确定性复现。不能由此确认候选文本自然、学术内容正确、来源真实、作者身份成立、paired-quality 已清除或 generation qualification 已批准。
## 53. 2026-07-20：策略快照漂移的有界、去敏组件诊断

### 53.1 可操作性缺口

真实长 TeX 前向曾在 prepare 与 finalize 之间发生策略变化，系统正确拒绝旧运行，但只返回 `run policy snapshot drift`。该信息足以阻断，却不足以帮助使用者判断应重新生成哪一类工件，也无法区分 Python 运行时、验证策略、路由器或具体实现脚本变化。

### 53.2 诊断合同

`prepare_humanize_long_document.py` 新增 `_policy_snapshot_drift_components()`。它只从当前可信快照取得允许显示的组件名，不回显旧快照中的任意键、路径、哈希或值。诊断分为三个固定命名空间：

- `validator_policy_hashes.<trusted-current-key>`；
- `implementation_hashes.<trusted-current-key>`；
- `runtime.<trusted-current-key>`。

未知顶层字段或未知子键只归并为 `snapshot_structure` 或 `<section>.structure`，不会显示攻击者提供的名字。组件列表最多返回 8 项，同时给出总差异数，并固定声明 `values_redacted=true`。例如 finalizer 字节变化现在返回：

```text
run policy snapshot drift: components=implementation_hashes.finalize_script_sha256; total=1; values_redacted=true
```

### 53.3 红队反例

测试向旧快照注入含用户目录形态的私有路径键、攻击者控制的“secret”键名、敏感值和 64 位哈希。诊断只返回 `snapshot_structure` 及总数；私有路径、注入键名、敏感值和哈希均不出现。另一项真实 finalization 测试确认 finalizer 哈希变化能够准确定位，同时错误文本不包含运行目录或旧哈希。

该改动改善的是 fail-closed 后的可操作性，不会允许旧快照继续运行，也不会泄露策略文件正文。

### 53.4 v1.25 验收

prepare 属于生成能力面，因此重新批准固定能力 inventory 并升级到 1.25.0：

```text
diagnostic focused tests   = 2 OK
joint targeted             = 239 OK (skipped=3)
full unittest              = 980 OK (skipped=8)
compileall                 = PASS
quick_validate             = PASS
git diff --check           = PASS; only LF/CRLF notices
policy / builder           = 1.25.0 / 1.25.0
capability source          = 6d993e911663b220dde379329843d5e4d3d9b6ea05712c9623ab81a500649871
evaluation surface         = 1954d03a6166a2cc20e815147222fe35a4b8e473aea5af397d7462ad2f1d1599
inventory                  = 6e6e1abadeb9950a34b399d6bdcd1e1b8d75f6129147c7ad8e5536f6a95b09b4
projection files           = 38 / 38
path/length/hash diff      = 0
projection tree            = 834f4a8c262f834ab8075a63cf05f685e570b407f7d060bc7baa60edbd7a5a4c
manifest sha256            = 846dc277d1d13195806bcebfd5cc2a6824cec4afa62aa761df7346092a8ef91f
manifest byte-equal        = true
evidence cap               = E2
generation qualification  = NOT_EVALUATED
```

两份投影位于 `build/generator-projection-maturity-v55-v125-20260720` 与同名 `-repro` 目录。

### 53.5 边界

组件级 drift 诊断只说明“当前安装的哪一类受信任字节与 prepare 时不同”，不能说明变化内容正确、旧候选自然、学术事实可靠或新版本具有生成资格。它也不授予自动迁移旧运行的权限；任何 drift 仍要求重新 prepare。

## 54. 2026-07-20：NO_CHANGE 理由的分级、去敏修复指引

### 54.1 真实前向暴露的可用性缺口

长 TeX 前向中，两个调用方认为已有位置与功能说明的 `NO_CHANGE` 理由仍被安全拒绝，但旧诊断只给
`NO_CHANGE_reason_generic_or_unlocated`；更短的 v3 理由还可能先落入 legacy 的“四个汉字”提示。
系统没有误放行，却没有把当前 v3 合同——至少 8 个汉字并指出具体功能——稳定地告诉使用者。
这会诱使调用方反复扩写“已经自然”，而不是说明保留对象、条件、模态、并列或段落职责。

### 54.2 分级诊断与兼容边界

finalizer 新增 `_no_change_reason_issue()` 与 `_no_change_reason_error()`，把 v3 失败固定分为：

- `too_short_han`：汉字数少于 8；
- `generic_template`：命中已登记的“保持原样/已经自然”等空泛模板；
- `missing_function_anchor`：长度达到门槛，但没有指出定义、段落、原句、结构、对象、范围、条件、指代、否定、模态、因果、并列、层级等具体功能。

错误合同固定为：

```text
NO_CHANGE_reason_invalid:<issue>;required=min_han_8+specific_function_anchor;reason_redacted=true
```

错误不回显原理由、注入字符串、路径或其他调用方内容。v3 在旧四字兼容门之前执行该合同；v2/legacy
仍保留原有至少四个汉字的兼容行为，避免借诊断升级暗改历史 schema。合法理由仍必须绑定
`evidence_spans`，存在 high signal 时仍须逐项填写 `keep_reasons`，之后仍进入统一验证器和外部成对质量门。

### 54.3 独立前向与二次修复

无答案泄漏的新代理在临时 Markdown 长文上连续提交三轮 v3 `NO_CHANGE`。第一轮四个单元均为
`UNRESOLVED`，观察到 `missing_function_anchor`；第二轮按提示补充具体段落功能后，一个单元进入
`NO_CHANGE`，其余暴露 `too_short_han` 与 `missing_function_anchor`；第三轮四个单元均形成 intent 机械
PASS，但顶层仍为 `DELIVERY REVIEW exit=2 publish=REVIEW_CANDIDATE`，且
`paired_quality_gate_status=PENDING_EXTERNAL_REVIEW`、`humanize_completion_claim_allowed=false`。
原始报告保存在
`C:\Users\Lenovo\.codex\tmp\humanize-no-change-forward-v126\REPORT.md`。

前向同时发现：旧 v1.26 顶层摘要只给 `UNRESOLVED`，精确 code 需要自行打开
`coverage_ledger.final.csv`。因此没有把 v1.26 当作最终版本。v1.27 新增去敏
`unresolved_reason_summary`：给出 total/classified/unclassified、固定 code 计数和
`details_artifact=coverage_ledger.final.csv`；文本摘要也直接输出该相对路径。聚合器只识别固定枚举，
不复制 notes、理由正文或任意调用方字符串。未分类数量不被包装成安全项。

### 54.4 测试与策略升级

新增测试覆盖三类 issue、固定修复提示、理由与 `SECRET-CONTENT` 注入不回显、v3 短理由不再出现
legacy 提示，以及具体功能理由仍可形成 intent 机械 PASS。finalizer 与长文合同属于固定 38 文件生成能力面，
因此重新计算 capability inventory；分级诊断中间版为 1.26.0，纳入前向反馈后的正式版本为 1.27.0。

```text
finalizer focused          = 168 OK (skipped=2)
joint targeted             = 242 OK (skipped=3)
full unittest              = 983 OK (skipped=8)
compileall                 = PASS
quick_validate             = PASS (PYTHONUTF8=1)
git diff --check           = PASS; only LF/CRLF notices
policy / builder           = 1.27.0 / 1.27.0
capability source          = 42aba92eb3571eb4f94028d438808531f1e53562fab4dbc08012d239db42addb
evaluation surface         = f85fa35521dd8c8cc52539e2751bbb52a032d42765136bb15df2a43629939fed
inventory                  = 1adfd38292a8b58974ebbf113c52233456abcba57c18462131fbe5730f05c727
projection files           = 38 / 38
path/byte diff             = 0 / 0
projection tree            = 81a8170a7be64eccedbc868dd0e4621ede610d4377e35fa37f7b2c69e7e88f54
manifest sha256            = 16f165a4bae24b134548f3b44cf113e7e72a2fe0cf2f9d5f9ae59afbfd41927e
manifest byte-equal        = true
evidence cap               = E2
generation qualification  = NOT_EVALUATED
```

两份最终投影位于 `build/generator-projection-maturity-v57-v127-20260720` 与同名 `-repro` 目录；38 个相对路径和逐文件字节完全一致。v1.26 投影只记录前向反馈前的中间状态，不是当前稳定面。

### 54.5 结论边界

分级诊断证明的是失败后更容易采取正确的下一步，并且错误面不泄露理由正文。它不证明某个理由真实、
某段原文已经自然、NO_CHANGE 是最佳文风决策，也不清除 `paired_quality_review_status=PENDING_EXTERNAL_REVIEW`。
单元 intent PASS、983 项测试和双投影复现均不能升级学术正确性、作者身份或 generation qualification。

## 55. 2026-07-20：v1.28 最新尝试权威头、未决原因闭集与运行时去路径化

### 55.1 v1.27 独立前向推翻了哪些“看似已经够用”的假设

在不知道预期输出的独立前向中，调用方得到 12 个未决单元。v1.27 顶层摘要把它们全部显示为
`unclassified`，但 `coverage_ledger.final.csv` 中实际已经存在两类稳定原因：

- `no_change_evidence_spans_must_be_nonempty`：8 项；
- `rewrite_intent_source_spans_must_be_nonempty`：4 项。

这说明 v1.27 的聚合白名单仍不完整：底层有可操作信息，顶层却把它降格成未知原因。前向还发现，已有
`REVIEW/PARTIAL` 候选的运行目录在下一次 finalize 失败后，会继续保留旧
`finalization_metadata.json`；最新失败只写入 `last_failed_attempt_metadata.json`。如果消费者只读取
canonical metadata，就会把“保留下来的上次候选状态”误当成“本次最新尝试状态”。

同一失败链还暴露两个信任面问题。其一，旧 runtime JSON 的 `error` 与 `run_dir` 会回显完整绝对路径；
其二，`processable_scope_complete=true` 可以与 `UNRESOLVED=12` 同时出现，但字段名没有明确说明它只指
“可处理单元是否完成记账”，并不表示所有单元已解决、候选可交付或人文化已经完成。四项缺口均来自真实
前向工件，而不是为新增规则而虚构的单元测试场景。

### 55.2 v1.28 的状态权威合同

finalizer 现在在每次尝试后都写入 `latest_attempt_metadata.json`，并把三个文件的职责拆开：

- `latest_attempt_metadata.json`：最新一次 finalize 尝试的权威状态；
- `finalization_metadata.json`：当前保留的 canonical candidate 状态，失败回滚时允许继续指向旧候选；
- `last_failed_attempt_metadata.json`：最近一次失败尝试的审计副本。

成功或 REVIEW 时，latest attempt 与 canonical metadata 一致，role 为
`CURRENT_AND_LATEST_ATTEMPT_AUTHORITY`。失败且事务恢复旧候选时，latest attempt 与 last failed 一致，
role 为 `LATEST_FAILED_ATTEMPT_AUTHORITY`；旧 canonical metadata 可以保留，但不再能冒充最新尝试。
普通文本摘要同时给出 `latest_attempt=latest_attempt_metadata.json` 和
`canonical_candidate=finalization_metadata.json`，使只读消费者无需猜测文件优先级。

### 55.3 未决原因与运行时错误的有限披露

`unresolved_reason_summary` 的固定白名单新增上述两种空 span 原因。聚合器只输出 code 与计数，不复制
ledger 的 `notes`、原理由、canary 或其他调用方字符串；因此 12 个真实未决可以被准确归为 8+4，同时不
扩大内容泄露面。无法识别的原因仍计入 `unclassified`，不会伪装成安全已分类。

运行时失败不再输出 `error` 或 `run_dir`。JSON 只给固定 `error_code`：`FILE_NOT_FOUND`、
`PERMISSION_DENIED`、`INVALID_ENCODING`、`VALIDATION_ERROR`、`RUNTIME_ERROR`、`OS_ERROR` 或
`INTERNAL_ERROR`，并固定声明 `error_message_redacted=true`、`paths_redacted=true`、
`run_dir_scope=CURRENT_RUN_DIR`。文本错误面只输出错误类型、固定 code、相对元数据文件名和
`content_redacted=true`。恢复逻辑也按 schema、固定 code、error type 与 role 验证最新失败元数据，不再
依赖可能包含路径或私有内容的异常正文。

### 55.4 `processable_scope_complete` 的作用域收窄

成功 metadata 新增：

```text
processable_scope_complete_scope=PROCESSABLE_UNIT_ACCOUNTING_ONLY
processable_scope_complete_does_not_mean_resolved_or_deliverable=true
```

因此该布尔量只能说明“被判定为 processable 的单元已经走完记账流程”。它不能抵消 unresolved、protected、
stale source、paired-quality pending、REVIEW/2 或发布候选限制，更不能被上层 UI 翻译成“全文已完成”。

### 55.5 回归、结构校验与确定性投影

```text
finalizer focused          = 170 OK (skipped=2)
joint targeted             = 245 OK (skipped=3)
full unittest              = 986 OK (skipped=8)
compileall                 = PASS
quick_validate             = PASS (PYTHONUTF8=1)
git diff --check           = PASS; only LF/CRLF notices
policy / builder           = 1.28.0 / 1.28.0
capability source          = 1c8f698554e6278ef8ca02dcbda1dd040b75fe320536e57d0477c3b5a021cb06
evaluation surface         = 2d81250430351230da83c236ac8ec2f09b0966fdfc0c72a9f96890857daaac84
inventory                  = 623ca198505e73313d27f1572d46086c6412007412476825238c5919f1d82ddd
projection files           = 38 / 38
path/size/hash diff        = 0 / 0 / 0
projection tree            = 837ff99f0569a965e2741677e5edecbb0b924a02b938a41ae6a1e7d6cb216411
manifest sha256            = 773d443b020fcc72bdc01280808aa277df7ddf54ea4a5e0067360f8f199b5703
manifest byte-equal        = true (23177 / 23177 bytes)
evidence cap               = E2
generation qualification  = NOT_EVALUATED
```

两份投影位于 `build/generator-projection-maturity-v58-v128-20260720` 与同名 `-repro` 目录。两次独立构建的
38 个相对路径、文件长度、逐文件 SHA-256、tree hash 和 manifest 原始字节均一致。

### 55.6 本轮能证明与不能证明的内容

v1.28 证明的是：最新尝试与保留候选不再混用；已知空 span 原因能在顶层准确聚合；失败元数据不再回显
绝对路径或异常正文；scope-complete 不再缺少机器可读的限定语；这些合同在现有 986 项回归与双投影中可
复现。它仍不证明候选文本自然、学术事实正确、原作者身份成立、外部 paired-quality clearance 已完成，
也不把 E2 投影复现升级为 generation qualification。机械门禁的成熟化继续服务于“拒绝虚假完成态”，而
不是替代人的连续阅读和学术判断。

## 56. 2026-07-20：v1.29 回滚证据断链、绝对路径残留与原因码碰撞修复

### 56.1 v1.28 不能作为稳定完成态的原因

独立只读红队在不查看本报告新增章节的前提下重建了正常 REVIEW、REVIEW_CANDIDATE 与失败回滚链。v1.28
的 latest/canonical 分权主体确实生效，但红队发现三个此前测试没有覆盖的缺口，因此 v1.28 只能视为中间状态：

1. 回滚后的 `latest_attempt_metadata.json` 声称本轮存在 UNRESOLVED，并继续把
   `unresolved_reason_summary.details_artifact` 指向 `coverage_ledger.final.csv`；该文件已经随事务恢复为上一
   canonical candidate 的 NO_CHANGE 台账。最新失败头与它所指证据互相矛盾。
2. failed metadata 仍保留 run-dir 外的 source 绝对路径；`compile_check.command` 也能保存调用方提供的绝对
   可执行文件路径。旧实现只清理有限 path key 且主要判断路径是否位于 run-dir 内，不能支撑“失败元数据已
   去路径化”的广泛声明。
3. `unresolved_reason_summary` 对整段 notes 做子串搜索。调用方只需把白名单 code 用作未知 bundle 字段名，
   实际错误虽然是 `unknown_rewrite_bundle_fields`，顶层仍会误报为空 evidence span。

原始红队工件位于 `C:\Users\Lenovo\.codex\tmp\hac-v128-redteam-20260720-a`。其中 latest 与 last failed
字节一致，canonical 成功保留，说明 v1.28 修复不是全盘无效；问题在于回滚证据引用和脱敏边界仍不自洽。

### 56.2 v1.29 的锚定原因解析

聚合器不再搜索 notes 中任意位置的 code。它只接受固定错误结构：

- 可选且闭集的 `invalid_rewrite_bundle:` 或 `rewrite_intent:` 前缀；
- 紧随其后的 `NO_CHANGE_reason_invalid:<fixed-code>`；
- 或 `invalid_rewrite_bundle:<fixed-empty-span-code>`；
- code 后必须是分号、空白或字符串结尾。

因此真实 NO_CHANGE 分级诊断仍能聚合，未知字段名中包含白名单 code 的碰撞则保持 `unclassified`。这里没有
把 notes 当作结构化数据的长期理想方案；v1.29 只是把现有字符串合同收窄为可审计的固定语法，后续仍可迁移
到显式 `unresolved_codes[]`。

### 56.3 失败记录的严格脱敏与证据断链

`_failed_attempt_record()` 现在递归清空：

- `command`、`cwd`、`stdout`、`stderr`；
- source/before/after/diff/published/rewrite-intent 等全部路径键；
- 任意字段中呈 Windows drive、UNC 或 POSIX absolute path 形态的字符串。

失败头新增 `failed_attempt_sensitive_fields_redacted=true`。由于事务回滚后本轮 final ledger 不再存在，
`unresolved_reason_summary.details_artifact` 固定清空，并写
`details_artifact_status=NOT_RETAINED_AFTER_ROLLBACK`。这样 latest failed attempt 可以保留去敏的 code 与计数，
但不能再诱导消费者打开上一候选的 ledger。运行时异常分支仍使用固定 error code，不回显异常正文。

### 56.4 回归与确定性投影

```text
new focused regressions    = 4 OK
finalizer + projection     = 216 OK (skipped=3)
full unittest              = 987 OK (skipped=8)
compileall                 = PASS
quick_validate             = PASS (PYTHONUTF8=1)
git diff --check           = PASS; only LF/CRLF notices
policy / builder           = 1.29.0 / 1.29.0
capability source          = 366d3ba05cdccf17c6f74899d1ecb5e10a593016eb8b3638ea85ad375d7c1330
evaluation surface         = 3dfef366657a9ebdd527bb2c31a553f807348adb7f32cb04816d4aed6c227464
inventory                  = 31bdb92acd3385b31b0c3eee791df6819e094b0d7cb84b5eb0c04fea9e70918a
projection files           = 38 / 38
path/size/hash diff        = 0 / 0 / 0
projection tree            = 51b825abadacba1493b55347a7430d7105c4c8a37223a24b40fd210fb6e82e6f
manifest sha256            = 6c90e3277c60c3c1ce92b9d2fcbd65714da49de94cbdbd6902811c2699bc1935
manifest byte-equal        = true (23177 / 23177 bytes)
evidence cap               = E2
generation qualification  = NOT_EVALUATED
```

双投影位于 `build/generator-projection-maturity-v59-v129-20260720` 与同名 `-repro`。38 个相对路径、文件
大小、逐文件 SHA-256、tree hash 和 manifest 原始字节完全一致。

### 56.5 剩余边界

红队尚未攻击 failed metadata 自身写入失败、权限失败和独立 runtime-exception 的全部组合；字符串锚定也仍
不是显式结构化错误数组。`processable_scope_complete=true` 在 FAIL、UNRESOLVED 或 REVIEW_CANDIDATE 中仍
可能成立，虽然现已有机器可读 scope 与否定字段，任何 UI 仍必须同时读取 `failed_attempt`、delivery gate、
publish state 和 completion claim，不能单独展示该布尔量。v1.29 提升的是状态与证据诚实性，不证明文本更
自然、学术事实更正确、作者身份成立、paired-quality 已清除或生成资格获批。

## 57. 2026-07-20：v1.30 结构化未决码与 metadata 权威文件组原子化

### 57.1 v1.29 剩余的两个工程性假闭环

代码审计确认 finalizer 有 31 个显式 UNRESOLVED 生产点，而 v1.29 顶层摘要只从 notes 的固定字符串语法中
识别 5 类原因。锚定解析已能阻止普通子串碰撞，但 notes 仍同时承担“人可读动态细节”和“机器状态码”两种
职责；新增分支容易忘记同步 regex，validator reason、字段名或异常文本也始终是潜在污染源。

另一个缺口位于 metadata 发布顺序。成功路径先写 `finalization_metadata.json` 再写 latest；失败路径先写
last failed 再写 latest。第二个文件写入失败时，第一个文件可能已经变成新状态，形成 authority pair 分裂。
若整个目录不可写，失败记录也无法落盘，而旧 main fallback 会缺少“run 已恢复但失败头未持久化”的准确证据。

### 57.2 31 个生产点统一进入闭集 code registry

v1.30 新增 `humanize-unresolved-code/v1` 和固定 `UNRESOLVED_CODE_VALUES`。所有 31 个显式 UNRESOLVED 分支，
以及 prepare 已冻结为 UNRESOLVED 的初始单元，都写入 `unresolved_codes`。code 只能来自 registry；传入拼接了
decision、字段名、span ID、validator reason 或用户字符串的动态 code 会触发内部断言。

主要 code 家族覆盖：bundle/chunk/Voice binding、NO_CHANGE 理由与 intent、keep reason、warning proposal、
validator、paired-quality request、结构计划、保护占位符、非结构 scope、结构事务回滚、文档覆盖不足和跨单元
重复。空 evidence/source span 拥有独立 canonical code，不需要再检查 notes 正文。

顶层 `unresolved_reason_summary` 新增：

```text
structured_code_schema=humanize-unresolved-code/v1
structured_code_source=UNIT_UNRESOLVED_CODES
structured_classified / structured_unclassified
structured_code_counts
```

旧 `codes/classified/unclassified` 暂时作为五类兼容 alias 保留。旧 run 缺结构化数组时只允许严格锚定的历史五
类 notes 迁移；未知 notes 不猜测。final ledger 新增 `unresolved_codes_json`，按 canonical JSON 数组写出，
不使用 Python repr。文本摘要追加固定 `unresolved_code_counts[...]` 行，动态 notes 不进入 stdout。

### 57.3 metadata authority group 的全组恢复

新增 `_write_json_group_atomic()`：写入前保存组内每个文件的“原字节或不存在”状态；任一成员写入失败，所有
成员恢复原字节。它用于两组权威文件：

- 成功/REVIEW：`finalization_metadata.json + latest_attempt_metadata.json`；
- 失败/回滚：`last_failed_attempt_metadata.json + latest_attempt_metadata.json`。

测试故意让第二个文件失败，确认第一个文件不会留下新字节。更深一层的测试让 latest 在正常候选和失败记录
两轮写入中都抛出 `PermissionError`：整个 run-dir 恢复到调用前哈希，三个 metadata 文件均不产生半状态。
异常对象携带去敏的内存 failure metadata，main 优先使用它，输出
`attempt_metadata_persistence_status=FAILED; paths_authoritative=false`；磁盘旧 latest 不再冒充本次尝试。

### 57.4 回归与投影

```text
new focused regressions    = 8 OK
finalizer focused          = 176 OK (skipped=2)
joint targeted             = 250 OK (skipped=3)
full unittest              = 991 OK (skipped=8)
compileall                 = PASS
quick_validate             = PASS (PYTHONUTF8=1)
git diff --check           = PASS; only LF/CRLF notices
policy / builder           = 1.30.0 / 1.30.0
capability source          = 99cbcb70dd683a30e71f7bb9cfbe0d8bf31631cb6e45944fe18951fad654f9c5
evaluation surface         = a41b8fba31700e5000bb180eeceaf83579da177089b845bae59ecd10506189cc
inventory                  = 7c3b62087c30fe410f455cc7b709392a24688ceac2f400f71a0fd6353c860667
projection files           = 38 / 38
path/size/hash diff        = 0 / 0 / 0
projection tree            = 8be8553296f0d1c0bf442187fd638679ae6ec9ced11f2a5bbde99a3e5aedda27
manifest sha256            = 24516cb5e52b84c4f19e3b745f7681ad11b64c3b410e9116dc2d124192357710
manifest byte-equal        = true (23177 / 23177 bytes)
evidence cap               = E2
generation qualification  = NOT_EVALUATED
```

双投影位于 `build/generator-projection-maturity-v60-v130-20260720` 与同名 `-repro`。38 个文件逐路径、逐大小、
逐 SHA-256 相同，manifest 原始字节一致。

### 57.5 剩余边界

当前原子组恢复属于进程内 best-effort rollback，不是操作系统级多文件事务；若写入失败同时伴随恢复写入失败、
进程断电或磁盘损坏，仍需更强的 journal/rename 协议。结构化 registry 已覆盖当前 31 个显式生产点，但未来新增
UNRESOLVED 分支仍应由静态测试强制要求 code；目前尚未加入 AST 级“status 赋值必须邻接 code”门。
这些改动证明状态更可审计，不证明文本自然度、学术正确性、作者身份、paired-quality clearance 或生成资格。

## 58. 2026-07-20：v1.31 静态原因码门、恢复失败权威与 CSV 安全边界

### 58.1 本轮攻击 v1.30 的完成态

独立只读红队没有读取本报告，直接从安装版 finalizer 构造故障模型。它确认 v1.30 仍有四个审计缺口：authority
group 恢复异常被吞；run-state 恢复失败后可能读取磁盘旧 latest；CSV 中的来源派生文本可能被表格软件解释为
公式；未来新增 `unit["status"]="UNRESOLVED"` 分支时没有静态门强制写 registry code。旧测试没有覆盖这些解释层和
恢复层故障，因此“991 项全绿”不能排除它们。

### 58.2 staged replace 与显式恢复失败

`_write_json_group_atomic()` 不再直接覆盖权威文件。每个 payload 先写入目标目录内的独立 staging 文件，flush/fsync
后才逐项 `os.replace`。任一 replace 失败，所有成员按调用前原字节或“不存在”状态恢复；恢复旧字节也使用同目录
staging + replace。恢复异常不再静默 `pass`，而是升级为 `metadata authority group rollback failed`。

该实现收窄了普通进程内异常的半写窗口，但仍不是跨文件、断电安全的数据库事务。SIGKILL/掉电发生在两个 replace
之间时，当前没有持久 journal 或单一 commit pointer 可供重启恢复。

### 58.3 恢复失败不再复用旧 latest

finalize 的两个 `_restore_run_state()` 入口都单独捕获恢复异常。失败时只构造本次异常对象携带的去敏内存记录，固定：

```text
run_state_restore_status=FAILED
run_state_restore_error_code=RUN_STATE_RESTORE_FAILED
attempt_metadata_persistence_status=FAILED
attempt_metadata_paths_authoritative=false
```

main 已删除“读取磁盘 latest，并用 error type/code 猜测是否属于本轮”的兜底。即使旧 latest 恰好也是
`PermissionError/PERMISSION_DENIED`，也不能再贡献本次时间、路径权威或恢复状态。

### 58.4 AST 原因码覆盖门

新增 AST 回归解析安装版 finalizer，遍历所有把 `unit["status"]` 赋为 `UNRESOLVED` 的语句。每个赋值所在控制块
必须在 `continue/break/return/raise` 前调用 `_add_unresolved_code`，否则测试按源码行号失败。这把“当前 31 个点
人工补齐”升级为“未来新增点也必须显式登记”。该门只证明同分支存在 registry 调用，不证明 code 的语义选择正确。

### 58.5 CSV 与旧 ledger 合同

所有 `_write_csv()` 文本单元在首字符为 `= + - @ TAB CR` 时统一前置单引号，避免 Excel/LibreOffice 把审计文本
解释为公式或外链。新增测试覆盖 `=HYPERLINK(...)`、`+SUM(...)` 与普通 note。

旧 final ledger 读取改为显式兼容入口：必须含 `unit_id/status`，unit ID 非空且唯一，status 属于当前闭集。缺列、
重复 ID 或未知状态直接拒绝；缺少新 `unresolved_codes_json` 但具备旧核心列的历史 ledger 仍可读取。

### 58.6 验收与双投影

```text
new focused regressions    = 8 OK
finalizer focused          = 182 OK (skipped=2)
projection focused         = 44 OK (skipped=1)
joint targeted             = 306 OK (skipped=5)
full unittest              = 997 OK (skipped=8)
compileall                 = PASS
quick_validate             = PASS (PYTHONUTF8=1)
git diff --check           = PASS; only LF/CRLF notices
policy / builder           = 1.31.0 / 1.31.0
capability source          = 14df16e3e0d8c813ac67004657482fe8a418fd636934137187310bd28c054fa6
evaluation surface         = 8e4dca8a88d18d69cad35dd04293c8d3a744f93f84415b5ecddbc638dd8b228e
inventory                  = 3ad01aa602ae02859a4be7f4b0ab7e2fec0225cd3bec6628a53cf4ee19501d28
projection files           = 38 / 38
path/size/hash diff        = 0 / 0 / 0
projection tree            = fd31cb30a923a4409a0ee87e9dca243cd36727fd061fc001e6f76b4167a81ac8
manifest sha256            = 435d963e3082e13cbe625850cd3c3811278a741de4bcba06b6b98b55056a0a02
manifest byte-equal        = true (23177 / 23177 bytes)
evidence cap               = E2
generation qualification  = NOT_EVALUATED
```

双投影位于 `build/generator-projection-maturity-v61-v131-20260720` 与同名 `-repro`，38 个文件逐路径、逐大小、
逐 SHA-256 一致，两个 manifest 原始字节一致。

### 58.7 未关闭边界

v1.31 尚无跨进程崩溃恢复 journal，也没有把 rendered/validation/diff/ledger/metadata 收敛为单一 generation 目录
与原子 commit pointer；强杀或断电仍可能留下跨目录半发布。AST 门不验证 code 与失败语义的一一对应。CSV 单引号
转义适合人工审阅；若未来要求字节语义完全无损的机器权威，应增加 canonical JSON ledger，把 CSV 定义为安全审阅
投影。本轮只提高状态、恢复和审计可信度，不证明自然度、学术正确性、作者身份、paired-quality clearance 或
generation qualification。

## 62. 2026-07-20：v1.35 长文运行错误契约与真实盲用闭环

### 62.1 prepare 的 exit-2 混同、路径泄漏与半成品目录

本轮先从实际 CLI 调用复现，而不是只读源码推断。旧 `prepare_humanize_long_document.py` 在输入不存在时由
argparse 风格路径退出：OS exit 为 2，和合法业务态 `REVIEW/2` 混同；stderr 会带出完整私有路径；更严重的是，
输入预检之前已经创建输出目录，留下看似可继续使用的半成品。这三个现象会共同诱发“把输入错误当人工复核”、
“日志泄露宿主路径”和“残留目录冒充有效 run”三类假闭环。

修复后，输入读取及调用合同错误统一输出去路径化的结构化 `FAIL/1`，并在任何输出写入之前完成输入 `stat()`、
输出目标存在性、editable wrapper、intensity 与 transaction 合同预检。稳定错误码包括：
`INPUT_ENCODING_INVALID`、`INPUT_NOT_FOUND`、`INPUT_PERMISSION_DENIED`、`INPUT_JSON_INVALID`、
`INPUT_READ_FAILED` 和 `INPUT_CONTRACT_INVALID`。真实缺文件复测结果为：

```text
OS exit_code = 1
status = FAIL
delivery_gate_status = FAIL
publish_state = FAILED
error_code = INPUT_NOT_FOUND
output_exists = false
stderr/private_path_leak = false
completion claims = false
```

这只证明运行期错误分类、写前预检和路径抑制已按测试合同生效；不把错误处理可靠性解释为改写质量。

### 62.2 独立长文盲用：流程可用，但候选质量被正确拦截

独立代理使用安装版 Skill，对 `physics2.tex` 第 443–517 行的连续课程讲义材料完成
`prepare -> scaffold -> 人工填写 bundle -> finalize`。GPT 来源 TeX 仅作为任务输入和压力材料，不作为真人 Voice、
正向句库或事实证据。源文件保持不变，试验副本位于 `.codex/tmp`。最终结果为：

```text
prepare = READY
editable units = 2
protected spans = 82
finalize delivery_gate_status = REVIEW
publish_state = PARTIAL
exit_code = 2
DONE = 1
UNRESOLVED = 1
source_files_modified = 0
```

未决单元触发 `SPEECH_ACT_NEGATION_CHANGED` 以及 modality/condition scope 告警。连续原文中的
“只有先……才不会……”和“只有当……才……”承载否定、必要条件和论证强度；代理候选没有完整保留这些力度。
因此本例不是 finalizer 的误杀证据，而是 authoring 质量不足被 fail-closed 门识别的正向证据。系统保持
`humanize_completion_claim_allowed=false`、`coverage_completion_claim_allowed=false` 和
`full_completion_claim_allowed=false`，没有用 1 个 DONE 掩盖另 1 个 UNRESOLVED。

### 62.3 盲用暴露的可发现性摩擦及修复

盲用首次把 `<empty-rewrites-dir>` 理解成“预先创建的空目录”，而实现安全合同要求目标路径尚不存在；首次还使用
了裸 `COURSE-*` target signal，finalizer 正确拒绝，合法形式应为 `SCENE-COURSE-*`。这些不是放宽安全门的理由，
但说明正确用法此前不够容易发现。本轮已完成：

- 文档统一改为 `<nonexistent-rewrites-dir>`，CLI `--output` 明示“该路径必须尚不存在”；
- scaffold JSON/text 输出公开权威 target signal 前缀和 `STYLE-EMPTY-ENDING`、`SCENE-COURSE-RHYTHM` 示例；
- 前缀由 finalizer 权威常量提供，避免文档与实现各自维护；
- 测试锁定 `SCENE-COURSE-RHYTHM` 接受、裸 `COURSE-RHYTHM` 以
  `rewrite_intent_target_signals_invalid` 拒绝；
- 测试锁定已存在空目录返回结构化 `FAIL/1`、不泄漏路径、不写入且保持原目录身份；
- policy snapshot drift 的恢复说明改为：使用当前安装版重新 prepare 到新的 run 目录，旧 run 只保留诊断，
  不继续 scaffold/finalize。

target signal 语法通过仅表示 authoring 标记可解析，不证明病灶真实、改写有收益或候选可交付。外层执行包装器偶尔把
子进程 exit 2 显示成笼统失败，属于包装层呈现问题，本轮没有在 Skill 内伪造兼容逻辑。

### 62.4 v1.35 回归与 v67 双投影

```text
focused prepare/scaffold/finalize = 301 OK (skipped=4)
full unittest = 1047 OK (skipped=8)
projection specialty = 44 OK (skipped=1)
compileall = PASS
quick_validate = PASS (PYTHONUTF8=1)
git diff --check = PASS（仅既有 CRLF 提示）
SKILL.md = 499 lines

primary = build/generator-projection-maturity-v67-v135-20260720
repro   = build/generator-projection-maturity-v67-v135-20260720-repro
files = 38 / 38
path/hash/byte differences = 0
manifest_bytes = 40739 / 40739
manifest_raw_byte_equal = true

capability_source_sha256 = a78cbdc394ee9286b37c9bef56b14144c0687d13345e6261ed45a47d40f7fbc4
evaluation_surface_sha256 = b74a8bfe67251933907ce6e3cddd460d9edd72584628d894ba74d6622e2dec2e
inventory_sha256 = 1ad4d473d82052245c10a0cf93d169ca651f9e8588930a873c435dc5a46f1ebf
projection_tree_sha256 = 1769737cc0a86001a02060d4b43504e716654e4eddcf6e233a502dcbf16aa531
manifest_sha256 = 0662b8fab0985f20a71ca27c7061df61ae19c7c2ef88bbf37507eb34bbacb4c6
```

全量输出中的 argparse usage 来自故意攻击非法缩写参数的测试，权威结果以最终 `Ran 1047 tests ... OK` 为准。
上述证据支持 v1.35 当前 capability surface 的错误合同、门控状态和投影复现性；仍不证明自然度、学术正确性、
作者身份、paired-quality clearance、外部隔离或 generation qualification。

## 59. 2026-07-20：v1.32 完整 run-state 双镜像恢复与虚假提交拦截

### 59.1 v1.31 为什么仍不能承受强杀

v1.31 已把三份 metadata 收敛到 authority group，但 rendered、validation、diff、final ledger、rollback
manifest 等非 authority 工件仍依赖进程内 `_restore_run_state()`。若进程在删除旧 validation 后、安装新目录前，
或在 rendered 已发布而 ledger 尚未发布时被强杀，下一次启动没有持久证据判断应保留 base 还是 next。更危险的是，
早期 run-state v1 只保存 base image；authority pointer 已切到 next 后，仅凭 transaction ID 与 generation 接受
live 现场，没有证明 live 的非 authority 闭包就是与该 pointer 同代的 next。

独立 journal 红队据此构造了跨代混合、cleanup 绕过、image hash/type 篡改、第三 pointer、nested 前缀误删、
staging 前缀碰撞和缺 run-state journal 仍发布 authority 等攻击。最初的 v1.32 草案虽通过 205 项 finalizer
测试，仍被推翻；测试绿色没有被用来替代协议级证据。

### 59.2 `humanize-run-state-journal/v2`

最终协议同时封存两个完整 image：

- `base/`：本次 finalize 开始前的全部非 transient 工件；
- `next/`：authority pointer 切换前、已经完成候选发布的全部非 transient 工件。

闭包不再只是文件 hash map，而是规范相对路径到严格 descriptor 的映射。文件记录 `bytes + sha256`，目录记录
`type=directory`，因此空目录和 file/directory 类型变化也进入恢复合同。复制前源、复制后源与 image 三者必须完全
一致；symlink、junction/reparse point、hardlink 和特殊文件在封存前拒绝。

authority writer 在创建 authority journal、安装 metadata 或替换 commit pointer 之前，必须预检匹配 transaction ID
的 run-state journal。之后它先生成精确 next authority commit，封存 next image，并把 commit SHA/generation 与
next closure 写入 run-state journal；只有这些步骤完成后，authority group 才能进入自己的 PREPARED 发布流程。
因此“缺 journal 时先修复 authority，再报缺失”也被禁止，原崩溃证据保持字节不变。

### 59.3 pointer-selected repair 与 cleanup marker

恢复只允许两个裁决：pointer 精确等于 base commit 时重装 base image；pointer 精确等于已绑定 next commit 时重装
next image。live 可能因第二次中断处于部分删除、部分复制或其他第三字节态，此时可以由所选密封 image 幂等修复；
但 pointer 本身属于第三 generation、selected image 缺件、hash/type 漂移、next binding 部分存在或 transaction
闭包异常时，不覆盖 live，保留 journal/image 并硬失败。

cleanup 也被纳入恢复协议。删除 transaction image 前重新验证 pointer-selected closure，再写入绑定 transaction ID、
authority pointer SHA 与 selected live closure 的 cleanup marker。journal 删除后，无论 transaction 目录尚未删除、
删除到一半或已经删除，重启都先验证 marker、pointer 与 live closure，再幂等完成剩余清理。两侧
`KeyboardInterrupt` 故障注入均已覆盖。

### 59.4 命名空间与 fail-closed 边界

红队发现把 `.humanize-run-state-` 解释为任意路径组件会漏掉普通嵌套工件，例如
`docs/.humanize-run-state-notes.txt`，恢复时可能永久删除。v1.32 将基础设施语义限定为 run 根目录的首组件，
取消递归 `copytree` ignore；嵌套同名前缀现在进入 base/next image 并恢复。无 journal 时只把精确
`.humanize-run-state-<24 位小写十六进制>` 识别为 orphan transaction，宽前缀普通文件不再阻断。

journal/cleanup staging 残留不能仅凭前缀认证。遇到模糊碰撞时保留原文件并 fail closed，不自动删除用户字节。
这牺牲了对无法认证 staging 残片的自动清理，但避免以恢复名义吞掉普通文件；调用方必须人工审计后再继续。

### 59.5 本轮验证证据

```text
focused run-state attacks = PASS
finalizer                 = 216 OK (skipped=2)
five-module joint         = 368 OK (skipped=5)
full unittest             = 1032 OK (skipped=8)
compileall                = PASS
quick_validate            = PASS (PYTHONUTF8=1)
latest journal red-team   = no remaining P0/P1
```

新增测试覆盖 base/next image hash 与类型篡改、第三 pointer 不改 live、next pointer 修复第三 live 闭包、
CLEANUP 重新校验、transaction 删除前后强杀、nested 前缀保留、staging 碰撞保留、宽 orphan 前缀不误伤、
缺 journal 不发布 authority，以及已有 authority crash journal 时预检仍保持全部证据不变。

### 59.6 能证明与不能证明的内容

v1.32 证明的是：在受控本地文件系统、单工具锁与非恶意同权限环境中，当前测试覆盖的进程异常和重启路径可以按
唯一 authority pointer 恢复文件内容、存在性和 file/directory 类型闭包，并拒绝无法裁决的第三状态。它不恢复
ACL、owner、mtime、xattr、NTFS alternate streams，不抵御恶意同权限写者同时伪造 pointer/journal/images，
不证明文件系统整体快照未回退，也不把单机故障注入夸大成物理掉电持久顺序证明。

更重要的是，事务可靠性与文风质量仍是正交问题。上述 PASS、1032 项测试、双镜像恢复或投影复现都不证明
文本更自然、学术论证正确、作者身份真实、paired-quality clearance 已取得或 generation qualification 已完成。

### 59.7 v1.32 双投影发布记录

本轮在 capability source hash 固定后独立生成两份 generator projection：

```text
primary = build/generator-projection-maturity-v64-v132-20260720
repro   = build/generator-projection-maturity-v64-v132-20260720-repro
files   = 38 / 38
```

两份 manifest 均为 40,739 bytes，原始字节逐字节相等；不是只比较排序后的字段或投影树摘要。共同发布证据为：

```text
capability_source_sha256 = 122d1f1e811236c3fe6ace95ae31008270acc305f88aad031a036054981dc6ce
evaluation_surface_sha256 = 053718e614f3ef06b97db97ac1929830f5589bbfdf48a96ffdeb1b2aa3338652
inventory_sha256 = c1e14b1b7a36baeefb66ae66c7169b43fa19384a43ffee4007488159c5f0ba43
projection_tree_sha256 = 68cf065ab34b7157ad59dc8672538b89a4dd59b1d1f05ce6eb71ac27a81db47d
manifest_sha256 = 338c0b4bd386ab28b699b3a553107fb0da872562f00f43972c60e9a9d24097a0
```

两次构建的路径集合、文件大小、文件 hash 与 manifest bytes 均无差异，manifest 中的 compile、import closure、
reference closure、quick validate、reparse point、casefold collision、forbidden reference 与 secret-control identifier
审计均为 `PASS`。这证明当前投影构建在该输入与环境下可复现，并证明投影记录绑定到了同一 capability/evaluation
surface；它仍不证明投影内生成器产出的文字自然、论文事实正确或具有作者本人身份。

## 60. 2026-07-20：v1.33 真实短文盲测、路径隐私与命令可移植性

### 60.1 盲测推翻机械假完成

独立代理直接使用安装版 Skill 处理 `cet6/test.tex` 第 96—98 行，候选仍保留“顺应了时代的演变”“个人/社会破局的关键”
和“必须持之以恒地践行这一趋势”，却报告机械验证 PASS。这证明普通词组合成的口号链可以绕过单词级规则，也再次证明
validator PASS 不能替代连续阅读。v1.33 扩展 `LEX-MARKET-01` 与 `HUM-09`，覆盖“顺应时代发展/演变/潮流/趋势”、
“个人/社会/行业/组织……破局的关键”和“持之以恒地践行/推进/贯彻”；测试要求组合链至少产生三个 finding，同时保护
“判断函数单调性的关键……”等专业表达不被误报。

### 60.2 两个 P1 调用链缺口

旧命令 `python scripts/...` 依赖 CWD；在论文目录复制后，Python 找不到脚本返回 OS exit 2，而 Skill 又把 exit 2 定义为
合法 `REVIEW`。validator 的缺文件、非法 UTF-8、无效 JSON 与调用合同错误此前也可能落入 exit 2。当前全部改为无路径的
结构化 `FAIL/1`：`INPUT_NOT_FOUND`、`INPUT_PERMISSION_DENIED`、`INPUT_ENCODING_INVALID`、
`INPUT_JSON_INVALID`、`INPUT_READ_FAILED`、`INPUT_CONTRACT_INVALID`；只有真实业务待复核继续使用 `REVIEW/2`。

旧 detector scope 在成功 JSON 中保存绝对 `report_path/source_path`，异常与输出写入失败也可能泄漏路径。schema 1.1
未持久化时只输出 `<LOCAL_*_NOT_PERSISTED>`；持久化时仅保存以 scope 父目录为基准的相对 locator。validator 兼容旧绝对
locator，但对新 locator 强制目录内解析，`../outside.html` 固定失败。读取、边界和写入失败分别使用
`INPUT_READ_FAILED`、`SCOPE_OUTPUT_BOUNDARY_INVALID`、`SCOPE_OUTPUT_WRITE_FAILED`，不回显路径、文件名或异常正文；
Voice builder 同样只公开稳定 error code。

### 60.3 命令可移植性与回归门

Skill 先固定 `$skillRoot = Join-Path $HOME '.codex\skills\humanize-academic-chinese'`，SKILL 与全部主要 reference 命令均改为
`python "$skillRoot\scripts\..."`。静态测试扫描安装版文档，禁止重新出现 `python scripts/`；`SKILL.md` 保持 499 行。

```text
focused detector/validator/voice/lexicon/skill = 176 OK
projection/audit/trial/capture                 = 126 OK (skipped=1)
full unittest                                  = 1042 OK (skipped=8)
compileall                                     = PASS
quick_validate                                 = PASS (PYTHONUTF8=1)
git diff --check                               = PASS（仅既有 CRLF 提示）
```

### 60.4 v65 双投影

策略版本升至 `1.33.0`，评测合同绑定升至 `2026-07-20.21`，requirements 升至 `2.11.0`，oracle catalog 升至 `1.12.0`。

```text
primary = build/generator-projection-maturity-v65-v133-20260720
repro   = build/generator-projection-maturity-v65-v133-20260720-repro
files = 38 / 38; manifest_bytes = 40739 / 40739; raw_byte_equal = true
capability_source_sha256 = 20c461d1a425e2f69daf9ded8de746c459b5fcb6cf6c3dffdd734104645c3cc4
evaluation_surface_sha256 = a90b12e143ca00968adc1d99d3e56c4ceccc15bfc123aa2cb7ee60aa39d8c19b
inventory_sha256 = 98c3bc542b7a886621f8d4aaa3138ccb4fa59ac40ed39a2be757c5942f025680
projection_tree_sha256 = e151ddfc81a705d7fc5bde615881db22635d6eb1bc1f2a31ef601a07153d7cec
manifest_sha256 = d3950036bf0889c5ead933b5661b4f144ba8592675125af67fbd963fc02600f2
```

两份投影的路径、逐文件字节和 manifest 原始字节完全一致。该证据只证明当前绑定与构建可复现，不证明自然度、学术正确性、
作者身份、paired-quality clearance 或 generation qualification。

## 61. 2026-07-20：v1.34 Windows UTF-8 CLI 闭环与低误报前向验证

### 61.1 唯一非 UTF-8 `--help` 入口

对安装版 `scripts/*.py --help` 做非 UTF-8 Windows locale 审计时，发现
`scaffold_humanize_rewrites.py` 是唯一不能由 UTF-8 自动化稳定解码的入口。脚本正文与业务输出虽然使用
UTF-8，但 argparse 的中文帮助仍继承 Windows 控制台编码；调用方若统一按 UTF-8 捕获，会得到
`UnicodeDecodeError` 或乱码。该缺口不改变 Humanize 算法，但会破坏跨 CWD、父进程封装和自动化帮助探测，
因此属于真实 CLI 互操作性问题，不能用“主流程能跑”忽略。

修复在 `main()` 解析参数之前显式把可重配置的 `stdout/stderr` 设为 UTF-8，并新增
`test_cli_help_is_utf8_from_non_utf8_windows_locale`。全脚本审计结果由修复前唯一失败：

```text
scaffold_humanize_rewrites.py  0  UnicodeDecodeError
```

变为：

```text
all scripts --help non_utf8_help = []
scaffold tests = 51 OK (skipped=2)
```

这里的“0”是脚本进程退出码，说明旧状态尤其危险：进程表面成功，但调用方无法可靠读取帮助文本。修复后既要求
退出码正确，也要求捕获字节可按 UTF-8 严格解码，避免把静默乱码当作成功。

### 61.2 真实段落低误报前向验证

独立代理使用安装版 Skill 处理 `cet6/CET6.tex` 第 50 行“节俭”段落。该 TeX 来源归属为 GPT 生成，故只作为
任务输入和负例/低误报压力材料，未作为真人 Voice、正向句库、事实证明或 production positive action card。

该段包含三个容易被粗糙“禁词表”误伤的表达：有明确主体和对象的“中国政府持续加强节约型社会的建设”、
有明确宾语的“推进资源循环利用”，以及必须逐字保护的直接引语“光盘行动”。实际结果为：

```text
scanner findings = 0
protected quote ranges = 1
mechanical_validation_status = PASS
delivery_gate_status = REVIEW
OS exit_code = 2
paired_quality_review_status = PENDING_EXTERNAL_REVIEW
academic_correctness = NOT_EVALUATED
```

连续阅读只定位到“理念/生活方式/生活理念”和“节约型社会的建设”的局部复用；候选把第一处政策动作改为
“持续推进节约型社会建设”，保留持续性、主体和对象，并原样保留“推进资源循环利用”和完整引语。该例支持
一个有限结论：当前规则没有把“持续/推进”机械设为禁词，能够在这个具体段落中保留有对象的正常政策动作。
它不证明所有同类表达都不会误报，也不证明改后段落已经比原文自然；paired-quality 仍待可信外部复核。

### 61.3 未形成证据的长文前向尝试

长文 usability 前向代理两次因平台 `stream disconnected` 中止，没有产出可重放任务记录。该现象既不记为
Skill 缺陷，也不记为 Skill 通过：平台断连没有证明脚本、规则、长文 finalizer 或生成质量的任何一方状态。
因此 v1.34 只归档已实际形成原始产物的短文低误报结果；长文实用性仍保留为后续待测面。

### 61.4 v1.34 回归门

`scaffold_humanize_rewrites.py` 属 capability surface，策略版本和 builder 同步升至 `1.34.0`，并重算 capability
source。当前验证结果为：

```text
full unittest                         = 1043 OK (skipped=8)
projection specialty                 = 44 OK (skipped=1)
compileall                            = PASS
quick_validate                        = PASS (PYTHONUTF8=1)
git diff --check                      = PASS（仅既有 CRLF 提示）
all scripts --help non_utf8_help      = []
SKILL.md                              = 499 lines
```

全量测试中的 argparse usage 文本来自故意攻击非法参数的用例，不是失败；权威结论以最终
`Ran 1043 tests ... OK (skipped=8)` 为准。

### 61.5 v66 双投影复现

在 capability source 固定后独立生成：

```text
primary = build/generator-projection-maturity-v66-v134-20260720
repro   = build/generator-projection-maturity-v66-v134-20260720-repro
files = 38 / 38
path/hash/byte differences = 0
manifest_bytes = 40739 / 40739
manifest_raw_byte_equal = true

capability_source_sha256 = d1fe8f8901af8a0949d7b4f369c463db25671c315b444fec0caf6c1167a2d378
evaluation_surface_sha256 = 4ec4182a32c0413527c23e62b95d335876cd809b8007b9d469530b452ae0ecec
inventory_sha256 = d7993a8ad917bf7a98ab62101e46037460f936b056f565a95d4d9eff90a69ed1
projection_tree_sha256 = 489d391508f2c1df312c1218b33c1701cf380bf2a04f6bdecb69bfbcef1a0594
manifest_sha256 = c143128c2878029eb2d13c956e953065d79e95de6d29dafb3ffa9a3e66d770db
```

manifest 内 compile、import closure、reference closure、quick validate、reparse point、casefold collision、
forbidden reference 与 secret-control identifier 审计均为 `PASS`。这组证据只证明当前 v1.34 capability/evaluation
surface 的构建闭包可重复；不证明自然度、学术正确性、作者身份、paired-quality clearance、外部隔离或
generation qualification。

## 63. 2026-07-20：v1.36 TeX 保护边界、引语、命令参数与错误输入红队

### 63.1 `$$...$$` 与 `$...$` 相邻时的数学遮罩越界

长文前向样本在同一段中连续出现 display math 的 closing `$$`、中文正文和多个 inline math。旧 inline-math
正则只禁止起始 `$` 的后邻也是 `$`，没有禁止前邻 `$`；因此 closing `$$` 的第二个字符会被误认成新 inline
math 起点。真实后果不是单纯多保护一个符号，而是同时破坏两侧边界：后续 `F = 6t`、微分项等公式裸露在
`masked_text` 中，可被生成器改写；从错误起点到后续某个 `$` 之间的中文“将力”“一并代入”等反而被吞入
保护跨度，失去可编辑性。

修复把 inline math 起点改为同时要求前后都不邻接 `$`：

```text
(?<![\\$])\$(?!\$)...(?<!\\)\$(?!\$)
```

新增 `test_adjacent_display_and_inline_math_do_not_cross_mask_boundaries`，并用
`%USERPROFILE%\.codex\tmp\v136_long_forward\input.tex` 重新执行 prepare。修复前错误地生成 53 个保护跨度；
修复后为 48 个，chunks 中不再出现裸露的 `F = 6t`，而相邻中文仍留在可编辑正文。保护跨度数量下降本身不是
正确性证明；决定性证据是每个公式回到数学保护区、相邻中文不再被跨界吞并，以及对应回归测试直接锁定该交界。

### 63.2 多行中文直接引语不得按行拆散

旧中文单双引号、`「」`、`『』` 保护匹配受单行边界限制。红队把跨行引语内部“乙项”改成“丙项”后，hard 与
mechanical 都可能 PASS，顶层仅因 paired-quality pending 保持 REVIEW；这意味着硬不变量没有真正识别引语漂移，
不能把 REVIEW 当作已拦截该攻击。修复后 scanner 将跨行成对引号识别为一个完整 protected span，invariant checker
对前后引语内容做逐字比较。真实复测结果为：

```json
{"case":"multiline_quote","status":"FAIL","exit_code":1,"hard":"FAIL","codes":["DIRECT_QUOTATION_CHANGED"]}
```

新增的 scanner 与 validator 测试分别证明“保护跨度完整”和“改写被硬拒绝”，避免只测其中一层。

### 63.3 自定义引用包装器和普通 TeX 命令参数默认全保护

旧逻辑偏重已知 citation/critical command 名单，导致两个可操作绕过：把
`\mycite{potter1994cooperative,de1995evolving}` 的第二个 key 换掉，或把 `\textbf{甲项}` 改为
`\textbf{乙项}`，hard/mechanical 均可能 PASS。前者能静默改变文献身份，后者说明普通 TeX 参数也没有被纳入
默认结构不变量。

当前 prepare 会解析所有 TeX 控制序列及其连续 `[]/{}` 参数，支持多可选参数、多必选参数与嵌套组，并把完整
调用作为保护跨度；invariant checker 使用同一更宽的命令调用模型比较前后结构。自定义名称以 `cite` 结尾时还会
进入 citation 识别，但保护不再依赖它是否命中 citation 名单。两类真实攻击修复后均为：

```json
{"status":"FAIL","exit_code":1,"hard":"FAIL","codes":["CRITICAL_LATEX_COMMAND_CHANGED"]}
```

唯一显式例外是用户在 prepare 时用 `--editable-style-wrapper` 授权 `textbf`、`emph` 或 `textit` 的包装格式清理；
默认不传时仍全保护。该授权只开放包装命令，不开放 citation、标题、标签、数学，也不赋予改变内部文字语义的权限。
finalizer 的 fragment、transaction 和 full-document invariant 均继续传递同一授权清单，防止 prepare 开放而
收尾阶段误用不同合同。

### 63.4 空泛 finding 豁免不再成为通行口令

旧 keep-reason 校验没有覆盖“此处表达功能需要保留”这一类看似完整、实则没有指出主体、语境、术语义或具体
功能的理由。红队可用该句让 high finding 从 REVIEW 降为 PASS。当前 vague-reason 规则显式拒绝“此处/这里/该处/
本处/此项/该项 + 表达/内容/语句 + 功能需要/应当/必须保留”等变体，并由
`test_keep_reason_requires_specific_chinese_reason` 锁定。豁免仍允许，但必须给出可审计的具体语境理由；该门只
证明理由不为空泛，不证明理由真实，可信复核仍不能由提交者自签。

### 63.5 decision-map 输入失败统一 `FAIL/1` 且不泄漏路径

scaffold 旧路径在 `--decision-map C:\private-user\secret-map.json` 缺失时会原样回显完整本地路径。当前新增
`ScaffoldInputFailure`，把输入面分成六个稳定错误码：

```text
DECISION_MAP_NOT_FOUND
DECISION_MAP_PERMISSION_DENIED
DECISION_MAP_READ_FAILED
DECISION_MAP_ENCODING_INVALID
DECISION_MAP_JSON_INVALID
DECISION_MAP_CONTRACT_INVALID
```

上述情况全部固定为 `FAIL/1`、`paths_redacted=true`、`completion_claim_allowed=false`，不回显路径或异常正文。
测试覆盖缺失、权限错误、一般 OSError、非法 UTF-8、非法 JSON、非对象、重复键和路径泄漏；`REVIEW/2` 继续只表示
真实业务待复核，不能再被输入读取错误占用。

### 63.6 transaction 回归根因与修复

本轮扩展 editable wrapper 传递后，`_validate_structural_transaction()` 已新增形参
`editable_style_wrappers`，但内部 fragment validator 一度错误引用函数作用域外的
`run_metadata["editable_style_wrappers"]`，造成 26 个 transaction/replay 测试统一 `NameError`。这不是 26 个
独立缺陷，也不能用局部 wrapper 测试绿色掩盖。内部调用改为使用该函数形参；外层 `_finalize_locked()` 仍从冻结
run metadata 传入授权清单。修复后 transaction/replay 专项 225 项全部通过（跳过 3 项）。

### 63.7 回归门与 v68 双投影

```text
transaction + replay specialty       = 225 OK (skipped=3)
math/quote/TeX/reason/scaffold focus  = 212 OK (skipped=2)
full unittest                         = 1055 OK (skipped=8)
projection specialty                  = 44 OK (skipped=1)
compileall                            = PASS
quick_validate                        = PASS (PYTHONUTF8=1)
git diff --check                      = PASS（仅既有 CRLF 提示）
SKILL.md                              = 499 lines

primary = build/generator-projection-maturity-v68-v136-20260720
repro   = build/generator-projection-maturity-v68-v136-20260720-repro
files = 38 / 38; path differences = 0; raw byte differences = 0
manifest_bytes = 40739 / 40739; manifest_raw_byte_equal = true
policy_version = 1.36.0
capability_source_sha256 = 55a7844acaf044cf321816d695e34b9bcc2b840631576201f8c6351f5c4441f1
evaluation_surface_sha256 = bf5a18d9add9c83396bc8c027c224b7f9544862e97b19fe5eafa994c8b1ccb80
inventory_sha256 = d409c63614101c6c35586c050f201db82d6df63749d4fc5843e0e58eab21c985
derived_artifact_sha256 = 1804375333ea69a3a633270fb4dd5e7ba13b4c72b98c2729838a0253e36ba87b
builder_executable_sha256 = a620d9b01ec90fbeafcbb684195a920757eb604abc43d13a9ee176d2c622cae4
projection_tree_sha256 = 1f13267d8b7399f5ee70a4f01d33ec27a04e24418609bceb9e0a68a2a7255375
manifest_sha256 = 98f5b8e11b6dc94e94ccb986afe49094b01e12a0b488a40e565c85b071c358ec
```

本轮证据证明的是六个具体攻击面已被当前机械合同捕获、错误态不再伪装成 REVIEW、transaction 参数合同已恢复，
以及 v1.36 的 38 文件投影可以逐字节复现。它不证明生成文本自然，不证明改后优于改前，不证明学术事实正确，
不证明作者身份，也不授予 paired-quality clearance、结构语义 clearance 或 generation qualification。GPT/未知来源
TeX 只作为负例与压力材料；不能反向进入真人 Voice 或正向句库。整体成熟化目标继续 active，后续仍需新的独立盲用和
对抗样本寻找尚未编码的保护边界与自然度失效。

## 64. 2026-07-20：v1.37 行内代码与跨行数学的 authoring 前置保护

### 64.1 “末端会拒绝”不能替代“前端不暴露”

v1.36 的 invariant checker 已把 `\verb`、`\lstinline` 和 verbatim 环境作为代码比较，但长文 prepare 的
`masked_text` 使用 scanner 保护语法。两层语法并不完全一致：旧 prepare 只把 `\verb`/`\lstinline` 命令 token
替换为占位符，分隔符和代码载荷仍直接交给 authoring 模型。真实旧工件
`%USERPROFILE%\.codex\tmp\v137_local_tex_probe\run\chunks\U-5392f137e507.json` 中出现：

```text
[[PROTECTED:...]]|token_甲=1|
[[PROTECTED:...]]!print([[PROTECTED:...]])!
```

第二行内部 ASCII 引语被另一个 quote span 遮罩，但 `print`、分隔符和其余代码仍裸露。final validator 可能在模型
改动后用 `PROTECTED_CODE_CHANGED` 拒绝，不代表 prepare 已保护；暴露会浪费生成回合、诱发不可交付候选，也违反
“代码不进入文风改写”的 authoring 边界。

### 64.2 行内 verb 语法覆盖

共享 scanner 新增 `latex-inline-verbatim` span，并与 invariant checker 对齐，覆盖：

- `\verb|...|` 与星号形式；
- fancyvrb 的大小写敏感 `\Verb+...+`；
- `\lstinline!…!`；
- `\lstinline[language=Python]!…!` 等可选参数形式。

实现没有把 `\verb` 的 `[...]` 误作可选参数：`\verb` 与 `\lstinline` 使用两个独立正则分支，因为前者允许 `[` 本身
充当 delimiter，而后者才有 option group。prepare 的通用 TeX command span 与新的 inline-verbatim span 合并后，
完整命令、选项、分隔符和载荷成为一个保护跨度；validator 同样比较完整代码跨度。长文工作流保护表同步明确
`\verb/\Verb/\lstinline（含可选参数）` 全部保护。

### 64.3 跨行 inline math 与反斜杠奇偶

旧 scanner 的 `$...$` 内容显式排除换行，且只要 `$` 紧邻任意反斜杠就当成已转义；invariant checker 则允许跨行并
按连续反斜杠奇偶判断转义。两个具体结果是：合法跨行 `$F=ma\n+G$` 的第二行可暴露，TeX 换行命令后的
`\\$H=mc$` 也可能因第二个反斜杠紧邻 `$` 而漏识别。

v1.37 允许 inline math span 跨行，并增加偶数反斜杠起点分支；单个 `\$` 仍作为字面 dollar，不误判为数学。
新测试同时检查 scanner span 和 prepare masked view，invariant 继续承担改后硬比较。这里保护 `\\$...$` 时会把紧邻
的换行控制序列与公式合并为一个 span；这是保守扩大，不赋予 authoring 修改换行命令的权限。

### 64.4 真实 prepare 前向复测

扩展后的 fixture 同时包含普通 `\verb`、`\lstinline`、带 option 的 `\lstinline`、`Verbatim` 环境、跨行数学和
偶数反斜杠数学。修复后
`%USERPROFILE%\.codex\tmp\v137_local_tex_probe\run-fixed2\protected_spans.jsonl` 形成 7 个保护跨度，其中：

```text
\verb|token_甲=1|                              latex-inline-verbatim
\lstinline!print("乙项")!                      latex-inline-verbatim
\lstinline[language=Python]!token_丁=2!        latex-inline-verbatim
$F=ma\n+G$                                     inline-math
\\$H=mc$                                       latex-inline-math-even-escape
```

对 chunks 搜索 `token_甲/token_丁/print/F=ma/G$/H=mc` 的结果为 0；环境外中文仍保留在 `masked_text`，没有因扩大
保护而把后续说明吞掉。该前向只证明这些具体载荷没有进入 authoring view，不证明任意自定义 verb 宏都能识别。

### 64.5 独立代理证据边界

本轮曾分别启动 TeX 边界、低误报和真实长文盲用三个只读代理。两个代理明确因平台 `429 Too Many Requests` 退出，
长文代理也没有留下可重放结果；因此三项均记为 `NOT_EVALUATED`，既不归因于 Skill 缺陷，也不记为 Skill 通过。
本节的修复依据只来自本地主代理可重放 fixture、旧/新 chunks 和测试，不使用“代理已测”作为支持。

### 64.6 回归门与 v69 双投影

```text
invariant/scanner/prepare/projection focus = 199 OK (skipped=1)
full unittest                              = 1061 OK (skipped=8)
compileall                                 = PASS
quick_validate                             = PASS (PYTHONUTF8=1)
task-scope git diff --check                = PASS（仅 CRLF 提示）
whole-repo git diff --check                = BLOCKED_BY_UNRELATED_CHANGE
unrelated finding                         = physics2.tex:453 trailing whitespace
SKILL.md                                   = 499 lines

primary = build/generator-projection-maturity-v69-v137-20260720
repro   = build/generator-projection-maturity-v69-v137-20260720-repro
files = 38 / 38; path differences = 0; raw byte differences = 0
manifest_bytes = 40739 / 40739; manifest_raw_byte_equal = true
policy_version = 1.37.0
capability_source_sha256 = 00d1f795bbdf78ef64701664c963f89e124c4e9b4c03d641f51740655d416bc2
evaluation_surface_sha256 = 36c18da3aa479fa48db354d522e5c9c3dbba9b15205b5db100eb5bb4fb7396ed
inventory_sha256 = 9509d2bc19e0461bc2a4f157717118cc36401c098eb2c575a07163241875b72a
derived_artifact_sha256 = 1804375333ea69a3a633270fb4dd5e7ba13b4c72b98c2729838a0253e36ba87b
builder_executable_sha256 = 441a016353cbaa89d66349e70423d3738ed49bbc83a65af581dccb1aebffb0c5
projection_tree_sha256 = 9bfbd602bcfd384ef4aa08e2aa1a9eb54a23d53f8cfa0b3a2c2581905593a598
manifest_sha256 = ab1aad8ccc50ae9546dd33e4a190d34099a110f144c9862afc97f69fb6dc7ad4
```

本轮只证明五种已编码行内字面量/数学边界在 scanner、prepare 与 invariant 三层的一致性，以及 v1.37 capability
投影可重复。它不证明自定义 verb 宏、宏展开后的环境、catcode 改写或任意 TeX 引擎语法都被解析；本工具仍不是完整
TeX 解释器。它也不证明自然度、改后优于改前、学术正确性、作者身份、paired-quality clearance、结构语义 clearance
或 generation qualification。整体成熟化继续 active。

## 65. 2026-07-20：v1.38 TeX 保护解析、结构视图与投影冻结

本节 supersedes 第 64 节中的“当前版本”数字；历史节保留其各自时点的证据。v1.38 的目标不是扩张为 TeX
解释器，而是消除会让受保护源码暴露、让伪命令污染长文结构、或把源码字节漂移误记为通过的已观察执行链缺口。

### 65.1 已修复的解析与结构边界

- `DefineShortVerb` / `UndefineShortVerb` 和自定义 verb 命令现在遵从分组局部作用域；显式
  `MakeShortVerb` / `DeleteShortVerb` 保持全局语义。保护载荷也不会递归声明或撤销命令。
- code 环境的结束标记改为大小写敏感、行首匹配；行内伪 `\end{...}`、注释中的伪结束和大小写不匹配不再提前泄露后文。
- code/verb/comment 先经固定点解析，再交给数学跨度解析；注释里的 `$` 或 `\end{equation}` 不能改变数学状态。
- `prepare_humanize_long_document.py` 的 include、未决 include、标题、环境、命令、切块等结构读取统一使用保留 offset/换行的 `_tex_structure_view`。因此保护区里的伪 `\input`、伪标题和伪环境不会创建文件、单元或未决项。
- invariant 改为按原始保护字节比较：CRLF 与行尾空格不再被预归一化后误放行。

### 65.2 回归与冻结证据

新增真实 `prepare()` 入口回归：两个幽灵 `.tex` 文件在磁盘真实存在，但只由 `\verb` / `Verbatim` 中的伪
`\input` 引用。通过条件不是“辅助函数返回空”，而是公开 `file_manifest.csv` 只含 `main.tex`，真实标题仍有
chunk，伪标题不出现。专项 scanner/prepare/invariant/projection 共 `243 OK (skipped=1)`；工作区完整命令
`python -m unittest discover -s tests -p 'test_*.py'` 为 `1105 OK (skipped=8)`。`compileall` 与
Skill quick validation 均 PASS。

投影策略只批准构建器 `_inventory()` 计算的 38 文件能力源：

```text
policy / builder                       = 1.38.0 / 1.38.0
capability_source_sha256               = f9399cb855dc729941e7c14dbec5c5b1086f37a211ca2f5387f684807970af31
evaluation_surface_sha256              = 41db4fc871f9084ff078da944adefe029e6c4829b14d3922a8435bcd86524dfd
inventory_sha256                       = ec7c9774f7965784d174e9c20e3540fd71a27d1cd214f19bd9ffa7bca239acf3
projection_tree_sha256                 = 26caa571a9423c84f0669e64d40a49fc599f80cabcd559cf94931fb69244feed
manifest_sha256                        = 023853796645cc210cf2b5bfbcef638238f4f04a16568cf236256ab6eacefb47
projection files / per-file differences = 38 / 0
manifest raw-byte difference            = 0
```

构建器拒绝把投影写回 Skill 源树；这是预期的源/产物隔离门。因此两份同名投影写在
`C:\Users\Lenovo\.codex\tmp\humanize-projection-maturity-v138-20260720\`，而非 Skill 的 `build/` 子目录。
两份 manifest 原始字节完全相同，逐路径 SHA-256 与 tree hash 相同。

### 65.3 后冻结验收与诚实边界

可重放维护者验收见
`C:\Users\Lenovo\.codex\tmp\postfreeze-humanize-selfcheck-v138\MAINTAINER_POSTFREEZE_ACCEPTANCE.md`：它实测
file graph、假标题、受保护/候选同词分流、注释内数学闭合与 CRLF/尾空格硬失败。两次独立代理请求没有留下报告或
工件，均为 `NOT_EVALUATED`，不得被包装成“独立黑盒通过”。

本轮证明 parser 与 capability projection 可测试、可重放；不证明文本更自然、改后质量更高、学术正确、作者身份、
外部 paired-quality clearance 或 generation qualification。自定义 catcode、宏展开、未知 verb-like 命令和真实引擎
语义继续是应攻击而非应假定已解决的范围。

## 66. 2026-07-22：v1.42 generator projection 双对象发布恢复与批准绑定红队

### 66.1 发现：目录 rename 不是“投影已发布”的充分条件

generator projection 有两个必须同时存在且相互绑定的交付对象：38 文件 projection 目录和其外部 canonical
manifest。旧构建器能在 Python 可捕获异常里删除目录，但发生在 `staging.rename(output_root)` 与
`os.replace(manifest_staging, manifest_path)` 之间的进程强杀，会留下“目录已存在、manifest 缺失、下次构建
又因 output 已存在而拒绝”的半发布状态。这样的目录不能被 runner 当作完整 projection，也不能靠“目录已经写出”
冒充 publication 完成。

该问题不改变中文文风规则本身，却影响生成资格审计的证据闭包：若 publication 状态可被误读，后续 runner 或
auditor 可能面对一个只有能力文件、没有其 source/policy/tree 绑定的目录。因此修复被限定在 builder 的控制面，
没有将审计条件、oracle 或资格原子重新放进 generator projection。

### 66.2 v1.42 状态机与 fail-closed 恢复

`build_humanize_generator_projection.py` 升至 `1.42.0`，增加
`humanize-generator-projection-publication-journal/v1`。journal 位于 manifest 同级，不写入 projection，也不进入
generator 文件闭集；控制文件以 canonical JSON 原子替换并尝试 `fsync`。状态只能单向推进：

| 状态 | 已落盘对象 | 重启处理 | 不一致处理 |
|---|---|---|---|
| `ALLOCATED` | staging 路径和 manifest staging 路径已登记 | 两个临时对象均删除 | final path 已出现即拒绝 |
| `PREPARED` | 预期 tree hash、manifest hash/size 和两个临时对象均已登记 | 未提交 output 回滚 | tree/hash/类型不符即拒绝 |
| `OUTPUT_PUBLISHED` | output 已 rename，manifest 尚可能在 staging | 只有目录 tree 与 staging manifest hash 都一致时补齐 manifest | 缺 manifest staging、目录/manifest 不符或 manifest 无 output 均拒绝 |
| `COMMITTED` | output 与 manifest 均已存在 | 校验两个 hash 后只清 journal | 任一最终对象缺失或漂移即拒绝 |

恢复还绑定调用时的 output、manifest、staging 路径；journal 的路径不等、staging 前缀/父目录不安全、symlink/reparse、
非普通文件、目录中的 reparse child、树哈希漂移或 manifest 长度/哈希漂移都会 fail-closed。恢复器不会根据一个可疑
journal 删除任意路径。成功构建仍只产生原有 projection 与 manifest；正常路径不会留下 journal。

构建前和 staging rename 前各做一次冻结 source 重读。这样 journal 解决的是受控本地文件系统上的可恢复发布顺序，
不把它夸大为同权限攻击者防护、硬件断电持久化顺序证明或历史真实性证明；这三项继续分别为
`same_privilege_tamper_resistance=NOT_EVALUATED`、目录持久化顺序未验证和
`historical_authenticity=NOT_EVALUATED`。

### 66.3 固定红队测试，而非一次性手工脚本

原临时 smoke 被提升为安装 Skill 的排除审计文件：
`scripts/test_humanize_generator_projection.py`。它被加入 builder 的固定 `exclude_exact`、policy 和
forbidden basename 闭集，manifest 明确列为 excluded；因此测试代码不会出现在 generator 的 38 文件能力面。

三个 unittest 覆盖的攻击/恢复路径为：

1. 构造 `ALLOCATED`、`PREPARED`、`OUTPUT_PUBLISHED`、`COMMITTED` 四种 journal，检查清理、补齐和保留的
   行为分别符合状态；把 `output_root` 篡改为另一路径时必须抛出 `ProjectionError`，且 sentinel 不被删除。
2. 对真实 `build_projection()` 注入 `KeyboardInterrupt`：一次发生在 manifest move 前，另一次发生在 manifest
   move 后、COMMITTED journal 写入前。下一次调用先恢复完整 publication，随后因 output 已存在而正常拒绝覆盖；
   不允许把恢复过程重新当成一次新构建。
3. 复制完整 Skill 后伪造 `approved_builder_executable_sha256`，必须拒绝；再修改
   `load_humanize_negative_guards.py`，同时伪造 capability source approval，仍必须在 source-bound replay 中以
   `transform dependency differs` 拒绝。第二项避免仅靠 capability hash 的第一道拒绝掩盖独立依赖绑定未生效。

本轮实际命令与结果：

```text
python -X utf8 scripts/test_humanize_generator_projection.py
Ran 3 tests in 7.967s
OK

python -X utf8 -m compileall -q <skill-root>
PASS

python -X utf8 <skill-creator>/quick_validate.py <skill-root>
Skill is valid!
```

`quick_validate.py` 在本机默认 GBK 环境下会因未显式 encoding 读取 UTF-8 `SKILL.md` 而抛
`UnicodeDecodeError`；`-X utf8` 是可复现的工具环境要求，不能把未经 UTF-8 强制的失败记为内容合同失败或通过。

### 66.4 v1.42 双投影复现

两份 projection 由当前 source 独立构建到源树之外，避免把派生产物写回 source：

```text
primary = C:\Users\Lenovo\.codex\tmp\humanize-projection-maturity-v142-20260722
repro   = C:\Users\Lenovo\.codex\tmp\humanize-projection-maturity-v142-20260722-repro

files = 38 / 38
path + SHA-256 differences = 0
manifest raw-byte equal = true
policy_version = 1.42.0
capability_source_sha256 = d604d4848a86b4d97bd968bed0c5ddd9c65da99f04942584338a62ab2d3f1864
evaluation_surface_sha256 = 2e5a213b623c0b44ffdd28a4f6d0298bcca50f23a89a20f72094924c86b65c26
inventory_sha256 = 85c2ca6cea2e2d736f49e04e1b0391608bb61b31b556e9c64b617fda1d3947f0
derived_artifact_sha256 = 728c0df053d1c6f4b73a6b0c0018df6fee629943855841cb41360efef6be80e7
builder_executable_sha256 = 7b8fcc43dbe80a6eee5d39d0ece79911d0b81748516486541c516f5431542e2d
transform_registry_sha256 = a192969ca26ffdbd92387ab923d386489d510175f1d03c3330a0df389f76e047
transform_dependency_sha256 = 854ad1e921994034e9dff8ec5ac4daaa268a69b00db7003e6f69676f680ed1a8
projection_tree_sha256 = 4a32c8563ce1403b0ddc93a3aa4cec78b9e4ecea8e0041c06b7293a6b626c869
manifest_sha256 = c24058a344f5fc1a2dae574f3c2f824250d4f77033b7707c061cc5edc93e863a
excluded records = 156; test_humanize_generator_projection.py = present only in excluded
```

能力源 hash 与本轮前的 v1.40 批准值相同，符合预期：journal、builder、evaluation contract 与测试均在 capability
surface 之外。evaluation/inventory/derived hash 改变也必须记录，不能用“投影正文没变”掩盖审计面变化。

### 66.5 证据边界与待攻面

本节证明当前 Python 级故障注入、当前 source-bound builder、当前 policy 与当前本地文件系统上的确定性重放。
它不证明实际操作系统强杀、断电、网络文件系统、并发多个 builder、同权限恶意替换 journal、外部时钟/签名锚定，
也不证明 generator 在真实盲用中生成得更自然。三次本轮独立子代理请求都因平台 `429 Too Many Requests` 失败，
故独立黑盒/盲用证据为 `NOT_EVALUATED`，不能包装为红队通过。

下一轮应优先使用隔离进程实际终止（而非仅 monkeypatch）验证 journal 重启，加入并发同路径的锁语义攻击，并以匿名的
真实中文学术段落做不泄漏规则结论的前向盲用。未得到这些证据前，Skill 继续是“有更强机械边界的待审工具链”，
不是可宣称所有文风任务均稳定完成的终局系统。

## 67. 2026-07-22：v1.43 从 GPT TeX 负例提取“题目槽位”而非再加泛禁词

### 67.1 人工阅读发现的漏项

本轮重新读取用户明确标为 GPT 生成、并在来源台账中固定为 `MODEL_GENERATED / negative_template_reference` 的
`D:\code LateX\elegantbook\cet6\test.tex`。该文件的英文例句不进入中文词库，也不作为正向风格材料；本轮只观察其
中文模板后台。旧扫描只命中 3 处 `LEX-MARKET-01`，却没有标出重复出现的“题型范围 → 给入首句 → 固定推演 →
号召/对照收尾”槽位说明。这不是单个词不好，而是文档把备课卡的控制语直接当作正文。

人工证据落在 7 个不同物理行：三个题型范围条目、三个固定推演链条及其首句提示，以及一个同类题可套用的说明。
同一文件中这些槽位随后承接统一的价值拔高、风险逆转或二元平衡出口。此前的 `LEX-META-01` 针对建模/研究稿中的
“正文应如何写”等编辑后台，场景和触发词都不覆盖这类考试模板；因此不能把旧规则已经存在误写成“已检测”。

### 67.2 新信号的窄化合同

`lexical-signals.json` 升为 `1.2.3`，新增 `LEX-META-02`：

| 字段 | v1.43 约束 |
|---|---|
| 可见锚点 | `适用题目`、`逻辑链条`、`给定首句`，以及“此类题目可用/套用”结构 |
| 数量门 | 同一 document 至少 3 次，且至少分布在 3 个不同物理行 |
| 场景 | `ALL`，避免把模板文件伪装成没有路由的例外 |
| 默认动作 | `REVIEW`，不授权扫描器删除或改写 |
| 保护 | 代码、公式、引语、题干、用户锁定模板仍由共享保护层排除 |
| 反误报原则 | 单次谈论题目范围或实体论证链不触发；候选也不判断作者身份、AIGC 分数或文本质量 |

新增 `HUM-17` 将其定义为“题目槽位和固定推演链泄露”。它要求先分开教师备课单、题库/模板原件和可编辑作者正文：
用户明确要求保留的模板可 `KEEP`；若目标是面向读者的课程讲义，应把槽位改为原材料已给出的条件、判断动作和后果；
论文/报告中没有这些事实锚点时只能 `PATCH/ANNOTATED` 或 `UNRESOLVED`，不能换一个更隐蔽的自动结尾。

该定义刻意不把英文题库句式纳入中文 detector，也没有把“逻辑链条”列为禁词。英文模板的真实识别需要独立的英语
写作工具和英语语料评估，不能借中文 Skill 偷做跨语言能力声明。

### 67.3 回归、真实重扫与反例边界

固定审计测试 `scripts/test_humanize_generator_projection.py` 新增 lexical case，验证：

1. 三类槽位加一个“同类题可用”结构形成 4 条 `LEX-META-02` 候选，全部为 `candidate=true / REVIEW`；
2. 单次“论证链连接条件和结论”的研究句不命中；
3. 同样的三行文本放入 TeX `verbatim` 环境不产生可编辑候选；
4. 既有投影 journal、伪造 builder approval、伪造 capability approval 加 transform dependency drift 的三类测试
   继续通过。

```text
python -X utf8 scripts/test_humanize_generator_projection.py
Ran 4 tests in 7.513s
OK

真实 CET6 test.tex（AUTO）
LEX-META-02 = 10 findings / 7 distinct lines / all REVIEW candidates
LEX-MARKET-01 = 3 findings

真实 main.tex（AUTO）
LEX-META-02 = 0
既有管理腔、过渡、对照、编辑后台、自动展望信号数量未因本规则增加
```

`main.tex` 仍是用户标注的 GPT 负例，但它在本轮没有三行题目槽位；0 命中只说明新规则没有滥用该术语，
不说明该文自然，也不推翻其余既有候选。CET6 的 10 条命中只说明固定槽位被定位，不能据此预测检测器结果，
更不能推断任何单篇文本的作者身份。

### 67.4 v1.43 投影与保留边界

词库、`HUM-17` 和 SKILL 高风险快检入口都在 capability surface 内，因此 v1.43 必须更新批准 capability hash；
新增测试仍在 audit exclusion，未进入 generator：

```text
primary = C:\Users\Lenovo\.codex\tmp\humanize-projection-maturity-v143-template-slots-20260722
repro   = C:\Users\Lenovo\.codex\tmp\humanize-projection-maturity-v143-template-slots-20260722-repro

files = 38 / 38
path + SHA-256 differences = 0
manifest raw-byte equal = true
policy_version = 1.43.0
capability_source_sha256 = 87b11d6ffca9841ce2293d1259861a69f6e5ab185fdb075f156443923722ea5e
evaluation_surface_sha256 = 5686894cc2fd370c1d6bf7715590d957ec44b749c8ceee984e45c8be9c4e3110
inventory_sha256 = 8c82cc366c4bc145b1be271e58a19eccee86baec80e29151cb693b1d8f15ba43
derived_artifact_sha256 = 728c0df053d1c6f4b73a6b0c0018df6fee629943855841cb41360efef6be80e7
builder_executable_sha256 = cafe97c9a26103765873fbda9fb7ff45711603b5644eda9dfa2d7e43da3339c9
projection_tree_sha256 = 7b2eee8462a88fd8703d0ae6cb287d651ffc539337606b3b51d970f43c4d186c
manifest_sha256 = 8f20446cc018f8bf714856a1ac0106950bfc172b744f30066ae0cddf1936c216
source-bound replay = SOURCE_BOUND_CURRENT / PASS
```

本节把一个真实负例的漏检转成了可复核、可撤回的候选规则和反例测试，但没有证明所有题库模板都会命中，
没有把英语模板自然化纳入范围，也没有完成真人盲读、改写收益或学术正确性的外部评价。下一轮应从不同体裁的
匿名中文课程说明、合法题干与真实论文方法段中扩大对照，以检验“三行门”是否过宽或过窄。

## 68. 2026-07-22：v1.44 用 GPT 建模 TeX 修复跨段“作品自证”开头漏检

### 68.1 漏检不是普通否定对照

用户标注为 GPT 生成、仅作负例的 `main.tex` 在“模型优缺点分析和优化”连续五个小节中，都用同一类
“本问 + 优点 + 不在于……而在于……”开头，再分别接问题一至问题五的模型解释。旧
`LEX-CONTRAST-01` 只匹配“不是……而是……”和连续纠偏；实际只命中同一问题五段的两处边界说明，五个优点式段首
全部漏检。不能因为词面都含否定就把这视为已覆盖：前者保护认识边界，后者是跨段的作品自我背书。

人工阅读确认，五个段首后的数据、条件、限制与机制各不相同；重复的是验收式起句，不是必须删除的事实关系。因此本轮
不把“优点”“价值”列为禁词，也不把任何“……不在于……而在于……”直接判为病灶，而是把对象、评价名词、对照骨架
和跨段重复同时作为条件。

### 68.2 `LEX-SELF-VALIDATION-01 / HUM-18`

新信号只在 `MODELING` 与 `RESEARCH` 场景启用，要求：

| 维度 | 约束 |
|---|---|
| 主语 | 本问、本研究、本文、本模型或本方案 |
| 评价壳 | 优点、价值、意义、贡献、关键或重点 |
| 结构 | 同一段首同时含 `不在于…而在于` |
| 数量门 | document 内至少 2 次，且分布在不同 paragraph |
| 动作 | `REVIEW`，不自动删除、改写或评价方法正确性 |
| 保留项 | 对照中的对象、条件、数据、范围、限制、题干、引语、代码、公式和用户锁定评价句 |

`HUM-18` 规定改写只能移除重复的验收式段首，并在原材料足够时直接进入本段真正改变判断的差异；不得把它轮换为
“核心价值”“真正优势”“关键意义”或另一种自夸开头。若评价主张被用户锁定或输入不足，固定降级
`PATCH/ANNOTATED` 或 `UNRESOLVED`，不伪造完整 `CLEAN`。

### 68.3 测试失败也进入台账

新增 lexical 保护测试第一次运行时失败：新自证测试作用域尾部误引用了前一测试的 `template` 变量，抛出
`NameError`。这只是测试夹具错误，且当时 v1.44 未被标为通过；随后把题库槽位的 `verbatim` 断言移回其自身测试，
再完整重跑。最终固定测试为：

```text
Ran 5 tests in 8.282s
OK
```

其中新增测试同时断言：两段不同 paragraph 的自证式对照产生 2 个 `REVIEW` 候选；单次有实体比较的句子不命中；
同样文字置于 TeX `verbatim` 时不形成可编辑候选。该测试只证明已编码的形式和保护边界，不证明改写后的读感收益。

### 68.4 实际重扫与有限反例

```text
main.tex (AUTO) = 5 LEX-SELF-VALIDATION-01 candidates / 5 paragraphs / REVIEW only
physics1.tex (AUTO) = 0
physics2.tex (AUTO) = 0
CET6 test.tex (AUTO) = 0
```

后面三份材料的 0 命中是窄化反例：它们说明当前规则没有把这些可读课程文本或题库槽位误称为作品自证；它们不是
大样本精确率，也不把 provenance 为 `UNKNOWN` 的 physics 材料升级为真人 Voice 证据。`main.tex` 的 5 命中同样
只定位重复段首，不能判断其作者身份、模型质量、检测器分数或五个模型是否真的更好。

### 68.5 v1.44 投影

```text
primary = C:\Users\Lenovo\.codex\tmp\humanize-projection-maturity-v144-self-validation-20260722
repro   = C:\Users\Lenovo\.codex\tmp\humanize-projection-maturity-v144-self-validation-20260722-repro

files = 38 / 38
path + SHA-256 differences = 0
manifest raw-byte equal = true
policy_version = 1.44.0
capability_source_sha256 = da73954f5d23d5840f07485b45f30e5cac29d05d94071f7a0d1f417a46c9dd35
evaluation_surface_sha256 = 4a4be853368c062881100d447bdd2e89e14613052be83acfb8faf5d63bfa3e98
inventory_sha256 = 96c17cc96426644e6bc61cefd1e79ab7a4879c863a52a1aecec96de60fc02b13
derived_artifact_sha256 = 728c0df053d1c6f4b73a6b0c0018df6fee629943855841cb41360efef6be80e7
builder_executable_sha256 = 32e6ce3531fb7a4bc28c87afd4685a888ecd5b38cfdc7b698e8a24c2df01727a
projection_tree_sha256 = 0cf552039e4f6151178d54aef12f5e444dc425e08d5381ba88c75436bb91ea2d
manifest_sha256 = 9bd099525126d84b7875af1e7bc693c37da1eb6cdfd56a3c237a3c3e644f72c3
source-bound replay = SOURCE_BOUND_CURRENT / PASS
```

本轮把又一个真实 GPT 负例的“批量段首”转化为窄化规则，但仍没有真人盲读、改写成对质量比较或跨领域中文论文的
足量反例。下一批应优先攻击“本研究的意义在于”“本方法的核心在于”等近邻变体，并检查两次出现是否在某些合法的
研究设计比较中产生误报。

## 69. 2026-07-22：v1.45 让既有后台/展望门覆盖“局限安排”和“继续补强”词形

### 69.1 不再为每个词造一个新病灶

`main.tex` 的五个模型分析段除重复优点式开头外，还有四个段落以“局限需要写清”的编辑安排引入限制，随后以
“后续若继续补强”安排下一轮工作。前者不是限制本身，后者也不等于具体研究计划；它们分别属于既有
`LEX-META-01` 的编辑后台和 `LEX-FUTURE-01` 的自动展望，而不是值得创建 `HUM-19` 的独立病灶。

初版扩展曾漏掉“应优先”词形：正则只接受“应当/应该/优先”作为完整词，无法处理“应 + 优先”的组合。真实重扫
显示 `LEX-META-01=6`、`LEX-FUTURE-01=1`，说明局限后台已被定位但四条后续安排仍漏检。该结果没有被当作通过；
词形修正为允许独立“应”后，`LEX-FUTURE-01=5`，其中四条来自相同的补强安排，另有一条是此前已有的未来展望候选。

### 69.2 收紧后的规则含义

- `LEX-META-01` 现识别“其/本问/本研究/本文/本模型 + 局限 + 需要/应当/仍需 + 写清/说明/交代”的后台壳，
  固定 `DELETE` 只删除写作安排，不能删除原句已有的条件、范围或限制。
- `LEX-FUTURE-01` 现识别“后续/未来 + 若继续 + 补强/完善/改进 + 应/建议/优先”的泛化安排，固定 `REVIEW`。
  只有原文给出待补对象、动作和原因时，才能保留成具体未决工作；否则不得把愿望改写成自动研究计划。
- `HUM-11` 与 SKILL 快检同步区分了“局限的具体内容”和“要求把局限写出来”的不同角色。前者可保留，后者是编辑
  后台；这一判断不评价模型质量，也不授权补造外部数据或未来实验。

新增固定测试使用近邻句，验证一个局限编辑壳产生 `LEX-META-01/DELETE`、一个泛化补强安排产生
`LEX-FUTURE-01/REVIEW`，而相同文字放入 TeX `verbatim` 不形成候选。测试不是凭正则输出自证，而是覆盖保护区和
动作合同。

```text
Ran 6 tests in 9.733s
OK

main.tex (AUTO)
LEX-SELF-VALIDATION-01 = 5
LEX-META-01 = 6
LEX-FUTURE-01 = 5

physics1.tex / physics2.tex / CET6 test.tex
new or extended META/FUTURE candidates = 0 / 0 / 0
```

后三个零值只是在当前三份对照材料上的窄化观察，不能外推为精确率，也不把未知 provenance 的课程材料当作真人
正向语料。`main.tex` 的计数仍只表明候选被定位，不表明其作者身份、检测器结果、内容正误或改写收益。

### 69.3 v1.45 投影

```text
primary = C:\Users\Lenovo\.codex\tmp\humanize-projection-maturity-v145-editorial-future-20260722
repro   = C:\Users\Lenovo\.codex\tmp\humanize-projection-maturity-v145-editorial-future-20260722-repro

files = 38 / 38
path + SHA-256 differences = 0
manifest raw-byte equal = true
policy_version = 1.45.0
capability_source_sha256 = 08fc8651630083327464a0f20fc5db699162e2defe774713e79dbbdc55e7eb9c
evaluation_surface_sha256 = 7d0a1e638f3f8ccce53a416db373b10389162f7cce347b96f7b0666d666489d6
inventory_sha256 = 771613b717a3e1df6649e76b7309e1af23eed1bfd4a7bb1fd1b8e3c5c4d64be3
derived_artifact_sha256 = 728c0df053d1c6f4b73a6b0c0018df6fee629943855841cb41360efef6be80e7
builder_executable_sha256 = c0cff34585b45dd464a21091dfdc0ca832fd70c7398b35190fa3268da89eeeab
projection_tree_sha256 = 3047db181d9614c7a699e68c4eeca181f9ad4657cbf8fe73b638db88414eb603
manifest_sha256 = 297a6cd7e25eb336d205345081d38094581e6bc8252968cf0e8580da3e614536
source-bound replay = SOURCE_BOUND_CURRENT / PASS
```

本轮说明连续人工阅读能发现“已有规则未覆盖的词形”，而不是只能不断堆新 ID。它仍没有回答不同学科的真实作者
会不会把合理的局限与后续计划写成相似形式；下一轮必须用匿名真实论文、教师明确保留的课件和人工成对读感来攻击这
两个门，不能因三个零值停止校准。

## 70. 2026-07-22：v1.46 编辑壳删除与言语行为门的前向一致性

词库已将“局限需要说明”定位为可删编辑后台，但初次前向候选把“如继续完善，应当”压成“可补入”，统一验证器正确返回
`REVIEW/2`：硬不变量通过，条件和模态标记却发生漂移。没有通过降低门槛来消除 warning。

随后把不变量的句首豁免严格限定为“本/其模型等 + 局限 + 需要/应当等 + 写清/说明/交代”的编辑壳；它只跳过该
编辑 marker，不跳过普通“需要”。固定测试直接断言删除这一壳后不再产生 modality/condition warning。前向候选保留
“如继续完善，应当”逐字，仅删除后台前缀，得到：

反向控制同时验证普通内容句“模型需要独立数据”改成弱化的“可使用独立数据”仍保留
`SPEECH_ACT_MODALITY_SCOPE_CHANGED`；因此该豁免没有把真实义务、条件或研究要求降成可自由改写的风格词。

```text
hard_invariant_layer_status = PASS
speech_act_layer_status = PASS
style_signal_layer_status = PASS
mechanical_validation_status = PASS
delivery_gate_status = REVIEW
paired_quality_review_status = PENDING_EXTERNAL_REVIEW
humanize_quality_claim_allowed = false
```

这说明编辑壳删除可以通过机械合同，但不等于文本已更自然或可正式交付；外部 paired-quality 仍不可由本地模型签发。

```text
policy_version = 1.46.0
files = 38 / 38; manifest raw-byte equal = true
capability_source_sha256 = b453414ae7ebd54fe323f9c3e7498da681a78081aa351493d653563742b176f1
projection_tree_sha256 = 8a46fd21d6976d89eb14918c9425f8d834572adcc76cc7dc10b2e086743ca0c4
manifest_sha256 = d0f1644e2a5aaf3f34e69c450c7b6e22213472ea126dd2b62823fdcb140c671a
```

随后新增的反向控制测试位于 audit exclusion，故不改变 capability tree，却会改变当前 manifest 的 evaluation
surface。当前 source 快照升为 `1.47.0`：
`C:\Users\Lenovo\.codex\tmp\humanize-projection-maturity-v147-editorial-control-20260722`，
manifest SHA-256 为 `acf696e2d73e1f064b975b5ad0561bc9389face9aba2811ba903f34190546475`。历史 v1.46
数字只描述其当时 source，不应被拿来证明当前 source-bound 状态。

## 71. 2026-07-22：跨小节“优点-局限-补强”验收块

### 71.0 对第 69.1 节的范围更正

第 69.1 节的“不值得创建 `HUM-19`”只基于当时对单个词形与原子规则的审计，尚未把五个模型分析小节作为连续
结构单元逐段比对。本节完成该人工阅读后，发现问题二至问题五不是三个偶发候选的并列，而是同一顺序在同级小节中
连续复用；因此撤回第 69.1 节关于“不需要组合病灶”的有限判断。该更正不改变原子规则仍然必要的结论，也不把
`HUM-19` 升格为自动删除或作者归因规则。

### 71.1 为什么原子规则不足以描述这个问题

对用户明确标为 GPT 生成的 `main.tex` 进行连续人工阅读后，问题二至问题五的“模型分析与改进”小节重复同一顺序：
先用“本问的优点不在于……而在于……”为本节自我背书，再用“其局限同样需要写清”把限制写成编辑动作，最后以
“后续若继续补强，应优先……”安排下一轮工作。问题一虽有优点段和补强事项，但限制直接说“其局限在于”，没有
“需要写清/说明/交代”的编辑壳，因此不被凑成同一结构病灶。

旧规则分别可以定位自评对照（`LEX-SELF-VALIDATION-01 / HUM-18`）、局限编辑壳（`LEX-META-01`）和自动展望
（`LEX-FUTURE-01`），却不能回答三者是否在**同一小节、按固定顺序、跨多个小节**复用。新增
`LEX-SELF-AUDIT-TRIPLET-01 / HUM-19` 只补这个组合层缺口，不把“局限”或“后续”变成禁词。

### 71.2 检测合同和防误伤边界

`section-self-audit-triplet-v1` 只接受 TeX `\\subsection{...}` 或 Markdown `## ...` 的同级区间；区间内必须按
先后出现自评对照、编辑性局限壳和“继续补强/完善/改进 + 模态词”起始标记，且至少两个完整区间才给候选。每个
候选只锚定该节首个自评壳，供人回读整个小节，而不会把小节、限制、数据或未来工作整体标成待删除内容。

任一组成部分位于代码、数学、引语或其他保护区时，不能拿来凑齐三元组。展望组件特意只截取未受保护的编辑标记
截至 `优先/应/建议`，不贪婪吞入后续的 `$K=3.20$` 或引语。这不是降低保护要求：公式、引语仍不可编辑；缩短的
只是用于判断结构的壳跨度，避免保护载荷让一个真实的未保护编辑壳产生假阴性。

### 71.3 改写许可仍然很窄

`HUM-19` 要求先把每节拆为“自评壳、事实限制、补强动作”。可删的只有“需要写清/说明/交代”这类写作后台；限制
自身的条件、范围、模态和证据角色仍受不变量门约束。材料不足时输出 `UNRESOLVED`，用户锁定自评主张时降级为
`PATCH/ANNOTATED`，绝不交付伪装成完整 `CLEAN` 的全文。改后还必须回扫 `HUM-18`、`HUM-19` 与展望规则，防止
把旧结构换成“真正的优点”“需要注意的局限”或“下一步仍应补充”等同功能轮换。

### 71.4 本轮证据、失败和未获得的结论

```text
main.tex, scene=RESEARCH
LEX-SELF-AUDIT-TRIPLET-01 = 4 candidates
locations = 问题二、三、四、五的“模型分析与改进”小节
action = REVIEW only

fixed tests = 7 / 7 OK
positive = 两个完整 TeX 小节触发
negative = 只有一个完整小节不触发；缺少展望不触发
protected = 整块放入 verbatim 不触发
payload boundary = 展望后接 $K=3.20$ 时只定位保护区前的编辑标记
```

源代码、词库和 Skill 文档变动后，projection builder 先以 `capability source hash is not approved by the fixed
projection policy` 拒绝发布；该失败不是通过记录。之后只更新重新计算的 capability approval，未放宽 builder、
transform dependency、保护区、语义或 paired-quality 门。最终 projection 结果在构建完成后另行记录。

这四个候选不证明作者身份、AIGC 分数、准确率、自然度、学术正确性或 external paired-quality clearance；它们只证明
一个用户标注的 GPT 负例中有可复现的四小节结构复用，并已被窄规则和反向样本约束为待复核范围。

### 71.5 当前 source-bound projection

```text
primary = C:\Users\Lenovo\.codex\tmp\humanize-projection-maturity-v147-self-audit-triplet-20260722
repro   = C:\Users\Lenovo\.codex\tmp\humanize-projection-maturity-v147-self-audit-triplet-20260722-repro

files = 38 / 38
manifest raw bytes equal = true
projection file bytes equal = true
verified_primary = PASS
verified_repro = PASS
source_currentness = PASS
capability_source_sha256 = 08a5ddff28fb01c53e94623885dd4928926674e9dde7faa1250eda34e37ac462
projection_tree_sha256 = 19091d20236da44cd5a286f518376af9b329e5f5f039299d759dffb4238560a8
manifest_sha256 = bf4c94ca6db25294d889ae15a7b91345ea76e4fc3dcc0f43394b40ade08b9c43
historical_authenticity = NOT_EVALUATED
same_privilege_tamper_resistance = NOT_EVALUATED
```

这里的 `PASS` 仅表示当前源、固定 policy、投影文件集和 manifest 的本地一致性。它不是历史真实性证明，不表示投影
目录抵抗同权限写入，更不为正文自然度、作者声线、学术正确性或外部 paired-quality 盖章。

## 72. 2026-07-22：问题分析开头的否定纠偏模板

### 72.1 语料复读发现的是“既有规则没有执行”，不是新禁词

建模场景的 `MOD-HUM-06` 早已规定：第三次复用“本问关注的不是……而是……”必须改结构；章节差异表也明确把
“不是 A 而是 B”五次复用列为问题分析的危险模板。实际扫描却只让 `LEX-CONTRAST-01` 在**同段**出现两次时触发。
在用户标注的 GPT 负例 `main.tex` 中，问题一至四分属不同小节，原规则因此只命中问题五内部的两处对照，漏掉了
跨问题的任务说明重复。

人工逐节读取得到四个实际锚点：

| 小节 | 原文角色 | 是否进入新规则 |
|---|---|---|
| 问题一分析，第 33 行 | `问题一并不是……而是……` | 是 |
| 问题二分析，第 46 行 | `本问的重点不是……而是……` | 是 |
| 问题三分析，第 53 行 | `这一问真正要回答的不是……而是……` | 是 |
| 问题四分析，第 64 行 | `问题四的核心不是……而是……` | 是 |
| 问题五分析，第 73 行 | `问题五才能……并不是……而是……` | 否；不是任务开场 |

最后一行是本轮前向攻击发现的误报。初版模式允许问题主语与 `不是` 相隔 42 字，错误地把“问题五才能从……上升为……，并不是……”认成任务开场。该模式没有被保留；收紧后只允许
问题主语后为空，或紧接 `重点/核心/任务/要回答的/真正要回答的`，再接 `不是`。

### 72.2 可执行检测边界

新增 `LEX-QUESTION-ANALYSIS-CONTRAST-01 / HUM-20`，只在 `MODELING` 场景生效。它必须同时满足：

1. 标题是 TeX `\\subsection{问题 X 分析}` 或 Markdown `## 问题 X 分析`；
2. 小节前 1600 字内由 `问题 X`、`本问` 或 `这一问` 以受限任务短语引出 `不是……而是……`；
3. 至少三个同级小节完整满足；
4. 任何组成部分落在公式、代码、引语、题干或其他保护区时不得借用。

输出固定为 `REVIEW`，每节只定位对照壳。它不判断 A 或 B 正误，不要求删除真实互斥条件，也不允许把所有句子换成
“本问重点是”。材料不足以直接改为对象/条件/判断时，原句保留并报告 `UNRESOLVED`。

### 72.3 CET6 阅读作为场景反例

本轮还读取了用户标注 GPT 生成的 CET6 `test.tex` 与三份 `section_b_final_conclusions_report*.tex`；`CET6.tex` 按用户
指示排除，`CET6.source-damaged.backup.tex` 只作 UTF-8 读取，未因乱码停滞。现有扫描导航为：

```text
test.tex = 13 candidates (LEX-META-02=10, LEX-MARKET-01=3)
final conclusions report = 8 (主要为 LEX-ORDER-01)
unified59 / v2 = 6 each (LEX-CONTRAST-01=4, LEX-COACH-01=2)
damaged backup = 0
```

这些课程报告里的“不是中间带，而是边缘带”“不是猜均值落点，而是先缩窗”确有明确学习动作。它们没有“问题 X 分析”
标题，也不在 `MODELING` 场景触发新规则。零命中只是设计边界在这批 GPT 课程材料上成立，不是人写对照、准确率或质量证明。

### 72.4 回归与 projection

```text
main.tex, scene=MODELING
LEX-QUESTION-ANALYSIS-CONTRAST-01 = 4 REVIEW candidates
locations = 问题一至四分析；问题五误报已排除

fixed tests = 8 / 8 OK
positive = 三个完整问题分析小节触发
negative = 两个小节不触发；非“问题 X 分析”课程标题不触发
protected = 第三个对照置入 verbatim 后不触发

primary/repro files = 38 / 38
manifest raw bytes equal = true
projection file bytes equal = true
source_currentness = PASS
capability_source_sha256 = 275f476b756f7f07ecfa1b0b3c08410a3617287e8b40e51199d629fef4cabea8
projection_tree_sha256 = f93756a077079404dafc805a1714abec2df5f732e06e80fbd43131f7ea4c9af0
manifest_sha256 = 8644bf652a2594eaff61e0cb2a9f3ed6be2af3fe0aae34a2d9a9f5f31f52b812
historical_authenticity = NOT_EVALUATED
same_privilege_tamper_resistance = NOT_EVALUATED
```

这里的机械通过不证明该规则具有语料外泛化能力，不证明作者身份、检测结果、读感收益、学术正确性或 external
paired-quality clearance。它只把已写入建模场景却未执行的跨小节约束，收紧为可审计、可反例攻击的候选检测。

## 73. 2026-07-23：v1.51 证据格式绑定、旧归档兼容与最终源绑定复验

### 73.1 当前权威版本与回归基线

本节只更新现行实现事实，不追认历史质量结论。当前版本面为：

```text
projection policy / builder = 1.51.0 / 1.51.0
qualification contract      = 2026-07-22.2
qualification requirements  = 2.13.0
oracle catalog              = 1.14.0
direct evidence             = humanize-direct-validation-evidence/v4
invocation                  = humanize-validation-invocation/v3
content-addressed run id    = hvr3-<sha256>
replay result               = humanize-validation-replay/v2
```

补丁后的完整命令为：

```powershell
python -X utf8 -m unittest discover -s tests -p "test_*humanize*.py"
```

实测输出是 `Ran 1173 tests in 805.769s`、`OK (skipped=8)`，进程退出成功。准确计数为 1165 项执行通过、
8 项环境相关跳过；不能写成“1173 项全部通过，另有 8 项跳过”。本轮新增 legacy replay 回归后，完整 replay
模块为 23 项通过；此前六个格式命名探针也全部通过。完整回归覆盖现有 30 个 `test_*humanize*.py` 模块，仍只证明
这些模块编码到的合同。

### 73.2 语料驱动同义换壳与显式格式绑定

连续阅读此前 GPT 科研 TeX/MD 后发现，删除“为后续研究奠定基础”并不能阻止模型换成“为理解该现象的内在机制
提供了线索”。现行词库将其作为独立的 `LEX-FUTURE-02` 抽象收益回填候选，并保留“确有具体解释功能时可按 finding
给位置级 KEEP 理由”的专业文本边界；scanner、统一验证器、候选队列和 quick checklist 均有对应回归。这里检测的是
功能壳迁移，不把“线索”单词本身列为禁词。

另一个缺口来自文件后缀与真实语法不一致：`.txt` 默认按 Markdown 推断，若内容实际是 TeX，调用方必须在
create/finalize/build/validate 链显式绑定 `document_format=TEX`。evidence v4 把解析后的格式写入 invocation v3，
replay 必须逐项复用；bundle、evidence 或 invocation 中任一格式不一致均拒绝。新增回归直接使用 `.txt + explicit TEX`，
验证 TeX 注释变化被拒绝、格式字段进入证据、离线 replay 仍按 TeX 解释。AUTO 推断没有被偷偷改成内容猜测，避免
不同入口对同一文件产生两种保护边界。

### 73.3 旧 invocation 的追溯拒绝缺陷

当前 invocation v3 新增 `paired_quality_verifier_sha256` 与 `paired_quality_contract_sha256`，总计要求八项 policy hash。
旧 invocation v1/v2 发布时只有 validator、invariant checker、scanner、lexicon、report extractor 与 runtime contract
六项。旧 replay 曾把后来新增的两项追溯要求到 v1/v2，导致结构完整的真实旧记录在解析阶段被误报
`INVALID_SCHEMA`。

修复后 policy hash 集按 invocation schema 版本化：v1/v2 只要求其发布时的六项，v3 继续严格要求现行八项；未知字段、
自哈希、run ID、闭集、跨工件绑定和策略漂移门均未放宽。独立合成回归覆盖 v1+evidence v2、v2+evidence v3，并证明
伪装成 v3 却缺少新增两项 hash 仍被 `INVALID_SCHEMA` 拒绝。

两份真实旧归档的当前重放结果为：

| 归档 | invocation | 完整性 | 当前策略 | 重执行 | 最终状态 |
|---|---:|---|---|---|---|
| `build/direct-validation-v28-final2-20260718` | v1 / `hvr1-*` | `PASS` | `POLICY_DRIFT` | `NOT_RUN` | `REVIEW/2` |
| `build/direct-validation-v29-smoke` | v2 / `hvr2-*` | `PASS` | `POLICY_DRIFT` | `NOT_RUN` | `REVIEW/2` |

这只是 `SELF_CONSISTENCY_ONLY` 的只读兼容：旧记录可被理解，但不会补写为新 schema，不会在当前 policy 下重新获得
PASS，也不会产生 humanize quality 或 academic correctness 声明。

### 73.4 旧投影失效与当前双投影重建

replay 脚本属于 projection policy 的 `exclude_exact`，不会进入生成器能力目录，但其字节属于 evaluation surface。
因此 replay 修复后，原 `humanize_projection_v151_primary/repro` 仍满足彼此 manifest 和 39 个投影文件逐字节一致，
却对当前源树正确返回 `projection manifest source does not replay from source`。它们只能作为修复前快照，不能继续写成
current。

随后从同一冻结源独立构建：

```text
primary = C:\Users\Lenovo\.codex\tmp\humanize_projection_v1511_legacy_replay_primary
repro   = C:\Users\Lenovo\.codex\tmp\humanize_projection_v1511_legacy_replay_repro

files per projection       = 39 / 39
path or SHA-256 differences = 0
manifest raw bytes equal   = true
manifest SHA-256           = 279763cd3f2170ac637f4f5d7bb07cd9ba8fed3912379043eccada932af0906f
projection tree SHA-256    = af74debe1815e096c536ffbb4c3b5855783baebb2e0a641ab62705d03a665595
capability source SHA-256  = 7f26a385b1d50d663bb906428f31962d2c1d01fdb6553f1164c3283e6836eafe
evaluation surface SHA-256 = 90d8b2b95af780ce1db0134dc57c745d41f33ec98c2dd1b7f4397446a05f1ede
inventory SHA-256          = 3b2238d6959aa805fdd2b65fddb7c0d1a7b574f37195536e993e01d176239ea3
builder executable SHA-256 = 1153b66f730a69ffb314c06c1d4a4c96ed64a74f9d848b6f48334d4a92d0a08c
verification scope         = SOURCE_BOUND_CURRENT
source currentness         = PASS
historical authenticity    = NOT_EVALUATED
same-privilege resistance  = NOT_EVALUATED
```

能力树哈希保持不变而 evaluation surface/inventory 改变，正是“兼容修复不进入生成器能力面，但审计面仍能感知”的预期
结果。`SOURCE_BOUND_CURRENT` 只证明此刻源树可重放，不能证明历史真实性或同权限攻击抵抗。

### 73.5 资格、验证环境与独立 QA 边界

默认资格审计的实测状态仍为：

```text
evidence_integrity_status = PASS
qualification_status      = NOT_EVALUATED
atoms                      = 0 PASS / 0 FAIL / 188 NOT_EVALUATED
academic_correctness       = NOT_EVALUATED
observed exit              = 2
```

Windows 默认 GBK 可能让官方 `quick_validate.py` 读取 UTF-8 中文时失败；使用 `PYTHONUTF8=1` 或 `python -X utf8`
后验证为 `Skill is valid!`。这属于启动环境要求，不应通过改写 Skill 为本地代码页来规避。

此前两次独立格式/真实前向代理因平台 `429` 失败，状态均为 `NOT_EVALUATED`；本轮另有一次 fresh main.tex
前向复测成功留下可复放工件，但它仍不是外部质量 clearance。该复测读取用户标注的 GPT TeX 原件，在隔离临时目录只
处理“问题三模型的分析与改进”一节：源文件 SHA-256 为
`f97c5dc63e66d094e2ec73fbd2c935393a3370229db1d46baae9772bdacd0625`，选区第 417--420 行与 frozen before 逐字匹配，
source `source_file_modified=false`。最终候选删去编辑性自证/局限后台壳，但保留公式、数值、条件、模态和“引入实测数据、
补充分岔图/相图/尾窗特征、由问题四承担严格识别”的具体研究动作；前向状态为
`hard=PASS / speech_act=PASS / style_signal=PASS / candidate_assembly=PASS / mechanical=PASS / delivery=REVIEW`，
`paired_quality_review_status=PENDING_EXTERNAL_REVIEW`、validator exit `2`。两次缺陷试跑分别被 speech-act `REVIEW` 和
`PROTECTED_MATH_CHANGED` 拒绝，未进入最终证据包。工件位于
`C:\Users\Lenovo\.codex\tmp\humanize_fresh_main_tex_forward_retry\`，其 direct evidence 为 v4、run id 为
`hvr3-43b105c3f93c061c47f1ef3d1685dd1bf1adcfae58fe5d9176af876a60850096`。按当前安装版重放时，外层
capture 为 `record_integrity=PASS / capture_integrity=PASS / reexecution=NOT_RUN /
CAPTURE_OR_VALIDATOR_POLICY_DRIFT / REVIEW/2`；独立父进程观察到 replay 进程实际退出码为 2。内层
validation record 则为 `SELF_CONSISTENCY_ONLY / reexecution=PASS / PASS/0`，但其记录的交付门仍为
`REVIEW/2`。两层状态不同：内层 PASS 不得外推为 capture 可重执行、候选质量通过或正式交付。

报告一致性子代理完成的是只读审计，不是文风前向评测；其一度给出的测试总数与主进程完整实跑冲突，已按权威输出丢弃。
没有可靠外部 paired-quality、真人对照或作者验证，故本节不能把 1173 项回归、双投影、真实旧归档重放或这一次局部
前向候选外推成自然度、学术正确性、作者身份、稳定生成能力或无人值守交付资格。

## 74. 2026-07-23：CET-6 路由、三候选盲审与真实漏检闭环

### 74.1 真实材料先暴露的是路由缺口

本轮前向材料不是为测试临时编造的短句，而是从用户指定的 GPT 生成 CET-6 TeX 中冻结出的完整课程单元。冻结 before
为 `C:\Users\Lenovo\.codex\tmp\hac_forward_cet6_local\before.tex`，SHA-256 为
`ffc81195384a78eebaa60e2615196c659f212db92d61a86f8a265e35b9cc98a8`。该单元讨论长篇段落匹配题应先做哪几道、
下一道向哪里找、如何用已完成题目缩小其他题目的搜索范围；其功能是考试策略讲解，而不是把考试题目作为研究对象。

scene policy revision 4 对该真实摘要只命中共享的“摘要”标题信号，实测为：

```text
COURSE=0 / MODELING=0 / RESEARCH=1
status=FALLBACK_GENERAL
final_scene=GENERAL
```

这不是措辞层的小偏差。若 COURSE 单元落入 GENERAL，后续讲义声线、轻口语保护和课程专属负向门都可能不执行。revision 5
因此增加窄化的 `COURSE-EXAM-STRATEGY-01`，只识别“做题顺序、先做哪几道、下一题往哪里找、缩小搜索范围”等教学
动作，不把“考试”“题目”本身当作课程证据。使用冻结单元的真实标题路径“六级长篇段落匹配做题规律总报告/摘要”重放：

```text
COURSE=10 / MODELING=0 / RESEARCH=1
status=ROUTED
final_scene=COURSE
margin=9
policy_revision=5
policy_sha256=7f4919b7df6aee03bb93b0f9f20cfe5d7a5724e2297e404dcfa0980fe474cebb
```

其中 COURSE 标题贡献 4 分，正文中三个有界教学动作贡献 6 分；共享“摘要”只给 RESEARCH 1 分。反向样本“研究方法 / 
本研究分析考试题目在不同年份的分布，并讨论样本范围”仍为 `COURSE=0 / MODELING=0 / RESEARCH=6 / ROUTED
RESEARCH`。这项反例证明修复绑定的是教学行为，不是主题词。

### 74.2 三个候选 checkpoint 不能混写成一个“第二稿”

三轮候选都绑定同一 before，但用途和当前状态不同：

| checkpoint | after SHA-256 | 当时机械层 | 当时 paired quality | 当前解释 |
|---|---|---|---|---|
| 本地初稿 | `51371fd7f25cb3742958e94699150719c0f6e13b90a86e84445e9b988829305a` | `REVIEW/2` | `BLOCKED_BY_MECHANICAL_GATE` | 五类言语行为变化，未进入质量复核 |
| 本地修订稿 | `5f93a4749c6854c7be566c2c734d06744fcf14f88e2e07004ccb3757c0d8bf47` | `PASS/0` | `PENDING_EXTERNAL_REVIEW` | 仅是历史机械 checkpoint，不是当前权威候选 |
| 独立前向候选 | `ebc1ad26c143f244fb7a8ec46768439d348629fa0c194dbeefe76d7857cf072c` | 修复前 `PASS/0`，修复后 `REVIEW/2` | 修复后 `BLOCKED_BY_MECHANICAL_GATE` | 独立盲审发现真实漏检，成为本轮回归输入 |

本地初稿同时触发：

```text
SPEECH_ACT_NEGATION_CHANGED
SPEECH_ACT_MODALITY_SCOPE_CHANGED
SPEECH_ACT_FOCUS_SCOPE_CHANGED
SPEECH_ACT_LOGICAL_RELATION_CHANGED
SPEECH_ACT_CONDITION_CHANGED
```

其 `hard=PASS / speech=REVIEW / assembly=REVIEW / mechanical=REVIEW / delivery=REVIEW/2`，paired-quality 请求固定为
`BLOCKED_BY_MECHANICAL_GATE`。这证明保护 TeX、数字和引语并不等于语义行为没有变化。

本地修订稿和独立前向候选在旧规则下都曾得到 `hard/speech/style/paired-style/assembly/mechanical=PASS`，但交付仍为
`REVIEW/2`，因为 `paired_quality=PENDING_EXTERNAL_REVIEW`、`humanize_quality_claim_allowed=false`。这里的机械 PASS
从未等于自然度通过，只是当时没有发现机械阻断项。

### 74.3 独立盲审推翻了“机械 PASS 即可收尾”

独立审阅者只获得 before/after 工件和通用成对审阅任务，没有收到预设缺陷答案。其结论是全文总体中等改善：TeX 控制行、
12 个列表项、11 处中文引语、59 套/590 题及位置百分比均保持；部分解释性填充和重复确实减少。但它同时定位了三类问题：

1. 第 33、35 行把“第一/第二种误判是：觉得……”改成“第一/第二种误判是，认为……”，逗号切断“是认为”的谓语结构；
2. “后面所有主要结论，默认都来自这同一批样本”被收紧成“主要结论均来自这批样本”，可能从默认口径滑向无例外断言；
3. “放在一个连续推进的过程中处理”比原稿“看成一个连续推进的过程”更迂回，且仍残留“概括为以下 6 点”“样本口径如下”等模板表达。

这组证据没有被扩张成“均来自”“认为”“默认”或正式词汇的禁词表。修复只编码两个可证明的窄边界：

- `默认` 加入 `modality_scope`；删除、新增或迁移都进入 `SPEECH_ACT_MODALITY_SCOPE_CHANGED`，由内容责任方确认断言力度；
- COURSE 场景新增 `LEX-COURSE-COPULAR-COMMA-01`，只匹配“（第 N 种）误判是，认为/觉得/以为/把/将”这一病句结构，
  不匹配“误判是：觉得……”“误判是把……”“问题是，认为……”或 RESEARCH 文本。

升级后的统一验证器重放 `ebc1...` 候选得到：

```text
hard_invariant_layer_status=PASS
speech_act_layer_status=REVIEW
style_signal_layer_status=REVIEW
paired_style_delta_layer_status=PASS
candidate_assembly_status=REVIEW
mechanical_validation_status=REVIEW
paired_quality_review_status=BLOCKED_BY_MECHANICAL_GATE
delivery_gate_status=REVIEW
exit_code=2
academic_correctness=NOT_EVALUATED
humanize_quality_claim_allowed=false
```

言语行为层命中被删除的一处 `默认`；词项层分别在第 33、35 行命中
`LEX-COURSE-COPULAR-COMMA-01`。这说明修复针对的是一次真实“机械 PASS、人工仍能立刻指出缺陷”的漏检，而不是为了增加
测试数量另造规则。

### 74.4 记录重放、退出码和证据边界

当前直接证据位于
`C:\Users\Lenovo\.codex\tmp\hac_forward_cet6_agent_v2\validation-evidence-v3-maturity\`，run ID 为
`hvr3-29c934eb1da5b8b6386569ff517e9246ed1a63d03682ded4a08d60fbebc5ba5f`。其记录完整性仍为 PASS，但此后文档协议
标识与 projection policy 批准哈希发生了受控更新；用当前安装版重放时正确返回：

```text
scope=SELF_CONSISTENCY_ONLY
record_integrity_status=PASS
reexecution_status=NOT_RUN
reason=POLICY_DRIFT
replay_status=REVIEW
replay_exit_code=2
```

旧记录可证明当时工件自洽，不能冒充当前策略下的重新执行。宿主命令工具会把子进程的任意非零码表面归一显示为 1；独立
PowerShell 父进程可读到真实 `CHILD_EXIT=2`。因此 Skill 的协议仍保持 `PASS/0、FAIL/1、REVIEW/2`，不能为了适配显示层
而把 REVIEW 改成 FAIL。

### 74.5 协议 currentness 与 v1515 checkpoint 双投影

审计还发现 `course-notes.md` 与 `workflow.md` 一度仍写
`humanize-course-voice-non-regression/v2`，而验证器运行时已发出 `/v3`。两处文档现已与代码统一为 `/v3`。由于它们都在
生成器能力面内，这不是“只改文档”：旧 capability hash `b4dee6...0bcc` 立即失效，批准绑定更新为：

```text
approved capability SHA-256 = 871f62a8ba79ec141eb34cf7ce6908b9481c24a622a9f6cc7f1472066f3b71cb
```

文件白名单、4 个转换规则、排除面、builder hash 和 transform hashes 均未放宽。随后从同一冻结源独立生成：

```text
primary = C:\Users\Lenovo\.codex\tmp\humanize_projection_v1515_protocol_current_primary
repro   = C:\Users\Lenovo\.codex\tmp\humanize_projection_v1515_protocol_current_repro

files per projection       = 39 / 39
path or SHA-256 differences = 0
manifest raw bytes equal   = true
manifest SHA-256           = 55510fde123f41e525f599579d2909f8bd883c9a5f71ad88ec62ed72f11df87f
projection tree SHA-256    = 6ec771e2aec6eb7f347dd373aa6c1612a178aaf830e8e9f36df35cac00508473
capability source SHA-256  = 871f62a8ba79ec141eb34cf7ce6908b9481c24a622a9f6cc7f1472066f3b71cb
evaluation surface SHA-256 = e2cb791a28bf107e18bda0ef5c7926bcefe7b8e8577723b574119147b0d3472d
inventory SHA-256          = 4b289663b5042c7633348594c83ca09e4191f3d403b3d86138338c7deb4f3a74
verification scope         = SOURCE_BOUND_CURRENT
source currentness         = PASS
historical authenticity    = NOT_EVALUATED
same-privilege resistance  = NOT_EVALUATED
```

v1514 及更早投影仍可作为历史快照，但不得继续声称对应当前源。

### 74.6 稳定源回归与当前结论上限

在所有 Skill 文件冻结后，权威验证结果为：

```text
validate_humanize_output module = 108 tests / OK
projection dedicated module     = 17 tests / OK
qualification audit module      = 44 tests / OK
full regression                 = Ran 1234 tests in 921.207s
full result                     = OK (skipped=8)
quick_validate                  = Skill is valid!
compileall                      = PASS
```

默认资格审计仍为：

```text
evidence_integrity_status=PASS
qualification_status=NOT_EVALUATED
atoms=0 PASS / 0 FAIL / 188 NOT_EVALUATED
cases_total=0
academic_correctness=NOT_EVALUATED
exit_code=2
```

因此本轮可声称的提升是：真实 COURSE 漏路由被修复；一次真实盲审发现的句法和模态漏检已进入窄化、可回归的机械门；协议
标识、批准能力面与双投影重新 current；1234 项稳定源回归通过。仍不能声称独立前向候选已经自然、学术正确、作者本人化，
也不能声称生成资格或无人值守交付已完成。下一轮成熟化应继续使用新的真实长文成对样本和外部盲审寻找“机械 PASS 但人工
可定位退步”的缺口，而不是继续扩张孤立禁词。

## 75. 2026-07-23：v1516 残余分诊、反过拟合门与源绑定复验

### 75.1 独立残余审计没有把所有不顺眼表达都升级成规则

本轮继续复读同一组真实 CET-6 成对工件，而不是根据既有修复反向编造测试：

```text
before    = C:\Users\Lenovo\.codex\tmp\hac_forward_cet6_local\before.tex
candidate = C:\Users\Lenovo\.codex\tmp\hac_forward_cet6_agent_v2\candidate.review.tex
```

独立只读审计再次确认两类可稳定定位的缺陷。第 33、35 行的“误判是，认为”是重复出现的系词谓语断裂，现有
`LEX-COURSE-COPULAR-COMMA-01` 足够窄；删除“默认”并改成“均来自”可能收紧断言范围，现有
`SPEECH_ACT_MODALITY_SCOPE_CHANGED` 足以要求内容责任方复核。两项都不需要禁止“认为”“均来自”，也不需要把所有
“是，……”列为错误。

审计同时指出三个容易诱发过拟合的观察：

- “放在一个连续推进的过程中处理”在该候选里比“看成一个连续推进的过程”更迂回，但仍可有合法语法和操作含义；
- “可以概括为以下 6 点”在真实 TeX 和工作流说明中都有承担摘要职责的实例；
- “样本口径如下”在当前上下文带有模板感，但单次出现不足以证明跨文档稳定病灶。

因此本轮没有把三者写入 `lexical-signals.json`，也没有形成“见词即删”的替换表。是否构成退步取决于改后有没有新增
顺序、操作、分组或条件信息，以及该表达在段落中的职责和跨语料重复密度。这个结论来自成对阅读，不是词频表或模型自评。

### 75.2 `NOTE-HUM-41` 把“不升级”本身变成可审计决策

`course-notes.md` 新增 `NOTE-HUM-41 MUST`，`workflow.md` 在 COURSE 成簇门之后增加对应残余分流。它要求每个观察至少
记录改前/改后完整句、变化的谓词与对象、是否产生信息增益、跨语料 occurrence 数和未升级理由。只有重复证据足够且能够
构造正反例时，才考虑进入机械规则；否则保持 `NO_CHANGE`、局部回退或送 paired review。

这一规则刻意不进入词项注册表，不计入 high finding 覆盖率，也不能被模型自评升级成质量 clearance。新增回归
`test_course_residual_triage_is_explicit_without_becoming_a_blacklist` 同时断言：规则存在于课程说明和工作流中，三个观察词形
可被审计者看到，但 `lexical-signals.json` 中不存在 `NOTE-HUM-41`。COURSE 场景规则总数由 40 增至 41；新增的是分诊合同，
不是第 41 个禁词。

### 75.3 v1516 双投影重新绑定当前能力面

`NOTE-HUM-41` 和工作流分流位于 generator capability surface，因此旧批准哈希不能沿用。构建器按冻结 inventory 重新计算
能力源后，只更新 `generator-projection-policy.json` 的 `approved_capability_source_sha256`；policy/builder 语义版本仍为
`1.51.0`，include/exclude 列表、4 个 transform、builder executable hash 和 transform hashes 均未改动。两次独立构建为：

```text
primary = C:\Users\Lenovo\.codex\tmp\humanize_projection_v1516_protocol_current_primary
repro   = C:\Users\Lenovo\.codex\tmp\humanize_projection_v1516_protocol_current_repro

files per projection       = 39 / 39
path or SHA-256 differences = 0
manifest raw bytes equal   = true
manifest SHA-256           = a7eb772318462759717a63f37ec260db61dd77b2bfdecb524c7313d532194963
projection tree SHA-256    = df245c7ca154dae562179c412bf39a09a702b8bd5df9da65460432711da0d528
capability source SHA-256  = da4d94202e4a264f6effe42bed07d8918720631e825298244e4c1b7037ea439e
evaluation surface SHA-256 = 7cc58567a1474c32653d9e2c532f45681667febd2ae5de05366a044fdc01e239
inventory SHA-256          = 6ad79e4cfe8b967a46013859c01396dd58a2aaad631761f85322730131c9789e
derived artifact SHA-256   = 4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945
verification scope         = SOURCE_BOUND_CURRENT
source currentness         = PASS
historical authenticity    = NOT_EVALUATED
same-privilege resistance  = NOT_EVALUATED
```

两份 manifest 不只是摘要哈希相等，其原始字节、source 记录和 39 条文件记录也完全相同；两次 verifier 都重新读取当前
Skill 源树并返回 `SOURCE_BOUND_CURRENT/PASS`。v1515 仍是可追溯历史 checkpoint，但不再代表当前能力面。

### 75.4 验证矩阵与资格上限

源文件和投影冻结后的实测结果为：

```text
core skill + lexical + validator modules = 214 tests / OK
projection dedicated module              = 53 tests / OK (skipped=1)
qualification audit module               = 44 tests / OK
full stable-source regression             = Ran 1235 tests in 800.508s
full result                               = OK (skipped=8)
quick_validate (-X utf8)                  = Skill is valid!
compileall                                = PASS
```

`quick_validate.py` 首次按 Windows 默认 GBK 读取 UTF-8 `SKILL.md` 时抛出 `UnicodeDecodeError`；以 `python -X utf8` 重跑
同一校验器后通过。该事件是启动编码差异，不通过改写中文文件或忽略校验来掩盖。

默认资格审计仍诚实返回：

```text
evidence_integrity_status = PASS
qualification_status      = NOT_EVALUATED
atoms                      = 0 PASS / 0 FAIL / 188 NOT_EVALUATED
cases_total                = 0
academic_correctness       = NOT_EVALUATED
report exit_code           = 2
```

因此 v1516 的成熟化增量是：真实残余不再只能在报告里留下主观评论，现有一条可执行、可测试、明确拒绝过拟合的分诊协议；
能力面、策略批准和双投影重新 current；完整回归新增一项并保持通过。它仍没有提供外部 paired-quality、真人作者对照、学术
正确性或 188 原子生成资格证据。下一轮应继续对新的真实 MD/TeX 成对候选做独立盲审，优先收集可重复的谓词空转、断言
力度漂移和段落职责错位；只有证据跨样本稳定时才升级机械门。

## 76. 2026-07-24：v1.52.0 生产工具链冻结与质量授权隔离

> 本节是唯一当前冻结口径。第 75 节及更早章节中的版本、测试数、原子数与投影哈希全部保留为历史过程证据，不再代表当前安装源。

### 76.1 冻结对象不是“万能改写模型”，而是候选与审计工具链

本轮首先收窄“成熟”的含义。`humanize-academic-chinese` 当前可以生产使用的职责包括：按 supplied content 起草、定位中文学术
模板病灶、生成待审改写候选、保护数字/数学/TeX/代码/引语/模板字段、对长文建立快照和覆盖账本、拒绝静默假完成，以及把
direct validation、父进程 capture、replay 和 paired-quality request 绑定到精确版本。它不能判断事实、引文、计算或学术结论是否
正确，也不能给自己的候选签发最终读感 clearance。

这一边界不是保守措辞，而是当前状态机的硬事实：机械层可以 PASS，顶层仍因可信外部成对质量复核缺失而保持 `REVIEW/2`；
学术正确性固定为 `NOT_EVALUATED`；本地 agent 名称、理由字符串、模型自检和同权限重放都不能建立真人身份或外部信任根。
因此本轮冻结名称为“生产级中文学术文风候选生成与审计工具链稳定版”，不使用“无人值守终审模型”“已完全人类化”或
“稳定生成最终合格论文”等越界称谓。

### 76.2 当前能力面、规则面与投影面

当前安装版共 82 个非缓存文件，`SKILL.md` 为 455 行，保持在 skill-creator 建议的 500 行入口上限以内；复杂合同继续放在
`references/`，确定性流程放在 `scripts/`。词项数据面仍是 39 组 signal、208 个固定变体和 58 个正则。这里的数字只说明可定位
覆盖面，不表示有 208 个“禁词”：单项命中必须经过上下文、保护状态、重复窗口、场景和 KEEP 理由裁决；`NOTE-HUM-41` 继续
要求对单例不顺表达做成对分诊，证据不足不得升级黑名单。

policy/builder 升为 `1.52.0`。两份 current projection 的冻结基线为：

```text
primary = C:\Users\Lenovo\.codex\tmp\humanize_projection_v1520_final_primary
repro   = C:\Users\Lenovo\.codex\tmp\humanize_projection_v1520_final_repro

files per projection          = 39 / 39
excluded audit/evaluation     = 43
path or SHA-256 differences   = 0
manifest raw bytes equal      = true
manifest SHA-256              = 8464cf5109865f97c193ce89c0cdf7a49846d48b29029f785fedbc573877a029
projection tree SHA-256       = 46644c75f482f88f87d89f16e93e5bee497022b3e01ef98fbdb2935bebb2301a
capability source SHA-256     = cef35dd4b48568ab2940c6f287526978bba899ac1466483fd2fadd7f684f3b76
evaluation surface SHA-256    = 669327c7577b5a12caf84923027dac7deec73adc00447a6e3849218fab33ee20
inventory SHA-256             = 830234570f7eaba78760978854438a8db64a2771bb3335a8ff56b2f0e7472f8d
derived artifact SHA-256      = 4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945
builder executable SHA-256    = 99077c4c57721d0b67f0b55654b421c3c3f3ecc804b3431b507936cd48265fba
transform dependency SHA-256  = 0f523daf2d391113983ea6007ff1f397d536d05dc4c4bd74e25a595b935a1771
transform registry SHA-256    = 92afbcb00f1ec1ad812e291d1be2530af64842ef02beafb81d123e50b9e6db78
```

39 文件投影只包含生成时需要的能力面；安装版额外 43 项为资格 oracle、trust policy、成对质量验签、capture/replay、候选队列和
second-pass 等审计面。该隔离避免生成器直接看到评分答案，但本机同权限构建仍不证明宿主 oracle 不可达，因此证据上限继续是 E2。

### 76.3 三份真实工件把“效果支持”和“最终授权”分开

本轮收尾不再只引用合成 fixture，而是固定三份真实 before/after：

| 工件 | Before SHA-256 | After SHA-256 | Current capture |
|---|---|---|---|
| Main modeling r4 | `9a435b85cdbd0aafc3260ed48fed9073297c5cd72c84a9d8ccaadbfdb2d46270` | `2e1ffbf36ff48c08576f76fee264b4da7b046e358366eba297bbdf27a1a2cc77` | `hvc1-c35f25ca35ed95608511656d64e256320bbe53f33676a1a62b89a16ae3e5deb3` |
| Modeling notes r3 | `654c7257bf3685c5d2b0c64d3fa15022d9e30f3573766ae94c42c6dae55e1c74` | `3b5dc98fc0cb73cf683e5703f6137a62361ea33ff40668ce099d46fb9364fd91` | `hvc1-e451fce2b19237991336c7c296d512eebd4b480b8b0b192ed6b947fe4722c44d` |
| CET-6 course | `0584de13acb8185c94ba35a5c48b74e909ed9cc2873cea1457fb435639c6ffcd` | `c1afab35d71804acecc20d03403f1bb03dbc5b073a877961ba8cc3aed05fef30` | `hvc1-37d60bc44137c014d4532f39cc4b2e78411fd3d89d23467dddda68401a59dfc8` |

三份 capture 均为 `capture_integrity_status=PASS`，父进程实际观察的 OS exit 均为 2，inner record、before/after 字节和 stdout 绑定
一致。三份验证器结果也一致保持：

```text
mechanical_validation_status=PASS
delivery_gate_status=REVIEW
paired_quality_review_status=PENDING_EXTERNAL_REVIEW
paired_quality_clearance_granted=false
academic_correctness=NOT_EVALUATED
humanize_quality_claim_allowed=false
```

Main r3 曾把“问题四沿用参数轴”扩大为“问题三和问题四使用同一参数轴”，又把相对建议形式化成“论文写作宜……”。r4 只回退
这两个局部退步，保留其余安全改动；两份独立 pairwise 阅读均偏好 r4，其中一份仅为小幅偏好。Modeling notes r2 倾向全面
正式化，把“用、先做、再写、重点放”统一成“采用、建立、呈现、收录”；r3 恢复直接的提纲语气，一份可定位的独立阅读偏好 r3。
这组证据说明“更书面”不等于“更自然”，局部回退常比继续同义轮换更可靠。

盲审原始记录只以 `ADVISORY_ONLY` 台账归档。Main 有两条，Notes 只有一条，CET-6 没有；未找到的
`/root/blind_r3_sol_a` 不补写，不把 agent 名称当真人身份，也不把 `BETTER` 票数转换为 paired-quality clearance。台账位于：

```text
C:\Users\Lenovo\.codex\reports\humanize-academic-chinese-v1.52.0-final\advisory-blind-review-ledger.json
```

### 76.4 回归、资格与成熟度数字的正确解释

正式冻结完整回归为：

```text
full regression = Ran 1277 tests in 821.729s
full result     = OK (skipped=8)
observed OS exit = 0
executed pass   = 1269
environment skip = 8
```

1277 是 discovered tests，不是“1277 项通过再另加 8 项跳过”。测试通过证明已编码合同、攻击 fixture 和重放路径没有回归，不能证明
任意新文本都会更自然。默认资格审计按 2026-07-24.1 合同扩为 193 个原子，实测仍为：

```text
evidence_integrity_status = PASS
qualification_status      = NOT_EVALUATED
atoms                      = 0 PASS / 0 FAIL / 193 NOT_EVALUATED
cases_total                = 0
academic_correctness       = NOT_EVALUATED
report exit_code           = 2
```

193 比旧 188 多，不是倒退，而是资格面新增了未被伪装成已测的原子。当前 local runner 最高 E2；E3 需要代理不可伪造的盲前向隔离，
E4 需要可验证的人类身份与独立评审。缺少这些可信链时，零 PASS 是诚实状态，不应用单元测试、投影一致性或三条 advisory 票覆盖。

据此，本轮将成熟度拆为两个数字：

- 候选生成、保护、拒错、长文事务、证据与重放工具链：约 90%，可冻结为生产稳定版；
- 生成模型“无需外部复核即可稳定产出最终学术稿”的资格：`NOT_EVALUATED`，不折算成虚假的百分比。

剩余约 10% 不应靠继续堆禁词补齐，主要需要外部 paired-quality 服务、真实 E3/E4 盲测、更多跨场景 before/after 和独立学科审查。

### 76.5 冻结后的变更纪律

v1.52.0 冻结后执行以下纪律：

1. 单篇文本中的一次不顺表达只进入 residual triage；没有跨样本、正反例和稳定触发，不新增禁词或泛正则。
2. 任何 generator capability surface 变化都升新版本、重建 primary/repro、复核 manifest 原始字节和 current-source binding。
3. 机械 PASS、direct replay PASS、capture integrity PASS、模型自检与 advisory 盲审一律不得签发质量 clearance。
4. GPT 生成的 MD/TeX 继续只作负例和压力材料，不能成为真人 Voice、事实源或 production positive action。
5. 后续迭代以真实成对工件、独立盲审、局部回退和跨样本复现为主要证据，不以规则数、报告行数或措辞更正式作为收益代理。

当前冻结证据目录为：

```text
C:\Users\Lenovo\.codex\reports\humanize-academic-chinese-v1.52.0-final\
```

其中 `captures/` 保存三份 current capture，`advisory-blind-review-ledger.json` 保存不具 clearance 权限的盲审偏好，
`generation-qualification-default.json` 保存诚实的默认资格三态，`full-regression-process.json` 与日志保存完整回归父进程事实，
`final-freeze-audit.md` 保存冻结边界；最终命令、哈希和回归结果由 `run_metadata.json` 绑定。任何一项后续发生漂移，都应创建新 checkpoint，
不得继续借用 v1.52.0 的“当前”称谓。
