# 审计摘要

## 权威状态

```text
DELIVERY REVIEW exit=2
mechanical_validation_status=PASS
hard_invariant_layer_status=PASS
speech_act_layer_status=PASS
style_signal_layer_status=PASS
paired_quality_review_status=PENDING_EXTERNAL_REVIEW
humanize_quality_claim_allowed=false
academic_correctness=NOT_EVALUATED
semantic_judgment=NOT_EVALUATED
```

闭集 verifier 返回 `INTEGRITY PASS exit=0 scope=SELF_CONSISTENCY_ONLY`，并重放得到 `CURRENT_POLICY_REPLAY PASS` 与 `COVERAGE PASS`。这只证明当前工件闭集与当前 policy 可重放、自洽，不把候选升级为交付 PASS，也不构成文风质量批准。

## 实际配置

```text
mode=REWRITE
scene=COURSE (EXPLICIT)
intensity=BALANCED
requested_output=PATCH
effective_output=PATCH
voice_profile=NONE
voice_disclosure=SCENE_DEFAULT
report_context=NONE
source_kind=DOCUMENT
corpus_action_support=NONE
```

处理范围仅为 `physics1.tex` 原第 398-407 行。没有写入或覆盖源文件；工具实际处理的是逐行提取后核对一致的 `source.lines-398-407.tex` 冻结片段。

## 候选与动作

权威候选：`review-final/candidate.review.tex`

权威可复核 PATCH：`review-final/review.md`、`review-final/patch.diff`

共 6 个互不重叠 hunk：

- 4 个 `REWRITE`：压缩同句内重复的“会变小”，并把“令……对……取极值”改为“求……关于……的极值”。
- 2 个 `DELETE_STYLE_SHELL`：删除只充当公式字幕的“因此”“于是”，同时删除各自物理行换行，避免在 TeX 中制造空段。
- 0 个 `UNRESOLVED` hunk。

首轮 `review/` 在模型成对复核中发现删除字幕后留下空行，会改变 TeX 段落结构，已标记为 superseded；它不是权威候选。最终 `review-final/` 重新绑定了包含换行符的精确 source span。

## 保护与扫描

- 冻结片段与原范围逐行相同：10/10 行。
- 原片段内联公式数：10；最终候选内联公式数：10。
- 公式及其中 TeX 源码序列逐字一致：`FormulaSequenceExact=True`。
- 最终候选空行数：0。
- 统一验证器硬不变量：`PASS`。
- 原片段扫描：0 个 high；4 个 medium `LEX-COURSE-FORMULA-CAPTION-01` 上下文候选。
- 改后扫描：无候选输出。扫描结果只作上下文线索，不作作者身份、概率或质量判断。
- coverage：`PASS`，范围仅为 `ENUMERATED_HIGH_AND_BOUND_DECLARATIONS_ONLY`；不证明语义病灶发现完整。

## 哈希

```text
source_sha256=b28dc286b43b7b581f95482d31d53be57a1d0cf743a0e890f58b1f3121fe934b
candidate_sha256=94387b959f2bdb8ca55ed194cd87bf1911e87e29010787d21ac84308e6182536
bundle_sha256=cc35ab6d80cc6ccf265b708d28e7386fdea5b238c4b7b63688791f6f60c28c38
evidence_manifest_sha256=45341f4c0f4424547a108bd4202d6afc09ec9525b976dcf62df36830fa5c605d
```

## 摩擦、误报与未决项

1. 首次 scaffold create 后，`scanner_sha256` 从 `a1e7...affa` 变为 `9086...2e0`，首次 finalize 因 `SCAFFOLD_POLICY_DRIFT` 返回 `FAIL/1`。在当前 policy 下重建同一 FOCUS scaffold 后 finalize 成功；失败工件保留，未改 hash 绕过。
2. scaffold 的 `NO_HIGH_FINDINGS/0` 只表示没有 scanner high，不等于 `NO_CHANGE`。本次 6 个 FOCUS span 来自连续阅读，并由工具完成唯一定位、保护区拦截和 UTF-8 绑定。
3. 原扫描器把连续 4 个公式字幕记为 medium 候选；其中“水平方向合力为”有对象标识功能，未因表面命中强制删除。该组命中不是 AI 判定。
4. applicator 的权威输出和持久化 result 均为 `REVIEW/2`；外层 `functions.exec` 将非零子进程表面化为 `Script error exit=1`。台账同时记录两层值，最终状态只读取 result 的 `delivery_gate_status=REVIEW, exit_code=2`。
5. 没有可信外部 paired-quality clearance，因此没有质量批准权。语义蕴含和物理正确性均未评估。
6. 两次只读 PowerShell 汇总因 `foreach` 后直接接管道触发 `empty pipe element`，另有一次 JavaScript 组合验收在子命令启动前触发语法错误；改用数组收集与独立命令后均通过，未改动候选或证据闭集。

## 未决项

- 外部成对文风复核：`PENDING_EXTERNAL_REVIEW`。
- 学术/物理正确性：`NOT_EVALUATED`。
- 自然语言语义完整性：`NOT_EVALUATED`。
- 当前工作文件新鲜度没有外部可信绑定；本次只证明冻结闭集自洽。
