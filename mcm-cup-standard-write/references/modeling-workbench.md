# 建模推演工作台

## 1. 作用与边界

这份工作台服务于起草以前的建模思考，首要目的不是审计，而是让论文正文写出“我们怎样走到这个模型”。每个分问先把题面、数据、前问输出和已经运行的计算还原为可操作的数学对象；再判断哪些关系可直接列式，哪些必须先缩域、换口径、补约束或改求解层。对非直接列式的路线，正文必须保留促成模型出现的真实节点，而不是一出现分问标题就报出模型名；这些节点可从事实、局部关系、试算、前问接口或结果反推中的任一处起步，不规定统一先后。

工作台要求的是简洁、可复核的建模底稿，不是逐字记录模型的内部思维链。不要保存或索要冗长的自言自语、概率式猜测或与结论无关的分支枚举。每条记录都应指向冻结后的题面、附件、公式、代码、图表、日志或实际试算文件；没有发生的候选比较、失败尝试和实验不得补造。

工作台的价值只有在正文中留下思考痕迹才算完成：读者应能看见哪个事实造成了什么数学问题、该问题怎样限制了表达或求解、模型又在何处接管。思考桥可以是一两句、一个推导段或一段结果后的回退解释，长短由题目决定。工作台字段顺序绝不能成为论文段落顺序。

## 2. 每问的推演面

不是每一问都要展开同样篇幅，但完成起草前至少逐项问清下列问题。

### 2.1 事实锚点

记录真正改变建模对象的输入：题面关系、数据读数、字段定义、物理或业务边界、前问接口、程序状态或一次试算结果。泛泛的“问题复杂”“数据量大”“精度要求高”不是锚点。

### 2.2 数学落点

把锚点翻译为变量、样本单位、方程、目标、约束、状态、候选集、精度口径或报告边界。此处回答的是“这项事实究竟改了哪一部分数学对象”，不是提前挑选流行算法。

### 2.3 可行路线

记录当前实际采用的路线，以及确实被考虑、推导、运行或由结构排除的其他路线。单一路线可由硬关系直接确定，此时只登记该路线；不要为了显得思考充分而虚构候选数量。若路线沿用前问，应分别写清冻结的接口和新开放的量。

### 2.4 反向检查（按需要使用）

当路线确实包含易错近似、候选筛选、参数搜索或数值结果时，再针对最脆弱的一处做挑战：边界是否满足、候选根是否符合方向、单位是否一致、方案是否可行、近似是否越界、结果能否回代，或参数微扰是否触发事件切换。它不是每问必须补的一段，更不能为了完整而虚构灵敏度或外部验证。

### 2.5 正文思考桥

对每个非直接列式的首次模型或算法，先在正文中安排一个可见的推演桥：

- A 类通常由对象关系、量级或几何/物理矛盾进入变量、方程、根筛选或离散方式；
- B 类通常由现实动作、成本触发、变量域或可行性进入目标、约束、状态和搜索层；
- C 类通常由记录粒度、字段现象、样本口径或数据形态进入数据变换、预测目标和模型输入。

这不是三种固定段式。直接由题面关系列式时，关系到公式本身就是思考过程；后问沿用接口时，应写清“前问留下什么、本问为什么只新增什么”；先有试算或异常时，应写清“它暴露了什么、后续为何改口径或缩域”。不要只放一句“考虑到……因此采用……”，也不要把所有分问写成同样的观察、比较和总结。

获奖论文中的真实做法可作为三个锚点：A053 在定长递推产生多根后，先用构件次序和极角条件完成选根判断，再用二分法落实；B026 先将散点上升趋势与转化率上界连在一起，再建立 Logistic 关系；C063 先完成变量、目标和线性约束的结构化表达，再选择 LINGO。应迁移的是“事实如何改变下一步数学动作”，不能照搬其模型或句子。

## 3. 轻量记录格式

正式竞赛稿在草稿目录维护 `modeling-workbench.json`。下列格式不是固定写作模板；`routes` 只登记真实路线，`checks` 只登记实际做过或可由已列关系完成的检查。

```json
{
  "schema": "mcm-modeling-workbench/v1",
  "sources": [
    {
      "id": "problem",
      "role": "problem",
      "path": "inputs/problem.pdf",
      "sha256": "<sha256>"
    },
    {
      "id": "solver",
      "role": "code",
      "path": "solver/position.m",
      "sha256": "<sha256>"
    }
  ],
  "questions": [
    {
      "id": "1",
      "anchors": [
        {
          "id": "fixed-distance",
          "kind": "relation",
          "terms": ["相邻构件距离固定"],
          "source_ref": "题面条件 (2)",
          "source_ids": ["problem"]
        }
      ],
      "targets": [
        {
          "id": "root-order",
          "terms": ["极角递增"],
          "source_ref": "构件顺序约束"
        }
      ],
      "routes": [
        {
          "id": "fixed-length-recurrence",
          "name": "定长递推与二分选根",
          "status": "selected",
          "terms": ["二分法"],
          "anchor_ids": ["fixed-distance"],
          "target_ids": ["root-order"],
          "evidence_ids": ["solver"],
          "evidence_ref": "solver/position.m:42-68"
        }
      ],
      "checks": [
        {
          "id": "root-direction",
          "kind": "feasibility",
          "terms": ["极角递增"],
          "result": "仅保留满足构件次序的可行根",
          "result_terms": ["可行根"]
        }
      ],
      "interpretations": [
        {
          "id": "root-order-active",
          "kind": "active_constraint",
          "observation_terms": ["可行根"],
          "explanation_terms": ["极角递增"],
          "source_ids": ["solver"],
          "source_ref": "solver/position.m:42-68"
        }
      ],
      "drafting": {
        "mode": "relation_then_method",
        "public_route_id": "fixed-length-recurrence",
        "keep_out_of_manuscript": "代码层的常规迭代细节"
      }
    }
  ]
}
```

