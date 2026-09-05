# 文风保留集基准

## 1. 用途与边界

本基准用于回答一个窄问题：同一场景下，某个编辑器在未参与规则调整的冻结文本上，是否仍得到更好的人工可见偏好。它不判断作者身份、不预测检测器，也不替代数学、事实、引用和领域审计。

基准把以下证据分开保存：

- 保护和语义门：候选是否可进入人评；
- 人工盲评：哪一段在自然度、判断轨迹、具体性、内容密度和语义忠实度上被选择；
- 失败条目：下一次应从段落组织、公开判断或限定条件哪个方向修正。

## 2. 开发集与保留集

一个 suite 只允许属于 `dev` 或 `holdout`，不能混用。

| 集合 | 可以做什么 | 不可以做什么 |
| --- | --- | --- |
| `dev` | 根据失败条目调整提示、参考资料或动作库，再建立新的开发版 | 把开发票数当作泛化结论 |
| `holdout` | 在规则冻结后生成三次候选并接受盲评 | 评分后追加候选、改规则、重排同一对来追求分数 |

每个案例每个提供者固定三次生成 trial。聚合时脚本拒绝开发集和保留集复用同一源文本。保留集还必须在 suite 中声明保管人和 release ID；`SCORED_HOLDOUT_SEALED` 后只能审计和汇总。

suite 必须区分两个目标：

| `benchmark_goal` | 源稿角色 | 合法决策 |
| --- | --- | --- |
| `preservation` | 已有人类判断痕迹的论文段落，测试是否被改坏 | `NO_CHANGE` 或 `REWRITE` |
| `improvement` | 真实机器初稿或明确存在结构病灶的工作稿 | 只能 `REWRITE` |

每次 generation envelope 都要显式记录 `authoring_decision=NO_CHANGE|REWRITE`。注册器执行 Unicode NFKC 规范化并折叠空白：`NO_CHANGE` 必须与源稿规范化后完全相同；`REWRITE` 必须达到最低可见字符变化量。`improvement` 不接受 `NO_CHANGE`。同一案例、同一提供者的多个 `REWRITE` trial 还要在规范化后保持实质差异；多个独立运行都选择 `NO_CHANGE` 则允许正文相同，因为这正是保真结论。换行、空格、编码或少量标点既不能冒充 `REWRITE`，也不能在 envelope 中隐去决策。manifest 的 `content_evidence` 保存目标、决策、规范化哈希、字符数、最低门槛和相似度，审计时从冻结文件重新计算。

每次登记还必须提交 `aigc-benchmark-generation/v1`。它绑定源稿和候选 SHA-256、原生运行报告的路径和哈希、唯一 `run_id` 以及当前写作规则包的 `writing_rule_snapshot`（路由、`deai-academic-writing`、四个场景内容 Skill、Humanize 词库、MCM 语料和公开判断门）。快照生成器还会读取当前 MCM TeX 路由，逐一核对场景编排、竞赛写作、模型完整性、主编辑、只读文风复核和工作台六类实际 provider；新增 provider 如果没有规则所有者映射或规则文件未进入快照，初始化直接失败。除显式列出的执行脚本外，五个核心 `SKILL.md` 直接链接且留在各自 Skill 目录内的规则文件会自动进入快照，避免新规则仅被文档引用却未绑定。本机 Humanize wrapper 不生成正文，因此由模型按 Skill 起草、再由 wrapper 验证和 emit 的记录必须写成 `execution.mode=model_authored_native_validated`，并明确 `native_generation_proven=false`；只有确有原生生成器时才使用 `native_executed`。`verify-candidate` 只能证明文件保护项，没有这份生成证据不能构成一次 trial。复制源稿或复用同一 `run_id` 会被拒绝。

真实初稿 `improvement` suite 默认声明 `required_generation_evidence=["stack_evaluation"]`。每个候选必须先写一份源绑定场景账本，并形成三角色证据链；这不是把三个 Skill 的词表混进一个提示，而是分别保存通用学术门、场景负责人判断和 Humanize 原生验证的工件：

```powershell
python scripts/audit_benchmark_owner_ledger.py owner-ledger.json `
  --source source.tex --candidate candidate.tex --document-type research `
  --format json --output owner-audit.json
python scripts/prepare_benchmark_stack.py --document-type research `
  --source source.tex --candidate candidate.tex `
  --candidate-verification candidate-verification.json `
  --owner-report owner-audit.json --output-dir stack-run --format text
python scripts/prepare_benchmark_generation.py --provider humanize-academic-chinese `
  --source source.tex --candidate candidate.tex --native-report native-run.json `
  --authoring-actor model --authoring-decision REWRITE `
  --stack-report stack-run\stack-report.json `
  --output benchmark-generation.json
