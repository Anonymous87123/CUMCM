# 纯文风验证门

## 目录

1. 状态与优先级
2. DIAGNOSE 门
3. REWRITE/DRAFT 共同门
4. 场景差异门
5. 长文门
6. 交付声明

验证门只判断文风执行与保护状态，不判断作者身份、AIGC 概率或学术正确性。

## 1. 状态与优先级

每道机器门只返回 `PASS/FAIL/REVIEW/NOT_RUN/NOT_APPLICABLE`。文本位置的动作另使用
`KEEP/DELETE/REWRITE/REVIEW/NO_CHANGE/UNRESOLVED`，不得把动作值当机器门状态。

`NO_CHANGE` 表示可编辑范围内没有值得保留的安全改动：可以是无可定位病灶、改动无稳定收益，
也可以是高优先级约束阻止改动。它不是“原文自然”或质量 clearance。

不计算综合“人类度”。一个 `NO_CHANGE` 不代表失败；保护语义比减少模板信号优先。

## 2. DIAGNOSE 门

### DG-01 模式一致

正文未被修改；输出没有“已改写、已调整”声明。

### DG-02 覆盖透明

明确区分全文、全量结构扫描、抽样连续阅读和局部段落。没有覆盖账本时不得声称全文完成。

### DG-03 问题排序

使用 `Dominant/Recurring/Local`；它只表示跨单元覆盖，不等于 scanner 的
`high/medium/low`。单一位置默认只能是 `Local`。默认只列 3-8 个最高价值病灶类型，
但每类须在 `Location/Trigger` 中给作者正文 occurrence 数和位置；一个位置只有一个主病灶。

### DG-04 候选不等于判定

词项命中附带上下文、窗口计数、保护状态和动作。单个高频词不被宣告为 AI 痕迹。

### DG-05 输出合同

严格使用 [operational-contract.md](operational-contract.md) 第 5.1 节的唯一 `DIAGNOSE`
schema。诊断扫描固定包含 protected/excluded 审计视图，覆盖摘要披露扫描、保护与排除
计数；保护命中不进入作者病灶数。用户指定其他展示格式时，语义字段仍须齐全。

## 3. REWRITE/DRAFT 共同门

### STYLE-01 配置

记录 `mode/scene/intensity/output/voice`。无作者样本时声明 `SCENE_DEFAULT`。

### STYLE-02 保护区

引语、题干、法规、OCR、代码、数学、TeX 命令和用户锁定区域未被改写。若用户明确授权例外，记录范围。

### STYLE-03 语义与言语行为

数字、单位、专名、术语、否定、模态、条件、完成状态和结论方向未漂移。特别比较：

```text
称为/定义为 != 是
结果表明/观察到 != 客观无来源断言
专家认为/文献指出 != 本文证实/本文证明
可能/仅/未/不/若/当/除非 != 可删除语气词
```

硬不变量使用脚本检查；警告必须 `REVIEW/UNRESOLVED`。归因主体与来源标记归入 `attribution_source`：不得删除模糊归因后把命题升级为本文结论，也不得为消除候选虚构作者、年份或引文。来源是否真实仍属于独立学术正确性门禁。

逐分句执行谓词来源门：只接受 `COPY`、`ENTAILED_PARAPHRASE` 和 `DELETE_STYLE_SHELL`。编辑要求不得变成已完成工件，抽象支撑不得变成实际工程使用，多重缓和不得生成新的程度判断。确定性检查只覆盖已登记的高风险转换，不等于完整语义蕴含证明；未命中脚本仍需人工连续阅读。

编辑要求的位置范围也属于谓词状态。`正文里既要保留…… -> 既要保留……` 不是单纯删后台词：它删除了“结果应出现在哪里”的约束，却保留其余祈使结构。命中 `SPEECH_ACT_EDITORIAL_SCOPE_DROPPED` 时恢复或明确迁移 `正文里/正文中/文中` 的范围；完整删除编辑要求或把范围移到同句其他位置时，不按该窄门机械拦截，但仍须连续阅读。

将真实负例中的谓词升级单独复扫：未生成工件不得写成验证失败；用途不得写成结果；待检不得写成已完成；内部投影不得写成外部验证；候选区间或不稳健排序不得写成经验证阈值或稳定结论。保留来源谓词、对象、完成状态与证据角色；finding 固定 `semantic_judgment=NOT_EVALUATED`。

