# MD/TEX 学术文风人工精读台账

本台账记录进入核心结论前实际阅读过的完整文档及其文体判断。清单扫描与段落索引只负责找材料；下列结论来自人工阅读文档结构、正文与上下文。

来源等级沿用《精细化语言风格分析执行计划书》：A1 为用户明确声明 GPT 生成，A2 为 assistant 写入证据闭环，B 为高可信项目产出，C 为仅有路径/项目关联，D 为第三方或模板对照。B/C 材料不能单独证明 GPT 的普遍人格。

## 1. 已精读 Markdown 文档清单

| 编号 | 文档/家族 | 来源级别 | 文体任务 | 阅读后的核心判断 |
|---|---|---:|---|---|
| MD-01 | `D:\LSGO-platform\report.md` | B | 项目交接与总审计 | 用“职责-完成度-风险-交接-自检”替代普通项目简介；同一风险存在多轮复述。 |
| MD-02 | `D:\LSGO-platform\docs\metric_screening_notes.md` | B | 指标筛选与角色分工 | 每个指标先问决策职责，再决定保留/下沉/排除；善于防止数字误读。 |
| MD-03 | `D:\LSGO-platform\docs\meta\ARCHITECTURE_REVIEW.md` | C | 双语架构审查 | 专业感主要来自审查模板、评级和优先级；泛化句若无代码证据会显空。 |
| MD-04 | `paragraph_level_rewrite_plan_sccd_2026-05-19.md` | B | 论文段落级施工图 | 以旧叙事排除、新主线锁定、章节责任和回滑禁令控制全文。 |
| MD-05 | `rewrite_blueprint_intro_prelim_method_sccd.md` | B | 引言/预备/方法蓝图 | 将章节当作生产工位，精确规定每段承担的解释任务。 |
| MD-06 | `paper_results_conclusions.md` | B | 结果边界说明书 | 用“已证明/未证明”与证据等级限制外推，严谨但容易自辩过密。 |
| MD-07 | `conditioning_aware_grouping.md` | B | 方法动机与缺口 | 先承认既有证据能解释什么，再推出仍未解决的决策缺口。 |
| MD-08 | `conditioning_aware_grouping_algorithm.md` | B | 算法定义草案 | 将概念缺口转为输入、输出、目标、代价、伪代码和退化边界。 |
| MD-09 | `sccd_experiment_master_plan_2026-05-21.md` | B | 实验总控与门禁 | 先定义 claim 和证据职责，再列实验命令；计划精密但标签密度高。 |
| MD-10 | `imitation/imitation_report.md` | B | 论文模仿映射 | “旧叙事-禁止项-主 claim-章节责任-转场句”的反向约束式写作。 |
| MD-11 | `imitation/requirement.md` | D/B | 外来核对卡与项目清单混合物 | 有读者路径意识，但翻译式长并列与全称命令明显，不能直接当 GPT 原创证据。 |
| MD-12~16 | Probet 五篇文献精读笔记 | B | 文献到项目决策的翻译器 | 五篇共用固定背景和五段骨架，应计作一个模板族，不是五种独立风格。 |
| MD-17 | `listening_blind_guess_strategy.md` | B | 证据型应试策略 | 每条启发式绑定分子/分母、反例和适用域，形成“规则强度校准”。 |
| MD-18 | `section_b_final_conclusions_report.md` | B | 分节策略报告 | 以总判断、规则拆分、反例和执行清单组织海量题目证据。 |
| MD-19 | `readme_demo_test.md` | B | 工程运行手册 | 同时给运行路线和误用边界；明确哪些失败不应先归咎于入口脚本。 |
| MD-20 | `D:\Probet\fingerprint-readme.md` | B | 方法/benchmark 边界手册 | 反复拆开“方法本体”和“后处理”，防止把 official accuracy 外推为 OOD 能力。 |
| MD-21 | `solution_quality_ledger.md` | B | 审计台账 | 语言单位是状态、行号、证据片段和风险标签，不是连续散文。 |
| MD-22 | `cpp_class_object_traps.md` | B | 教材-反陷阱讲义 | 同一规则在解释、题型、解析、速记中多次编码，检索强但冗余高。 |
| MD-23 | `圆锥曲线\例题人类化撰写计划.md` | B | 数学改写质控计划 | 把“自然”转译为可验收条件：字母用途、条件说明、推导因果和禁用跳步词。 |
| MD-24 | `简单导数\例题人类化撰写计划.md` | B | 教学改写计划 | 使用有限状态集追踪拆解、重写与复核，呈现语言质量管理化。 |
| MD-25 | `对话系统技术文档.md` | C | 产品技术文档 | 模块、接口、性能、测试、维护全覆盖；覆盖优先导致功能重复。 |
| MD-26 | `应用介绍.md` | C | 参赛/产品展示稿 | “问题三联-方案三联-架构-MVP-愿景”的创业竞赛模板明显。 |
| MD-27 | `Student_Score_Management_System/README.md` | C | 多轮开发与验收合并稿 | 章节来自不同维护轮次，不能整体当成一次独立成文。 |
| MD-28 | `aigc-down-skill/SKILL.md` | D | 历史退休材料 | 已逐项蒸馏并删除，现不可调用；只保留审计来源意义，检测操纵、固定配额、噪声预算、虚构经历/引用等危险规则未迁移。 |
| MD-29 | `openclaw-persona-forge/SKILL.md` | D | 人格提示模板 | 刻意要求角色化隐喻与态度，不属于学术输出基线。 |
| MD-30 | `2024年数学高考前瞻.md` | C | 短预测评论 | 体量和任务与技术文档差异太大，只进其他/未溯源档。 |

## 2. 阅读卡：项目交接与可审计治理体

代表文档：MD-01、MD-02。

### 文档任务与结构

`report.md` 开篇主动纠正读者预期：“这份报告不是单纯的‘项目简介’，而是一个夏同工作线的完整交接文档。”此后不是按技术主题平铺，而是按接手者的决策顺序展开：文档职责、角色边界、已完成/未完成、旧判断复核、项目全貌、风险、交接顺序、最终自检。

它最有辨识度的判断是把“平台骨架存在”与“论文可交付、实验稳定、结果沉淀”分开：

> “项目当前并不缺‘代码目录’，缺的是‘最后收口’。”
>
> “把‘代码写了’误判成‘实验收官’。”
>
> “平台骨架成型，但实验收官未完成。”

### 风格价值

这类写法能阻止接手者被单一完成度误导。`metric_screening_notes.md` 也不把字段丰富等同信息有用，而是追问指标角色：

> “有些量虽然很重要，但它们的职责是‘检查记录是否可信’，不是‘说明算法性能有多强’。”

### AI 痕迹

同一风险常被“总体结论-复核-再复核-最终强化判断”多次改写。标题层级过深时，目录在替正文完成论证。去 AI 时不应删除边界判断，而应合并同证据、同结论的重复章节。

### 可执行规则

- `SHOULD`：一个风险只保留“判断、证据、影响、动作”四个位置，其他同义复述合并。
- `MUST`：完成度必须拆成可验证维度，不给无定义的百分比。
- `SHOULD`：标题写问题，正文给新证据；标题和正文不得重复同一句判断。

## 3. 阅读卡：论文重写施工图与叙事控制体

代表文档：MD-04、MD-05、MD-10。

### 主论证链

这类文档不直接论证科研命题，而是控制论文怎样论证。稳定结构是：旧叙事失效、新中心问题、章节职责、段落职责、禁止回滑、自检句。

> “论文目标必须是‘提出并验证一种分组方法’，不是‘发现一个现象’。”
>
> “方法论必须先把算法讲出来，再讲验证。”
>
> “每一段都要问自己：它是在帮助读者理解我们的方法，还是只是在堆现象和证据？”

