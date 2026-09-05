# Reconstruction boundary

本目录原始导入只有 `.gitignore`、`LICENSE` 和 `README.md`。README 描述了候选池、局部评分、keep/discard 与 repair 闭环，但其声称的 `humanize.py`、`scripts/`、`SKILL.md` 和运行时并未随下载内容提供。

当前实现只恢复能够从公开说明独立定义、并可机械验证的候选治理部分：

- 冻结源和候选哈希；
- 数字、TeX 命令、公式、引用键与标签核对；
- 候选相对源稿的改动率；
- 重复四元组和常见套语的可解释统计；
- 只在硬保护通过后给出人工复核顺序。

没有恢复、也不声称恢复原 README 提到的 BGE 模型评分、LLM 候选生成或原作者未发布的 repair 实现。比较结果不能证明作者身份、文本质量或外部检测结果。

