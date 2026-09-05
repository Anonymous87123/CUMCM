---
name: mcm-cup-standard-write
description: 按全国大学生数学建模竞赛 A/B/C 题优秀论文的证据、结构和真实行文习惯，起草、续写、重构或审计中文建模论文。适用于摘要、问题分析、假设、模型建立与求解、结果解释、检验、灵敏度、评价、参考文献、附录和 LaTeX 模板；重点解决模型空降、思考过程缺失、段落过度工整、AI 套语、模板化承接和结论越界。不用于 D/E 题，不承诺检测器分数或人类作者身份。
---

# MCM-CUP-STANDARD-WRITE

## 目标

写出可复算、能看见真实建模思考如何逐步走到公式和模型、读起来像同一支队伍连续完成的 A/B/C 类论文。人类感来自题面对象、局部矛盾、数学转化、试算痕迹、公式接口、局部取舍和有限结论，不来自错别字、随意口语、禁用词替换或伪造经历。

## 证据顺序

1. 赛题原文和附件定义对象、变量、单位、约束及提交任务。
2. 实际代码、日志、表格和图形定义模型、参数、结果和检验。
3. 59 篇编号论文只提供结构、判断动作和语言节奏，不授权复制句子、模型或数值。
4. 专家评述只用于理解题型背景，不混入获奖论文文风统计。
5. 证据不足时保留空缺或降低结论强度；不补造试算、比较、性能、显著性、引用和失败路线。

比赛初稿若同时提供题面、数据、代码和结果，先读取 `$aigc-writing-router` 的
[material-first-competition.md](../AIGC/aigc-writing-router/references/material-first-competition.md)，
并使用其 `evidence-manifest.json` 作为材料入口。该台账只负责来源、哈希和运行记录，
不能替代本 Skill 的建模推演；缺少实际运行记录时，不得把代码文件或预期输出写成已获得的结果。

## 按任务加载资料

不要把全部 references 同时装入一次生成上下文。规则过载会把不同论文的写法平均成整齐的模板腔。

| 当前任务 | 必读资料 | 选读资料 |
| --- | --- | --- |
| 起草或重写中文正文 | [fulltext-language-usage.md](references/fulltext-language-usage.md)、[modeling-workbench.md](references/modeling-workbench.md)、[reasoning-before-model.md](references/reasoning-before-model.md)、[decision-moves.md](references/decision-moves.md) | 先用 `scripts/query_style_patterns.py --source fulltext` 按题型、章节、动作和模型取 3--8 个正文段落及相邻上下文；成稿校准再读 [human-drafting.md](references/human-drafting.md) 和 [corpus-overlap.md](references/corpus-overlap.md)，需要单篇判断轨迹时用 `--source card` |
| 规划章节和篇幅 | [fulltext-language-analysis.md](references/fulltext-language-analysis.md)、[paper-structure.md](references/paper-structure.md) | 当前题型对应的 [problem-types-abc.md](references/problem-types-abc.md) |
| 生成 25--30 页正式竞赛正文 | [competition-longform.md](references/competition-longform.md)、[paper-structure.md](references/paper-structure.md)、[modeling-workbench.md](references/modeling-workbench.md)、[reasoning-preflight.md](references/reasoning-preflight.md)、[section-authoring-brief.md](references/section-authoring-brief.md)、[reasoning-review.md](references/reasoning-review.md)、[corpus-overlap.md](references/corpus-overlap.md)、[decision-moves.md](references/decision-moves.md)、[public-judgment-ledger.md](references/public-judgment-ledger.md) | 当前题型资料、`$aigc-writing-router` 的 evidence bundle、逐节 `public_judgment_contract`、`scripts/audit_section_judgment_bridges.py`、`scripts/audit_competition_length.py`、`scripts/audit_content_density.py`；若有外部结果，再运行结果同步门 |
| 生成或修改模板、学习报告 | [template-contract.md](references/template-contract.md) | 正式交付前读取 [contest-rules-2026.md](references/contest-rules-2026.md) |
| 设计模型改进 | [model-innovation.md](references/model-innovation.md) | 与当前模型动作最相近的论文卡 |
| 审稿、编译和交付 | [quality-gates.md](references/quality-gates.md) | `scripts/audit_manuscript.py`、`scripts/audit_math_semantics.py`、`scripts/audit_repro_manifest.py`、`scripts/audit_style_retrieval_plan.py`；发生学术改写时再读 [single-pass-rewrite.md](references/single-pass-rewrite.md) |
| 用陌生题检验 Skill 或在整稿大改后复核 | [blind-test-abc-protocol.md](references/blind-test-abc-protocol.md) 以及当前题型对应的 [2019 A](references/blind-test-2019-cumcm-a.md)、[2018 B](references/blind-test-2018-cumcm-b.md)、[2025 MCM C](references/blind-test-2025-mcm-c.md) 记录 | `scripts/test_longform_abc.py`、`scripts/audit_result_sync.py`；测试稿只提供前向测试门，不作为获奖论文文风样本 |
| 更新语料 | [evidence-updates.md](references/evidence-updates.md)、`scripts/audit_style_corpus.py` | [corpus-index.md](references/corpus-index.md)、[language-coverage-audit-20260813.md](references/language-coverage-audit-20260813.md) |

