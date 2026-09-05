# 运行记录

## 配置

- `mode=DIAGNOSE`
- `scene=AUTO -> RESEARCH`
- `intensity=BALANCED`（沿用参数默认值；诊断模式下未执行改写）
- `output=ANNOTATED`（由 `DIAGNOSE` 合同强制）
- `voice_profile=NONE`；`voice=SCENE_DEFAULT`
- `source_roles=AUTO`；本次可诊断文本识别为 `author`
- `structure_lock=false`
- `title_lock=true`
- `scope=document`（仅指定输入文件）
- `report_context=NONE`

## 覆盖范围

- 输入：`blind_diagnose_input.md`
- 覆盖：文件标题及全部两段正文；完成全文连续阅读、全量词项扫描和 RESEARCH 场景上下文复核。
- 词项扫描：运行 `scan_humanize_chinese.py --scene AUTO --format text`；扫描命中仅作为候选，最终按上下文裁决。
- 保护区：未发现引语、数学、代码、OCR 或报告元数据；标题受 `title_lock=true` 保护。
- 未读取：同目录其他 fixture、既有报告和预期答案。
- 未覆盖：无。

## 正文状态

- 是否修改正文：否。
- 输入文件写入：无。
- 诊断输出只包含定位、读感、决策与动作，不包含替换后的完整正文。
- 诊断前输入 SHA-256：`759749460CEBA9F5D21E178A72636FCA39047ED2F8734516320D605E781835CE`。
- 诊断后输入 SHA-256：`759749460CEBA9F5D21E178A72636FCA39047ED2F8734516320D605E781835CE`；与诊断前一致。
- 保护检查：`NOT_RUN`；本次为 `DIAGNOSE`，未生成改写稿，不适用改写验证器。
- `academic_correctness=NOT_EVALUATED`。

## 输出合同回归

- 诊断输出：`blind_diagnose_output.md`。
- 九列表头 `Severity | Location | Source role | Scene | Signal/Pathology | Trigger | Reading effect | Decision | Action` 只出现一次，列名和顺序均与合同一致。
- 输出不含改后全文，不含“改后正文”“已改写”“已调整”等完成态改写声明。
- 输出保留 `UNRESOLVED`，没有把缺失指标改写成无来源结论。

## 未决项

- 第 2 段“模型效果有所提升”缺少可在本片段内定位的指标、基线或观察差异。该处标为 `UNRESOLVED`，未补造任何信息。
