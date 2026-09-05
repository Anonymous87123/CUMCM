# AIGC 能力组合架构

## 目录

1. 五层结构
2. 正式场景组合
3. 新增 Skill 的完整职责
4. 外部项目的完整职责
5. 选用原则
6. 角色契约与组合评测

## 1. 五层结构

```text
组合入口：aigc-writing-router
    |
场景/内容：deai-* / mcm-cup-standard-write
    |
主编辑器：humanize-academic-chinese / academic-humanizer
          / humanizer-medical-academic / humanizer / humanizer-zh
    |
同源候选与只读复核：baibai-aigc / patina / ai-check / 显式通用编辑器
    |
文档治理：FYADR / AI_paper / 其他人工工作台
    |
统一适配：source freeze / protected proxy / candidate verify / native preflight
```

入口不写正文，文风 Skill 不补证据，复核器不选稿，工作台不覆盖权威源。

## 2. 正式场景组合

| 场景 | 内容责任 | 主编辑器 | 可选复核 | 最终门 |
| --- | --- | --- | --- | --- |
| CUMCM | `mcm-cup-standard-write` + `deai-modeling-writing` | `humanize-academic-chinese` | `patina` prose audit、`ai-check` 报告 | 模型、结果、密度、复现、数学、XeLaTeX、页面 |
| 中文建模/研究/课程 | 对应 `deai-*` | `humanize-academic-chinese` | `patina` 或 `ai-check` | 场景门、引用/数学、文档完整性 |
| 英文学术 | `deai-research-writing` | `academic-humanizer` | `patina`、`ai-check`、Brandonwise 英文报告 | 论断证据、引用、版本、文档 |
| 英文医学 | `deai-research-writing` | `humanizer-medical-academic` | 同上 | 论断证据、构念一致、引用、文档 |
| 一般中文 | 已有源稿 | `humanizer-zh` | `humanize-chinese-copy-lab` 或 `patina` 作为显式替代流程 | 事实、语气、格式 |
| 一般英文 | 已有源稿 | `humanizer` | Brandonwise、voice-profile、English editor、Patina 作为显式替代流程 | 事实、语气、格式 |

复核器运行自己的完整 audit/analyze 流程，但只产生报告。显式替代编辑器是从源稿产生一个候选，不接着修改主编辑器输出。

## 3. 新增 Skill 的完整职责

| 调用名 | 完整职责 | 允许场景 | 禁区 |
| --- | --- | --- | --- |
| `academic-humanizer` | 英文学术 audit -> rewrite -> invariant check -> report | 英文论文、英文 TeX | 中文、CUMCM 文风迁移 |
| `humanizer-medical-academic` | 作者画像 + 两遍英文医学编辑 | 医学英文论文 | 中文、非医学模板照搬 |
| `patina` | 多语言 pattern/anchor/MPS/fidelity audit 或单一通用候选 | 普通中英文；学术只读复核 | 原始 TeX 权威稿、自动裁决 |
| `humanizer-brandonwise` | 英文 CLI pattern/statistical analysis；显式一般英文候选 | 一般英文、英文只读报告 | 中文、学术正确性、TeX |
| `humanizer-voice-profile` | 使用一个明确 voice profile 完成一般英文候选 | 一般英文 | 论文内容与引用 |
| `humanize-chinese-copy-lab` | 中文沟通文案候选池、局部评分、repair 和可见报告 | 邮件、微信、客服、通知 | 学术、数学、TeX |
| `ai-check` | 带原文证据的文风信号报告 | 中英文只读诊断 | 作者身份判断、自动选稿 |
| `humanize-english-editor` | 一般英文的完整 source-bound rewrite protocol | 一般英文 | 学术、中文、TeX |

下载包中的名称冲突已消除。不能再用模糊的 `$humanizer` 指代多个 GitHub 版本。

## 4. 外部项目的完整职责

| 项目 | 完整角色 | 使用条件 |
| --- | --- | --- |
| FYADR | DOCX/TXT 快照、正文映射、候选承载、逐块复核、恢复与导出 | 长文或格式关系重要 |
| AI_paper | 写作项目、人工语法/格式/批注、历史与导出 | 需要桌面人工工作区 |
| AI-Cleaner | 中文诊断、Diff、历史实验 | 只读或候选实验 |
| AI-content-detector | 英文 PDF 句级分析、标注 PDF、文本候选 | 英文 PDF 人工复核 |
| GankAIGC | 多用户、BYOK、项目历史、外部反馈 | 明确需要部署能力 |
| BypassAIGC | 旧双阶段流程兼容和回归 | 比较旧版本退化 |
| ai-humanizer | Raycast + Rephrasy 外部 API 演示 | 黑盒交互研究 |
| humanize-text | 翻译链、多引擎和步骤轨迹 | 研究基线，不处理权威稿 |
| humanize-ai-main | transformation/cache/change-trace 可执行参考工作台 | 关闭随机 Markov；返回逐项候选变更 |
| humanize-main(Tiany) | 重建后的同源候选、保护区、比较与 repair 证据 | 不声称恢复缺失的生成器或 BGE 评分器 |

## 5. 选用原则

1. 先按语言、文体、格式和证据风险选主责任人。
2. 同一份源稿只接受一个候选作为新基线。
3. 多候选必须从同一冻结源独立生成。
4. 只读复核器不修改源稿，也不凭分数选稿。
5. TeX 的公式、命令、数字、标签、引用和结构优先于任何文风收益。
6. 原生生成接口不适用或暂不可用时，不把整个项目丢弃；通过统一适配器保留其 `audit`、`candidate` 任务准备或 `workbench` 价值。
7. “全部可执行”不等于“全部串联”。同一正文只由适合当前场景的负责人和一个被人工接受的候选进入下一基线。

## 6. 角色契约与组合评测

`stack-registry.json` 记录包、入口、运行时和安全边界；`role-contracts.json` 逐包记录适用场景、完整交付物、必交证据、失败回退和禁止性结论；`folder-utilization.json` 再把包内嵌套的 `SKILL.md`、`skill.json` 和实际入口类逐项树哈希绑定。新增或改造项目必须同时进入三张表，不能只做到“目录可发现”或“适配器能出一个文件”。

路由器会把对应 `role_contract` 附在每一阶段上。外部登记包按 `role-contracts.json`
收集证据，五个场景内容 Skill 按 `content-role-contracts.json` 收集台账、推演和门结果；
两者都通过 `aigc-role-receipt/v1` 交接，证据文件逐项锁 SHA-256。任一阶段缺证据、硬门
或人工回退记录，组合只到机械待审状态，不能写成“多个 Skill 已协同完成”。

候选完成后用 `run_stack_evaluation.py` 核对冻结源、场景责任链、候选回验、盲评和人工裁决。详见 [stack-evaluation.md](stack-evaluation.md)。自然度只能由来源隐藏的人工成对评审支持；检测器、困惑度、MPS 和启发式分数仍只负责定位问题。

当需要判断一次升级是否能迁移到未见文本时，建立开发集与保留集分离的三次候选基准。`run_style_benchmark.py` 冻结案例、隐藏候选来源、封存评分后的保留集，并把逐段落、逐维度的失败回流到下一版开发集。完整流程见 [style-benchmark.md](style-benchmark.md)。
