# TeX、Markdown 与纯文本长文工作流

## 目录

1. 适用范围
2. 长文完成定义
3. 固定输入快照
4. 文件清单
5. TeX 感知解析
6. Markdown 感知解析
7. 来源角色保护
8. 文档单元清单
9. 分块预算
10. 重叠上下文
11. 场景与 Voice Profile
12. 覆盖账本
13. 分节编辑
14. Diff 与回滚
15. 合并与冲突
16. 幂等重跑
17. 编译与格式检查
18. 乱码与异常
19. 完成交付
20. 长文检查表

### 执行分支索引（不替代完整阅读）

- 所有长文：第 1-15、17-20 节；先冻结快照、角色、unit、覆盖和交付边界。
- `LIGHT/BALANCED`：重点执行第 13.1、14、14.3 节；不得借局部强度进入 STRUCTURAL 路径。
- `STRUCTURAL` 单 unit：另读第 13.2 节和 `structural-rewrite-contract.md`；实际移动保持结构语义待审。
- `STRUCTURAL + ADJACENT_PAIR`：另执行第 3.1、13.2、14.2 节的冻结 transaction、逐候选 disposition 与双 member 原子回滚。
- Voice、fresh second pass、`check_command`：分别执行第 11/14.3、16、17.3 节；不满足各自前置条件时保持 `NOT_RUN/REVIEW`。

## 1. 适用范围

在以下任一条件成立时使用本工作流：

- 单文件超过 1200 行；
- 可编辑作者正文超过 20000 个汉字；
- 文档包含 10 个以上一级或二级章节；
- TeX 文档通过 `\input` 或 `\include` 引用多个文件；
- 用户要求“全文”“整本”“所有章节”Humanize；
- 单次上下文无法连续阅读完整文档。

只处理文风、节奏、句式、模板和语态。`.txt` 按无标题的纯文本段落处理：空行是默认单元边界，
没有 TeX/Markdown 结构保护；数字、单位、引语、代码样式和用户锁定范围仍按统一验证器保护。
目录输入会递归纳入 `.txt`、`.md`、`.markdown`、`.tex`、`.ltx`，乱码文件记录后跳过，不中断其他文件。
不要在长文流程中加入内容审查。

## 2. 长文完成定义

先区分两个完成态：

- `coverage_completion_claim_allowed`：只证明快照、单元覆盖、局部保护和格式/编译门闭合；
- `humanize_completion_claim_allowed`：还必须证明 Voice 绑定、逐单元场景裁决、全文声线与跨块重复门、以及 fresh second-pass convergence。

只有后者为 true 时才声明“全文 Humanize 已完成”。在当前没有外部 paired-quality/结构语义审批
适配器的安装路径中，正常可交付态是 `publish_state=REVIEW_CANDIDATE`：它表示机械候选已组装、
但仍待外部复核，不是失败，也不是正式终稿。它至少要求：

- 输入文件均已进入固定快照；
- 每个文档单元均出现在 manifest；
- 每个可编辑单元均有覆盖状态；
- 所有可编辑 `author` 单元均为 `DONE` 或 `NO_CHANGE`，且不存在 `PENDING`、`IN_PROGRESS` 或 `UNRESOLVED`；
- 文件级不存在 `SKIPPED_GARBLED` 或 `CHANGED_AFTER_SNAPSHOT`；
- 每个修改单元均有 diff 和回滚依据；
- 重叠区没有重复编辑；
- TeX/Markdown 结构检查通过，或失败位置已明确报告；
- 同一输出重跑不再产生无意义措辞漂移。
- STRUCTURAL 的逐段 plan 机械门通过；若发生实际移动/合并，结构语义映射不能停在 `NOT_EVALUATED`。
- `ADJACENT_PAIR` inventory 中每个 `STX-*` 均有精确绑定的 `EXECUTED` 或 `DECLINED`
  disposition，不存在候选 `PENDING`；普通 unit `NO_CHANGE` 不替代这项覆盖。
- 每个可编辑 `REWRITE/NO_CHANGE` unit 都有 paired-quality request，且全部当前 request 已由可信外部
  复核链清除；机械 PASS、request 覆盖 PASS 和模型 second pass 都不能替代质量 clearance。
- 每个可编辑 unit 的 `rewrite_intent_coverage_status=PASS`：standalone unit 使用
  `humanize-unit-rewrite-bundle/v4` 并通过 authoring binding 与模板字段权限边界重放；transaction member 使用
  `humanize-structural-transaction-bundle/v3` 的 fragment `local_rewrite_intent` 与逐 fragment
  `template_field_edit_scope`。声明理由、冻结 source/evidence span 与实际局部 diff 双向覆盖，并有
  bundle/before/after/diff/request hash 证据；
  该 PASS 不证明理由真实、结构语义正确或读感收益成立。

<!-- GENERATOR_PROJECTION_CONTROL_BEGIN:SECOND_PASS_SUMMARY -->
fresh second pass 只证明同一能力投影在新回合中是否提出进一步改动。全部 fresh `NO_CHANGE`、第二遍
ledger 闭合和 rendered tree 一致时，只能形成 `second_pass_stability_status=CONVERGENCE_OBSERVED`；
它不证明第一遍优于原稿，也不能清除 paired-quality pending。当前没有可信外部质量复核链，因此
即使稳定性通过，`humanize_completion_claim_allowed` 仍必须为 false。这些门也不判断完整作者气质、
作者身份、学术正确性或外部隔离。
<!-- GENERATOR_PROJECTION_CONTROL_END:SECOND_PASS_SUMMARY -->

不要用抽样阅读支持“全文完成”。抽样只能用于预诊断和确定规则优先级。

## 3. 固定输入快照

在编辑前固定以下信息：

```yaml
snapshot_id:
created_at:
root:
files:
  - path:
    bytes:
    readable_bytes:
    encoding:
    sha256:
    modified_at:
```

按字节读取并计算 SHA-256。记录开始时可读长度。若活动文件在处理期间追加内容，不把新增字节混入本轮；将文件标为 `CHANGED_AFTER_SNAPSHOT`。

不要覆盖源文件来制造快照。优先使用副本、版本控制 diff 或独立 patch 记录。

### 3.1 使用准备器固定快照

没有作者样本、直接使用场景 DEFAULT：

```powershell
python "$skillRoot\scripts\prepare_humanize_long_document.py" <main.tex|document.md> `
  --output <empty-run-dir> `
  --scene <AUTO|GENERAL|COURSE|MODELING|RESEARCH> `
  --intensity <LIGHT|BALANCED|STRUCTURAL>
```

默认 `--structural-transaction-scope NONE`。只有用户明确授权同一文件、同一 heading 内相邻双 unit
原子结构事务时，才对 STRUCTURAL 追加：

```powershell
python "$skillRoot\scripts\prepare_humanize_long_document.py" <main.tex|document.md> `
  --output <empty-run-dir> `
  --scene <AUTO|GENERAL|COURSE|MODELING|RESEARCH> `
  --intensity STRUCTURAL `
  --structural-transaction-scope ADJACENT_PAIR
```

该参数不自动改变分块预算，也不把一个完整小节强拆成 pair；没有候选时 inventory 为 `EMPTY`。
确需更细分块时，显式调整 `--max-author-chars/--min-author-chars` 并生成全新快照，不能手改旧 run。合法范围为 `--max-author-chars >= 1000`、`--max-lines >= 50`、`--min-author-chars >= 0`；小于这些下限会在 prepare 前由 CLI 拒绝。

显式提交代码注册表产生的、零样本的确定性场景 DEFAULT：

```powershell
python "$skillRoot\scripts\prepare_humanize_long_document.py" <main.tex|document.md> `
  --output <empty-run-dir> `
  --scene <GENERAL|COURSE|MODELING|RESEARCH> `
  --intensity <LIGHT|BALANCED|STRUCTURAL> `
  --voice-profile <scene-default-profile.json> `
  --voice-profile-sha256 <64-lowercase-hex>
```

提交 PERSONAL，或 builder 由样本产生的证据绑定 DEFAULT：

```powershell
python "$skillRoot\scripts\prepare_humanize_long_document.py" <main.tex|document.md> `
  --output <empty-run-dir> `
  --scene <GENERAL|COURSE|MODELING|RESEARCH> `
  --intensity <LIGHT|BALANCED|STRUCTURAL> `
  --voice-profile <voice-profile.json> `
  --voice-profile-sha256 <64-lowercase-hex> `
  --voice-manifest <voice-manifest.json> `
  --voice-sample-spec <samples.spec.json> `
  --voice-allowed-root <sample-root>
```

supplied Profile 必须为 `validation_status=PASS`，且其 `binding_scene` 必须与本次
prepare 的有效绑定场景相同。`AUTO` 不接受单一 supplied Profile；它按完整 unit 独立路由，
并物化 `GENERAL/COURSE/MODELING/RESEARCH` 四个确定性 DEFAULT 及 Profile set。PERSONAL 与
证据绑定 DEFAULT 只能用于显式单场景；缺少上述任一证据参数时必须拒绝，不得退化成只校验
Profile 自哈希。

证据 manifest 使用 `humanize-voice-sample-manifest/v2`，并绑定冻结 sample spec 的
canonical SHA-256。finalize 不把可重算的 `prepare_integrity.json` 当成该绑定的替代品：
即使 spec 修改后重新封装，来源角色、场景或范围与 manifest 不一致仍须失败。

TeX 正文需要清理装饰性样式包装时，只有用户明确授权后才追加
`--editable-style-wrapper textbf`（也支持 `emph/textit`，可重复）。默认不传时仍保护全部命令；该参数只开放包装命令本身，不开放标题、引用、数学、标签或内部文字的语义改写。

准备器只读源文件，并在读取开始时固定字节长度。它先尝试 UTF-8/UTF-8-SIG，再尝试 GB18030；仍不可读的文件标 `SKIPPED_GARBLED`，不会阻断其他 include。输出目录必须为空，避免旧 manifest 与新快照混合。

固定产物：

| 文件/目录 | 用途 |
|---|---|
| `snapshot.json` | 输入长度、编码、SHA-256、修改时间和快照 ID |
| `source/` | 只读快照副本；作为回滚依据，不是编辑目标 |
| `file_manifest.csv` | seed、include 关系、缺失/乱码/变动状态 |
| `source_role_overrides.json` | strict caller scope override 的规范化请求、原请求 hash、逐文件 ID/快照 SHA-256 应用绑定与“非作者身份/质量证明”权限边界；未提交 override 时也生成空工件 |
| `units.jsonl` | 单元锚点、行范围、hash、owner 与初始状态 |
| `coverage_ledger.csv` | 初始覆盖账本；不得出现 `DONE` |
| `protected_spans.jsonl` | 保护区 ID、范围、理由、hash 与恢复内容 |
| `chunks/<unit_id>.json` | 带 `[[PROTECTED:...]]` 占位符的可编辑块 |
| `run_metadata.json` | 预算、状态回加、保护数、完成声明权限和闭集 policy snapshot |
| `voice_profile.json` | 显式单场景下已校验并按 canonical JSON 物化的 supplied 或场景 DEFAULT Profile |
| `voice_profile_set.json`、`voice_profiles/` | AUTO 下四场景 DEFAULT 的精确绑定、逐场景 Profile 与不可越权 claims |
| `scene_routing_policy.json` | 冻结的逐 unit 路由规则；finalizer 还会与当前安装 policy 比较并独立复算 |
| `structural_transaction_inventory.json` | 始终生成的 transaction 候选/禁用清单；绑定 scope、snapshot、pair、边界、chunk/inventory、Voice 与 policy |
| `prepare_integrity.json` | strict schema 2 完整性清单；按规范路径排序，绑定上述状态/结构文件、transaction inventory 与全部 chunk 的 SHA-256 和 bytes |

`run_metadata.json` 在准备阶段固定写 legacy prepare-only 字段 `completion_claim_allowed=false`，并冻结
`policy_snapshot` 与 `policy_snapshot_sha256`：其中包含 validator/保护检查/scanner/lexicon/report
extractor、prepare/finalizer、scene/Voice/negative-guard 实现和 Python runtime 的闭集 hash。finalizer
在读取场景、Voice 或 bundle 前先用当前安装面重建该 snapshot；缺字段、自哈希错误或任一 policy drift
均直接 `FAIL/1`，不能用重算 `prepare_integrity` 或旧 run metadata 继续消费旧候选。
终态不得读取该字段，只能读取 finalization metadata 的分层完成字段。准备成功只表示材料可进入改写，不表示任何正文已处理。若 `processable_editable_units=0`，准备状态必须为 `REVIEW`，并标记 `no_editable_scope=true`；仅有标题、公式、标签、引语或其他保护内容的文件不能进入“可处理长文”状态。