`imitation_report.md` 更直接规定：“这份报告的职责不是重复旧报告里‘每篇论文写得怎么样’的读书笔记，而是把模仿对象压缩成可执行的写作动作。”这说明“不是 A，而是 B”在这里不是偶然句式，而是文档的决策压缩器。

### AI 痕迹

`唯一主线、绝对不要、必须死守、锁定、收束、回滑`等控制词把编辑判断写成项目门禁。它适合内部施工图，但若直接进入论文正文，会让论证显得由管理语言推动，而非由问题和证据推动。

### 可执行规则

- `MUST`：方法名称首次出现前，必须有具体未解决问题；不能用“为解决上述问题”空转。
- `SHOULD`：内部写作计划可用禁止项，论文正文改写为正向的因果链。
- `SHOULD`：删除“唯一、绝对、必须”等元控制词，除非它们描述数学条件或实验约束。

## 4. 阅读卡：证据等级、边界声明与方法自辩体

代表文档：MD-06~09。

### 文档任务与结构

`paper_results_conclusions.md` 自称“给论文写作使用的结果边界说明书”。其结构是：一句话主张、强/中/边界证据、已证明、未证明、审稿质疑、可用结论、应避免写法、下一块证据。

> “这仍然不是一个‘所有 CEC 函数、所有优化器、所有指标都服从同一规律’的万能定理。”
>
> “论文必须采用‘函数族分层 + 指标分层’的叙事，而不是一刀切。”

`conditioning_aware_grouping_algorithm.md` 把问题转成显式任务：“给定一个黑盒目标函数、变量维度和目标组大小上限，如何构造一个分组……”这种写法的优点是把抽象动机压到可验证输入和输出。

### AI 痕迹

严谨感可能被“已经证明/没有证明”“可以说/不能说”模板化。若每一节都预演审稿人反驳，论文会由防守而非发现推进。边界写得好不代表边界已经被实验或理论证实。

### 可执行规则

- `MUST`：每个边界声明绑定样本、预算、后端、指标或假设中的至少一项。
- `MUST`：不能用“更谨慎地说”替代数值、对照或置信区间。
- `SHOULD`：一节最多集中陈述一次主要边界，局部限定放在相应结果句旁。

## 5. 阅读卡：实验总控与证据门禁体

代表文档：MD-09。

文档开篇写“一次性把主结果、机制证据、边界证据、附录储备和图表路线全部规划清楚”，并以 `claim -> evidence -> matrix -> stopping rule -> artifact` 组织实验。其有价值的判断是：

> “过去的返工，主要不是因为代码写不出来，而是因为实验设计总在事后才发现缺口。”
>
> “主表必须来自独立预算；shared-budget 只能是边界说明。”

这比普通“先跑 A 再跑 B”更接近科研设计：实验先回答主张，命令只是实现。AI 痕迹在于每个对象都被赋予标签和职责，计划可能过细，读者在 `LOCK/APPX/RESERVE` 等元数据中失去对科研问题的注意。

可执行规则：先写研究问题和判定标准，再列命令；每个实验必须说明“若结果相反，将改变哪个结论”；标签只保留在项目计划，不进入论文结果叙述。

## 6. 阅读卡：文献精读到项目决策的翻译器模板

代表文档：MD-12~16，五篇 Probet 文献笔记。

五篇共享骨架：论文讲什么、当前项目背景、PDF 主线、原文精读、最后判断如何使用。开头说明几乎一致：

> “先讲论文主线，再引用 PDF 原文做精读，最后说明它能怎样支撑我们的数学探针，以及哪些地方不能照搬。”

共享句还包括：

> “它不是被拿来‘装饰引用’的背景文献，而是用来解释我们数学探针或结构路由中的一个具体环节。”

优点是每篇文献都被迫回答“能用什么、不能搬什么”；缺点是异质论文被压入同一项目叙事，独特理论贡献被固定背景稀释。五篇应视为一个模板族，不能把共有句按五份独立证据计数。

可执行规则：每篇文献摘要至少保留一个只属于该文献的数学对象、假设或反例；公共项目背景只在系列首页出现一次；引用用途必须落到具体命题，不写“提供重要支撑”。

## 7. 阅读卡：证据型应试策略体

代表文档：MD-17、MD-18。

`listening_blind_guess_strategy.md` 先声明研究口径，再给总判断、分 Section 规则、反例和执行顺序。其核心不是口诀，而是规则强度校准：

> “这份文档能支持的不是‘固定口诀’，而是四层更稳的判断。”
>
> “短项只是弱加分。短要和‘关系完整、能接住题问’一起看，不能因为短就直接选。”

随后用 `48/247`、`40/351` 等实际命中率拆掉“最长项更可靠”的直觉。高价值写法是每条启发式都有权重、反例和适用域。AI 痕迹是“先排包装，再看关系”“不是铁律”“只能/不能”反复出现，规则多时读者仍可能需要二次压缩。

可执行规则：任何策略词（通常、倾向、值得）必须给适用范围和反例；策略总结最多保留三级强度（强排除、弱提示、无证据），不要每条都再写一段免责声明。

## 8. 阅读卡：工程运行手册与责任边界体

代表文档：MD-19、MD-20。

`readme_demo_test.md` 的读者路径明确：仓库做什么、入口在哪、负责什么、不负责什么、怎样运行、输出在哪、哪些结果不能写进论文。它写道：

> “目标不是‘简单介绍一下’，而是让你在不了解历史上下文的情况下，也能尽快搞清楚下面几件事。”
>
> “这个仓库不是‘某一个算法的实现’，而是一个 LSGO 实验平台。”

工程文档的稳定双动作是“给路线 + 预先声明不该如何解读”。这不是普通的严谨，而是对误操作负责。AI 痕迹是每个概念都配反定义、每步都配边界，导致上手手册逐渐长成架构报告。

可执行规则：快速开始只保留最短成功路径；责任边界集中到一个表；同一警告不在入口、示例、FAQ 三处全文重复。

## 9. 阅读卡：审计台账与结构化核对体

代表文档：MD-21。

该文档由生成依据、全局计数、风险标签、逐题行号、证据片段、建议和状态枚举组成。其“句子”本质上是可定位记录，不是散文。把其中“风险、复核、必须”等词频并入普通写作，会错误夸大 GPT 的口头禅。

可执行规则：先判定文档是否是表/台账；台账评价字段完整性、状态一致性和可定位性，不用散文流畅度评价；最终论文只引用台账结论和方法，不复制台账语气。

## 10. 阅读卡：教材-反陷阱讲义体

代表文档：MD-22。

结构是总地图、规则、代码微例、典型题、答案解析、坑点、背诵版。同一命题被解释、题型和速记三次编码。标题使用“阴招、秒杀、救命表、坑点”，读者被设定在考试场景；代码不是附件，而是最小解释单元。

优点是检索和复习友好；AI 痕迹是覆盖欲过强，一条规则为了“完整”被多轮复现。去 AI 不能简单删例子，而应选择一个主解释和一个反例，其余移入索引或练习。

## 11. 阅读卡：语言质量管理化

代表文档：MD-23、MD-24。

圆锥曲线计划把“人类推理链”具体化：不靠“显然、注意到、由引理知”跨步；新字母先解释用途；关键变形说明目标；后一步由前一步逼出。它还写：

> “语言保持参考答案式冷静克制，不写讲稿腔、表演腔、安慰腔。”

这说明 GPT 擅长把模糊审美要求翻译成验收动作。风险是自然写作被过度流程化，所有句子都解释“为什么现在出现”，反而没有必要留白。

