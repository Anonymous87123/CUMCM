---
name: aigc-writing-router
description: 统筹本机 AIGC 写作能力组合，按 CUMCM/数学建模、中文学术、英文通用学术、英文医学论文、课程笔记、一般中文、一般英文、只读文风复核和外部文档工作台分配完整职责。当用户说“调用 AIGC”“用 AIGC 改比赛论文”“降低初稿机器味”或同义表达时，对已给出的 CUMCM TeX 执行源冻结、内容优先改写、一次受保护语言候选、相对比较、质量门和 PDF 编译，不得只返回路由计划。也用于组合、选择、重组或审计多个去 AI/学术写作 Skill，以及同源候选、TeX/DOCX 保护、语义锚点复核和最终质量门。不得串联多轮改写，也不得把检测分数当作质量或作者身份结论。
---

# AIGC Writing Portfolio Router

正式 MCM 长稿的逐节 packet 还包含来源绑定的 `public_judgment_contract`。发布门会运行 `audit_section_judgment_bridges.py`，检查候选稿在命名模型前是否公开本题事实和数学变化，路线是否出现在依据之后，以及比较声明是否有真实记录的备选；这只审计可公开承担的判断，不要求或重建隐藏思维链。

正式学术候选还会实际执行 `audit_reasoning_scaffold.py`。它只比较三个及以上实质分段的可见动作序列；只有同一“依据/比较/建模/求解/结果”类骨架在多问中重复到足以形成结构性病灶时才进入 `REVIEW`。该门不把一次正常推导改成固定八步，也不替正文补造未发生的思考过程。
正式 MCM 长文的 `run_longform_portfolio.py run-gates` 还把这只审计器作为独立 `public-reasoning-scaffold` 门执行，并将其输入、脚本哈希和结果写入发布账本；它不只作为 `academic-style-release` 的内部子检查存在。

把本 Skill 作为能力组合的唯一入口。它负责冻结权威源、选择完整责任链、生成候选分支、接入只读复核器和组织最终门；它不亲自替代内容、语言或文档治理 Skill。

## 比赛初稿一句话模式

用户已经给出数学建模初稿并要求“调用 AIGC”时，完整读取
[competition-one-call.md](references/competition-one-call.md)，进入 `MCM_COMPETITION_REWRITE`。
这是执行请求：若代码或结果尚不存在且用户授权自行完成，先建模、写代码、实际运行并锁定
输入/输出；随后必须继续到独立候选 TeX、编译 PDF、源稿对照和未决项，不能在路由计划、
诊断分数或任务包处停下。源稿始终保留；候选没有具体收益或发生语义退化时回退原段，
不得为了显示 Skill 有效而强行改写。

比赛材料齐全时，先按 [material-first-competition.md](references/material-first-competition.md)
建立 `aigc-competition-evidence/v1` 台账。可执行入口为：

```powershell
python scripts/prepare_competition_evidence.py init --source main.tex `
  --output-dir evidence-run --problem-type A `
  --problem-file statement.pdf --data-dir data `
  --code-dir code --result-dir results --provenance provenance.json --copy
python scripts/prepare_competition_evidence.py attach-execution evidence-run\evidence-manifest.json `
  --repro-manifest repro.json --output evidence-run\evidence-executed.json
python scripts/prepare_competition_evidence.py audit evidence-run\evidence-executed.json `
  --require-materials --require-execution --format text
```

该台账把题面、数据、代码、结果和复现记录按 SHA-256 绑定；没有实际运行记录时只返回
`REVIEW`，不把“有代码文件”写成“已求解”。网络数据必须在 `provenance.json` 中记录
`source_url` 与获取日期。脚本不执行陌生代码，实际运行仍由建模阶段完成并交给
`audit_repro_manifest.py` 复核。

相对结构退化检查运行：

```powershell
python scripts/compare_style_revision.py source.tex candidate.tex --format text
```

该结果只用于比较同一源稿的结构信号。`IMPROVED` 不是作者身份或自然度证明，
`UNCHANGED/REVIEW` 也不能触发第二轮 Humanizer；需要回到具体段落事实和推导处理。

## 先生成组合计划

多工具任务先运行：

```powershell
python scripts/route_aigc_tools.py --document-type mcm --intent rewrite --document-format tex --format text
```

该 MCM TeX 默认路由会同时挂接 `$ai-check` 的只读证据报告和 AI_paper 的
`workbench-plan --document-type mcm`。两者只复核冻结候选：前者定位具体文风信号，
后者从 16 个内嵌单元中筛出 MCM 可用的结构、摘要、引文、图表和同行审阅能力；
都不能再生成一份串联候选，也不能代替主线程选稿。

需要独立复核时显式加入：

```powershell
python scripts/route_aigc_tools.py --document-type mcm --intent audit --document-format tex --requested-reviewer patina --format text
```

可用文档类型：`mcm`、`modeling`、`research`、`course-notes`、`academic-mixed`、`academic-en`、`medical-en`、`technical`、`general-en`、`general-zh`、`external-app`。

可用意图：`draft`、`generate`、`audit`、`rewrite`、`compare`。

不确定角色时完整读取 [portfolio-architecture.md](references/portfolio-architecture.md)。生成候选或接入外部应用时再完整读取 [workflow-contract.md](references/workflow-contract.md)。需要调用某个导入项目时，完整读取 [package-playbooks.md](references/package-playbooks.md) 中该项目的条目，并继续读取它自己的 `SKILL.md` 或原生说明。[stack-registry.json](references/stack-registry.json) 是 21 个目录的权威能力登记表；其中嵌套的 `SKILL.md` 与 AI_paper 的 `skill.json` 还必须逐项通过 [folder-utilization.json](references/folder-utilization.json) 的 29 单元目录审计。[role-contracts.json](references/role-contracts.json) 是逐包适用场景、完整交付物、必交证据、失败回退和禁止性结论的权威职责覆盖层；五个场景内容 Skill 的台账和交接证据见 [content-role-contracts.json](references/content-role-contracts.json)。

先检查所有项目的真实入口和离线边界：

```powershell
python scripts/inspect_aigc_capability.py --package all --format text
```

纯提示词 Skill、外部 API 和 GUI 项目统一通过适配器建立源哈希、保护区、候选返回与采用契约：

```powershell
python scripts/run_aigc_adapter.py --package PACKAGE --action prepare-candidate --source source.tex --output-dir run
python scripts/run_aigc_adapter.py --package PACKAGE --action verify-candidate --source source.tex --candidate candidate.tex --output-dir run\verify
```

查看“项目真正运行到哪一层”，使用分级实测，不把适配器可用等同于上游程序已执行：

```powershell
python scripts/test_native_integrations.py --execute-safe --format text
python scripts/audit_folder_utilization.py --format text
python scripts/test_folder_utilization.py
```

报告只允许使用 `native_executed`、`syntax_checked`、`prompt_contract`、`entrypoint_only` 和 `blocked` 五个等级。前一等级也只证明列出的离线命令实际运行，不证明联网生成器、GUI 或外部质量服务可用。
声明离线原生审计时必须同时给出 `native_audit_contract`。命令必须显式消费 `{source}`、保持
源文件哈希不变、成功退出并输出满足 required keys 的单一 JSON；测试还会在两份差异明显的
文本上比较 contract 指定字段的语义指纹。失败、超时、恒定输出、无效 JSON 或只打印成功字样
均不得记为 `native_executed`。

新增、移动或改造 AIGC 包后必须检查职责闭合，并实际执行每个包声明的全部离线角色接口：

```powershell
python scripts/audit_role_contracts.py --format text
python scripts/test_role_contracts.py
```

不得用“每包挑一个最容易通过的动作”代替完整角色验证。路由结果中的每个阶段均附带 `role_contract.completion_evidence`；本轮缺少这些证据时，该阶段不得写成已完成。

需要实际比较中文学术候选时，必须使用源绑定组合器，而不是只打印路由结果。默认只建立 H1；只有明确比较 Baibai 时才加入 `--candidate-provider baibai-aigc`：

```powershell
python scripts/orchestrate_portfolio.py init --source source.tex `
  --document-type research --document-format tex `
  --output-dir portfolio-run --candidate-provider humanize-academic-chinese `
  --candidate-provider baibai-aigc --reviewer patina --workbench AI_paper `
  --proxy prose-proxy.txt