supplied Profile 必须同时提供文件与调用方 pin 的 `profile_sha256`；两者缺一、hash 非 64 位小写十六进制、自哈希无效或实际值不一致都属于全局配置失败。未提供 Profile 时，显式场景物化对应版本化 DEFAULT；`AUTO` 运行独立路由器并为每个 unit 绑定四场景 Profile set 中的对应 DEFAULT。路由 evidence 只记录 rule ID、计数和贡献，不导出命中正文；强信号平局固定 `AMBIGUOUS/UNRESOLVED`。逻辑文档 prior 沿 TeX include 根传播，但只有本 unit 已有同场景、局部最高的弱证据时才能补足阈值；零证据中性块、用途不明的共享标题保持 `GENERAL`。Profile 的 ID、revision、confidence、kind、source、hash 与 disclosure 必须同时进入 metadata、unit、chunk 和 ledger。

`finalize_humanize_long_document.py` 在读取任何终态前必须严格校验 schema 2
`prepare_integrity.json`。重复/未知字段、重复或非规范路径、`..`、非法 SHA、bytes 不一致、
artifact 集合或顺序漂移都必须失败。清单缺失、文件集合变化、`units.jsonl`、初始账本、protected
spans、snapshot、manifest、transaction inventory 或任一 chunk 被修改时，收尾直接失败，不发布
`rendered`、`rendered_partial` 或 `rendered_review`。完整性清单只是审计辅助，不是独立信任根：
收尾器还会从冻结 `source/` 副本、文件范围、预算、保护跨度和 canonical chunk 独立重建初始
units、账本、占位符恢复结果、`author_chars` 与 transaction inventory，并要求它们逐项相等。
即使攻击者同时修改台账/inventory 并重算封条，也不能伪造 DONE、扩大 pair scope 或替换
`STX-*`。终态只能由本次实际提交的 `REWRITE`/`NO_CHANGE`/transaction 和运行时验证产生。

同一个 `run-dir` 的 finalize 通过跨进程锁串行执行，共享 staging 目录不得并发清理或发布。
可选检查命令只在正文 staging 的一次性副本中运行；运行前后同时核对真实正文 staging、
待发布的 validation/diff 证据 staging 和其余 run 产物。任一文件被新增、删除或修改都使
编译门 `FAIL`，受污染证据不得发布。
空文件集或零可处理单元属于 `REVIEW`，不能把“没有待处理内容”解释为全文完成；只有
`finalization_metadata.json` 明确给出 `humanize_completion_claim_allowed=true`（兼容字段
`full_completion_claim_allowed=true`）才能对外声明全文 Humanize 完成。覆盖层单独读取
`coverage_completion_claim_allowed`。

每个 chunk 还包含 `context_before_unit/context_after_unit` 和最多 1200 字符的 `read_only_context_before/read_only_context_after`。这些字段只用于判断衔接，唯一 owner 仍是当前 `unit_id`；改写包只能提交当前 `masked_text`，不得把只读上下文复制进输出。

prepare 还对去掉自身 hash 字段后的 canonical chunk 计算 `chunk_binding_sha256`。该 hash 覆盖 unit 身份、原文 hash、masked text、保护 ID、只读上下文、场景与 Voice 绑定；它进入 chunk、unit 和 ledger。改写包必须回显它，不能只靠文件名指向当前单元。

## 4. 文件清单

递归追踪主文件中的本地引用：

- `\input{...}`；
- `\include{...}`；
- `\subfile{...}`；
- Markdown 相对链接中明确作为正文纳入的文件；
- 用户显式指定的附录和章节文件。

为每个文件记录：

| 字段 | 说明 |
|---|---|
| `file_id` | 稳定短 ID |
| `path` | 规范化绝对路径 |
| `parent` | 引用它的文件 |
| `include_order` | 文档展开顺序 |
| `encoding` | 实际读取编码 |
| `hash_before` | 快照哈希 |
| `role` | 主文件、章节、附录、模板或资产 |
| `editable` | 是否包含可编辑作者正文 |
| `status` | `PENDING/DONE/NO_CHANGE/SKIPPED/UNRESOLVED` |
| `source_role` | `AUTHOR_TEXT/GENERATED/UNRESOLVED` 文件级来源角色 |
| `source_role_evidence` | 规范 JSON：发现关系、有限 marker ID/行号/注释 hash、辅助路径段与 override ID；不保存拍脑袋结论 |
| `source_processing_status` | 是否进入 authoring queue；生成/未决来源固定保留快照但不形成普通 `PENDING` unit |

目录 seed 扫描仍排除构建目录、缓存、第三方模板和用户未纳入正文的备份文件；但 TeX 主文件通过
`input/include/subfile` 显式纳入的可读文件必须进入快照与输出闭包，不能因为路径含
`generated/build/autogen/dist` 就从 manifest 消失。文件级生成角色只接受有限 registry 中、位于真实
TeX 注释且不在 verbatim/opaque protected span 内的确定性标记；正文、命令参数、verbatim payload
或仅仅出现 `generated` 一词均不构成标记。路径段只是辅助信号：没有确定性 marker 或显式 override
时固定 `source_role=UNRESOLVED`、prepare `REVIEW`，并且不进入 authoring queue，不能直接猜成
`GENERATED` 后静默排除。

需要覆盖来源角色时显式传 `--source-role-overrides <json>`。输入必须是 strict
`humanize-source-role-overrides/v1`，每项只含 `path/source_role/reason`，role 只允许
`AUTHOR_TEXT/GENERATED`；相对路径相对 override 文件解析，规范路径必须唯一命中一个可读闭包文件。
prepare 把原请求 SHA-256、规范路径、理由、override ID 与实际 `file_id + snapshot_sha256` 写入
`source_role_overrides.json`，并在 manifest evidence 中回显 override ID。该 override 只改变本轮
authoring scope，不证明作者身份、来源真实性、学术正确性或质量；未知目标、重复路径、未知字段和
缺理由均硬失败。确定性生成文件以及 `GENERATED` override 文件保留 `source/` 副本和最终原样输出，
但不得形成普通 `PENDING` author unit。

## 5. TeX 感知解析

### 5.1 先识别结构，不按空行盲切

识别：

- `\part`、`\chapter`、`\section`、`\subsection`、`\subsubsection`；
- `\paragraph` 和 `\subparagraph`；
- `\begin{...}` / `\end{...}` 环境边界；
- 命令参数和可选参数；
- 注释行与转义百分号；
- `\input`、`\include` 和文件展开顺序；
- 行内与陈列数学边界；
- verbatim 类环境；
- `comment`、`filecontents`、`filecontents*` 等有限白名单内的不渲染环境。

标准主文件存在 `\begin{document}` 时，准备器必须在该命令后重新开始正文分区。命令之前的
前导区整体记为 `SKIPPED_PROTECTED`，其中的类选项、宏定义、页眉页脚和自定义标题接口均原样
保留；它们不得与摘要或首个正文单元合并。没有 `\begin{document}` 的被引入章节文件仍按普通
正文文件处理，不能把整份 include 误判为前导区。

保持命令、花括号、方括号、标签、引用键和环境边界原样。

### 5.2 区分结构参数与可编辑文本参数

使用以下固定分类：

| TeX 对象 | 处理方式 |
|---|---|
| 章节标题参数 | 默认受 `title_lock` 保护；解锁后仅改标题文字 |
| `\caption{作者说明}` | 可将文字部分标为 `author`，保留命令结构 |
| `\footnote{作者说明}` | 可编辑文字部分，保持嵌套命令完整 |
| `\textbf/\emph/\textit{作者正文}` | 默认保护包装命令；用户授权格式清理时用 `--editable-style-wrapper` 开放，内部文字仍受不变量和 Voice 约束 |
| `\label{}`、`\ref{}`、`\cite{}` | 全部保护 |
| `\url{}`、`\path{}`、`\verb`/`\Verb`/`\lstinline`（含星号与可选参数） | 完整命令、delimiter 与载荷全部保护 |
| `\DefineShortVerb`/`\MakeShortVerb` 声明的短 verb | 仅在声明生效区间内逐物理行保护；`\UndefineShortVerb`/`\DeleteShortVerb` 后恢复普通正文 |
| `\CustomVerbatimCommand`/`\RecustomVerbatimCommand` 声明的命令 | 不依赖命令名是否以 `Verb` 结尾；声明后的 delimiter 型调用整体保护 |
| 自定义命令参数 | 默认保护；只有明确知道参数为作者正文时才编辑 |
| 数学环境 | 标 `math`，不编辑内部内容 |
| `verbatim`/`Verbatim`/`BVerbatim`/`LVerbatim`（含星号）、`alltt`、`lstlisting`、`minted` | 含环境可选参数的完整范围标 `code`，不编辑内部内容 |
| `comment`、`filecontents`、`filecontents*` | 整个环境按不渲染载荷保护；其中的标题、列表、include 和负例词不得进入正文、场景或重复门证据 |
| 注释 | 默认不作为正文改写；用户明确要求时单独处理 |

short verb 与 `\verb` 一样不得跨物理行。当前行缺少 closing delimiter 时，准备器先遮罩从 opener 到行尾，继续识别后续行的其他合法载荷，同时登记 protection parse problem；不能把下一行 delimiter 借来配对。CRLF 与 LF 使用同一物理行语义。注释、已识别代码环境和既有 verb 载荷中的伪声明不得激活新命令或 delimiter。

未闭合 `\verb`、声明式 short verb、自定义 verbatim command、代码环境、`$...`、`$$...$$`、`\(...\)`、`\[...\]` 或数学环境即使载荷已被 fail-closed 遮罩，也必须使所在单元为 `UNRESOLVED`、prepare 顶层为 `REVIEW`；不得因 `masked_text` 中没有可编辑字符而降成 `SKIPPED_PROTECTED`。invariant checker 对原样未闭合结构给出 `TEX_PROTECTION_PARSE_REVIEW`，载荷变化另给硬错误。全角 `＄` 不是 TeX 数学 delimiter。

`comment`、`filecontents` 或 `filecontents*` 未闭合时，适用与未闭合代码环境相同的 fail-closed 合同：载荷遮罩至 EOF，所在单元为 `UNRESOLVED`，prepare 顶层为 `REVIEW`。

这些规则是有限、保守的 authoring 保护语法，不是完整 TeX 宏展开器。catcode 动态改写、任意引擎扩展或无法静态确认的宏生成语法都标 `UNRESOLVED`，不要猜测；不要用正则替换穿越嵌套命令边界。

### 5.3 保存 TeX 锚点

为每个可编辑单元保存：

```yaml
unit_id:
file_id:
heading_path:
start_line:
end_line:
prefix_hash:
content_hash:
suffix_hash:
```

使用标题路径和前后文哈希共同定位。不要只依赖行号；前序编辑会改变行号。

## 6. Markdown 感知解析

识别：

- ATX 与 Setext 标题；
- YAML frontmatter；
- fenced code block 与缩进代码；
- blockquote；
- 表格；
- 列表层级；
- HTML 块；
- 链接目标、图片和引用定义；
- 行内代码和公式；
- 脚注定义。

默认保护 YAML、代码、HTML 属性、链接目标、图片路径和引用键。根据来源角色决定是否编辑 blockquote；直接引语标 `quoted`，作者自写的提示块可标 `author`。

保持表格列数、分隔行和列表层级。只编辑确认属于作者正文的单元格或列表项。

## 7. 来源角色保护

先执行第 4 节的文件级 `source_role` 门，再对实际进入 authoring queue 的文件划分 span 角色。
文件级 `GENERATED/UNRESOLVED` 不产生作者 unit；这不是删除文件，其冻结字节仍属于 snapshot、
rendered output 与完整性闭包。finalizer 必须从冻结副本、有限 marker registry、辅助路径信号和
`source_role_overrides.json` 独立重建角色，不能只相信 CSV 字段或目录名。

为每个文本 span 标记：

- `author`；
- `quoted`；
- `exam-original`；
- `OCR`；
- `code`；
- `math`。

使用最内层保护优先。不要编辑 `quoted`、`exam-original`、`OCR`、`code` 和 `math` 内部内容。

建立保护区清单：

```yaml
protected_id:
unit_id:
role:
start_anchor:
end_anchor:
hash_before:
reason:
```

编辑后再次计算保护区哈希。任何保护区哈希变化都必须回滚该单元并重新处理。

