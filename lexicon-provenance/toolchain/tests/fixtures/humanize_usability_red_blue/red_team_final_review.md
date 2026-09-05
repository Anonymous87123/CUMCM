# 独立红队最终复审

评审结论：默认生成直改不具备资格；完整生成资格为 `NOT_EVALUATED`。本轮证据中没有确认 P0 的静默放行，但 P1 仍成立。

## 量表结果

| 维度 | 分数（0-2） |
|---|---:|
| 保护区、公式和数字 | 1 |
| 信息补造 | 1 |
| 诊断合同 | 1 |
| 普通短改实用性 | 2 |
| 科研改写 | 0 |
| 课程改写 | 2 |
| 门禁诚实性 | 2 |
| 长 TeX 最小流程 | 1 |
| PowerShell BOM 兼容性 | 1 |
| 模板残留 | 0 |
| 完成态真实性 | 1 |
| 测试证据质量 | 1 |
| 文档约束可执行性 | 1 |
| 可泛化性 | 0 |
| **总分** | **15/28** |

## P0

未确认本轮 P0。`research_fresh_body.md` 中新增“已有研究”和“温度循环”均被 `validation/research_fresh.json` 降为 `REVIEW`，没有静默通过。

## P1

1. 默认科研直改不可靠。`research_fresh_body.md` 新增了输入中没有的“已有研究”和“温度循环”；`SPEECH_ACT_ATTRIBUTION_SOURCE_CHANGED` 已被记录，退出码为 `2`。
2. 科研样本未收敛。`research_final_body.md` 仍有“值得注意的是”“深刻揭示”“为后续研究奠定坚实基础”；验证 JSON 保留三个未解释 high finding，状态为 `REVIEW/2`。
3. 完整生成资格缺失。当前仅有 `COURSE` 与 `RESEARCH` 的七个短文本和一个 TeX unit；没有完整的模式、角色、16 类病灶、`REPORT_INFORMED`、盲评和幂等矩阵。按 `evaluation-contract.md`，不能声明生成资格通过。

## P2

- TeX 仅为一个 unit probe；`compile_check=NOT_RUN`、`idempotency=NOT_RUN`，不证明真实项目可编译或长文可幂等发布。
- BOM 改写包已验证，但尚无 BOM 输入正文的端到端 fixture。
- `diagnose_fresh_output.md` 符合表头和只诊断约束，但清单已标注它是人工最小复现，不构成独立蓝队通过证据。

## 资格判断

| 面 | 判断 |
|---|---|
| 确定性工具链 | `REVIEW`：有正向证据，但尚未覆盖合同要求的完整工具 fixture 门。 |
| 默认生成直改 | 不合格：科研核心维度为 0，不能作为一次性交付能力发布。 |
| 完整生成资格 | `NOT_EVALUATED`：完整矩阵未实际运行。 |