python scripts/orchestrate_portfolio.py register portfolio-run `
  --provider humanize-academic-chinese --candidate candidate.tex
python scripts/orchestrate_portfolio.py attach-role portfolio-run `
  --role content-owner --provider deai-research-writing --artifact research-receipt.json
python scripts/orchestrate_portfolio.py attach-role portfolio-run `
  --role candidate --provider humanize-academic-chinese --artifact H1-receipt.json
python scripts/orchestrate_portfolio.py attach-role portfolio-run `
  --role reviewer --provider patina --artifact patina-receipt.json
python scripts/orchestrate_portfolio.py attach-role portfolio-run `
  --role workbench --provider AI_paper --artifact paper-receipt.json
python scripts/orchestrate_portfolio.py select portfolio-run `
  --accepted H1 --reviewer 队长 `
  --reason "保留条件和数值，比较对象与题面事实对应"
python scripts/orchestrate_portfolio.py status portfolio-run
```

组合器会冻结源稿，按显式参数建立 H1 (`humanize-academic-chinese`) 和可选 B1
(`baibai-aigc Round 1`) 分支，调用已登记的离线适配器，并把格式不兼容、未注册
Skill、缺少内容阶段证据和只读评审等待写入 `portfolio-plan.json`。H1/B1 必须各自记录
输入哈希，`parent_candidate` 必须为 `null`；任何候选都不能读取另一个候选继续改写。
对 TeX，Baibai 和 Patina 默认只能处理单独冻结的正文代理，不能把原始 TeX 静默送入
不支持 TeX 的包。`status` 不是完成命令：只有候选文件、候选门、内容阶段回执、复核回执、
工作台回执和人工选择都登记后，才允许进入组合级评估。H1 登记时会立即运行
`audit_academic_candidate.py`，不能先把带有 strict 命中或保护漂移的稿件登记成“候选通过”；
H1 回执中的 `native-run-report` 还必须指向可重新验证的 `humanize-inline-run/v2|v3`
`run.json`，或长文流程的 `finalization_metadata.json + rendered_manifest.csv`。组合器会重新执行
inline `emit` 或核对长文源快照—渲染候选哈希，不接受手写的 `native_executed` 字样。
统一回执格式为
`aigc-role-receipt/v1`，每个证据条目必须有文件路径和 SHA-256；缺少任何必交证据、硬门
或回执文件漂移都会阻断。能力不可用时只能使用 `waive-role` 写明具体回退原因，不能
把“准备任务”“已读 SKILL.md”或“扫描通过”计为完整协同。
回执中的证据还必须通过 `scripts/validate_role_evidence.py`：提示词型内容角色提交
`aigc-role-evidence/v1`，按 `evidence_type` 填写不同的非空记录，并把实际输入路径与
SHA-256 绑定到当前冻结源；普通 TXT、改名后的泛化 JSON 或空台账不能完成角色。MCM 的
建模工作台、分问预审、判断账本、内容密度和结构审计使用各自原生报告，报告写入实际
输入文件哈希；组合器同时核对工作台审计与预审引用同一份工作台。复核器与带候选核验的
工作台必须绑定 `candidate_id`、候选哈希和候选级报告。成功挂接会记录证据验证器版本与
脚本哈希；旧版回执或验证器变化后必须重新挂接，不能沿用历史 `complete`。
可用 `template-role` 生成待填回执，但模板本身永远不是完成证据；填完后必须由
`attach-role` 重新计算文件哈希并通过对应角色的完整交付物检查。
回执还必须包含 `execution.mode`、`execution.run_id`；内容角色列出实际读取的参考资料，
候选声明 `pass_count=1`，复核器和工作台声明真实原生/人工工作台层级。`template`、
`pending` 和 `detector_only` 不能作为通过模式。

没有 `portfolio-plan.json` 的分支状态、适配器报告和人工选择记录，不得在最终回答中
声称“多个 Skill 已协同完成”；“已读取 SKILL.md”或“路由列出 provider”不算执行证据。

## 五层职责

1. 组合入口：`$aigc-writing-router` 只做分流、冻结、契约和最终编排。
2. 场景与内容：`$mcm-cup-standard-write`、`$deai-modeling-writing`、`$deai-research-writing`、`$deai-course-notes` 对内容、证据和模型负责。
3. 主编辑器：中文学术用 `$humanize-academic-chinese`；英文通用学术用 `$academic-humanizer`；英文医学论文用 `$humanizer-medical-academic`；一般中文用 `$humanizer-zh`；一般英文用 `$humanizer`。
4. 独立候选与只读复核：`$baibai-aigc`、`$patina`、`$ai-check` 及显式通用编辑器只在适用场景完整运行自己的流程。
5. 文档工作台：FYADR、AI_paper 等只承担导入、映射、差异、人工复核、项目历史或导出，不自动裁决正文。