## 8. 文档单元清单

按最小完整写作功能建立 unit，不逐句切块：

1. 优先使用完整小节；
2. 小节过长时按段落组切分；
3. 保持列表、表格、引语和公式邻接说明完整；
4. 不跨文件引用边界生成一个可编辑 unit；
5. 不把标题与其首段分开；
6. 不把公式与紧随其后的作者解释无故分开。

记录：

| 字段 | 说明 |
|---|---|
| `unit_id` | 稳定 ID |
| `file_id` | 所属文件 |
| `heading_path` | 章节路径 |
| `scene` | 场景路由 |
| `voice_profile` | 使用的声线档案 |
| `author_chars` | 可编辑正文规模 |
| `protected_spans` | 保护区数量 |
| `owner_chunk` | 唯一编辑分块 |
| `status` | 覆盖状态 |

## 9. 分块预算

按可见作者正文字符而不是文件字节控制分块：

| 项目 | 预算 |
|---|---|
| 目标分块 | 4000 至 7000 个可见正文字符 |
| 硬上限 | 8000 个可见正文字符 |
| 最小分块 | 1200 个可见正文字符，除非完整小节更短 |
| 上下文重叠 | 前后各 1 个完整段落，合计不超过 1200 字符 |
| 单次结构重排 | 不跨越一个授权章节 |

若一个不可拆结构超过硬上限，保留完整结构并标记超限原因。不要在表格、列表、数学环境、引语或 TeX 命令中间硬切。

对密集 TeX 命令的分块，额外限制总行数，避免保护区吞噬上下文。每块最多 600 行；超出时在完整段落边界继续切分。

## 10. 重叠上下文

只把重叠段用于理解衔接，不重复编辑。

为每个重叠段指定唯一 owner：

```yaml
overlap_id:
owner_chunk:
reader_chunks: []
hash_before:
```

执行以下规则：

- owner chunk 可编辑重叠段；
- reader chunk 只读，不输出该段改写；
- 合并时只接受 owner 版本；
- owner 版本变化后，更新相邻块的衔接检查；
- 相邻块不得各自生成一份竞争改写。

若跨块衔接必须同时改两侧，不得在 prepare 后手造临时 unit、合并 ID 或拼接普通 bundle。只有用户已授权 `STRUCTURAL + ADJACENT_PAIR`，且本轮 prepare 已冻结对应 `STX-*` 时，才按第 13.2 节提交双 fragment 原子 transaction；当前 run 没有合法候选时，调整分块预算并新建 prepare run，或把该处保留为 `UNRESOLVED`，不得分别猜测。

## 11. 场景与 Voice Profile

先在文档级识别主要用途，再按完整 unit 路由。不要逐句切换场景。

为每个 unit 记录：

- 显式用户场景；
- 自动路由得分；
- 最终场景；
- 平局裁决；
- Voice Profile 版本；
- Profile 置信等级；
- 未提供作者样本时的默认声明。

混合文档允许不同 unit 使用不同场景。共享摘要或总引言用途不明时使用 `GENERAL`，不要拼接三种声线。document prior 按 include 根覆盖逻辑文档，而不按物理文件割裂；它只补全与本 unit 唯一弱信号一致、且其他场景得分为零的场景，不得把完全中性的“背景/结论”静默改成邻近强场景。两个正分场景平局或 margin 不足时，无论 top score 是否达到强路由阈值都属于 `AMBIGUOUS`；document prior 不得替低分或强分歧义作隐藏裁决。

## 12. 覆盖账本

为每个 unit 使用且只使用一个状态：

| 状态 | 含义 |
|---|---|
| `PENDING` | 已列入但尚未处理 |
| `IN_PROGRESS` | 当前唯一正在处理的单元 |
| `DONE` | 改写候选机械验证通过，变化与 diff 已登记；作用域只是候选组装，不代表 paired-quality clearance 或交付完成 |
| `NO_CHANGE` | 已完整阅读且未提交变化；仍需 paired-quality request，不证明原文自然 |
| `SKIPPED_PROTECTED` | 全单元均为保护角色 |
| `SKIPPED_GARBLED` | 可读性不足，按规则跳过 |
| `UNRESOLVED` | 角色、权限、解析或冲突无法解决 |
| `CHANGED_AFTER_SNAPSHOT` | 源文件在快照后变化，未混入本轮 |

账本至少包含：

```yaml
unit_id:
status:
scene:
mode:
intensity:
decisions:
hash_before:
hash_after:
diff_path:
protected_hashes_ok:
style_gates:
notes:
```

不要把只抽查了首尾的 unit 标为 `DONE` 或 `NO_CHANGE`。

## 13. 分节编辑

对每个 owner unit 执行：

1. 核对快照哈希；
2. 加载前后重叠只读上下文；
3. 标记保护区；
4. 加载场景规则和 Voice Profile；
5. 连续阅读完整 unit；
6. 给候选位置分配 `KEEP/DELETE/REWRITE/REVIEW/NO_CHANGE/UNRESOLVED`；
7. 按强度改写；
8. 比较改前改后；
9. 核对保护区哈希；
10. 运行机械验证并生成 paired-quality request；
11. 生成 diff；
12. 更新覆盖账本。

`SCENE=MODELING` 的 unit 在第 6 步前另读
[modeling-reasoning-preservation.md](modeling-reasoning-preservation.md)，只盘点 source 中实际存在的
观测/约束、数学变化、方法选择和结果/限制节点。不存在的节点不补造；存在的节点及其具体连接
必须在候选中可定位。相关变化的 `rewrite_intent.target_signals` 使用
`SCENE-MODELING-JUDGMENT-*`，source span 覆盖发生改动的原判断。全文组装后运行
`audit_rewrite_contract.py --scene MODELING`；出现 `MODELING_JUDGMENT_CHAIN_LOSS` 时保持
`REVIEW/2`，只能回到相应 source span 局部修订，不能启动第二个人文化工具。

一次只把一个 unit 标为 `IN_PROGRESS`。发生中断时从该状态恢复，不重复改写已完成单元。

### 13.1 改写包合同

只读取 `chunks/<unit_id>.json` 中状态为 `PENDING` 的块。`masked_text` 中的每个保护占位符必须原样、恰好保留一次；不得改 ID、12 位 hash、顺序或数量。

不要手写 binding 骨架。先用安装版脚本从冻结 run 生成模板：

```powershell
python "$skillRoot\scripts\scaffold_humanize_rewrites.py" `
  --run-dir <run-dir> `
  --output <nonexistent-rewrites-dir> `
  --decision REWRITE `
  --format text
```

**骨架成功后不要直接运行 finalizer。** `SCAFFOLDED` 只表示冻结 binding 已安全发布，stdout 必须同时出现
`authoring_state=PENDING_TEMPLATE_COMPLETION` 和
`next_action=COMPLETE_EVERY_TEMPLATE_BEFORE_FINALIZE`。逐个连续阅读模板后：`REWRITE` 必须先改
`masked_text`，再替换 `rewrite_intent.summary`，补齐 `operations/source_spans/target_signals` 并覆盖每一条
实际变化的 source line；`NO_CHANGE` 必须替换具体理由并补至少一个 hash-bound `evidence_span`。任一模板
仍含 TODO、空 intent/evidence 数组或未覆盖变化行时，禁止进入“完成”叙述；如误运行 finalizer，应得到
`REWRITE_INTENT_AUTHORING_INCOMPLETE` 或 `NO_CHANGE_AUTHORING_INCOMPLETE` 的 `REVIEW/2`，然后按
`actionable_next_actions` 修复，而不是放松 schema。

scaffold 的 JSON 输出把可执行合同放在 `rewrite_intent_authoring_contract`；text 输出也逐项打印同一
合同。开始填写前必须读取其中的 `rewrite_intent_exact_fields`、`operation_contract.exact_fields`、
`source_span_contract.exact_fields/hash_algorithm`、`coverage_contract` 和
`valid_rewrite_intent_example`，不能凭字段名猜 schema。operation 只能有
`id/kind/source_span_ids/target_signals/summary`；source span 只能有
`id/start_line/end_line/sha256`。span hash 的固定算法是：先把 CRLF 和裸 CR 归一为 LF，再按
`splitlines(keepends=True)` 得到冻结 masked source 的物理行，按 1-based 闭区间拼接所选行，保留行尾，
用无 BOM UTF-8 编码后计算小写 SHA-256。局部 span 不得填写整 unit hash；示例中的真实 hash 只绑定
示例行，不能复制到当前单元。

单次操作只涉及一个连续 source span 时，不要手算 hash，运行只读辅助入口：

```powershell
python "$skillRoot\scripts\build_humanize_rewrite_intent.py" `
  --run-dir <run-dir> --unit-id <U-id> `
  --start-line <1-based> --end-line <inclusive> `
  --operation-kind REWRITE_STYLE_SHELL `
  --target-signal STYLE-EMPTY-ENDING `
  --summary "删除空泛收尾并保留材料范围" --format json
```

把返回的 `rewrite_intent` 插入对应 scaffold bundle，再单独编辑 `masked_text`。辅助入口只读取经 preflight
验证的冻结 unit，不修改 bundle；`writes_performed=false`、`completion_claim_allowed=false`。多跨度或多
operation intent 仍按 scaffold 的 exact-field 与 coverage 合同逐项编写，不能把单跨度辅助结果扩张成未
声明的变化。

finalizer 对常见作者错误同时保留总类和细类。`REWRITE_BUNDLE_INVALID`/
`REWRITE_INTENT_INVALID` 表示总类；operation/source-span 字段集合、span hash、operation 引用、完整
coverage、span 不与 diff 相交、变化行未声明分别产生 `REWRITE_INTENT_*` 细类。顶层
`actionable_next_actions` 会给出闭集修复动作；先按细类修复，再重跑同一 finalizer。动作只解释机械
合同，不代表文风收益或 paired-quality clearance。

若不同单元需要不同处置，使用严格覆盖全部 `PENDING` unit 的 UTF-8 JSON 映射，不能把未列出的
unit 默认为 `REWRITE` 或 `NO_CHANGE`：

```powershell
python "$skillRoot\scripts\scaffold_humanize_rewrites.py" `
  --run-dir <run-dir> `
  --output <nonexistent-rewrites-dir> `
  --decision-map <unit-decisions.json> `
  --format text