可执行规则：只解释非显然选择；常规代数变形不逐步元叙述；删除“为了……我们……”时，检查数学目标是否已由式子和前句清楚显示。

## 12. 阅读卡：产品技术与参赛展示体

代表文档：MD-25、MD-26。

技术文档追求模块、接口、性能、测试、维护全覆盖；展示稿采用“问题三联-方案三联-技术架构-MVP-增长愿景”。两者都使用粗体、符号、指标和密集列表，且存在功能列表重复，显示“覆盖优先于去重”。

这些材料不是论文文风核心样本。它们的价值是提醒：任务模板对语言影响很大，不能把竞赛稿的“痛点/亮点/愿景”误报为所有 GPT 正式写作的固有味道。

## 13. 排除与混杂记录

- C 盘中文 `SKILL.md` 是环境提示模板，不能当作历史 assistant 成稿。
- `requirement.md` 含翻译/外来核对卡，必须区分来源段。
- `Student_Score_Management_System/README.md` 是多轮维护合并稿，文体变化可能来自版本叠加。
- 路径出现在日志中只证明“被提到”，不证明由 assistant 生成。
- 完全重复哈希、工作树副本、备份和版本文件按家族分析。
- 乱码文件保留在 manifest，不进入例句，也不拖延其他可读样本。

## 14. TeX 精读总览

全域索引记录 1,657 个 TeX，其中 1,639 个可读、17 个空文件、1 个二进制/含空字节文件。“已归集”不等于“已人工精读”；本轮完整精读用户明确指定的 `main.tex` 和 CET6 TeX，并按版本族而非文件数计权。

| 编号 | 文档/版本族 | 来源 | 文体任务 | 核心判断 |
|---|---|---:|---|---|
| TEX-01 | 微信文件 `main.tex` | A1 | 数学建模论文 | 审计意识强；草稿元话语、五问同构、重复边界和事实矛盾并存。 |
| TEX-02 | `CET6.source-damaged.backup.tex` + `test.tex` | A1 | CET-6 作文功能句库 | 固定论证槽位配华丽词替换；乱码部分跳过。 |
| TEX-03 | `section_b_final_conclusions_report_v2.tex` + `unified59.tex` | A1 | Section B 长报告 | 近重复版本；旧结论未退出，免责声明不能消解冲突。 |
| TEX-04 | `section_b_final_conclusions_report.tex` | A1 | Section B 考生手册 | 动作具体、边界诚实，但同一结论多轮重复支架。 |

## 15. `main.tex` 全文阅读卡

该文件共 479 行，无乱码。摘要把背景、模型、校准、结果、局限和建议压在一个长段；逐问分析混入“应该怎样写”的编辑提示；五问模型逐层传递，`E(t)` 从问题一进入问题二，实体承接自然；406-430 行五次“本问的优点不在于……而在于……”和同构局限段，是最强模板痕迹；全文没有独立综合结论。

高价值原文包括：

> “恢复并不意味着单向改善。”
>
> “硬锚点校准……外推一致性检验，而非独立外部验证。”
>
> “问题三承担的是‘代表性长期轨道展示’，而不是直接给出混沌判据。”

文本还如实报告 75 组压力测试中仅 5 组保留符号跨越，没有隐藏不稳健结果。应保留这种证据降格能力。

主要 AI 痕迹是“后文若、正文里要、表格的作用、参数扫描的写法、如果把它放到图上”等编辑元话语，以及“口径、锚点、角色、模块、链条、闭环、压力测试”等工程评审词。严谨内容又被五组完全对称的优点/局限模板包住，同一阈值边界跨章节复述。

前向审计发现六类硬问题：

1. 文字称只改变一个食源权重、其余不变；表格同时改变三个权重。
2. “禁渔+污染”情景还提高阻隔，却把变化归因于污染，存在混杂。
3. “中华鲟”和“长江鲟”混用，可能错配生物对象。
4. `S(t)` 同时指代珍稀物种和另一个鱼类状态。
5. `0.204` 在摘要、结果和局限中被称为不同指标，并把终点最低值称为“暂时下降”。
6. 只有 5/75 组保留的区间仍被称为“混沌阈值”，主张过强。

因此去 AI 必须先过事实、符号和实验设计门禁，再处理句式。

## 16. CET-6 作文素材库阅读卡

`CET6.source-damaged.backup.tex` 的中文大面积乱码，按要求跳过；可读英文与 `test.tex` 一并分析。两者是前后版本，不是两份独立风格。

旧版频繁使用 `profound awakening`、`ultimate armor`、`civilizational imperative`、`catastrophic`、`unprecedented`，把普通社会话题升级为危机或文明命题；第 130 行还出现 `universities must offering`，说明高词汇密度会遮住基础语法错误。

`test.tex` 将作文显式写成四段式生成语法。第 226 行直接规定：

> “统一套路：承接第二段结果 -> 表层解释 -> 深层机制 -> 辩证限制 -> 目的导向收束。”

第 318-327 行轮换 `What matters / The ultimate question / The real value / The defining test`；第 337-357 行轮换 `Ultimately / In conclusion / Taken together / On balance`。词不同，逻辑槽位不变。这类 AI 感来自“固定论证槽位 + 华丽词替换”，不是几个禁词。

## 17. Section B 短报告阅读卡

短版采用考生口语：`先看、先记、一眼认出来、先放着、塞进去、硬找、账本`。基本单元是“误区 -> 统计发现 -> 直接动作 -> 防误用边界”。它能区分统计最优与考场成本，也明确小样本规则不能当绝对命令。

主要 AI 痕迹是过度教学支架：摘要、章节、执行版和结尾反复给同一套动作。它适合作为培训手册，不适合直接当学术报告正文。一个结论应只有一个权威出口，其余位置短回指。

## 18. Section B 长报告版本族阅读卡

`v2` 与 `unified59` 是近重复，应按一个版本族计权。长版混合统计报告的“熵、覆盖率、样本口径”，项目管理的“主入口、补回、统一口径”，考试教练的“裸做、死磨、满仓、减仓、收割、铁律”，作者声音不断切换。

最严重的问题是“声明统一，但旧结论仍在正文”：一处说 Q36 不是默认起手锚，后文又给 Q36 起手流程；一处按 59 套解释，旧附录表仍回加为 56。`铁律、永远、显著`又没有绑定检验，甚至把负相关、低近邻率和绝对互斥互换。

这揭示另一种模板机制：“不断追加版本 + 用免责声明维持表面统一”。真正修复需要列出旧结论的删除、保留和替换，全文搜索相反动作，并让表格分组回加到总样本。句子润色无效。

## 19. TeX 新增强制规则

1. 同一版本族只计一次；新版本必须列旧结论的删除/保留/替换。
2. 写“最终统一口径”前全文搜索相反动作，不能用免责声明覆盖冲突。
3. `显著、铁律、永远、100%、足以证明`必须绑定检验和适用范围。
4. 负相关、低近邻率和绝对互斥不得互换。
5. 表格分组必须回加到总样本。
6. 学术正文保持研究者声音；考试教练词只留在手册。
7. 一个结论只设一个权威出口，不在摘要、动作卡、速记版和结论四次复述。
8. 不用 `This practice/shift/trend`充当万能主语，改用具体变量、样本和观察。
9. 不把“表层-深层-思辨-目的”设为每段必经路线。
10. 转换 MD 到 TeX 后检查 Markdown 标记、残句、空格和主谓错误。
11. 符号一义；物种、变量、指标名称不得为了词汇变化而轮换。
12. 复合情景不得用单因素因果语言解释。

## 20. 其他去重教材 TeX：正确性门禁

