# 分问公开判断账本

这是一份写作前的私有核对材料，不是正文提纲，不是隐藏推理记录，也不能作为“已经比较多个模型”的证据。它只登记实际发生且可公开核对的桥梁：哪条题面关系、数据观察、约束、前问接口、试算或结果，使某个方法在当前位置出现。

## 最小格式

```json
{
  "schema": "mcm-public-judgment-ledger/v1",
  "questions": [
    {
      "id": "1",
      "basis": [
        {
          "id": "fixed-distance",
          "kind": "relation",
          "terms": ["相邻距离固定", "定长圆"],
          "source_ref": "题面条件 (2) 与式 (4)",
          "source_ids": ["problem"]
        }
      ],
      "methods": [
        {
          "name": "首次事件二分",
          "terms": ["二分法", "二分搜索"],
          "basis_ids": ["fixed-distance"]
        }
      ]
    }
  ]
}
```

`kind` 只能是 `relation`、`data`、`constraint`、`interface`、`trial`、`result`、`boundary` 或 `structure`。`terms` 是当前正文中实际可找到的词，不是后来补的概括；`source_ref` 指向题面、图表、公式、日志、代码输出或前问接口。

当本问由题面关系直接列式且没有命名方法时，保留至少一个 `basis`，并写 `"methods": []` 与 `"direct_relation": true`。不要为了填账本凭空添加候选模型、失败试算或算法比较。

## 使用与边界

```bash
python scripts/audit_judgment_ledger.py main.tex --ledger judgment-ledger.json --workbench modeling-workbench.json --format text
```

提供 `--workbench` 时，账本依据还必须用 `source_ids` 指向同一工作台冻结的来源，并与当前分问的同名锚点绑定；依据类型须相同，`terms` 至少保留一个工作台锚点术语，不能只借用锚点 ID 后换成另一句泛化文字。`source_ref` 只负责页码、字段、函数或图表的细定位，不能单独充当证据。审计还会对正文中可明确识别的“采用/使用/引入某具体模型、算法、方法、回归、规划、网络或求解器”逐项检查，未在账本 `methods.terms` 中登记的命名方法会阻断；泛称“建立模型”“采用算法”不会被强行当作独立方法。审计仍不判断依据是否充分，不证明模型正确，也不能发现没有明确动作词的隐性方法。成稿时把依据放回题面、公式、图表或结果附近；不要把 `basis`、`methods` 或 `source_ref` 变成论文标题。