```

映射值只能是 `REWRITE` 或 `NO_CHANGE`；大小写碰撞、缺失 unit 和多余 unit 均整体拒绝。`--output`
必须指向尚不存在的新目录，不要预先创建空目录；这使两阶段发布能区分调用方目录与本轮原子产物。
`--decision-map` 的缺文件、权限、读取、UTF-8、JSON 和对象合同错误分别返回稳定的
`DECISION_MAP_*`、`FAIL/1`，普通失败载荷不得回显输入路径；它们不属于 `REVIEW/2`。

脚本只读取 `PENDING` chunk，逐个回显 `unit_id`、`chunk_binding_sha256`、
`voice_profile_sha256` 和 masked text；`scaffold_metadata.json`（`humanize-rewrite-scaffold/v5`）明确
`completion_claim_allowed=false`。`REWRITE` 模板默认复制冻结 masked text，未产生真实变化时
finalizer 会拒绝并要求改成带具体理由的 `NO_CHANGE`；`NO_CHANGE` 模板的 `reason=TODO` 故意不满足
理由门，必须由调用者替换。模板输出不等于执行包、机械 PASS 或质量 clearance。
每个 v4 模板都显式带 `template_field_edit_scope: null`。只有确认用户已授权精确字段 payload 后，
才把某个 `REWRITE` 的 null 替换为 unit scope；scaffold 本身不推断授权，`NO_CHANGE` 也不得改成非 null。

v5 骨架发布采用两阶段标记。目录进入最终名称时只含
`.humanize-scaffold-uncommitted`；普通成员与 marker 均由句柄冻结并复验后，才把同一 marker 原子改名为
`.humanize-scaffold-committed`。commit marker 以 strict JSON 绑定 `scaffold_metadata.json` 的原始字节
SHA-256，并固定 `completion_claim_allowed=false`。目录存在、metadata 可读或模板齐全都不表示发布完成：
finalizer 必须拒绝缺 committed marker、残留 uncommitted marker、marker link/hardlink、非法 schema、
metadata hash 错配或 legacy metadata 携带 marker。发布后复验失败会先按 pinned parent handle 回滚；
若回滚也失败，骨架器返回 `FAIL_DIRTY/1` 与 `output_may_exist=true`，调用方必须隔离该目录，不能把它
当作 `SCAFFOLDED`。安全发布当前只支持本地 NTFS；ReFS、FAT/exFAT、SMB 和非 Windows 平台明确
fail closed，不退化为按路径先检查再 rename。

sidecar 用 `metadata_scope=SCAFFOLD_CREATION_TIME` 和
`template_hash_scope=ORIGINAL_TEMPLATE_BYTES` 明确 `requires_manual_completion=true` 与
`template_sha256` 都描述骨架生成时刻：前者不是动态进度，后者绑定原始模板字节，人工填写后自然不再
等于当前 bundle。finalizer 只把 sidecar 作为严格审计旁证，
仍以每个 bundle 的当前 binding、正文和验证结果裁决，不把 sidecar 当完成台账。v5 只从 strict
schema 2 `prepare_integrity.json` 签发；合法历史 schema 1 运行返回
`legacy_prepare_requires_reprepare / REVIEW/2`，要求重新 prepare，不把旧闭集静默升级成新 authoring
权限。preflight 的 `run_state_sha256` 只绑定 manifest 明列的 immutable prepare closure；后来生成的
rendered、validation、ledger 与 metadata 不改变该值，但任何明列 prepare artifact 漂移仍整体拒绝。
每个 v4 模板还冻结完整 `humanize-long-authoring-binding/v1`：source span、chunk、scene route、Voice、
snapshot 和 policy 均由 finalizer 从准备工件重建，调用方修改 binding 并同步改 sidecar hash 也不能通过。
骨架器把 `unit_id` 当作文件名使用，只接受由 ASCII 字母/数字开头、总长不超过 128 且仅含
字母、数字、`.`、`_`、`-` 的 ID；路径分隔符、保留路径段、空白和控制字符均在写入前拒绝。
同一 run 中不区分大小写的重复 ID 也必须整体拒绝，避免 Windows 文件名碰撞或覆盖另一单元。

改写结果写到独立 `<rewrites-dir>/<unit_id>.json`：

下例只展示人工可编辑字段；`authoring_binding` 必须原样保留 v5 模板中的完整对象，省略它、手写它或
修改其中任一值都会失败。

```jsonc
{
  "schema_version": "humanize-unit-rewrite-bundle/v4",
  "unit_id": "<chunk.unit_id>",
  "chunk_binding_sha256": "<chunk.chunk_binding_sha256>",
  "decision": "REWRITE",
  "voice_profile_sha256": "<chunk.voice_profile_sha256>",
  "authoring_binding": { /* 原样保留 scaffold 生成的完整对象 */ },
  "masked_text": "改写后的完整占位文本",
  "rewrite_intent": {
    "summary": "删除空泛收尾并保留材料范围",
    "operations": [{
      "id": "O1",
      "kind": "REWRITE_STYLE_SHELL",
      "source_span_ids": ["S1"],
      "target_signals": ["STYLE-EMPTY-ENDING"],
      "summary": "删除空泛收尾并保留材料范围"
    }],
    "source_spans": [{
      "id": "S1",
      "start_line": 2,
      "end_line": 2,
      "sha256": "<冻结 masked chunk 第 2 行（保留行尾）的 SHA-256>"
    }],
    "target_signals": ["STYLE-EMPTY-ENDING"]
  },
  "template_field_edit_scope": null,
  "keep_reasons": {
    "LEX-RESULT-01": "此处承担结果报告言语行为"
  },
  "warning_resolutions": {
    "<warning_fingerprint>": "建议恢复原句模态以保留结论范围"
  },
  "warning_review_request_sha256": "<current_request_sha256>"
}
```

`template_field_edit_scope` 是 unit v4 必填字段。绝大多数 `REWRITE` 写 `null`；只有用户明确授权当前
unit 中精确 live field 的载荷编辑时，才写 strict 嵌入对象：

```json
{
  "schema_version": "humanize-unit-template-field-edit-scope/v1",
  "permission_boundary": "PAYLOAD_ONLY",
  "edits": [
    {
      "line": 1,
      "label": "适用题目",
      "permission": "PAYLOAD_ONLY",
      "reason": "用户明确授权修复该字段载荷的表达，同时保持字段职责、范围和力度不变。"
    }
  ]
}
```

对象只接受精确键，`edits` 必须非空，同一 source line 只能出现一次，label 只允许
`适用题目/逻辑链条/给定首句/用词建议`，reason 必须具体。行号相对冻结 unit 的 masked source；
finalizer 用该 unit 的实际 source SHA 物化 direct
`humanize-template-field-edit-scope/v1`，调用方不能自填或替换 source SHA。非 null scope 只允许
`decision=REWRITE`；所有 `NO_CHANGE` 必须显式写 `template_field_edit_scope: null`。

三层字段角色仍由 validator 重建：`artifact_role=before|after`、`source_role=TEMPLATE_FIELD`，以及
四类精确 payload role。header 的缩进、label、全角/ASCII 冒号、位置与顺序永不可授权；header 改动
硬 `FAIL/1`。没有 scope 的 payload 编辑为 `TEMPLATE_FIELD_PAYLOAD_EDIT_UNAUTHORIZED / REVIEW/2`；
已授权但职责、适用范围、逻辑关系、否定或力度漂移时为
`TEMPLATE_FIELD_ROLE_OR_FORCE_DRIFT / REVIEW/2`。scope 固定
`local_clearance_supported=false`，不贡献 paired-quality clearance。Markdown fenced/inline code、
TeX verbatim 与 TeX 注释中的同形字段不属于 live field。

上例是 warning proposal 包，不是可完成的 `DONE/PASS` 包。首次运行没有 warning 时，或尚未
提交 proposal 时，同时省略 `warning_resolutions` 与 `warning_review_request_sha256`，不得单独携带
其中任一字段。`warning_review`、`reviewer_kind`、`reviewer_id`、`reviewer_id_sha256` 等身份字段已
退役；出现即拒绝，不回显调用方标签，也不把标签或其 hash 写入队列、ledger 或 validation 工件。

已连续阅读且无需改写的单元必须显式提交：

```jsonc
{
  "schema_version": "humanize-unit-rewrite-bundle/v4",
  "unit_id": "<chunk.unit_id>",
  "chunk_binding_sha256": "<chunk.chunk_binding_sha256>",
  "decision": "NO_CHANGE",
  "voice_profile_sha256": "<chunk.voice_profile_sha256>",
  "authoring_binding": { /* 原样保留 scaffold 生成的完整对象 */ },
  "template_field_edit_scope": null,
  "reason": "正式定义组保持原有等权结构",
  "evidence_spans": [{
    "id": "S1",
    "start_line": 2,
    "end_line": 2,
    "sha256": "<冻结 masked chunk 第 2 行（保留行尾）的 SHA-256>"
  }],
  "keep_reasons": {}
}
```

`REWRITE` 与 `NO_CHANGE` 都必须从当前 chunk 精确回显 `unit_id`、`chunk_binding_sha256` 与 `voice_profile_sha256`。文件名与内部 unit 不同、chunk hash 缺失/非法/错配、Voice hash 缺失/非法/错配时，在正文 validator 之前分别拒绝，不得由 finalize 自动补值。旧式 `.txt` bundle 无法承载这些字段，因此 Profile-bound run 只接受 strict JSON；重复 key、浮点数、非有限数字和过深结构直接拒绝，不能依赖解析器“最后一个 key 生效”的覆盖行为。

v4 的 `REWRITE` 必须形成完整 intent 图：每个 source span 和 target signal 都至少被一个 operation 引用；
target signal 必须以 `LEX/HUM/VOICE/STYLE/SCENE/USER/REPETITION/COLLOCATION/RHYTHM/HIERARCHY`
之一开头，后接可定位标签，例如 `STYLE-EMPTY-ENDING` 或 `SCENE-COURSE-RHYTHM`；裸
`COURSE-*` 不合法。scaffold 的 JSON/text 输出会回显当前前缀集合，但该语法通过只证明字段可解析，
不证明病灶判断或改写收益成立。
source span 使用 normalized-LF 后、保留行尾的 frozen masked chunk 行字节计算 SHA-256。`source_spans` 清单必须按行递增、互不重叠，不能用不同 ID 重复登记同一范围；多个 operation 可以引用同一个已登记 span。每个声明 span
必须与实际 masked diff 相交，实际变化的每一 source line 也必须被声明 span 覆盖；另改一处未申报文本
固定拒绝。`NO_CHANGE` 理由至少含 8 个汉字、指向定义/段落/原句/结构/职责/对象/范围/条件/指代/
模态等具体功能，并至少有一个 hash-bound evidence span；“保持原样、无需修改、符合要求、已经自然、
没有问题”及其空泛改写固定拒绝。若单元含 high 表面命中，仍必须在 `keep_reasons` 中逐 signal 说明
正式功能或用户锁定依据。不要用空改写包或复制原文冒充处理；`REWRITE` 与原文完全相同时，收尾器会
拒绝并要求改用带理由的 `NO_CHANGE`。

v4 理由失败使用固定、去敏的 `NO_CHANGE_reason_invalid:<issue>`：`too_short_han` 表示不足 8 个汉字，
`generic_template` 表示命中已登记的空泛模板，`missing_function_anchor` 表示长度足够但没有指出保留的
具体功能。错误同时返回 `required=min_han_8+specific_function_anchor;reason_redacted=true`，不回显原理由。
修复时应说明“哪一处内容承担什么功能、改动会破坏什么关系”，不得仅扩写“已经自然”。该诊断只提高
可操作性，不证明理由真实，也不替代 hash-bound evidence span、high signal `keep_reasons` 或成对质量复核。
只要存在 `UNRESOLVED`，顶层 JSON 的 `unresolved_reason_summary` 与文本摘要的
`unresolved_details=coverage_ledger.final.csv` 必须指向精确台账；已知 NO_CHANGE code 只按固定枚举聚合计数，
不回显 unit notes 或理由正文。`classified/unclassified` 只表示是否命中当前固定诊断枚举，不表示未分类项安全。
固定枚举还包括 `no_change_evidence_spans_must_be_nonempty` 与
`rewrite_intent_source_spans_must_be_nonempty`，使空证据/来源 span 可从顶层直接定位；不得用开放式 notes
复制代替白名单扩展。聚合必须解析固定错误前缀和完整 code token，不得对整段 notes 做子串搜索；调用方把
code 字符串放进未知字段名、理由或其他错误正文时，必须保持 `unclassified`。

新运行还必须给每个 UNRESOLVED unit 写闭集 `unresolved_codes`，schema 为
`humanize-unresolved-code/v1`。`structured_code_counts`、`structured_classified/unclassified` 只从该数组聚合；
code 只能来自脚本内 registry，禁止拼接 decision、字段名、span/placeholder ID、validator reason 或异常正文。
最终账本把数组写成 canonical JSON 的 `unresolved_codes_json` 列。旧五类 `codes` 字段仅作为兼容 alias；旧 run
缺结构化数组时最多使用严格锚定的五类历史 notes，不得开放式推断。

每次 finalize 都写 `latest_attempt_metadata.json` 作为“最近一次尝试”的权威头。成功或 REVIEW 时它与当前
`finalization_metadata.json` 一致；失败且事务恢复旧候选时，它与 `last_failed_attempt_metadata.json` 一致，
而旧 `finalization_metadata.json` 只表示被保留的上一份 canonical candidate，不能代表最新尝试。
运行时失败只保留固定 `error_type/error_code`、恢复状态和相对工件名；绝对 run/rewrites 路径与异常正文不落入
失败 JSON 或文本摘要。失败回滚记录还必须清空 command、cwd、stdout/stderr、所有路径字段和任何位置的绝对
路径字符串。若本轮 final ledger 已随事务回滚，`unresolved_reason_summary.details_artifact` 必须为空，并以
`details_artifact_status=NOT_RETAINED_AFTER_ROLLBACK` 明示不可跟随到旧 ledger。`processable_scope_complete` 的作用域固定为
`PROCESSABLE_UNIT_ACCOUNTING_ONLY`，不表示全部单元已解决、候选可交付或 Humanize 已完成。

v2、v3 与无 `schema_version` 的旧 bundle 只读兼容。v2/v3 的 bundle contract 固定为 `REVIEW`：
v2/无 schema 缺少当前 authoring binding，v3 缺少 v4 的模板字段权限边界。即使旧 intent 可生成机械证据，
`rewrite_intent_coverage_status` 仍为 `REVIEW`，不得形成正式交付或 Humanize 完成声明。未知 schema、
TODO、空数组、span hash/行范围错配、operation 覆盖不全或未申报 diff 都不是 legacy，必须拒绝。

`LIGHT/BALANCED` 只允许其强度表中列出的局部编辑，不提交 `structural_plan`，也不得交换完整段落。
finalizer 对非 STRUCTURAL 候选执行高置信度整段顺序检查：两个以上唯一、完整保留的作者段落出现逆序时，
登记 `non_structural_paragraph_reorder_detected`，单元固定为 `UNRESOLVED`，不进入 paired-quality 或
`rendered_review/`。该门只声称拦截可机械确认的完整段落换位，不把它夸大成所有近似结构移动检测器。

BALANCED 的段落拓扑变化另走声明式窄门，不等于开放任意拆并段。只有 v4 `REWRITE` operation 精确使用
`MERGE_ADJACENT_REDUNDANCY` 或 `SPLIT_OVERLOADED_PARAGRAPH`，每个 operation 只引用一个与冻结
masked source 精确对齐的 span，且对应 target signal 分别为
`HIERARCHY-ADJACENT-REDUNDANCY` / `HIERARCHY-OVERLOADED-PARAGRAPH` 时才进入验证。合并 span 必须
恰好覆盖两个相邻作者段，拆分 span 必须恰好覆盖一个作者段；目标分别恰好为一段/两段，多个操作的
source/target 范围不得重叠，独立保护占位符不能夹在拓扑 span 内。段数净差与 operation kind 必须回加；
净差为零时仍以唯一句子-段落 membership 检测同时发生的 merge/split，缺唯一证据才回退行级 diff。
LIGHT、legacy、generic operation、错 signal、过宽 span、未申报拓扑或 scope 外变化固定阻断。
`topology_authorization_status=PASS` 只证明上述机械关系，不证明相邻两段确实语义重复或原段确实职责过载；
paired-quality 与人工读感复核仍保持 pending。

writer bundle 不得自填 paired-quality PASS、reviewer 身份或 clearance。普通 warning proposal 固定
为 identity-free `UNVERIFIED_CALLER_PROPOSAL`。finalizer 从实际恢复后的
before/after 与当前 validator policy 独立生成
`validation/<unit_id>.paired-quality-review-request.json`；`REWRITE` 登记逐 hunk 变化，`NO_CHANGE`
也生成 `changes=[]` 请求。机械验证通过的 unit 可进入候选组装，但在可信外部复核接入前，unit 的
`paired_quality_review_status` 固定为 `PENDING_EXTERNAL_REVIEW`，不能因理由具体或原文未变而升级。
同时生成 `validation/<unit_id>.rewrite-intent.json`，内容寻址绑定规范 bundle、before/after、实际落盘
diff 字节和 paired-quality request SHA；final metadata 中的 paired-quality record 反向给出 intent
evidence path/hash。该双向索引仍不是外部质量 clearance。

### 13.2 STRUCTURAL 包

STRUCTURAL 先读 [structural-rewrite-contract.md](structural-rewrite-contract.md)。prepare 固定输出
逐段来源 ID、职责、保护 ID、移动资格和 inventory hash。默认 `NONE` 只接受普通 unit
`structural_plan`，且每个来源段恰好映射一次。显式 `ADJACENT_PAIR` 还会生成
`structural_transaction_inventory.json`，但 inventory 只是候选：它给出机械 scope permission，
不等于执行请求或语义 clearance。正式 transaction bundle 必须以
`humanize-structural-transaction-bundle/v3` 精确回显某个冻结 `STX-*` 的 ID、binding、inventory
hash、两个 chunk/Voice binding 和两个完整 target fragment。普通 unit bundle 不能拼接成
transaction。两种模式都不解锁标题、不拆分或删除来源段；普通内联数学只可随完整来源段移动，
陈列数学、正式环境、引语和关键命令所在段锁定。

v3 每个 fragment 还必须提交 `local_rewrite_intent` 与 `template_field_edit_scope`。intent 的
source/evidence span 绑定 finalizer 根据
`target_groups` 重放得到的“只移动、不改字”结构基线，而不是原 member chunk：

- `decision=REWRITE`：使用与普通 unit 相同的 `rewrite_intent` 图；所有局部变化行都被声明 span 覆盖，
  每个 span 都实际命中局部 diff；
- `decision=NO_CHANGE`：候选 masked fragment 必须逐字等于结构基线，并提供具体 reason 与至少一个
  hash-bound evidence span；它表示“只执行已声明的结构移动，不另改措辞”，不是整个 transaction
  没有变化；此时 scope 必须为 null。

scope 通常为 null。只有该 fragment 的 local decision 为 `REWRITE` 且用户明确授权精确 live-field
payload 时，才写 strict `humanize-unit-template-field-edit-scope/v1`；line/label 绑定该 target fragment
的派生结构基线，finalizer 再用实际 baseline bytes/SHA 物化 direct scope。它不能跨 member 授权，
不能授权 header，也不能清除职责/力度漂移或 paired-quality 门。

v1/v2 仅只读兼容：v1 缺 local intent，两个 member intent 固定 `REVIEW`；v2 的 local-intent 证据
保留用于审计，但因缺少 v3 每-fragment scope 边界，bundle contract 与整篇
`rewrite_intent_coverage_status` 固定 `REVIEW`。v3 缺 scope 字段、NO_CHANGE 使用非 null scope、scope
line/label 不命中结构基线、未知 transaction schema、NO_CHANGE 偷改、span hash 错配或声明外第二处
变化均拒绝/原子回滚，不按 v1/v2 降级。

transaction 的来源段使用 `{unit_id, paragraph_id}` 复合 ref；两个 fragment 的联合 ref 必须恰好
覆盖两个 member 的全部来源段一次。允许 `movable=true` 的完整段在 pair 内换 target unit；锁定段
留在原 unit。一个 unit 不能同时有 standalone bundle 和 transaction，也不能属于两个 transaction。
prepare 可以列出三 unit 链中的两条重叠候选边，但同一次 finalize 必须先做全局 member claim，
在正文验证前拒绝共享 member 的提交。

v5 scaffold 与 transaction execution 的替换步骤固定为：先把预定 member 以 `REWRITE` 生成普通 v4
模板；完成绑定同一冻结 `STX-*` 的 transaction bundle；删除且只删除这些 member 的 standalone JSON；
保留 `scaffold_metadata.json` 中的原记录和原始 template hash；再 finalize。sidecar 的 record 全集仍须
等于冻结 PENDING 全集，而本次 submission coverage 等于剩余 standalone unit 与 execution member 的
不相交并集。member 同时有 standalone 和 transaction、缺失其他 PENDING、transaction 替换的 record
原决策为 `NO_CHANGE`、未知 member 或绑定漂移都在正文处理前拒绝。decline 不进入这个替换并集：它只
关闭候选 disposition，两个 member 仍各自需要 standalone `REWRITE/NO_CHANGE`。

inventory 为 `READY` 时，每个候选必须另有 disposition。执行使用上面的 transaction bundle；
不执行使用 `humanize-structural-transaction-decline/v1`，精确回显 transaction/inventory hash、
冻结顺序的两个 chunk/Voice binding、枚举 reason code、至少 8 个汉字的具体理由，以及两个 member
各至少一个、不重复且命中冻结来源段的 `{unit_id, paragraph_id}` 证据。合法 decline 不 claim
member，所以重叠候选可以逐边 decline；但共享 member 不能让相邻另一条边自动完成。一个 ID 同时
execution/decline、stale binding、空泛理由、单侧/未知/重复证据均须拒绝。

decline 与 unit 覆盖正交：两个 member 仍分别提交 `REWRITE/NO_CHANGE`；只有 decline 而没有 unit
bundle 时，候选 coverage 可以 PASS，但 unit 仍 `PENDING`。反过来，两个 unit 都 `NO_CHANGE`
但没有 execution/decline 时，该 `STX-*` 为 `PENDING`，
`structural_transaction_candidate_coverage_status=REVIEW`、
`structural_transaction_scope_complete=false`、`candidate_assembly_status=REVIEW`、
`delivery_gate_status=REVIEW`、`exit_code=2`、`coverage_completion_claim_allowed=false`，不得发布正式
`rendered/`。绑定正确但后续原子 gate 失败的 execution 仍记 `EXECUTED`，同时两 member 按原有
规则共同 `UNRESOLVED`。

finalizer 先按 plan 重放“只移动、不改字”的结构基线，再以该基线执行 FRAGMENT 与 DOCUMENT
不变量，避免把随段移动的数字/公式误报为改值。plan PASS 只证明机械映射；发生实际移动或合并时
`structural_semantic_mapping=NOT_EVALUATED`，并生成
`humanize-structural-semantic-review-request/v1`。transaction 则对两个 fragment 分别运行 FRAGMENT
validator，再运行联合 DOCUMENT gate；三项全 PASS 才能一次性提交两侧，并生成一个
current transaction v3 对应的 `humanize-structural-transaction-review-request/v2`。request schema
名称保持 v2；归档的 v1 request 只读兼容。该请求反向索引两个
fragment intent 的 canonical hash 与 diff-binding hash；每个
`humanize-transaction-fragment-rewrite-intent-evidence/v1` 又绑定 transaction request、paired-quality
request、bundle/fragment、结构基线、候选和 member diff。
任一 member、保护、fragment、DOCUMENT 或
后置 repetition 门失败时，双方共同回滚，零 accepted member diff/发布；逐 fragment validation/scope
失败审计可以保留，但 paired-quality request、accepted diff、clearance 与发布不得半边残留。请求绑定 before/baseline/after、
复合来源 ref、内外边界、member claim、plan/transaction、上下文、warning 和 policy hash；证据
路径使用提交后的 `validation/...` 相对引用。当前不消费本地或模型自填 clearance。完整候选的机械
组装可以是 `candidate_assembly_status=PASS`，但顶层必须为 `delivery_gate_status=REVIEW`、`exit_code=2`，候选
只进入 `rendered_review/`，不得据此声明全文完成。

`warning_resolutions` 只记录统一验证器非硬性言语行为 warning 的处理 proposal。每个 key
必须是当前 `warning_review_request` 中的完整 fingerprint，且
`warning_review_request_sha256` 必须精确绑定当前 unit 的 before/after SHA、warning details、
场景/格式/保护术语和 validator/invariant/scanner/lexicon/report-extractor/runtime 六项 policy hash。模型或执行代理可以
生成建议，但不得把自身复核描述为人工审批。bundle 不采集 reviewer kind、label 或稳定假名；proposal
固定写 `proposal_source=UNVERIFIED_CALLER_PROPOSAL`、`reviewer_identifier_collected=false`、
`identity_verified=false`、`review_clearance_granted=false`、`attestation_status=NOT_APPLICABLE`。
proposal 对应 warning 仍是 pending，unit
保持 `UNRESOLVED/REVIEW`，不得成为 `DONE/PASS`。跨 unit、跨 artifact 或 policy 变化后的
request 重放必须拒绝。

本地收尾器没有外部信任根，identity-free proposal 也不能升级为 `VERIFIED_HUMAN`。真正的
`VERIFIED_HUMAN` 必须由代理不可访问私钥的外部审批服务签发，并验证签名、unit/artifact、
request hash、审批范围和时效；当前 rewrite bundle 不承载这种 clearance。未接入该服务时，
应按 proposal 继续修改 `masked_text`，直到新版本不再产生 warning。公式、数字、单位、引语、
代码、TeX 命令、环境或结构等错误在候选单元门内属于不可接受的硬错误，任何 proposal 都不得
把它们降级为可接受候选。若门禁在组装前发现错误、拒绝该单元并逐字节回退到冻结原文，单元写
`UNRESOLVED`、`protected_hashes_ok=FAIL`，顶层写 `REVIEW/2`；这里的局部 `FAIL` 记录候选违规，
不表示损坏已经进入派生稿。只有保护损坏进入组装/发布工件，或隔离、回退、发布完整性失败时，
才升级为顶层 `FAIL/1`。prepare policy、冻结保护清单或完整性 manifest 的 hash 漂移属于信任基线
损坏，也直接使用顶层 `FAIL/1`，不得与候选 placeholder token 的局部 hash mismatch 混为一谈。

## 14. Diff 与回滚

完成一个或一批改写包后运行：

```powershell
python "$skillRoot\scripts\finalize_humanize_long_document.py" `
  --run-dir <run-dir> `
  --rewrites <rewrites-dir> `
  --check-command "<optional project build command>" `
  --check-timeout-seconds 300 `
  --format text
```

