---
name: humanize-academic-chinese
description: 纯中文学术文风 Humanize、材料约束起草、待审候选生成与机械审计工具，用于“去 AI 味、人工润色、学术文本自然化、全文去模板、减少机器腔、消除套话与过度工整、按检测报告标注定点润色”，也用于按用户给出的要点、事实表、研究记录或课程材料起草中文学术初稿；起草只组织 supplied content，缺口省略或保留占位。覆盖学术文本生成后的纯文风终审辅助、本科/专科/硕博论文、社科、人文、法学、课程讲义、数学建模、工程论文、科研稿、MD/TEX/TXT 长文和报告辅助改写。检测报告或检测器标注只能作为候选范围线索，不用于判断作者身份、预测或优化分数；拒绝目标百分比、规避检测和操纵检测器。Humanize or draft Chinese academic writing from user-supplied content, preserving author voice and protected content while revising rhythm, emphasis, transitions, explanation density, and endings. Produce review candidates and mechanical evidence; do not claim final quality clearance without an external trusted review. Do not invent missing facts. Do not promise detector outcomes, optimize scores, evade detection, judge academic correctness, verify evidence or citations, or infer authorship.
---

# Humanize Academic Chinese

PowerShell 先执行 `$skillRoot = Join-Path $HOME '.codex\skills\AIGC\humanize-academic-chinese'`。所有命令均从该根调用，不依赖当前工作目录。

## 唯一职责

只改变中文学术文本的可感知文风：词句复用、衔接、节奏、段落重心、解释密度、腔调和收尾。让作者的真实选择可见，不把所有文章改成同一种“克制学术腔”。

不得判断内容对错、来源真伪、科研质量或作者身份；不得承诺检测规避；不得用错字、病句、随机拆句、虚构经历或口语填充制造假人味。GPT 生成的 MD/TeX 只能作为负例或压力材料，不能充当真人正向声线。

## 触发与边界

以下请求由本 Skill 接管：去 AI 味、去模板、减少机器腔、人工润色、学术文本自然化、全文或局部文风统一，以及按 supplied facts/notes 起草学术正文。后一类固定为 `DRAFT`，信息不足时省略或保留占位，不补造事实。

检测报告任务使用 `report_context=REPORT_INFORMED`。标红和分数只决定优先阅读范围；不得预测、承诺或优化检测结果。混合请求只执行可分离的纯文风部分；含目标百分比或规避要求时，先简短拒绝该目标，再处理可分离正文。报告文件需按 [detector-report-intake.md](references/detector-report-intake.md) 建立 scope；内联标红固定为 `INLINE_SELECTION/REVIEW`。

“终审”只表示生成待审候选、机械证据和复核请求。没有可信外部成对质量复核时，不得声称文风已经最终通过。

## 默认配置

```text
mode=REWRITE
scene=AUTO
intensity=BALANCED
output=CLEAN
voice_profile=NONE
voice_disclosure=SCENE_DEFAULT
report_context=NONE
lexical_policy=STRICT_CORPUS
```

没有作者样本时必须写 `voice_profile=NONE; voice_disclosure=SCENE_DEFAULT`，不得声称保留了个人声线。
`STRICT_CORPUS` 不得由模型自行降级。它把语料词库中的 1417 个词和词组视为默认禁用项；
保护区自动 KEEP，正文中的专业术语只能用绑定具体 `SIGNAL_ID@LINE:COLUMN` 或 finding hash 的
功能理由例外保留。泛称“这是术语、符合语境、原文如此”不是有效理由。

## `REWRITE/DRAFT` 必做主路径

任何 `REWRITE` 或 `DRAFT` 都执行本节；一句内联文本、“只输出正文”和看似无保护内容的文本均不豁免。`DIAGNOSE` 不生成候选，不走发射步骤。

1. 冻结 `mode`、解析后的 `scene`、`document_format` 和可见输出。将原文或 supplied content 写入 UTF-8 before。先运行 `scan_humanize_chinese.py`；读取全部 `LEX-STRICT-CORPUS-*` finding，按意群建立位置清单后才写 UTF-8 after。只凭整体读感判断“没有机器腔”无效；不得先回复正文、事后补扫描或验证。
2. 运行唯一短文入口：