所谓完整运行，是调用该 Skill 自己的模式、必读资料、保护规则、输出契约和验证步骤；不得只摘取它的词表、评分公式或几条提示塞入另一个 Prompt。嵌套单元也不能只登记不调用：AI_paper 必须通过 `run_aigc_adapter.py --package AI_paper --action workbench-plan` 读取 16 个工作台能力；humanize-main 的 `ai-check`/英文子 Skill 和 humanizer 的 canonical entry 必须按目录声明为复核器或显式替代；Gank Trellis 的 10 个单元必须保持维护专用，不能流入论文候选链。

## CUMCM 与中文学术

固定主链（比赛材料先行）：

```text
deai-academic-writing
-> evidence-bundle -> mcm-cup-standard-write / deai-modeling-writing / deai-research-writing / deai-course-notes
-> humanize-academic-chinese
-> ai-check（只读文风证据）/ AI_paper MCM workbench-plan（只读结构与呈现复核）
-> 源冻结、建模推演工作台与分问预审门、语料重合复核、公开判断账本门、领域门、数学门、结果门、复现门、队内思考桥偏离复述、TeX 编译与页面复核
```

- CUMCM 必须由 `$mcm-cup-standard-write` 先完成事实锚点、数学落点和实际路线的建模推演。正文要让读者看见模型为何从本题材料中出现，但不规定“事实、数学转化、模型/公式”的唯一句序：事实观察、局部关系、前问接口、试算回退或结果异常中的任一真实节点都可以先行，方法名只不能空降在全部本题节点之前。25--30 页长稿还必须在扩写每问前由对应队员批准一页以内的来源、锚点、数学落点和路线；未批准不得生成该问长正文，来源或路线变化必须先重审。建模推演和预审均是内部工作底稿，不输出逐字隐藏思维链，也不把固定字段改写成机械选型段；反向检查只在实际需要时使用，不能取代正文思考过程。
- `research`/`academic-en` 的 TeX 在文风候选前必须运行 `audit_research_draft_readiness.py`。摘要或一级章节仍为空、存在 TODO/占位、重复标签、悬空内部引用、空贡献承诺或模板作者身份残留时，停在 `BLOCKED_CONTENT_INCOMPLETE`，回到研究问题、论证、实验或证明本身补齐；不得让 Humanize 把论文空壳润色成成稿。该门只判断是否具备进入改写的最低载体，不证明创新、数学或实验正确。
- 老师提供的未完成 IEEEtran 稿件只作为这一闸门的压力测试，具体解释见 [teacher-research-readiness.md](references/teacher-research-readiness.md)。它不是英文文风范文，也不提供可直接套用的句子。摘要、贡献、理论/方法、实验、分析和结论必须各自承担内容责任；示例作者、致谢、页眉、收稿日期、TODO、重复标签和悬空引用必须先清除。结构检查通过只表示可以进入一次受保护候选，不表示研究、数学、结果或作者身份已经得到证明。
- `$humanize-academic-chinese` 只在内容门通过后执行一次受保护候选流程。
- 受保护候选后若某个段落仍显机械，只回到该段的题面事实、数据、公式、试算或前问接口做局部内容修订，再运行保护项和语义审计；不把该段送入第二个降 AI 工具，也不重新启动整稿改写。
- 只有用户明确比较短授权段时，才让 `$baibai-aigc` 从同一冻结源产生 Round 1 候选；不得读取 Humanize 候选继续改。
- `$patina` 可作为只读复核器完整运行 audit/MPS/fidelity；面对 TeX 时只接收抽取后的正文代理，权威 TeX、公式和引用不进入它的改写流程。
- `$ai-check` 只给出带证据的文风信号报告，不判断作者身份，也不决定采用哪个候选。其上游
  `VERDICT`、`AI-EDITED FRACTION` 和“检测器会怎样判”字段在本路由中必须删除；九类信号、
  0--27 的定位负载、逐项原文证据、体裁校准和修订建议仍完整保留。适配报告写
  `SIGNAL LOAD` 与 `CALIBRATION`，不得把低负载改称“像人”或把高负载改称“AI”。

当长文同时包含研究正文、证据附录和操作手册，或一次受保护改写后仍有明显卡片式结构时，完整读取 [real-trial-lessons.md](references/real-trial-lessons.md)，先分文体，再查正文节奏：

```powershell
python scripts/audit_voice_mode.py candidate.tex --format text
python scripts/audit_style_rhythm.py candidate.tex --mode auto --format text
```

第一只审计器允许证据区保留文件、哈希和字段清单，也允许操作区保留命令式步骤，只定位研究正文中的单项列表链、标签卡片和列表支配。第二只默认只检查被识别为研究正文的段落，定位重复段首、统一收束、等长段落串、标签化短段和 `不是……而是……` 对举纠偏壳；后者在研究正文中单次出现也进入 `REVIEW`，定义性排他或约束表达只能登记位置级保留理由，不能由普通 PASS 吞掉。CUMCM 统一门另把 1417 条严格词库与 59 篇全文逐词复计：至少跨 5 篇出现且没有合并命中普通结构信号的短语保留为 `REVIEW_CONTEXT`，不因一个词硬阻断；所有位置和统计仍进入报告。两类审计均不得用于判断作者身份，不追求命中清零，也不把操作手册的“先、再、不要”改成学术套话。若 `REVIEW` 对应真实结构病灶，回到该段材料、读数、公式或实际动作做局部重写；不得启动第二个人文化工具。用户授权打破列表或标题结构时，严格字面不变量可以诚实降为 `REVIEW`，但数字、公式、引用、环境闭合、编译和逐页检查仍须重新执行。