`--format text` 的第一行固定为 `DELIVERY <status> exit=<code> publish=<state>`，随后只显示候选组装、
paired-quality、unit 作用域、候选路径和编译状态；默认 `json` 仍保留全部审计字段。进程退出码
`0/1/2` 分别表示 `PASS/FAIL/REVIEW`，因此通用命令包装器可能把正常待审的 `2` 显示成“命令失败”；
调用者必须读取第一行或 `finalization_metadata.json`，不得把包装器的通用错误标签改写成硬失败。
run 目录中的 `.finalize.lock` 是跨进程锁的持久载体；进程退出后文件仍可存在，是否正在占用由操作系统
文件锁决定，不能用 `Test-Path .finalize.lock` 推断仍有活动 finalizer。

收尾器按单元恢复保护占位符，核对单元原始 hash，调用统一输出验证器，再决定是否接受。任何占位缺失、重复、未知或 hash 不符都会把该单元标为 `UNRESOLVED`，不会进入派生稿。

逐单元验证显式使用 `document_scope=FRAGMENT`。chunk 可能只含跨块 TeX 环境或外层花括号
的一侧；此时只允许改前已经存在、且改后问题列表完全相同的边界不平衡。环境名称/顺序变化、
花括号问题变化、保护跨度变化仍为硬失败。`FRAGMENT` 通过后，收尾器还必须把所有接受的
unit 组装回冻结全文，并以 `document_scope=DOCUMENT` 重新检查完整环境与花括号平衡；前一层
不能替代后一层，也不能把源文件本身已有的完整文档错误静默改成通过。

