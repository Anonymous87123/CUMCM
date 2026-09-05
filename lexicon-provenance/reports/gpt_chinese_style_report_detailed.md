# GPT/Codex 中文风格深度语料报告

生成时间：2026-07-10T04:23:22.142167+00:00  
输入快照：`C:\Users\Lenovo\.codex\reports\gpt_chinese_style_2026-07-10.snapshot.json`  
详细数据目录：`C:\Users\Lenovo\.codex\reports\gpt_chinese_style_2026-07-10`

## 1. 执行摘要

本报告从 1187 个真实聊天文件中提取了 **117,696** 条中文 assistant 正文（共 44,831,639 个去代码正文字符）。与简版报告不同，本次结果同时按模型、人设、时间、消息阶段、来源与任务类型统计，并保留可复现的输入快照、CSV 与 SVG 图表。

观察对象是 Codex 工程代理环境中的 GPT 输出，不是脱离系统提示和任务构成的“裸模型人格”。因此，所有模型差异均只描述本地语料中的可观察差异，不做能力或因果归因。

## 2. 数据审计与隐私处理

| 指标 | 数值 |
|---|---:|
| 扫描 JSONL 文件 | 1,193 |
| 识别为聊天文件 | 1,187 |
| 无 session 元数据而排除 | 6 |
| 中文 assistant 消息 | 117,696 |
| 非中文 assistant 消息 | 482 |
| JSON 解析错误 | 0 |
| 快照后发生变化的文件 | 2 |
| 精确重复正文 | 59,548 |
| 证据节选数量 | 120 |

仅 assistant 的 `output_text` 进入语料。用户、system、developer、reasoning、工具调用与工具输出没有进入统计或证据附录。所有节选均已执行密钥、Token、JWT、私钥、密码、连接串、邮箱、手机号、IP 与用户目录路径脱敏。

## 3. 样本构成

### 消息阶段

| 阶段 | 消息数 |
|---|---|
| commentary | 87920 |
| final_answer | 28950 |
| unspecified | 826 |

### 模型与人格

| 模型 | 人格 | 消息数 |
|---|---|
| gpt-5.4 | friendly | 64940 |
| gpt-5.4 | pragmatic | 6154 |
| unknown | unknown | 5691 |
| gpt-5.5 | friendly | 36099 |
| gpt-5.5 | pragmatic | 4738 |
| gpt-5.4-mini | friendly | 43 |
| gpt-5.4-mini | pragmatic | 6 |
| gpt-5.6-sol | pragmatic | 25 |

任务类型是依据最近有效用户任务的中英文规则词典推定，仅保存类别而不保存用户正文；未分类和多标签情况均保留在 `task_classification_summary.csv`。

| 任务类别 | 主标签消息 | 占比 |
|---|---|---|
| debugging | 19494 | 16.6% |
| design | 5737 | 4.9% |
| documentation | 12090 | 10.3% |
| implementation | 4564 | 3.9% |
| operations | 4146 | 3.5% |
| research | 8567 | 7.3% |
| review | 4144 | 3.5% |
| testing | 9144 | 7.8% |
| unknown | 49810 | 42.3% |

## 4. 全局语言画像

平均每条去代码正文 380.9 字符，平均 6.3 个句子，汉字占去代码正文的 33.7%。Markdown 格式、标点和句法特征见 `metrics.json`；阶段长度分布见 `figures/phase_length_distribution.svg`。

这批文本的主要味道仍然是工程代理式的“动作 - 状态 - 证据 - 下一步”：中间消息偏短，频繁播报检查和确认；最终答复偏长，更集中使用结论、限制、验证、建议和收尾邀请。`group_comparisons.csv` 给出每个说法的样本量、Wilson 95% 区间和相对总体差值。

## 5. 数据驱动高频短语

以下短语来自去代码正文的连续汉字 2-4 gram，按消息覆盖率排序；它们不是中文分词结果，且已过滤纯功能字串。

| 短语 | 消息覆盖率 | 出现次数 |
|---|---|---|
| 现在 | 33.4% | 60094 |
| 直接 | 24.6% | 41867 |
| 不是 | 24.1% | 53159 |
| 继续 | 23.7% | 38232 |
| 没有 | 22.6% | 36299 |
| 编译 | 19.4% | 28107 |
| 我先 | 17.2% | 20514 |
| 下一 | 17.2% | 23357 |
| 我会 | 16.5% | 20742 |
| 当前 | 15.5% | 26012 |
| 一步 | 15.1% | 24081 |
| 正文 | 14.6% | 27776 |
| 结果 | 14.5% | 27095 |
| 公式 | 14.4% | 36287 |
| 确认 | 14.3% | 18281 |
| 这样 | 14.2% | 19621 |
| 结构 | 13.9% | 27189 |
| 文件 | 13.6% | 22797 |
| 先把 | 13.2% | 16569 |
| 改成 | 12.8% | 22182 |
| 一轮 | 12.5% | 18348 |
| 而是 | 12.4% | 23369 |
| 下一步 | 11.9% | 15324 |
| 出来 | 11.8% | 15898 |
| 里的 | 11.4% | 15896 |
| 说明 | 11.1% | 18575 |
| 一下 | 10.6% | 13068 |
| 结论 | 10.5% | 17953 |
| 所以 | 10.5% | 18491 |
| 这些 | 10.4% | 16207 |

完整排行、出现次数、文档覆盖数、模型区分度和搭配数据见 `phrase_rankings.csv`。这部分比人工指定的“我先、下一步、核心、关键”等词表更能显示实际反复出现的短语。

## 6. 修辞结构与功能词簇

脚本分别统计第一/第二人称、完成态、未来承诺、状态限定、建议、邀请、证据、风险约束、实现、结论、保守限定、对比和行动词簇，并用规则识别以下结构：

- `先……再……`：步骤化与过程可预期性。
- `不是……而是……`：根因澄清和对照论证。
- `为了避免/确保……`：风险控制的理由前置。
- `当前/目前/现在……但……`：已有结果与残余缺口并置。
- `结论/核心/关键……验证/测试/结果……`：结论与证据联结。

模型通常不是单纯“爱说某个词”，而是在反复使用一整套工程沟通框架：先安排动作，随后给状态和证据，最后限定边界并提出下一步。证据型词簇、风险型词簇和行动型词簇共同构成了这种可靠但略带工单感的中文。

## 7. 分组差异

只有分组样本至少 500 条且与总体差异至少 3 个百分点的项才被标为“明显差异”。这样可避免小样本模型、人设或月份被过度解释。

| 维度 | 分组 | 特征 | 覆盖率 | 相对总体 | 样本 |
|---|---|---|---|---|---|
| phase | commentary | action | 28.2% | -8.0% | 87920 |
| phase | commentary | completion | 30.2% | -8.9% | 87920 |
| phase | commentary | conclusion | 16.7% | -9.3% | 87920 |
| phase | commentary | contrast | 16.6% | -9.7% | 87920 |
| phase | commentary | evidence | 33.9% | -5.5% | 87920 |
| phase | commentary | first_person | 50.9% | +3.8% | 87920 |
| phase | commentary | future_commitment | 26.0% | -5.0% | 87920 |
| phase | commentary | hedging | 4.8% | -3.9% | 87920 |
| phase | commentary | implementation | 16.7% | -3.4% | 87920 |
| phase | commentary | invitation | 0.0% | -4.1% | 87920 |
| phase | commentary | recommendation | 4.6% | -9.6% | 87920 |
| phase | commentary | risk_constraint | 17.4% | -4.5% | 87920 |
| phase | commentary | second_person | 1.3% | -9.1% | 87920 |
| phase | commentary | state_scope | 37.0% | -8.5% | 87920 |
| phase | commentary | contrastive | 4.3% | -5.9% | 87920 |
| phase | commentary | state_gap | 2.3% | -3.3% | 87920 |
| phase | final_answer | action | 60.0% | +23.8% | 28950 |
| phase | final_answer | completion | 67.0% | +27.8% | 28950 |
| phase | final_answer | conclusion | 54.2% | +28.3% | 28950 |
| phase | final_answer | contrast | 55.9% | +29.6% | 28950 |
| phase | final_answer | evidence | 56.4% | +17.0% | 28950 |
| phase | final_answer | first_person | 35.3% | -11.7% | 28950 |
| phase | final_answer | future_commitment | 46.8% | +15.7% | 28950 |
| phase | final_answer | hedging | 20.8% | +12.0% | 28950 |
| phase | final_answer | implementation | 30.0% | +10.0% | 28950 |
| phase | final_answer | invitation | 16.8% | +12.6% | 28950 |
| phase | final_answer | recommendation | 43.5% | +29.3% | 28950 |
| phase | final_answer | risk_constraint | 35.8% | +13.8% | 28950 |
| phase | final_answer | second_person | 38.1% | +27.7% | 28950 |
| phase | final_answer | state_scope | 71.5% | +26.0% | 28950 |
| phase | final_answer | conclusion_evidence | 9.0% | +5.7% | 28950 |
| phase | final_answer | contrastive | 28.2% | +18.0% | 28950 |
| phase | final_answer | state_gap | 15.9% | +10.2% | 28950 |
| phase | final_answer | stepwise | 24.5% | +4.2% | 28950 |
| phase | unspecified | action | 50.2% | +14.1% | 826 |
| phase | unspecified | completion | 14.6% | -24.5% | 826 |
| phase | unspecified | conclusion | 19.7% | -6.2% | 826 |
| phase | unspecified | contrast | 16.9% | -9.3% | 826 |
| phase | unspecified | evidence | 29.8% | -9.6% | 826 |
| phase | unspecified | first_person | 52.3% | +5.2% | 826 |
| phase | unspecified | future_commitment | 18.5% | -12.6% | 826 |
| phase | unspecified | hedging | 3.1% | -5.6% | 826 |
| phase | unspecified | implementation | 28.5% | +8.4% | 826 |
| phase | unspecified | risk_constraint | 16.3% | -5.6% | 826 |
| phase | unspecified | state_scope | 41.0% | -4.5% | 826 |
| phase | unspecified | contrastive | 3.8% | -6.4% | 826 |
| model | gpt-5.4 | completion | 42.6% | +3.4% | 71094 |
| model | gpt-5.4 | future_commitment | 25.9% | -5.2% | 71094 |
| model | unknown | action | 68.2% | +32.0% | 5691 |
| model | unknown | completion | 77.9% | +38.7% | 5691 |

阶段长度、模型/人格的证据用语、月度第一人称行动用语、最终答复修辞结构分别对应：

- `figures/phase_length_distribution.svg`
- `figures/model_personality_heatmap.svg`
- `figures/monthly_trend.svg`
- `figures/pattern_comparison.svg`

时间变化必须与模型、人设和任务构成一起理解。某月某个表达升高，可能来自当月任务集中于代码排错或切换到不同人格配置，而不能单独归因为模型语言能力变化。

## 8. 模板化与 AI 痕迹

从精确正文重复、句首/句尾短语和高覆盖 n-gram 可以区分两类重复：一类是工程任务需要的稳定交付模板，例如“确认、验证、下一步”；另一类是可能影响自然度的固定路标，例如反复的“我先”“我已经”“如果你愿意”。

较自然的改写原则是：简单任务省略过程播报；用具体测试或文件事实替换抽象“闭环/落地”；只在确实互斥时使用“不是 A，而是 B”；有明确后续价值时再使用邀请式收尾。保留证据和边界意识，但减少重复的状态词，通常能让文本更像经验丰富的人类工程师。

## 9. 真实脱敏原文证据

以下是从 assistant 正文中分层抽样的真实节选。它们用于展示统计项在原始语言中的实际形态，不代表所有对话，也不包含用户消息或工具输出。

### 证据 1

`2026-04-20 | gpt-5.4 | friendly | commentary | debugging | session:78145e61124ba72c8baa`

> 我已经把可用结果源收出来了。最适合交付的不是单个 csv，而是一个 xlsx 工作簿：一个文件、多个工作表，能同时放三问的汇总结果、样本级输出和 ID1/2/3 详细方案，不会把不同问题硬挤进一张表里。下面我先核实几个关键结果表的字段和规模，再直接生成最终提交文件。

### 证据 2

`2026-05-24 | gpt-5.4 | friendly | commentary | debugging | session:d1a0d3c0ddce637f2d80`

> 我已经把证据拆出来了。下一步我把它整理成一版可以直接转给 MDG/CHECC/CCFR3/CBCCO/CMAES 相关同事的排查说明：明确“不是我们改了你们的管线”，而是“我们外层拿来跑时，在 F3 这片上这 3 条都抛了同一个 MemoryError，因此后续字段没法完整生成”。我会把“缺了什么字段”与“为什么缺”分开讲清楚。

### 证据 3

`2026-06-09 | gpt-5.4 | friendly | commentary | debugging | session:f7c32450735bbeefeb19`

> 核心代码已经接上了，我先跑一次全新的 Qt CMake 配置，确认 edusys 和 edusys_gui 两个目标都能被生成出来。构建如果再卡，我会优先从配置和生成文件里判断问题，不让你反复撞命令。

### 证据 4

`2026-04-28 | gpt-5.4 | pragmatic | commentary | design | session:4d8b181ad9a43f9805ac`

> 脚本确认了两件事：   1. 这批任务的 runs.csv/summary.csv 是**全部 repeats 跑完后才一次性写盘**。所以现在看不到中间 CSV，不代表卡住。   2. 正常情况下，stdout 本来应该有每个 repeat 的 [repro] ... repeat=... 进度行；但这次 out.log 为空，像是 Start-Process 重定向下的缓冲没刷出来。   我继续查 cec profile 配置和旧批次时间，给你估剩余时长。

### 证据 5

`2026-05-10 | gpt-5.4 | friendly | commentary | design | session:c7ec16ea78c5c2eb2624`

> 我已经把目标区段重新扫过一遍。接下来补读几个关键定义与代表短题的原文措辞，确保建议不是泛泛而谈，而是能直接映射到现有讲义段落和题解写法。

### 证据 6

`2026-06-01 | gpt-5.4 | friendly | commentary | design | session:1eeaee20a9f07e6669d2`

> 我已经定位到一个关键问题：报告正文前半已经统一成 59/590，但后面的深度附录里还有一批旧的 56 口径结论混在里面。现在我把这些旧结论逐条对照新结果，再统一回写 md。

### 证据 7

`2026-04-27 | gpt-5.4 | friendly | commentary | documentation | session:4d8b181ad9a43f9805ac`

> 我已经看到这份外部笔记的骨架了，它的核心不是重复我们现在的理论，而是提出了一个很实用的“下一步算法方向”： 把 DG2 这类 linkage 学习和“曲率/尺度估计”联合起来，让分组同时兼顾“不要切断耦合”和“不要把条件数撑爆”。我再把正文读细一点，看看哪些观点能直接迁移进我们的 README、notes 和后续实验设计。

### 证据 8

`2026-05-12 | gpt-5.4 | pragmatic | commentary | documentation | session:d1a0d3c0ddce637f2d80`

> 我已经确认两件事：一是这两个说明必须改成“站在整个仓库架构里解释外层入口”，二是它们现在虽然内容多，但确实还不够贴合组内分工、文档体系和当前正式矩阵。接下来我再补一轮代码层面的核对，锁定需要在文档里明确写死的真实接口和边界。

### 证据 9

`2026-06-01 | gpt-5.4 | friendly | commentary | documentation | session:1eeaee20a9f07e6669d2`

> 数据和 tex 已经刷新好了，PDF 这次不是内容错误，而是 xdvipdfmx 打开旧 pdf 输出文件时失败，像是文件被占用或锁住。这个很像临时文件锁问题；我会先核一下 pdf 是否已存在，再用一个新的输出文件名编译，避免和旧文件打架。

### 证据 10

`2026-04-18 | gpt-5.4 | friendly | commentary | implementation | session:78145e61124ba72c8baa`

> 这次要纠正一个关键误解：你贴来的“指导教授”提醒原则上是对的，但**我们这份问题二里的数字并不是瞎编的**，而是我已经在本地真实跑出来并写入结果目录的。为了把这件事彻底钉死，我现在不去“重做一版假的代码”，而是直接把问题二脚本补成“论文证据导出版”，把正文里用到的每个数字都单独导出成可复核 CSV。

### 证据 11

`2026-05-10 | gpt-5.4 | friendly | commentary | implementation | session:c7ec16ea78c5c2eb2624`

> 我已经确认这份讲义本身就大量使用 note、definition、property、solution 等环境，所以“把学生提问融进正文”最自然的办法大概率不是改骨架，而是在这些现有节点上加一层自学导向的解释。   我再读几段关键章节的原文风格，随后把“问题应该插在哪、用什么口吻、哪些题解最值得扩”落成可执行清单。

### 证据 12