只有需要核对原页措辞、证据编号或详细边界时才读取 `human-style.md` 的相应材料；它是证据库，不是每次生成都要整体注入的系统提示。`fulltext-style-index.jsonl` 是 59 篇全文的段落级语言记忆，`fulltext-language-usage.md` 说明怎样迁移，`query_style_patterns.py` 是默认检索入口。`language-patterns-59.md` 和论文卡保留作压缩索引，不能再代替正文段落检索。

## 核心规则 0--7

### 0. 人类行文

- 一节只选一个主范文动作，必要时再补一个不同功能的动作。不得把多篇论文的漂亮结构全部拼进同一段。
- 先写实际工作稿，再做学术化整理。保留“计算到这里才发现什么”“哪一项可直接得到”“哪一处必须回退或改口径”等局部判断；删除聊天口吻，不删除判断痕迹。
- 起草前先在草稿区完成 [建模推演工作台](references/modeling-workbench.md)：事实锚点怎样改变数学对象、当前路线怎样被约束、哪一处经受了边界或反例挑战、还缺什么证据。它要求充分的建模准备，但不要求输出或保存逐字的隐藏思维链，更不得把工作台字段翻成每问同一段选型话术。正式长稿还必须在扩写每问前通过 [分问推演预审](references/reasoning-preflight.md)：负责队员先确认一页以内的冻结来源、锚点、数学落点和路线；来源或路线一变，旧预审失效，先重审再写，不能等 25 页后补理由。
- 思考过程必须进入正文，而不只停留在工作台。对非直接列式、首次出现的模型、算法或求解器，先让读者看到本题的事实或现象如何变成变量、约束、方程性质、数据口径或局部矛盾，再落到模型或公式；不能写成“题目要求……，故采用某模型”。直接关系到公式、前问接口到新增量、试算异常到改口径，都可以成为不同形态的正文思考桥。
- 不统一段落长度、首句、因果顺序和收束句。公式密集处可以短，异常结果和方案取舍可以长；有的段落直接进入定义，有的从图表或前问结果起笔。
- 不要求每段同时出现依据、方法、结果、解释和边界。写到当前任务已经交代清楚便停止，不额外补一句“这说明模型有效”。
- 模型名由附近的题面结构、数据形态、方程性质、变量规模、现实后果或真实试算自然引出；没有比较过候选时不编造“经过比较”。
- 对问题一、问题二等每一问分别定位模型、算法或求解器的第一次出现；总“问题分析”写得充分，不能替代分问内部的前问接口、局部边界和求解依据。
- 允许题面关系直接列式，允许后问只用一两句说明沿用接口与新增量。不得为了展示思考过程，给每问补齐相同长度的选型故事。
- 允许有限结论和未解决项，如“这里只排除了线性关系”“当前数据还不能区分两种机制”。不把局部检查扩写成全面验证。
- 不用故意错字、随机口语、假装犹豫、伪造第一人称经历或检测器对抗制造“人味”。
- 每次起草一个新章节前，必须从全文索引取回同题型、同功能的真实段落及相邻上下文；只读规则、不读正文样本时不得宣称已按获奖论文文风校准。
- 需要呈现中间判断时，从 [decision-moves.md](references/decision-moves.md) 中选择与当前证据真正相符的一两个动作，把判断放回触发它的数据、公式、边界、试算或结果附近。动作库只供内部选路，不得按编号、固定次序或同一连接词组写进各分问。
- 词法终检必须运行 `audit_lexical_corpus_calibration.py`。严格词库中跨至少 5 篇已核验论文出现的短语仍记录位置，但单次出现只作上下文复核；与普通结构病灶合并命中时不降级。不得把“更好”“可视化”“较强”等人类高覆盖短语机械清零，也不得因语料出现就忽略其空泛或重复使用。
- 跨分问终检不得只找完全相同的句子。`audit_reasoning_scaffold.py` 同时检查完全相同和动作序列相似度不低于 0.8 的重复骨架；至少三个分问、仍含有意义的选择/模型/求解链且占合格分问多数时进入复核。不要只增删一个“现象”或“解释”段掩盖同一流程，也不要为躲避审计故意打乱真实推导。
- `query_style_patterns.py` 默认排除 [style-benchmark-holdout.json](references/style-benchmark-holdout.json) 中封存的保留段落。只有运行其对应的 AIGC 盲测时才可显式使用 `--include-reserved-holdout`；不得把保留段落用于日常检索、提示调优或规则迭代。

### 1. 论文框架