```powershell
python "$skillRoot\scripts\run_humanize_inline.py" run <before> <after> `
  --mode <REWRITE|DRAFT> --scene <RESOLVED_SCENE> `
  --document-format <markdown|tex> --visible-output <BODY_ONLY|BODY_WITH_SUMMARY>
```

只有用户明确授权某个 live 模板字段的载荷措辞时，`REWRITE` 才追加
`--template-field-edit-scope <scope.json>`。scope 必须是 source-bound strict
`humanize-template-field-edit-scope/v1`，只授予精确 `line + label` 的 `PAYLOAD_ONLY`；`DRAFT`
不得携带。缩进、label、冒号、位置和顺序组成的 header 永不可授权；scope 也不能清除字段职责、
适用范围、否定、因果或断言力度漂移，更不能替代 paired-quality 复核。

3. 读取 JSON 的 `mechanical_validation_status`、`delivery_gate_status`、`exit_code`、`run_dir` 和 `diagnostics`。先逐条处理 `diagnostics.actionable_findings`：按 `matched + line + column` 找到原位，根据 `action/rationale` 删除、改写或给位置级 KEEP 理由；不得只缩短形容词而保留同一句壳。`LEX-STRICT-CORPUS-*` 在 after 中每出现一次都必须有位置级处置，不能用一个笼统理由覆盖多个位置，也不能把它换成同组另一词。只要仍有未解释 strict finding，`NO_CHANGE`、`CLEAN` 和完成声明全部禁止。言语行为警告还带 `source_side`：`before` 表示原文中的否定、模态或主张力度在候选中丢失，应恢复原措辞或等强显式标记；`after` 表示候选新增了原文没有的力度，应删除或回退。再按其余错误码定点修复；诊断不足时才读 `validation.json`。硬保护失败时不得交付正文。`REVIEW` 的退出码是 `2`，不是脚本崩溃。
4. 每次修改 after 后重新运行。首轮先清空 strict finding，再处理普通密度和结构信号；优先删除无功能句壳，保持标题、段界、数字、否定、模态、焦点和原有言语行为谓词。不得为“换一种说法”互换“说明/表明/观察到/证明”，不得把“构建、形成、实现、支撑、保障”等同组包装词相互轮换。无法安全修复时降级为 `PATCH/ANNOTATED/UNRESOLVED`，不得回退成“无需修改”。
5. 交付前最后一步从同一 run 发射冻结正文：

```powershell
python "$skillRoot\scripts\run_humanize_inline.py" emit <run_dir> --format body
```

`emit` 会重查 before/after、validation 和 evidence manifest；验证后任何字节变化都会阻断正文。机械层 `PASS` 但成对质量仍待审时，`emit --format body` 会正常写出候选正文，同时保留进程退出码 `2` 和 `delivery_gate_status=REVIEW`；这表示“候选发射成功、质量未清关”，不是命令崩溃，也不是最终完成。发射后不得再改一个字；确需修改就生成新 after 并重跑。`emit` 只证明本地 stdout 来自冻结 after，聊天传输和 UI 渲染固定为 `NOT_EVALUATED`。

新 run 固定写 `humanize-inline-run/v3`、`humanize-inline-invocation/v2` 和
`humanize-inline-verification/v3`。wrapper 在建立 run 目录前稳定读取 scope，将原字节冻结为
`artifacts/template-field-edit-scope.json`，并把 provided/path/SHA/size/source SHA、
`PAYLOAD_ONLY` 与 `local_clearance_supported=false` 同时绑定到 invocation、run artifacts 和 direct
evidence v5 的 `inputs/template-field-edit-scope.json`；`emit` 会全部重验。旧
`run/v2 + invocation/v1` 只读兼容，不能通过改 schema 获得 scope 能力，也不能作为新记录格式。

需要核验调用方保存的可见字节时运行：

```powershell
python "$skillRoot\scripts\run_humanize_inline.py" attest <run-dir> <caller-supplied-visible-file>
```

attest PASS 只覆盖 caller-supplied bytes，不证明聊天界面、语义正确或文风质量。完整字段见 [operational-contract.md](references/operational-contract.md)，快速执行只读 [quick-checklist.md](references/quick-checklist.md)。

## 决策优先级

冲突时按以下顺序裁决：

1. 用户明确的不可改范围、输出格式和结构锁；
2. 引语、题干、OCR、代码、数学、TeX 命令等保护区；
3. 数字、单位、术语、否定、模态、焦点、定义和报告状态等语义不变量；
4. 用户指定的模式、场景、强度和 Voice Profile；
5. 体裁与场景规则；
6. 通用病灶和改写示例。

