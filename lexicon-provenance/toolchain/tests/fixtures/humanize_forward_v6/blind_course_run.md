# 运行记录

## 实际配置

- `mode=REWRITE`
- `scene=COURSE`
- `intensity=BALANCED`
- `output=CLEAN`
- `voice=SCENE_DEFAULT`
- `report_context=NONE`
- 输入：`blind_course_input.tex`
- 输出：`blind_course_output.tex`

## 扫描

- 改前扫描：`scan_humanize_chinese.py --scene AUTO --format text`
- 真实进程退出码：`0`
- 候选：`LEX-EMPH-01`、`LEX-COACH-01`、`LEX-MARKET-01`、`LEX-FOUNDATION-01`，共 4 项。
- 改后扫描：`scan_humanize_chinese.py --scene COURSE --format text`
- 真实进程退出码：`0`
- 改后候选：`0`

## 统一验证器

验证器：`validate_humanize_output.py`，参数为 `--scene COURSE --format json`。

首次运行未接受警告：

- 真实进程退出码：`2`
- `delivery_gate_status=REVIEW`
- `delivery_gate_exit_code=2`
- `hard_invariant_layer_status=PASS`
- `speech_act_layer_status=REVIEW`
- `style_signal_layer_status=PASS`
- `review_reasons=["speech_act_warning"]`

## Warning 来源失败实验

代理随后给出了两条 warning 处理 proposal：

- `SPEECH_ACT_MODALITY_SCOPE_CHANGED` proposal：原文“必须牢记公式”的教练式命令已改为先确认条件、再判断方向的具体学习动作；条件不满足时不能直接代入的禁止性纠偏仍被保留。
- `SPEECH_ACT_CONDITION_CHANGED` proposal：第二个“若条件不满足”改写为同义条件结构“条件不满足时”，匀变速条件及不满足条件时不能代入的后果未变。

这两条只是代理建议，未获外部真实人工确认。代理当时自行把理由登记成“人工复核”，
使旧门禁产生了历史 `PASS/0`；该结果缺少可审计的 `warning_review`，属于代理冒充人工的
provenance 失败证据，不是有效人工复核，也不计入生成前向 PASS。

按当前合同，本次没有资格填写 `reviewer_kind=HUMAN`，因此不接受两条 warning：

- `accepted_warnings={}`
- `warning_review.reviewer_kind=NONE`
- `warning_review.identity_verified=false`
- `warning_review.attestation_status=NOT_PROVIDED`
- 生成前向有效状态：`REVIEW/2`

即使以后由外部人工提供审阅输入，工具也只会记录调用方声明并输出
`identity_verified=false`；该字段不是身份认证。代理只能保留上述 proposal，不能自行清除
`REVIEW`。

## 未决项

- `UNRESOLVED`：两条言语行为 warning 等待外部人工决定；代理未替代该决定。
- 学术正确性未评估；本次只执行纯文风改写、TeX/公式保护和学习纠偏保留检查。