本轮还人工核查了去重后的教材/习题 TeX 家族。来源没有完成作者闭环，因此只作观察样本，不归因成 GPT 的普遍能力。

`D:\code LateX\learn-shufen\chapters\chap3.tex` 有两处能说明“流畅不等于正确”：第 14-16 行将中心差分中的 `f(x_0-\Delta x)`误写成 `f'(x_0-\Delta x)`；第 117 行又把 `e^{-t}/e^t`化成 `e^{2t}`，正确应为 `e^{-2t}`。完整的推导口吻和连续等号掩盖了对象/指数错误。

`D:\code LateX\elegantbook\QA\QA.tex` 第 154-160 行先以“选项有马脚”和凸性排除答案，再使用正态近似及正态三阶原点矩公式解释二项分布。本题 `p=0.5` 时结果恰为 1150，但更可靠的论证应使用二项分布阶乘矩精确计算；答案数值正确不能证明方法可推广。

新增硬规则：数学对象、指数和符号必须独立验算；有精确公式时不得用未量化误差的近似替代；看选项策略只属于考试手册，不得进入学术证明。

## 21. 日志明确指向 assistant 输出的 207 份文件逐项闭环清单

本节使用 2026-07-10 当前 manifest 与 provenance 的精确交集重新编号。纳入条件是：路径出现在 assistant `response_item`、能与本地 manifest 精确匹配、文件可读且含中文。`explicit_assistant_output` 只说明 assistant 输出过该路径，不自动证明全文原创。

覆盖标记：`F` 表示 Markdown 全文阅读或 TeX 按完整章节/论证链读完；`S` 表示超大 TeX 的结构全览与跨章精读；`X` 表示坏 OCR 段跳过、可读部分继续。`F` 不等于每个公式已经独立验算。

### 21.1 研究论文、建模稿与写作控制文档（0-20）

| ID | 覆盖 | 文件 | 段落身份/文体 | 人工结论 |
|---:|:---:|---|---|---|
| 0 | F | `C:\Users\Lenovo\.codex\AGENTS.md` | 代理指令 | 环境约束，不是学术成稿；从风格流行率分母剔除。 |
| 1 | F | `D:\【赛题相关】...\2026A...\gpt思路.md` | 建模施工图 | “结论-锚点-模型-代码-论文”总编式分解，职责清楚但元控制过密。 |
| 2 | F | `D:\【赛题相关】...\solution\paper\main.tex` | 数学建模论文 | 五问承接自然；局地验证、权重敏感性和复合情景的因果主张偏强。 |
| 3 | F | `D:\2026-BYD-arxiv\drafts\conditioning_aware_grouping_algorithm.md` | 方法设计稿 | 定义、评分、算法、边界齐全；局部几何到优化性能的外推需降格。 |
| 4 | F | `D:\2026-BYD-arxiv\drafts\method_section_cn_cag_sort_v1.md` | 方法章节 | “不是分组器而是后处理”纠偏密集，公式对象较明确。 |
| 5 | F | `D:\2026-BYD-arxiv\drafts\paper_rewrite_outline_after_pivot.md` | 论文改写提纲 | 把章节写成生产工位，职责清楚但元写作明显。 |
| 6 | F | `D:\2026-BYD-arxiv\drafts\paragraph_level_rewrite_plan_2026-05-18.md` | 段落施工图 | 每段固定 claim/evidence/boundary/transition，机械对称。 |
| 7 | F | `D:\2026-BYD-arxiv\drafts\paragraph_level_rewrite_plan_sccd_2026-05-19.md` | 段落施工图 | must/not、保留/删除和审稿预演反复，管理声线强。 |
| 8 | F | `D:\2026-BYD-arxiv\drafts\rewrite_blueprint_intro_prelim_method_sccd.md` | 章节蓝图 | “缺口-方法-贡献”稳定，但模板先于证据。 |
| 9 | F | `D:\2026-BYD-arxiv\drafts\sccd_experiment_master_plan_2026-05-21.md` | 实验总控 | 门禁和停止条件有价值；P2/P3 定义后继续引用不存在的 P4。 |
| 10 | F | `D:\2026-BYD-arxiv\drafts\sccd_v2_converged.md` | 方法收敛稿 | 块级四分类解释充分，同一决策链多次复述。 |
| 11 | F | `D:\2026-BYD-arxiv\imitation\imitation_report.md` | 写作模仿报告 | 将论文拆成可复制动作，审稿预演和模板迁移感强。 |
| 12 | F | `D:\2026-BYD-arxiv\imitation\requirement.md` | 混合需求/外来材料 | 不整体归因 GPT；翻译卡、要求和生成说明需分段。 |
| 13 | F | `D:\2026-BYD-arxiv\notes\2026-05-18_meeting_reorientation.md` | 会议转向记录 | “放弃旧线-锁定新线-立即动作”，典型项目经理声线。 |
| 14 | F | `D:\2026-BYD-arxiv\notes\conditioning_aware_grouping.md` | 方法探索笔记 | 对象、公式、风险、伪代码齐全，探索判断过早定稿化。 |
| 15 | F | `D:\2026-BYD-arxiv\notes\experiment_protocol.md` | 实验协议 | 预算和缓存口径可复现；缓存与论文表述存在冲突风险。 |
| 16 | F | `D:\2026-BYD-arxiv\notes\paper_results_conclusions.md` | 结果边界说明 | 正负证据分级好，但大量“怎么写”尚未转为实际论证。 |
| 17 | F | `D:\2026-BYD-arxiv\paper\main.tex` | 英文论文主稿 | 长句复沓且有中文草稿残留；算法与尺寸控制承诺未完全对应。 |
| 18 | F | `D:\2026-BYD-arxiv\paper\paper_CN.tex` | 中文论文版本 | 机制、相关和对照并重；分组规模、缓存和嵌套相关有过强论断。 |
| 19 | F | `D:\2026-BYD-arxiv\paper\paper2.tex` | 论文版本稿 | 新增尺寸控制又与 hostile 整块保留矛盾；结果区留有脚手架。 |
| 20 | F | `D:\2026-BYD-arxiv\README_CN.md` | 项目首页 | 运行、目录和研究叙事一体化，清楚但与论文重复。 |

### 21.2 教材、CET-6 策略与早期审计（21-38）