### STYLE-03A 模板字段

四类 live field 统一登记 `source_role=TEMPLATE_FIELD`，另以 `artifact_role=before|after` 区分工件一侧。
payload role 必须按 label 精确映射：

- `适用题目`：`EDITORIAL_PAYLOAD/APPLICABILITY_CLASSIFICATION`；
- `逻辑链条`：`EDITORIAL_PAYLOAD/TEACHING_REASONING`；
- `给定首句`：`READER_FACING_ARTIFACT_ROLE/PROMPT_STEM`；
- `用词建议`：`EDITORIAL_PAYLOAD/LEXICAL_GUIDANCE`。

尤其不能把读者可见的 `给定首句` 当成后台编辑载荷。Markdown fenced/inline code、TeX verbatim 与
TeX 注释中的同形行必须排除，防止示例误报。

缩进、label、全角/ASCII 冒号、位置和顺序组成 header；任何 header 修改、增删或移动均为
`TEMPLATE_FIELD_HEADER_CHANGED`、硬 `FAIL/1`。payload 默认不可编辑；没有精确
`humanize-template-field-edit-scope/v1` 的变化为
`TEMPLATE_FIELD_PAYLOAD_EDIT_UNAUTHORIZED`、机械 `REVIEW/2`。scope 必须绑定改前 SHA、唯一
`line + label`，permission 固定 `PAYLOAD_ONLY`。

已授权 payload 只有在职责、适用范围、逻辑关系、否定和断言力度均未漂移时才可能机械 PASS；否则为
`TEMPLATE_FIELD_ROLE_OR_FORCE_DRIFT`、`REVIEW/2`。至少回归
`ASSERTION_FORCE_WEAKENED/STRENGTHENED`、`NEGATION_SCOPE_CHANGED`、
`CAUSAL_OR_CONDITION_RELATION_CHANGED`、`APPLICABILITY_OBJECT_CHANGED`、
`APPLICABILITY_PREDICATE_CHANGED`、`APPLICABILITY_RANGE_CHANGED` 与
`CLASSIFICATION_TO_READER_INSTRUCTION_DRIFT`。`PAYLOAD_ONLY` 固定
`local_clearance_supported=false`；授权与机械 PASS 都不提供 paired-quality clearance。

### STYLE-04 权限

`LIGHT` 不改段序；`BALANCED` 不跨节重排；`STRUCTURAL` 有明确授权并交付 patch。长文默认提交
同一 unit 的来源段 plan；只有显式 `ADJACENT_PAIR` 才能提交精确绑定 prepare `STX-*` 的双 fragment
`humanize-structural-transaction-bundle/v3`，且只允许同一文件/heading 的物理相邻 pair。每个 fragment
必须给 `local_rewrite_intent` 与 `template_field_edit_scope`；scope 通常为 null，非 null 只允许 local
REWRITE，并按该 fragment 的派生结构基线 line/label 物化，不能跨 member 授权。v1/v2 只读兼容；
v2 local intent 可保留审计，但缺 v3 scope 边界，不能形成当前 bundle-contract PASS。两侧来源 ref、
保护归属、FRAGMENT 和 DOCUMENT gate 必须原子闭合；任何 member scope/intent/validator 或后置 repetition
失败时共同回滚。plan/transaction
机械 PASS 不替代结构语义复核。实际结构变化必须生成 hash-bound review request，顶层保持
`REVIEW/2`，候选只进 `rendered_review/`。用户结构锁优先。

### STYLE-05 真实主次

只放大原文或 Voice Profile 可确认的重点。定义组、定理条件、标准条款和等权比较保持平行，不为了“人味”制造中心项。

### STYLE-06 词项上下文

管理、营销、教练和抽象词只有在承担错位声线时才处理。术语与对象用法如“闭环控制、约束方程、边界条件、显示屏、决策框架”默认 `KEEP/REVIEW`。

理论段首、案例点题尾、被动分析壳、核心问题壳、系词回避和学术包装词只按跨句复用、信息功能与 Voice Profile 裁决。单次正常使用不能仅因表面命中被改写；扫描器的 exclusion、正反例和阈值必须随词库一起复核。

### STYLE-07 功能性连接

证明链、算法不变量和规范步骤中的真实因果与平行可保留。只处理无功能或密集重复的“因此、本文、结果表明、首先”等。

### STYLE-08 结构与节奏