```

场景账本字段随文体变化：`modeling` 要落到问题对象、数学变化、模型决定与保留结果；`course-notes` 要落到来源身份、教学职责、关键步骤与保留条件；`research` 要落到论断、证据边界、论断力度与保留对象。任何账本都不得存隐藏思维链、作者身份概率或检测分数。该证据只证明三个职责确实作用于这份源稿和候选，不证明改写更自然；自然度仍由匿名人工比较给出。

矩阵链还必须执行两类只读辅助职责。`AI_paper` 通过 `run_aigc_adapter.py --package AI_paper --action workbench-plan --document-type mcm` 每次运行建立一次工作台计划，锁定其实际选择的 MCM 能力，但它不生成候选、不重写正文、不替队伍选择版本。每个候选再通过 `humanize-main` 的 `audit` 适配器挂接 `ai-check` 诊断报告；当前适配器层级是 `ADAPTER_DIAGNOSTIC_ONLY`，它不提供作者身份结论、检测分数或候选选择。相关路径、哈希和禁止性 claims 会写入 `auxiliary/`、generation envelope 与最终链报告。只读职责未成功挂接时，候选不得登记为 `BLIND_READY`；“只在路由结果中列出 provider”不算执行证据。

## 3. Suite 定义

```json
{
  "schema": "aigc-style-benchmark-suite/v1",
  "suite_id": "cumcm-a-prose-holdout",
  "version": "2026-01",
  "split": "holdout",
  "benchmark_goal": "improvement",
  "providers": ["humanize-academic-chinese"],
  "required_trials": 3,
  "holdout_policy": {
    "curator": "未参与规则调优的保管人",
    "release_id": "mcm-style-v1"
  },
  "cases": [
    {
      "id": "event-switch",
      "scene": {
        "document_type": "mcm",
        "document_format": "plain",
        "scope": "document"
      },
      "source": "heldout/event-switch.txt",
      "challenge_tags": ["public-judgment", "specificity", "result-explanation"]
    }
  ]
}
```

案例应是一个完整且可独立比较的段落或小节，不要用单句禁用词替换题。`mcm` 案例宜覆盖：对象切换、边界条件、基线失效、反例、误差解释或结果限定。源码在 `init` 时复制并锁定哈希。

## 4. 运行顺序

```powershell
python scripts/run_style_benchmark.py init suite.json --output-dir benchmark-run

# 每一个案例、提供者和 trial 都各登记一次；候选先经过统一适配器 verify-candidate，
# 提交源绑定的 native generation envelope（含 NO_CHANGE/REWRITE 决策），并通过目标对应的内容门。
python scripts/run_style_benchmark.py register benchmark-run\benchmark-source-frozen.json --case-id event-switch --provider humanize-academic-chinese --trial 1 --candidate H1.txt --verification verify\candidate-verification.json --generation humanize-run\benchmark-generation.json --output benchmark-run\r01.json

# 三次候选齐全后生成匿名 packet、离线 review.html 和 review bundle。
python scripts/run_style_benchmark.py prepare benchmark-run\r03.json --seed 2026 --output benchmark-run\blind-ready.json
python scripts/render_style_benchmark_review.py audit benchmark-run\blind\review-bundle.json --format text
# 两名评审只打开 review.html，各自导出一份 CSV；先合并再正式评分。
python scripts/merge_style_benchmark_ratings.py benchmark-run\blind\evaluation-packet.json `
  ratings-R01.csv ratings-R02.csv --output benchmark-run\blind\ratings-merged.csv `
  --report benchmark-run\blind\ratings-merge.json
python scripts/run_style_benchmark.py probe benchmark-run\blind-ready.json model-ratings.csv --output benchmark-run\model-probe.json
python scripts/run_style_benchmark.py score benchmark-run\blind-ready.json `
  benchmark-run\blind\ratings-merged.csv --ratings-merge benchmark-run\blind\ratings-merge.json `
  --output benchmark-run\scored.json
