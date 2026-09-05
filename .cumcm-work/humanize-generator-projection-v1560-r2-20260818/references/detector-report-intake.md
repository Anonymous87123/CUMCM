# 检测报告标注的纯文风输入边界

## 目录

1. 唯一用途
2. 安全边界
3. 可接受输入
4. 静态提取规则
5. 源文映射
6. 状态与退出码
7. Humanize 接续方式
8. 不得执行的动作
9. 异常与人工复核
10. 复现命令
11. 交付台账

## 1. 唯一用途

AIGC 检测报告在本流程中只有一个作用：提供候选文本范围。报告中的高亮、颜色、标签和分数不构成文风诊断结论，也不证明文本由何种主体生成。

该输入状态记为 `REPORT_INFORMED`，执行的是 `scope-only` 交接：报告不是作者身份或文本来源的证据，只用于指出哪些源文片段需要优先阅读。

从报告提取出的片段仍须回到源文中定位。只有片段在指定源文的规范化视图中恰好出现一次，才可自动转成 `scope: selection`。报告本身没有源文时只能返回 `REVIEW`，不得直接据此改写或宣告完成。

本流程不解释检测率，不预测修改后的数值，不设目标百分比，不提供检测规避策略，也不声称能够改变任何检测系统的判断。

### 1.1 粘贴标红片段的受限路径

用户直接粘贴“标红原文/检测标签”而没有本地 HTML 时，使用
`source_kind=INLINE_SELECTION`。要求用户同时给出明确的原文片段边界；该片段只作为
`scope-only` 候选，不生成 `report_scope.json`，也不声称报告映射通过。固定字段为
`report_scope_check=REVIEW`、`report_path=INLINE_NOT_ARCHIVED`、`coverage=MANUAL_BOUNDARY`，
并按普通内联工件规则运行保护检查。若用户没有给出原文边界，返回 `UNRESOLVED`，不从标签
或分数猜测正文。只有本地 HTML + 源文 + 唯一映射才允许 `PASS/0`。

固定拒绝口径是：不得优化检测分数，不得设置噪声预算，不得提供抗检测评分，不得虚构引用，不得虚构经历。

## 2. 安全边界

提取器只读取本地 HTML 字节并交给 Python 标准库 `HTMLParser`。它不会：

- 打开、请求或跟随 `href`、`src`、表单目标及其他 URL；
- 执行 JavaScript、CSS、内嵌事件或浏览器扩展；
- 读取报告引用的远程资源；
- 上传报告、源文、片段或哈希；
- 根据分数推断作者身份或文本来源；
- 把报告界面、说明文字或评分条改写进作者正文。

`script`、`style` 和 `noscript` 内的内容始终忽略。注释、标签属性和链接地址不进入可见片段。

## 3. 可接受输入

输入由两部分组成：

| 输入 | 必需性 | 作用 |
|---|---|---|
| 本地 HTML 报告 | 自动映射必需 | 提取候选高亮文本；缺失时只能走 `INLINE_SELECTION/REVIEW` |
| 原始源文 | 可选，但自动通过必需 | 验证每个片段的唯一精确规范化位置 |

源文可以是纯文本、Markdown、TeX 或其他可按文本读取的文件。提取器只做字符串定位，不解析其学术内容，不判断报告标注是否正确。

报告和源文优先按 UTF-8 读取。HTML 可使用其 `meta charset` 声明；常见中文本地编码可回退到 GB18030。仍无法读取时返回 `REVIEW`，不猜测乱码内容。

## 4. 静态提取规则

提取以下元素的可见文字：

1. 任意 `<mark>` 元素；
2. `class` 或 `id` 的值含下列任一关键词的元素；
3. 任意 `data-*` 属性名或属性值含下列任一关键词的元素。

固定关键词为：

```text
aigc / risk / highlight / suspicious / detected / flagged
```

匹配不区分大小写。元素内的普通内联标签只贡献可见文字；属性值、URL 和脚本不贡献正文。

片段先折叠连续空白，再按 Unicode NFKC 生成规范化键。规范化键相同的报告片段只保留一项，同时记录 `report_occurrences` 和全部报告位置。去重只消除报告重复展示，不把源文中的多个位置合并为一个可编辑位置。

提取规则是保守的格式规则，不是检测器适配器的完整语义模型。某一厂商使用未知标签时，结果可能为空；此时返回 `NO_FLAGGED_VISIBLE_TEXT/REVIEW`，不得扫描整份报告后自行猜选正文。

## 5. 源文映射

映射使用“唯一精确规范化匹配”：

1. 对报告片段和源文分别执行 Unicode NFKC；
2. 把连续空白折叠为一个普通空格，并去除首尾空白；
3. 在整个规范化源文中查找完整规范化片段；
4. 零次命中记为 `MISSING`；
5. 一次命中记为 `UNIQUE`；
6. 两次及以上命中记为 `AMBIGUOUS`。

映射不做模糊匹配、相似度匹配、分词补齐、OCR 猜测或语义近似。报告片段与源文略有差异时宁可进入 `REVIEW`，也不把相似段落当成原段落。

`UNIQUE` 片段记录源文原始字符偏移、行号和列号。偏移来自规范化字符到原始字符的映射，供后续建立精确 selection；不得使用报告中的显示顺序替代源文位置。

## 6. 状态与退出码

| 状态 | 退出码 | 条件 |
|---|---:|---|
| `PASS` | `0` | 仅限本地 HTML + 源文且全部片段均为 `UNIQUE` |
| `REVIEW` | `2` | 未提供源文、无可见标注、任一片段缺失或歧义、输入不可读 |

