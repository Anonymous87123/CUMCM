# 21 项能力执行手册

本手册回答四个问题：项目原本会做什么、怎样真实启动、断网时还能做什么、进入统一写作链后承担什么。所有检测、困惑度、重排分数和所谓 authenticity 只作为定位信号，不证明作者身份或学术质量。

## 统一适配接口

```powershell
# 查看原生入口、运行时和联网边界
python scripts/inspect_aigc_capability.py --package all --format text

# 只读审计
python scripts/run_aigc_adapter.py --package PACKAGE --action audit --source draft.txt --output-dir run

# 给纯提示词 Skill 或联网应用准备受保护候选任务
python scripts/run_aigc_adapter.py --package PACKAGE --action prepare-candidate --source draft.tex --output-dir run

# 外部工具返回候选后核对公式、数字、引用和标签
python scripts/run_aigc_adapter.py --package PACKAGE --action verify-candidate --source draft.tex --candidate candidate.tex --output-dir run\verify

# 生成真实入口、依赖、网络与采用规则清单
python scripts/run_aigc_adapter.py --package PACKAGE --action workbench-plan --source draft.txt --output-dir run
```

`prepare-candidate` 不伪造生成结果。它冻结源稿、生成保护区代理和原生调用契约；真正的 Skill、API 或 GUI 完整运行后，输出必须进入 `verify-candidate`。

组合器还要求每个实际承担角色的包提交 `aigc-role-receipt/v1`。回执中的
`evidence` 是“证据类型 -> 文件路径 + SHA-256”映射；内容 Skill 使用
`content-role-contracts.json` 的台账和门结果，候选使用候选哈希与硬门结果，复核器绑定
被审候选哈希，工作台绑定映射、Diff 或导出文件。只运行 `prepare-candidate`、只读
`SKILL.md`、只做语法检查或只得到检测分数，都不能填充完整回执。不可执行的项目必须在
组合器中写清 fallback，不能删掉其职责后继续宣称完成。
回执的 `execution.mode` 和 `execution.run_id` 还要说明真实执行层级；内容角色列出
`references_read`，候选固定 `pass_count=1`。`template`、`pending` 和 `detector_only`
只能留在待办或诊断记录中，不能被 `attach-role` 接受。

每项能力在组合中的完整交付物、必交证据、失败回退和禁止性结论以 [role-contracts.json](role-contracts.json) 为准。调用前从路由结果读取该阶段的 `role_contract`；不能只运行下面列出的一个入口便声称该项目已经履责。

原生接入证据另行分级：

```powershell
python scripts/test_native_integrations.py --execute-safe --format text
```

`native_executed` 才表示列出的离线命令实际返回成功；`syntax_checked` 只表示入口源码通过解释器/运行时语法检查，`prompt_contract` 只表示 Skill 契约可发现，`entrypoint_only` 只表示入口存在。GUI、服务端、联网 API 和需要密钥的生成流程不会在该测试中启动。

## 逐项职责

### 1. aigc-writing-router

- 原生入口：`python scripts/route_aigc_tools.py ...`。
- 完整职责：场景分流、源稿冻结、同源候选、只读复核、文档工作台、最终门、失败候选恢复路由和开发/保留集盲测编排。
- 离线接口：`audit`、`workbench-plan`。不写正文，不替代领域 Skill。
- 升级文风规则时：使用 `run_style_benchmark.py` 建立独立开发集和保留集，每案例三次候选；保留集评分后只允许审计和聚合。
- 候选保护项漂移时：用 `prepare_academic_recovery.py` 强制回到冻结源；只有保护契约通过的候选才生成位置绑定的局部修复项。

### 2. humanize-academic-chinese

- 原生入口：先运行 `scan_humanize_chinese.py`，再按 `SKILL.md` 生成 after 文件，最后运行 `run_humanize_inline.py run/emit/attest`。
- 完整职责：中文学术、数学建模与 TeX 长文的一次受保护编辑；保留命令、数学、代码、引用、数字和术语。
- 离线审计：`python scripts/scan_humanize_chinese.py INPUT --scene AUTO --format json`。组合层核对 JSON 字段、源文件未修改，并以两份不同输入的 findings/coverage 指纹确认命令确实读取正文。
- 适配：原生扫描只定位词法和句壳信号，不给作者身份或质量结论；生成候选前仍建立统一保护包，返回后再做组合层核验。

### 3. baibaiAIGC

- 原生入口：`python scripts/run_aigc_round.py DOC_ID 1 INPUT OUTPUT MANIFEST`。
- 完整职责：从同一冻结源生成保守的第二候选；只自动允许 Round 1。
- 依赖：完整生成需要 OpenAI-compatible API；dry-run 只验证分块。
- 适配：保护区代理补足其 prompt-only TeX 保护；CUMCM 正文只允许从冻结源独立产生 Round 1 候选，不能接着改 Humanize 候选，也不启用 Round 2；普通短文本若另有授权，仍须走其自身的非数学场景。

### 4. humanizer

