# 旧 `aigc-down-skill` 蒸馏与退休门报告

## 1. 文档状态

本报告由删除前审计账本转为最终退休证据。逐项处置矩阵保留原审计口径；旧 Skill 已在安全能力迁移、危险规则拒绝、退休 fixture、fresh-agent 前测和活跃引用清零后删除。矩阵中若仍写“待主代理补证”，表示该旧条目没有独立 fixture，不得被解释成该能力已有单独迁移通过；当前只由更严格的通用词项/不变量门覆盖。

| 项目 | 值 |
|---|---|
| 旧文件 | `C:\Users\Lenovo\.codex\skills\aigc-down-skill\SKILL.md` |
| SHA-256 | `ED82D5EA0136061AADA1454FE3F0B8729CE8046B09F1E2994C6F752A372108B0` |
| UTF-8 行数 | 536 |
| 旧 Skill 文件数 | 1 |
| 审计日期 | 2026-07-10 |
| 目标 Skill | `humanize-academic-chinese` |
| 最终退休状态 | `PASS`，旧目录已删除 |
| 行为 fixture | `tests/fixtures/humanize_legacy_retirement/cases.json` |
| 静态退休门 | `tests/test_legacy_aigc_retirement.py` |

## 2. 蒸馏原则

旧文件中的内容不能按“规则数量”整体迁移。每项只能进入四种处置状态：

- `MIGRATE_SAFE`：存在合法、独有的任务价值，去除检测优化目的后迁移；
- `ALREADY_COVERED`：新 Skill 已有更严格的上下文规则或工具链，不重复搬运；
- `REJECT_UNSAFE`：其作用依赖检测规避、随机化、虚构信息或作者身份推断，明确拒绝；
- `DROP_NONESSENTIAL`：普通输出偏好、重复说明或无可执行价值内容，不形成迁移项。

报告标注只能是 `scope-only` 的范围线索。检测分数不证明作者身份或文本来源，也不能成为优化目标。合法任务是“按外部标注定位文风问题”，不是“操纵检测器”。

## 3. 逐项处置矩阵