- 正式稿通常采用摘要与关键词、问题重述、问题分析、模型假设、符号说明、分问题模型建立与求解、结果分析与模型检验、灵敏度/稳健性、模型评价与改进、AI 工具使用声明、参考文献、附录。
- 这是章节主干，不是段落句序。分问内部按证据出现的顺序穿插定义、推导、算法、结果和检查，不复制七个同名小标题。
- 篇幅参考 59 篇论文实测中位数和四分位范围，不按预造比例凑页数。篇幅应增加在变量口径、推导接口、约束来源、结果解释和检验边界上。
- 用户要求正式比赛长稿时，启用 25--30 页正文模式。正文页数从问题重述起算，到结论或模型评价结束；封面、摘要、目录、AI 声明、参考文献和附录不计。必须读取 [competition-longform.md](references/competition-longform.md)，编译后执行 `audit_competition_length.py` 与 `audit_content_density.py`。页数、逐问覆盖和内容密度三者必须分别复核；页数达标但靠重复段落、空白、表格堆叠或无信息扩写形成的长稿仍不合格。

### 2. 题型文风

- A 类突出机制、坐标、守恒、边界/初值、离散误差和局部几何；方法切换由方程性质、事件或精度要求触发。
- B 类突出决策变量、成本会计、硬软约束、状态转移、可行性、求解预算和同口径方案比较。
- B 类事件调度若存在并发设备，先定义各资源时钟、动作起止和占用关系，再写派工规则；产量、忙碌、等待和班末动作使用同一报告边界。目标值相同只说明该指标打平，不自动说明动作序列或策略等价。
- C 类突出样本单位、字段语义、清洗口径、训练/测试隔离、代理量、评价指标、预测到决策的接口和业务含义。
- 混合题按主导困难选择叙述重心，其他方法只作为子链。不要为显示全面而均匀介绍全部算法。

### 3. 建模与求解

- 写清变量、参数、目标或状态方程、约束、边界/初值、求解步骤、停止条件和输出，但允许它们分布在最相关的位置。
- 公式前写出关系从哪里来、为何必须转化为当前数学对象；公式后只解释新出现或容易误解的量，不逐式重复符号表。
- 真实发生的基线、失败试算、缩域、回退、换参和局部改模应保留；没有发生的过程不补写。
- 搜索窗口、最终回放窗口和统计尾窗必须显式区分并保持裁决口径一致。有限网格、有限规则集或固定预算只支持相应候选集内结论；参数微变触发离散事件切换时，报告相邻候选和触发对象，不把末位数写成连续物理精度。
- 同类方法边界必须与当前数据、变量域、规模或精度相连，不写算法百科。

### 4. 图表

- 图表先被正文提出，随后至少承担一个判断；标题写对象、条件和指标。
- 不要求每张表后都套“条件--读数--比较--原因--影响”。显然的读数可以一句带过，只展开改变模型、方案或结论的部分。
- 完整结果、坐标和日志放附录或支撑材料，主文只保留裁决所需的行列。

### 5. 结果与检验

- 结果解释优先写异常、拐点、约束活跃、方案切换和与预期不一致的地方；不逐格复述表格。
- 按真实证据命名回代、守恒检查、误差比较、交叉验证、基准对照、消融、重复随机或外部验证。它们不能互相冒充。
- 灵敏度说明扰动来源、范围、固定量、输出变化和决策是否切换；只有步长加密或一次重算时不写成全面稳健性。
- 评价与改进回到已识别的误差源、数据缺口和计算限制，不列通用优缺点。

### 6. 质量门

- 自动检查章节、占位符、标签、引用、模型空降、重复段首、固定理由链、过密连接词和过度整齐的段落节奏。
- 经 `$aigc-writing-router` 做正式候选审计时，还会比较不同分问的可见动作序列；只有三处及以上实质分段重复同一完整论证骨架才进入结构复核，不能用换模型名掩盖固定段式。
- MCM 长文发布时该结构复核还以独立 `public-reasoning-scaffold` 门执行；`academic-style-release` 内部的同名检查不能替代发布账本中的独立记录。
- warning 只提供复核线索，不能为了清零而在正文补造解释。先保事实，再处理语言。
- 正式稿编译至少两遍，核对公式、单位、摘要数字、图表、代码入口、随机协议和附件清单。
- 合规、编译成功和脚本通过不证明模型正确，也不证明文风自然；需由队员逐段朗读和复述模型。

### 7. 证据更新

- 新范文结论必须附论文编号、页码、证据片段、核验日期和适用范围。
- 区分稳定结构、题型倾向、单篇动作和未确认 OCR，不把单篇句式写成全语料惯用语。
- 当前语言记忆覆盖 59/59 篇、2892/2892 页。页级 OCR 经正文边界重建为 8293 个段落，7679 个非低质量段落进入全文模式统计，其中 2871 个标为高质量；再排除关键词、公式残片、未完整收束、异常拉丁串和已知 OCR 错词后，1632 个完整低噪声段落进入默认检索。448 个关键正文页另作 220 DPI 复识，362 页通过双门比较并替换，86 页保留原文本。详细统计见 `fulltext-style-stats.json`。公式、表格和小字号图注仍以原始栅格为准，OCR 段落不得用于核对数值或公式。

