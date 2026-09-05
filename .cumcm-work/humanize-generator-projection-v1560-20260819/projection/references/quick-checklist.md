# Humanize 快速检查表

本表用于短文本和首次分诊。扫描候选不等于 AI 判定；语义、术语、引语和用户结构锁优先。
当前默认启用 `STRICT_CORPUS`：1417 条语料词项不是普通提示，而是 CLEAN 前必须逐处处置的严格候选。

## 目录

- [决策状态](#决策状态)
- [19 类快速分诊](#19-类快速分诊)
- [旧规则安全蒸馏抓手](#旧规则安全蒸馏抓手)
- [高风险豁免](#高风险豁免)
- [优先级](#优先级)
- [反修复模板](#反修复模板)
- [文件交付门](#文件交付门)

## 决策状态

| 状态 | 含义 |
|---|---|
| `KEEP` | 表达有实际功能，原样保留 |
| `DELETE` | 删除后信息不变且上下文自然 |
| `REWRITE` | 病灶明确，需改变句子或结构 |
| `REVIEW` | 需结合作者意图或上下文判断 |
| `NO_CHANGE` | strict 扫描为零且可编辑范围内无值得保留的安全改动；不证明原文自然或质量通过 |
| `UNRESOLVED` | 信息不足，不能安全决定 |

## 严格语料词项

`lexical-signals.json` 的 `strict_phrase_inventory` 含 1417 个词和词组，按 12 个意群写入
`LEX-STRICT-CORPUS-*` 信号。它们默认 `high/REWRITE`，单次命中也进入 finding：

单字根只作候选发现：1770 个单字根中 1167 个进入宽召回层；完整父词、CSV 内嵌子串和 1--3 字倒排根合并后审计 17670 个根，其中 4753 个进入完整家族扫描。683 个根至少发布一个搭配，4064 个经精确复计后拒绝，6 个截断或噪声根在复计前拒绝，未路由根为 0。最终库存只含 2--12 字词或完整搭配。不得把单字 `稳/准/清/强` 当作 literal ban；应扫描由它们追出的 `更稳/会更稳/这样更稳/更稳一点/更稳的说法/写法/做法` 等实际库存词项。`收紧` 这类可独立定位的双字动作词可以发布，其家族还包括 `继续收紧/进一步收紧/再收紧一点/口径收紧/同步收紧`。强发现根必须有发布、明确拒绝或人工复核去向；不能只凭总榜“零新增”宣布收敛。

- 过程播报、完成闭环、审计治理、范围边界；
- 否定纠偏、过渡路标、重点提示、学术包装；
- 论文自证、建议展望、确定性限定、助手邀请。

改写前先扫描 before，改写后再扫描 after。after 中每个非保护区命中必须 `DELETE/REWRITE`，
或使用 `SIGNAL_ID@LINE:COLUMN` / finding hash 给出具体专业功能 KEEP 理由。只要仍有未解释命中，
`NO_CHANGE` 和 `CLEAN` 均不可用；不能用同组词轮换、拆词或全局一句“属于术语”绕过。

## 19 类快速分诊

| ID | 找什么 | 只有何时才处理 | 常用动作 |
|---|---|---|---|
| `HUM-01` | 相邻段同构起句 | 形成批量槽位，不是单次自指 | 让独有对象进入部分首句 |
| `HUM-02` | 万能过渡复用 | 删除后关系仍清楚或窗口内过密 | 删除；用具体关系改写 |
| `HUM-03` | 假转折、假递进 | 两侧没有改变预期 | 直接并列或分段 |
| `HUM-04` | 每段同一完整流水线 | 不同职责仍被压成同构段 | 改段落职责，不换词 |
| `HUM-05` | 段句等长 | 信息本来不等权 | 按真实权重调节；等权内容不动 |
| `HUM-06` | 全文匀速 | 关键处与例行处解释量相同 | 关键处放慢，例行处回指 |
| `HUM-07` | 管理、营销、教练、编辑腔 | 词不是正式对象或原文术语 | 改回具体对象或删除 |
| `HUM-08` | 抽象评价和名词串 | 句子缺少具体动作且非标准术语 | 还原对象；不能还原则 REVIEW |
| `HUM-09` | 创新表演、空洞拔高 | 强调词替代具体差异 | 具体动作先行；不判断创新真假 |
| `HUM-10` | 公式、图表、步骤字幕 | 旁白没有新增解释 | 压缩例行旁白 |
| `HUM-11` | 强制总结、升华、展望 | 结尾没有新功能 | 删除或停在具体判断 |
| `HUM-12` | 全知、全覆盖、无留白 | 完整性来自自动填槽，不是体裁要求 | 删除低价值部件，不制造瑕疵 |
| `HUM-13` | 对称句和列表凑数 | 内容实际不等权 | 重项展开；正式等权列表 KEEP |
| `HUM-14` | 每段均等用力 | 作者已有可确认的主次 | 显示真实主次；不凭空制造重点 |
| `HUM-15` | 模态缓和堆叠 | 多个词重复限定同一命题 | 锁定认识强度后合并；不确定则 REVIEW |
| `HUM-16` | 修复语形成新模板 | 改后跨段重复“这里真正/只需”等 | 二次扫描并恢复作者自然承接 |
| `HUM-17` | 段落职责丢失 | 精炼后不再承担原有图表引介、量化问题、范围或分支说明 | 恢复职责；不能稳定改好则 `NO_CHANGE` |
| `HUM-18` | 论证层级被拆平 | 总论、细节、排除项或并列分支被切成同构短句 | 按关系重组；保留有功能的连接词 |
| `HUM-19` | 改后病句或搭配错位 | 主语在对举中切换、修饰语无着落、动宾不搭配 | 朗读回检；修不好回退原句 |

## 旧规则安全蒸馏抓手

下列旧定位项只产生上下文候选，不是禁词，也不使用“命中几处即失败”的旧式硬配额；这句话不适用于 `LEX-STRICT-CORPUS-*`：

| Signal | 找什么 | 默认保护 |
|---|---|---|
| `LEX-THEORY-OPEN-01` | 多段重复“依据/基于某理论”起笔 | 单次正常理论引入、定理/法规依据 |
| `LEX-CASE-CLOSE-01` | 多个案例段重复点题尾句 | 案例是正式对象或尾句新增具体差异 |
| `LEX-PASSIVE-ANALYSIS-01` | “该处理/设计体现了”批量推出抽象价值 | 明确标准、数据或测量依据 |
| `LEX-PROBLEM-SHELL-01` | “核心问题/挑战”报幕壳复用 | 直接给出证明、求解或测量任务 |
| `LEX-VAGUE-ATTRIBUTION-01` | 当前句中来源不可见的泛化归因 | 显式作者年份、文献编号和引文命令 |
| `LEX-COPULA-AVOID-01` | 载体、角色、作用壳在同段堆叠 | 明确变量、输入、边界条件等技术角色 |
| `LEX-ACADEMIC-PACKAGE-01` | 可跨主题复用的学术包装词成束出现 | 已写清方法分工或可观察结果 |
| `LEX-ENUM-01` | 三步、三维、三项结构为凑数而镜像 | 等权分类、算法、证明和规范步骤 |
| `LEX-PUNCT-DASH-01` | 同段破折号集中制造固定节拍 | 单次正常破折号、标题和引语 |
| `LEX-FORMAT-BOLD-01` | 正文加粗替代真实信息主次 | 单次重点、字段标签和表格表头 |

归因候选不得按普通套话删除。把“专家认为 X”改成“本文证实 X”改变了来源与结论主体，至少 `REVIEW`；把“结合问题背景和实验现象”改成“结合问题背景、实验现象和已有研究”同样是新增来源背景，至少 `REVIEW`。没有输入证据时不得补作者、年份、机构、引文、已有研究或相关文献。用户正要求改写该无来源归因句时，必须保留归因主体和模态，并登记 `UNRESOLVED_UNSOURCED_ATTRIBUTION`；只换“提升/提高”等外围词不代表归因病灶已经解决。

## 高风险豁免

普通信号默认 `KEEP/REVIEW`；strict 命中只有保护区自动 KEEP，正文术语必须位置级说明不可替代功能：

- 定义、命名、假设、观察、结果报告等言语行为；
- 定理条件、标准条款、正式分类和等权对照；
- “闭环控制、边界条件、约束方程、显示屏”等术语搭配；
- 真实证明链、算法不变量和规范步骤中的功能性平行；
- 直接引语、题干、法规、OCR、引用标题、代码、数学和 TeX 命令。

“保留公式和数字”还包括不根据已有结论自行补出新的区间端点、运算步骤、数值范围或单位。文风层只改作者的叙述，不把可推导内容写成新的数学结论。

保护“直接引语”是逐字保护完整跨度，不只是保留引语语义。原引号或书名号、内部标点、空格和嵌套 TeX 必须原样；更换中文单双引号也算保护区变化。

## 优先级

先处理 `Dominant` 跨段模板，再处理 `Recurring` 句壳，最后处理 `Local` 词项。一个位置只保留一个主病灶；次病灶只有在改变改写动作时才列出。

短句也要复扫改后全文。删除一个空重点壳后若仍有“具有重要意义、深刻揭示、全面提升、为后续检验提供线索、为理解该现象提供线索、涉及更深层机制”等 high 候选，必须继续改写、给具体 `KEEP` 理由，或保持 `REVIEW/UNRESOLVED`。单点删除不等于通过；同义换壳也不等于通过。

混合请求中，拒绝检测率、噪声或规避部分之后，剩余正文仍使用同一完成门。不要把“系统梳理/深入探讨/提供支撑”轮换成“由此形成认识/供后续参考”；能直接写“梳理对象、讨论机制”就直接写，信息不足则 `UNRESOLVED`。

`CLEAN` 不能原样带回未决 high span；摘要声明未决不能补救正文中的 high 残留。主张锁与 high 句壳无法同时满足时，改用 `UNRESOLVED + 最小 PATCH/ANNOTATED`，把安全改动和原样未决跨度分开，并声明 `requested_output=CLEAN; effective_output=PATCH`（逐处注释则为 ANNOTATED）。不得把降级后的 PATCH/ANNOTATED 标成 CLEAN。effective_output=PATCH 时必须给实际 hunk；不得把截短正文标成 PATCH，所有省略的 source span 都要显示 `DELETE_STYLE_SHELL/REWRITE/UNRESOLVED` 动作。模态强度保留不等于模态 marker 逐字保留；压缩重复 marker 必须如实说明。

先于教练腔删除检查源文内部张力。源文内部冲突不属于纯文风层的裁决权限；同一对象附近若同时出现“可以直接……”与“不能直接……”等正反许可，不判断哪一条主张正确，不得自行选择其中一条主张。两个冲突 span 都必须原样回显为 `UNRESOLVED`，请求 CLEAN 时改用 `requested_output=CLEAN; effective_output=PATCH`。`SPEECH_ACT_SOURCE_POLARITY_TENSION_SELECTED` 是共同词汇锚下的选择性删极告警，不是通用矛盾或学科正确性检测。

冲突降级 PATCH 还要记录 `patch_hunks_source_partition=NON_OVERLAPPING`。同一 source span 只能属于一个 patch hunk；短 PATCH 的 `REWRITE` 不超过 1200 UTF-8 bytes、不跨物理行且至多一个 `。！？!?` 句末边界，若有句末标点，其后只能是空白或闭合引号/括号；`REWRITE hunk 不得包住另一个 UNRESOLVED span`。先切出原样未决句，再分别处理它前后的安全句壳，不能用重叠大块制造“既改写又原样保留”的假补丁。

## 反修复模板

改后再次扫描以下句壳的跨段复用：

```text
这里真正…… / 这里只看…… / 只需……
其余……沿用…… / 不再展开…… / 直接……即可……
```

出现一次可以自然，批量复用必须 `REVIEW`。不要用新的统一口吻替换旧模板。

同时复查抽象路径壳：`实证/论证/分析闭环`，以及“某种关系由 A 出发，经 B，最终落到 C”。它们若只是把现有并列项包装成完整流程，应改回实际对象关系；若属于控制理论等正式术语则 `KEEP`。

## 成对质量门

扫描器和 validator 都不能证明改后比原文自然。提交候选前逐段做 A/B 复核：先说出原段落在做什么，再核对改后是否保留该职责和句间层级；最后检查主谓、动宾、修饰和对举两端。逐句问清改动对应哪个原病灶；“更正式、更书面、换个说法”，以及 `让 -> 使`、`造成 X 过多 -> 使过多 X 被 Y` 一类形式化轮换，不是独立收益。先局部回退无收益或新增硬被动的句子，仍不能稳定优于原文就恢复原段并标 `NO_CHANGE`。

统一验证器对 `REWRITE/NO_CHANGE` 都生成 hash-bound paired-quality request。模型 A/B 自检只能
重写、回退或否决；不能自签“每个改句都有收益”。`NO_CHANGE changes=[]` 也只证明没有字节变化，
不证明原文没有可行动病灶。没有可信外部复核链时，机械 PASS 候选仍为 `REVIEW/2`。

## 文件交付门

普通内联 `REWRITE/DRAFT` 不直接调用验证器，统一走带快照和发射绑定的主入口：

```powershell
python "$skillRoot\scripts\run_humanize_inline.py" run <before> <after> `
  --mode <REWRITE|DRAFT> --scene <SCENE> --document-format <markdown|tex> `
  --visible-output <BODY_ONLY|BODY_WITH_SUMMARY>
python "$skillRoot\scripts\run_humanize_inline.py" emit <run-dir> --format body
```

只有用户明确授权精确 live 模板字段的载荷措辞时，使用 `REWRITE` 并在 `run` 后追加
`--template-field-edit-scope <scope.json>`。scope 只接受 strict
`humanize-template-field-edit-scope/v1`：改前 source SHA、非空 `edits`、唯一 `line + label`、
`permission=PAYLOAD_ONLY` 和具体理由必须齐全。`DRAFT` 携带 scope 会在建立 run 工件前拒绝。
header 的缩进、label、全角/ASCII 冒号、位置和顺序永不可授权；职责、适用对象/范围、因果、否定或
断言力度漂移仍为 `REVIEW/2`，授权也不清除 paired-quality 门。

新记录使用 `run/v3 + invocation/v2 + verification/v3`。wrapper 在创建 run 目录前稳定读取 scope，
冻结 `artifacts/template-field-edit-scope.json`，并在 invocation、run artifacts 和 direct evidence v5
的 `inputs/template-field-edit-scope.json` 中绑定 scope SHA/size、source SHA、`PAYLOAD_ONLY` 与
`local_clearance_supported=false`；`emit` 会重验三处绑定及 evidence manifest。旧
`run/v2 + invocation/v1` 只读兼容，不接受 scope，也不能通过手改 schema 降级绕过 v3 检查。

`BODY_ONLY` 只隐藏审计展示，不跳过审计。先读取 `run` 返回的机械状态、顶层交付状态、退出码和
`run_dir`；机械层不是 `PASS` 时先按 `diagnostics` 中的错误码定点修复，不先通读整份验证 JSON，
且不得发射 CLEAN 正文。首轮只删有证据的纯句壳，保持标题、段界、数字、否定、模态和原有
言语行为谓词。最终正文必须逐字来自 `emit`，验证后任何
修改都必须重新建立 after 并重跑。验证器没有实际运行时只能记 `NOT_RUN/REVIEW/2`，不能用目测
替代，也不能输出 BODY_ONLY CLEAN 正文。

本地 `emit` 只能证明 stdout 与冻结 after 一致。需要比对调用方保存的可见响应文件时运行
`run_humanize_inline.py attest <run-dir> <caller-supplied-visible-file>`；其 PASS 不证明聊天传输、界面
渲染或文风质量，后二者保持 `NOT_EVALUATED`。

长文件或受控工件仍可直接调用统一验证器：

```powershell
python "$skillRoot\scripts\validate_humanize_output.py" <before> <after> --scene <SCENE> --format text
```

- `mechanical_validation_status=PASS`：硬不变量通过，无未接受言语行为 warning、未解释 high 候选或新增模板；它不是交付 PASS；
- `1=FAIL`：公式、数字、引语、代码、关键 TeX 命令等硬不变量变化；
- `2=REVIEW`：需要人工裁决，不得写 PASS；
- `paired_quality_review_status=PENDING_EXTERNAL_REVIEW`：request 已签发但质量未放行；当前正常
  `REWRITE/NO_CHANGE` 即使机械 PASS 也返回顶层 `REVIEW/2`；
- 改后可编辑正文中的正式术语等待复核 candidate 使用 `--keep-reason SIGNAL_ID[@LINE:COLUMN|@sha256:HASH]=至少六个汉字且说明具体表达功能的理由`；受保护或排除命中天然不进入 candidate 审计，不能也不需要用 KEEP 绑定；同 ID 多处 candidate 必须精确绑定；
- 言语行为 warning 首次出现时保存 JSON 中的 `warning_review_request.request_sha256` 和逐条 `warning_fingerprint`；本地 identity-free proposal 只使用 `--propose-warning-resolution WARNING_FINGERPRINT=具体处理建议 --warning-review-request-sha256 <REQUEST_SHA256>`；
- proposal 固定为 `UNVERIFIED_CALLER_PROPOSAL`，`reviewer_identifier_collected=false`、`identity_verified=false`、`review_clearance_granted=false`、`attestation_status=NOT_APPLICABLE`，warning 仍 pending，退出码仍为 `2`。旧 reviewer 字段/hash 必须拒绝且不回显；没有 proposal 时不得带 request hash，旧 request 不得跨 artifact、上下文或 policy 重放；
- 真正 `VERIFIED_HUMAN` 需要代理不可访问私钥的外部审批服务并验证签名与 request/artifact 绑定；当前本地 CLI 无此信任根。未接入时只能改稿消除 warning；硬错误始终不可降级；
- 检查后正文又有改动，原 PASS 立即失效并重跑。