- 原生形态：通用英文提示词 Skill；仓库只有包验证脚本，没有生成 CLI。
- 完整职责：普通英文 prose 的模式诊断和一次源稿约束编辑。
- 适配：`prepare-candidate` 把它从“几条提示”升级为带源哈希、保护区和返回核验的完整任务；学术、中文和 TeX 权威稿会被分流。

### 5. Humanizer-zh-main

- 原生形态：普通中文非学术提示词 Skill，完整保留其 33 类模式。
- 完整职责：博客、邮件、叙事和普通说明的诊断或一次候选编辑。
- 适配：使用保护任务包和 JSON 核验，不把其规则移植到论文；学术中文改走 `humanize-academic-chinese`。

### 6. academic-humanizer-main

- 原生形态：英文论文、学位论文、rebuttal 和 proposal 的完整提示词工作流。
- 完整职责：claim-evidence、venue/register、proposal feasibility、方程/数字/引用保留和 change report。
- 适配：使用候选任务包与机械核验；不能替代研究证据负责人，也不能转用于中文 CUMCM。

### 7. humanizer_academic-main

- 原生形态：英文医学稿的作者画像与两遍编辑工作流。
- 完整职责：医学术语、hedging、因果强度、Methods/Discussion 语体和 self-audit。
- 适配：作者画像必须显式确认或使用默认值；返回候选后核对数字、否定、单位、术语和引用，不把固定画像迁移到非医学文本。

### 8. patina-7.0.0

- 原生离线入口：`node bin/patina.js --lang zh --score --offline --format json --quiet input.txt`；联网/本地模型可用时另运行 `--audit`。Node 18+。
- 完整职责：中英日韩 pattern、semantic anchor、MPS/fidelity、diff 与 deterministic offline score。
- 离线接口：组合层 `audit --execute-native` 真正调用 deterministic `score --offline`；原生 `--audit` 仍需要 API key 或已登录的本地 CLI backend。TeX 只能给抽取后的正文代理，不能给权威 `.tex`。

### 9. humanizer-main(brandonwise)

- 原生入口：`node src/cli.js analyze --json -f draft.txt`，另有 report/suggest/stats/autofix、HTTP 与 MCP。
- 完整职责：完全本地的英文模式、词汇、burstiness、TTR、重复和可读性诊断。
- 适配：`audit --execute-native` 运行原生分析；autofix 只能生成候选，不能原地改 TeX、代码或学术权威稿。

### 10. humanizer-skill-0.1.0

- 原生形态：五种英文 voice profile 的纯提示词 Skill，支持 detect/rewrite/edit。
- 完整职责：普通英文的目标语气诊断和一次候选编辑。
- 适配：默认禁用原地 edit；任务包明确禁止虚构第一人称经历和观点，返回候选后再核验。

### 11. humanize-main

- 原生入口：`python humanize.py --text TEXT --output-root RUNS`；另含 `$ai-check` 和 `$humanize-english-editor`。
- 完整职责：普通中文沟通文案的候选池、repair、比较报告；`ai-check` 给逐项证据；英文子 Skill 做源稿约束编辑。
- 依赖：首次评分会建立运行时并下载 BGE reranker。该 logit 不是自然度或作者身份真值。
- 适配：学术/CUMCM 不进入其客服场景评分；本地审计可用，模型比较仅在原场景完整运行。

### 12. AI-Cleaner

- 原生入口：后端 `uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8000`，前端 `pnpm dev`。
- 完整职责：中文本地 NLP、启发式信号、best-of-N、结构化 diff、历史和可选 LLM 候选。
- 离线接口：`python backend/app/nlp/humanize_chinese/scripts/detect_cn.py INPUT --json --rule-only` 只运行纯 Python 本地诊断；完整 rewrite 需要 OpenAI 或 Anthropic API。
- 证据边界：组合层验证输入未修改、JSON keys 和跨输入内容指纹；score、level、困惑度或所谓 AI 风险只能定位复核范围，不能判断作者身份、决定候选或优化外部检测率。
- 适配：远程请求只接收受保护代理；数据库正文保存策略需在处理敏感稿前确认。

### 13. AI-content-detector-Humanizer-main

- 原生入口：`streamlit run main.py`。
- 完整职责：英文 PDF 句级分类与标注副本、英文文本候选、APA-like 引用占位。
- 依赖：HF 模型、NLTK 与 spaCy 首次联网下载；缓存齐全后可离线推理。
- 适配：作为 PDF 人工定位器，不把标签当作者判决；中文、公式、LaTeX 和数字必须由组合保护层处理。

### 14. AI_paper

- 原生入口：Windows 下 `python main.py`。
- 完整职责：人工写作工作区、批注、历史、引用格式、DOCX/LaTeX/TXT/PDF 导出和可选 API。
- 离线接口：编辑、历史、导入导出；联网才有模型编辑。
- 适配：先运行 `workbench-plan`；修正硬编码配置目录，损坏的 Skill JSON 逐个验证，导出稿重新核对公式、数字与引用。AI_paper 下的 16 个 `Management/skills_src/*/skill.json` 已纳入 `folder-utilization.json` 的树哈希；实际调用必须使用 `python scripts/run_aigc_adapter.py --package AI_paper --action workbench-plan --format json`，按当前场景选择摘要、提纲、论证、图表、引用或复核能力，不能把 16 个入口串成连续改写链，也不能让 research-only 单元替题面、代码或结果作决定。

