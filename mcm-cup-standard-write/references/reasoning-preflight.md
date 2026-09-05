# 分问推演预审门

## 目的

长稿最容易被迫大修的时刻，不是排版，而是写到十几页以后才发现某个分问的事实依据、数学转化或路线本身没有被队员确认。这个门把确认移到扩写之前：每问只用一份短记录，确认**已冻结来源中的事实锚点**怎样落到**当前数学对象**，以及**选定路线**是否就是准备写入正文的路线。

它不是向模型索要隐藏思维链，也不把“观察、比较、选择”改造成统一段式。队员看到的是本问的具体对象和短路线图；正文仍按实际关系、推导、前问接口、试算回退或结果解释自然展开。

## 使用时机

1. 先在工作台目录冻结题面、数据、代码、结果等源文件，并完成 `modeling-workbench.json`。
2. **在生成任一分问的长正文前**，由负责该问的队员填写 `reasoning-preflight.json`，审批一页以内的事实、数学落点和路线。
3. 运行：

```powershell
python scripts/audit_reasoning_preflight.py modeling-workbench.json --approval reasoning-preflight.json --format text
```

4. 只有该问为 `approve`，才扩写该问。若新增事实、换数据、改代码、改结果、改锚点或改路线，工作台 SHA-256 改变，旧预审自动失效；应回到本步骤重新确认，不得在长稿末尾补贴理由。
5. 成稿后仍运行 `audit_modeling_workbench.py`，确认正文实际写出了已批准的“锚点 -> 数学落点 -> 路线”；最后的 [思考桥复述](reasoning-review.md) 只检查正文有没有偏离预审，不负责替整稿重新选路。

## 最小记录

```json
{
  "schema": "mcm-reasoning-preflight/v1",
  "workbench_sha256": "<modeling-workbench.json 的 sha256>",
  "approvals": [
    {
      "question_id": "1",
      "reviewer": "队长",
      "reviewer_kind": "human",
      "anchor_ids": ["fixed-distance"],
      "target_ids": ["root-order"],
      "source_ids": ["problem", "solver"],
      "route_id": "fixed-length-recurrence",
      "basis_confirmation": "相邻构件距离固定，后续节点不能独立选择位置。",
      "transition_confirmation": "把构件次序写成极角递增后，定长递推只保留满足该可行条件的根。",
      "change_trigger": "若连接关系改为可伸缩，应重新定义递推约束，不沿用当前选根规则。",
      "decision": "approve"
    }
  ]
}
```

审计器要求 `reviewer_kind` 明确为 `human`；缺失该字段或标为 `model` 的记录不计入批准。模型可以准备预审材料，但不能批准自己将要扩写的路线。预审中的锚点、数学落点、来源和路线还必须与工作台中该问的唯一 `selected` 路线完全一致；确认文字分别触及该锚点、数学落点和路线术语。它因此能拦住“先写 25 页、最后再改模型”的流程错误。

## 记录边界

- `basis_confirmation` 只说明题面、数据、前问接口或试算事实为何重要。
- `transition_confirmation` 只说明它怎样改变变量、约束、方程、样本口径、可行域或求解任务，并为什么进入当前路线。
- `change_trigger` 只写会使本路线不再适用的真实条件；不要求每问都虚构失败路线或完整验证。
- 三段均须具体到本问对象，不能填写“经讨论同意”“综合考虑后可行”之类的空话。

通过只证明短计划、冻结源和批准记录未漂移；它不能证明审批人身份、数学正确性、实际私人思考或最终文风。它的作用是把需要队员判断的内容前移到一页以内，避免把修正成本留给完整长稿。