### 14.1 保存每节 diff

每个 `DONE` unit 必须保存：

- 原始内容哈希；
- 修改后内容哈希；
- 上下文锚点；
- 统一 diff 或等价逐段 patch；
- 使用的参数和规则版本；
- 保护区校验结果；
- 回滚内容或可逆 patch。

不要只保存最终整文件 diff；逐节 diff 才能定位回滚。

### 14.2 使用原子回滚

出现以下任一情况时回滚整个 unit：

- 保护区哈希变化；
- TeX/Markdown 结构边界损坏；
- patch 无法在原锚点唯一应用；
- unit 被快照后外部修改；
- 改写越过授权强度；
- 二次阅读发现言语行为被改变。

回滚后将状态设为 `UNRESOLVED` 或重新处理。不要只手工补一个括号后继续宣称通过。

transaction 的原子范围固定为两个 member。任何一侧回滚原因都必须扩展到整个 pair；两侧
`hash_after/diff_path` 清空，均不得进入 accepted replacement 或 invariant baseline。只有两个
FRAGMENT validator 与 DOCUMENT gate 全 PASS，才把两侧 replacement、ledger、diff 和 review
request 一次性从 staging 提交。`rollback_manifest.json.atomic_transactions` 至少记录 transaction
ID、两个 unit、失败 gate、`accepted_member_count=0` 和 `published_member_count=0`。如果同一 run
还有独立非事务进度，可以发布普通 partial，但 pair 对应范围必须与冻结 source 精确相同。

收尾器从不覆盖原源文件。所有接受的单元先写入 `.rendered_staging`；全文不变量和可选编译门通过后，只有全部交付门均有 clearance 的正式终态才发布到 `rendered/`，覆盖未闭合时发布到 `rendered_partial/`。机械候选完整但 STRUCTURAL 结构语义或 paired-quality 任一待外部复核时，完整候选发布到 `rendered_review/`，顶层保持 `REVIEW/2`。编译失败时 staging 改名为 `failed_staging/`，不创建新的正式输出。`rollback_manifest.json` 明确记录源文件未改、快照依据和丢弃失败 staging 的动作。

整次 finalize 还必须是 run-dir 级事务。持锁后先把全部非 transient 工件复制到隔离备份，再依次
提交 rendered namespace、validation、diff、最终账本和 metadata；任一步抛出异常时恢复调用前
字节，不能留下“有 rendered、无 validation/ledger/metadata”的半发布状态。已有发布证据的失败
重跑、或 `check_command` 通过绝对路径改变 run-dir 时，同样恢复上一版 canonical 状态；上一版
`finalization_metadata.json` 不得被本轮候选哈希覆盖。本轮失败只写
`last_failed_attempt_metadata.json`。该记录中的本轮 request hash 可以保留用于诊断，但所有已经
回滚的 `validation/...`、`diffs/...`、rendered 和 staging 路径必须清空，并标
`failed_attempt_evidence_status=NOT_RETAINED_AFTER_ROLLBACK`、
`failed_attempt_evidence_paths_reusable=false`，不得让新 request hash 指向恢复后的旧文件。该限制同时覆盖失败
metadata 内的 source path、check command、cwd、stdout/stderr 和 unresolved details pointer；不得只清理
run-dir 内路径而保留外部绝对源路径或命令行路径。
三份 authority metadata 必须作为一个固定闭包提交：`finalization_metadata.json`、
`last_failed_attempt_metadata.json`、`latest_attempt_metadata.json`。成功轮和失败轮都把未变化成员写入同一
generation 描述，不再依赖两个重叠 pair。组内 old/new 字节先写入同目录 transaction 并 flush/fsync，
随后持久化 `PREPARED` journal、安装三成员，最后原子替换
`.humanize-authority-group-commit.json`；该 pointer 是唯一提交点。重启时 pointer 仍绑定 base generation 就
恢复全部 old，已绑定 next generation 就从保留的 new image 补全全部 new；成员处于 old/new 之外、pointer
属于第三 generation、journal/commit/transaction 闭集或 hash 不一致时保持证据并硬失败，不猜测“最新”。
普通异常、事务内 `KeyboardInterrupt/SystemExit` 均先执行同一恢复状态机。恢复 canonical 后若失败 metadata
仍无法保存，调用方只能使用本次异常对象携带的去敏内存记录，stdout 标记
`attempt_metadata_persistence_status=FAILED`、`paths_authoritative=false`，不得回退读取磁盘旧 latest。
该协议可处理受控本地文件系统上的进程异常和下次启动恢复，但仍不证明恶意同权限写者不能同时伪造
pointer/journal/images，不证明文件系统整体快照未回退，也不夸大为物理断电下目录项持久顺序已经验证。

run-dir 级恢复使用 `humanize-run-state-journal/v2`，不得只保存 base 哈希后在 pointer=next 时相信
live 现场。事务目录必须同时保留 `base/` 与 `next/` 两个密封 image；闭包清单记录规范相对路径、文件
字节数与 SHA-256、空目录以及 file/directory 类型。authority writer 在创建 authority journal、安装
metadata 或移动 commit pointer 之前，必须先确认匹配 transaction ID 的 run-state journal，并把精确
next authority commit SHA/generation 与 next image 绑定。恢复只读取唯一 authority pointer：精确指向
base 时重装 base，精确指向 next 时重装 next；live 恰处于中断产生的第三字节态可以由密封 image 修复，
但 pointer 第三态、所选 image 篡改、类型变化、closure 缺件或部分 next binding 一律不修改 live 并硬失败。

清理不是无证据的 `rmtree`。删除事务 image 前先重新执行 pointer-selected closure 校验，并写入同时绑定
pointer SHA、transaction ID 与 selected closure 的 cleanup marker；journal 删除后无论事务目录尚在、已删
或删除中断，下一次启动都只能在 pointer 与 live closure 仍精确匹配时幂等完成清理。无法认证的 journal/
cleanup staging 前缀碰撞保留原文件并 fail closed，不凭模糊前缀删除。基础设施保留名只作用于 run 根目录
的首路径组件；`docs/.humanize-run-state-notes.txt` 一类普通嵌套工件必须进入 image 并可恢复。无 journal
时只把精确 `.humanize-run-state-<24-lower-hex>` 识别为 orphan transaction，宽前缀普通文件不阻断运行。

协议边界仍是受控本地文件系统上的文件内容、存在性与 file/directory 类型恢复。它不恢复或证明 ACL、owner、
mtime、xattr、NTFS alternate streams，不抵御恶意同权限写者同时伪造 pointer/journal/images，也不证明
文件系统整体快照未回退或物理断电下目录项持久顺序。任何机械恢复 PASS 仍不证明候选更自然、学术正确、
属于目标作者，或已经获得 paired-quality/结构语义 clearance。
所有账本 CSV 对公式前缀执行 spreadsheet-safe 转义；旧 final ledger 只接受
明确的 `unit_id/status` 合同、唯一 ID 与当前合法状态，缺列、重复或未知状态要求重新 prepare/finalize。
备份前还要拒绝 run-dir 自身或内部工件的 symlink、junction/reparse point 与多链接文件，并核对
复制前、复制后和备份树三份文件哈希一致；否则不能把外部目标或漂移快照当成可恢复基线。

逐单元证据保存在：

- `validation/<unit_id>.before.*` 与 `.after.*`；
- `validation/<unit_id>.validation.json`；
- `diffs/<unit_id>.diff`；
- `coverage_ledger.final.csv`；
- `rendered_manifest.csv`；
- `finalization_metadata.json`；
- `last_failed_attempt_metadata.json`：仅在事务恢复或运行时异常时记录失败尝试，不替代 canonical metadata；
- `rollback_manifest.json`。

### 14.3 全文 Voice 与跨 unit 二阶段门

局部 `mechanical_validation_status=PASS` 只进入临时候选，不构成质量完成。finalize 使用冻结 chunk 的
`masked_text` 与候选 bundle 的 `masked_text` 建立成对作者视图，保护占位符内部字节不进入
统计。Voice 门只消费 Profile 注册表中可机械重建的特征和负控：DEFAULT 的 PASS 表示场景
默认工件、逐 unit validator 与披露闭合，个人声线状态固定为 `NOT_APPLICABLE`；PERSONAL
至少需要 6 个目标正文块，逐 feature 核对当前 extractor hash、before/after 支持数和比例，
只拦截显著回退，不因样本常用连接词、括号或分号而强迫目标正文插入这些形式。所有结果均
保持 `identity_verified=false`。

跨 unit 门先运行 `LEX-REPAIR-01`，再由 `load_humanize_negative_guards.py` 严格加载当前
detector-only registry，运行其中适用于当前场景的 `negative_guard`。loader 只返回
`id/scene/detector` 及派生状态，完整 action-profile builder 不进入此运行链，`positive_action`
没有可执行入口。完整安装版 catalog 还必须先执行固定来源权限：只有
`MODEL_GENERATED/MODEL_ORIGIN_UNRESOLVED` 的负例 detector 可进入运行集，`UNKNOWN`、
`HUMAN_CONFIRMED`、`OCR_INHERITED`、`THIRD_PARTY` 的负例记录均为 `AUDIT_ONLY`。所有 detector
先按 `(document_id, resolved_scene)` 分区；审计记录必须以 `resolved_scene` 作为权威线格式字段。
仅为旧消费者展示而同时携带 `scene` 时，两字段必须大小写无关地相等；只有 `scene`、任一字段为空、
场景不在注册表内或两字段冲突时，整道跨 unit 门均为 `REVIEW`，不得静默补成默认文档或
`GENERAL`。跨 unit 工件使用 `humanize-cross-unit-repetition/v3`，其 policy 使用
`cross-unit-repetition/v3`；任何命中、before/after 增量与阈值计算均不得跨分区。
匹配视图使用 NFKC，删除零宽字符与汉字内部空格，但不跨保护占位符、段落或结构边界拼接。

版本化 detector 的计数合同如下：

- `regex_groups/v1`：延续跨 unit 负例语义。after 相比对应 before 新增 occurrence，且同一分区内
  至少两个不同 unit 共同达到 detector 阈值时才命中；同一 unit 内出现多次不能代替跨 unit 证据。
- `structured_repeated_list/v1`：先以 heading role 确定结构块，再按不同 block identity 计数；多个块
  即使同属一个 unit 也可满足 `minimum_blocks`，同一块无论产生多少匹配视图都只能计一次。每个块
  还必须满足 `minimum_items_per_block`，共享锚点按声明的 `shared_anchor` 覆盖不同块。TeX 原始视图
  先遮罩数学、代码、不渲染环境、注释、引语和完整普通命令调用，只恢复未处于这些跨度或外层命令参数中的
  `\\begin{itemize|enumerate}`、`\\item`、`\\end{itemize|enumerate}` 结构 token；
  `\\item[标签]` 只恢复 `\\item`，标签和普通命令参数不得进入锚点或 evidence。Markdown 的代码、
  引语和内联保护载荷同样不得进入结构锚点。