正式长文执行 `run_longform_portfolio.py run-gates` 时，不能把源稿—候选比较器、词法扫描器、受保护契约、段落角色、语料检索和节奏审计分散成几个可忽略的提示。`--style-retrieval-plan`、`--authoring-brief`、`--drafting-packet-index` 与 `--drafting-usage` 都是 MCM 发布门的必填输入；`audit_style_retrieval_plan.py` 会绑定选定稿件完整 TeX 树哈希、59 篇全文索引哈希、盲测保留排除、章节角色和分问归属、每节 3--8 个全文锚点以及至少 2 篇不同论文的来源多样性。`audit_section_authoring_brief.py` 再把同一节的本题事实、数学落点、实际路线和真人预审与这些只供观察的语料 ID 绑定，禁止嵌入范文原文、移植范文事实或把工作台字段排成固定段式。逐节 drafting packet 则把当前节的完整本题材料、主锚段落与上下文、辅助段落和写作契约真正放进同一个模型输入文件；发布门锁定索引及每个 `Txx.json`，候选完成后再由 usage receipt 绑定源章节、packet 和候选章节哈希，但不声称已从外部证明模型实际阅读。`audit_academic_candidate.py` 会在同一个冻结候选上实际调用 Humanize 词法扫描、59 篇词法校准、`audit_rewrite_contract.py`、`audit_voice_mode.py`、`audit_style_rhythm.py`、公开判断脚手架和相对修订比较；脚手架同时比较完全相同与相似度不低于 0.8 的跨分问动作序列，不能靠增删一个过渡段逃过。正式长文的 `academic-style-release` 会显式传入 `--require-style-gain --packet-index ...`：候选既要无词法、保护项、语义和段落病灶，又必须相对源稿消除至少一项结构病灶，或者在同一来源绑定 packet 下修复原稿已有的模型空降、局部依据/数学变化缺失、无记录比较、结果观察与解释脱节、检验动作与结论脱节等问题；结果与检验收益只有在工作台预先登记来源绑定的 `interpretations` 或 check `result_terms` 时才成立，不能从候选成稿倒推。候选自身未通过相同 packet 审计时阻断。相同稿件、只换词或只挂接 packet 而没有修复时停在 `REVIEW/FAIL`，应回到具体材料和推导局部重写。该比较仍是来源绑定的相对信号，不把“改善”当成人类文风证明。脚本与词库哈希写入硬门；任一未处置候选、保护项漂移、语义力度警告或段落病灶都不能进入 `GATES_PASS`。候选选定前还必须由 `audit_portfolio_selection.py` 核对编排器的角色回执、原生运行记录、候选哈希和人工决定，消除“回执手填通过”以及发布门与选稿互相等待的循环。

工作台审计必须区分生成前后：`generation-input-lock` 对冻结初稿运行 `audit_modeling_workbench.py --phase preflight`，只验证来源、工作台结构和分问映射，允许初稿仍有本轮准备修复的模型空降或判断桥缺失；候选发布门运行 `--phase release`，才要求锚点、数学变化、路线、结果解释和已声明检查真正进入正文。不得在生成前调用 release 阶段形成“原稿必须先写好才能改”的循环，也不得在发布时沿用 preflight 阶段放过未落地内容。

词项位置保留和语义警告接受必须在 `academic-style-decisions.json` 中声明 `reviewer_kind: human`。模型可以生成预审意见和修订建议，但 `reviewer_kind: model` 或缺失该字段都保持 `REVIEW`，不能让同一个生成系统自审后把候选推进到 `GATES_PASS`。
长文 `select` 与 `finalize` 同样必须写入 `reviewer_kind: human`；模型可以准备盲评包、页面清单和差异报告，但不能伪造选择或逐页终审记录。
分问 `reasoning-preflight.json` 和完稿 `reasoning-review.json` 的每条记录也必须写入 `reviewer_kind: human`；模型记录不计入批准或两人复述覆盖。

`SCENE=MODELING` 时，受保护契约还会报告 `MODELING_JUDGMENT_CHAIN_LOSS`：source 中已有的
观测/约束、数学变化、方法选择或结果/限制节点在候选中消失时，统一门保持 `REVIEW`。该警告
只能通过恢复具体节点、回退原段或提交与精确 finding 绑定的人工裁决处理；不能用第二轮 Humanizer
或固定“问题—模型—结果”段式覆盖。

短文 Humanize 已对源稿继承的技术短语做过位置级 KEEP 时，统一门必须接收并重放同一 run，
不能要求队伍在另一份 decisions 文件中重复签字：

```powershell
python scripts/audit_academic_candidate.py source.tex candidate.tex --scene MODELING `
  --humanize-run <humanize-inline-run-v3-directory> --format text
```

该接口只接受单文件 `REWRITE`、场景一致、当前扫描器/词库哈希一致、before/after 哈希匹配且
`emit` 可重放的 run；KEEP 还必须精确绑定 `SIGNAL_ID@line:column` 和 finding hash，并且同一
`signal_id + phrase` 已在冻结源中出现不少于候选保留次数。它只清除该位置的 strict 词汇
finding，不是人工文风审批，也不能清除否定、因果、论断力度、公式、数字、TeX 或任何语义
warning。候选变一个字、run 交叉绑定、词库变化、源稿未出现该短语或存在未使用记录时均保持
`REVIEW`。

统一门允许在 `aigc-academic-style-decisions/v1` 中逐条处置 advisory semantic warning，但每条必须同时绑定源树 SHA-256、候选树 SHA-256、warning code 与按 diff block 生成的 `finding_sha256`，并记录具体理由和复核者。未使用、重复、漂移或指向 error 的决策均阻断；公式、数字、单位、引用、TeX、目标与约束方向任何 hard error 都不能通过决策豁免。该机械裁决不替代来源隐藏的成对质量复核。

统一审计还必须读取其 `recovery.route`。若为 `REBASE_FROM_FROZEN_SOURCE`，说明公式、数字、
单位、引用、TeX 或约束方向已经漂移；此时候选中的词法命中只作诊断，不得逐词修补，也不得把
该候选作为下一次 Humanize 输入。运行：

```powershell
python scripts/prepare_academic_recovery.py academic-style-audit.json `
  --scene MODELING --materialize-root recovery-run `
  --output recovery-plan.json --format json
