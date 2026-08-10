# CUMCM 双模式写作模板

本目录直接改造现有 `thesis template/`，没有新建平行的 `thesis-template/`。上游
`cumcmthesis.cls`、字体和 `example.tex` 保持原样。

## 入口

- `main.tex`：指导模式。每级标题下显示目标、必备清单、语言风格、篇幅排版、图表位置、高分点和错误警示。
- `submission.tex`：提交模式。定义 `MCMSubmission` 后载入同一份 `main.tex`，隐藏全部指导框、示例表和占位内容。
- `example.tex`：上游写法参考，不参与当前双模式正文。
- `ITERATION.md`：记录证据版本、增量来源和后续批注协议。

## 证据范围

截至 2026-08-01，2020--2025 年 A/B/C 题 59 篇编号论文已完成 59/59 篇、
2892/2892 页人工逐页阅读，A/B/C 分别为 20/19/20 篇，十四类章节检查为
826/826。篇幅提示使用 59 篇的页级实测中位数和四分位范围；文风入口覆盖
59/59 篇，其中 44 篇保留带原页位置的细粒度记录，另 15 篇补入结构化判断动作卡；
不把人工选段冒充全文词频。

指导模式优先教“观察--判断--动作--结果--边界”的真实论文推进：模型名前先写
为何需要它，公式后解释作用，结果后解释机制，遇到跳变或反常时回到事件对象、
局部结构、共同情景或全过程核查。必要错误警示只用于检查自己的稿件，不用于给
获奖论文排错。

## 编译

在本目录执行：

```text
latexmk -xelatex -interaction=nonstopmode -halt-on-error -outdir=<临时目录> main.tex
latexmk -xelatex -interaction=nonstopmode -halt-on-error -outdir=<临时目录> submission.tex
```

不要直接编辑 `cumcmthesis.cls` 或字体文件。新增范文结论先按“来源编号、年份、
核验日期、原文页码、题型、结论、页面复核状态”写入 `main.tex` 末尾批注区和
`ITERATION.md`，再修改可见指导。