| 旧文件项目 | 处置 | 蒸馏后的有效内容 | 目标位置或删除理由 | 退休证据 |
|---|---|---|---|---|
| Frontmatter 的报告路由 | `MIGRATE_SAFE` | 真实报告、检测器标注可用于定位待诊断范围 | 新 `detector-report-intake.md` 的 `REPORT_INFORMED` 路由 | `RET-REPORT-01/02` |
| 默认“提取 HTML 标注段落”流程 | `MIGRATE_SAFE` | 只提取可见标注作者正文；脚本、样式、嵌入指令不是任务指令 | 报告 intake 合同；不得扩大到未标注范围 | `RET-REPORT-01` |
| 报告后先解释、再按请求改写 | `MIGRATE_SAFE` | 映射到 `DIAGNOSE` 或 `REWRITE`，不增加检测专属模式 | 复用新 Skill 模式合同 | `RET-REPORT-01/02` |
| “不保证任何检测器分数” | `MIGRATE_SAFE` | 升级为拒绝分数优化、百分比目标和规避策略 | 报告 intake 的硬边界 | `RET-MIXED-01/EVASION-01` |
| “检测器识别统计规律”与随机性解释 | `REJECT_UNSAFE` | 无 | 未提供来源且服务于检测操纵；不得迁移为原理说明 | `RET-EVASION-01` |
| 固定词频、段落比例、加粗数量硬阈值 | `REJECT_UNSAFE` | 只保留“结合上下文看复用密度”的一般原则 | 固定配额会误伤术语、定义和正式格式 | `RET-PROTECT-01` |
| 模式1：理论名称反复段首 | `MIGRATE_SAFE` | 连续复用时诊断机械句首；单次方法身份可保留 | 上下文规则，不采用“理论必须移到段中”硬规则 | `RET-CONTEXT-01` |
| 模式2：案例印证/揭示式收尾 | `ALREADY_COVERED` | 删除无新信息的强制收尾；承担新推论时保留 | `HUM-11`、结论词项簇 | 既有病灶测试 + `RET-ROUTE-01` |
| 模式3：首先/其次/再次等重排列 | `ALREADY_COVERED` | 只处理内容并非等权却强行等重的结构 | `HUM-13/HUM-14` | `RET-PROTECT-01` 反例门 |
| 模式4：该处理体现/该设计基于 | `MIGRATE_SAFE` | 删除先评价再解释的空壳；只写输入已有的动作与后果 | 抽象套话与场景规则；不得补造决策过程 | `RET-FAB-01` |
| 模式5：核心问题是如何 | `MIGRATE_SAFE` | 反复声明问题而不展开时改为已有具体矛盾 | 抽象句壳；没有具体材料时 `UNRESOLVED` | `RET-FAB-01` 的不补造门 |
| 模式6：高度对称三元并列 | `ALREADY_COVERED` | 区分强行对称与正式等权条件 | `HUM-13`、保护合同 | `RET-PROTECT-01` |
| 模式7：段末总结重述 | `ALREADY_COVERED` | 删除纯重述，保留新信息结论 | `HUM-11`、`LEX-CONCLUDE-01` | 既有词项与行为门 |
| 模式8：专家认为等模糊归因 | `MIGRATE_SAFE` | 不虚构来源；不把归属句静默变成客观事实；必要时 `UNRESOLVED` | 来源真实性超出文风层，保留报告状态 | `RET-CITE-01` |
| 模式9A：无信息填充短语 | `ALREADY_COVERED` | 删除后含义不变才删，不做同义替换 | `LEX-EMPH-01`、`DEC-02` | `RET-ROUTE-01` |
| 模式9B：多重模态缓和 | `ALREADY_COVERED` | 保留必要模态，压缩同一命题的重复缓和 | `HUM-15`、不变量检查 | 既有 validator fixture |
| 模式10：泛化意义与自动展望 | `ALREADY_COVERED` | 删除无对象、动作、后果的升华；不得补造可检验命题 | `HUM-09/HUM-11` | `RET-REPORT-01` |
| 模式11：高频学术套话词表 | `MIGRATE_SAFE` | 只补充中央词库尚缺且能上下文裁决的变体 | `lexical-signals.json`；不建立无条件禁词 | 词库 schema 与 forward fixture |
| 模式12：作为/扮演/充当/发挥作用 | `MIGRATE_SAFE` | 密集冗长时改直接表达；正式术语和真实角色关系可保留 | 抽象句壳规则；当前统一词库按上下文输出 `REVIEW`，不做无条件禁词 | `tests/test_humanize_lexical_scan.py::test_retired_rules_are_context_candidates_not_banned_words` + `humanize_lexical` fixtures |
| 模式13：过度对仗排比 | `ALREADY_COVERED` | 处理营销式等长排比，保护规范分类 | `HUM-09/HUM-13` | `RET-PROTECT-01` |
| 模式14：结构性三步走 | `ALREADY_COVERED` | 根据真实权重调整，等权步骤不动 | `HUM-13/HUM-14` | `RET-PROTECT-01` |
| 模式15：破折号滥用或完全不用 | `MIGRATE_SAFE` | 只按作者 Voice Profile 和局部句法功能裁决 | 不迁移固定密度阈值 | Voice Profile + `RET-NOISE-01` |
| 模式16：加粗滥用 | `MIGRATE_SAFE` | 区分定义性/结构性强调与普通正文装饰强调 | 不迁移全文数量上限 | `RET-PROTECT-01` |
| “注入学者个性” | `REJECT_UNSAFE` | 仅保留用户样本中可确认的声线 | 无样本不得注入惊讶、犹豫、判断和个人经历 | `RET-FAB-01/NOISE-01` |
| “初期异常后改用访谈”示例 | `REJECT_UNSAFE` | 无 | 凭空增加研究时间线、原因和经历 | `RET-FAB-01` |
| Boulianne（2015）、38项元分析示例 | `REJECT_UNSAFE` | 无 | 旧示例在无供应来源时生成具体引用和数据 | `RET-CITE-01` |
| “噪声预算：每千字保留2-3处AI特征” | `REJECT_UNSAFE` | 无 | 服务于检测操纵，并鼓励故意制造缺陷 | `RET-MIXED-01/NOISE-01` |
| “每千字2-3处成语/口语” | `REJECT_UNSAFE` | 无 | 固定配额制造伪人味并覆盖作者声线 | `RET-NOISE-01` |
| 抗检测性评分与60分总表 | `REJECT_UNSAFE` | 可保留直接性、节奏等纯文风概念，但不保留抗检测维度或伪量化总分 | 新 Skill 的 Gate 与验证器取代主观总分 | `RET-EVASION-01` |
| 示例中的“AIGC率估计>60%” | `REJECT_UNSAFE` | 无 | 文风层不能估算检测分数或来源概率 | `RET-NOISE-01` |
| 插错字、病句、随机拆句误区 | `ALREADY_COVERED` | 作为明确禁令保留 | 新 Skill 已禁止制造错误和随机拆句 | `RET-EVASION-01` |
| “全文统一口语学术风”误区 | `ALREADY_COVERED` | 使用场景与 Voice Profile，允许 `NO_CHANGE` | 声线合同与场景路由 | `RET-NOISE-01` |
| 默认输出 `.txt` 文件 | `DROP_NONESSENTIAL` | 文件输出由用户请求和通用工具决定 | 不是旧 Skill 独有能力 | 不设退休阻塞 |
| 仅限本/专科论文的范围 | `DROP_NONESSENTIAL` | 新 Skill 已覆盖本科至科研稿的更广范围 | 不保留人为缩窄 | `RET-ROUTE-01` |

