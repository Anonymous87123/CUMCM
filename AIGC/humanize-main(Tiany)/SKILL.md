---
name: humanize-tiany-candidate-lab
description: 从同一冻结源比较多个普通中文候选，机械检查数字、TeX 命令、公式、引用和标签，并报告改动幅度、重复与套语信号。用于需要恢复 Tiany README 所述 candidate pool、keep/discard 和 repair 记录但原始运行时缺失时。只做候选治理和比较，不生成正文，不判断作者身份，不把分数当成检测结论，也不自动采用候选。
---

# Tiany Candidate Lab

这是依据本目录 README 公开设计重新实现的本地候选比较 Skill，不是对缺失原代码的还原。开始前完整读取 [reconstruction-boundary.md](references/reconstruction-boundary.md)。

## 使用边界

- 只比较从同一个冻结源独立产生的候选；不得把候选继续串联改写。
- 学术、CUMCM、TeX 或事实密集文本先交给 `$aigc-writing-router` 和对应场景 Skill 建立内容与保护门。
- 本 Skill 不生成候选。先用适用的主编辑器产生候选文件，再运行本地比较器。
- 保护区漂移的候选直接标为不合格；其余统计只用于定位人工复核处。
- 不输出“AI 概率”“人类概率”或外部检测放行结论。

## 比较候选

```powershell
python scripts/compare_candidates.py source.txt candidate-a.txt candidate-b.txt --format text
```

需要机器可读结果时：

```powershell
python scripts/compare_candidates.py source.tex candidate-a.tex candidate-b.tex --format json --output report.json
```

输出包含每个文件的 SHA-256、保护区核对、改动率、重复片段、套语命中和人工复核状态。排序只在保护区通过的候选之间进行，而且 `recommended_for_human_review` 不等于自动采用。

## Repair 规则

若候选失败，回到冻结源重新生成一个新候选，不得在失败候选上继续加工。修复任务只能引用具体证据，例如“恢复式 (7) 中的 0.35”或“删除第 4 段的重复句”；不得以降低检测分数为目标。

## 与组合路由器配合

组合任务先运行：

```powershell
python ..\aigc-writing-router\scripts\run_aigc_adapter.py --package humanize-tiany-candidate-lab --action prepare-candidate --source source.txt --output-dir run
```

返回候选后使用 `verify-candidate`，再运行本 Skill 的比较脚本。原文始终保留为候选，最终选择必须由人工记录具体收益。