保护区逐字复制完整跨度，包括成对符号、内部标点、空格和 TeX 源码。低优先级规则不得覆盖高优先级约束；无法同时满足时返回 `NO_CHANGE` 或 `UNRESOLVED`。

源文内部冲突不属于纯文风层的裁决权限。不得自行选择其中一条主张，也不判断哪一条主张正确；两个冲突 span 都必须原样回显并标 `UNRESOLVED`，其余安全改动降级为最小 PATCH：`requested_output=CLEAN; effective_output=PATCH`。

## 模式

### `DIAGNOSE`

只诊断，不改正文。按 [operational-contract.md](references/operational-contract.md) 第 5.1 节输出可定位的 `Dominant/Recurring/Local` 病灶；短文本没有真实病灶时允许 `NO_FINDINGS`，不得凑数。用户要求“先指出再改写”时，诊断和改写分别留门禁记录。

### `REWRITE`

只重排输入中已有的事实关系，不新增作者、机构、年份、引文、数据来源、实验条件、研究路径、数值推导或未来工作。每个改后独立分句只能是 `COPY`、`ENTAILED_PARAPHRASE` 或 `DELETE_STYLE_SHELL`。

保持来源谓词和证据角色：不得把“未生成”改成“验证失败”、把“用于比较”改成“结果表明”、把“待复核”改成“已证明”，也不得把内部指标升级成外部事实。内容缺失不能改写成关系缺失；`缺少 X 层 -> 缺少 X 的衔接` 命中 `SPEECH_ACT_MISSING_CONTENT_TO_LINKAGE`，必须回退或保持 `REVIEW`。

`GENERAL` 场景只有在 before 的 strict 扫描为零、普通 Gate 也没有可定位病灶时才允许 `NO_CHANGE`。任一 `LEX-STRICT-CORPUS-*` 命中都会使 `NO_CHANGE` 失效；每处命中必须改写、删除或给位置级专业功能理由。每处改动仍要能说明读感收益；“更正式、换个说法、字数更少”不构成收益。若改句新增搭配问题、指代不明、硬被动或作者声口损失，先局部回退，但不得恢复未解释的严格词条。

### `DRAFT`

只组织 supplied content。区分 `FACT_PAYLOAD`、`EDITORIAL_REQUIREMENT` 和 `FACT_BOUNDARY`；编辑要求要由结构落实，不能原样混进成稿。认识论和适用范围限制也是 `FACT_BOUNDARY`，例如“不构成独立外部验证”“不是本问的直接观测目标”。

只有建立覆盖全部材料的 `unit_id + source_span + category` 台账后才报告分类数量；否则写 `classification_counts=OMITTED_UNUNITIZED`，不得输出 `FACT_PAYLOAD=n` 等伪精确计数。数字在材料中出现不等于授权自行比较；不得新增“更大/更高/低于另一情景/进一步侵蚀”等关系，窄门代码为 `DRAFT_DERIVED_COMPARISON_NOT_SUPPLIED`。

DRAFT 的机械 PASS 只证明已编码的表面载荷未越界，不证明自然语言蕴含、学术正确性或文风质量。

## 改写强度与输出

| 强度 | 允许 | 禁止 |
|---|---|---|
| `LIGHT` | 去路标、套话和局部句式问题；保留段序 | 合并段落、移动信息、删除内容 |
| `BALANCED` | 段内重组；声明式拆并相邻重复或职责过载段 | 未声明拆并、跨节重排、改变章节职责 |
| `STRUCTURAL` | 明确授权后按冻结结构事务重排 | 无 plan、跨标题/文件、改标题、静默删段 |

`CLEAN` 给无标注候选；`ANNOTATED` 逐处给决策；`PATCH` 给最小 diff 和未决项。没有可信外部 paired-quality clearance 时三者都是待审候选。

PATCH 必须满足 `patch_hunks_source_partition=NON_OVERLAPPING`：同一 source span 只能属于一个 patch hunk，`REWRITE hunk 不得包住另一个 UNRESOLVED span`。短 PATCH 的完整流程、span 限制、FOCUS、coverage、amend 和 live-source 语义只读 [short-patch-workflow.md](references/short-patch-workflow.md)；不得在主流程中凭记忆手写 bundle。