| ID | 覆盖 | 文件 | 段落身份/文体 | 人工结论 |
|---:|:---:|---|---|---|
| 21 | S | `D:\code LateX\beauty\beautybook-cn.tex` | 超大教程 TeX | 问句、类比、公式、白话、小结循环；拟人和宏大词过量。 |
| 22 | F | `...\section_b_correlation_notes.md` | 跳转桩 | 章节号失效的版本残留，不作独立文风样本。 |
| 23 | F | `...\section_b_exam_playbook.md` | 跳转桩 | 与正文报告的入口关系过期，不独立计权。 |
| 24 | F | `...\section_b_final_conclusions_report.md` | 统计型应试报告 | 59 套 590 题边界较诚实；8-12 例的小规则容易过拟合，结论重复。 |
| 25 | F | `...\section_b_final_conclusions_report.tex` | 排版副本 | 24 的 TeX 版本，按一个 composition 计权。 |
| 26 | F | `...\listening_blind_guess_strategy.md` | 听力策略报告 | 强排除、弱提示和候选簇分级好；1088 行造成同结论多出口。 |
| 27 | F | `...\listening_exam_addendum.md` | 策略补充 | 与 playbook/complete 大段复用，版本职责不清。 |
| 28 | F | `...\listening_exam_playbook.md` | 考试教练手册 | 题点、陷阱、动作层级清楚，教练口吻强。 |
| 29 | F | `...\listening_source_audit.md` | 证据审计 | 简短诚实，明确答案键不完整。 |
| 30 | F | `...\listening_strategy_complete.md` | 完整策略版 | “不是答案保证而是题眼预警”反复；旧版本口径需核对。 |
| 31 | S | `D:\code LateX\elegantbook\CET6\CET6.tex` | 超大作文/策略 TeX | 口诀按钮、让步-边界-反噬和可替换槽位，模板作文味强。 |
| 32 | F | `...\elegantbook1\.codex\short_display_math_report.md` | 机器审计表 | 表格型检测结果，不作自然散文证据。 |
| 33 | F | `...\elegantbook1\build\pdf_import\manual-audit.md` | PDF 导入审计 | 来源、页码、问题、修正和状态可追溯。 |
| 34 | F | `...\elegantbook1\build\pdf_import\progress.md` | 进度记录 | “本轮/已录入/已核对”属于状态词，不混入论文词频。 |
| 35 | F | `...\elegantbook1\cpp_class_object_traps.md` | 反陷阱讲义 | 地图、代码、答案、坑点、口诀多重编码；“阴招/秒杀/救命”教练腔。 |
| 36 | S | `...\elegantbook1\elegantbook1.tex` | 超大概率教材 | 定义、性质、例题、口诀、陷阱循环，检索友好但模板化。 |
| 37 | F | `...\elegantbook2\chapter7_solution_audit.md` | 总体解答审计 | 状态码和问题表清楚；记录条件不足与高阶计算跳步。 |
| 38 | S | `...\elegantbook2\elegantbook2.tex` | 4.4 万行教材 | “入口/底座/母式/送回/收口”把知识写成决策树。 |

### 21.3 `elegantbook2` 解答质量审计流水线（39-73）

下列文件属于同一整改 composition。逐份阅读全文的价值是观察规则如何演化和错误如何暴露，不按 35 个独立文体样本重复加权。

| ID | 覆盖 | 文件 | 人工结论 |
|---:|:---:|---|---|
| 39 | F | `batch_001_review.md` | 数学、排版、子任务和放行五重状态并列。 |
| 40 | F | `batch_002_confirmation.md` | 自动分级后仍发现退化条件和中间推导不闭合。 |
| 41 | F | `batch_003_confirmation.md` | 记录递推错误、Green/面积法串台和占位解。 |
| 42 | F | `batch_004_review.md` | 三角积分整改；“重点落地/不扩审/清零/编译”治理语体。 |
| 43 | F | `batch_005_review.md` | 特殊函数；参数条件、算子残留、长式和 PDF 抽查。 |
| 44 | F | `batch_006_review.md` | 微分方程；补特殊解、区间并修五阶通解。 |
| 45 | F | `batch_007_review.md` | 一阶方程逐号整改，以禁词清零和编译放行收尾。 |
| 46 | F | `batch_009_review.md` | 修零频率、共振、根型和题面不闭合。 |
| 47 | F | `batch_010_review.md` | 多元极限/方向导数；路径法和余项商，反对短式机械 display。 |
| 48 | F | `batch_012_review.md` | 定义域、间断点、Jacobian 与 52.5 字符排版阈值并列。 |
| 49 | F | `batch_013_review.md` | 直接记录二阶偏导和符号硬错；格式完整未掩盖事实修复。 |
| 50 | F | `batch_015_review.md` | 极值/几何；数值根与 Hessian 复核，数据密度高。 |
| 51 | F | `batch_016_review.md` | 重积分；奇点、Tonelli、Jacobian，账本思维明显。 |
| 52 | F | `batch_017_review.md` | 脚本高估后回到人工 PDF 目检，放行不等于“公式不长”。 |
| 53 | F | `batch_018_review.md` | 三重积分；修数值错误、引力方向和反常截断。 |
| 54 | F | `batch_019_review.md` | 总习题；换序、奇点和题名/方法冲突。 |
| 55 | F | `batch_020_review.md` | 第一类线积分；参数、微元、密度和积分统一。 |
| 56 | F | `batch_021_review.md` | 第二类线积分；奇点、保守场、Green/Stokes 定向。 |
| 57 | F | `batch_022_review.md` | Green/Stokes；挖洞、内边界符号、观察方向转法向。 |
| 58 | F | `batch_023_review.md` | 统一第二类曲面积分分量顺序，定理和解答一起修。 |
| 59 | F | `batch_024_review.md` | 曲线积分基础；定义、分段路径、方向和通量。 |
| 60 | F | `batch_025_review.md` | 第一类面积分；投影、面积元和绝对值，短而完整。 |
| 61 | F | `batch_029_review.md` | 从拆长式转向压缩低地位短 display。 |
| 62 | F | `batch_030_review.md` | 散度/Gauss；全表面、上下底和侧面封口账本。 |
| 63 | F | `batch_031_review.md` | 旋度/Stokes；法向与观察方向可追溯。 |
| 64 | F | `batch_032_review.md` | 向量恒等式；补二阶连续条件和证明跳步。 |
| 65 | F | `batch_033_review.md` | 补缺失题图，并修 Hooke 中心力实质模型错误。 |
| 66 | F | `batch_034_review.md` | 级数估阶；有限初项、零因子和参数边界。 |
| 67 | F | `batch_035_review.md` | 补交错裂项和 Cauchy 尾和下界。 |
| 68 | F | `batch_036_review.md` | 修 `ln 1` 起点和不严谨不等号，判别条件完整。 |
| 69 | F | `batch_037_review.md` | 修正由上下界极限不同仍直接夹逼收敛的错误证明。 |
| 70 | F | `batch_038_review.md` | 继续使用“范围-复核-证据-放行”模板。 |
| 71 | F | `batch_039_review.md` | 批次复核与残余风险收尾，工单声线稳定。 |
| 72 | F | `phase1_confirmation_packet.md` | 明确自动 flag 只是队列，不是最终判断；设硬性放行门槛。 |
| 73 | F | `solution_quality_ledger.md` | 台账状态化和“候选清零”语言，不作论文散文词频。 |

### 21.4 风格报告、历年试题与 OCR（74-113）

