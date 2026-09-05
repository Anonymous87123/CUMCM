---
name: deai-course-notes
description: Audit, rewrite, and generate Chinese course notes, textbook chapters, classroom derivations, worked examples, exam solutions, learning recaps, OCR-based study materials, CET4/CET6 strategy notes, calculus notes, and conic-section notes in a natural teaching voice. Use when Codex must reduce AI-like rigidity or academic overstatement in MD/TEX learning materials while preserving mathematical correctness, theorem conditions, notation, source provenance, question/answer identity, and a reader-friendly step-by-step explanation.
---

# De-AI Course Notes

把课程笔记写成“有人真正讲过、算过、复盘过”的学习材料，而不是压缩版期刊论文、流水线证明或质量验收报告。

## 核心边界

执行以下优先级：

```text
来源忠实与数学正确性
> 读者能否沿着推导复现
> 教学重点是否突出
> 语言自然度与去模板化
> 表面词汇替换
```

允许：

- 解释一步为什么要做；
- 在关键转折处使用“先看”“这里要注意”“回到原式”等轻量教学提示；
- 在章末回顾易错点、识别线索和适用条件；
- 对基础读者补充一个中间式、反例或小量检验；
- 对常规可逆代数进行合理压缩。

不得：

- 把课堂笔记强行改成期刊论文，不要求“创新点、学术贡献、外部验证、研究空白”；
- 为降低 AIGC 痕迹而编造亲身经历、课堂互动、数据、引文或“老师说过”；
- 用口语感掩盖错误，用“显然、容易看出、继续检查”跳过决定结论的步骤；
- 把题干、教材原文、OCR、官方答案和生成解答混成一种作者声音；
- 以编译通过、禁词清零或步骤齐全代替内容正确。

## 先识别场景

仅在材料的主要任务是学习、讲解或训练时使用本 Skill。典型对象包括：

- 课程知识点、课堂板书整理、章节复盘；
- 教材章节、例题、习题解析、答案册；
- 基础或中等深度的数学推导；
- CET4/CET6 词汇、阅读、选项策略和错题笔记；
- OCR/扫描题目的转录、校对与配套讲解；
- 微积分、概率、线性代数、解析几何、圆锥曲线等学习材料。

以下对象应停止套用本 Skill：

- 数学建模竞赛论文、参数拟合、仿真和工程验证报告；
- 期刊投稿、科研创新主张、系统综述和高等级理论论文；
- 纯 OCR 转录任务中未经授权的风格润色；
- 项目 README、代码文档、质量验收单等非教学主文体。

混合文档必须先按段标记：`SOURCE`（题干/教材）、`OCR`、`OFFICIAL`（官方答案）、`RECON`（重建答案）、`EXPLAIN`（生成讲解）、`NOTE`（学习笔记）、`AUDIT`（审校记录）。只对授权段落改写。

## 必须加载的参考资料

每次任务先读 [rules.md](references/rules.md)。再按任务加载：

| 任务 | 必须读取 |
|---|---|
| 全文审计 | [diagnostic-matrix.md](references/diagnostic-matrix.md)、[validation-gates.md](references/validation-gates.md)、[cases.md](references/cases.md) |
| 生成教材/笔记 | [playbook.md](references/playbook.md)、[validation-gates.md](references/validation-gates.md)、[rewrite-patterns.md](references/rewrite-patterns.md) |
| 重写章节/解答 | [rewrite-patterns.md](references/rewrite-patterns.md)、[validation-gates.md](references/validation-gates.md)、[cases.md](references/cases.md) |
| 数学证明、包络、轨迹、全局符号 | [validation-gates.md](references/validation-gates.md)、[cases.md](references/cases.md)、[rewrite-patterns.md](references/rewrite-patterns.md) |
| OCR、题库、答案册 | [playbook.md](references/playbook.md)、[validation-gates.md](references/validation-gates.md)、[cases.md](references/cases.md) |
| 为其他模型编写约束 | [system-prompt-contract.md](references/system-prompt-contract.md) |

在 Windows 上按 UTF-8 读取；遇到乱码段先标记并跳过，不猜测、不用乱码支撑结论。

## 三种模式

### Audit

审计而不直接改文。输出顺序固定为：

1. 文档场景与目标读者；
2. 来源分段表；
3. `Blocking` 数学/来源问题；
4. 教学结构与讲解节奏问题；
5. 带 `NOTE-*` ID 的代表性发现；
6. 2-5 个代表性改写；
7. 验证门结果与未检查项。

不要把所有“AI 痕迹”混成一个分数。分别报告正确性、来源、可学性、结构、语气和机械完整性。