## 生成流程

### 1. 冻结事实

列出不可改的题面定义、公式、变量、数字、单位、图表、标签、引用和代码接口。缺证据的结论先不写。正式结果出现后，另存结果源哈希与正文关键字面量清单；分析脚本重跑时，旧清单哈希失效，必须重新核对摘要、正文、表格、结论和附录，不能只替换一处数字。

正式竞赛长稿还要建立逐问覆盖清单，记录每问的题面/数据入口、变量与口径、数学关系、求解实现、结果、解释、检验和边界，并为每问设置编译页码的起止标签及能定位正文块的标题正则。每个标签只能出现一次；各分问区间必须按清单顺序出现、位于正文起止标签之间且互不交叉或嵌套。清单用于发现缺口和统计实际页数、段落、公式、图表及结果解释，不得按八项顺序改写成八段正文。

冻结事实后、落笔正文前，为每一问建立 [建模推演工作台](references/modeling-workbench.md)。先把题面、数据、代码和结果归档到工作台目录并冻结 SHA-256；锚点和路线必须分别指向这些文件，不能只填来源文字。再把事实锚点翻译为数学落点并登记实际路线；对 25--30 页长稿，先由负责队员完成 [分问推演预审](references/reasoning-preflight.md)，没有 `approve` 不得扩写该问。首个非直接模型或算法不能早于全部本题节点：此前至少已有一个事实观察、前问接口、局部数学关系、有效试算或结果反推，另一个节点按真实推导放在需要处。直接列式、前问承接、试算回退和结果解释分别采用不同写法，不强行补候选比较，也不统一排成“锚点、转化、路线”三句。反向检查和尚未解决的边界只在确有实际作用时记录。工作台是内部建模底稿，不进论文，也不等同于公开判断账本。预审命令为：

~~~bash
python scripts/audit_reasoning_preflight.py <modeling-workbench.json> --approval <reasoning-preflight.json> --format text
~~~

初稿完成后执行：

~~~bash
python scripts/audit_modeling_workbench.py <main.tex> --workbench <modeling-workbench.json> --format text
~~~

正文稳定后执行全篇语料重合复核；未裁决的长字面量重合不得进入正式候选：

~~~bash
python scripts/audit_corpus_overlap.py <main.tex> --min-chars 20 --fail-on-overlap --format text
~~~

人工选定并冻结正式候选后，每问至少两名队员完成 [思考桥复述](references/reasoning-review.md)。它只确认正文没有偏离预审后的锚点、数学落点和路线；复述不进入论文，作用是做最终偏离检查而不是让模型生成另一份“思维链”或让队员重建整问：

~~~bash
python scripts/audit_reasoning_review.py <main.tex> --review <reasoning-review.json> --format text
~~~

正式竞赛长稿还要在草稿区维护一份 [公开判断账本](references/public-judgment-ledger.md)：它不是推演本身，而是写后检查每个有命名模型、算法或求解器的分问，是否已在正文中呈现了真实的局部依据及来源位置。账本只记录题面关系、数据、约束、前问接口、试算、结果或边界，不记录隐藏推理；它不进正文，也不授权补造候选比较。逐节 packet 还会把这些来源绑定的依据、数学变化和路线物化成 `public_judgment_contract`，供正文生成和候选审计使用；模型名不能代替这座桥，没有真实备选记录时不能写成“比较多种模型后选择”。起草后执行：

~~~bash
python scripts/audit_judgment_ledger.py <main.tex> --ledger <judgment-ledger.json> --workbench <modeling-workbench.json> --format text
~~~

题面关系直接列式而无命名方法的分问，在账本中声明 `direct_relation: true` 并记录相应关系即可。不得为了通过审计，把“核心困难/基线/候选/选择”重新写进论文。

### 2. 选择局部范文

先用 [fulltext-language-usage.md](references/fulltext-language-usage.md) 判断当前段属于哪种真实动作，再取回原段和相邻上下文：

~~~bash
python scripts/query_style_patterns.py --source fulltext --problem-type A --section analysis --query 缩域 --action choice --limit 5
~~~

完整读取返回的 3--8 个段落及其相邻段，观察事实入口、模型名位置、公式/图表接口和停止位置；若需要核对某篇完整判断轨迹，再以 `--source card --paper <编号>` 查询论文卡。优先匹配“当前段在做什么”，其次才匹配题型和算法名。检索计划会在与最高检索分相差不超过 2 分的已入选锚点中确定一个低复用主锚点；没有同等相关替代项时允许重复，不为了表面多样性引入不相干范文。查询无合适结果时直接按本题证据写，不硬套邻近动作。

