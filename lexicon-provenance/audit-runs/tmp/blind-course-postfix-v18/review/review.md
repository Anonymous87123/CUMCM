# 短 PATCH 审阅视图

## 交付状态

- 候选交付：`REVIEW/2`
- 机械验证：`REVIEW`
- 硬不变量层：`PASS`
- 成对质量复核：`BLOCKED_BY_MECHANICAL_GATE`
- `humanize_quality_claim_allowed=false`
- `academic_correctness=NOT_EVALUATED`

## 已变化 hunk

### H001

- 决策：`REWRITE`
- 来源字节：`315:336`
- 理由：把独占行的对象标签改为方向切换，保留水平方向合力这一原有职责。

原文：

<pre>水平方向合力为</pre>

替换文本：

<pre>转到水平方向，合力为</pre>

### H002

- 决策：`REWRITE`
- 来源字节：`412:418`
- 理由：由公式对象直接承接前式，减少连续的泛化推进字幕。

原文：

<pre>因此</pre>

替换文本：

<pre>加速度为</pre>

### H003

- 决策：`DELETE_STYLE_SHELL`
- 来源字节：`481:485`
- 理由：删除命令式句首，极值动作仍由同一行其余文字和公式完整表达。

原文：

<pre>令 </pre>

替换文本：

<pre></pre>

### H004

- 决策：`REWRITE`
- 来源字节：`498:503`
- 理由：把命令式搭配改成函数关于变量的直接说明，不改变两个数学对象。

原文：

<pre> 对 </pre>

替换文本：

<pre> 关于 </pre>

### H005

- 决策：`REWRITE`
- 来源字节：`513:526`
- 理由：让后接导数方程直接承担极值条件，避免为公式另配操作命令。

原文：

<pre> 取极值：</pre>

替换文本：

<pre> 的极值条件为：</pre>

### H006

- 决策：`REWRITE`
- 来源字节：`603:609`
- 理由：明确末式来自上一行方程求解，替换泛化的推导推进词。

原文：

<pre>于是</pre>

替换文本：

<pre>解得</pre>

## 未变化的未决 hunk

无。
## 显式冲突对

未声明。
## 覆盖范围与限制

- 状态：`PASS`
- 作用域：`ENUMERATED_HIGH_AND_BOUND_DECLARATIONS_ONLY`
- 任务场景 / 扫描场景：`COURSE` / `AUTO`
- high / selection / conflict：`0` / `6` / `0`
- `semantic_completeness_claim_allowed=false`
- `humanize_quality_claim_allowed=false`
- 本视图不证明完整语义发现、学术正确性、作者身份或外部成对质量 clearance。

## 验证边界

- 交付：`REVIEW/2`
- 言语行为层：`REVIEW`
- 审阅时同时查看 `patch.diff`、`patch.bundle.json`，以及存在时的 `coverage.json`。