消除实际存在的批量段落槽位、匀速解释和多重出口。不得用随机长短、强制一段一重点或新固定句壳替代。

三项枚举只有在实际不等权且由凑数产生时调整；算法、证明、标准步骤和等权分类保持平行。破折号与加粗不设绝对数量上限：单次正常使用、标题、字段标签和表头保持不动，只有集中复用确实替代语义停顿或信息主次时才处理。

短句不是默认修复手段。不得把一个带模态和条件的命题平均切成多个短句，也不得为了“克制”让连续句都采用“对象 + 判断”的同一节拍。作者动作必须在当前交付范围内有正文兑现；没有兑现的“本文梳理/讨论/探讨”按元话语处理。

### STYLE-09 修复模板

检查改后段首与段尾。“这里真正、这里只看、只需、其余沿用、不再展开、直接即可”等修复语不得在相邻段批量复用。

### STYLE-10 作者声线

有 Voice Profile 时保留其高置信习惯；无 Profile 时只做场景保守改写，不宣称个人拟声。

### STYLE-11 输出合同

`CLEAN/ANNOTATED/PATCH` 与用户要求一致。内部 Gate、语义清单和重心图不泄漏到“只输出正文”。

文件改写的 `机械验证=PASS` 必须能回查到 `validate_humanize_output.py` 的
`mechanical_validation_status=PASS` 和对应前后 SHA-256。顶层退出码 2 仍是 `REVIEW`；不得因
机械层 PASS 改写成顶层 PASS。没有运行记录时是 `NOT_RUN`。

### STYLE-12 无越界

没有内容正确性、证据、来源、实验、复现、创新真实性或检测率判断。

### STYLE-13 成对质量

每次 `REWRITE`（含 `NO_CHANGE`）都有与当前 artifact 和 policy 绑定的
`humanize-paired-quality-review-request/v1`。变化稿逐 hunk 登记 before/after 行区间和 hash；
无变化稿明确登记 `changes=[]`，不得把“没有改动”解释成“没有病灶”。

机械门只回答已编码约束，不能回答搭配是否自然、每处变化是否有独立收益、段落职责和逻辑层级
是否保留、是否出现新的主语错位/硬被动/机械短句/路径壳。模型自检、调用方身份标签、普通盲评
和 fresh second pass 只有否决或建议权，没有放行权。没有可信外部复核链时，本门固定为
`PENDING_EXTERNAL_REVIEW`，顶层固定 `REVIEW/2`，`humanize_quality_claim_allowed=false`。

已观察到的 COURSE 声线压平另设确定性 advisory。它先在字符级 change region 中绑定“功能性轻口语确实删除/抽象正式形式确实新增”，而不是把同一行的两个无关词硬配成替换；引语、数学、代码、TeX 注释、正式环境、完整 TeX 命令调用和与原稿 high-severity `DELETE/REWRITE` finding 交叠的 source anchor 均排除。只有同一标题、双侧各不超过 1200 字符与 24 行的窗口达到 `4 个不同转换 + 3 个功能 family + 3 个变化 hunk` 才命中；同一规则的多个 occurrence 分别保留，BOM 计入原始 artifact 的 UTF-8 byte offset。

命中 `STYLE_COURSE_VOICE_FLATTENING_CLUSTER` 时，style、paired-style-delta 与机械层均为 `REVIEW`，顶层为 `REVIEW/2`，paired-quality request 为 `BLOCKED_BY_MECHANICAL_GATE`；本地 KEEP 不得放行。报告使用中性 provenance/scope，不暴露盲测工件身份。该门不把 `足以/纳入/改写为` 等常见词单独列为禁词，不在 DRAFT/RESEARCH/NO_CHANGE 或反向转换上运行，也不推断作者身份。未命中不等于原稿自然、候选更好或成对质量 clearance。

## 4. 场景差异门

同一份中性文本不能仅换场景标签而得到完全相同的解释策略。只有当前场景可观察条件成立时才应用差异门。

### COURSE-GATE

- 学习难点决定解释峰值；不是所有公式都统一压缩。
- 第二解只从分叉点写差异。
- 同一知识避免多个完整复习出口。
- 不引入科研防御或工程决策声线。
- 保护承担范围判断、注意力定位、纠偏强调、对象关系或贯穿隐喻的轻口语；没有可定位病灶时 `NO_CHANGE`，不得整段提高注册语域。
- 成对检查不得把 `补成/记账/接得上` 等具体关系成簇轮换为 `改写为/纳入/对应` 等通用正式表达；单处精确化须单独证明收益。