原文已有且未增加的 repetition 只进入 inherited 证据。命中时只把拥有新增 occurrence 或新增 block
的 unit 从临时接受集回退为 `UNRESOLVED`，删除其待发布 diff，并以原文组装 partial。证据写入
`validation/cross_unit_repetition.json`，包括 finding fingerprint、unit inventory、逻辑文档 hash、
lexicon、registry 原始字节、canonical registry 和 detector 定义 hash。命中 unit 属于 transaction
时，阻断集合必须先扩展到同一 transaction 的全部 member，再共同撤销两侧 diff/replacement；不能
让后置 repetition 门拆开已经通过 fragment validator 的 pair。registry 缺失、非法 UTF-8、重复键、
未知字段、未知 detector type、schema/scene/detector/threshold 漂移、缺失分区键、结构块身份不确定、
detector 评估异常、partial 范围或任一适用负例 guard 不可用时均 fail closed 为 `REVIEW`，不能跳过
该 guard、回退为其他 detector 或按空 registry 继续。

## 15. 合并与冲突

按 include 顺序和 unit 顺序合并。使用以下优先级：

1. 用户最新明确修改；
2. 快照后外部修改；
3. owner unit 的已验证 patch；
4. 未修改原文。

若源文件在处理期间变化：

- 不直接覆盖；
- 尝试用锚点做三方定位；
- 只有上下文唯一且保护区未变时才重放 patch；
- 其他情况标 `CHANGED_AFTER_SNAPSHOT` 并保留外部修改。

不要用“最后写入者胜出”覆盖用户变化。

## 16. 幂等重跑

把幂等定义为：对上一轮 clean 输出使用相同参数、相同规则版本和相同 Voice Profile 重跑时，不再产生实质文风改动。

只有未来已由可信外部链清除 paired-quality 与结构语义门、且
`finalization_metadata.json` 为 `publish_state=FINAL` 的唯一完整 `rendered/`，才可进入 fresh
second pass。它还须满足 coverage、场景、Voice、rewrite binding、全文 Voice 和跨 unit 门均 PASS。
`rendered_review/` 是质量或结构语义待审候选，任何针对它的 receipt 都是
`INVALID_EVIDENCE`；`rendered_partial/` 同样不能进入。然后执行：

```powershell
python "$skillRoot\scripts\prepare_humanize_second_pass.py" --format json prepare `
  --first-run <first-run> --second-run <second-run> --cases <cases-root>

# 对 second-pass-plan.json 中每个 case_path 分别启动一次新进程：
python "$skillRoot\scripts\run_humanize_generation_trial.py" `
  <cases-root>/<case-path> --output <trials-root>/<unit-id> --format json

python "$skillRoot\scripts\prepare_humanize_second_pass.py" --format json collect `
  --second-run <second-run> --cases <cases-root> `
  --trials <trials-root> --rewrites <second-rewrites>

python "$skillRoot\scripts\finalize_humanize_long_document.py" `
  --run-dir <second-run> --rewrites <second-rewrites>

python "$skillRoot\scripts\verify_humanize_second_pass.py" `
  --first-run <first-run> --second-run <second-run> --cases <cases-root> `
  --trials <trials-root> --rewrites <second-rewrites> `
  --output <second-pass-receipt.json> --format json

python "$skillRoot\scripts\finalize_humanize_long_document.py" `
  --run-dir <first-run> --rewrites <first-rewrites> `
  --second-pass-receipt <second-pass-receipt.json>
```

第二遍 prepare 必须继承第一遍 scene、budgets、editable wrappers 和同一 Voice Profile；证据绑定 PERSONAL/DEFAULT 还要重新提供 `--voice-allowed-root`。sealed prompt 只要求模型重新判断当前 chunk 是否仍需实质修改，不包含预期 `NO_CHANGE`、验收 atom、旧 diff 或第一遍 decision。每个 trial 必须有唯一 run id、真实新进程、严格 JSON、精确 unit/chunk/Voice 绑定，并让 receipt、run record、run seal、public seal 和 projection 相互一致。

MODELING trial 还必须继承 [modeling-reasoning-preservation.md](modeling-reasoning-preservation.md)。
fresh `NO_CHANGE` 不能只表示没有新的文风建议；它还要确认第一遍 source 中已有的公开判断节点
及其连接仍能在当前 candidate 定位。节点消失、方法名被提前成直接结论或限定被压平时，
`MODELING_JUDGMENT_CHAIN_LOSS` 使本轮保持 `REVIEW/2`，不能计入收敛。

第二遍也必须继承第一遍 intensity。STRUCTURAL case 保持 `title_lock=true`，但
`structure_lock=false`，并要求 fresh REWRITE 重新提交当前 second-run inventory 对应 plan；不得把
第二遍偷偷降成 BALANCED 或锁死结构后，用 `NO_CHANGE` 制造假收敛。

第一遍若包含相邻 pair transaction，结构语义已经固定为 `NOT_EVALUATED` 并只发布
`rendered_review/`，因此不具备启动 fresh second pass 的前提。不能把该候选重新 prepare 后让两个
member 都提交 `NO_CHANGE`，也不能用 second-pass receipt、assembly replay 或调用方声明清除原
transaction review request。只有未来外部可信语义审批形成正式 `rendered/` 后，才可按当时合同
开始新的 second pass；当前本地工具没有这条升级路径。

合法正式 `rendered/` 的 second pass 中，缺 trial、第二遍未完整 finalization、任一 fresh `REWRITE`
或两遍 rendered tree 不同，均为未收敛 `REVIEW/2`；receipt、plan、collection、run id、projection、
scene、Voice、tree 或 artifact hash 错配为 `FAIL/1`。第一遍 finalizer 不信任 receipt 自哈希，必须按
receipt 中的 evidence roots 重跑 verifier；删除或修改任一底层 trial 后，旧 receipt 立即失效。
即使 verifier 返回 convergence PASS，也只映射为稳定性观察，
`second_pass_quality_clearance_granted=false`，不会新增或替换此前已经存在的外部质量 clearance。
对 `rendered_review/` 提交 receipt 则直接拒绝并记 `second_pass_stability_status=INVALID_EVIDENCE`。

不要把“每次输出都不一样”当作拟人化。稳定取舍比随机变化更重要。

同一 run-dir、同一 rewrites 目录再次运行收尾器时，派生目录哈希完全相同只记录
`assembly_replay_idempotency=PASS`（旧字段 `idempotency` 为兼容别名）。它不等于上文的
fresh second pass；后者单独记录 `humanize_second_pass_convergence`。若已发布完整
`rendered/` 而新 staging 不同，保存为 `non_idempotent_staging/` 并返回 `FAIL`，不覆盖旧
输出。分批补齐 `rendered_partial/` 属于推进而非幂等比较，替换前后 hash 写入
`partial_history.jsonl`；覆盖终态后删除陈旧 partial，只保留当前完整 namespace：可信 clearance
齐全时为 `rendered/`，质量或结构语义待审时为 `rendered_review/`。

本地 runner 的 process boundary 只到 E2：它能记录新进程、read-only sandbox 请求和投影字节，但不能证明宿主文件系统、oracle 或完整 system/developer context 对模型不可达。receipt 必须保持 `filesystem_isolation_verified=false`、`oracle_unreachable_verified=false`、`academic_correctness=NOT_EVALUATED`。外部 Codex/API 因认证、额度或网络失败而未产生 trial 时，只能保持 `NOT_RUN/REVIEW`；单元测试中的 fake runner 只证明实现合同，不构成真实 fresh forward。

## 17. 编译与格式检查

这些检查只验证编辑没有破坏文件形式，不评价内容。

### 17.1 TeX 检查

优先使用项目现有构建命令。若没有，至少检查：

- 花括号与环境边界是否平衡；
- `\begin` / `\end` 是否配对；
- 引用键、标签和文件引用是否原样保留；
- verbatim、代码和数学环境哈希是否不变；
- 主文件是否仍能解析 include 图；
- 已存在的编译流程是否成功退出。

只报告由编辑引入的形式错误。不要借编译过程分析公式或论证。

逐 unit 的 `FRAGMENT` 检查只解决 chunk 边界造成的假不平衡；发布前的整文件检查仍按本节
全部条件执行。validation 证据必须公开 `document_scope`，warning request 也必须绑定该字段，
防止把 fragment request 重放到 document 检查或反向重放。

### 17.2 Markdown 检查

检查：

- fenced code block 是否闭合；
- 标题层级是否符合授权；
- 表格列数是否保持；
- 链接目标和引用定义是否不变；
- 列表层级是否未意外漂移；
- YAML frontmatter 是否保持原样。

### 17.3 格式失败处理

定位失败到最小 unit，回滚该 unit，重跑检查。若项目原本就无法编译或格式检查已有失败，记录 baseline，不把它归因于本次编辑，也不要在纯文风任务中修复。

`--check-command` 默认在 `.compile_check_staging/` 的一次性副本中执行，不直接接触待发布的 staging、run/source 快照或原始源文件。命令必须由调用方选用项目现有构建流程；若构建依赖原项目资产，应在命令中显式设置搜索路径或调用能接受派生主文件的现有脚本。检查副本会在命令后删除；命令在副本中产生的辅助文件不进入发布目录。收尾器同时对真实 staging 和 run 产物做前后文件集合/字节哈希核对，任何新增、删除或修改都使 `compile_check=FAIL`。未提供命令时 `compile_check=NOT_RUN`，但全文结构不变量仍会逐文件运行。不得把 `NOT_RUN` 写成编译通过。

检查命令默认有界运行 300 秒，可用正数参数 `--check-timeout-seconds` 缩短或延长；零、负数、`NaN` 与无穷值均拒绝。超时固定输出 `compile_check.status=FAIL`、`exit_code=124`、`timed_out=true` 与实际 `timeout_seconds`，并先走当前平台的完整后代清理，再读取编译输出和专用状态 FD。未超时和未执行检查时 `timed_out=false`；未提供命令时 `timeout_seconds=null`。专用状态 FD 读取也有独立短截止时间和 64 KiB 上限，只接受恰好一条、字段严格为 `cleanup/command_exit` 且退出码与 wrapper 实际退出码一致的记录；写端不关闭、超量、多记录、额外字段、退出码错配、非法编码或非法 JSON 一律使后代清理状态为 `FAIL`，不得让收尾器无限等待或把不完整状态当成成功。

执行检查命令时还要收拢其进程树。Windows 固定先启动不执行用户命令的受控 wrapper，把它加入
启用 `KILL_ON_JOB_CLOSE` 的 Job Object 后才发送命令；wrapper 返回后终止整个 job，再做哈希
复核。wrapper 解释器固定使用 `-I -S -X utf8`，不得让用户 site、`sitecustomize` 或
`PYTHONPATH` 在 containment 建立前执行启动代码。Job Object 创建、配置、分配或终止异常时必须
关闭已经取得的 handle；若分配失败，则不得发送用户命令，并须有界重试直接终止 wrapper，无法
确认退出即记 `FAIL`。结果记录 `process_containment=WINDOWS_JOB_OBJECT` 与
`descendant_cleanup=PASS`。Linux 使用独立 process group 与先于用户命令启用的 child subreaper；
wrapper 正常返回或收到 `SIGTERM/SIGINT` 时，都必须先停止并等待直接 shell，再杀死、收割其收养的
`setsid()` 脱离后代，最后通过专用继承 FD 回报清理状态。父进程中断时先让仍存活的 wrapper 自清理；
第二次中断不得跳过 `terminate/kill/wait` 的剩余有界清理。若超时，必须在 wrapper 仍存活且后代
关系仍可由 `/proc` 观察时先清理全部后代；每轮与末次扫描后都要重新确认 wrapper 存活，再杀 wrapper
和残余 process group。成功记录 `LINUX_SUBREAPER_PROCESS_GROUP`；Linux `prctl` 不可用时记录
`LINUX_SUBREAPER_UNAVAILABLE`，其他 POSIX 记录 `POSIX_SUBREAPER_UNSUPPORTED`。若 wrapper/Job
启动、配置或分配阶段抛出无法归类的平台异常，记录通用 `UNAVAILABLE`；这些标签均不得执行
未受控的用户命令。后代清理失败使 `compile_check=FAIL`。只等待直接 shell、先杀 wrapper、只清理
同组进程，或只在返回前多算一次 hash 都不合格：后台子进程可以脱离 session，并在正式目录发布后
继续写入。

## 18. 乱码与异常

遇到乱码时：

1. 尝试识别已有文件编码，不转换源文件；
2. 若同一段在候选编码下均不可读，标 `OCR` 或 `SKIPPED_GARBLED`；
3. 保存位置、行号范围和哈希；
4. 跳过该段，继续其他单元；
5. 不猜字、不调用上下文补写；
6. 交付时汇总跳过范围。