```

`prepare` 将页面与 bundle 一并锁入 manifest；旧的 `BLIND_READY` 可运行 `package-review` 产生后继 manifest，不能覆盖历史文件。页面生成器升级后使用 `package-review --refresh` 生成带版本号的新页面和后继 manifest。bundle 审计按当前生成器逐字复算页面，并同时核对页面、packet 和评分模板哈希。manifest 还锁定 `aigc-blind-scoring/v2` 与评分器 SHA-256；评分器变化后旧 manifest 不能直接评分。`probe` 只接受 `rater_kind=model`，要求每对至少一条模型记录，并固定输出 `MODEL_PROBE_ONLY`；它不改 manifest 状态、不封存 holdout、不增加 `human_coverage`，也不能选稿。正式 `score` 强制验证 merge report，重新读取至少两份单人 CSV，并核对 packet、评审编号、合并行和哈希；每对还要有两份五维均有效的真人评分，`SKIP` 不计有效覆盖，每个维度形成严格多数。两人对立时追加第三位独立评审，不覆盖旧评分。

最后对多份已评分 suite 聚合：

```powershell
python scripts/run_style_benchmark.py aggregate dev-scored.json holdout-scored.json --output portfolio.json
```

## 5. 失败条目如何使用

失败条目不直接改稿。先按维度处理：

- `naturalness`：检查句群节奏、段落起落和重复连接，不增加统一套话；
- `judgment_trajectory`：补回可公开的证据、候选比较或边界裁决，不套八步结构；
- `specificity`：恢复变量、事件对象、阈值和适用条件；
- `content_density`：区分重复扩写与解释缺口；
- `semantic_fidelity`：直接丢弃候选，从冻结源重新写。

只有开发集的失败可用于更新文风资料。保留集的失败作为本版边界记录，留给下一版新规则验证，不可反向调本版规则。

## 6. 已封装的 CUMCM 回归基准

本 Skill 随附两份来自已核验 CUMCM 全文索引的套件定义：

- `references/benchmarks/cumcm-v1-dev.json`：A/B/C 各一段，用于开发期定位段落组织或公开判断的退化；
- `references/benchmarks/cumcm-v1-holdout.json`：A/B/C 各一段，规则冻结后才可登记候选并盲评。

每个案例在 suite 定义中保留论文编号、页码、全文索引记录号和来源位置。其源文本是原本已具备人类判断痕迹的段落，因此固定属于 `preservation`：它检验编辑器会不会把阈值、条件、试算、限定语和句群节奏改平，而不单独证明编辑器能把任意机器初稿提升到同一水平。评估“初稿是否真正改善”必须另建 `benchmark_goal=improvement` 的同题真实工作稿 `draft -> candidate` 套件，并由人工盲评。

从真实 TeX 初稿建立 development/holdout 时使用固定种子抽样器。它只按连续段落、标题分散、中文正文量和公式/环境排除选样，不读取质量标签；报告锁定整稿、抽样脚本、段落行号、标题、段落哈希和两个 suite：

```powershell
python scripts/prepare_draft_improvement_suite.py main.tex `
  --output-dir real-draft-suite --suite-prefix cumcm-real-draft `
  --version 2026-08 --seed 20260823 --dev-count 3 --holdout-count 3 `
  --curator 队长 --release-id cumcm-real-draft-v1 --document-type modeling
```

生成后先冻结规则，再只使用 development 结果调试；holdout 在本版规则中只生成候选和接受匿名评分，不将段落或反馈写回动作库。

同一规则版不能只验证数学建模场景。分别为 `modeling`、`course-notes`、`research` 建立上面的 3+3 套件，并把三份 build report、六份当前 manifest 和来源锁写入 `aigc-style-benchmark-matrix/v1`。矩阵审计会复算抽样脚本哈希、来源行、段落哈希、历史排除集、dev/holdout 不重叠、三次候选和 `stack_evaluation`：

```powershell
python scripts/audit_style_benchmark_matrix.py matrix.json --format text
```

本地开发夹具可以用一条命令执行完整责任链：初始化并冻结来源、生成同源的三个独立试写、逐个运行一次受保护 Humanize、按行列重放允许的源继承严格词项、执行候选保护核验、建立场景 owner 台账、挂接 `ai-check` 只读诊断和 `AI_paper` 工作台计划、构造三角色 stack、生成 source-bound envelope、登记三次 trial 并输出匿名页面：

```powershell
python scripts/run_matrix_dev_chain.py dev-suite.json `
  --output-dir dev-run --document-type modeling
```

该入口只接受 development suite；它不会读取或调参 holdout，也不会自动打分。任何未知严格词项、移动后伪装成源继承的 KEEP、公式/数字/论断力度漂移、非实质改写、角色证据缺失、辅助职责缺失或规则快照变化都会中止。完成状态仍是 `BLIND_READY` 与 `PENDING_EXTERNAL_REVIEW`，不是人类文风放行。

链报告落盘后还必须运行辅助职责审计；开发链和 holdout 链入口会自动执行同一硬门，也可以单独复算：

```powershell
python scripts/audit_auxiliary_roles.py chain-report.json --format text
```

该审计逐候选核对 `ai-check` 报告、`AI_paper` 工作台计划的文件存在性、SHA-256、适配器 schema、16 个嵌套能力清单和禁止性 claims。它只证明辅助证据没有漂移，不证明自然度、作者身份或检测结果。

规则和开发集冻结后，由主编辑器从同一 holdout 源分别形成三份独立候选，再把候选放入单独目录。候选入口只验证并登记，不生成、不修改正文，也不允许缺文件或额外文件：

```powershell
python scripts/run_matrix_holdout_chain.py holdout-suite.json `
  --candidate-dir holdout-candidates --output-dir holdout-run `
  --document-type modeling