## 场景与声线

按“用户声明 > 文档用途/章节身份 > 段落功能 > 扩展名”路由：

| 场景 | 主要用途 | 文风目标 |
|---|---|---|
| `COURSE` | 概念、题解、复盘 | 难点决定解释峰值，第二解只写差异 |
| `MODELING` | 计算、方案比较、工程决策 | 取舍落到操作和结果后果；保留公开判断链 |
| `RESEARCH` | 研究问题、范围、讨论 | 保持主张状态，减少防御串和验收式结论 |
| `GENERAL` | 普通论文或证据不足 | 使用通用内核，不强套期刊腔 |

只有弱证据时回退 `GENERAL`；两个场景平局或低于 policy margin 时返回 `AMBIGUOUS/UNRESOLVED`。复杂路由运行 [route_humanize_scene.py](scripts/route_humanize_scene.py)，规则见 [scene-routing-policy.json](references/scene-routing-policy.json)。

`MODELING` 另读 [modeling-reasoning-preservation.md](references/modeling-reasoning-preservation.md)。改写前
标出 source 中实际存在的观测/约束、数学变化、方法选择和结果/限制；不强行补齐不存在的节点，
但不得把已有节点压成“直接采用某模型”。候选若删掉 source 中的节点或节点间的具体关系，使用
`audit_rewrite_contract.py --scene MODELING` 的 `MODELING_JUDGMENT_CHAIN_LOSS` 结果回到原事实、
数据或公式做局部修订，不能用第二个人文化工具覆盖。

用户提供可确认的本人样本时读取 [voice-profile.md](references/voice-profile.md)；没有样本只用版本化 `SCENE_DEFAULT`。定义、定理条件、标准条款和等权比较中的有意平行结构可 `NO_CHANGE`，不得为制造不对称而改坏。

## 词项定位与高风险快检

需要明确抓手时运行：

```powershell
python "$skillRoot\scripts\scan_humanize_chinese.py" <path> --scene AUTO --format text
```

词库见 [lexical-signals.json](references/lexical-signals.json)。其中两层不能混用：原有 `LEX-*` 信号仍按上下文、重复窗口和场景裁决；`LEX-STRICT-CORPUS-*` 来自本机 2843 个去重聊天会话快照、168039 条 assistant 正文和 26192 个 MD/TEX 文件的合并扫描。词根只负责发现；第二轮宽 CSV 保留 894778 个完整候选，发布层只收入 1417 个通过边界、覆盖和语义门的 2--12 字词或词组，默认 `high/REWRITE`。相对最初 1400 条表，本版保留 226 条、新发现 1191 条并淘汰 1174 条旧项，不靠机械追加凑数。单个 strict 命中就必须记录，不能因频次只有一次而跳过。

单字只用于发现，不是禁用项。当前台账对 1770 个单字根排序，其中 1167 个进入宽召回发现层；完整父词、CSV 内嵌子串和 1--3 字倒排根合并后审计 17670 个根，4753 个进入完整家族扫描。最终去向为：683 个根至少发布一个完整搭配，4064 个在精确复计后明确拒绝，6 个截断或噪声根在复计前明确拒绝；未路由根为 0。最终库存只允许 2--12 个连续汉字的词或完整搭配。例如发现根 `稳` 会追出 `更稳/会更稳/这样更稳/更稳一点/更稳的说法/更稳的写法/更稳的做法`；动作根 `收紧` 会追出 `继续收紧/再收紧/口径收紧/同步收紧/进一步收紧/再收紧一点`。不得据此禁用单字 `稳` 或技术词中的同形字符；`收紧` 作为可独立定位的双字动作词，则由本轮证据决定是否发布。

发现器不得只看大短语总榜，也不得使用 Top-K 截断来宣布完成。它必须同时执行大词组内嵌 1--3 字根拆解、根的左右 2--8 字搭配扩展、聊天与 MD/TEX 的精确复计、句首/句尾完整壳检查和技术内容保护。闭环只在连续两轮的最终短语集、全部候选集和发现根集都零增零减且哈希一致时成立；仅“最终词表零新增”不构成收敛。

严格词库按 12 个意群执行：过程播报、完成闭环、审计治理、范围边界、否定纠偏、过渡路标、重点提示、学术包装、论文自证、建议展望、确定性限定、助手邀请。命中后的合法结果只有：