字段含义：

- `sources` 冻结实际题面、数据、代码、结果、图表、日志或前问输出文件。`role` 取 `problem`、`data`、`code`、`result`、`figure`、`log` 或 `prior-output`；路径必须位于工作台目录内，且 SHA-256 与当前文件一致。
- `anchors` 是事实锚点。`kind` 取 `relation`、`data`、`constraint`、`interface`、`trial`、`result`、`boundary` 或 `structure`。每个锚点以 `source_ids` 指向实际冻结源，`source_ref` 只记录页码、字段、函数或图表定位，不能单独充当证据。
- `targets` 是本问需要落到的数学对象或关键技术问题，不是算法宣传词。
- `routes` 的 `status` 取 `selected`、`rejected` 或 `deferred`；每问恰有一个 `selected`。每条路线以 `evidence_ids` 绑定实现、结果或题面源。`rejected` 与 `deferred` 仅在确有依据时登记，并给出 `reason` 与 `evidence_ref`。
- `checks` 是可选字段。确有相关工作时，其 `kind` 取 `derivation`、`boundary`、`feasibility`、`counterexample`、`unit`、`sensitivity`、`replay`、`residual` 或 `implementation`。检查可由正文中的术语定位，也可由 `artifact` 指向实际的代码、图表或结果文件；后者宜附 SHA-256。需要在检验章节核对“检查动作与结论是否连在一起”时，再填写非空 `result_terms`；不能从 `result` 句子自动猜词。
- `interpretations` 也是可选字段，只记录确实由代码、结果、图、日志或前问输出支持的结果解释。`kind` 取 `active_constraint`、`event_switch`、`trend`、`exception`、`comparison`、`mechanism`、`uncertainty` 或 `boundary`；`observation_terms` 定位看到的结果对象，`explanation_terms` 定位正文要公开承担的解释对象，`source_ids` 至少包含一个 `code/result/figure/log/prior-output` 来源。没有这类证据时保持空数组，不为满足章节形式补造原因。
- `drafting.mode` 仅描述写入位置，可取 `direct_derivation`、`relation_then_method`、`interface_extension`、`result_then_refine` 或 `method_after_structure`。它不规定论文必须使用这些词，也不要求各问轮换模式。

## 4. 执行顺序

1. 把题面、附件、代码、日志和已有结果归档到工作台目录，记录角色、相对路径和 SHA-256；之后任何源文件变化都会使旧工作台失效。
2. 每问填写事实锚点与数学落点，先不急于给模型命名。
3. 只记录确有事实支持的路线；直接列式时写 `direct_derivation`，不要强造比较。
4. 在扩写任何分问的长正文以前，完成 [分问推演预审](reasoning-preflight.md)。它只核对本问的冻结来源、锚点、数学落点和选定路线是否已经由队员确认；未通过的分问不要先写成长稿。若工作台或任一冻结来源变化，旧预审失效，先重审再续写。

```powershell
python scripts/audit_modeling_workbench.py main.tex --workbench modeling-workbench.json --phase preflight --format text
python scripts/audit_reasoning_preflight.py modeling-workbench.json --approval reasoning-preflight.json --format text
```

`preflight` 只验证来源、结构和分问映射，不要求初稿已经写出准备补入的判断桥；否则“直接跳模型”的原稿会在改写前被循环阻断。

5. 把“事实锚点 -> 数学落点 -> 选定路线”写进已批准分问的正文实际位置；这是主要产物。根据直接推导、前问承接、试算回退或结果解释选择不同节奏，不照抄工作台字段。若登记了 `interpretations`，结果段应让相应观察与解释在局部形成关系；若登记了检查的 `result_terms`，检验段应同时写清实际检查和它支持的结论。
6. 只在确有风险点时补相关的反向检查，并记录没有解决的边界或需要补取的证据。
7. 完成初稿后运行审计，确认工作台中的选定路线在本问正文中有完整的“锚点 -> 数学落点 -> 路线”思考桥；已声明的检查再检查其支撑位置：

```powershell
python scripts/audit_modeling_workbench.py main.tex --workbench modeling-workbench.json --phase release --format text
```

8. 最后才运行 `audit_judgment_ledger.py`，检查正式正文中被声明的方法没有在本问空降。

## 5. 不通过的替代品

- 只列模型名称和优点，没有把题面事实翻译为数学对象。
- 为每问强行填写“基线、候选、改进、验证”四项，即使这些工作没有发生。
- 把最终结果倒灌为事前理由，或把一次内部回代写成外部验证。
- 把工作台原样贴入“问题分析”，造成所有分问同一首句、同一顺序、同一收束。
- 用 `reason` 写“经过深入思考”“综合分析后认为”等不可复核叙述，而没有对象、条件或证据位置。

## 6. 审计边界

工作台审计器有两个阶段：`preflight` 检查结构、冻结源文件的路径和 SHA-256、分问映射以及路线记录；`release` 才进一步要求候选正文存在“事实锚点 -> 数学落点 -> 路线”的局部联系，并核对已声明的检查。分问预审在扩写以前锁定每问的短路线图。两阶段都不能自动判断 PDF 中的某句题面是否真的支持锚点，也不能证明数学正确；最终仍须由队员对题面、代码、结果和论文复述。它们的价值在于把“要先想清楚并写出来”变成可执行的建模准备，而不是把推理伪装成一套可检测的套话。