`2026-06-01 | gpt-5.4 | pragmatic | commentary | implementation | session:1eeaee20a9f07e6669d2`

> 正文已经进一步去掉了“历史留痕”和复核过程说明，页数也从 26 页降到 24 页。现在卡住的不是 TeX 本身，而是原 PDF 文件被占用，导致 xdvipdfmx 不能覆盖写回同名文件；我先改成输出到一个新文件，保证你能先看到新版结果。

### 证据 13

`2026-04-19 | gpt-5.4 | friendly | commentary | operations | session:a6a890fd025b5efba52f`

> 正文已经更新为四层目标了。我现在重跑脚本，检查四层字典序是否改变任何输出方案；如果数值不变，也会在结论里说明这是“目标定义更严谨，但当前参数下最优策略拓扑保持不变”。

### 证据 14

`2026-05-10 | gpt-5.4 | friendly | commentary | operations | session:0a816d78d11b526a0386`

> 我在把高风险片段按文件分桶，刚才那轮统计命令没正常吐出结果，我会换成更直接的读取方式继续。现在已经能确定：special.tex 和 chap10.tex 的问题最重，不只是“风格夸张”，而是已经影响到题解体裁本身。

### 证据 15

`2026-06-09 | gpt-5.4 | friendly | commentary | operations | session:f7c32450735bbeefeb19`

> 源码边界很清楚：StatsService 只回结构化结果，ReportExporter 单独负责落盘，菜单层只做 I/O，和 claude.md 里“未来 GUI 直接复用 service 层”的思路是对上的。现在我再补一轮文档和仓库差距检查，看看还有没有“看起来完成了，但答辩时容易被问住”的地方。

### 证据 16

`2026-04-19 | gpt-5.4 | friendly | commentary | research | session:78145e61124ba72c8baa`

> 我已经核对了当前稿子。结论比较明确：外部建议里真正值得采纳的，不是那些夸张包装，而是三点很具体的工程改进： 1. 问题分析 用“难点 + 策略”式结构，提升扫读效率。 2. 模型假设 明确补上“无后效性 / 状态诱导成本”这类为 DP 建模兜底的假设依据。 3. 符号说明 改成分组表，并把排版和下标规范做得更稳。  我不会整段照搬它们的版本，而是会按你这篇文章现有语气重写成更克制、统一的版本，然后回读检查和正文是否完全对齐。

### 证据 17

`2026-05-23 | gpt-5.4 | friendly | commentary | research | session:4d8b181ad9a43f9805ac`

> 我已经定位到两件关键事实了：实验不是卡死，而是在往外吐结果；文稿的大空白大概率就是 rotated_block_truncation.pdf 这张跨双栏浮动图和 \FloatBarrier 一起造成的。我接下来会同时处理这两个点。

### 证据 18

`2026-06-06 | gpt-5.4 | friendly | commentary | research | session:a4ca951a050a69a21624`

> 我已经把第一层残留压下去了，现在进入真正的“隐蔽句式”收尾阶段。下一步我会优先处理那些看起来不明显、但读起来还是像机器在汇报步骤的地方，尤其是 chap6/chap7 里还在重复冒头的标题句和过渡句。

### 证据 19

`2026-05-24 | gpt-5.4 | friendly | commentary | review | session:b0dd9021f8a272b17fb3`

> 我已经把关键页核到了图像级，接下来直接整理成可转 LaTeX 的中文底稿，并同步补齐逐页 checklist 与总风险说明。编辑前不会碰 elegantbook2.tex，也不会动别人现有文件。

### 证据 20

`2026-06-01 | gpt-5.4 | friendly | commentary | review | session:0801fe8e010ecb09732a`

> 第 1 批已经回来了，10 套题的答案都被独立确认，无修正。我现在继续等其余批次回传，同时会快速看一眼回传格式，确保后面的自动汇总不会卡住。

### 证据 21

`2026-04-27 | gpt-5.4 | friendly | commentary | testing | session:d1a0d3c0ddce637f2d80`

> 我已经确认当前只动了外层文件，方向没越界。下一步我直接做编译和小规模跑通检查，同时补看 utils.py 里新加的摘要/导出函数，避免“写了但挂在导出链路上”的情况。

### 证据 22

`2026-05-10 | gpt-5.4 | friendly | commentary | testing | session:4aee99422cccf4626f1a`

> 我已经能确认一件很关键的事：demo_test.py 不是“随便写的测试脚本”，它其实是你这条工作线的统一编排入口；utils.py 也不是普通工具箱，而是记录、汇总、导出、可追溯性这一整层基础设施。我再补上精确的函数边界和引用关系，这样后面给你的建议会更稳。

### 证据 23

`2026-06-06 | gpt-5.4 | friendly | commentary | testing | session:a4ca951a050a69a21624`

> 我把当前还能改得更自然的几句直接收掉，优先是章节导语和那些“说明/验证/这意味着”的句子。这样改动小，但能明显把 AI 腔再往下压一层。

### 证据 24

`2026-04-27 | gpt-5.4 | friendly | commentary | unknown | session:4d8b181ad9a43f9805ac`

> 有个好消息：F5/F13/F14 这三批第二梯队 paper 已经先落出完整结果了，现在只剩 F9 还没落、F2/F3 还在跑。   我接下来会启动第一轮方法线 pilot，不过我会控制并行度，先开两路，再看负载，不把机器当烤箱。

### 证据 25

`2026-05-10 | gpt-5.4 | friendly | commentary | unknown | session:2e983faa3d9315f94b9c`

> 我再补一层“工作树视角”：当前分支不只是“有 GUI 代码”，还有一批未提交修改集中在 CMakeLists.txt、gui_main.cpp、三个主窗口和新增对话框上。这通常意味着核心框架已经搭起来了，但还在做收口和验证，所以我会把“已实现”和“仍在施工”分开给你。

### 证据 26

`2026-06-01 | gpt-5.4 | friendly | commentary | unknown | session:0801fe8e010ecb09732a`

> 这轮我先接着深挖“题号之间的结构信息”，重点不是再做单题均值，而是找更能转化为实战策略的联动规律、条件规律和整套题轨迹模式。先把现有分析产物、脚本和补充结果扫一遍，确认哪些已经跑过，哪些还值得继续往下挖。

### 证据 27

`2026-05-25 | gpt-5.4 | friendly | final_answer | debugging | session:4d8b181ad9a43f9805ac`

> 我已经把这段改成“定义先行”了，见 [paper2.tex](/d:/2026-BYD-arxiv/paper/paper2.tex:175)。现在它不再重复引言的动机，而是直接交代了初始分组、非可分变量组、SCCD 的输入输出，以及下一步要回答的核心问题。  下一句建议直接接： “要完成这一步判断，关键在于两类信息：一类说明组内哪些联系不能被轻易打断，另一类说明该组内部的局部尺度是否已经失衡。”

### 证据 28

`2026-05-25 | gpt-5.4 | friendly | final_answer | design | session:4d8b181ad9a43f9805ac`

> 可以，下面是一版可直接并入正文的最终稿：  如果你愿意，我下一步可以把 \subsection{流程与复杂度} 再压得更像论文原文一点，统一成你前面那种语气。

### 证据 29

`2026-06-09 | gpt-5.4 | friendly | final_answer | design | session:f7c32450735bbeefeb19`