长稿起草前必须把上述选择固化为按章节绑定的检索计划，避免生成器只看到几条脱离上下文的提示：

~~~bash
python scripts/prepare_style_retrieval_plan.py <main.tex> \\
  --problem-type A|B|C --output style-retrieval-plan.json \\
  --minimum 3 --limit 4 --context-window 1 --format text
~~~

计划中的每个可写章节至少绑定 3 个、最多 8 个已核验全文段落及相邻上下文，且至少来自 2 篇不同论文；它只提供事实入口、判断动作、公式/图表接口和收束位置的观察材料，不得复制原句、移植范文事实或把同一段落顺序套到所有分问。计划必须记录当前稿件哈希、全文索引哈希和盲测保留编号排除结果，并作为 `$mcm-cup-standard-write` 的阶段证据交回路由器。没有通过该计划时，仍可按题面和结果写作，但不得声称已经完成语料风格接入。

检索计划、工作台和真人预审都通过后，再生成 [逐节写作底稿](references/section-authoring-brief.md)：

~~~bash
python scripts/prepare_section_authoring_brief.py <main.tex> --problem-type A|B|C \
  --style-plan style-retrieval-plan.json --workbench modeling-workbench.json \
  --preflight reasoning-preflight.json --output section-authoring-brief.json
~~~

正式起草前，为每个可写章节物化一份完整的逐节输入包。输入包把本题事实、已批准路线、当前章节原始 TeX、选定的获奖论文完整段落及其上下文、辅助段落和防搬运契约放在一起。语料先按章节职责、本题词项和模型接口取得高相关候选，再在有限分差内按论文来源、动作序列、开头、表面收束、最后一个段落动作、句群尺度及公式/图表接口选成写法组合；不把四段近义样本重复交给模型，也不为追求变化引入明显不相关段落。写某一节时必须完整读取对应的 `Txx.json`，以 `current_draft_tex` 为公式、图表、标签、引用和命令结构的权威，从真实证据允许的写法中选择一种段落运动；辅助样本只用于观察替代开头、动作次序、节奏和停止位置，禁止把多个样本的表面词句平均拼接。不能只看剥离公式后的 `current_draft`，也不能把输入包的字段顺序直接变成正文顺序。

~~~bash
python scripts/prepare_section_drafting_packets.py <main.tex> \
  --brief section-authoring-brief.json \\
  --style-plan style-retrieval-plan.json \\
  --output-dir section-drafting-packets --format text

python scripts/audit_section_drafting_packets.py <main.tex> \
  --brief section-authoring-brief.json \\
  --style-plan style-retrieval-plan.json \\
  --index section-drafting-packets/packet-index.json --format text
~~~

输入包审计证明材料是确定的、与来源绑定的，并为后续发布复核锁定每个章节文件。它不能证明模型确实读过输入包，也不能证明生成文字自然；写作者仍必须只依据本题材料落笔，队伍仍必须复核选定候选稿。

候选稿生成后，再建立逐节 usage receipt，把每个章节的冻结源哈希、输入包哈希、候选章节哈希和“保留/生成”处置绑定起来：

~~~bash
python scripts/prepare_section_drafting_usage.py <frozen-source.tex> <candidate.tex> \
  --packet-index section-drafting-packets/packet-index.json \
  --run-id <run-id> --author-kind model --output section-drafting-usage.json

python scripts/audit_section_drafting_usage.py <frozen-source.tex> <candidate.tex> \
  --packet-index section-drafting-packets/packet-index.json \
  --usage section-drafting-usage.json --format text
~~~

这份回执只记录公开的章节血缘和内容哈希，不要求、记录或暴露模型隐藏思维链；`consumption_proven` 必须保持为 `false`。它能发现候选章节漂移、包文件替换、目标章节缺失和虚假的保留/生成标记，但不能代替队员复述题面、代码和结果。

经 `$aigc-writing-router` 处理正式长稿时，先在候选生成前用 `run_longform_portfolio.py lock-generation` 锁定工作台、预审、检索计划、逐节底稿和 packet，并冻结当前 MCM 路由全部规则所有者的写作规则树；候选完成后才生成 usage receipt。两者不可倒置，也不能在候选写成后回填或重建预生成材料。发布门会同时核对候选前锁定哈希、写作规则树与候选后的逐节回执；规则树发生变化后旧候选只能保留为历史材料，不能继续进入当前发布。

底稿把问题一的事实与路线只交给问题一章节，把范文段落保留为只供观察的 ID、定位和不含原文的语言动作画像（主锚点、动作序列、开头/收束类型、公式/图表接口及篇幅分布）；摘要等全局章节可以读取全部已批准分问，但不要求逐问罗列。起草时必须去检索计划读完整范文上下文，却不得把范文事实或句子写入本题。底稿字段顺序不是正文顺序，不能翻译成“锚点—落点—路线—检验”的固定四段。