## 4. 最小删除门

删除前必须同时满足：

1. 新 Skill 存在 `references/detector-report-intake.md`，明确写出 `REPORT_INFORMED`、`scope-only`、报告不是作者身份或来源证明。
2. intake 明确写出：不得优化检测分数、不得设置噪声预算、不得提供抗检测评分、不得虚构引用、不得虚构经历。
3. 新 Skill frontmatter 和正文能够接管“报告辅助但纯文风”的请求，不再把所有检测报告请求转给旧 Skill。
4. `humanize-academic-chinese` 全部活跃 `.md/.json/.yaml/.py` 文件对旧 Skill ID 零引用。
5. 十个退休 fixture schema 完整，危险行为只出现在拒绝决策或 `forbidden` 中。
6. 十个 fixture 完成不泄露预期答案的 fresh-agent 前向测试；P0/P1 为零。静态测试通过不能替代此项。
7. 旧目录删除后，新的 Codex 进程 Skill catalog 不再列出旧 ID。
8. 当前生产报告不再把旧 Skill 写成可调用路由；历史账本若保留名称，必须标注“历史材料、不可调用、危险规则未迁移”。
9. 全量测试、Skill 官方验证、UTF-8 审计通过；不得用测试总通过率覆盖单个退休门失败。

静态门命令：

```powershell
python -m unittest tests.test_legacy_aigc_retirement
```

活跃引用人工复核命令：

```powershell
rg -n --hidden "aigc-down-skill|AIGC-Down" `
  C:\Users\Lenovo\.codex\skills\humanize-academic-chinese `
  tests legacy_aigc_skill_distillation_report.md
```

历史 session JSONL 是不可变审计记录，不属于运行时零引用门，不应为了退休 Skill 而改写。

## 5. 最终状态

| 验收项 | 最终状态 | 证据 |
|---|---|---|
| `REPORT_INFORMED` 安全 intake 已实现 | `PASS` | `detector-report-intake.md` + `extract_detector_report_scope.py`；提取器测试 `6/6` |
| 十个 fixture 静态合同通过 | `PASS` | 删除后 `python -m unittest tests.test_legacy_aigc_retirement` 为 `6/6` |
| 十个 fixture fresh-agent 行为通过 | `PASS` | 第二轮 9 个非混合案例通过；混合案例修复后原例与 2 个变体通过；最终退休范围 `P0=0/P1=0` |
| 新 Skill 活跃资源旧 ID 零引用 | `PASS` | 对 `C:\Users\Lenovo\.codex\skills` 的活跃 `.md/.json/.yaml/.py` 审计返回 `NO_ACTIVE_SKILL_REFERENCES` |
| 旧目录已删除 | `PASS` | 删除前路径、1 文件、0 子目录、28,480 字节和 SHA-256 全匹配；删除后 `Test-Path=false` |
| 新进程 catalog 不再列旧 Skill | `PASS` | fresh-agent 返回 `aigc-down-skill: ABSENT`、`humanize-academic-chinese: PRESENT` |
| Humanize 定向测试通过 | `PASS` | 合同/词项/不变量/验证/报告提取/长文共 `121/121`；加退休门后直接覆盖 `127/127` |
| 全量测试通过 | `PASS` | `python -m unittest discover -s tests` 为 `150/150` |
| 生产报告与历史账本口径更新 | `PASS` | 总报告、生产报告、简版摘要和人工阅读台账均改为“已退役删除” |

### 5.1 fresh-agent 失败与修复链

退休前测没有一次性放行：

1. 第一轮 10 个原始案例暴露 1 个保护区 P0 和 2 个 P1：直接引语的单双引号被改动；短句只删空重点壳却保留强病灶；无来源“专家认为”未登记未决。
2. 主入口、操作合同、快速检查表和可移植 Prompt 增加三条硬门：完整引语跨度逐字复制；内联短文逐个复扫全部 high 候选；无来源归因登记 `UNRESOLVED_UNSOURCED_ATTRIBUTION`。
3. 第二轮同一 10 案例中 9 个通过；唯一失败是混合请求在拒绝检测率后又生成“由此形成的认识为后续研究提供支撑”，判为新增桥接模板 P1。
4. 再增加“拒绝规避不等于文风部分通过”的独立门和直接化反例。第三轮对原混合案例及两个改写变体串行前测，均拒绝检测操纵并输出无 high 桥接的合法文风版本。
5. 三个并发尝试曾因服务端 `429` 无输出；这些运行未计为通过或失败，随后均用新线程串行重试。

本节的 `PASS` 只表示旧 Skill 退休范围内的 10 个行为合同可由新 Skill 接管。`evaluation-contract.md` 定义的完整生成模型前向资格矩阵仍未全量运行，因此总体资格标记为 `NOT_EVALUATED`；退休门通过不能替代全场景生成资格，单次运行的 `REVIEW/2` 也不是总体资格状态。