> 云服务器里只是缺 cmake，这一步很好处理。你现在是 root，直接装，不用 sudo`：  装完先确认：  然后在项目根目录只构建 CLI，不构建 Qt：  构建成功后，先跑自检，再进交互演示：  如果你愿意，我们下一步可以直接一起把“老师演示时在云端终端里依次输入什么”也整理成一套最稳的 CLI 演示顺序。

### 证据 30

`2026-04-20 | gpt-5.4 | friendly | final_answer | documentation | session:78145e61124ba72c8baa`

> 已按你的要求改掉：现在不再写“注：原文献标注为 LDL……”，而是直接表述为“的 TC 、 TG 、 LDL-C”。  修改位置在 `final/article.tex`。没有编译。

路径审计：原始会话记录指向 `E:\BaiduNetdiskDownload\2026MathorCup-C\MT01\final\article.tex`，该路径当前不可用；未猜测替代位置。

### 证据 31

`2026-05-10 | gpt-5.4 | friendly | final_answer | documentation | session:b351e5996fdac059afd6`

> 已写好 [fingerprint-readme.md](D:/Probet/fingerprint-readme.md:1)，把思路、路由、随机 OOD 数据、当前效果和运行命令都整理进去了。我用了 ASCII 文件名，方便跨平台；如果你想改成你说的那个中文破折号名字，我也可以顺手改。

### 证据 32

`2026-05-25 | gpt-5.4 | friendly | final_answer | implementation | session:4d8b181ad9a43f9805ac`

> 可以，就接你这段往下收，不用再开新意思了。后面这一段我建议你写成这样：  有两个小地方我也顺手提醒你一下：  1. 你正文里的 "可以细化" 最好改成中文引号 “可以细化”。   2. 对 refinable 块而言 这句如果你嫌英文夹着突兀，也可以改成 对已经通过上一节判定的变量组而言。  如果你愿意，我下一步就把 \subsection{流程与复杂度} 也直接给你起草出来。

### 证据 33

`2026-05-11 | gpt-5.4 | pragmatic | final_answer | operations | session:34ef2433a5b6fec776fb`

> 已处理完。现在用 latexmk -xelatex ... -jobname=elegantbook2_chk 复核后，日志里没有 hyperref、tcolorbox、Overfull/Underfull \hbox 警告。  主要改动是：清理了标题里的 PDF 字符串数学残留，把几段长公式拆成多行，并给 introduction 环境加了局部 \sloppy，同时补了约束最优化前的分页。

### 证据 34

`2026-05-23 | gpt-5.4 | friendly | final_answer | research | session:4d8b181ad9a43f9805ac`

> 对，这里缺的不是换个词，而是把“**为什么偏偏是对角元**”说出来。  最稳的改法，是先把 **非对角元 vs 对角元** 的分工点明。这样读者就不会觉得你突然挑了一个量。  我建议直接改成：  把它接回你前一句，整段会顺很多：  这样有三个好处：  1. 对这一目的 这种悬空说法没了   2. 为什么是对角元 说清楚了   3. 后面接“一维二阶中心差分去近似对角元”就自然了  下一句其实就可以顺着写成：  如果你愿意，我可以继续把这后面两三句一口气帮你收顺。

### 证据 35

`2026-05-30 | gpt-5.4 | friendly | final_answer | review | session:659ba8205788347ce914`

> 继续压了一大批，已经把第 2、3 章里一串短 \[...\]、短推导块和若干解答里的短显示式压回正文或合并了，同时把第 3 章那处已知过宽点 14634–14641 拆成了更稳的两行 align* 加内联结论，方向是对的。  还没编译，这次按你的要求先继续积累改动再统一编译。下一步我会顺着第 3 章后半和第 4 章继续按同样节奏扫下一批，把还能安全压的短公式再吃一轮。

### 证据 36

`2026-06-07 | gpt-5.4 | friendly | final_answer | review | session:659ba8205788347ce914`

> 继续压了一大批，已经把第 2、3 章里一串短 \[...\]、短推导块和若干解答里的短显示式压回正文或合并了，同时把第 3 章那处已知过宽点 14634–14641 拆成了更稳的两行 align* 加内联结论，方向是对的。  还没编译，这次按你的要求先继续积累改动再统一编译。下一步我会顺着第 3 章后半和第 4 章继续按同样节奏扫下一批，把还能安全压的短公式再吃一轮。

### 证据 37

`2026-05-11 | gpt-5.4 | friendly | final_answer | testing | session:0a816d78d11b526a0386`

> 已收口完成：solution 语气统一到更短、更稳的数学证明风格，重点压平了 chap1.tex、chap2.tex、chap3.tex、chap4.tex 的讲解腔，并把 chap3.tex 的重复解答收掉了；chap4.tex、chap8.tex 的局部标题也统一成了直述式。  main.tex 已重新编译通过。当前只剩少量 Overfull/字体警告，没有硬错误。

### 证据 38

`2026-04-19 | gpt-5.4 | friendly | final_answer | unknown | session:78145e61124ba72c8baa`

> 推荐标题：  这个标题最贴合你的正文，因为它同时覆盖了三条主线：  体质：九种中医体质、痰湿质重点人群   代谢：血脂、血糖、尿酸、BMI 等生化指标   活动：ADL/IADL 活动能力与干预耐受度   风险预警与动态干预优化：对应问题二、问题三的核心任务  备选标题：  我最建议用第一个：   **基于体质-代谢-活动多维融合的中老年高血脂症风险预警与动态干预优化**  它比原题更有论文特色，又不会过度包装。

### 证据 39

`2026-05-25 | gpt-5.4 | friendly | final_answer | unknown | session:4d8b181ad9a43f9805ac`

> 会，但不是当主判据。  它现在的角色是“解释层”而不是“决策层”: - 预备知识里用它说明什么叫局部尺度失衡 - 方法里用 span(C) / overflow(C) 去落地 - 讨论或结果分析里再用它解释为什么这个代理量是合理的  也就是说，**条件数不再直接出现在四类判定里**，但会作为理论支撑再提一次。   如果你愿意，我下一步可以帮你把“局部尺度依据”那一段顺手写成一版，把条件数和 span(C) 的关系收住。

### 证据 40

`2026-06-09 | gpt-5.4 | friendly | final_answer | unknown | session:bb79929612c37c3df180`

> 可以，直接用这两组命令就行。既然 oj1.cpp 已经确认是 **GBK 源码 + UTF-8 终端输出**，oj2.cpp 和 oj3.cpp 先按同样方式处理最稳。  oj2.cpp：  如果要用输入重定向：  oj3.cpp：  如果也要喂输入文件：  如果其中某一个编完还是乱码，那就说明它和 oj1.cpp 不一样，不是 GBK 源码。那时再单独切成：  但按你现在这个仓库的情况，先用 GBK -> UTF-8 这一套更靠谱。

### 证据 41

`2026-05-20 | gpt-5.4 | friendly | unspecified | debugging | session:659ba8205788347ce914`

> 我先在仓库里全局扫一遍 elegantbook2.tex，把“看起来很短的行间公式（含 \[...\]/equation*/align* 中的短行）”批量定位出来，再优先按章节整段把相邻的短块合并压行，同时每一轮都编译到 build/ 并确保日志不新增警告。

### 证据 42

`2026-05-25 | gpt-5.4 | friendly | unspecified | implementation | session:4d8b181ad9a43f9805ac`

> 看起来已经接近你要的“紧凑+不打架”的效果了：放大图贴近主图、F10 不再和 0.03 之类的刻度打架、分式公式也在左侧就位。接下来我把中英文重新编译一遍，确认版面没有被 caption 或新高度影响。

### 证据 43

`2026-05-16 | gpt-5.4 | friendly | unspecified | research | session:06d95321d6be28329abf`

> 已找到全书里包含占位文本的若干行号；下一步只截取 \section{PLIC, PLY, PLI, PLE, PLEX, PLO} 这一章的范围，并把其中命中的占位例句逐条回溯到对应的 word 词条起始行和义项位置。

### 证据 44

`2026-05-15 | gpt-5.4 | friendly | unspecified | testing | session:7de32ec455baba06a3e1`

> 我会在仓库里新增一个 scripts/ 目录：放 qc_word_tex.py（生成清单+断点进度）和 extract_slice.py（抽取某章节/某序号区间做快速编译）。先把脚本写好再跑一次全书 QC。

### 证据 45

`2026-05-15 | gpt-5.4 | friendly | unspecified | unknown | session:157b29b0902bec0161b2`

> 我把你现在版本里最明显的“符号口径裂缝”先补上了：问题二正文用的是 $A(t)$，但敏感性表和说明仍在用 $S$，这会被审稿人一眼抓住。我已经统一改成 $A$。接下来我会再编译一次，确保表格引用和公式编号都没被影响。

### 证据 46

`2026-05-11 | gpt-5.4-mini | pragmatic | commentary | debugging | session:03c7be5838accb4982a5`

> 我已经看到一个明显信号：正文和代码里的参数、阈值、变量命名不完全一致，后面很可能会落到“结论像是算出来的，但和模型本身不严丝合缝”。继续把管线后半段和图表生成逻辑读完，确认哪些结论是直接来自 summary.json，哪些是作者自己在文中二次加工的。

### 证据 47

`2026-06-15 | gpt-5.4-mini | friendly | commentary | implementation | session:3125714cbb90f34998db`

> 我已经定位到第七章当前的骨架了，接下来只补一段上下文，确认它现在是“按题型推进”还是“按概念推进”，这样重构建议就能落到具体层级。

### 证据 48

`2026-05-26 | gpt-5.4-mini | friendly | commentary | operations | session:3cbe40db425fd236835d`

> 我已经定位到文件里大量 \[...\] 分布，但要严格按“第 4 章”来收敛范围，先确认第 4 章的起止行，避免把后面章节的候选混进来。

### 证据 49

`2026-05-28 | gpt-5.4-mini | friendly | commentary | research | session:ea2b19e6ceece27766be`

> 我先把 6400–7050 这一段重新扫一遍，只挑现在还最值得压的高置信度位置，并避开上一轮已经提过的段落。接着我会按“浪费点 + 推荐压法 + 风险”给你前 5 条，不改文件。

### 证据 50

`2026-05-28 | gpt-5.4-mini | friendly | commentary | unknown | session:b30af494fe16a6d230d6`

> 我已经把公式密集点位扫出来了，但要把结论做准，还得回到 7700–9300 的原文上下文里确认每个展示公式到底是“短到还能压”还是“已经是合适长度”。接下来我只看这一段，不扩到别处。

### 证据 51

`2026-05-26 | gpt-5.4-mini | friendly | final_answer | operations | session:3cbe40db425fd236835d`

> 第 4 章里没有我能按你这套严格规则高把握报出的候选。   我把 重积分 章内的 \[...\] 位置都扫了一遍，能像“短公式 + 短文字 + 短公式”那样靠并的片段，基本都落在 \item、enumerate、itemize、align* 或其他结构里；按你要求这些都不报。

### 证据 52

`2026-04-28 | gpt-5.5 | friendly | commentary | debugging | session:4d8b181ad9a43f9805ac`

> 我会先把这些建议分成“可直接采纳”“需要降调采纳”“暂时不能写死”三类，然后按可证据支持的版本改 paper.tex。尤其是 ghost coupling 和 purity 数字这两处，我会先查本地 README.md / notes，避免把 AI 建议里的夸张表述直接写进论文。

### 证据 53

`2026-05-25 | gpt-5.5 | friendly | commentary | debugging | session:4d8b181ad9a43f9805ac`

> 我会先把这些建议分成“可直接采纳”“需要降调采纳”“暂时不能写死”三类，然后按可证据支持的版本改 paper.tex。尤其是 ghost coupling 和 purity 数字这两处，我会先查本地 README.md / notes，避免把 AI 建议里的夸张表述直接写进论文。

### 证据 54

`2026-06-22 | gpt-5.5 | friendly | commentary | debugging | session:a9485baa1882f0bcd498`

> 二进制里能确认几个关键点：有 approval_policy 配置键，也有独立的 ApplyPatchApprovalRequestEvent，说明补丁确认确实是单独事件，不只是 shell 命令白名单。现在我会改 config.toml 加 approval_policy = "never"，并尽量避免破坏当前 session；但热生效这点需要实测，宿主可能已把配置读进内存。

### 证据 55

`2026-07-01 | gpt-5.5 | friendly | commentary | debugging | session:8ba9e58beba6826d2a46`

> 我已经抓到第一处硬错误了：l.5873 附近的公式还带着 \tag{1}，但它现在不在可打标签的显示环境里，所以 amsmath 直接停了。先把这一处改掉，再重新编译继续追后续报错。

### 证据 56

`2026-04-28 | gpt-5.5 | friendly | commentary | design | session:4d8b181ad9a43f9805ac`

> 我会把 Preliminaries 之后的 WCC/MetaBBO 内容整块替换成 BYI 的实验协议、分组策略、诊断指标、结果骨架、讨论和结论。先确认一下当前 section 边界，避免误碰前面已经写好的 Introduction / Related Work / 数学背景。

### 证据 57

`2026-05-23 | gpt-5.5 | friendly | commentary | design | session:4d8b181ad9a43f9805ac`

> 我会把 Preliminaries 之后的 WCC/MetaBBO 内容整块替换成 BYI 的实验协议、分组策略、诊断指标、结果骨架、讨论和结论。先确认一下当前 section 边界，避免误碰前面已经写好的 Introduction / Related Work / 数学背景。

### 证据 58

`2026-06-07 | gpt-5.5 | friendly | commentary | design | session:0cd812a0840babe8367a`

> 目前最有希望的路线不是直接估计 f，而是把三根的对数看成同一函数 rho 的三条水平截线，再用一个“指数余量”引理处理紧的部分。为了避免给你一个漂亮但不真的成立的证明，我会继续用更强/更弱权重做压力测试，确认哪些替换是安全的。

### 证据 59

`2026-04-26 | gpt-5.5 | friendly | commentary | documentation | session:4d8b181ad9a43f9805ac`

> 依赖检查里有个小发现：所谓 Lambda 不是包，这点确认了；真正的加速包 numba 已安装。当前环境里 yaml 显示缺失，虽然这批主实验大概率不用它，但 requirements.txt 里已经写了 pyyaml，我会把依赖文件补完整，并在 README 里把 “Lambda 不是包” 这件事写清楚。

### 证据 60

`2026-05-18 | gpt-5.5 | friendly | commentary | documentation | session:4d8b181ad9a43f9805ac`

> 依赖检查里有个小发现：所谓 Lambda 不是包，这点确认了；真正的加速包 numba 已安装。当前环境里 yaml 显示缺失，虽然这批主实验大概率不用它，但 requirements.txt 里已经写了 pyyaml，我会把依赖文件补完整，并在 README 里把 “Lambda 不是包” 这件事写清楚。

### 证据 61

`2026-06-06 | gpt-5.5 | friendly | commentary | documentation | session:b6f663a727665d9fe559`

> 我会稍微谨慎一点处理 2005 的“近重复”：如果只是同一个物理模型但数据/边界条件不同，我会录入；如果 physics.tex 已经有同等题干和同样结论，就只进台账不重复写正文。先确认几个波动和光栅的现有例题，免得重复塞题。

### 证据 62

`2026-07-01 | gpt-5.5 | friendly | commentary | documentation | session:8ba9e58beba6826d2a46`

> 我已经抓到总轮廓了：最后一章不是常规讲义，而是“真题整理”式的题库章。现在我再看几组样例，确认它是怎么从试卷标题过渡到题目、再到标准解析的。

### 证据 63

`2026-06-08 | gpt-5.5 | friendly | commentary | implementation | session:b123806452f736d2858b`

> 已经定位到第7章从第 35032 行开始，并且文件里已经定义/使用了 shortexenum 与 shortanswerenum，所以建议会优先复用现有环境，避免引入新宏带来的版面副作用。接下来我会筛出第7章内“短列表、短选项、连续短公式”的高性价比点，再人工看上下文确认不误伤。

### 证据 64

`2026-07-04 | gpt-5.5 | friendly | commentary | implementation | session:8046f8dc5e9888adea65`

> 这个转义坑比它应该有的戏份多。为了不继续猜，我会先在 Python 里直接打印目标行和比较结果，再把同一表达式改到写回脚本里；到目前为止 git diff -- elegantbook2.tex 为空，文件仍未改动。

### 证据 65

`2026-05-27 | gpt-5.5 | friendly | commentary | operations | session:d1a0d3c0ddce637f2d80`

> 我已经确认 run_xiatong_closure_phase.py 支持 pending_rescreen，所以这条 CBCCO 可以直接用现有外层入口跑，不需要碰 baseline。接下来我先打开指标筛选文档，找一个合适位置写 v2 更新，再起后台任务。

### 证据 66

`2026-06-21 | gpt-5.5 | friendly | commentary | operations | session:41d054c56c38c6e3b5b0`

> 我会接着把第七章 solution 的压行目标往前推一轮：先用当前文件和最新编译日志做一次现状盘点，再从剩余高密度解答里分批挑短公式处理，最后重新编译和扫 warning，确保这次不是“看起来压了”，而是确实落地。

### 证据 67

`2026-07-07 | gpt-5.5 | friendly | commentary | operations | session:f42705534fc6f2d1cbc9`

> 这段源码在当前 PowerShell 输出里中文有乱码，但 LaTeX 结构、公式和行号都能读；我会用 UTF-8 方式再抓真题段，避免漏掉文字型陷阱。前半段已经看到几个强候选：单边方向与样本方向、先 F 后 pooled t、置信区间和单边检验不能机械等价、两类错误的概率写法。

### 证据 68

`2026-04-28 | gpt-5.5 | friendly | commentary | research | session:4d8b181ad9a43f9805ac`

> 现在看起来上一轮已经吸收了不少建议：摘要也已经有数字了，分解成本和 independent budget 也在稿子里。剩下我会主要补三类：Related Work 的步长困境、结果段的统计防御、讨论段的边界案例，以及把已有图正式挂进 LaTeX。

### 证据 69

`2026-05-18 | gpt-5.5 | friendly | commentary | research | session:4d8b181ad9a43f9805ac`

> 现在看起来上一轮已经吸收了不少建议：摘要也已经有数字了，分解成本和 independent budget 也在稿子里。剩下我会主要补三类：Related Work 的步长困境、结果段的统计防御、讨论段的边界案例，以及把已有图正式挂进 LaTeX。

### 证据 70

`2026-06-07 | gpt-5.5 | friendly | commentary | research | session:25c44689ff5179c0fb7e`

> 我已经定位到最后一题，当前 Get-Content 默认编码显示有乱码，所以我会用 UTF-8 重新读取题面及前面同类例题。前面紧挨着有一个同函数的“极值点比较”例题，里面的参数范围和结论可能能复用，但这道最后题多了三个零点，第(2)问明显需要更细的零点结构。

### 证据 71

`2026-07-08 | gpt-5.5 | friendly | commentary | research | session:702a627bd1b7bf8e9e3d`

> 我扫完了，结论更明确：现在 B 章已经有 read/write/seek/tell/eof/is_open 等碎片，但确实没有一张“文件流成员函数总表”，这会让你遇到 open()、good()、fail() 这种题时找不到抓手。我现在补一张总表，并顺便把我刚才新增 open() 后造成的小节编号重复修正掉。

### 证据 72

`2026-05-30 | gpt-5.5 | friendly | commentary | review | session:659ba8205788347ce914`

> 我继续推进，不先编译；当前批次还没到“千行级”改动，但已经有不少短显示被压掉。我接下来会优先处理第 3 章剩余高收益候选，等再收一批后统一编译看 Overfull/Underfull 是否回稳。

### 证据 73

`2026-06-05 | gpt-5.5 | friendly | commentary | review | session:4a178a18351a58d1cb2e`

> 定向结果已经有雏形：Startup 目录目前没有 .vbs，只看到 OneNote 快捷方式和 desktop.ini；注册表 Run 项没有直接指向 .ps1/.vbs/隐藏 PowerShell，但有几个常规软件从 AppData 自启。接下来我会把 AppData 下的 .ps1 完整路径和其中是否含隐藏执行/写启动项关键字核对清楚。

### 证据 74

`2026-04-26 | gpt-5.5 | friendly | commentary | testing | session:4d8b181ad9a43f9805ac`

> F11 也很强：oracle 约 2.72e9，sequential/random 到 1e12 量级，说明 20 个非重叠 Schwefel 子组件上 oracle 对齐非常关键。现在进入重叠函数 F13/F14，可能解释会更复杂，但证据价值也高。

### 证据 75

`2026-05-24 | gpt-5.5 | friendly | commentary | testing | session:4d8b181ad9a43f9805ac`

> F11 也很强：oracle 约 2.72e9，sequential/random 到 1e12 量级，说明 20 个非重叠 Schwefel 子组件上 oracle 对齐非常关键。现在进入重叠函数 F13/F14，可能解释会更复杂，但证据价值也高。

### 证据 76

`2026-06-07 | gpt-5.5 | friendly | commentary | testing | session:659ba8205788347ce914`

> 我已经确认主文件没有乱码。现在我会把第 7 章当成当前最大风险点来审：源文件清单、manifest、主文件 section 三者逐项对齐，先找“漏搬/漏登记/重复但未说明”的缺口。

### 证据 77

`2026-07-04 | gpt-5.5 | friendly | commentary | testing | session:e6841734966e797751a2`

> 结构核查的核心结果已经出来了：第一章现在 6 个 section、0 个 subsection、155/155 题解。一个额外检查脚本因为中文正则在管道里乱码报错，不影响文件；我会用无中文匹配重跑题解邻接检查，然后编译。

### 证据 78

`2026-04-28 | gpt-5.5 | friendly | commentary | unknown | session:4d8b181ad9a43f9805ac`

> 我先用现有 1e6 paper 结果里的 runtime 粗估一下，再看当前 3e6 进程有没有已经完成首个 repeat。这样给你的不是拍脑袋时间，而是按本机历史速度估出来的区间。

### 证据 79

`2026-05-27 | gpt-5.5 | friendly | commentary | unknown | session:d1a0d3c0ddce637f2d80`

> 我检查一下当前解析逻辑对空格的处理：查询字符串首尾空格已经会被清理，但如果中间误加空格，例如 cec2013 lsgo 或 MDG + CCFR3 + CMAES，现在多半会走相似度建议。为了更稳，我会补一个“忽略空白/分隔符”的匹配口径，让常见空格错误直接查到。

### 证据 80

`2026-06-21 | gpt-5.5 | friendly | commentary | unknown | session:7911a39214b7216de604`

> 现在的状态是：rg 读原文可用，但 apply_patch 的 sandbox helper 仍读不了同一个文件；我不会把已经定位好的内容丢掉。先再做一次小范围恢复检查，若补丁工具继续失败，我会用“可复核的固定文本替换”方式救场，并在最后明确说明原因。

### 证据 81

`2026-07-05 | gpt-5.5 | friendly | commentary | unknown | session:00a19c4a8f9bf7e3956c`

> 已经找到位置了：当前解答直接引用了前面极坐标 Laplace 命题。你要求“不使用既有结论”，所以我会把这里改成从链式法则和矩阵形式的二阶导变换直接推出结果。

### 证据 82

`2026-04-28 | gpt-5.5 | friendly | final_answer | debugging | session:6d39c82e06fd8f78b0f4`

> 已更新 [audit_round1.md](<D:/code LateX/elegantbook/DiscreteMathematics/learn-lisanshuxue/audit_round1.md>)。  我做了两件事：第一轮里已经实际改稿修复的硬错，都在判定栏标成了 已处理：...；未标记的条目保留为第二轮/教材口径待确认项。然后新增了 第二轮审校清单：第 1 章 命题逻辑，目前列了 9 条，只是审校清单，没有改 .tex 正文。  这轮我只动了 audit_round1.md。下一步就是按这个格式继续做第 2 章第二轮清单。

### 证据 83

`2026-05-27 | gpt-5.5 | friendly | final_answer | debugging | session:d1a0d3c0ddce637f2d80`

> 已给 [query_experiment_results.py](/d:/LSGO-platform/query_experiment_results.py) 加了拼写纠错建议。  现在如果输错一两个字母，会这样：  输出：  也支持 benchmark 输错：  如果差得太远，比如完全不存在的组合，仍然只输出：  我也验证了正常查询仍然不受影响。

### 证据 84

`2026-06-06 | gpt-5.5 | friendly | final_answer | debugging | session:f7c32450735bbeefeb19`

> 只读复审完成，未编辑文件。  当前 README.md 没有明显的表演式、居高临下、变魔术、自夸式或营销式口吻。上一轮那些比较突出的表达已经基本处理掉了；剩下的“关键事实”“必须”“完整 CRUD”“证明从根目录调用也能正常回归”等词，在当前上下文里属于技术说明或验证说明，不构成明显语气问题。

### 证据 85

`2026-06-06 | gpt-5.5 | pragmatic | final_answer | design | session:0801fe8e010ecb09732a`

> 筛选后建议：Consequently / As a consequence 做主力结果句；Accordingly 用来写“随之需要调整”；It follows that 用来写逻辑结论；Apart from the obvious benefits 只保留少量，用来写“表层收益之外的显化结果”。

### 证据 86

`2026-06-09 | gpt-5.5 | friendly | final_answer | documentation | session:f7c32450735bbeefeb19`

> 你质疑得对，我前面应该直接给证据，不该只用一句话带过。  我刚查了当前磁盘上的文件，结果是：  第 19 节也确实在 README 里：  现在仓库里只剩一个 Markdown：  你看到“只添加了 10 行”，大概率是在看我后一次“删除源文件并微调 README 引用”的局部变化；大的合并动作是在前一步已经加进去了。更准确地说：原 Markdown 的内容主体已经合进 README 第 19 节，标题层级和旧相对链接被我调整过，不是完全逐字原封不动。

### 证据 87

`2026-06-09 | gpt-5.5 | friendly | final_answer | implementation | session:f7c32450735bbeefeb19`

> 你接下来可以顺着“工程搭起来以后，我具体怎样一步步实现系统”的线继续写。建议从 **分层架构、数据持久化、登录权限、业务功能、CLI 到 Qt GUI、测试验证** 这条线展开。下面这段可以直接接在你现有内容后面：  你后面如果要插图，建议放这几类图：  这样接下去写就不会散：先讲开发步骤，再配图说明每一步的证据。

### 证据 88

`2026-07-08 | gpt-5.5 | friendly | final_answer | implementation | session:702a627bd1b7bf8e9e3d`

> 输出结果是：  按顺序拆：  创建 d1，调用构造函数：  然后进入外层 { }，再进入内层 { }：  创建 d2，调用构造函数：  内层 { } 结束，d2 生命周期结束，调用析构函数：  然后执行：  创建 d3，调用构造函数：  外层 { } 结束，d3 生命周期结束，调用析构函数：  最后 main 结束，d1 生命周期结束，调用析构函数：  核心规律：  > 局部对象进入作用域时构造，离开所在作用域时析构。   > 同一作用域中，后构造的对象先析构。

### 证据 89

`2026-06-21 | gpt-5.5 | friendly | final_answer | operations | session:41d054c56c38c6e3b5b0`

> 本轮继续压了第七章多批高密度 solution，主要处理短定义、短约束、端点判断、简单导数/特征根/势函数等不需要行间展示的公式。编译已通过，build/elegantbook2.pdf 当前为 747 页。  验证结果：xelatex 成功；日志中没有 Warning、Overfull、Underfull；也没有空的 \(\) 或 \[\]。不过剩余短行间公式候选仍不少，所以我没有把目标标记为完成，下一轮会继续从当前剩余候选最多的 solution 分批压。

### 证据 90

`2026-07-01 | gpt-5.5 | friendly | final_answer | operations | session:ad076555db421650c297`

> 补好了。4561 附近那个空的 solution 现在已经填上了，内容是等温压缩和绝热压缩两条路径的做功比较：  \[ W_T=\frac{m}{M}RT\ln\frac{V_1}{V_2},\qquad W_Q=\frac{p_2V_2-p_1V_1}{\gamma-1} \]  并且补了最后的比较句，说明绝热压缩更费功。  另外我顺手确认过，那里真正断掉的是这个空解答块，不是前一个 solution 的收尾。现在文件结构已经接回来了。

### 证据 91

`2026-06-08 | gpt-5.5 | friendly | final_answer | research | session:e568a11b98d140157a02`

> 因为这轮不是模型自己挂了，而是被外部中断了。  日志里这条很明确：turn_aborted，reason: "interrupted"，时间是 2026-06-08 03:41:09Z。也就是说，至少从 jsonl 看，原因是“被打断/取消”，不是别的上游报错。  更具体点，常见触发就是点了停止、切走会话、或客户端主动回滚这轮；但日志没有写出是哪一个动作，所以我只能确认“interrupted”，不能再往下硬猜。

### 证据 92

`2026-07-08 | gpt-5.5 | friendly | final_answer | research | session:8f2b01722925f95128ef`

> 选 **B**。  表达式是：  先看优先级：  如果 ++ 和 * 都是**友元运算符**，也就是非成员函数重载，那么调用形式是：  原因：  后置 ++ 的函数形式是：  其中第二个 int 是哑元参数，用来区分前置和后置。所以通常写成：  然后再和 k 做乘法：  因此：  \[ \boxed{\text{B. } operator*(operator++(j,0),k)} \]  补充区分：  前置：  友元形式：  后置：  友元形式：

### 证据 93

`2026-06-06 | gpt-5.5 | friendly | final_answer | review | session:4138477aefadce623278`

> 已完成 [2013-B-draft.tex](</d:/code LateX/elegantbook/word/past-exams/reviewed/2013-B-draft.tex>) 收尾：从 Word 内嵌公式对象恢复了全部 56 处题面公式，并补齐了可确定的参考答案与简解。  验证结果：没有遗留 \missingformula{}、[[EQ..]] 或乱码占位；临时公式图片目录已清理。没有无法可靠恢复的题面公式，因此最终报告中无 missingformula 条目。

### 证据 94

`2026-06-08 | gpt-5.5 | friendly | final_answer | testing | session:659ba8205788347ce914`

> 我先继续往下压，不会停。刚才已经并掉了几处第 7 章里最稳的短显示式，现在还剩一批可以继续处理的候选，我会按同样方式接着扫。

### 证据 95

`2026-07-01 | gpt-5.5 | friendly | final_answer | testing | session:8ba9e58beba6826d2a46`

> 已经处理完了：我按你给的估算逻辑先全量筛了一遍 elegantbook1.tex，把所有估算宽度小于 0.6\textwidth 的行间数学环境逐个手工回退成了行内公式，没有用脚本批量改公式。复查后，剩余符合条件的行间公式为 0。  改动都在 [elegantbook1.tex](<D:\code LateX\elegantbook\elegantbook1\elegantbook1.tex>)，这次是 10 行新增、35 行删除。LaTeX 还没重新编译验证版面。

### 证据 96

`2026-04-29 | gpt-5.5 | friendly | final_answer | unknown | session:781c8981eb16958ad964`

> 改好了，在 [elegantbook2.tex](<D:/code LateX/elegantbook/elegantbook2/elegantbook2.tex:1242>)。  我在这一段先加了 设 $C=y^2\pm x^2$，则，然后把原来默认的 1 补成了对应的 C, C^2, C^3, C^4，比如： ∫y dx 里是 \frac12 C∫dx/y，后面每降一次幂就多累积一个 C。  没有重新编译，只做了局部公式修改。

### 证据 97

`2026-05-27 | gpt-5.5 | friendly | final_answer | unknown | session:d1a0d3c0ddce637f2d80`

> 已新增脚本 [query_experiment_results.py](/d:/LSGO-platform/query_experiment_results.py)，只读取已有 experiment_record.json，不碰 baseline。  固定输入格式是：  查到会输出一行关键结果，例如：  查不到会精确打印：  也支持几个实用参数：  我已经验证了：存在结果能查到，不存在结果会输出 unfound，--json 和自定义列也正常。

### 证据 98

`2026-06-20 | gpt-5.5 | friendly | final_answer | unknown | session:7019d90cdeed9315be06`

> 我看到了，26199 现在只甩了一个中心二项式系数结论，确实对没熟悉 Stirling 的学生有点跳。  不过当前环境权限明确是只读，我这轮不能写入文件。建议把 26199-26202 替换成下面这段：  这段放进“常见估阶模型库”里刚好，既解释 Stirling 的用法，又给学生可直接套的三条结论。

### 证据 99

`2026-07-01 | gpt-5.5 | friendly | final_answer | unknown | session:8ba9e58beba6826d2a46`

> 你说得对，前面的表述不够严谨，我应该把“还在继续处理”说清楚，不该让你以为我已经停在第一组就收口。  现在的真实状态是：elegantbook1.tex 已经完整处理完了，我刚刚又按同一套估算逻辑复查过一遍，display blocks: 1395，below 0.6: 0。也就是说，当前文件里所有按脚本估算低于 0.6\textwidth 的 $$...$$ 和 \[...\] 都已经回退成了行内公式。

### 证据 100

`2026-06-21 | gpt-5.5 | friendly | unspecified | unknown | session:7911a39214b7216de604`

> 我继续接手。现在的关键不是数学内容，而是把补丁链路稳定下来；我会先用最短外部命令探测可用 shell，然后一处一处落第一批修改。

### 证据 101

`2026-07-10 | gpt-5.6-sol | pragmatic | commentary | implementation | session:2016ce1a59a82f5b7685`

> 实现已通过前两项测试；剩下的失败不是采集或脱敏缺陷，而是测试样本文字短于计划规定的 60 字证据下限。我会把 fixture 调整为合法长度，再运行完整测试套件。

### 证据 102

`2026-07-10 | gpt-5.6-sol | pragmatic | commentary | unknown | session:2016ce1a59a82f5b7685`

> 第一轮结果已经出来：共 117,677 条中文助手消息、约 5,093 万字符。最突出的不是某个单独口头禅，而是一套稳定的“工程代理话语”：高频使用“我先 / 我会 / 当前 / 确认 / 下一步”，并反复采用“先……再……”和“不是……而是……”结构；我正在补充分阶段统计，让报告能说明这些词分别在什么场景出现。

### 证据 103

`2026-05-24 | unknown | unknown | final_answer | debugging | session:4d8b181ad9a43f9805ac`

> 我已经把这段改成“定义先行”了，见 [paper2.tex](/d:/2026-BYD-arxiv/paper/paper2.tex:175)。现在它不再重复引言的动机，而是直接交代了初始分组、非可分变量组、SCCD 的输入输出，以及下一步要回答的核心问题。  下一句建议直接接： “要完成这一步判断，关键在于两类信息：一类说明组内哪些联系不能被轻易打断，另一类说明该组内部的局部尺度是否已经失衡。”

### 证据 104

`2026-05-24 | unknown | unknown | final_answer | design | session:4d8b181ad9a43f9805ac`

> 可以，下面是一版可直接并入正文的最终稿：  如果你愿意，我下一步可以把 \subsection{流程与复杂度} 再压得更像论文原文一点，统一成你前面那种语气。

### 证据 105

`2026-05-24 | unknown | unknown | final_answer | implementation | session:4d8b181ad9a43f9805ac`

> 可以，就接你这段往下收，不用再开新意思了。后面这一段我建议你写成这样：  有两个小地方我也顺手提醒你一下：  1. 你正文里的 "可以细化" 最好改成中文引号 “可以细化”。   2. 对 refinable 块而言 这句如果你嫌英文夹着突兀，也可以改成 对已经通过上一节判定的变量组而言。  如果你愿意，我下一步就把 \subsection{流程与复杂度} 也直接给你起草出来。

### 证据 106

`2026-05-23 | unknown | unknown | final_answer | research | session:4d8b181ad9a43f9805ac`

> 对，这里缺的不是换个词，而是把“**为什么偏偏是对角元**”说出来。  最稳的改法，是先把 **非对角元 vs 对角元** 的分工点明。这样读者就不会觉得你突然挑了一个量。  我建议直接改成：  把它接回你前一句，整段会顺很多：  这样有三个好处：  1. 对这一目的 这种悬空说法没了   2. 为什么是对角元 说清楚了   3. 后面接“一维二阶中心差分去近似对角元”就自然了  下一句其实就可以顺着写成：  如果你愿意，我可以继续把这后面两三句一口气帮你收顺。

### 证据 107

`2026-05-24 | unknown | unknown | final_answer | unknown | session:4d8b181ad9a43f9805ac`

> 会，但不是当主判据。  它现在的角色是“解释层”而不是“决策层”: - 预备知识里用它说明什么叫局部尺度失衡 - 方法里用 span(C) / overflow(C) 去落地 - 讨论或结果分析里再用它解释为什么这个代理量是合理的  也就是说，**条件数不再直接出现在四类判定里**，但会作为理论支撑再提一次。   如果你愿意，我下一步可以帮你把“局部尺度依据”那一段顺手写成一版，把条件数和 span(C) 的关系收住。

### 证据 108

`2026-06-12 | gpt-5.5 | friendly | commentary | unknown | session:dc82700209a5f0da9153`

> 我已经确认 .txt 解析文件本身就是可读的，而且里面直接带题号、答案和精析。现在重点不是“有没有材料”，而是“脚本有没有把这批材料吃进去”。我会先补这层，然后再回头把 md 里的结论全部按全量数据重写。

### 证据 109

`2026-06-06 | gpt-5.5 | friendly | commentary | unknown | session:659ba8205788347ce914`

> 检查结果显示：主文件里第 7 章已经存在并能编译，但它目前仍是 29 个 section、41 个来源项的“来源骨架”，不是最终的题目正文。reviewed/ 刚才没有列出可用文件，说明上一轮子代理底稿很可能没落盘；我会重新把可处理源文件分批推进，先从 Word/DOC 可抽取卷入手，扫描 PDF 单独排队做 OCR。

### 证据 110

`2026-06-22 | gpt-5.5 | friendly | commentary | debugging | session:174f7896d40105abf13b`

> 刚才的输出因 PowerShell 默认编码出现了乱码，但文件本身大概率是 UTF-8。统计上已经能确认：当前源文件包含 1322 个 solution，既有台账标出了 992 个需人工复核、444 个长行内公式风险、572 个跳步关键词风险；我会用 UTF-8 重新读取关键台账，得到可用中文内容。

### 证据 111

`2026-06-05 | gpt-5.5 | friendly | commentary | debugging | session:e53dea8290441e91aa04`

> 我已确认 .dat 里没有直接检出 S900/C900 字符串，残留主要是 CSV 和 app.log 记录；这说明主线清理 .dat 目标基本能完成，但手册对“文件输出/日志残留”的清理口径还不够完整。现在我会把问题按“必须修、建议修、可接受残余风险”整理成现场走读审查结论。

### 证据 112

`2026-06-21 | gpt-5.5 | friendly | commentary | unknown | session:7911a39214b7216de604`

> 现在连 Write-Output ok 这种最短命令也被 helper 拒了，说明不是文件内容或命令格式问题，而是当前工具沙箱处于短暂不可用状态。我会再等一个节拍重试；如果恢复，就继续第一批修改，否则我会把本轮已经定位好的第七章待扩展清单交代清楚，避免你误以为文件已经改完。

### 证据 113

`2026-06-22 | gpt-5.5 | friendly | commentary | debugging | session:670ad7470dce8c47a19d`

> 收到，这个阈值我会钉死：只有估算宽度接近或超过 0.75\textwidth 的行内公式才优先拆出；短的展示公式若只是变量定义、小代入、小结论，则要更积极地压回行内。我先接上当前 TeX 状态和审计记录，确认上一批修改边界，再从下一批开始按这个标准动手。

### 证据 114

`2026-06-05 | gpt-5.5 | friendly | commentary | unknown | session:659ba8205788347ce914`

> 当前计数已经继续下降：align* 从 542 压到 530，行间 \[...\] 从 707 压到 683，禁用项仍然是 0。下一步我会继续扫“每行都短但还在竖排”的 align*，优先处理第 3 章后段、第 4、5、6 章里低风险的结果型块。

### 证据 115

`2026-05-12 | gpt-5.4 | pragmatic | commentary | unknown | session:66ea98383146527c8587`

> 我先把你刚锁定的方向落成实现约束：本轮目标是“教材化优先”，配图密度是“核心章配图”，并且每章都要有“练习 + 延伸读”。接下来我只再确认两件会实质改变终修方案的事实：现有仓库能不能复用图示/参考文献基础设施，以及是否已有练习风格可继承。

### 证据 116

`2026-06-07 | gpt-5.5 | friendly | commentary | research | session:61d23986126f8e257195`

> 日志精扫已经没有命中，说明刚才的 Overfull 也压掉了。现在我把范围收窄到 special.tex 和 chap4.tex 的残留句式：先处理短文件 special，再回到 chap4，末题证明继续等子代理结果但不让主线停住。

### 证据 117

`2026-06-07 | gpt-5.5 | friendly | commentary | debugging | session:8bf2a11176127d89c088`

> 中间三章的子智能体已经回来了，问题质量不错：不是泛泛说“像 AI”，而是抓到了构造来源、分支选择、轨迹计算压缩这些真正会让读者卡住的点。我会优先处理这些高置信项；有些只需一句来源说明，有些要读上下文后再补中间环节，避免改坏原方法。

### 证据 118

`2026-06-07 | gpt-5.5 | friendly | commentary | unknown | session:61d23986126f8e257195`

> 我会先回到当前工程状态：确认 chap3 最后一题、计划文档和编译状态，再决定是继续攻克未闭合证明，还是先清理已经能落稿的章节。这个任务现在最关键的是不能“写得像完成了但数学没闭合”，所以我会先把可验证事实和缺口重新压实。

### 证据 119

`2026-05-23 | gpt-5.4 | pragmatic | commentary | research | session:4d8b181ad9a43f9805ac`

> 结论已经很清楚了：你的判断是对的。imitation 里大多数摘要不是“把全文数据硬压成一段”，而是先把论文的身份、问题、方法和结论边界说清楚。当前这版摘要还是偏“结果清单化”。我直接把中英文摘要一起改成更像范文的写法。

### 证据 120

`2026-05-18 | gpt-5.4 | pragmatic | commentary | research | session:4d8b181ad9a43f9805ac`

> 结论已经很清楚了：你的判断是对的。imitation 里大多数摘要不是“把全文数据硬压成一段”，而是先把论文的身份、问题、方法和结论边界说清楚。当前这版摘要还是偏“结果清单化”。我直接把中英文摘要一起改成更像范文的写法。


完整最多 120 条证据见 `evidence_raw_redacted.md` 与 `examples.jsonl`。

## 10. 复现与限制

复现命令、输入路径、脚本版本、快照、运行时间和核心计数均记录在 `run_metadata.json`。同一 `snapshot.json` 重跑会读取相同文件的同一字节范围，避免活动会话追加内容改变结果。

局限包括：任务类型采用可审计但不完美的规则分类；2-4 gram 不等于中文语义分词；工程任务本身会提高“验证、风险、边界、下一步”等词的频率；不同模型、人格和时间段的样本量可能不均衡。报告因此描述本地语料的风格分布，而不是对某个 GPT 版本做普遍性断言。

## 11. LaTex 成稿语料补充分析

本节补入 `D:\code LateX\elegantbook\cet6` 中除 `cet6.tex` 以外、由 GPT 生成的 LaTex 文件，以及外部提供的 `main.tex` 数学建模论文。它们与前文的 Codex JSONL 语料不同：前者是为了交付给读者而写的长文、模板或论文，后者主要是执行任务时的对话。因此，这一组材料特别适合观察 GPT 中文从“边做边说”切换到“整理完再教、再论证”的样子。

### 11.1 纳入、跳过与去重

| 文件 | 定位 | 是否进入主统计 | 处理说明 |
|---|---|---|---|
| `CET6.source-damaged.backup.tex` | 损坏备份稿 | 否 | 读取时存在明显乱码；按分析要求跳过，不做修复和推断。 |
| `test.tex` | CET 写作模板库 | 单独讨论 | 清洗后约 688 个中文字符、35,903 个英文字符；它的中文主要是分类标签，不应与中文长报告混算。 |
| `section_b_final_conclusions_report.tex` | 早期段落匹配策略报告 | 是 | 独立的教学/实战报告版本。 |
| `section_b_final_conclusions_report_unified59.tex` | 全量分析总报告 | 是，作为主版本 | 完整的报告型 GPT 中文样本。 |
| `section_b_final_conclusions_report_v2.tex` | 全量分析总报告修订版 | 仅作版本证据 | 与 `unified59` 的中文 4-gram Jaccard 相似度为 0.977，几乎同稿；若双倍计入会虚增高频表达。 |
| 外部 `main.tex` | 长江生态数学建模论文 | 是，单独讨论 | 可正常读取，与两份 CET-6 策略报告的中文 4-gram Jaccard 仅为 0.0018 和 0.0034；是独立的论文体样本。 |

因此，CET-6 报告型中文的主语料由早期策略报告和 `unified59` 组成，合计约 **20,528 个汉字**；外部 `main.tex` 以 **12,689 个汉字**的独立建模论文体另行分析。`test.tex` 用来观察模板化和中英切换，`v2` 用来观察同稿版本迭代，乱码备份不参与任何语言频率结论。

### 11.2 文件结构量化

| 文件 | 汉字数 | 句子/条目级单元 | 平均单元长度 | 标题层级项 | `\\item` 条目 | 图表引用 |
|---|---:|---:|---:|---:|---:|---:|
| `section_b_final_conclusions_report.tex` | 9,790 | 189 | 69.9 字符 | 33 | 69 | 5 |
| `section_b_final_conclusions_report_unified59.tex` | 10,738 | 541 | 55.9 字符 | 156 | 533 | 5 |
| `section_b_final_conclusions_report_v2.tex` | 10,638 | 539 | 55.8 字符 | 156 | 533 | 5 |
| `test.tex` | 688 | 33 个含中文单元 | 132.4 字符 | 26 | 263 | 0 |
| 外部 `main.tex` | 12,689 | 204 | 97.3 字符 | 35 | 5 | 4 |

这里的“句子/条目级单元”按中文终止符和 LaTex `\\item`/`\\par` 切分，适合衡量交付时的阅读颗粒度，不等同于严格语言学分句。最显眼的不是句长，而是**结构密度**：`unified59` 用约 1.07 万汉字组织出 156 个标题和 533 个条目。它不是自然散文，而是一份把分析、说明书、策略卡和附录揉在一起的“可扫描知识产品”。

### 11.3 两种新增的 GPT 中文文体

#### A. 数据分析总报告体

三份 `section_b_final_conclusions_report` 文件形成的主文体是“研究说明 + 考试策略 + 操作手册”。其外观和语言都有固定的三层结构：

1. **先定义读法和口径**：摘要、研究问题、样本口径、变量、图表说明、文件索引。
2. **再解释发现和反直觉结论**：单题位置、字母分布、题间关系、容量约束、边缘带、条件联动。
3. **最后把发现改写为机械动作**：先做什么、做出一题后如何缩窗、哪些情况不要误判、最短执行版和决策卡。

代表性标题并不只是排版标签，而是在替读者预先安排阅读顺序：

- `先把这份报告看懂`
- `这 5 张图到底按什么顺序看`
- `谁适合先做，谁更适合后做`
- `开做前 30 秒，先做什么`
- `每做出一题，都要记账`
- `做出一题以后，下一步怎么机械推进`

这是一种很强的“读者路径设计”习惯：GPT 不假定读者会从证据自动推到行动，而是把“看什么、怎么理解、如何执行”都显式写出来。

#### B. 中英双语作文模板库体

`test.tex` 则是另一种完全不同的生成方式。中文只负责组织框架和提示用途，真正可替换的写作部件主要是英文：

- 以 `开头段 / 第二段 / 第三段 / 第四段` 规划作文位置；
- 以 `定性 / 观点 / 背景重述 / 举例论证 / 深层机制 / 行动分工 / 愿景抬升` 命名功能槽位；
- 以 `肯定作用 / 契合需求 / 危机剖析 / 平衡双轨` 提供可组合的论证方向；
- 以连接词、因果链和例句片段填充英语表达。

这种文体的核心不是完整叙述，而是**把写作拆成可替换模块**。它带有 GPT 常见的“组合式生成”特征：先穷举题目功能，再给每个功能一套语言积木；覆盖面很广，但相邻模板的语义边界有时会重叠。

### 11.4 与 Codex 对话中文的连续性

虽然这批 `.tex` 不是聊天记录，但它保留了前文已识别的几个深层习惯，只是把它们换成了交付文体：

| Codex 对话中的表现 | CET-6 成稿中的对应形式 | 共同语言倾向 |
|---|---|---|
| `我先……再……最后……` | `先把报告看懂`、`先用单题粗分布锁大区，再用容量约束……` | 用步骤把复杂工作线性化。 |
| `当前/目前 + 发现` | `当前样本口径已经统一`、`当前数据适合回答什么` | 先限定信息边界，再给结论。 |
| `确认/验证/结果` | `样本口径`、`变量定义`、`图表说明`、`统计局限` | 判断需要交代证据来源和适用范围。 |
| `核心/关键/结论` | `核心结论可以概括为五点`、`最该记住什么` | 先给读者一个可记忆的主结论。 |
| `不是 A，而是 B` | `不是默认起手锚，而是……`、`不是猜均值落点，而是……` | 用对照纠正表层直觉。 |
| `下一步/建议` | `做出一题以后怎么机械推进`、`最短执行版` | 不停留在解释，必须落到动作。 |

这种连续性说明，GPT 的稳定特征并非某几个口头禅，而是一个更深的组织算法：**范围限定 -> 证据/材料 -> 反直觉判断 -> 可执行步骤**。在终端里它表现为“我先检查”；在报告里它表现为“先看口径”；在作文模板里它表现为“先给功能槽位”。

### 11.5 最显著的风格切换：从代理自述到无主语教学

对话语料里，`我先`、`我会`、`我已经`、`如果你愿意` 是明显的代理标记。CET-6 成稿中，这些表达全部为零：

| 表达 | 策略报告 | `unified59` | `v2` | `test.tex` |
|---|---:|---:|---:|---:|
| `我先` | 0 | 0 | 0 | 0 |
| `我会` | 0 | 0 | 0 | 0 |
| `我已经` | 0 | 0 | 0 | 0 |
| `如果你愿意` | 0 | 0 | 0 | 0 |

替代它们的是无主语或读者导向的指令句：`先做`、`优先去`、`不要`、`一旦……就……`、`如果……`、`结论：`。这使语言从“我正在帮你做事”变成“这是一套你可以照着执行的规则”。

这也是 GPT 面对长篇交付时最明显的成熟化：把过程叙述藏起来，把可复用的方法和结论放到前台。不过，读者如果需要知道推导过程，仍会发现许多段落保留了模型式的解释性铺垫。

### 11.6 可复核的高频证据

以下次数按清洗后的 LaTex 正文计算，`unified59` 与 `v2` 仅作并列展示，不作双倍总体加权：

| 表达 | 策略报告 | `unified59` | 风格解释 |
|---|---:|---:|---|
| `先做` | 19 | 32 | 不是抽象分析，而是安排解题顺序。 |
| `已经` | 46 | 24 | 把已知信息、既有题目或已满足条件当作下一步推理的约束。 |
| `直接` | 34 | 24 | 偏好给出可直接采用的判断或路径。 |
| `当前` | 1 | 21 | 统一版更重视限定当前样本和当前结论范围。 |
| `结论` | 9 | 38 | 统一版更明显地把长文切成可记忆的结论节点。 |
| `样本` | 17 | 19 | 反复声明数据来源，增强报告的证据感。 |
| `口径` | 3 | 24 | 将数据定义和可回答边界显式化。 |
| `分析` | 0 | 20 | 从实战策略稿转向分析型总报告。 |
| `图表` | 2 | 21 | 让图表成为论证路径的一部分，而不只是装饰。 |
| `不是……而是……` | 12 组 | 14 组 | 延续 GPT 最有辨识度的反直觉对照句。 |

统一版还稳定出现一批技术化名词短语：`容量约束`、`条件联动`、`边缘带`、`信息增益`、`残余熵`、`连续窗口覆盖率`、`机械化做题策略`。它们使文本呈现“数据科学报告”的精确外观；不过读者仍需区分：这些词有些是严格统计术语，有些是为了教学而起的操作性标签，不能仅凭名称推断方法严谨程度。

### 11.7 长文节奏和句式

两类报告的平均切分单元为约 56-70 字符，远短于前文 JSONL 的最终答复平均长度。原因不是它们更口语，而是 LaTex 结构把长论证拆成了大量标题、列表、决策卡和短段。

最常出现的句式可以概括为：

1. **条件 - 行动**：`如果……，先……；一旦……，就……`。它把统计发现转换成考场规则。
2. **反直觉 - 纠正**：`不是……，而是……`。它先提出常见误判，再指定更值得关注的对象。
3. **层级结论**：`核心结论可以概括为……`、`这一章可以先记什么`、`最短执行版`。它不停在局部收束，防止读者迷失。
4. **边界声明**：`当前样本`、`统计局限`、`只解释辅助价值，不替代最终实战口径`。这与聊天中的谨慎限定相同，但更学术化。
5. **读者操作化**：`容量账本`、`决策卡`、`机械推进`。抽象概念被改写成可执行的认知工具。

### 11.8 这批成稿带来的新优点

- **读者导航非常强**：标题不是简单编号，而是把疑问、答案和下一步都写进标题。
- **证据和行动连得很紧**：每个分布、图表或条件关系都会被翻译成“先做/不要做/优先看哪里”。
- **长文可扫描**：156 个标题、533 个条目虽然密集，但让考试场景下的回查成本很低。
- **边界意识更成熟**：统一版显式写出样本口径、变量定义、统计局限和“不能替代什么”。
- **版本意识明显**：`文档合并说明`、`当前样本口径已经统一` 这类标题说明模型会把数据来源和版本差异纳入交付内容。

### 11.9 同时暴露出的长文 AI 痕迹

这批成稿也比聊天语料更清楚地展示了 GPT 的另一面：

1. **过度架构化**：约 1 万汉字配 156 个标题、533 个条目，很容易把一篇报告写成目录、说明书、附录和口诀的叠加体。扫描方便，但连续阅读会疲劳。
2. **局部结论重复**：`结论`、`先做`、`直接`、`已经`、`不是……而是……` 不断回归。它们保证读者不掉队，也会让文本反复提醒已经说过的事情。
3. **“数据感”可能超过方法透明度**：`信息增益`、`残余熵`、`枢纽题`、`高杠杆`、`边缘带` 等命名很有解释力，但需要回看定义、样本和计算方法，避免术语成为权威感装饰。
4. **把复杂判断写成机械规则**：`if-else 式流程`、`机械推进` 对应试有用，但会把依赖语义理解的任务包装得比实际更确定。
5. **模板库覆盖优先于自然表达**：`test.tex` 把题目拆得很细，优点是可组合，缺点是相邻标签和句块可能同义重复，用户仍需做取舍。

### 11.10 `main.tex`：方法论自辩型数学建模论文体

外部 `main.tex` 是一份围绕长江禁渔、食物链恢复、混沌阈值和入侵风险的数学建模论文。它不是 CET-6 题型资料，也不是仅仅把计算结果贴出来的技术说明；它的核心语言任务是同时完成四件事：**复述题面、解释建模选择、限制结论边界、把结果转成治理建议**。

#### 结构和语言密度

| 指标 | `main.tex` | 意义 |
|---|---:|---|
| 汉字数 | 12,689 | 是本次新增的最大独立中文长文样本。 |
| 句子/条目级单元 | 204 | 比统一版 CET 报告更少、更长，说明它保留了论文段落而非全量拆成决策卡。 |
| 平均单元长度 | 97.3 字符 | 解释、限定和转折经常在同一个长句中完成。 |
| 标题层级项 | 35 | 结构完整但明显低于 CET 统一版的 156 个标题。 |
| 列表项 | 5 | 不依赖密集清单，主要靠连续论证推进。 |
| 表格 / 图表 / 引文 | 11 / 4 / 8 | 使用数据论文的证据外观，而不只使用语言性说服。 |

这组指标把它和 CET-6 总报告区分开：CET 统一版更像扫描型操作手册，`main.tex` 更像“段落论证 + 图表/公式/表格支撑”的竞赛论文。它仍然高度结构化，但结构服务于五个问题的逐一建模，而不是服务于读者快速背诵。

#### 高频论证骨架

清洗后的 LaTex 正文中，以下表达高度集中：

| 表达 | 次数 | 语言作用 |
|---|---:|---|
| `模型` | 48 | 把事实、参数、方程和结果不断绑回同一解释框架。 |
| `不是` | 41 | 主动划掉过于简单的解释或错误读法。 |
| `因此` | 32 | 将前一段机制说明收束为方法或判断。 |
| `结论` | 25 | 频繁声明何处是结果、何处只是中间解释。 |
| `当前` | 22 | 用当前参数、当前扫描分辨率、当前情景限定结论。 |
| `结果` | 22 | 将模型输出和文字解释相互回指。 |
| `本文` | 14 | 以论文作者身份声明方法与贡献，而不是以聊天代理身份报告动作。 |
| `题面` | 14 | 反复把变量、假设和模型选择锚回题目事实。 |
| `同时` | 13 | 并列处理恢复与失衡、自然过程与工程补偿、结果与限制。 |
| `稳健` | 13 | 强调敏感性、参数扫描和结论是否可复核。 |
| `本问` | 9 | 使每个小节保持与对应问题的一一映射。 |

它保留了 GPT 的典型对照句，而且更密集地用于方法论修正：全文可识别出 13 组 `不是……而是……`。例如，语言结构不断从“不是只看末值”“不是单点拟合精度”“不是绝对生态真值”转向“而应追踪过程、区间、相对排序或机制差异”。这与 CET-6 报告的“不是猜均值落点，而是执行规则”同源，但论文体的对照对象是**推断边界**，不是解题动作。

#### 三层写法：事实映射、机制论证、边界防卫

`main.tex` 最有辨识度的地方，是每个问题通常都按三层推进：

1. **事实映射层**：把题面、公报、附件或治理事实映射到变量、初值、参数或情景。
2. **机制论证层**：解释“为什么”某种恢复、滞后、振荡或失衡会出现，而不只报出模拟末值。
3. **边界防卫层**：紧跟着说明模型不代表什么、阈值应如何表述、当前设置下的结果为何不能外推。

问题四的写法是这三层的典型缩影：先以最大李雅普诺夫指数作为判别量，再区分负、近零和正值对应的动态行为，随后立刻补上“当前扫描分辨率下的起点区间”而非“绝对阈值”的限定。问题五同样如此：综合健康指数被反复界定为内部情景比较工具，不替代外部生态监测；随后才讨论权重扰动、排序是否交换和治理建议。

这使它带有一种很强的 GPT 式“预先回应质疑”的口气。模型不仅论证自己的答案，也会同时写出评审可能提出的反问：校准是不是过度？网格点是不是硬阈值？综合指标能否当作现实真值？然后在正文中预先加入限定语。

#### 与此前三种文体的区别

| 文体 | 主语与姿态 | 证据的作用 | 动作的落点 |
|---|---|---|---|
| Codex 过程消息 | `我先/我会` 的代理自述 | 证明当前执行方向正确 | 下一条检查或命令。 |
| CET-6 策略报告 | 无主语的教练式指令 | 把统计关系翻译成做题规则 | 先做、缩窗、记账、排除。 |
| CET-6 模板库 | 分类者/编排者 | 覆盖不同作文功能槽位 | 选择并拼接句块。 |
| `main.tex` 建模论文 | `本文/本问` 的论文作者 | 支撑模型假设、参数与结论边界 | 给出可解释的模型结果和治理建议。 |

`main.tex` 与两份 CET-6 策略报告的中文 4-gram 相似度只有 0.0018 和 0.0034，说明它不是沿用相同措辞的改题版本。它共享的是更抽象的 GPT 组织习惯：先设框架，再解释，再反驳简化读法，最后给出可执行结论。

#### 论文体带来的优点

- **解释比报数更完整**：多次把“恢复”和“健康”、“自然恢复”和“工程补偿”、“复杂化”和“混沌”明确拆开，减少了把同一指标当成全部结论的风险。
- **边界声明具体**：`当前扫描分辨率`、`内部比较指标`、`硬校准锚点`、`一致性检验`等表述，体现出对数值结论适用条件的意识。
- **问题链条连续**：五问不是并列回答，而是从资源、鱼群、珍稀物种、食物链动力学到污染/入侵情景逐层传导。
- **证据形式多样**：文字解释与方程、图表、参数表、引文、敏感性讨论相互补充，符合建模论文的交付预期。

#### 论文体带来的 AI 痕迹与风险

1. **解释性铺垫偏多**：同一个核心意思常以“本问真正要回答的不是……”“只有……才能……”和“这样才能……”重复铺开。它照顾读者，却会让篇幅膨胀。
2. **预设异议的密度很高**：频繁提前澄清“不代表什么”“不能怎样解读”，会提高严谨感，但也可能让正文像答辩预案而不是自然的研究叙事。
3. **术语和精确感需要回溯验证**：`混沌候选区间`、`内部综合健康指数`、`硬校准锚点` 等措辞可读性强，但其科学有效性必须由数据、方程、参数来源和计算过程验证；语言分析不对这些事实或方法本身背书。
4. **治理建议收束得较快**：从模型情景到“水质治理、通道修复、定向放流和入侵压制”的建议，逻辑上顺畅，但真实政策优先级、成本和外部有效性仍需要额外证据。

#### 逐章风格剖面：不是一篇均质长文

此前的总量指标只能说明 `main.tex` 像论文，不能说明论文内部各部分具体怎样写。按 `abstract` 和每个 `\section` 的正文切分后，实际呈现出很清楚的功能分工。下表中的句子/单元同时以中文句末符号和 LaTex 条目边界识别；符号表、参数表和源代码本身以记号为主，不能用普通散文的句长标准评价。

| 章节/模块 | 汉字数 | 单元数 | 平均长度 | 主要语言任务 | 显著用语特征 |
|---|---:|---:|---:|---|---|
| 摘要 | 465 | 5 | 124.6 | 一次性交代框架、校准、结果、风险和建议 | `本文` 3 次、`模型` 3 次；典型“五段式压缩”。 |
| 问题重述 | 582 | 8 | 90.8 | 重新搭建生态问题和题面口径 | 用 `但` 建立恢复/失衡的张力，以年份链条统一事实。 |
| 问题分析 | 3,278 | 63 | 58.2 | 为五问建立因果机制和判题逻辑 | `问题` 33 次、`不是` 20 次、`因此` 11 次、`结论` 9 次。 |
| 模型假设 | 213 | 5 | 45.8 | 明确尺度、空间和归一化限制 | 短句、陈述式，不扩展论证。 |
| 符号说明 | 232 | 表格为主 | 不适用 | 将生态事实压缩为可计算对象 | 信息密集，几乎不是自然语言段落。 |
| 问题一建模与求解 | 1,860 | 32 | 112.7 | 建立模型、校准锚点、解释机制 | `本文` 5 次、`模型` 8 次；是最完整的“事实 - 参数 - 对照”样本。 |
| 问题二建模与求解 | 899 | 15 | 120.3 | 将问题一输出传入珍稀物种模块 | 强调“不是单独外推拟合，而是上游输入”。 |
| 问题三建模与求解 | 461 | 9 | 119.3 | 选择最小动力学闭环并分类行为 | 大量模型术语，但主动说明“不复原全部真实结构”。 |
| 问题四建模与求解 | 610 | 11 | 104.4 | 用李雅普诺夫指数界定混沌候选区间 | `当前` 3 次、`稳健` 1 次；重点是阈值表述降级。 |
| 问题五建模与求解 | 877 | 11 | 148.1 | 污染/入侵情景与综合指标比较 | 单元最长，侧重权重、排序和内部指标边界。 |
| 模型优缺点分析和优化 | 2,521 | 34 | 98.6 | 自我审查、局限声明和下一轮改进 | `模型` 11 次、`当前` 10 次、`因此` 12 次、`稳健` 5 次。 |
| 问题一参数附表 | 532 | 14 | 86.7 | 保存默认参数、依据和角色 | 语言让位于参数可追溯性。 |

这张表说明，GPT 在这份论文里没有把所有章节写成同一种“解释腔”。它把长文分为四类文字：**叙事背景、机制分析、形式化建模、方法论自查**。这种分工本身就是风格特征。

#### 摘要：一段话塞进完整答辩链

摘要只有约 465 个汉字，却同时完成了以下动作：

1. 先给出三层框架：资源/功能群、珍稀物种、三级食物链混沌。
2. 再按 `首先、其次、再次、最后` 罗列方法路径。
3. 随后补入校准锚点和两个量化误差，制造“模型可检验”的证据感。
4. 紧接着不只报正向恢复，而是加入水草承压、情景排序交换等反面结果。
5. 最后才落到治理建议。

这是典型的 GPT 高密度摘要法：**框架 -> 方法 -> 数字 -> 限制 -> 建议**。它的优点是任何评阅者都能迅速看到模型做了什么；缺点是信息单元非常多，读者第一次阅读时很难判断哪些数字是主结论、哪些只是校准细节。

摘要中的“硬校准锚点”“拟合外的一致性检验”“内部综合健康指数”“权重扰动后排序存在交换”尤其值得注意。它们不是普通结论词，而是主动展示模型并非完美的证据。这比只写“结果表明模型有效”成熟得多，但也带有明显的语言性防御：模型先把潜在反驳写出来，再把反驳纳入自己的结论。

#### 问题重述：把题目从背景叙事改写成矛盾结构

这一章并不机械重抄题面。它先把长江生态写成“过度捕捞、污染、通道阻隔”共同造成的退化链，随后用转折把禁渔后的现象拆成两面：

- 一面是资源量和局部水质改善；
- 另一面是鱼类过快增长、底层资源承压、通道不足和入侵扩散。

这就是全文后续论证的母题：**恢复不等于健康**。这一句式没有被直接当作口号反复喊出，而是通过“但恢复并不意味着单向改善”“需要用统一模型区分恢复与健康的差别”建立。它决定了后面每一个问题都不是单纯求一个增长量，而是要同时说明正效应与副作用。

章节末尾把 2021--2026 年材料命名为“政策起点--公报标定--现实验证”的连续口径，是 GPT 很典型的资料重编排：面对分散事实，不先讨论事实可信度，而是先为其设计一个能放入模型的时间轴。这种处理让问题变得可算，也可能把现实材料之间的口径差异压得过平。

#### 问题分析：全文最强的“反直觉解释器”

`问题分析`是语言密度最高的部分：3,278 个汉字中出现 20 次 `不是`、10 次 `而是`、11 次 `因此`。它的主要功能不是增加公式，而是不断禁止读者采用过于简单的读法。

五个分问题的写法可以拆成以下逻辑卡：

| 子问题 | 先否定的简化读法 | 再建立的正确读法 | 语言效果 |
|---|---|---|---|
| 问题一 | 不是只比禁渔前后数量涨跌，也不是只给末值比率 | 追踪底层资源、中层鱼类、捕食压力、滞后和局地压力 | 把“增长”转写成反馈结构。 |
| 问题二 | 不是展示珍稀物种是否增长，也不是套用同一个增长率 | 区分食源、通道、放流、污染和自然恢复 | 把数字变化转写成机制分化。 |
| 问题三 | 不是复原整个长江食物网，也不是追单点曲线 | 保留代表性最小闭环，判断长期行为类型 | 为模型简化辩护。 |
| 问题四 | 不是看曲线不规则就认定混沌，也不是把网格点写成硬阈值 | 用指数、粗扫/加密扫和区间判断 | 为数值结论降调。 |
| 问题五 | 不是一个绝对生态真值，也不是单项扰动的简单叠加 | 用内部情景排序、权重敏感性和复合机制 | 为综合指标限定用途。 |

这是一种非常稳定的 GPT 论证程式：**先找一个“看起来合理但不够好”的解释，再把自己的模型写成更高层、更完整的解释。** 它让文章显得有思辨性，但如果没有足够实证支撑，也容易把“更复杂的表述”误当作“更强的证据”。

#### 假设、符号与参数：从自然语言到可计算对象

在 `模型假设` 中，语言突然变短，连续使用“在十年尺度内”“不对每个局地水域逐一建网格”“采用归一化尺度”等句子。这不是文风变弱，而是论文从解释阶段进入压缩阶段：

- 空间异质性被压成单区平均；
- 量纲差异被压成归一化尺度；
- 复杂生态关系被压成状态变量和参数；
- 现实年份信息被压成校准、验证和情景节点。

`符号说明`和参数附表进一步让文字退到后台。这里的 GPT 特征不是华丽措辞，而是**命名完整性**：变量不仅给符号，还给生态含义、来源、依据和模型角色。它很擅长给每个对象找一个“可解释的位置”，这会显著提高读者的可跟随性。

风险也在这里出现：归一化、代理变量和综合参数一旦被命名得过顺滑，读者会忘记它们是建模选择，不是直接测得的自然事实。论文虽然在后文补了局限，但符号表本身会天然制造一种“所有对象均已被严密定义”的感觉。

#### 五个建模章节：每一问都有不同的叙述策略

**问题一**是全篇最完整的“建模故事”。它先以“避免把湖北段局地观测和全流域平均口径混为一谈”设立范围，再用功能群、食性、观测锚点和反事实对照逐层推进。该节的语言优势在于不会把校准写成纯技术步骤，而会说明校准为何只能锁住一个硬锚点、另一个指标为何只能做一致性检验。它使用的是“模型建立 - 校准 - 机制解释”的论文节奏。

**问题二**采用“上游输出复用”叙述：不是另起炉灶给珍稀物种做孤立拟合，而是把问题一的食源代理传入新模块。语言上频繁区分江豚与长江鲟的约束来源，强调自然恢复、通道、放流和污染不是同一类增长因素。这是一种因果链延续写法，避免了五问各自为政。

**问题三**最像教科书式模型选择说明。它先承认 Hastings-Powell 模型“不精确复原全部营养级”，再说明保留顶层捕食、底层供给和中层转移已足以判定长期行为方向。它不是宣称模型真实，而是宣称模型对当前问题“足够代表”。这种“最小闭环”表述是 GPT 在复杂问题中常用的降维辩护。

**问题四**是全篇最谨慎的章节之一。它没有直接宣布 `K≈3.22` 是混沌阈值，而是反复改写为“当前扫描分辨率下正最大李雅普诺夫指数首次出现的起点区间”。这句的语言价值在于把一个尖锐数字结论降成依赖步长、初值和网格密度的观察。它明显比一般 GPT 的肯定式结论更克制。

**问题五**则把论文从“模型是否能跑”推进到“结论是否稳健”。综合健康指数被界定为内部情景排序工具，权重变化导致排序交换被主动呈现。其核心语言不是“这个指数证明生态更好”，而是“这个指数在什么范围内可比较、何时会失稳”。这让它成为全文最接近方法学自查的一问。

#### 结果语言：数字不是终点，而是需要翻译的对象

`main.tex` 出现 22 次 `结果`、25 次 `结论`、32 次 `因此`。这些词的用法显示，它不会满足于给出图线或表格，而是会再追加一层“结果意味着什么”的翻译。常见模式是：

1. 给一个情景、参数或指标结果。
2. 解释该结果对应的生态机制或方法含义。
3. 紧接着加上“当前参数组下”“当前扫描设置下”“内部比较意义上”的限制。
4. 将其转写成下一问的输入或最后的治理建议。

这种写法让图、表、方程、数字都进入同一叙述链。相比 CET-6 报告中“图表 -> 策略”的短路，建模论文多了一层“图表 -> 机制 -> 边界 -> 建议”。代价是同一个结论常在图注、正文、结果小节和优缺点章节以不同说法出现。

#### 优缺点与优化：最像 GPT 自我审稿的章节

`模型的优缺点分析和优化`有 2,521 个汉字，是仅次于问题分析的第二大连续论证块。它不像通常的“优点三条、缺点三条”形式，而是把每一问重新走一遍：先确认什么环节收紧了模型，再指出什么假设仍然粗糙，最后列出下一轮补强方向。

其关键词分布很能说明这种姿态：`模型` 11 次、`当前` 10 次、`因此` 12 次、`稳健` 5 次、`本问` 5 次。语言在这里形成一个固定循环：

> 当前版本做对了什么 -> 它仍然不能代表什么 -> 因此下一步应增加什么独立指标、空间结构、参数扰动或情景对照。

这种自我审稿式表达是整份论文最值得吸收的部分。它不把局限当作最后的免责声明，而是把局限重新接回改进方案。不过它也最容易制造篇幅：每个问题都同时写“优势、局限、改进”，有时会和前文的边界声明重复。

#### 代表性语言证据与功能解读

下面的句式均来自 `main.tex` 的实际表达结构，保留足以观察风格的短片段：

| 语言证据 | 在文中的功能 | 所反映的 GPT 风格 |
|---|---|---|
| `恢复并不意味着单向改善` | 给全文建立中心矛盾 | 先承认正向事实，再引入复杂化。 |
| `不是简单比较……数量涨跌，而是……反馈方向` | 把题目改写为机制问题 | 高密度使用反直觉对照。 |
| `不单独做外推拟合，而是把问题一……作为上游食源代理` | 连接问题一和问题二 | 喜欢把独立任务组织成数据流。 |
| `并不是要精确复原……全部营养级，而是……保留关键链条` | 为简化模型辩护 | 用“代表性”替代“完全真实”。 |
| `更合适的表述应当是……起点区间` | 降低阈值结论的断言强度 | 在数值结论处主动加适用条件。 |
| `只是内部比较指标，不是……替代` | 限定综合指数用途 | 防止单一指标越权解释。 |
| `只要……就说明……；如果……则说明……` | 把敏感性结果变成判据 | 将连续结果改写为可执行规则。 |
| `后续若继续补强，应优先引入……` | 从局限导出研究计划 | 以未来改进收束负面评价。 |

这些证据显示，论文并不是简单“像 GPT”，而是具体地呈现了 GPT 的四项习惯：**先重构问题、再给机制、立即限定、最后操作化**。

#### 对写作质量的细化判断

从语言组织角度看，`main.tex` 明显比普通模板式生成更成熟：它知道什么时候应把结论降成区间、什么时候应区分代理变量和现实指标、什么时候应说明内部排序不等于外部真值。这些都是好的学术表达习惯。

但需要把“表达成熟”与“模型正确”严格分开。语言上越能预先说明局限，越容易让读者误以为局限已经被解决。对于这份论文，仍需要独立检查：事实来源是否可靠、校准是否足够、方程与参数是否一致、图表能否复现、引文是否真实支撑主张、健康指数的权重是否有外部依据。这里的分析只证明它**如何说服、如何限定、如何组织**，不证明其生态结论或数值结论为真。

若把它作为可复用的 GPT 论文写法，最值得保留的是：

- 每个问题都写清“不能用什么简化读法”；
- 让模型选择、参数来源、结果解释和局限声明互相对应；
- 把数字结论写成条件化的观察，而不是绝对事实；
- 让优缺点章节真正导向下一轮模型改进。

最应压缩的是：

- 同一“不是……而是……”在问题分析、建模、结果和优化中反复出现；
- 每一节都预先解释读者可能的误解，造成论证前置过多；
- 从模型情景直接滑到治理建议时，缺少成本、政策执行和外部验证层；
- 标题和段落均十分完整，但个别章节可以让图表承担更多信息，减少同义复述。

### 11.11 合并后的总画像

把 CET-6 成稿加入后，GPT 中文不应只概括成“工程师边做边汇报”。更完整的三态画像是：

| 场景 | 主导口气 | 典型句法 | 核心目标 |
|---|---|---|---|
| Codex 过程消息 | 代理执行体 | `我先……再……`、`当前……` | 让用户知道正在做什么。 |
| Codex 最终答复 | 工程交付体 | `已完成……验证……下一步……` | 交代改动、证据、边界和后续。 |
| CET-6 分析报告 | 无主语教学/策略体 | `如果……先……`、`不是……而是……`、`结论：` | 把证据变成读者可复用的规则。 |
| CET-6 模板库 | 分类组合体 | `段落位置 + 功能标签 + 句块` | 用模块快速覆盖写作任务。 |
| 数学建模论文 | 方法论自辩体 | `本文……因此……`、`当前……`、`不是……而是……` | 把题面事实、模型、边界和建议串成可答辩的论证。 |

所以，GPT 的中文“味道”在不同载体中会变形，但不变的是：**喜欢先建立框架，明确范围；再用对照和证据压缩结论；最后把结论改成步骤、规则、模板或可答辩的主张。** 这既是它最强的组织能力，也是最容易造成模板感、重复感和过度确定感的来源。

## 12. 2026-08-01 全量严格词项扫描与执行层升级

前面的分析回答“GPT 中文大致是什么味道”，但仍有一个执行缺口：普通词表把命中视为候选，
模型容易在上下文裁决阶段选择保留，最后给出 `NO_CHANGE`。本轮改用更粗暴的策略：先扩大语料，
再把高频机器腔词和词组写成默认禁用项。词条仍不用于判断作者身份或 AIGC 概率，但会阻断
Humanize 的 CLEAN 完成态。

### 12.1 新扫描范围

| 数据层 | 数量 |
|---|---:|
| `.codex` JSONL | 2,973 个文件 |
| JSONL 总行数 | 11,905,120 |
| assistant `output_text` | 167,319 条 |
| 连续汉字 1-8 gram 唯一候选 | 7,155,460 |
| 进入机器腔意群初筛 | 35,739 |
| Markdown/TeX 文件 | 12,744 |
| Markdown 文件 | 11,060 |
| TeX 文件 | 1,675 |
| Markdown/TeX 意群 | 2,133,466 |
| 精确重复文档 | 6,073 |
| 乱码或不可读文档 | 9 |
| 最终严格词条 | 1,400 |

在最终 1,400 条中，**1,106 条合并出现不少于 100 次**，1,346 条不少于 50 次，最低也有
14 次语料命中。因此“至少 1,000 个高频词和词组”不是用零频人工扩写凑数；每条都有实际语料支持。

聊天侧仍只取 assistant 正文，不取用户消息、工具输出、reasoning、系统提示或开发者提示。
Markdown/TeX 先剔除代码围栏、内联代码、URL、路径、TeX 注释、数学环境和命令，再按句末、
分号、冒号、换行以及长句逗号拆成意群。排名同时记录聊天消息覆盖、Markdown/TeX 意群覆盖、
文件覆盖和总出现次数。重复文件保留在审计清单中，避免把“发现文件”误写成“独立语料”。

### 12.2 1400 条词项的意群构成

| 意群 | 词条数 | 代表抓手 |
|---|---:|---|
| 过程播报 | 246 | `当前、下一步、本轮、接下来、先把` |
| 完成闭环 | 135 | `已完成、闭环、收尾、收口、定版、全量测试` |
| 审计治理 | 192 | `验证、审计、复核、清关、门禁、可追溯` |
| 范围边界 | 155 | `不得、不能、固定、范围、边界、只保留` |
| 否定纠偏 | 98 | `不是、而不是、不等于、更准确、核心问题` |
| 过渡路标 | 73 | `因此、同时、进一步、综上、换言之` |
| 重点提示 | 38 | `值得注意、需要指出、需要强调、可以看出` |
| 学术包装 | 170 | `机制、框架、体系、路径、构建、形成、支撑` |
| 论文自证 | 38 | `结果表明、本文提出、奠定基础、提供支撑` |
| 建议展望 | 53 | `未来工作、后续研究、有必要、可以继续` |
| 确定性限定 | 164 | `已经、完全、稳定、真实、实际生效` |
| 助手邀请 | 38 | `如果你愿意、我可以、告诉我、我再补` |

这里故意保留了“当前、机制、框架、方法、条件”等会产生误伤的普通词。原因不是这些词天然属于
AI，而是本轮策略按用户要求选择高召回：命中后一律记录和拦截，真正的专业术语再逐位置豁免。
这种设计会增加人工处置量，但能直接消除“模型觉得没必要改”的保守逃逸路径。

### 12.3 Skill 中的严格门

`humanize-academic-chinese` 现默认使用 `lexical_policy=STRICT_CORPUS`。1400 条词项按上述 12 个
意群写入独立 `LEX-STRICT-CORPUS-*` 信号，统一配置为 `severity=high`、`action=REWRITE`、
`min_occurrences=1`。执行含义如下：

1. 写候选稿前先扫描 before，逐位置建立 strict finding 清单。
2. after 中每个命中必须删除、改写，或给出绑定行列/finding hash 的专业功能 KEEP 理由。
3. 一个笼统理由不能覆盖同一信号的多个位置。
4. 把“构建”换成“形成”、把“支撑”换成“保障”仍属于未处理。
5. 代码、公式、引语和 TeX 保护区自动 KEEP，不要求人工理由。
6. 任一未解释 strict finding 都使 `strict_no_change_allowed=false`，并阻断 BODY/CLEAN 发射。
7. 无法安全修改时只能降级 `PATCH/UNRESOLVED`，不能声称无需改动。

为了防止词库被悄悄缩短，扫描器会验证：库存不少于 1000 条、实际数量与声明一致、词条唯一、
每条有正数语料支持、12 组 signal 与库存逐项相等、所有 strict signal 保持 `high/REWRITE/1`。
任一条件漂移都会令词库加载失败，而不是静默回到宽松策略。

### 12.4 产物与复核入口

- 完整 1400 条排名：`C:\Users\Lenovo\.codex\reports\humanize-strict-lexicon-20260801\strict_ai_phrase_rankings.csv`
- 含逐词来源计数的 JSON：`C:\Users\Lenovo\.codex\reports\humanize-strict-lexicon-20260801\strict_ai_phrase_inventory.json`
- 12 组摘要：`C:\Users\Lenovo\.codex\reports\humanize-strict-lexicon-20260801\strict_ai_phrase_report.md`
- 全部 MD/TEX 文件审计：`C:\Users\Lenovo\.codex\reports\humanize-strict-lexicon-20260801\file_manifest.csv`
- 运行时词库：`C:\Users\Lenovo\.codex\skills\humanize-academic-chinese\references\lexical-signals.json`

这次升级解决的是“机器腔召回不足和执行过于保守”，不是证明 1400 个词都只由 AI 使用。
严格层的定位是高召回终审：宁可多报、逐项 KEEP，也不再让明显模板词因为单次出现而自动放过。

## 13. 历史阶段：词根拆解与 4455 条严格搭配扩榜

> 本节保留 2026-08-01 中间版本的统计与决策脉络，便于复核策略怎样演化；它不再代表当前
> 安装态。当前 5924 条根闭包版本、守恒台账和执行契约以第 14 节为准。

第 12 节记录的是第一阶段 1400 条基线。继续人工阅读 CSV 后可以看到，四至八字的大词组中还
反复藏着相同的小词，原先的最短候选门槛又漏掉了 `更稳` 这类二字评价壳。本轮因此不再只做
“大短语排名”，而是把已有严格词组拆开寻找词根，再沿词根回到全部聊天和文档中寻找完整搭配。

这里有一条不可混淆的边界：**单字是发现索引，不是 literal ban；真正进入 Skill 的仍是有
位置、有边界、有当前语料覆盖的 2–8 字搭配。** 例如 `稳` 可以把扫描引向 `更稳`，但不能据此
删除“稳态”“稳定性”中的单字。

### 13.1 最终冻结快照

| 数据项 | 最终值 |
|---|---:|
| 聊天 JSONL 快照 | 2,984 个 |
| 含有效 assistant 正文的聊天文件 | 2,679 个 |
| JSONL 扫描行 | 5,645,554 |
| assistant `output_text` | 168,762 条 |
| 非法 JSON 行 | 0 |
| 跳过的乱码 assistant 消息 | 313 条 |
| 聚合连续汉字 n-gram | 7,155,460 条 |
| MD/TEX 快照文件 | 26,038 个 |
| 实际读取 Markdown | 21,256 个 |
| 实际读取 TeX | 4,773 个 |
| MD/TEX 意群 | 3,358,707 个 |
| 精确重复文档 | 9,284 个 |
| 乱码或不可读文档 | 9 个 |

聊天仍只取 `response_item` 中 assistant 的 `output_text`。用户正文、system/developer、reasoning、
工具调用和工具输出不进入词频。文档侧剔除代码围栏、路径、URL、TeX 命令和数学环境；乱码文件
按要求记录后跳过。每个文件在扫描开始时冻结字节长度，运行中追加的会话内容不会混入该文件。

### 13.2 四条发现路线

| 路线 | 最终词条 | 作用 |
|---|---:|---|
| 原 1400 条基线中仍有当前覆盖 | 1,346 | 保留已经验证且本轮仍出现的严格词项。 |
| 父词拆出的隐藏小词 | 109 | 要求藏在多个父词中，并在聊天与 MD/TEX 中分别取得覆盖。 |
| 单字发现根扩出的完整搭配 | 2,799 | 先找单字根，再只接纳边界完整的 2–8 字家族成员。 |
| 独立长词组 | 101 | 从 715 万条聚合 n-gram 中独立发现，不依赖旧父词。 |
| 比较评价词根族 | 100 | 单独处理 `更/很/最/较/太/愈 + 评价根`，补回二字短壳。 |
| **最终严格库存** | **4,455** | 比 1400 条基线净增 3,055 条。 |

证据范围不是统一伪装成“双语料”：2,917 条同时有聊天与文档覆盖，1,530 条为聊天侧高频，
8 条为文档侧高频。每条的 `evidence_scope`、聊天消息覆盖、Markdown/TeX 意群覆盖和文件覆盖均
保留在 CSV/JSON 中。原基线有 54 条在最终快照中零覆盖，已移入 stale 审计表而不是继续冒充
活跃禁用词。

### 13.3 单字发现根如何工作

脚本先对 500 个汉字建立根台账，记录它们出现于多少个既有父词、跨多少个意群、在父词中的
首中尾位置，以及包含该字的完整 n-gram 家族覆盖。最终 204 个根通过发现门；其余 296 个被
以下原因拦截：116 个功能字停用、168 个父词不足 3 条、11 个跨意群不足 2 类、1 个家族最大
消息覆盖不足 50。

单字通过发现门仍不等于进入禁用表。候选必须继续满足：

1. 形成 2–8 字连续汉字片段；
2. 命中一个完整风格标记，或使用经人工确认的比较/评价壳；
3. 避开连接词开头、功能字结尾和固定宽度截断；
4. 在当前冻结聊天或文档中精确复计；
5. 合并覆盖和出现次数均不少于 80；
6. 不被一个覆盖更高、语义更完整的长片段支配；
7. 通过最终 required/forbidden 回归哨兵。

因此，`稳`、`准`、`清`、`强` 是检索入口，Skill 的扫描器实际匹配的是 `更稳`、`更准`、
`更清楚`、`更强` 等库存短语。`lexical-signals.json` 明确记录
`bare_single_character_bans=0`。

### 13.4 “稳”及比较评价族的真实覆盖

| 搭配 | 聚合聊天消息覆盖 | 当前聊天消息覆盖 | MD/TEX 意群覆盖 | 合并覆盖 |
|---|---:|---:|---:|---:|
| `更稳` | 2,527 | 4,797 | 1,560 | 6,357 |
| `会更稳` | 160 | 364 | 9 | 373 |
| `这样更稳` | 97 | 156 | 0 | 156 |
| `更稳一点` | 224 | 391 | 0 | 391 |
| `更稳的说法` | 104 | 177 | 2 | 179 |
| `更稳的写法` | 99 | 152 | 1 | 153 |
| `改成更稳` | 123 | 390 | 0 | 390 |
| `最稳` | 2,216 | 3,165 | 535 | 3,700 |
| `更稳妥` | 152 | 352 | 102 | 454 |
| `更好` | 1,545 | 2,242 | 2,956 | 5,198 |
| `更自然` | 1,159 | 1,820 | 1,206 | 3,026 |
| `更强` | 859 | 1,378 | 1,629 | 3,007 |
| `更准` | 1,370 | 1,795 | 616 | 2,411 |
| `更清` | 482 | 1,069 | 368 | 1,437 |
| `更清楚` | 438 | 875 | 197 | 1,072 |
| `更成熟` | 516 | 1,126 | 46 | 1,172 |

这说明 `……更稳` 不是印象判断，而是大规模助手语料中反复出现的句尾评价壳。它常把选择写成
一种没有展开判据的工程判断：不是说明哪项约束、误差或读者成本发生了变化，而是用“更稳”
快速封口。Humanize 命中后应追问并改写具体依据，不能机械换成“更可靠”或“更合适”。

`更全` 在聚合表中仅约 14 条消息覆盖，低于当前 80 的严格入表门槛。本轮把它保留在发现证据
而不硬塞入禁用表；这也是“积极扩榜”与“凭空造词”之间的边界。

### 13.5 从大词组中拆出的 109 个小词

父词拆解不是简单截取所有 2–6 gram。候选必须出现在至少三个二字父词或两个三字以上父词中，
左右上下文不能被单一字符固定，同时聊天和文档侧分别达到门槛。最终留下的高覆盖项包括
`处理、一步、运行、读取、修改、编译、发现、支持、推进、会话、我建议、当前会话、完整性、
重新计算、先运行、继续修`。

其中一些是正常技术词，不是“AI 专属词”。它们仍进入 strict 层，是因为本轮按用户要求选择
高召回、低漏检策略：正文命中时先记录，再由位置级 KEEP 保护真正不可替代的技术含义。模型
不能用一句“这是专业术语”批量放行，也不能因为单次命中就宣布无需修改。

### 13.6 高频不等于完整：54 个父词碎片的人工回退

第一次扩榜后人工读 CSV，发现 `下一、当前文、机器结、证据支、由此可、尚未完` 等片段也会
因为藏在多个大词组中而取得高频。它们没有独立表达功能，不能作为可执行的禁词。最终增加
`known_subphrase_fragment` 门，一次剔除 54 条，并把以下失误写进回归测试：

- 比较级伪前缀：`成更稳、文更自然、前最稳妥、个更稳`；
- 普通技术词误扩：`持久化、目标值`；
- 定宽尾巴：`目标不、完整读取并、继续压了、续成熟化`；
- 父词截断：`机器结、证据支、由此可、尚未完`。

发布门同时要求 `更稳、会更稳、这样更稳、更稳一点、更稳的说法、更稳的写法、更好、更清、
更强、更准、更自然` 必须存在。任何后续阈值或边界改动只要漏掉确认族，或让已知碎片回流，
脚本就直接失败，不生成完成态词库。

### 13.7 写入 Skill 后的实际执行含义

最终库存已写入：

`C:\Users\Lenovo\.codex\skills\humanize-academic-chinese\references\lexical-signals.json`

安装器把 4,455 条词项重建为 12 个 `LEX-STRICT-CORPUS-*` 信号，统一为
`severity=high`、`action=REWRITE`、`min_occurrences=1`。库存源文件 SHA-256 为
`1ecb8885c480467afeca07044f22e38e4fc4c5dd97cf27a91f1d492507c92b80`。

这意味着：`更稳` 一旦出现在非保护正文中，扫描器必须生成 finding；候选稿要么删掉评价壳，
要么写出实际比较依据，要么提供绑定具体位置的不可替代 KEEP 理由。未处理 finding 会阻断
`NO_CHANGE/CLEAN`。代码、公式、引语和 TeX 保护区仍自动保留，学术正确性仍由独立门负责。

### 13.8 最终产物

- 完整库存：`C:\Users\Lenovo\.codex\reports\humanize-strict-lexicon-20260801-pass4h\strict_ai_phrase_inventory_expanded.json`
- 4455 条逐项排名：`C:\Users\Lenovo\.codex\reports\humanize-strict-lexicon-20260801-pass4h\strict_ai_phrase_rankings_expanded.csv`
- 单字根台账：`C:\Users\Lenovo\.codex\reports\humanize-strict-lexicon-20260801-pass4h\single_character_root_rankings.csv`
- 109 条隐藏小词：`C:\Users\Lenovo\.codex\reports\humanize-strict-lexicon-20260801-pass4h\new_hidden_subphrases.csv`
- 100 条比较评价族：`C:\Users\Lenovo\.codex\reports\humanize-strict-lexicon-20260801-pass4h\new_comparative_root_phrases.csv`
- 2799 条单字根完整搭配：`C:\Users\Lenovo\.codex\reports\humanize-strict-lexicon-20260801-pass4h\new_single_root_phrases.csv`
- 全部淘汰原因：`C:\Users\Lenovo\.codex\reports\humanize-strict-lexicon-20260801-pass4h\rejected_after_exact_rescan.csv`
- 扩榜报告：`C:\Users\Lenovo\.codex\reports\humanize-strict-lexicon-20260801-pass4h\strict_ai_phrase_expansion_report.md`

本轮证明的是这些片段在 GPT 生成语料中反复出现，并且足以作为高召回文风编辑抓手；它不证明
词条只由 AI 使用，也不证明命中数量可以判断作者身份。真正的执行目标是阻止模型以“看起来
没问题”为由跳过改写，同时保留位置级术语豁免和人工终审。

## 14. 根优先全量闭包：从“用户能随手指出漏词”反推发现策略

### 14.1 为什么旧策略会漏掉明明很高频的短根

`稳` 和 `收紧` 暴露的不是两个孤立漏项，而是候选生成方向错了。旧流程以已经成形的四至八字
短语为中心，再从排行榜里看高频项。这个方向至少有六个系统性盲点：

1. **最短长度门槛吞掉短壳。** 原候选至少四字，`更稳`、`收紧` 甚至没有进入比较范围；
2. **Top-K 把长尾词根挤掉。** 一个根可以分散在几十种完整搭配中，每个搭配单独排名不高，
   但合并后覆盖极大；
3. **从完整词往下拆，受旧词表先验约束。** 没进旧表的家族不会反过来生成新根；
4. **一次扫描无法闭包。** 第一轮新增短语本身还可能暴露第二轮新根，只跑一轮不能声称完整；
5. **纯频率会把主题词误认成风格词。** `泰勒展开、随机切分、匹配空串` 很高频，但主要来自
   学科内容；
6. **只看最终条数，没有根级守恒。** 即使一个高覆盖根的全部候选被意外丢失，总表仍可显示
   “新增为零”。

因此，正确顺序必须倒过来：先把单字和二至三字短根当作发现索引，再回到冻结语料中扩出完整
搭配；根负责召回，完整搭配及其上下文负责发布。裸根不直接成为禁词。

### 14.2 冻结语料与两种正文视图

本轮复用同一冻结快照，避免活动会话在迭代之间继续追加而制造假新增。聊天仍只纳入
`response_item` 中 `role=assistant` 且内容类型为 `output_text` 的正文；用户消息、系统与开发者
提示、reasoning、工具调用和工具输出不参与词频。MD/TEX 先剔除代码围栏、TeX 命令、数学环境、
URL 和路径；无法可靠解码的内容登记后跳过。

| 数据项 | 当前冻结值 |
|---|---:|
| 聊天 JSONL 快照 | 2,990 个 |
| assistant `output_text` | 168,791 条 |
| 跳过的乱码 assistant 消息 | 313 条 |
| 聚合连续汉字候选行 | 7,155,460 条 |
| MD/TEX 快照路径 | 26,042 个 |
| 精确复计读取 Markdown | 13,096 个 |
| 精确复计读取 TeX | 3,642 个 |
| 精确重复文档 | 9,278 个 |
| 精确复计语义单元 | 3,463,027 个 |
| 精确复计跳过的乱码/不可读文档 | 26 个 |
| n-gram 发现视图去重后读取文件 | 16,710 个 |
| n-gram 发现视图语义单元 | 3,343,863 个 |

“精确复计语义单元”和“n-gram 发现语义单元”不是统计冲突：前者用于候选的最终原位计数，后者
先做更严格的文档去重和风格正文过滤，用于发现种子。报告同时列出两者，不能混成一个数字。

### 14.3 当前根优先算法

#### A. 宽发现，不设 Top-K

- 对 2–8 字连续汉字候选保留完整计数，不以展示排行榜截断候选池；
- 从已确认词项、文档短串和聚合聊天短串中抽出单字窗口，记录父词数、父词类别、首中尾位置、
  左右上下文、消息覆盖、文档单元覆盖和文件分散度；
- 同时对完整父短语枚举 1–3 字窗口，反推带比较壳、程度壳、过程壳和句尾评价壳的复合发现根；
- 单字根只进入发现台账，不允许直接进入 literal ban。

本轮共排序 1,761 个单字根，1,078 个进入宽召回层；在更严格的完整壳、父词分散度和上下文门后，
266 个 1–3 字根进入完整家族扫描。

#### B. 沿根扩完整搭配

对每个发现根回扫所有候选，扩展根左右两侧，保留 2–8 字完整片段。完整性不是“字数够长”，
而是至少满足一种可审计边界：

- 根本身是可独立定位的二至三字核心；
- 前后缀构成完整的比较、程度、状态、建议、完成或过程壳；
- 左右边界在真实上下文中均有足够分散度，不被单一相邻字支配；
- 短语在句首、句尾或独立分句边界反复出现，而不是固定宽度截断。

这一步会保留 `更稳、会更稳、更稳一点、进一步收紧、收紧一点`，但淘汰 `成更稳、步收紧、
收紧一、续成熟化` 等半截字符串。

#### C. 精确复计与双来源证据

所有候选重新回到冻结 JSONL、MD 和 TEX 中逐字计数，记录消息覆盖、语义单元覆盖、文件覆盖、
左右边界率和上下文优势度。根发现阶段的聚合数只用于召回，不能直接充当发布证据。

跨聊天和文档均出现的候选证据更强；少量已在历史人工高精度表中确认的 chat-only 片段仍保留，
但必须显式标记 `evidence_scope=chat-only`，不能伪称双来源。后续新增小根默认优先要求两侧真实
覆盖。

#### D. 风格门与技术内容门分开

高频不自动等于机器腔。候选还要区分：

- 助手过程播报、完成封口、审计治理、建议展望、比较评价等风格功能；
- 公式、算法、编译、数据结构和学科术语等内容功能；
- 普通功能词、固定宽度碎片和被更完整长串支配的片段。

例如 `展开` 能召回 `不再展开` 和 `泰勒展开`；前者可能是自动收尾壳，后者是数学术语。发现根
相同，不意味着发布动作相同。专业含义不能因为根命中而被删除。

### 14.4 一次失败实验：无限放宽 n-gram 为什么不行

为了检查召回上限，曾运行不限制独立长串路线的三轮闭包：

| 轮次 | 基线 | 最终 | 新增 |
|---|---:|---:|---:|
| 1 | 5,891 | 7,118 | 1,227 |
| 2 | 7,118 | 7,445 | 327 |
| 3 | 7,445 | 7,532 | 87 |

表面上它持续“发现新词”，实际新增几乎全来自固定宽度独立切片。抽查出现 `个严格受、件复制成多个、
前向代理完` 等没有独立表达功能的碎片；其中 1,599 条只因独立长串路线进入，不具备可靠词根或
边界证据。这条路线没有安装进 Skill。

失败实验说明：**无 Top-K 不等于无发布门。** 候选池可以尽量宽，最终禁用片段必须能回到一个
发现根、一个完整边界和一组真实覆盖。当前正式闭包启用 `root-closure-only`，独立长串只作发现
材料，不再单独取得发布资格。

### 14.5 正式闭包结果

正式根闭包以 5,891 条根优先清单为起点：

| 轮次 | 基线 | 最终 | 新短语 | 新发现根 | 候选池截断 |
|---|---:|---:|---:|---:|---:|
| 1 | 5,891 | 5,924 | 33 | 0 | 0 |
| 2 | 5,924 | 5,924 | 0 | 0 | 0 |

停止条件不是单一的“最终条数相同”，而是同时满足：

1. 第二轮合格完整短语新增为 0；
2. 强发现根新增为 0；
3. 子词池、长词池、文档种子池和根家族池均无 quota/Top-K 丢弃；
4. 所有强发现根的候选都有发布或明确拒绝去向，无未路由行；
5. 快照、聚合聊天文件和复用的精确计数缓存均通过内容绑定。

最终库存 5,924 条，比上一安装态 4,455 条增加 1,469 条；其中根优先首个冻结版已经增加 1,436
条，闭包再补 33 条。第二轮候选和计数绝大部分从同一内容哈希缓存复用，只重新扫描新增候选；
缓存只有在聚合文件及两份快照文件集绑定一致时才允许使用。

### 14.6 `稳` 家族：从单字根到实际禁用片段

当前库存中共有 98 条短语含 `稳`。裸字 `稳` 不禁；以下完整搭配才是可定位 finding：

| 搭配 | 聊天消息覆盖 | MD 单元 | TEX 单元 | 合并覆盖 | 证据范围 |
|---|---:|---:|---:|---:|---|
| `更稳` | 4,798 | 78 | 1,268 | 6,144 | chat-and-document |
| `会更稳` | 364 | 4 | 6 | 374 | chat-and-document |
| `这样更稳` | 157 | 1 | 0 | 158 | chat-and-document |
| `更稳一点` | 392 | 1 | 0 | 393 | chat-and-document |
| `更稳的说法` | 177 | 2 | 1 | 180 | chat-and-document |
| `更稳的写法` | 152 | 1 | 1 | 154 | chat-and-document |
| `更稳的做法` | 91 | 1 | 25 | 117 | chat-and-document |

`……更稳` 的机器感不来自“稳”这个字，而来自它经常在没有比较维度时替代判断：省略了更低的
误差、更少的假设、更小的维护成本或更明确的适用范围。改写动作不是把它机械换成“更可靠”，
而是恢复原材料中已经存在的具体比较依据；材料没有依据时删除无功能评价或标 `UNRESOLVED`。

### 14.7 `收紧` 家族：从过程动词到治理式旁白

当前库存中共有 12 条短语含 `收紧`：

| 搭配 | 聊天消息覆盖 | MD 单元 | TEX 单元 | 合并覆盖 | 证据范围 |
|---|---:|---:|---:|---:|---|
| `收紧` | 4,207 | 111 | 106 | 4,424 | chat-and-document |
| `再收紧` | 470 | 0 | 0 | 470 | chat-only |
| `继续收紧` | 246 | 1 | 0 | 247 | chat-and-document |
| `进一步收紧` | 196 | 5 | 0 | 201 | chat-and-document |
| `收紧一点` | 207 | 0 | 0 | 207 | chat-only |
| `口径收紧` | 94 | 1 | 0 | 95 | chat-and-document |

`收紧` 常把“删哪些范围、提高哪个阈值、减少哪类例外”压成编辑后台动作。它也可能是合法术语，
如“收紧约束上界”。所以默认 strict finding 要求处理，但技术含义允许用位置级 KEEP 理由保留；
不能用一句“这是术语”批量豁免全文。

### 14.8 根级守恒台账：不再把灰区藏在总数里

266 个强发现根逐一建立以下守恒字段：

```text
root
inventory_hit_count
family_candidate_count
family_selected_for_exact_rescan_count
exact_rescan_candidate_count
released_candidate_count
terminal_rejection_count
unrouted_candidate_count
terminal_rejection_reasons
```

当前结果为 249 个根至少发布一个完整搭配，17 个根零发布但全部候选已有终态拒绝，未路由候选为
0。17 个复核根是：

`申请提、后面、根据、像论文、额外、理解、一条、切分、细化、匹配、展开、结合、只剩、产生、
编译一、直接读、直接作`。

这 17 个根不能简单视为“漏词”。抽样显示：

- `展开` 同时覆盖 `泰勒展开、傅里叶展开、不再展开`，技术义和收尾壳混在同一根下；
- `细化` 同时覆盖 `几何细化、条件性细化、进一步细化`；
- `匹配` 的高覆盖项包括 `匹配空串、匹配路径`，主要是技术内容；
- `编译一` 主要扩出 `编译一次、编译一遍`，属于工具过程，不应自动污染学术正文；
- `像论文`、`现在只剩`、`直接作为最终` 更接近助手旁白，但部分候选只有聊天覆盖；
- `根据、理解、产生` 是普通表达根，必须依靠完整搭配和位置功能，不能把裸词一刀切。

它们现在以 `TERMINAL_REJECTED_REVIEW` 留在台账，而不是从报告消失。后续若人工确认某个完整搭配，
应把该搭配作为新候选进入精确复计，不能直接把整个根升级为禁词。

### 14.9 闭包新增的 33 条及精度警告

闭包第一轮新增：

`现在回到、会回到、继续补强、不回到、已经回到、不要让它、再让它、完整性清单、一份完整、
不升级、错误升级、必须列出、要升级、顺序重写、写清楚、让读者、不会静默、保留少量、不声明、
避免再次、会再次、最后封口、最后警告、所以最后、要最后、需要注意、必须注意、克制、更克制、
很克制、直接列出、回来、明显错误`。

这些条目满足当前高召回规则，但 `回来、会回到、一份完整、所以最后、要最后` 等仍有普通表达
误报风险。它们进入 strict 层的含义是“命中必须处置”，不是“出现即判 AI”。若原句承担明确
时序、空间返回或专业功能，应使用位置级 KEEP；若只是助手过程播报，则删除或写成对象事实。

### 14.10 执行层修复：防止 Skill 再说“什么都不用改”

旧安装态存在两个会导致假完成的问题：扫描器只要求词表不少于 1,000 条，且 policy schema 与
安装器已经漂移。即使词表被替换，或者扫描器根本无法加载，外围调用也可能只看到宽松结果。

当前安装态做了四层绑定：

1. policy schema 统一为 `humanize-strict-corpus-policy/v3`；
2. 精确条目数固定为 5,924，而不是“至少 1,000”；
3. 对完整 inventory 规范化排序并计算 SHA-256：
   `44ebe19134a6ca5c99d736f3476706569935ec8e254734437c924e946ae2a94d`；
4. 扫描器启动时重算哈希，并核对 12 组 strict signal 的 variants 与 inventory 完全相等。

删除、替换或改分类一条词项，即使同步篡改声明数量，也会令词库加载失败。安装源文件 SHA-256 为
`7e8fdc76f2717ef9952035d99909808a560e1853aef7bb8356413715d38c3d47`。

验证器也不再把“原文和候选字节相同但仍含 strict finding”写成可误读的 `NO_CHANGE`。这种情况
现在进入 `BLOCKED_NO_CHANGE`，`decision_eligible=false`，机械状态和交付状态均为 `REVIEW/2`；
只有逐处改写、删除或给出有效的位置级 KEEP 理由后，strict 层才允许 no-change 判断继续向下走。

### 14.11 复现与审计入口

- 正式闭包清单：`C:\Users\Lenovo\.codex\reports\humanize-strict-lexicon-20260802-root-closure-v2\round-02\strict_ai_phrase_inventory_expanded.json`
- 逐项排名：`C:\Users\Lenovo\.codex\reports\humanize-strict-lexicon-20260802-root-closure-v2\round-02\strict_ai_phrase_rankings_expanded.csv`
- 全候选及精确计数：`C:\Users\Lenovo\.codex\reports\humanize-strict-lexicon-20260802-root-closure-v2\round-02\all_candidates_after_exact_rescan.csv`
- 所有淘汰理由：`C:\Users\Lenovo\.codex\reports\humanize-strict-lexicon-20260802-root-closure-v2\round-02\rejected_after_exact_rescan.csv`
- 强发现根：`C:\Users\Lenovo\.codex\reports\humanize-strict-lexicon-20260802-root-closure-v2\round-02\root_inversion_selected_roots.json`
- 根守恒台账：`C:\Users\Lenovo\.codex\reports\humanize-strict-lexicon-20260802-root-closure-v2\round-02\root_release_accounting.csv`
- 收敛状态：`C:\Users\Lenovo\.codex\reports\humanize-strict-lexicon-20260802-root-closure-v2\root_closure_manifest.json`
- 当前运行时词库：`C:\Users\Lenovo\.codex\skills\humanize-academic-chinese\references\lexical-signals.json`

复现脚本位于本工作区：

- `scripts/expand_humanize_strict_lexicon.py`：根发现、完整家族扩展、精确复计和发布门；
- `scripts/run_humanize_root_closure.py`：固定快照迭代、候选缓存、根守恒和停止条件；
- `scripts/apply_expanded_strict_inventory.py`：审核态哈希绑定与安装。

### 14.12 这套方法能证明什么、不能证明什么

它能证明 5,924 个片段在已冻结的 GPT 助手聊天和 GPT 生成文档中有可复核覆盖，并且当前 Skill
会把其非保护区命中作为高召回改写候选。它还能证明候选池没有因 Top-K 或 quota 静默丢弃，强
发现根的所有精确候选都有发布或拒绝去向。

它不能证明这些词只由 AI 使用，也不能依据命中数判断作者身份；当前正向语料并不是一套严格
匹配主题、年代和体裁的人类对照库。`更稳、根据、产生` 等词在人类写作中同样可能自然出现。
因此，禁用表是编辑抓手，不是作者分类器；专业术语和真实表达功能仍需位置级 KEEP，最终文风
质量仍是 `PENDING_EXTERNAL_REVIEW`，学术正确性仍是 `NOT_EVALUATED`。