本工具没有“部分片段通过即可整体通过”的状态。若十个片段中九个唯一、一个歧义，总体仍是 `REVIEW/2`。可以在人工确认后只接续九个唯一片段，但交付必须明确剩余歧义位置，不得说报告范围已全部处理。

`coverage.ratio` 等于唯一映射片段数除以去重片段总数。它是映射覆盖率，不是 AIGC 分数、文风质量分数或完成度替代品。

## 7. Humanize 接续方式

提取器 `PASS/0` 后，按以下方式接入纯文风工作流：

1. 固定报告和源文 SHA-256；
2. 将每个 `UNIQUE` 的源文区间登记为 `scope: selection`；
3. 报告标签、分数和 UI 文本登记为 `report-metadata`，不进入作者正文；
4. 对 selection 重新执行 Humanize 自身的词项扫描与连续阅读；
5. 报告标注只决定“看哪里”，不决定“必须改什么”；
6. 自然段落可以返回 `NO_CHANGE`；
7. 改写后运行 `validate_humanize_output.py <source> <after> --report-scope <extractor-json>`；
8. 验证器按 scope 中的绝对 `report_path` 重新静态解析本地报告；report SHA、coverage 和 fragments 必须与保存 JSON 一致，手工扩大 range 的 scope 不能通过重放；
9. 只有 `report_scope_check=PASS` 才证明当前成稿可由 UNIQUE selection 替换形成，未标注前缀、片段间文本和后缀保持不变；普通 REWRITE 的 `PASS` 不能替代这一范围门；
10. 继续执行统一不变量、言语行为和词项复扫，任一层未通过都不能宣告完成。

检测报告不能替代 `DIAGNOSE`。Humanize 诊断必须依据文本本身的句式、节奏、段落结构和 Voice Profile，而不是依据报告颜色或分数。

## 8. 不得执行的动作

不得以本输入流程为依据执行以下动作：

- 承诺降低检测率、达到某个百分比或通过某个平台；
- 估计“改前/改后 AIGC 率”；
- 为打乱统计分布插入错字、病句、随机标点或所谓噪声；
- 按报告分数机械决定改写强度；
- 把没有映射到源文的报告文本写入源文；
- 为让标注句更“像人”虚构事实、引用、数据、经历、意外或作者立场；
- 删除、改写或伪造引用来处理模糊归因；
- 将报告供应商的说明文字误当成作者正文；
- 使用模糊匹配悄悄消解 `MISSING` 或 `AMBIGUOUS`。

若用户同时要求纯文风改写和检测规避，只执行能明确隔离的纯文风 selection；对分数、目标率和规避承诺明确拒绝。无法隔离时返回 `UNRESOLVED`，不扩大任务。

## 9. 异常与人工复核

### 9.1 无源文

输出片段和报告 SHA，但所有片段为 `NOT_MAPPED_NO_SOURCE`，总体 `REVIEW/2`。用户可据此提供准确源文，不能把报告复制文本直接当成源文。

### 9.2 缺失

`MISSING` 常见于报告对空格、标点或引用做了非显示转换，也可能说明报告与源文版本不同。核对版本和 SHA；不要自动改成相似匹配。

### 9.3 歧义

`AMBIGUOUS` 表示同一完整规范化片段在源文中出现多次。必须用章节、行号或更长原文消歧。报告顺序不能证明它对应哪一次出现。

### 9.4 报告无标记

先确认厂商是否使用了不在固定规则中的结构。扩展解析规则时必须增加脱敏 fixture，说明匹配的属性或标签；不要退化为“抽取 HTML 中全部中文”。

### 9.5 编码失败

保留输入文件，不用替换字符继续。可以由用户另存为 UTF-8 后重跑；未重跑前保持 `REVIEW`。

## 10. 复现命令

只提取报告候选，不形成可自动使用的 selection：

```powershell
python "$skillRoot\scripts\extract_detector_report_scope.py" report.html
```

对指定源文做唯一精确规范化映射：

```powershell
python "$skillRoot\scripts\extract_detector_report_scope.py" report.html `
  --source thesis.tex `
  --output report_scope.json

python "$skillRoot\scripts\validate_humanize_output.py" thesis.tex thesis.revised.tex `
  --scene GENERAL `
  --report-scope report_scope.json `
  --format json
```

提取器标准输出始终为 JSON。指定 `--output` 时同一 JSON 也写入目标文件。调用方必须使用两个进程各自的退出码，并核对验证器顶层 `delivery_gate_status` 与 `report_scope_check`；不得只搜索任一输出中的 `PASS` 字样。

## 11. 交付台账

报告输入处理至少保存下列字段：

```text
status / exit_code
report_path / report_sha256 / report_encoding
source_path / source_sha256 / source_encoding
coverage.total_fragments
coverage.uniquely_mapped
coverage.missing
coverage.ambiguous
coverage.not_mapped_no_source
fragment.index / text / normalized_text
fragment.report_line / report_column / triggers / report_occurrences
fragment.mapping_status / source_occurrences
fragment.source_start / source_end / source_line / source_column
review_reasons
```

原始报告分数可以由调用方作为不参与决策的外部元数据另存，但本提取器不解析、不转述、不比较该分数。台账只证明“哪些静态可见片段被提取、是否唯一映射到哪个源文版本”，不证明文本来源，也不证明 Humanize 已执行。