### 15. BypassAIGC

- 原生入口：`cd package; python main.py`，FastAPI + React。
- 完整职责：旧版 polish/enhance 两阶段、会话和 DOCX 格式化，作为回归基线保留。
- 依赖：完整候选需 OpenAI-compatible API；本地数据库与文档处理可离线。
- 适配：两阶段输出都只能成为独立候选，不能自动覆盖源稿或以检测结果验收。

### 16. GankAIGC-2.1.0

- 原生入口：配置 PostgreSQL 后运行 `package/main.py`，或使用 Docker Compose。
- 完整职责：多用户、BYOK、队列、项目历史、PDF/DOCX/MD/TXT 解析与导出。
- 依赖：模型生成需 API；PDF 可依赖 MinerU；外部反馈可依赖浏览器和网络。
- 适配：用于明确的部署/协作实验；Zhuque 等外部反馈降为可选报告，不能决定正文。嵌套 `.agents/skills/` 的 10 个 Trellis 单元全部登记为 `maintenance-only`：它们可以维护 Gank 自身的规格、工作流和代码，但不参与中文论文生成、候选选择或 Humanize 后处理；目录审计会对任何把它们声明到 `mcm`/`modeling`/`research` 场景的改动直接报错。

### 17. fuck-your-ai-detection-rate-main (FYADR)

- 原生入口：Windows `start_web.bat -Install` 后 `start_web.bat`；或 `docker compose up -d --build`。
- 完整职责：长 DOCX/TXT 快照、正文映射、分块 diff、checkpoint、人工选择、历史和可恢复导出。
- 离线接口：除模型候选外的大部分文档治理能力均可离线。
- 适配：作为首选长 DOCX 工作台；现有公式、表格、参考文献和页眉页脚保护继续保留，TeX 仍需外部保护层。

### 18. ai-humanizer-main

- 原生入口：Raycast 中 `ray develop`，调用 Rephrasy 固定远程 API。
- 完整职责：快速剪贴板/表单候选实验。
- 阻断：无网络或 API key 时不能生成；原代码无公式、数字、引用保护且会记录响应。
- 适配：仍可离线准备脱敏、带哈希的候选任务；真正调用前必须去掉正文日志、增加 timeout/retry，敏感稿不得上传。
- 离线可达层：按 `package-lock.json` 安装依赖后，对 `src/index.tsx` 运行 TypeScript
  `transpileModule` 语法检查；该结果只把入口从“存在”提升为“可解析”，不表示 Raycast 或 Rephrasy 已执行。

### 19. humanize-text

- 原生入口：`python -m src.standard.pipeline --input input.txt --output output.txt --verbose`。
- 完整职责：多 provider、两次 LLM 加跨语言翻译的研究基线，并保留每一步轨迹。
- 阻断：LLM、Google 翻译和 Niutrans 均需网络；高 temperature 与跨语言链会引入语义漂移。
- 适配：只在非事实密集纯文本上作为对照候选；TeX、公式、引用和正式论文权威稿禁止进入原生链。

### 20. humanize-ai-main

- 原生入口：`pnpm dev` 后调用 `/api/transform`。
- 完整职责：转换管线、provider 注入、变更轨迹、缓存和低置信过滤的实现参考。
- 风险：英文 NLP/Datamuse、随机 Markov 和远程 Gemini/HF 不适合中文学术与结构化文本。
- 适配：升级为可执行 audit/candidate/workbench 参考接口；默认关闭随机 Markov，只返回逐项可拒绝的低风险候选变更。
- 离线可达层：按 `pnpm-lock.yaml` 安装依赖后，对转换服务与 API 入口运行 TypeScript
  `transpileModule` 语法检查；不启动 Next 服务，不把解析通过冒充远程 provider 已运行。

### 21. humanize-main(Tiany)

- 原始状态：下载内容只有 README、LICENSE 和 `.gitignore`，其宣称的运行时不存在。
- 新入口：`python scripts/compare_candidates.py SOURCE CANDIDATE... --format json`；新 Skill 名 `$humanize-tiany-candidate-lab`。
- 恢复能力：同源哈希、保护区核对、改动率、重复四元组、套语命中、keep/discard 人工复核顺序和 repair 证据。
- 边界：这是依据公开设计的独立重建，不声称恢复原 BGE/LLM 代码；不生成正文、不自动采用候选。

## 采用顺序

1. 路由器确定场景和唯一内容负责人。
2. 冻结源稿；每个编辑器从同一源稿独立生成至多一个候选。
3. 只读复核器完整运行自己的原生 audit，但不选稿。
4. 文档工作台只做映射、diff、人工操作和导出。
5. 机械保护、领域门、文档门和人工接受全部通过后，候选才成为新基线。

“物尽其用”不等于把 21 个项目依次改写同一篇稿。它表示每个项目都有一个真实、可执行、不会越权的接口，需要时完整调用；不适用的生成能力也通过适配器保留其审计、候选准备或工作台价值。