| ID | 覆盖 | 文件 | 段落身份/文体 | 人工结论 |
|---:|:---:|---|---|---|
| 74 | F | `physics/full_style_reorganization_plan.md` | 风格重整计划 | 方法边界清楚；自身仍有计划书的对称栏目和验收语体。 |
| 75 | F | `physics/gpt_chinese_style_report.md` | 聊天风格简报 | 结论可扫描，但口头禅分析不应替代学术文稿分析。 |
| 76 | F | `physics/gpt_chinese_style_report_detailed.md` | 数据型深度报告 | 表格、限定语和证据附录完整，结构密度高。 |
| 77 | F | `physics/gpt_chinese_style_report_restructured.md` | 学术风格主报告 | 报告诊断模板化时自身仍偏层级化；本轮继续实质扩写。 |
| 78 | F | `word/past-exams/audit.md` | 试题审计 | 明确部分答案由题目重建而非官方来源；从编译转向数学正确性。 |
| 79 | F | `word/past-exams/audit-pdf-ocr.md` | OCR 审计 | 页码、截图、残缺和来源证据链清楚。 |
| 80 | F | `word/past-exams/ch7-skeleton.tex` | 章节骨架 | 模板结构，不作为完整自然成稿。 |
| 81 | F | `word/past-exams/manifest.md` | 文件清单 | 状态记录，不并入散文语气。 |
| 82 | F | `reviewed/2006-2007.tex` | 继承题面 + 生成解答 | 只归因解答段；短链“由-代入-得”明显。 |
| 83 | F | `reviewed/2009-A-draft.tex` | 试题解答 | 条件-公式-结论压缩，收尾同质。 |
| 84 | F | `reviewed/2009-B-draft.tex` | 试题解答 | 连续计算链强，解释峰值较弱。 |
| 85 | F | `reviewed/2012-A-draft.tex` | 试题解答 | 定理和代入为主，题面不计模型文风。 |
| 86 | F | `reviewed/2012-B-draft.tex` | 试题解答 | 证明短而工整，结论句模板化。 |
| 87 | F | `reviewed/2013-A-draft.tex` | 试题解答 | “令-由-故”稳定；需独立核验公式。 |
| 88 | F | `reviewed/2013-B-draft.tex` | 试题解答 | 计算链完整，来源题面与生成解答分层。 |
| 89 | F | `reviewed/2014-A-draft.tex` | 试题解答 | 例行步骤可再压缩，关键理由应突出。 |
| 90 | F | `reviewed/2014-B-draft.tex` | 试题解答 | 稳定参考答案体，几乎无第一人称。 |
| 91 | F | `reviewed/2015-A-draft.tex` | 试题解答 | 结论明确，过渡句均匀。 |
| 92 | F | `reviewed/2015-B-draft.tex` | 试题解答 | 条件、计算、答案四段式稳定。 |
| 93 | F | `reviewed/2016-A-draft.tex` | 试题解答 | 教材式冷静语气，例行推导篇幅偏满。 |
| 94 | F | `reviewed/2016-B-audit.md` | 校勘审计 | 来源、风险和修改状态，不作题解文风。 |
| 95 | F | `reviewed/2017-A-audit.md` | 校勘审计 | 人工判断与自动检查边界清楚。 |
| 96 | F | `reviewed/2017-A-draft.tex` | 试题解答 | 短证链清晰，收尾公式化。 |
| 97 | F | `reviewed/2017-B-audit.md` | 校勘审计 | 可定位风险记录，非散文样本。 |
| 98 | F | `reviewed/2018-A-draft.tex` | 试题解答 | 参考答案式陈述，逻辑连接密。 |
| 99 | F | `reviewed/2018-B-draft.tex` | 试题解答 | 条件到结论直接，但方法解释层级不足。 |
| 100 | F | `reviewed/2019-A-draft.tex` | 试题解答 | 数学对象主语较少，常用无主语推进。 |
| 101 | F | `reviewed/2019-B-draft.tex` | 试题解答 | “代入/化简/可得”高密，需防黑箱步骤。 |
| 102 | F | `reviewed/2020.tex` | 题面 + 生成答案 | 段落级区分来源后，解答保持短链模板。 |
| 103 | F | `reviewed/2020-audit.md` | 年度审计 | 编译、题面、答案和风险分栏。 |
| 104 | F | `reviewed/2021-2023.tex` | 多年份题面 + 重建答案 | 答案不能标成官方；重建语气确定但证据来源较弱。 |
| 105 | F | `reviewed/2021-2023-audit.md` | provenance 审计 | 明确答案系重建，限制值得保留。 |
| 106 | F | `reviewed/2022.tex` | 题面 + 生成解答 | 答案链压缩，需与校勘文件共同阅读。 |
| 107 | F | `reviewed/2022-A-audit.md` | 分卷审计 | 版本和校勘说明清楚。 |
| 108 | F | `reviewed/2022-audit.md` | 总审计 | 完整性与正确性并列，审计声线稳定。 |
| 109 | F | `reviewed/2022-B-audit.md` | 分卷审计 | 状态、风险和待复核项可定位。 |
| 110 | F | `word/word.tex` | 宏/编码/词典数据 | assistant 创建不等于自然语言原创；排除核心文风。 |
| 111 | X | `道德与法治/ocr.tex` | 教材 OCR 转写 | 破损段跳过；源教材措辞不归因 GPT。 |
| 112 | F | `道德与法治/.../closure_report.md` | OCR 闭环报告 | 反对仅凭脚本放行，保留手写/OCR 残余风险。 |
| 113 | F | `道德与法治/.../manual_ocr_audit.md` | 人工 OCR 复核 | 状态、页级证据和未决问题清楚，治理语体强。 |

### 21.5 简单导数教材与清理记录（114-133）

| ID | 覆盖 | 文件 | 人工结论 |
|---:|:---:|---|---|
| 114 | F | `简单导数/AI味句式清理第二轮.md` | 早期从怪词转向句式清理，但仍依赖人工词表。 |
| 115 | F | `简单导数/AI味句式清理第三轮.md` | 继续清理元话语；验收语气本身偏流程化。 |
| 116 | F | `chapters/chap1.tex` | Rolle/辅助函数证明多次以“模型”包装；存在复合函数端点论证风险。 |
| 117 | F | `chapters/chap10.tex` | 求和/裂项题模板稳定，关键裂项由来应保留。 |
| 118 | F | `chapters/chap11.tex` | 部分分式链反复“设-先-再-最终”；曾混有 OCR 和旧注释稿。 |
| 119 | F | `chapters/chap2.tex` | 复合函数与均值定理题，连续参考答案体。 |
| 120 | F | `chapters/chap3.tex` | 长证依赖插值余项和计算证书；旁白压缩后仍需说明工具边界。 |
| 121 | F | `chapters/chap4.tex` | 三角/零点题曾有双层“先概述再证明”；后续清理记录承认初判过早。 |
| 122 | F | `chapters/chap5.tex` | Padé 与辅助函数密集；若干数值界缺推导或引用。 |
| 123 | F | `chapters/chap6.tex` | 条件方向冲突、局部 Taylor 推全局和增长手挥是事实硬风险。 |
| 124 | F | `chapters/chap7.tex` | 概率、数列和三零点长证；连续推理比小标题自然，但长证仍匀速。 |
| 125 | F | `chapters/chap8.tex` | 截线宽度比较用 Sturm/Bernstein/余项证书，证据重但已超出普通高中题解负担。 |
| 126 | F | `chapters/chap9.tex` | 斐波那契矩阵套路稳定；`2^n/2^(n-1)` 和乘积符号前后矛盾。 |
| 127 | F | `chapters/special.tex` | 构造法总述清楚；关键全域正性有“继续检查可知”的黑箱跳步。 |
| 128 | F | `Gemini残留统计第六轮.md` | 明确承认早期“基本清完”过于乐观，深层残留是句法和证明脚本。 |
| 129 | F | `Gemini残留统计第四轮.md` | 高风险词扫描归零后即宣称无明显 Gemini 腔，构成反例。 |
| 130 | F | `Gemini残留统计第五轮.md` | 继续以模板词清零和编译通过作阶段验收，仍未覆盖语义/正确性。 |
| 131 | F | `Gemini词汇清理清单.md` | 保存真实历史词证据；“第一轮定位”不能充当最终验收。 |
| 132 | F | `简单导数/main.tex` | 主要是章节装配和宏配置，几乎无自然文风；不独立加权。 |
| 133 | F | `简单导数/例题人类化撰写计划.md` | 主动要求连续短段、重工具说明和主次层级；自身仍像质量总控。 |

### 21.6 圆锥曲线教材（134-148）