```

恢复包会重新核对源稿、候选和审计哈希；提供 `--materialize-root` 时，它还会从冻结源稿实际
执行原生长文 prepare 和 committed scaffold，并写 `recovery-execution.json`。该状态只能是
`AUTHORING_REQUIRED` 或 `PREPARE_REVIEW`，不能冒充正文已改写。只有
`LOCAL_REPAIR_ON_CURRENT_CANDIDATE` 或
`SEMANTIC_REVIEW_ON_CURRENT_CANDIDATE` 才允许在当前候选上处理精确位置；每处改动都要回到
附近事实或推导，并重新运行同一保护门，不能启动第二个人文化工具。恢复包本身不改正文，也不
产生完成声明。

25--30 页比赛稿先建立完整 TeX 文件树台账，并在生成任何长正文或文风候选前完成分问预审：

```powershell
python scripts/prepare_style_retrieval_plan.py main.tex --problem-type A --output style-retrieval-plan.json --minimum 3 --limit 4 --context-window 1
python C:\Users\Lenovo\.codex\skills\mcm-cup-standard-write\scripts\audit_reasoning_preflight.py mcm-draft\modeling-workbench.json --approval mcm-draft\reasoning-preflight.json --format text
python C:\Users\Lenovo\.codex\skills\mcm-cup-standard-write\scripts\prepare_section_authoring_brief.py main.tex --problem-type A --style-plan style-retrieval-plan.json --workbench mcm-draft\modeling-workbench.json --preflight mcm-draft\reasoning-preflight.json --output mcm-draft\section-authoring-brief.json
python C:\Users\Lenovo\.codex\skills\mcm-cup-standard-write\scripts\prepare_section_drafting_packets.py main.tex --brief mcm-draft\section-authoring-brief.json --style-plan style-retrieval-plan.json --output-dir mcm-draft\section-drafting-packets
python scripts/run_longform_portfolio.py init main.tex --output-dir longform-run --document-type mcm --problem-type A --portfolio-plan portfolio-run\portfolio-plan.json --style-retrieval-plan style-retrieval-plan.json --authoring-brief mcm-draft\section-authoring-brief.json --drafting-packet-index mcm-draft\section-drafting-packets\packet-index.json --judgment-ledger mcm-draft\judgment-ledger.json
python scripts/run_longform_portfolio.py lock-generation longform-run\longform-manifest.json --workbench mcm-draft\modeling-workbench.json --preflight mcm-draft\reasoning-preflight.json --style-retrieval-plan style-retrieval-plan.json --authoring-brief mcm-draft\section-authoring-brief.json --drafting-packet-index mcm-draft\section-drafting-packets\packet-index.json
python scripts/run_longform_portfolio.py register longform-run\longform-manifest-generation-locked.json candidate\main.tex --provider humanize-academic-chinese --candidate-id H1
python C:\Users\Lenovo\.codex\skills\mcm-cup-standard-write\scripts\prepare_section_drafting_usage.py longform-run\source-tree\main.tex candidate\main.tex --packet-index mcm-draft\section-drafting-packets\packet-index.json --run-id mcm-draft-001 --author-kind model --output mcm-draft\section-drafting-usage.json
python scripts/run_longform_portfolio.py select longform-run\longform-manifest-H1.json --candidate-id H1 --reviewer 队长 --reviewer-kind human --reason "保留数学限定且段落衔接更清楚"
python scripts/run_longform_portfolio.py run-gates longform-run\longform-manifest-H1-selected.json --output-dir release-run --portfolio-plan portfolio-run\portfolio-plan.json --style-retrieval-plan style-retrieval-plan.json --authoring-brief mcm-draft\section-authoring-brief.json --drafting-packet-index mcm-draft\section-drafting-packets\packet-index.json --drafting-usage mcm-draft\section-drafting-usage.json --judgment-ledger mcm-draft\judgment-ledger.json --coverage coverage.json --math-contract math-contract.json --repro-manifest repro.json --result-manifest results.json --workbench mcm-draft\modeling-workbench.json --preflight mcm-draft\reasoning-preflight.json --reasoning-review mcm-draft\reasoning-review.json --evidence-bundle evidence-run\evidence-executed.json
```

`run-gates` 还必须接收 `--judgment-ledger mcm-draft\judgment-ledger.json`；发布器会在选定稿副本上实际执行 `audit_judgment_ledger.py --workbench mcm-draft\modeling-workbench.json`，要求账本依据 ID、类型、锚点术语和 `source_ids` 与当前工作台一致，并逐项覆盖正文中可明确识别的具体方法引入。缺失、漂移、来源绑定不一致、空降具体方法或未通过的账本不能进入 `GATES_PASS`。

初始化会冻结主文件及递归 `\input`/`\include` 文件，按标题记录段落、公式、标签、引用和哈希。完成 `init` 后，先在 `mcm-draft` 中归档题面、数据、代码和结果，填写工作台与预审；每问均为 `approve` 后运行 `lock-generation`。该命令会实际执行工作台、预审、检索计划、逐节底稿和 packet 五道门，锁定输入、脚本、日志及 packet 依赖快照；同时从当前 MCM 路由生成写作规则快照，覆盖场景编排、竞赛写作、模型完整性、主编辑、只读复核和工作台 provider，并逐文件保存源哈希与不可变副本。状态随后推进到 `GENERATION_INPUTS_LOCKED`；未经过该状态不能注册 MCM 候选。候选必须提供同构文件树；新增、缺失、复用权威章节或任一被引入章节发生保护项漂移，均不得采用。逐文件验证报告也记录 SHA-256，报告被改动后原采用记录失效。发布时五份预生成材料和写作规则树必须与候选前锁定哈希完全相同；规则在候选生成后变化就重建运行，不能把旧候选称作当前规则结果。

`select` 只记录人工决定，不按分数自动选稿；有两个以上机械通过候选时，必须提供覆盖这些候选 ID、每对至少两名评审者的 `--blind-score`。该 score 必须是 `aigc-blind-scoring/v2`，含 `effective_human_coverage`、逐维严格多数、`pairwise_exact_agreement` 和 merge report；只有由至少两份独立真人 CSV 重算通过的报告才能进入 `select`。选稿同时解析并锁定采用稿的完整编译资源树：图片、参考文献库、`lstinputlisting`/`inputminted` 代码、本地 `.cls`、`.sty`、`.bst` 以及递归 TeX 文件都会记录相对路径、字节数和 SHA-256；注释掉的依赖命令不计入资源树。资源必须归档在候选目录内，不能让 `../` 或动态路径把发布结果指向目录外。预审通过后生成的候选，在人工选定后先由至少两名队员填写 `reasoning-review.json`，只确认正文没有偏离预审中的思考桥，不在这一阶段重新为整问选路。随后 `run-gates` 先以 `evidence-bundle` 核验题面、数据、代码、结果及已通过的复现记录，再在发布副本上强制执行 `$mcm-cup-standard-write` 的预审、工作台、语料重合和队内偏离复述审计，最后执行论文结构、数学语义、结果同步、XeLaTeX 编译、25--30 页和内容密度等门，并锁定实际 Python 门脚本快照、输入、标准输出、PDF、AUX 与 TeX 主日志。另运行 `audit_judgment_ledger.py`，确认每个声明的方法均有本问可公开的题面、数据、约束、前问接口、试算或边界依据；该账本同样不进入正文。主日志中的未定义引用、缺文件、缺字形和 Overfull 作为硬失败；Underfull 与字体警告保留计数，交给逐页复核。门全部通过后仍不是提交状态，逐页看过 PDF 后再运行：

```powershell
python scripts/run_longform_portfolio.py finalize longform-run\longform-manifest-H1-selected-gated.json --reviewer 组员1 --reviewer-kind human --review-note "逐页检查完成" --checked title --checked cross-page-tables --checked formulas --checked captions --checked references --checked appendix --checked overflow-and-garbled-text
python scripts/run_longform_portfolio.py audit longform-run\longform-manifest-H1-selected-gated-release-ready.json --format text
```

只有 `RELEASE_READY` 可以作为组合层的最终放行状态。任一门失败、文件或报告哈希漂移、页面清单不全时都不能进入该状态。

## 英文学术

- `academic-en`：`$deai-research-writing` 对论断、证据、引用和版本负责，`$academic-humanizer` 完整执行 audit、rewrite、数字/方程/引用核对和 change report。
- `medical-en`：内容门同上，默认由 `$humanizer-medical-academic` 完整执行作者画像和两遍学术编辑；`$academic-humanizer` 仅作为显式替代。
- 英文医学 Skill 的作者画像不能迁移到中文论文、非医学论文或 CUMCM。

## 一般文本

- 一般中文默认由 `$humanizer-zh` 完整处理。需要候选池、局部评分和可见 repair 记录时，可显式选择 `$humanize-chinese-copy-lab`。
- 一般英文默认由 `$humanizer` 完整处理。需要不同完整流程时，可显式选择 `$humanizer-brandonwise`、`$humanizer-voice-profile`、`$humanize-english-editor` 或 `$patina`。
- 这些通用编辑器只能处理已有源稿，不得补造事实。含研究论断、数学、复杂 TeX、结果字面量或引用约束时，必须重新分流到学术/建模场景。
- 原文始终是候选；没有实质收益时保留原文。

## 导入项目的角色

新增 GitHub 项目按原生能力接入，但每一个都必须公开至少一个可执行的 `audit`、`candidate` 或 `workbench` 接口：

- 可调用 Skill：`academic-humanizer-main`、`humanizer_academic-main`、`patina-7.0.0`、`humanizer-main(brandonwise)`、`humanizer-skill-0.1.0`、`humanize-main`。它们使用唯一调用名，避免 `humanizer`/`humanize` 冲突。
- 人工工作台：AI-Cleaner、AI-content-detector、AI_paper、FYADR、BypassAIGC、GankAIGC、ai-humanizer、humanize-text。它们不能原生离线生成时，仍可执行离线审计、候选任务准备或工作台预检。
- 改造后的实现参考：`humanize-ai-main` 保留依赖注入、低置信变更过滤、变更轨迹和缓存，并通过统一适配器实际参与 audit/candidate/workbench 实验。
- 重建 Skill：`humanize-main(Tiany)` 已新增 `$humanize-tiany-candidate-lab` 和本地候选比较器，恢复同源候选、保护区、keep/discard 与 repair 证据；不声称恢复缺失的原生成器或 BGE 评分器。

外部黑盒 API、翻译链和检测导向项目的输出只能重新进入同源候选契约，不能覆盖权威稿。

## 候选契约

候选组合使用 `aigc-candidate-portfolio/v1`，并运行：

```powershell
python scripts/audit_candidate_portfolio.py <portfolio.json> --format text
```

硬规则：

1. 每个候选的输入哈希都等于冻结源哈希。
2. `parent_candidate` 必须为 `null`，单个候选只允许一次写作通过。
3. 中文学术比较最多为 Humanize H 与 Baibai B；其他场景按路由只生成一个显式候选。
4. 数字、TeX 命令、公式、引用键、标签和受保护术语必须通过机械核对。
5. TeX 候选还要核对最小化/最大化、等式/不等式方向；否定、因果标记和结论强度发生变化时必须逐处人工裁决。
6. 只有领域门、文档门和人工选择都通过，候选才可成为新基线。
7. 复核器报告和检测分数不能自动选稿。

需要比较源稿和候选，或两个同源候选时，使用来源隐藏的成对评审：

```powershell
python scripts/sample_tex_blind_pairs.py source.tex candidate.tex `
  --output-spec holdout-spec.json --total 12 --seed 20260818 `
  --exclude-spec development-spec.json --exclude-spec previous-holdout-spec.json