```

三场景 dev/holdout 都到 `BLIND_READY` 后，使用实际 source、build report 和六份最终 manifest 建立总矩阵，再运行矩阵审计：

```powershell
python scripts/build_style_benchmark_matrix.py --root matrix-root --output matrix.json `
  --modeling-source modeling.tex --modeling-build modeling-build.json `
  --modeling-dev-manifest modeling-dev.json --modeling-holdout-manifest modeling-holdout.json `
  --course_notes-source course.tex --course_notes-build course-build.json `
  --course_notes-dev-manifest course-dev.json --course_notes-holdout-manifest course-holdout.json `
  --research-source research.tex --research-build research-build.json `
  --research-dev-manifest research-dev.json --research-holdout-manifest research-holdout.json
python scripts/audit_style_benchmark_matrix.py matrix.json --format text
```

矩阵的机械通过只产生 `HUMAN_RATINGS_PENDING`。保留集必须继续由至少两名真人在匿名页面上逐维评分，不能用模型 probe、词表命中率或路由器自审替代。

对源稿与候选逐行同构的长 TeX，可在规则冻结后使用 `scripts/sample_tex_blind_pairs.py`
按章节抽取真实 `draft -> candidate` 留出对，并用 `--exclude-spec` 排除开发期已经看过的行。
采样器不读质量标签，也不评分；它生成的是私有映射清单，仍须经过
`prepare_tex_blind_pairs.py`、匿名化和至少两名真人独立评分。该流程补充长文实战验证，
不替代上面的 A/B/C 三次候选回归套件。

正式 `score` 只接受 `rule_freshness=current-bound` 的新建 suite；缺少写作规则快照的历史 manifest 仍可做文件与评审传输审计，但会被拒绝进入正式评分或封存。旧活动清单因此不重写，只在审计中显示 `historical-unbound` 警告。

本机还登记了一份真实数学建模长稿的历史 `draft -> candidate` 留出集，共 10 对，覆盖摘要、
问题重述、模型建立、求解结果和稳健性讨论。该候选生成后规则文件已有演进，因此使用
`attach_legacy_blind_review.py` 只追加当前匿名评审页面，旧 seal、原 packet、抽样行和历史规则
哈希均不替换。其登记固定为 `historical_transport_only` 和
`current_release_validation=false`；可用于评估这份真实候选，不可证明当前版本已经通过实战盲评。

为保持保留集陌生，`mcm-cup-standard-write` 的默认全文检索已排除三条 holdout 记录。不要把套件原文、候选稿或评分反馈加入常规写作提示；只有准备盲评时才按下列命令读取：

```powershell
python scripts/run_style_benchmark.py init references/benchmarks/cumcm-v1-dev.json --output-dir <dev-run>
python scripts/run_style_benchmark.py init references/benchmarks/cumcm-v1-holdout.json --output-dir <holdout-run>
```

项目工作区的初始冻结清单位于 `.cumcm-work/aigc-style-benchmark/`。本机活动目录由 `$mcm-cup-standard-write` 的 `references/style-benchmark-runs.json` 登记，也可用环境变量 `CUMCM_STYLE_BENCHMARK_RUNS` 或 `--runs-root` 覆盖；路径登记不构成通过证据，审计器仍逐项核对 suite、候选、generation envelope、写作规则快照、评分协议快照、匿名 review bundle、真实长稿历史附录和源文本哈希。当前 dev 与 holdout 的活动 manifest 是历史创建的 `BLIND_READY`，尚未绑定这份规则快照，因此审计会明确标为 `historical-unbound`，不把它们冒充当前版本的生成验证；真实长稿已有 10 对匿名页面，但三者均尚无真人评分或正式质量结论。新建 suite 会自动绑定当前规则包。

每次移动段落、更新原文索引或重新初始化上述套件后，都执行 `$mcm-cup-standard-write` 提供的跨层审计。审计器会读取 `references/style-benchmark-runs.json` 的活动根和 manifest，默认核对当前 dev/holdout 的候选矩阵与 `BLIND_READY`/正式评分状态；也可用 `--runs-root` 或环境变量覆盖：

```powershell
python C:\Users\Lenovo\.codex\skills\mcm-cup-standard-write\scripts\audit_cumcm_style_benchmark.py --format text
```

它逐一核对原文、论文定位、索引行号、A/B/C 覆盖、开发/保留不重叠、保留检索排除、`SOURCE_FROZEN` 快照哈希、实质内容变化、trial 独立性、匿名页面 bundle、真实长稿附录和活动 manifest 的候选矩阵。文本输出把传输/结构审计与 `HUMAN_RATINGS_PENDING` 分开显示；审计通过不意味着候选稿自然，也不替代人工盲评。