| ID | 覆盖 | 文件 | 人工结论 |
|---:|:---:|---|---|
| 134 | F | `圆锥曲线/chap5_gemini_cleanup_checklist.md` | 记录历史伪术语和夸张词；表层删除不等于证明修复。 |
| 135 | F | `圆锥曲线/chap5_verification_log.md` | 明确 `2640-2703` 数值复核失败，结论和证明需重做。 |
| 136 | F | `圆锥曲线/chap6_gemini_cleanup_checklist.md` | 记录伪学术/表演词清理；需与现正文分开。 |
| 137 | F | `圆锥曲线/chap7_gemini_cleanup_checklist.md` | 清理游戏和教程口吻，但深层曲线系跳步仍在。 |
| 138 | F | `圆锥曲线/chapters/chap1.tex` | 基础工具铺陈完整，逐步解释密度高。 |
| 139 | F | `圆锥曲线/chapters/chap2.tex` | 参数和坐标关系解释充分，关键与例行步骤篇幅接近。 |
| 140 | F | `圆锥曲线/chapters/chap3.tex` | 定点/定值题按统一算子路线处理，模板迁移明显。 |
| 141 | F | `圆锥曲线/chapters/chap4.tex` | `T=E-1` 被误称双线性式，对象类型错误。 |
| 142 | F | `圆锥曲线/chapters/chap5.tex` | 三特殊位置推出完整包络、黑箱消元和失败数值例并存。 |
| 143 | F | `圆锥曲线/chapters/chap6.tex` | Poncelet 条件未就地建立，复杂半径公式用“化简可得”跳过。 |
| 144 | F | `圆锥曲线/chapters/chap7.tex` | 曲线系“存在常数使恒等”高频，交点重数/非退化条件常省略。 |
| 145 | F | `圆锥曲线/chapters/chap8.tex` | 后段例题仍沿用联合二次式和系数比较模板。 |
| 146 | F | `圆锥曲线/chapters/chap9.tex` | 定圆/轨迹题覆盖完整，但结论职责和例行运算未分层。 |
| 147 | F | `圆锥曲线/main.tex` | 章节装配文件，结构证据多于自然文风证据。 |
| 148 | F | `圆锥曲线/例题人类化撰写计划.md` | 明确反对“显然/由引理知”跳步，并要求只解释非显然选择。 |

### 21.7 LSGO 算法 README 与双语版本族（149-165）

前 14 份 `README.md` 的中文字符主要来自“中文版本”链接或极短导航，不足以支撑中文学术文风归纳；它们仍逐项列账，用于证明没有把“含几个汉字”误判成“中文成文”。三个 `README.zh-CN.md` 才进入中文方法说明的人工判断，但按一个稳定模板族计权。

| ID | 覆盖 | 文件 | 人工结论 |
|---:|:---:|---|---|
| 149 | F | `D:\LSGO-platform\baseline\cc\contribution_based\cbcco\README.md` | 英文算法说明，只有极少中文导航；保留来源记录，不进入中文正文权重。 |
| 150 | F | `D:\LSGO-platform\baseline\cc\contribution_based\occ\README.md` | 英文贡献型协同进化 README；栏目完整性不能当作中文文风证据。 |
| 151 | F | `D:\LSGO-platform\baseline\cc\statistics_based\ccshademl\README.md` | 英文统计型算法 README；中文含量不足，排除中文行文归纳。 |
| 152 | F | `D:\LSGO-platform\baseline\cc\vil\csg\README.md` | 英文主版与中文链接桩；与中文副本按同一 composition 处理。 |
| 153 | F | `D:\LSGO-platform\baseline\cc\vil\dg2\README.md` | 英文 API/算法说明；不因 assistant 输出路径而认定为中文原创。 |
| 154 | F | `D:\LSGO-platform\baseline\cc\vil\eadg\README.md` | 英文结构化算法说明；与中文说明共享栏目骨架。 |
| 155 | F | `D:\LSGO-platform\baseline\cc\vil\edg\README.md` | 英文算法 README，中文仅导航；从中文风格分母剔除。 |
| 156 | F | `D:\LSGO-platform\baseline\cc\vil\erdg\README.md` | 英文算法 README；“存在路径”只作 provenance，不作汉语样本。 |
| 157 | F | `D:\LSGO-platform\baseline\cc\vil\mdg\README.md` | 英文方法说明；不把文件级写入事件扩展为句级中文作者归因。 |
| 158 | F | `D:\LSGO-platform\baseline\cc\vil\oedg\README.md` | 英文主版，与中文副本和同族算法说明去重计权。 |
| 159 | F | `D:\LSGO-platform\baseline\cc\vil\rddsm\README.md` | 英文算法说明；名称和职责必须以源码/论文核验，格式不能作证。 |
| 160 | F | `D:\LSGO-platform\baseline\cc\vil\rdg2\README.md` | 英文算法 README；中文字符不足以形成可分析段落。 |
| 161 | F | `D:\LSGO-platform\baseline\cc\vil\rdg3\README.md` | 英文算法 README；仅纳入版本族和事实一致性检查。 |
| 162 | F | `D:\LSGO-platform\baseline\cc\vil\README.md` | VIL 家族英文索引；职责是导航，不作为连续学术论证。 |
| 163 | F | `D:\LSGO-platform\baseline\cc\vil\csg\README.zh-CN.md` | “一句话定义-核心特点-流程-优势-机制-复杂度”栏目齐全；评价词缺比较基准。 |
| 164 | F | `D:\LSGO-platform\baseline\cc\vil\eadg\README.zh-CN.md` | 三项特点和三阶段流程高度对称；方法对象清楚，但“高效/准确/全面”证据不足。 |
| 165 | F | `D:\LSGO-platform\baseline\cc\vil\oedg\README.zh-CN.md` | 与 CSG/EADG 复用同一说明壳；应突出 OEDG 独有假设、失败条件和实验依据。 |

### 21.8 LSGO 治理、API、实验记录与长文档（166-179）

| ID | 覆盖 | 文件 | 人工结论 |
|---:|:---:|---|---|
| 166 | F | `D:\LSGO-platform\baseline\cc\vil\VIL_CODE_STANDARD.md` | 规范条目可执行，但命令式“必须/禁止”属于代码治理声线，不迁入论文论证。 |
| 167 | F | `D:\LSGO-platform\CHANGELOG.md` | 版本事实应按日期和变更对象阅读；列表密度不是自然散文风格。 |
| 168 | F | `D:\LSGO-platform\CODE_REVIEW_STANDARD.md` | 检查表、严重度和放行条件清楚；只适合作为审查规则，不作为学术段落模板。 |
| 169 | F | `D:\LSGO-platform\CONTRIBUTING.md` | 贡献流程、命名和提交流程是协作合同；管理词在此合理，不能外推为论文偏好。 |
| 170 | F | `D:\LSGO-platform\SECURITY.md` | 安全报告边界与联络流程明确；篇幅短且任务专用，不进入一般学术文风权重。 |
| 171 | F | `D:\LSGO-platform\docs\en\api\algorithms.md` | 英文 API 文档外观完整；算法全称、类路径和性能主张仍需源码/基准核对。 |
| 172 | F | `D:\LSGO-platform\docs\zh\api\algorithms.md` | 中英标题、参数表、星级和建议形成“栏目先行”写法；发现错误全称、类路径和无来源性能评级。 |
| 173 | F | `D:\LSGO-platform\readme_utils.md` | 长期追加导致章节号整体滞后一章、相邻职责重复；需重建目录而非只改编号。 |
| 174 | F | `D:\LSGO-platform\experiment_record_v1_fields.md` | 字段 schema 和状态定义属于机器可读记录合同；不按连续论文散文评价。 |
| 175 | F | `D:\LSGO-platform\repository\demo_test\lsops2022\f1\2026-05-01_21-57-16\data\experiment_record.md` | 单次实验元数据/结果记录，证据价值在可复现字段，不在修辞。 |
| 176 | F | `D:\LSGO-platform\repository\demo_test\lsops2022\f1\2026-05-01_21-57-16\data\experiment_record.tex` | Markdown 记录的 TeX 排版副本；同一 composition，不重复加权。 |
| 177 | F | `D:\LSGO-platform\docs\metric_screening_notes.md` | 指标筛选将候选、标准和保留理由写成决策账本；阈值与外部有效性需另证。 |
| 178 | F | `D:\LSGO-platform\readme_demo_test.md` | 上手说明持续追加后出现章节号和职责漂移；`run/observer` 边界多次复述。 |
| 179 | F | `D:\LSGO-platform\report.md` | 多轮“最终/完成度/闭环”产生多个权威出口；新结论没有回写并替换旧结论。 |