python scripts/prepare_tex_blind_pairs.py holdout-spec.json --output pairs.json
python scripts/blind_pair_evaluation.py prepare pairs.json --output-dir blind-run --seed 2026
# 浏览器直接打开 blind-run\review.html；两名评审独立导出各自 CSV。
python scripts/merge_style_benchmark_ratings.py blind-run\evaluation-packet.json `
  ratings-R01.csv ratings-R02.csv --output ratings-merged.csv `
  --report ratings-merge.json --format text
python scripts/seal_tex_blind_holdout.py --spec holdout-spec.json --pairs pairs.json `
  --key blind-run\evaluation-key.json --packet blind-run\evaluation-packet.json `
  --ratings-template blind-run\ratings-template.csv --review-page blind-run\review.html `
  --review-bundle blind-run\review-bundle.json --rule-file scripts\audit_academic_candidate.py `
  --release-id release-v1 --output holdout-seal.json
python scripts/audit_tex_blind_holdout.py holdout-seal.json --format text
python scripts/blind_pair_evaluation.py score blind-run\evaluation-key.json ratings-merged.csv `
  --merge-report ratings-merge.json --format text
```

历史 holdout 的候选生成规则若已经变化，不得拿当前规则重新封存旧候选。只升级匿名评审页面时使用：

```powershell
python scripts/attach_legacy_blind_review.py attach old-holdout-seal.json --output review-addendum.json
python scripts/attach_legacy_blind_review.py audit review-addendum.json --format text
```