- `DELETE`：删掉不承载信息的词壳；
- `REWRITE`：让对象、动作、条件、差异或结果直接承担表达；
- `KEEP`：保护区自动保留，正文专业术语需绑定位置并说明不可替代的技术功能；
- `UNRESOLVED`：无法安全修改时显式交回人工处理。

严格层没有泛化的 `NO_CHANGE`。同义替换、减少一个修饰词、把短语拆开但保留原抽象关系，均不算处理完成。

交付前逐字复核以下常见 AI 风味抓手：

- 空重点壳：`值得注意的是/需要指出的是/必须强调的是`；
- 教练腔：`必须牢记/务必记住/千万不要/秒杀/救命表/锁死答案`；
- 营销拔高：`全面提升/深刻揭示/填补空白/全新范式/提供有力支撑`；
- 泛化意义：`具有重要意义/意义深远/意义重大/前景广阔`；
- 学术包装成束：`系统梳理/深入探讨/综合运用/充分说明` 与抽象评价连用；
- 管理闭环：`形成/构建/实现……闭环`、`收口/核心抓手/锁定故事线`；
- 对举纠偏壳：`不是……而是……`、`重点不在于……而在于……`；定义性排他或约束表达需绑定位置级 KEEP，其余改为直接陈述对象、条件和处理；
- 编辑后台和自证开头：`本节需要/正文应/适用题目/逻辑链条/给定首句`，以及“优点不在于……而在于……”；
- 强制桥接和自动展望：`为后续研究提供支撑/奠定基础`、`未来可进一步……`；
- 多重缓和：同一命题叠加 `可能/或许/一定程度/某种意义`；
- 无来源归因：`专家认为/研究表明/一些学者指出/已有研究/相关文献`。

上面的人工短表用于说明病灶，不是完整词表。原有普通信号不是无条件禁词；但 1417 条 strict inventory 是默认禁词。术语、真实教学约束和用户锁定原句可 KEEP，但理由必须绑定具体位置、表达功能和不可替代性。high 信号若无具体 KEEP 理由，不得进入 CLEAN；输入不足以具体化时降级为 PATCH/UNRESOLVED，不能只换同义套话。复杂病灶按 `rg -n "^## HUM-XX" references/pathology-catalog.md` 定点读取，不全量加载病灶库。

## 交付层

普通用户只看“正文/候选 + 最多三行范围、未决项和下一步”。不要把 policy hash、内部枚举、ledger 路径和退出码塞进自然语言摘要。“只输出正文”时省略摘要，但后台验证不省略，可见正文仍只能来自已验证 emit。

必须区分三件事：机械验证是否通过、成对文风质量是否有可信外部 clearance、学术正确性是否评估。后两者默认分别为 `PENDING_EXTERNAL_REVIEW` 和 `NOT_EVALUATED`。

## 引用路由

| 任务 | 只读取或运行 |
|---|---|
| 普通短文 | 本文件主路径 + `quick-checklist.md` + 匹配场景窄段 |
| 诊断/Gate | `style-gates.md`；复杂病灶定点读 `pathology-catalog.md` |
| 场景改写 | `workflow.md` + `course-notes.md`、`modeling-engineering.md`、`modeling-reasoning-preservation.md` 或 `research-journal.md` 中唯一匹配文件 |
| 改写范例 | 只读 `rewrite-patterns.md` 的匹配场景 |
| 短文 PATCH | `short-patch-workflow.md` + scaffold/build/apply/verify 脚本 |
| 作者样本 | `voice-profile.md` |
| 检测报告/标红片段 | `detector-report-intake.md` + `extract_detector_report_scope.py` |
| 长 MD/TEX/TXT | `long-document-workflow.md` + prepare/scaffold/finalize |
| STRUCTURAL | `structural-rewrite-contract.md` |
| 来源分类 | `source-provenance-trust.json` |
| 可复用 Prompt | `system-prompt-contract.md` |

不要为小段落加载全部场景、全部范例或完整 Gate。reference 超过百行时先看其目录，只读取与当前分支直接相关的小节。

## 文件与证据

文件后缀不能表达真实格式时，显式传 `--document-format tex|markdown`。乱码先以 UTF-8 重试一次，仍不可读才跳过并记录 `SKIPPED_GARBLED`，不要拖住其他可读范围。