### Rewrite

先锁定题干、公式、符号、标签、引用和答案身份，再重写获授权的讲解段。交付：

1. 修改后的正文；
2. 简短变更账本（位置、规则 ID、动作）；
3. 未解决的数学或来源问题；
4. 未执行的验证项。

遇到实质错误时，明确修正或停在问题处；不得仅把错误证明改得更顺。

### Generate

先定义学习目标、前置知识、目标难度、材料来源和答案身份，再起草。正文优先顺序：

```text
问题/对象 -> 直观或关键观察 -> 必要定义
-> 决定性步骤 -> 常规计算 -> 条件/易错点
-> 小检验或例题 -> 学习回顾
```

不得为了“像教材”自动填满背景、意义、创新、展望等论文式章节。没有来源的题目、数据和引文必须标为自拟，而非伪装成教材原题。

## 统一工作流

### 1. 建立文档契约

记录：课程、章节、读者层级、学习目标、预备知识、题型、允许改写范围、权威入口文件、是否存在官方答案。信息不足时作保守假设并明示，不虚构课程背景。

### 2. 标记来源身份

逐段分类 `SOURCE/OCR/OFFICIAL/RECON/EXPLAIN/NOTE/AUDIT`。OCR 看不清处写 `[无法辨认：页码/位置]`；重建答案写“重建解答”或“参考推导”，不得冒充官方答案。

### 3. 建立事实与符号锁

锁定：题设、定义域、单位、变量类型、量词、分支、公式、答案选项、页码、标签、引用和已知更正。对长证明建立对象账本：

| 符号 | 定义 | 类型/阶数 | 定义域 | 依赖参数 | 允许操作 |
|---|---|---|---|---|---|

### 4. 先验数学，再验风格

依次检查：

```text
题设完整 -> 对象一致 -> 每步等价/蕴含方向
-> 定理条件 -> 定义域/零点/分支 -> 全域覆盖
-> 结论与答案 -> 教学层次 -> 语言自然度
```

数学链断裂时标为 `Blocking`。不要让排版漂亮、解释流畅或禁词清零降低严重级别。

### 5. 找出真正的教学主线

用一句话回答：“这道题或这一节最值得学会的动作是什么？”围绕这个动作分配篇幅：

- 关键构造、符号选择、分支排除、定理条件要展开；
- 可逆展开、重复代入、相同套路的第二遍要压缩；
- 例题只重复章节路线中发生变化的决策；
- 小结回收“何时用、为什么有效、哪里会失效”，不复述目录。

### 6. 改成自然教学语气

让对象做主语，让动作具体。允许轻提示，但每个提示必须带来一种功能：定位、解释、警告、回指或复盘。删除质量管理、游戏攻略、宣传和伪科研话术。不要机械轮换同义词，也不要随机打碎句子。

### 7. 运行场景验证门

至少运行 [validation-gates.md](references/validation-gates.md) 中的来源、数学、教学结构、答案身份和机械完整性门。只声明实际执行并通过的门；未查原图、未核官方答案或未编译时写 `NOT RUN`。

## 严重级别

| 级别 | 含义 | 处置 |
|---|---|---|
| Blocking | 错误题设、来源冒认、对象/符号漂移、无效等价、漏域、结论错误 | 停止受影响段落交付，先修正或请求证据 |
| Major | 关键条件被藏、答案身份不清、主线被模板淹没、章节未接入权威入口 | 优先修复后再润色 |
| Moderate | 句式工整过度、讲解层次均匀、重复路线、小结空泛 | 按教学功能重构 |
| Minor | 局部搭配、标点、轻微冗余 | 最后处理 |

## 不可越级的完成状态

以下状态互不推出：

```text
已转录 != 已对照原图 != 已编译
!= 已核数学 != 已核答案来源 != 已完成教学优化
```

交付时逐项写 `PASS/FAIL/NOT RUN`，不得用“已闭环、已验证、完全正确”代替具体检查对象。

## 最终质量标准

只有同时满足以下条件才通过：

- 读者知道本节要学什么，也能沿步骤复现；
- 决定性步骤比常规运算获得更多解释；
- 数学对象、条件、定义域、量词、分支和结论一致；
- 来源段落与生成讲解明确分开；
- 题干和官方材料未被擅自润色；
- 语气像耐心但克制的教师，不像论文作者、审核员、营销文案或游戏攻略；
- 小结提供可迁移的识别线索和失效边界，不是章节内容复读；
- 只声明实际通过的验证门。

单纯删掉“首先、其次、综上所述”，或随机增加口语词，不算完成。