风格基准的新建 suite 还会写入 `writing_rule_snapshot`，锁定 `$aigc-writing-router`、`deai-academic-writing`、`deai-modeling-writing`、Humanize 词库、本 Skill 的全文统计和公开判断门。旧的 `BLIND_READY` 如果没有这份快照，只能标为 `historical-unbound`；它可以证明冻结文件未被替换，不能证明候选是在当前写作规则下生成的，也不能冒充真人盲评或质量放行。

### 3. 写工作稿

按实际求解顺序把对象、思考转折、公式、试算和结果写清楚，像队员向另一名队员解释已经做完的工作。模型名出现前，至少先写出该问独有的对象/现象，再写它如何改变变量、关系、约束、数据口径或求解任务；存在真实试算、候选取舍或前问接口时，把它们放在发生处。此稿允许轻重不均：关键转折展开，常规步骤压缩；允许一句短判断接在推导之后；不补开场金句和结尾总结。

动笔前按 [reasoning-before-model.md](references/reasoning-before-model.md) 在草稿区逐问定位前文接口、首个数学变化、数学落点、首次方法名和证据位置。未发生的项留空；该定位表不得直接改写成正文顺序。若首次方法名以前只有“问题复杂”“因素较多”或算法通用优点，先补题面/数据/公式/试算证据，证据不存在就收窄表述或询问队员。

### 4. 学术化

删除口语填充和重复自述，补齐必要符号、单位与引用。保留工作稿的事实顺序、局部取舍和长短差异，不把每段修成同一种“证据充分、边界完整”的标准答案。

### 5. 文风校准

按 [human-drafting.md](references/human-drafting.md) 检查：模板段式、段首重复、成组连接词、三项排比、每段必收束、过度解释、无代价的全面评价；再按 [reasoning-before-model.md](references/reasoning-before-model.md) 逐问检查模型首次出现。先删多余句，再考虑改写；不要用同义词轮换掩盖同一骨架。

若确需调用降 AI 或中文学术改写 Skill，只允许在证据稿完成后执行一次受保护改写。改写前冻结数学环境、TeX 命令、标签与引用、数字、单位、术语、结果字面量和章节层级；改写后逐项比对。若仍发现具体段落机械，回到该段触发它的题面事实、数据、公式、试算或前问接口做一次局部内容重写；这不是第二轮降 AI，不得再次把整段送入其他人文化工具。不得把 `humanize-academic-chinese`、`baibaiAIGC` 或同类工具连续叠加，也不得为了绕过检测器削弱限定条件或伪造思考过程。

长稿混有证据附录、代码索引或操作说明时，先用 `$aigc-writing-router` 的 `audit_voice_mode.py` 区分文体，再用 `audit_style_rhythm.py --mode auto` 只查研究正文。证据区的字段列表、操作区的步骤和正文中的真正并列项不因词项命中而改写；只对正文中的连续单项列表、标签卡片、重复段首、统一收束和等长段落串回到本题事实做局部修订。两只审计器的 `PASS` 不证明自然，`REVIEW` 也不是强制改写配额。

若同时使用本机 AIGC 组合器，内容稿、主编辑器、独立候选、只读复核器和文档工作台
必须各自留下 `aigc-role-receipt/v1`。内容阶段至少交接题面/数据事实表、建模工作台、
判断账本、模型代码结果对应和内容密度门；候选阶段还要交接候选哈希与场景硬门；复核器
绑定被审候选哈希；工作台绑定映射、Diff 或导出文件。只读 `SKILL.md`、完成准备任务或
得到一个检测分数不算角色完成。统一入口和命令见 `$aigc-writing-router` 的
`orchestrate_portfolio.py`；无法执行的工具必须用 `waive-role` 写明具体回退，不得伪装成
完整协同。

### 6. 审计与复现

~~~bash
python scripts/audit_manuscript.py <main.tex> --problem-type A --format text
~~~

候选 TeX 若位于独立审计目录，而 `.bib` 保留在已冻结的项目资源树中，追加可重复的
`--resource-root <project-root>`。审计器会解析 `\addbibresource`/`\bibliography` 的实际文件和
引用键；找不到资源或键仍为 error。`\keyword` 与 `\keywords` 均可作为类接口，明确标题为
“主要符号/符号说明”的符号表可不设 label，普通图表仍必须有 caption 与 label。

修复 error，人工裁决 warning；随后编译并回查代码、数字和附件。最终由队员回答三件事：这一段为什么在这里、这一选择依据什么、这个结论到哪里为止。回答不出时，继续补证据，不继续润色。

存在外部结果文件时，再建立并执行结果同步清单：

~~~bash
python scripts/audit_result_sync.py <main.tex> --manifest <result-manifest.json> --format text
~~~

