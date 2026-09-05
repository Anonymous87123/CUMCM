# 逐节写作底稿

## 作用

`section-authoring-brief.json` 把生成正文前原本分散的三类材料对齐到同一个 TeX 章节：本题题面、数据、代码与结果形成的事实路线；负责队员已经批准的分问预审；59 篇论文中只供观察语言动作的段落编号。它解决的是“检索到了人类论文，但没有把它和当前分问的真实推导接起来”的问题。

这份底稿不生成正文，也不是固定写作模板。JSON 中的 `fact_anchors`、`mathematical_targets`、`selected_route` 和 `human_preflight` 是内部材料，不能依字段顺序改写成四句或四段。真正落笔时按该问实际发生的关系、前问接口、试算、计算或结果组织；没有候选比较就不补候选比较。

## 生成与审计

先完成通过审计的 `style-retrieval-plan.json`、`modeling-workbench.json` 和真人批准的 `reasoning-preflight.json`，再运行：

```powershell
python scripts/prepare_section_authoring_brief.py main.tex --problem-type A `
  --style-plan style-retrieval-plan.json `
  --workbench modeling-workbench.json `
  --preflight reasoning-preflight.json `
  --output section-authoring-brief.json --format text

python scripts/audit_section_authoring_brief.py main.tex `
  --brief section-authoring-brief.json --problem-type A `
  --style-plan style-retrieval-plan.json `
  --workbench modeling-workbench.json `
  --preflight reasoning-preflight.json --format text
```

审计同时核对完整 TeX 文件树、检索计划、工作台、预审以及每节分问归属。任一输入变化都会使底稿失效。问题一的章节只能取得问题一已批准的事实路线；摘要、总体分析等全局章节可以看到全部已批准分问，但只选择当前章节实际需要的信息。

## 写作时怎样使用

1. 从 `current_problem.question_plans` 读取当前题目的事实、数学落点、实际路线及代码/结果来源。事实只能来自这里列出的本题材料。
2. 到 `style-retrieval-plan.json` 读取 `human_style.anchor_ids` 指向的完整段落和相邻上下文；同时读取 `human_style.language_action_profile`，先用其中的主锚点、动作序列、开头/收束类型、公式/图表接口和篇幅分布决定观察重点，再回到原段确认事实怎样进入段落、模型名放在哪里、作者写到哪里停止。主锚点只在本节已入选且与最高分相差不超过 2 分的段落中做低复用选择；相关性不足时仍保留重复，不机械轮换。画像是压缩后的观察索引，不是可粘贴句式。
3. 只迁移语言动作和节奏，不复制原句，不迁移范文中的对象、模型、数值、结论或引用。
4. 按当前证据自然安排段落。不要顺次输出“事实锚点、数学落点、模型选择、结果验证”，也不要让每个分问使用相同连接词和相同段落长度。

全局章节附带全部分问路线不表示必须逐问罗列。摘要只选真正完成的关键模型、数字和检查；问题分析只解释决定后文数学入口的关系；模型评价只写已经暴露的误差源和数据边界。`section_job` 是当前章节的职责提醒，不是可粘贴的句子。

## 逐节 drafting packet

底稿通过后，不能再要求写作者在 `section-authoring-brief.json`、`style-retrieval-plan.json` 和工作台之间自行跳转。先生成逐节输入包：

```powershell
python scripts/prepare_section_drafting_packets.py main.tex `
  --brief section-authoring-brief.json `
  --style-plan style-retrieval-plan.json `
  --output-dir section-drafting-packets --format text

python scripts/audit_section_drafting_packets.py main.tex `
  --brief section-authoring-brief.json `
  --style-plan style-retrieval-plan.json `
  --index section-drafting-packets\packet-index.json --format text
```

每个 `Txx.json` 同时给出当前节可见正文、原始 TeX 片段及哈希、本题已批准事实与路线、主锚完整段落及上下文、辅助段落、语言动作画像和写作契约。检索器先保证章节和题型相关，再在有限分差内主动拉开论文来源、动作序列、开头、表面收束、最后一个段落动作、句群尺度及公式/图表接口。写某一节时必须完整读取对应包，只输出该节正文。`current_draft_tex` 是公式、图表、标签、引用和命令结构的权威；`current_draft` 只便于阅读，不能据此重建或猜测数学内容。依据本题事实从样本中选择一种段落运动；辅助段落只用于观察替代开头、动作次序、节奏和停止位置，不得把多个样本混成统一腔调，不得拼接原句，也不得把范文对象、模型、数字或结论带入本题。

包内字段是输入材料，不是正文提纲。不得按 JSON 顺序依次写成“事实、目标、路线、检验”，也不得为填满字段编造试算、候选淘汰或失败经历。发布审计会锁定索引和每个分包的 SHA-256，并允许同内容的冻结源快照换路径；它只能证明提供给写作者的材料确定且未漂移，不能证明模型确实阅读或文章已经自然。

候选稿完成后，运行：

```powershell
python scripts/prepare_section_drafting_usage.py frozen-source.tex candidate.tex `
  --packet-index section-drafting-packets\packet-index.json `
  --run-id run-001 --author-kind model `
  --output section-drafting-usage.json

python scripts/audit_section_drafting_usage.py frozen-source.tex candidate.tex `
  --packet-index section-drafting-packets\packet-index.json `
  --usage section-drafting-usage.json --format text
```

usage receipt 逐节记录源正文、输入包和候选正文的哈希，并按是否变化标记 `retained` 或 `generated`。它用于防止“包生成了但候选与包完全脱节”以及后续章节漂移；它不是隐藏思维链记录，也不把模型读取行为伪装成可证明事实。若候选标题结构改变到无法与原目标一一对应，应先恢复可追踪的章节结构，不能手填目标编号绕过。
回执还锁定有序的“目标编号—标题—章节职责—分问归属”签名；交换两个章节、改变章节职责或把某一问移到另一节都会被拒绝，即使新的 `T01/T02` 编号集合看起来完整。

## 边界

- `corpus_for_style_only=true`：获奖论文语料不提供本题事实。
- `facts_from_current_problem_only=true`：本题结论必须回到题面、数据、代码、日志和结果。
- `human_preflight_required=true`：模型可以整理材料，不能批准自己的路线。
- `fixed_step_template_forbidden=true`：底稿字段不得成为统一段式。
- `brief_is_not_manuscript_prose=true`：不得把底稿整体贴入论文或附录。

通过该门只证明材料在章节坐标上正确绑定，不能证明模型正确或文风自然。初稿后仍需运行工作台对应审计、语料重合审计、思考复述、受保护改写门和 PDF 检查。
