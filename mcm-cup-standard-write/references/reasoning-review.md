# 思考桥队内复述门

自然的思考过程不是靠脚本判定，而是队员确实能解释正文中的推演。长稿写作前应先通过 [分问推演预审](reasoning-preflight.md)；正式候选冻结后的本门不再承担首次选路，而是检查正文是否偏离已确认的路线。每个分问由至少两名队员独立填写一次简短复述：

- 本题哪项事实是该段的起点；
- 它为什么会变成当前变量、约束、方程性质、数据口径或求解任务；
- 改变哪个关键条件会让这条推演失效或需要换路。

复述针对已写入正文的思考桥，不记录逐字隐藏思维链，也不能用“综合考虑”“反复思考”等空话代替对象和条件。记录锁定完整 TeX 文件树的 SHA-256，并由审计器确认每问至少两名不同队员、桥接术语位于本问正文：

```powershell
python scripts/audit_reasoning_review.py main.tex --review reasoning-review.json --format text
```

最小格式如下：

```json
{
  "schema": "mcm-reasoning-review/v1",
  "manuscript_sha256": "<flattened-tex-tree sha256>",
  "reviews": [
    {
      "question_id": "1",
      "reviewer": "组员1",
      "reviewer_kind": "human",
      "bridge_terms": ["大量零值", "同期平均", "Bayesian 模型"],
      "anchor_explanation": "零值改变了每日记录作为连续响应的含义。",
      "transition_explanation": "同期聚合把数据口径调整为时段层面的输入。",
      "condition_change": "若零值来自缺报，应先补查记录而不是直接聚合。",
      "decision": "pass"
    }
  ]
}
```

每条记录的 `reviewer_kind` 必须为 `human`；模型生成的复述意见只能作为待队员核对的草案，不能增加每问的两人覆盖。若本门出现 `revise`，先回看同问预审、工作台和冻结来源：只有正文偏离已确认的锚点、数学落点或路线时才局部修复并重新审计；不在成稿末尾重新发明一条选路故事。该门只能证明记录完整、稿件未漂移且复述术语位于相应分问；不能证明评审身份、数学正确性、作者身份或文风自然。