该门只检查列入清单的结果源哈希和正文关键字面量，不替代全量复算。任一结果源哈希变化或关键数字缺失都先阻断交付；若结果源重跑但内容哈希不变，可保留原稿。

正式结果还要冻结运行元数据与产物血缘，并对关键数学接口建立显式契约：

~~~bash
python scripts/audit_repro_manifest.py <repro-manifest.json> --format text
python scripts/audit_math_semantics.py <main.tex> \
  --contract <math-contract.json> --format text
~~~

复现清单至少包含实际运行命令、Python/主要库版本、随机种子、生成时间、数据/清洗配置，以及题面或输入、分析脚本、关键中间结果、最终结果、图表和审计合同哈希。事件仿真还要独立复算报告边界内的时间会计，例如 `忙碌+等待=班次长度`。数学契约只列风险最高的符号、单位、目标方向、约束、代码映射与可独立复算量；通过不等于证明全模型正确。

若执行过一次受保护学术改写，再运行：

~~~bash
python scripts/audit_rewrite_contract.py <before.tex> <after.tex> \
  --terms <protected-terms.txt> --scene MODELING --format text
~~~

若该候选来自 Humanize inline run，并且 run 中对源稿继承的技术短语使用了精确位置 KEEP，
还要把同一 run 交给上层统一门：

~~~bash
python C:\Users\Lenovo\.codex\skills\AIGC\aigc-writing-router\scripts\audit_academic_candidate.py \
  <before.tex> <after.tex> --scene MODELING --humanize-run <run-dir> --format text
~~~

这只复用可重放、源稿已有且哈希一致的词汇处置，避免跨层重复裁决；它不清除语义 warning，
不提供人工文风放行，候选、词库或 run 任一漂移后立即失效。

否定、因果和结论力度 warning 会按 diff block 给出源/候选位置、上下文和
`finding_sha256`；不得用全局计数猜测实际变化。公式、数字、引用、目标与约束方向仍是不可豁免的
hard error。
位置级 KEEP、warning 接受决定、分问推演预审和完稿思考复述都必须声明 `reviewer_kind: human`；模型可以准备材料和预审意见，但不能清除发布阻断，也不能增加队员审批或复述人数。
较长 changed block 明显缩短并丢失多处公开判断线索时，`ARGUMENT_COMPRESSION_REVIEW`
同样要求逐段裁决。它不禁止精简；只有确认被删内容确属重复，且模型职责、条件、限制和结果
解释仍完整时才保留短版。

在 `MODELING` 场景下，同一审计还检查 source 中已经公开的观测/约束、数学变化、方法选择和
结果/限制节点。缺少任一已有节点或其具体连接时报告 `MODELING_JUDGMENT_CHAIN_LOSS`；
它是位置绑定的 `REVIEW/2`，要求回到题面、数据、公式或实际试算局部修订，不允许用固定
“问题—模型—结果”段式或空泛收束句补齐。

该门除公式、数字、单位、标题层级、TeX 命令、标签、引用和术语外，还硬性比较最小化/最大化及不等式方向；否定、因果标记和结论强度变化进入逐处人工复核。任何通过都只说明已列不变量未漂移，不证明模型或文风正确。

随后对混合长文运行结构级只读复核：

~~~powershell
python C:\Users\Lenovo\.codex\skills\AIGC\aigc-writing-router\scripts\audit_voice_mode.py <main.tex> --format text
python C:\Users\Lenovo\.codex\skills\AIGC\aigc-writing-router\scripts\audit_style_rhythm.py <main.tex> --mode auto --format text
~~~

先裁决文体误置，再裁决正文节奏；不能把两个报告的命中数相加为“AI 率”。修改后重新运行保护项和编译门，而不是继续叠加降 AI 工具。

正式竞赛长稿编译后再运行：

~~~bash
python scripts/audit_competition_length.py <main.tex> \
  --aux <build/main.aux> --coverage <coverage.json> \
  --min-pages 25 --max-pages 30 --format text
~~~

再检查逐问和全稿的内容密度：

~~~bash
python scripts/audit_content_density.py <main.tex> \
  --aux <build/main.aux> --coverage <coverage.json> \
  --problem-type A --format text
~~~

`--coverage` 存在时按冻结台账统计每问区间；没有台账时，审计器会从编译 AUX
中的顶层中文“问题一/第1问……模型建立与求解”标题和页码自动推断分问区间，
并明确标记为 `status=inferred`，不把推断结果冒充队员批准的覆盖证据。两种模式
都会给出每问页数、段落、公式、图表和结果解释。每问另有两套动作统计：
`action_distribution` 记录互斥的段落主功能及可加总篇幅，`action_evidence` 允许同一段同时
提供模型、求解、结果和检验证据。判断“有没有写到”看后者，判断篇幅重心看前者，禁止
因复合标题或一段多职而把其中一项误判为零；语料四分位只作软提示。

