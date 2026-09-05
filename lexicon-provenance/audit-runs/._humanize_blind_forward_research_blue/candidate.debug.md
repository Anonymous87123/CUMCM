# 论文结果与结论草案

更新时间：2026-04-27

本文档汇总现有结果的论证边界，标题为“结果边界说明书”。它专门回答六个问题：

1. 现有数据能够支持的最强主张。
2. 可纳入论文主表与主图的结果。
3. 只能作为第二层级支持或边界条件的结果。
4. method-line（`CURV_SORT vs DG2`）能够及不能支持的结论。
5. 审稿人可能提出的质疑与相应回应。
6. 论文 Results/Discussion 的组织方式。

---

## 1. 当前一句话主张

当前数据支持以下分层主张：

在 CEC2013 LSGO 的强信号函数族中，变量分组失败不只是传统意义上的 linkage 切断问题。错误分组会显著恶化子空间投影后的几何结构，表现为子空间 Hessian 条件数、谱扩展或隐藏原生 rank 跨度增大；这种几何恶化会在固定的 `CC + CMA-ES` 后端上转化为显著的最终优化性能退化。

在 `CURV_SORT vs DG2` 的独立预算 method-line 实验里，我们已经看到：即使一个分解器在隐藏结构恢复上更“正确”（`weighted_purity` 更高），如果它没有给后端提供更可优化的子空间几何，它依然可能在最终 `best_so_far_y` 上输给一个 purity 很低但采用 geometry-first 的低成本分解器。

这一主张仍不意味着“所有 CEC 函数、所有优化器、所有指标都服从同一规律”。F2/F3/F6/F10 说明，多峰结构、平台区、预算规模和后端动态会调制最终性能；F8 的 method-line 结果也说明，不同过程指标可能强调收敛的不同阶段。因此，结果必须按“函数族分层 + 指标分层”展开，不能作一刀切解释。

---

## 2. 证据等级总表

### 2.1 强证据：可以作为论文主结果

1. **F1 精确 Hessian 证明分组会直接改变子空间条件数。**
   - 输出：`outputs/tables/f1_exact_hessian_verify/2026-04-26_01-10-32_smoke/paper_table_f1_exact_condition.csv`
   - `sequential`：20 个子组的精确条件数全部约为 `1.969`。
   - `random`：条件数均值约 `6.17e5`，最大约 `8.35e5`。
   - `swap_5`：条件数均值约 `1.11e5`，最大约 `9.86e5`。
   - `swap_10`：条件数均值约 `3.60e4`，最大约 `5.52e5`。
   - 解释：这不是有限差分误差，而是 elliptic core 的精确二次型结论。

2. **F1 paper 级优化实验表明几何恶化会转化为最终精度损失。**
   - 输出：`outputs/tables/repro_permutation_by_fun/2026-04-26_16-22-03_paper/summary.csv`
   - `sequential` 最终均值约 `1.12e-3`。
   - `random` 最终均值约 `2.22e4`。
   - `swap_5` 最终均值约 `3.85e3`。
   - `swap_10` 最终均值约 `1.40e2`。
   - `swap_20` 最终均值约 `1.36e-3`。
   - 解释：`random/swap_5/swap_10` 在 `1,000,000` FEs 下仍明显受损；`swap_20` 追上 `sequential`，说明破坏并非绝对不可修复，而是受预算与后端适应能力调制。

3. **F4/F7/F8/F11 的 oracle paper 级实验给出多个数量级的性能差异。**
   - 输出根目录：`outputs/tables/repro_permutation_oracle_by_fun/`
   - F4：`sequential=4.51e12`，`random=6.09e12`，`oracle=1.34e5`。
   - F7：`sequential=9.01e10`，`random=9.98e10`，`oracle=8.65e4`。
   - F8：`sequential=3.60e17`，`random=3.45e17`，`oracle=6.62e8`。
   - F11：`sequential=3.25e12`，`random=8.40e12`，`oracle=1.58e8`。
   - 解释：一旦分组顺应隐藏原生结构，优化性能可以发生 4 到 7 个数量级的变化。

4. **F4/F7/F8/F11 的 paper 级统计检验表明差异稳定存在。**
   - 输出：`outputs/tables/statistics_oracle_paper_strong/2026-04-26_19-15-18_statistics/`
   - sequential/random 相对 oracle 的 `best_so_far_y` Cliff's delta 全部为 `1.0`。
   - Mann-Whitney p 全部为 `0.000183`。
   - paired Wilcoxon p 全部为 `0.001953`。
   - 强信号集合中，`spectral_spread_max` 与 `best_so_far_y` 的 Spearman 相关为 `rho=0.510`，`p=2.72e-9`。
   - `hidden_rank_span_ratio_mean` 与 `best_so_far_y` 的相关更强，`rho=0.688`，`p=3.67e-18`。

5. **Method-line 的 independent paper 已经包含结果与统计。**
   - 主结果：`outputs/tables/decomposer_compare_independent_paper_by_fun_restart/2026-04-27_12-17-13_paper/summary.csv`
   - 统计：`outputs/tables/statistics_method_paper_final/2026-04-27_16-31-43_statistics/decomposer_tests.csv`
   - F4：`CURV_SORT=2.50e10`，`DG2=5.73e11`，DG2 差约 `1.36` 个 `log10` 数量级。
   - F7：`CURV_SORT=6.65e9`，`DG2=2.97e13`，DG2 差约 `3.65` 个 `log10` 数量级。
   - F8：`CURV_SORT=6.00e11`，`DG2=4.68e14`，DG2 差约 `2.89` 个 `log10` 数量级。
   - `best_so_far_y` 上，DG2 相对 CURV_SORT 的 Cliff's delta 在 F4/F7/F8 全部为 `1.0`。
   - Mann-Whitney p 在 F4/F7/F8 全部为 `0.000183`。
   - paired Wilcoxon p 在 F4/F7/F8 全部为 `0.001953`。
   - 解释：在固定 `CC + CMA-ES` 后端、等优化预算、强信号函数上，geometry-first 已经表现出稳定而显著的最终精度优势。

### 2.2 中等证据：可以作为第二层级支持

1. **F5/F9 的 paper 级结果继续支持 hidden structure，但幅度弱于 Elliptic/Schwefel。**
   - F5：`sequential=2.70e7`，`random=2.78e7`，`oracle=2.53e6`。
   - F9：`sequential=2.22e9`，`random=2.26e9`，`oracle=1.58e8`。
   - 解释：Rastrigin 上 oracle 仍约优于 sequential/random 1 个 `log10` 数量级，但多峰性削弱了“条件数到最终性能”的直达映射。

2. **F13/F14 的 paper 级 overlap 结果继续支持 hidden structure。**
   - F13：`sequential=9.48e11`，`random=5.62e11`，`oracle=6.64e9`。
   - F14：`sequential=1.17e12`，`random=2.64e12`，`oracle=9.77e10`。
   - 解释：即使有重叠变量和冲突子组件，顺应官方隐藏结构仍然有明显优势。不过这些函数的收敛过程更复杂，不能只看单一指标。

3. **证据链派生表和图已经联合呈现几何、性能与统计归因。**
   - analysis：`outputs/tables/paper_analysis/2026-04-26_19-15-41_paper_analysis/`
   - 图：`outputs/plot/paper_figures_v2/`