附录继承并复核原 spec、pairs、key、packet 和空白模板，保留旧规则哈希及其当前漂移状态，固定
`current_release_validation=false`。它只证明评审传输层完整，不能把历史候选改称当前 Skill 版本结果。

自动采样器只按行是否改变、正文汉字量、章节和固定随机种子选段，不读取质量标签；它要求源稿与
候选逐行同构，并把源稿、候选和开发排除清单的 SHA-256 写入私有 spec。该 spec 只用于生成
匿名 packet，不得交给评审者。`prepare` 同时生成只嵌入 packet 的 `review.html` 和
`review-bundle.json`；bundle 锁定页面、packet 与空白评分表，页面漂移会被拒绝。两名评审分别
导出单人 CSV 后用合并器检查全对覆盖、唯一评审编号和 `rater_kind=human`。保留集一旦生成，
本版规则不得根据其评分回调；模型评分只能作为
开发探针，不能替代真人覆盖。

评审分别判断自然度、公开判断轨迹、具体性、内容密度和语义忠实度。正式比较每对至少两名独立评审者；映射键在评分冻结前不得交给评审者。评审键同时锁定原始 pairs 和匿名 packet 的哈希，packet 漂移时拒绝汇总。完整规则见 [human-blind-evaluation.md](references/human-blind-evaluation.md)。
评分行必须声明 `rater_kind=human|model`。模型探针只进入开发诊断，不能增加
`human_coverage`。单人 CSV 必须先由合并器生成持久化 merge report；正式 benchmark
`score` 会重新读取单人文件并核对 packet、评审编号、合并行和全部 SHA-256。`SKIP` 只保留
“无法判断”信息，不计 `effective_human_coverage`；每一对的
每个维度都要有至少两张有效真人票并形成严格多数。两名评审结论相反时不得改写原 CSV，须追加
第三位独立评审；报告保留 `pairwise_exact_agreement` 和逐维票数。只有
`formal_human_ready=true` 才能供选稿和发布门使用。
正式 benchmark manifest 与新建 TeX holdout seal 都必须记录
`scoring_protocol=aigc-blind-scoring/v2` 以及 `blind_pair_evaluation.py` 的 SHA-256；评分前若
脚本漂移，先建立后继 manifest 或新的 release，不能让同一 packet 静默改用另一套评分语义。

候选、阶段门和盲评完成后，用组合级清单确认这些证据确实属于当前源稿与候选：

```powershell
python scripts/prepare_stack_evaluation.py manifest --document-type mcm --document-format tex --source source.tex --candidate candidate.tex --candidate-id H1 --provider humanize-academic-chinese --candidate-verification candidate-verification.json --stage-evidence scene-owner.json --stage-evidence genre-owner.json --stage-evidence model-owner.json --output evaluation.json
python scripts/run_stack_evaluation.py evaluation.json --format text
```

没有锁定盲评与明确人工决定时，最高状态只能是 `MECHANICAL_PASS_HUMAN_PENDING`；有完整人工证据后才可到 `HUMAN_EVALUATED_PASS`。`detector_score`、作者身份概率、AIGC 率和所谓 human score 不得进入该清单。格式与状态含义见 [stack-evaluation.md](references/stack-evaluation.md)。

调整文风动作库、路由或候选策略后，不能只拿已经看过的段落验证。建立至少一个开发 suite 和一个独立保留 suite，每个案例、提供者均登记三次独立候选：

```powershell
python scripts/run_style_benchmark.py init suite-dev.json --output-dir benchmark-dev
python scripts/run_style_benchmark.py register benchmark-dev\benchmark-source-frozen.json --case-id case-id --provider humanize-academic-chinese --trial 1 --candidate H1.txt --verification verify\candidate-verification.json --generation humanize-run\benchmark-generation.json --output benchmark-dev\r01.json
python scripts/run_style_benchmark.py prepare benchmark-dev\r03.json --seed 2026 --output benchmark-dev\blind-ready.json
# prepare 自动把匿名离线评审页和 review bundle 锁入 manifest；旧运行只可追加后继 manifest：
python scripts/run_style_benchmark.py package-review benchmark-dev\blind-ready-legacy.json --output benchmark-dev\blind-ready-reviewed.json
# 生成器或页面逻辑升级后只能创建新工件与后继 manifest：
python scripts/run_style_benchmark.py package-review benchmark-dev\blind-ready-reviewed.json `
  --refresh --output benchmark-dev\blind-ready-review-v2.json
python scripts/merge_style_benchmark_ratings.py benchmark-dev\blind\evaluation-packet.json `
  ratings-R01.csv ratings-R02.csv --output benchmark-dev\blind\ratings-merged.csv `
  --report benchmark-dev\blind\ratings-merge.json
python scripts/run_style_benchmark.py score benchmark-dev\blind-ready.json `
  benchmark-dev\blind\ratings-merged.csv --ratings-merge benchmark-dev\blind\ratings-merge.json `
  --output benchmark-dev\scored.json