TeX 可在正文起止处写 `\label{mcm-body-start}` 与 `\label{mcm-body-end}`，每问另设唯一且互不重叠的起止标签；若模板未提供这些可选标签，`audit_content_density.py` 会退回识别标准 `\begin{document}`/`\end{document}`，并在报告中记录边界来源，不把普通可编译稿误报为缺正文。页数不足时只按覆盖清单补真实接口；页数超限时优先把完整代码、全量表格、中间日志和重复定义移到附录。内容密度报告中的语料四分位只作软性提示，不能据此机械配比。不得用 `\newpage`、空白、字号/行距放大、背景、题面复述或算法百科凑页。

单独运行审计器不构成验收，报告里的 `coverage` 字段决定这次结果能不能被引用。缺
`--aux` 时没有读任何页码，缺 `--coverage` 时没有核对逐问接口，缺 `--terms` 或
`--workbench` 时对应的术语与锚点检查同样没有发生；这些情况报告会给出
`coverage=partial` 与逐条 `[SKIPPED]`，此时即便 `errors=0` 也不得写成“该门通过”。
25--30 页模式的发布判断只以 `run_longform_portfolio.py run-gates` 的
`REQUIRED_RELEASE_GATES` 全集为准，它会补齐全部参数并在缺任一门时把状态记为
`GATES_FAILED`。以下三种叙述都属于流程错误：把 `coverage=partial` 的 `PASS` 当
门通过；把 `pages=null` 当页数达标；把跑过的少数门当成整份长稿的验收结论。

长文发布器还会自动记录 AIGC 路由器的 `voice-mode` 与 `style-rhythm` 两个只读审阅门。
它们把研究正文、证据清单和操作附录分开判断，发现正文卡片链或重复节奏时只生成
`review_only` 提醒，不把证据列表误判为 AI 腔，也不以文风信号替代事实、数学、复现和编译门。
处理方式是回到该段的题面事实、读数、公式或实际动作局部重写；不得叠加第二轮降 AI 工具。

使用 `$aigc-writing-router` 管理候选时，按 `SOURCE_FROZEN -> CANDIDATES_READY -> HUMAN_SELECTED -> GATES_PASS -> RELEASE_READY` 交付。进入 `HUMAN_SELECTED` 时必须一并锁定图片、参考文献、代码输入和本地 TeX 资源的路径、字节数与 SHA-256；目录外依赖必须先归档到候选目录。发布门必须针对人工选择的稿件及其锁定资源树运行，且包括预审、工作台对应、语料重合和队员偏离复述，不能审计冻结源稿后把另一个候选提交。TeX 主日志中的未定义引用、缺文件、缺字形和 Overfull 为硬失败；Underfull 与字体警告只记录，不替代 PDF 逐页查看。A/B/C 真实 25 页回归及 C 题失败对照见 [release-state-regression-20260815.md](references/release-state-regression-20260815.md)。`GATES_PASS` 仍需队员逐页核对标题、跨页表、公式、图注、参考文献、附录、溢出和乱码；只有带人工页面记录的 `RELEASE_READY` 才是组合层放行状态。

修改 Skill 的语言索引、标签或审计规则后，必须再运行：

~~~bash
python scripts/audit_style_corpus.py
python scripts/audit_lexical_corpus_calibration.py
python scripts/audit_cumcm_style_benchmark.py
python scripts/test_modeling_workbench.py
python scripts/test_corpus_overlap.py
python scripts/test_reasoning_review.py
python scripts/test_judgment_ledger.py
python scripts/test_audit_section_scope.py
python scripts/test_cumcm_style_benchmark.py
python scripts/test_lexical_corpus_calibration.py
python scripts/test_competition_length.py
python scripts/test_content_density.py
python scripts/test_result_sync.py
python scripts/test_repro_manifest.py
python scripts/test_math_semantics.py
python scripts/test_rewrite_contract.py
python scripts/test_style_forward.py
python scripts/test_reasoning_preflight.py
python scripts/test_section_authoring_brief.py
python scripts/test_longform_abc.py
~~~

前者验证 59 篇证据、正文边界、复识采用关系和低噪声检索层可达；后者还读取 `forward-writing-calibration.md`，验证三个陌生题样稿中局部事实先于方法、段落节奏不被统一，并检查未连续复刻语料原句。两者通过只说明规则门禁闭合，不代替队员复核模型和文风。

## 不采用的做法

- 不把 `humanize-academic-chinese`、`baibaiAIGC` 或任何降 AI 工具的禁用词表直接叠在初稿生成上。需要润色时，先完成证据稿，只选一个工具做一次受保护、分段、最小化改写并逐式核对；同一段不进入第二轮降 AI 改写。仍显机械时，回到事实和推导做局部内容修订，再复核保护项，不重新启动降 AI 链。
- 不通过增加更多“推荐句”“万能段式”和固定检查顺序改善人类感。
- 不以检测器分数代替教师阅读、队员复述和模型复现。
