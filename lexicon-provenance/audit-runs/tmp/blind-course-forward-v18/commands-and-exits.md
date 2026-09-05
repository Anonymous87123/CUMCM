# 实际命令与退出码

以下记录任务相关的工件生成、验证和故障定位命令。Skill/引用文件的纯读取命令均为只读；首次 raw Skill 读取为 `exit=0`，但终端编码错误且输出截断，随后用 `Get-Content -Encoding UTF8` 分段重读，均为 `exit=0`。

## 范围与准备

```powershell
Test-Path -LiteralPath 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18'
# exit=0; output=False

New-Item -ItemType Directory -Path 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18'
# exit=0

$orig=(Get-Content -Encoding UTF8 'D:\code LateX\elegantbook\physics\physics1.tex')[397..406]; $slice=Get-Content -Encoding UTF8 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18\source.lines-398-407.tex'; Compare-Object -CaseSensitive $orig $slice
# exit=0; PerLineExact=True; 10/10 lines
```

`source.lines-398-407.tex`、FOCUS JSON、authoring hunk 和本审计文件通过 `apply_patch` 写入工件目录；`apply_patch` 不是子进程，没有 OS 退出码，工具调用均成功。

## 首轮流程与 policy 漂移

```powershell
python scripts/scan_humanize_chinese.py 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18\source.lines-398-407.tex' --scene AUTO --format text
# exit=0; high=0; medium formula-caption candidates=4

python scripts/scaffold_humanize_short_patch.py create 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18\source.lines-398-407.tex' --scene COURSE --source-kind DOCUMENT --suggest-spans FOCUS --focus-spec 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18\focus.json' --output 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18\selection.authoring.json' --format text
# exit=0; NO_HIGH_FINDINGS; suggestions=6; route=EXPLICIT COURSE

python scripts/scaffold_humanize_short_patch.py finalize 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18\source.lines-398-407.tex' --authoring 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18\selection.authoring.json' --output 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18\selection.v2.json' --format text
# exit=1; FAIL: SCAFFOLD_POLICY_DRIFT

python scripts/scaffold_humanize_short_patch.py create 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18\source.lines-398-407.tex' --scene COURSE --source-kind DOCUMENT --suggest-spans FOCUS --focus-spec 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18\focus.json' --output 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18\selection.authoring.retry.json' --format text
# exit=0; NO_HIGH_FINDINGS; suggestions=6

# First policy-hash comparison PowerShell expression
# exit=1; ParserError: empty pipe element

# Corrected policy-hash comparison
# exit=0; only scanner_sha256 differed

python scripts/scaffold_humanize_short_patch.py finalize 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18\source.lines-398-407.tex' --authoring 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18\selection.authoring.retry.json' --output 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18\selection.v2.json' --format text
# exit=0; FINALIZED hunks=6 selected=6

python scripts/build_humanize_short_patch.py 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18\source.lines-398-407.tex' --selection-spec 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18\selection.v2.json' --output 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18\patch.bundle.json' --format json
# exit=0; BUNDLED; coverage=PASS

python scripts/apply_humanize_short_patch.py 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18\source.lines-398-407.tex' --bundle 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18\patch.bundle.json' --output 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18\review' --format text
# child/result exit=2; DELIVERY REVIEW
# outer functions.exec surface=1 because the child exit was nonzero
```

首轮 `review/` 的 verifier、改后扫描与公式比较均为 `exit=0`；闭集自洽、公式 10/10 逐字一致。模型成对复核随后发现删除字幕留下 TeX 空段，因此该 candidate 被废弃，没有作为最终候选交付。

## 最终流程

```powershell
python scripts/scaffold_humanize_short_patch.py create 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18\source.lines-398-407.tex' --scene COURSE --source-kind DOCUMENT --suggest-spans FOCUS --focus-spec 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18\focus.final.json' --output 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18\selection.authoring.final.json' --format text
# exit=0; NO_HIGH_FINDINGS; suggestions=6; route=EXPLICIT COURSE

python scripts/scaffold_humanize_short_patch.py finalize 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18\source.lines-398-407.tex' --authoring 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18\selection.authoring.final.json' --output 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18\selection.final.v2.json' --format text
# exit=0; FINALIZED hunks=6 selected=6

python scripts/build_humanize_short_patch.py 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18\source.lines-398-407.tex' --selection-spec 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18\selection.final.v2.json' --output 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18\patch.final.bundle.json' --format json
# exit=0; BUNDLED; coverage=PASS; bundle=cc35ab6d...c28c38

python scripts/apply_humanize_short_patch.py 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18\source.lines-398-407.tex' --bundle 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18\patch.final.bundle.json' --output 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18\review-final' --format text
# child/result exit=2; DELIVERY REVIEW
# unified_validator=PASS; paired_quality=PENDING_EXTERNAL_REVIEW
# outer functions.exec surface=1 because the child exit was nonzero

# One combined JavaScript orchestration attempt before child execution
# functions.exec exit=1; SyntaxError: Unexpected identifier 'r'; no child checks ran

python scripts/verify_humanize_short_patch.py 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18\review-final' --format text
# exit=0; INTEGRITY PASS; CURRENT_POLICY_REPLAY PASS; COVERAGE PASS; DELIVERY REVIEW

python scripts/scan_humanize_chinese.py 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18\review-final\candidate.review.tex' --scene AUTO --format text
# exit=0; no candidate findings emitted

$a=Get-Content -Raw -Encoding UTF8 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18\source.lines-398-407.tex'; $b=Get-Content -Raw -Encoding UTF8 'D:\code LateX\elegantbook\physics\tmp\blind-course-forward-v18\review-final\candidate.review.tex'; $pattern='\\\((?s:.*?)\\\)'; $ma=[regex]::Matches($a,$pattern)|ForEach-Object{$_.Value}; $mb=[regex]::Matches($b,$pattern)|ForEach-Object{$_.Value}; Compare-Object -CaseSensitive $ma $mb
# exit=0; SourceFormulaCount=10; CandidateFormulaCount=10; FormulaSequenceExact=True; CandidateBlankLines=0

# First final artifact inventory expression
# exit=1; ParserError: empty pipe element

# Corrected final artifact inventory using an intermediate $rows array
# exit=0; all required artifacts Exist=True
```

## 最终权威退出状态

```text
candidate delivery: REVIEW/2
mechanical validator: PASS
closed-set verifier: PASS/0 (SELF_CONSISTENCY_ONLY)
paired-quality: PENDING_EXTERNAL_REVIEW
academic correctness: NOT_EVALUATED
```