### 21.9 Probet 提示词、可视化与审计资产（180-184）

| ID | 覆盖 | 文件 | 人工结论 |
|---:|:---:|---|---|
| 180 | F | `D:\Probet\gpt55_deep_research_prompt_random_dimension_generic_round4.md` | 研究提示词以角色、任务、输出、禁项和验收组织；属于元指令，不得当作论文成稿。 |
| 181 | F | `D:\Probet\lsgo_visualization_assets\examples\formal_single_closure_audit\aggregate_formal\multi_experiment_summary.md` | 多实验汇总按证据位置、状态和结论组织，审计性强；状态完成不等于模型有效。 |
| 182 | F | `D:\Probet\lsgo_visualization_assets\examples\formal_single_closure_audit\xiatong_closure_audit.md` | 单闭环样例强调可追踪和放行；适合质量记录，不宜复制其工单语气到论文。 |
| 183 | F | `D:\Probet\lsgo_visualization_assets\readme_visualization.md` | 可视化工程入口、输入输出和失败归因清楚；说明体与研究结论必须分开。 |
| 184 | F | `D:\Probet\fingerprint-readme.md` | 把特征指纹写成项目决策接口；对象和用途明确，但“探针/闭环”管理隐喻密集。 |

### 21.10 Probet 文献精读与项目决策翻译器模板族（185-204）

20 份文件逐份阅读全文，但作为一个版本/模板家族计权。共同骨架是“论文角色-边界判断-原文解释-项目关系-可借鉴-不可照搬-最终用途”；逐篇判断重点是保留各自独有的数学对象、假设、失败条件和可支撑命题。

| ID | 覆盖 | 文件 | 人工结论 |
|---:|:---:|---|---|
| 185 | F | `D:\Probet\papers_probe_related\01_DG_2014_Cooperative_CoEvolution_with_Differential_Grouping.md` | 以变量交互和分组为中心；项目映射完整，但公共背景占用论文独有假设的篇幅。 |
| 186 | F | `D:\Probet\papers_probe_related\02_DG2_Faster_More_Accurate_Differential_Grouping.md` | 重点是 DG2 的判别对象与效率改进；“更快更准”必须绑定原论文实验而非标题复述。 |
| 187 | F | `D:\Probet\papers_probe_related\05_RDG_Recursive_Differential_Grouping.md` | 递归分组逻辑可转为算法对象；需把项目启发与论文实际证明分栏。 |
| 188 | F | `D:\Probet\papers_probe_related\06_GIAT_Global_Information_Adaptive_Threshold.md` | 自适应阈值是独有对象；不能用相邻 OCR 或页码替代精确命题证据。 |
| 189 | F | `D:\Probet\papers_probe_related\08_FDG_Fast_Differential_Grouping_Algorithm.md` | 快速分组的复杂度/实验条件是核心；模板化“可借鉴”段落需要落到具体操作。 |
| 190 | F | `D:\Probet\papers_probe_related\09_RDG3_Overlapping_Components_Decomposition.md` | 重叠组件是关键边界；项目迁移不得抹平其问题设定。 |
| 191 | F | `D:\Probet\papers_probe_related\10_SVG_Surrogate_Assisted_Variable_Grouping.md` | 代理辅助分组需保留代理误差和适用条件；不能只抽取“减少评估”结论。 |
| 192 | F | `D:\Probet\papers_probe_related\11_OEDG_Enhanced_Differential_Grouping_Overlapping_Problems.md` | OEDG 的重叠变量处理应成为主轴；公共探针叙事不应覆盖算法限制。 |
| 193 | F | `D:\Probet\papers_probe_related\12_LSGO_Review_Part_I.md` | 综述类证据层级低于原始算法论文；适合建立版图，不替代具体命题来源。 |
| 194 | F | `D:\Probet\papers_probe_related\15_Randomized_Hessian_Estimation_and_Directional_Search.md` | 随机 Hessian 估计与方向搜索对象明确；类比到探针时必须标成设计动机。 |
| 195 | F | `D:\Probet\papers_probe_related\16_Mixed_Second_Order_Partial_Derivatives_Decomposition_Method_for_Large_Scale_Optimization.md` | 混合二阶偏导是可验证对象；“支撑项目”必须指向可读原命题。 |
| 196 | F | `D:\Probet\papers_probe_related\17_Exploratory_Landscape_Analysis_GECCO2011.md` | ELA 特征和任务边界需分清；不能把描述性特征直接写成因果机制。 |
| 197 | F | `D:\Probet\papers_probe_related\18_Automated_Algorithm_Selection_by_ELA_and_ML.md` | 算法选择依赖数据集、特征和评估协议；项目迁移应保留外部验证要求。 |
| 198 | F | `D:\Probet\papers_probe_related\20_Towards_Exploratory_Landscape_Analysis_for_LargeScale_Optimization.md` | 大规模 ELA 的尺度限制是独有内容；不应被统一“可借鉴/不可照搬”模板压平。 |
| 199 | F | `D:\Probet\papers_probe_related\21_Wedge_Sampling_for_Computing_Clustering_Coefficients_and_Triangle_Counts.md` | 楔采样来自图统计语境；跨域借鉴必须说明对象映射和不可迁移条件。 |
| 200 | F | `D:\Probet\papers_probe_related\23_Landscape_Features_Generalization_Wall_2025.md` | 泛化边界本身是核心结论；不应为项目正向叙事删去失败条件。 |
| 201 | F | `D:\Probet\papers_probe_related\24_Enhanced_Differential_Grouping_for_Large_Scale_Optimization.md` | 增强 DG 的对照对象和预算必须明确；评价词不能脱离基准。 |
| 202 | F | `D:\Probet\papers_probe_related\25_A_Composite_Decomposition_Method_for_Large_Scale_Global_Optimization.md` | 复合分解方法需保留组合条件；不能把算法名直接扩成普遍机制。 |
| 203 | F | `D:\Probet\papers_probe_related\26_On_the_Separability_of_Multivariate_Functions.md` | 可分性定义和判据是基础证据；最需要避免伪术语替代标准数学对象。 |
| 204 | F | `D:\Probet\papers_probe_related\README_论文索引.md` | 索引负责来源、状态和导航；不作为第 20 篇独立论证证据。 |

### 21.11 产品问卷与混合工程长文档（205-206）

| ID | 覆盖 | 文件 | 人工结论 |
|---:|:---:|---|---|
| 205 | F | `D:\project-costrict\Project_Documentation\Xiaomi_MiMo问卷填写建议.md` | 对外问卷代拟按问题拆目标、证据和建议措辞；属于产品申报写作，不混入论文文风。 |
| 206 | F | `D:\Student_Score_Management_System\README.md` | 6356 行将现状、旧计划、架构、答辩、测试和验收混在一条主路径；六/七/八页签与自测只读/会写入互相冲突。 |

至此，第 21 节编号从 0 连续到 206，共 207 项。机器对账只用于发现漏列路径；覆盖标记、文体身份和结论仍来自人工阅读。英文链接桩、重复版本、OCR/继承正文、机器 schema 和模板族均已列出，但没有被用来虚增中文学术散文证据。