遇到截断命令、未闭合环境或无法解析的嵌套结构时，标 `UNRESOLVED`。不要为完成覆盖率擅自修复结构。

CLI 参数语法错误仍由 argparse 以 usage/error 和退出码 `2` 表示。prepare 的缺文件、权限、编码、
JSON、读取或调用合同错误必须在写入新输出目录前返回去路径化的结构化 `FAIL/1`；合法准备态
`REVIEW/2` 仍须有完整 metadata JSON。finalize 运行期异常同样必须输出结构化 JSON
`status=FAIL, delivery_gate_status=FAIL, publish_state=FAILED, exit_code=1`。不得让无 JSON 的 argparse
退出码 `2` 冒充正常的业务 `REVIEW/2`。

## 19. 完成交付

输出以下长文交付摘要：

```yaml
snapshot_id:
files_total:
source_role_summary:
source_processing_status_summary:
source_role_override_status:
files_changed:
units_total:
units_done:
units_no_change:
units_protected:
units_garbled:
units_unresolved:
units_changed_after_snapshot:
scenes:
voice_profile:
diffs:
assembly_replay_idempotency:
humanize_second_pass_convergence:
second_pass_stability_status:
second_pass_quality_clearance_granted:
scene_routing_status:
voice_binding_status:
voice_conformance_status:
structural_plan_status:
structural_semantic_mapping:
structural_semantic_review_status:
structural_semantic_review_requests:
structural_changes_applied:
structural_transactions_total:
structural_transaction_declines_total:
structural_transaction_candidates_total:
structural_transaction_candidates_executed:
structural_transaction_candidates_declined:
structural_transaction_candidates_pending:
structural_transaction_candidate_coverage_status:
structural_transaction_scope_complete:
structural_transaction_candidate_dispositions:
structural_transaction_decline_results:
structural_transaction_results:
structural_transaction_review_requests:
structural_transaction_rolled_back_ids:
candidate_assembly_status:
mechanical_validation_results:
paired_quality_review_request_coverage_status:
paired_quality_gate_status:
paired_quality_review_requests:
paired_quality_units_total:
paired_quality_units_pending:
paired_quality_units_missing:
paired_quality_clearance_granted:
rewrite_intent_coverage_status:
rewrite_intent_evidence:
rewrite_intent_units_pass:
rewrite_intent_units_review:
rewrite_intent_units_missing:
delivery_gate_status:
publish_state:
cross_unit_repetition_status:
coverage_completion_claim_allowed:
humanize_completion_claim_allowed:
format_check:
compile_process_containment:
compile_descendant_cleanup:
run_state_restored_after_failure:
finalization_metadata_preserved:
failed_attempt_metadata_path:
```

附上：

- 修改文件列表；
- 生成/未决来源文件及其 marker/辅助路径/override 依据与处理状态；
- 每节 diff 或其目录；
- 覆盖账本；
- `UNRESOLVED`、乱码和活动文件变化位置；
- 使用场景默认声线的披露；
- 格式检查结果。

只有 `PENDING` 和 `IN_PROGRESS` 均为 0 时，才能结束本轮。存在明确列出的
`UNRESOLVED` 不等于隐瞒未完成；必须准确说“可处理范围已完成”，不要说“全文完成”或
“无遗漏”。任何 `UNRESOLVED`、`SKIPPED_GARBLED` 或 `CHANGED_AFTER_SNAPSHOT` 都使
`coverage_completion_claim_allowed=false`；Voice、全局重复或 fresh second pass 未评估时，
`humanize_completion_claim_allowed=false`。

机器可读完成证据以 `finalization_metadata.json` 为准：

- `candidate_assembly_status=PASS`：没有硬失败、PENDING 或未决单元，只证明候选组装完成；
- `unit_status_scope=CANDIDATE_ASSEMBLY_NOT_DELIVERY`：`DONE/NO_CHANGE` 只属于单元候选账本；
- `status/delivery_gate_status=PASS`：候选组装完成，且结构语义与 paired-quality 均已获得可信 clearance；
- `status/delivery_gate_status=REVIEW`：仍有 PENDING/UNRESOLVED，或完整候选仍待结构语义/paired-quality 外部复核；
- `status=FAIL`：全文形式检查、编译门或完整输出幂等检查失败；
- `processable_scope_complete=true`：PENDING/IN_PROGRESS 为 0，不代表无乱码或未决；
- `coverage_completion_claim_allowed=true`：覆盖终态闭合、无未决且无硬失败，只允许声明
  覆盖与局部保护闭合；
- `scene_routing_status`、`voice_binding_status`、`voice_conformance_status`、
  `cross_unit_repetition_status`：分别报告逐单元场景、Profile 绑定、声线符合性和跨块新增
  模板；`NOT_EVALUATED` 不得改写成 PASS；
- `assembly_replay_idempotency`：同一 rewrite bundle 的派生字节重放；不是二次 Humanize；
- `humanize_second_pass_convergence`：把上一轮 clean 输出作为新输入的 fresh second pass；
- `second_pass_stability_status`：只把 second-pass 结果解释为
  `CONVERGENCE_OBSERVED/DISAGREEMENT_OR_INCOMPLETE/INVALID_EVIDENCE/NOT_RUN`；不承担质量放行；
- `paired_quality_review_request_coverage_status=PASS`：只证明所有可编辑 unit 都有当前 request；
  request 缺失时 coverage 为 `REVIEW`、quality gate 为 `BLOCKED`；齐全但未复核时 quality gate 为
  `PENDING_EXTERNAL_REVIEW`；无适用 unit 时两者为 `NOT_APPLICABLE`。`BLOCKED` 与 pending 都阻断
  正式交付；
- `rewrite_intent_coverage_status=PASS`：只证明所有 standalone unit 使用 unit v4、所有 executed
  transaction 使用 transaction v3，且每个 member 的 local intent/scope、evidence span 与结构基线到
  候选的实际 diff、bundle/fragment、member diff、paired-quality request 和 transaction request 完整绑定；
  legacy、缺件、回滚或任一绑定失败为 `REVIEW`，阻断正式交付；
- `humanize_completion_claim_allowed=true`：上述 Humanize 级门全部通过，才允许“全文
  Humanize 已完成”；兼容字段 `full_completion_claim_allowed` 必须与它相同；
- `publish_state=REVIEW_CANDIDATE` 与 `rendered_review/`：机械完整但结构语义或文风质量待审，不能称为正式输出；
- `publish_state` 只使用 `FAILED/PARTIAL/REVIEW_CANDIDATE/FINAL`；调用方不得由目录存在与否猜状态；
- `structural_transaction_results`：逐 transaction 报告 ID、bundle hash、两个 member、全局 claim、
  两个 fragment gate、DOCUMENT gate、真实变化、原子回滚原因和 review request；其中任一 PASS
  都不能覆盖顶层 delivery gate；
- `structural_transaction_candidate_dispositions`：以冻结 inventory 为全集逐 ID 报告
  `EXECUTED/DECLINED/PENDING`。四项计数必须回加；`READY` 中任一 `PENDING` 都使候选覆盖
  `REVIEW`，即使全部 unit 已是 `NO_CHANGE`；
- `structural_transaction_decline_results`：只保存通过 strict schema、冻结 transaction/inventory、
  两个 chunk/Voice、具体理由和双 member 来源段证据校验的 decline 规范化记录；它是逐 decline
  审计证据，不是 inventory 全集，候选覆盖仍只能读取 dispositions 与四项计数；
- `rollback_manifest.atomic_transactions`：证明单边失败时 accepted/published member 均为 0；
- `source_files_modified=0`：原源文件没有被工具覆盖。
- `run_artifacts_changed_during_check=true`、`staging_artifacts_changed_during_check=true` 或
  `evidence_artifacts_changed_during_check=true`：检查命令通过绝对路径污染了快照、正文
  staging 或 validation/diff 证据；编译门必须 `FAIL`。检测到证据 staging 污染时，
  本轮未发布的 validation/diff 会被丢弃；若已有正式发布证据，必须保留旧证据而不覆盖。
- `staged_evidence_discarded=true`：本轮证据因污染被丢弃，不表示旧证据不存在，也不表示
  新一轮正文或文风验证通过。
- `run_state_restored_after_failure=true`：本轮失败后已恢复调用前 run-dir；此时 canonical
  `finalization_metadata.json` 与 validation/diff/rendered 仍属于上一轮，失败尝试只能读
  `last_failed_attempt_metadata.json`。其中 `failed_attempt_evidence_paths_reusable=false` 时，
  任何空路径都不得回填成 canonical `validation/...`；
- `compile_check.process_containment` 与 `descendant_cleanup`：只有实际执行检查命令且进程树清理
  为 `PASS`，才允许继续读取编译结果；`NOT_RUN` 不表示命令隔离通过。

Voice/Rewrite 绑定固定输出 `voice_profile_sha256`、`voice_profile_bindings_total/matched/missing/mismatched`、`rewrite_binding_status`、`rewrite_bindings_total/matched/missing/mismatched`、`voice_profile_default_units/default_scenes` 与 `voice_default_disclosure_required`。只有所有初始 `PENDING` unit 的最终 bundle 均回显精确 Voice hash 时，`voice_binding_status=PASS`；只有 unit 与 canonical chunk hash 也全部匹配时，`rewrite_binding_status=PASS`。尚未提交、缺失或错配时为 `REVIEW`。这些字段只证明 Profile 与目标块工件身份闭合。`voice_conformance_status=PASS` 另由注册机械特征非回退门产生，并公开 DEFAULT/PERSONAL basis、feature/negative-control 计数和限制；它仍不能证明完整作者气质或作者身份。

不得以 `units_done > 0`、`rendered_partial` 存在或准备器 `status=READY` 代替全文完成门。

## 20. 长文检查表

- [ ] 已固定字节长度、编码和 SHA-256；
- [ ] 已递归列出正文引用文件；
- [ ] 目录 seed 已排除模板/缓存/构建输出；TeX 显式 include 的生成文件仍保留在 snapshot/output 闭包；
- [ ] 文件级来源角色只由有限 TeX 注释 marker、辅助路径信号和冻结 caller override 裁决；路径段未被单独当作生成证明；
- [ ] `GENERATED/UNRESOLVED` 文件未形成普通 `PENDING` author unit，override 的 ID/理由/应用文件可审计；
- [ ] 已识别 TeX/Markdown 结构边界；
- [ ] 已区分作者正文和五类保护角色；
- [ ] 每个 unit 都有稳定锚点和唯一 owner chunk；
- [ ] 分块未切断环境、表格、列表、引语或公式；
- [ ] 重叠段只被 owner 编辑一次；
- [ ] 每个 unit 已路由场景并绑定 Voice Profile；
- [ ] 每个可编辑 unit 均有终态；
- [ ] 每个 `DONE/NO_CHANGE` unit 都有当前 paired-quality request；缺失时 gate 为 `BLOCKED`；
- [ ] 每个 `DONE/NO_CHANGE` unit 都有当前 rewrite-intent evidence；standalone v4 span 与 unit diff、
      transaction v3 fragment span 与结构基线到候选的局部 diff 双向覆盖；
- [ ] 每个 standalone bundle 均为 unit v4 且含 `template_field_edit_scope`；普通 REWRITE/全部 NO_CHANGE
      为 null，非 null 仅来自用户对精确 payload 的授权，并已由 finalizer 用冻结 source SHA 物化；
- [ ] 每个 transaction v3 fragment 均含 `template_field_edit_scope`；NO_CHANGE 为 null，非 null scope
      只绑定该 fragment 的派生结构基线，未跨 member 授权；
- [ ] live 模板字段 header 未变；无授权 payload、职责/力度漂移与 protected-span 同形示例分别得到
      `REVIEW/REVIEW/排除`；standalone unit v2/v3 legacy 未被计入当前 bundle-contract PASS；
- [ ] 每个修改 unit 均有可逆 diff；
- [ ] 保护区哈希全部通过；
- [ ] 活动文件追加未混入本轮；
- [ ] 幂等重跑没有同义词 churn；
- [ ] `rendered_review/` 未被用作 second-pass seed，second pass 未被当成质量 clearance；
- [ ] TeX/Markdown 形式检查已执行；
- [ ] baseline 失败与本次引入失败已区分；
- [ ] 乱码和未决位置已报告；
- [ ] 未用抽样结果代替全文覆盖；
- [ ] 未输出内容正确性或检测规避结论。