直接验证、evidence、replay、capture、模板字段授权和外部审批链全部以 [operational-contract.md](references/operational-contract.md) 为唯一权威。正常环境不得手写 PASS 或绕过统一验证器；证据包 PASS 只表示已声明范围内的完整性或 self-consistency，不证明历史真实性、作者身份、文风收益或学术正确性。

## 来源信任边界

按 [source-provenance-trust.json](references/source-provenance-trust.json) 裁决来源角色。当前没有代理不可伪造的外部来源证明链，因此 `HUMAN_CONFIRMED/UNKNOWN` 最高为 `PROVISIONAL`；`MODEL_GENERATED/MODEL_ORIGIN_UNRESOLVED` 固定为 `NEGATIVE_ONLY`。本地标签、路径、SHA 或调用方声明不能升级信任。

普通生成、改写和长文处理不依赖正向来源卡；运行时只可加载去台账化负例 detector。来源边界不证明模型心理上从未受其他材料影响，只限制本工具可声称、可选取和可入队的证据角色。

## 长文边界

超过一个可连续阅读章节、含复杂 TeX 环境或需要修改源文件时，必须读取 [long-document-workflow.md](references/long-document-workflow.md)。没有全量结构清单、覆盖账本和保护检查时，只能声称抽样诊断。

```powershell
python "$skillRoot\scripts\prepare_humanize_long_document.py" <main.tex|doc.md> --output <empty-run-dir> --scene <SCENE>
python "$skillRoot\scripts\finalize_humanize_long_document.py" --run-dir <run-dir> --rewrites <rewrites-dir> --format text
```

只编辑 chunks 中的 PENDING unit，不改 `[[PROTECTED:...]]`；使用 scaffold 生成 strict bundle，不手写或覆盖源文件。scaffold 返回 `PENDING_TEMPLATE_COMPLETION` 后不得直接 finalize：先读取 stdout 的 `rewrite_intent_authoring_contract`，按其中的 exact fields、保留行尾 hash 算法、coverage 合同和合法示例逐 unit 替换 TODO；单个连续 span 优先用 `build_humanize_rewrite_intent.py` 从冻结 unit 生成 hash-bound intent，不手算 hash。`REWRITE` 补齐 summary、operations、source_spans 和 target_signals，`NO_CHANGE` 补具体理由和 hash-bound evidence span。遗漏或字段错误时，优先按 finalizer 的细粒度 `REWRITE_INTENT_*` 与 `actionable_next_actions` 修复，不凭 notes 猜 schema。`LIGHT/BALANCED` 不越过冻结 unit；`STRUCTURAL` 必须有明确授权和事务合同。finalizer 必须重建状态、逐 unit 验证，并在全文上重验 TeX、Voice 和跨 unit 模板。

完成声明只读取顶层 `delivery_gate_status` 和 `humanize_completion_claim_allowed`。`PENDING`、`UNRESOLVED`、`SKIPPED_GARBLED`、`CHANGED_AFTER_SNAPSHOT`、任一 REVIEW/FAIL、编译失败或质量待审都阻断全文完成；`rendered_partial` 和 `rendered_review` 不是正式交付。


## 可执行 Voice Profile

用户确认本人样本时，按 [voice-profile.md](references/voice-profile.md) 建立并验证 Profile。代码、公式、引语、题干、OCR、模板、未知归属和模型生成文本不得成为作者声线证据；乱码记录后跳过。只有 rebuild-evidence 返回生产准入 PASS 的 Profile 才能进入长文 prepare。没有样本时使用 `SCENE_DEFAULT`，并披露“不声称复现个人文风”。

## 完成条件

- `DIAGNOSE`：问题可定位、排序和行动化，正文未被改写。
- `REWRITE`：所有未保护 strict finding 已删除、改写或获得位置级 KEEP；目标病灶下降，作者声线与保护项未漂移，硬不变量通过；质量完成还需要与当前全部变化绑定的可信外部 paired-quality clearance。
- `DRAFT`：只使用供应内容，符合场景和 Voice Profile，没有伪造信息，成稿中没有未解释 strict finding。
- 所有模式：没有制造不对称，没有把旧套话换成新模板，没有输出学术质控结论，也没有用 `NO_CHANGE` 掩盖严格词条。

条件不足时报告 `UNRESOLVED`，不得用“已闭环、已完全人类化”代替具体结果。