```

开发集失败可以用于下一版规则，保留集在评分后为 `SCORED_HOLDOUT_SEALED`，不得追加候选、重排同一对或反向调本版规则。每次 trial 还必须绑定 `aigc-benchmark-generation/v1`，记录源/候选哈希、原生运行报告、唯一 `run_id`、`authoring_decision=NO_CHANGE|REWRITE` 和 `writing_rule_snapshot`；对 `modeling`、`course-notes`、`research` 改进集还必须带 `stack_evaluation`，逐字绑定 `deai-academic-writing -> 场景负责人 -> humanize-academic-chinese` 三段真实工件。场景负责人账本分别记录模型选择与数学变化、教学来源与关键步骤、研究论断与证据边界；只列 provider 名称不算协同完成。写作快照锁定本路由、四个内容 Skill、Humanize 词库、MCM 全文统计、场景账本和跨场景矩阵审计器。Humanize wrapper 只验证和 emit，不生成正文，模型起草的 trial 必须显式标为 `model_authored_native_validated`，不能把验证运行说成原生生成。仅有 `verify-candidate` 不能算完整 trial。`preservation` 用于获奖论文等人类段落，允许有证据的 `NO_CHANGE`；`improvement` 用于真实机器初稿，只接受达到实质变化量的 `REWRITE`。多个 `REWRITE` trial 必须互有实质差异，多个独立运行均选择 `NO_CHANGE` 时正文可以相同。只换行、加空格、改编码、微调少量标点或隐去决策均不能冒充有效改写。`probe` 只接收 `rater_kind=model` 并输出 `MODEL_PROBE_ONLY`，不改变 manifest、不增加 `human_coverage`；正式 `score` 还要求 `rule_freshness=current-bound`，再从持久化 merge report 重算至少两份单人 CSV，验证 `effective_human_coverage`、严格多数和一致率。失败条目按 `naturalness`、公开判断轨迹、具体性、内容密度和语义忠实度分别处理；其中语义忠实度落败必须丢弃候选。完整定义、案例要求和聚合命令见 [style-benchmark.md](references/style-benchmark.md)。

对 CUMCM 文风改动，优先使用随附的 `references/benchmarks/cumcm-v1-dev.json` 与 `references/benchmarks/cumcm-v1-holdout.json`。前者只能发现对已有人类段落的破坏，后者只在规则冻结后盲评；两者都不允许作为“检测器通过”或“人类作者身份”的证据。其 holdout 段落已从 `$mcm-cup-standard-write` 的默认全文检索中排除，禁止反向将其用于提示调优。
要验证真实机器初稿是否改善，使用 [style-benchmark.md](references/style-benchmark.md) 的 `prepare_draft_improvement_suite.py` 固定种子抽取 `benchmark_goal=improvement` 的开发/保留套件；不能把 `preservation` 的获奖论文改写结果替代该证据。
本版发布还必须各保留一组 `modeling`、`course-notes`、`research` 的 3 段开发集和 3 段盲保留集，且每段有 3 个独立候选。用 `audit_style_benchmark_matrix.py` 统一检查来源、排除历史样本、dev/holdout 不重叠、规则当前绑定及三角色证据；矩阵链报告使用 `aigc-matrix-dev-chain/v2`，每个候选的 generation envelope 必须挂接 `ai-check` 的诊断哈希和 `AI_paper` 的 MCM 工作台计划哈希，且明确二者均不生成正文、不选稿。链报告落盘后还必须通过 `audit_auxiliary_roles.py` 的逐候选硬审计。机械通过后的状态仍是 `HUMAN_RATINGS_PENDING`，不能据此宣称自然度已经过真人认可。

## 外部工作台

- FYADR：长 DOCX/TXT 的源快照、正文映射、逐块复核和可恢复导出。
- AI_paper：人工语法、格式、批注、项目历史及 DOCX/LaTeX 导出工作区。
- AI-Cleaner：中文诊断实验室和 Diff 界面。
- AI-content-detector：英文 PDF 句级诊断和标注 PDF，仅作提示。
- GankAIGC：明确需要多用户、BYOK、项目历史或外部反馈时的部署工作台。
- BypassAIGC：旧两阶段流程的兼容/回归基线。
- ai-humanizer：Raycast/Rephrasy 黑盒演示，不处理权威稿。
- humanize-text：跨语言、多引擎研究基线，不处理 TeX 或事实密集稿。
- humanize-ai：关闭随机 Markov 后，作为逐项变更、低置信过滤和缓存实验工作台。
- humanize-main-Tiany：本地同源候选比较和 repair 证据工作台，不生成正文。

## 不可串联

- 不执行 `源稿 -> Humanize -> Baibai -> Patina rewrite -> AI-Cleaner -> Gank`。
- 不让通用 Humanizer 接管学术正确性、模型选择、公开判断轨迹或结果同步。
- 不把命中词数、句长方差、困惑度、MPS 或检测百分比合成为“人类度”。
- 不要求所有项目都处理同一份稿件。物尽其用是给每项能力完整且有边界的场景，不是堆叠工具数量。
- AIGC 目录只允许本路由器隐式调用；其余编辑器、复核器和候选实验室必须显式选择。运行 `scripts/audit_invocation_policy.py` 检查这一边界。

## 验证

在 Windows 中文区域设置下，`quick_validate.py` 可能沿用系统的 GBK 默认编码；为避免把 UTF-8 的中文 `SKILL.md` 误报成损坏，固定使用 UTF-8 模式调用 Skill 创建器的验证器：

```powershell
python -X utf8 C:\Users\Lenovo\.codex\skills\.system\skill-creator\scripts\quick_validate.py C:\Users\Lenovo\.codex\skills\AIGC\aigc-writing-router
```

```powershell
python scripts/audit_aigc_stack.py --format text
python scripts/audit_folder_utilization.py --format text
python scripts/test_folder_utilization.py
python scripts/audit_role_contracts.py --format text
python scripts/inspect_aigc_capability.py --package all --format text
python scripts/test_router.py
python scripts/test_academic_candidate.py
python scripts/test_source_bound_gain_flow.py
python scripts/test_academic_recovery.py
python scripts/test_humanize_long_preamble.py
python scripts/test_orchestrate_portfolio.py
python scripts/test_candidate_portfolio.py
python scripts/test_all_capabilities.py
python scripts/test_role_contracts.py
python scripts/test_role_evidence.py
python scripts/test_stack_evaluation.py
python scripts/test_style_benchmark.py
python scripts/test_benchmark_generation.py
python scripts/test_draft_improvement_suite.py
python scripts/test_benchmark_role_chain.py
python scripts/test_style_benchmark_matrix.py
python scripts/test_audit_auxiliary_roles.py
python scripts/test_research_draft_readiness.py
python scripts/test_voice_mode.py
python scripts/test_style_rhythm.py
python scripts/test_compare_style_revision.py
python scripts/test_competition_evidence.py
python scripts/test_longform_portfolio.py
python scripts/test_longform_release.py
python scripts/test_native_adapter_contract.py
python scripts/test_native_integrations.py --execute-safe
python scripts/test_json_cli_encoding.py
python scripts/test_blind_pair_evaluation.py
python scripts/test_style_benchmark_review.py
python scripts/test_attach_legacy_blind_review.py
python scripts/test_prepare_tex_blind_pairs.py
python scripts/test_sample_tex_blind_pairs.py
python scripts/test_seal_tex_blind_holdout.py
python scripts/test_audit_tex_blind_holdout.py
python scripts/audit_invocation_policy.py
```

最终报告列出场景负责人、内容负责人、主编辑器、候选来源、只读复核器、工作台、实际运行的门和仍需人工决定的项目。机械 PASS 不得写成人类作者证明、外部检测放行或学术正确性结论。