### MODELING-GATE

- 关键取舍只连接到输入已明确给出的模型操作、情景比较或方案后果。
- 方案后果不是必填项；输入只有数值变化、比较方向或成本取舍时就在该层停止，不补写“用于工程决策”。
- 只有输入明确报告实际采用、选择、部署或使用，结果段才回答“变化对选择意味着什么”。
- 不把建模稿仅改成通用对象先行，也不套期刊贡献声线。

### RESEARCH-GATE

- 保留命名、观察、报告和主张范围。
- 同一误读只集中纠偏一次，减少审稿回复式防御。
- 图表先给研究观察；结论不按问题编号验收。
- 不加入课堂提示或工程命令。

### GENERAL-GATE

- 原体裁与 Voice Profile 优先。
- 只处理高置信通用病灶。
- 不强制符合 COURSE/MODELING/RESEARCH 的专属节奏。
- 改写前登记具体病灶跨度；无病灶即 `NO_CHANGE`，`BALANCED` 不是改动配额。
- 每个改句必须有独立收益；“更正式/更书面”及无功能近义轮换不算收益。
- 不把自然主动句改成 `使/让 + 抽象对象 + 被 + 动词` 的硬被动；合法技术被动按上下文保留。
- 成对复核先逐句回退劣化，再判断整段是否仍稳定优于原文。

三类专属场景最高分为 0 或 1、且来源角色和权限明确时固定使用 `GENERAL`。只有来源
角色不明、用户指定场景与明确用途冲突或保护/权限无法裁决时返回 `UNRESOLVED`；不得
用一个通用输出冒充已解决的场景冲突。

## 5. 长文门

长文必须分别报告：

- 结构清单覆盖率；
- 实际处理块与未处理块；
- 输入 hash、规则版本和路由；
- 保护检查与 TeX 格式检查；
- 逐 section patch 与可回滚状态；
- 相同版本 dry-run 是否产生新 diff。
- `prepare_humanize_long_document.py` 生成的快照、manifest、保护占位和初始覆盖账本；
- `finalize_humanize_long_document.py` 生成的最终账本、逐单元验证、diff、回滚清单和发布目录。
- 每个可编辑 `REWRITE/NO_CHANGE` unit 的 paired-quality request 覆盖；任一 request 缺失时
  `paired_quality_review_request_coverage_status=REVIEW`、`paired_quality_gate_status=BLOCKED`，
  机械完整候选也不得进入正式 `rendered/`。request 齐全时 quality gate 为
  `PENDING_EXTERNAL_REVIEW`；无可编辑 unit 时为 `NOT_APPLICABLE`。
- run-dir 事务覆盖 rendered、validation、diff、ledger 与 metadata；任一提交异常或检查命令污染
  都恢复旧 canonical 状态。失败尝试的 request path 不得指向恢复后的旧证据；检查命令的后台
  后代必须在发布前清理完毕。

任何一项未执行都标 `NOT_RUN`。抽样诊断不能通过全文完成门；`rendered_partial` 不能
作为全文交付。任何 `UNRESOLVED`、`SKIPPED_GARBLED` 或 `CHANGED_AFTER_SNAPSHOT` 都使
`coverage_completion_claim_allowed=false`。Voice 绑定、全文声线/跨块重复门或 fresh
second pass 尚未执行时，`humanize_completion_claim_allowed=false`，兼容字段
`full_completion_claim_allowed` 也必须为 false。

## 6. 交付声明

### Diagnose

```text
已完成纯文风诊断；未修改正文。覆盖=<...>，未覆盖=<...>。
```

### Rewrite

```text
已生成授权范围内的纯文风待审候选；scene=<...>, intensity=<...>, voice=<...>。
机械验证=<PASS/FAIL/REVIEW/NOT_RUN>；paired-quality=<PENDING_EXTERNAL_REVIEW/NOT_RUN>；
未运行学术质控。
```

### Draft

```text
已根据用户提供内容起草；scene=<...>, voice=<...>。
semantic_source_check=<PASS_COPY_ONLY/NOT_EVALUATED>；仅在 PASS_COPY_ONLY 时声明逐字来源已确定。
```

用户要求只输出正文时不添加声明。
