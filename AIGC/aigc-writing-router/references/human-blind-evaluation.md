# Human blind pair evaluation

Use this stage only after deterministic protection checks pass. It compares two
same-source passages as writing, without asking a detector to infer authorship.

## What raters see

Each pair is randomly labelled `A` and `B`. The packet hides provider, source
status and candidate status. Keep `evaluation-key.json` away from raters until
all rating rows are frozen. The key records SHA-256 for the source-pair file and
the anonymised packet; scoring fails if the visible packet changes afterward.
The score report also records the compared variant IDs, per-pair dimension
counts and non-empty rater notes, and hashes the key, ratings, packet and
source-pair files. A release decision may use the report only when those IDs
match the candidate IDs in the long-form ledger.

Rate five separate questions:

- `naturalness`: does the passage read like purposeful academic prose rather
  than a sequence of interchangeable template sentences?
- `judgment_trajectory`: can the reader follow the public, evidence-based
  decisions that led from the observed difficulty to the adopted treatment?
- `specificity`: are data conditions, variables, boundary cases and result
  changes named concretely?
- `content_density`: does each paragraph perform a distinct explanatory job
  without padding or unexplained jumps?
- `semantic_fidelity`: does the candidate preserve the source claim, scope,
  uncertainty and mathematical direction?

Choose `A`, `B`, `TIE` or `SKIP` for every dimension. A formal comparison should
use at least two independent raters per pair. Discuss disagreements after scores
are recorded; do not let the first rater train the second.

`SKIP` records that the reviewer cannot judge that dimension; it is excluded from
`effective_human_coverage`. Every pair-dimension needs at least two effective human
votes and a strict majority. If two reviewers split, freeze both CSV files and add
an independent third reviewer instead of editing either prior row. The score report
retains per-dimension vote counts and `pairwise_exact_agreement`.

Every rating row also declares `rater_kind=human|model`. Independent model
raters may be used as development probes, but their votes are reported under
`model_coverage` and can never satisfy release coverage. Formal evidence requires
`formal_human_ready=true`, at least two complete human rows in
`effective_human_coverage`, and a strict majority for every dimension. Missing legacy `rater_kind` values remain
`unspecified`; they are not silently promoted to human evidence.

## Commands

```powershell
python scripts/sample_tex_blind_pairs.py source.tex candidate.tex `
  --output-spec holdout-spec.json --total 12 --seed 20260818 `
  --exclude-spec development-spec.json --exclude-spec previous-holdout-spec.json
python scripts/prepare_tex_blind_pairs.py holdout-spec.json --output holdout-pairs.json
python scripts/blind_pair_evaluation.py prepare holdout-pairs.json --output-dir blind-run --seed 2026
# Each reviewer opens blind-run/review.html locally and exports one CSV.
python scripts/render_style_benchmark_review.py audit blind-run/review-bundle.json --format text
python scripts/merge_style_benchmark_ratings.py blind-run/evaluation-packet.json `
  ratings-R01.csv ratings-R02.csv --output blind-run/ratings-merged.csv `
  --report blind-run/ratings-merge.json --format text
python scripts/seal_tex_blind_holdout.py --spec holdout-spec.json --pairs holdout-pairs.json `
  --key blind-run/evaluation-key.json --packet blind-run/evaluation-packet.json `
  --ratings-template blind-run/ratings-template.csv --review-page blind-run/review.html `
  --review-bundle blind-run/review-bundle.json --rule-file scripts/audit_academic_candidate.py `
  --release-id release-v1 --output holdout-seal.json
python scripts/audit_tex_blind_holdout.py holdout-seal.json --format text
python scripts/blind_pair_evaluation.py score blind-run/evaluation-key.json blind-run/ratings-merged.csv `
  --merge-report blind-run/ratings-merge.json --output blind-run/score.json --format json
```

If a historical seal still binds its packet but its rule files have since changed,
do not reseal the old candidate with current rule hashes. Upgrade only the review
transport and retain the historical boundary:

```powershell
python scripts/attach_legacy_blind_review.py attach old-holdout-seal.json --output review-addendum.json
python scripts/attach_legacy_blind_review.py audit review-addendum.json --format text
```

The addendum verifies the inherited spec, pairs, key, packet and ratings template,
records current rule drift, and forces `current_release_validation=false`. A PASS
means that the historical blind packet can be reviewed safely; it does not relabel
that candidate as output from the current rules.

`sample_tex_blind_pairs.py` 只适用于逐行同构的 TeX 源稿与候选。它只从发生改动的正文行中
取样，按章节和固定随机种子分层，并记录 `quality_labels_used=false`；源稿、候选和可选的
开发 spec 都按 SHA-256 绑定。显式 spec 与 pairs 映射属于私有准备材料，评审者只接收匿名
`review.html`，或 `evaluation-packet.json` 和评分表副本。网页把 packet 以 base64 数据嵌入，
只用 `textContent` 显示段落；provider、源稿/候选身份、key 和 pair-map 均不进入页面。
`review-bundle.json` 锁定 packet、页面和空白模板，发放前先审计。两名评审独立导出单人 CSV，
`merge_style_benchmark_ratings.py` 拒绝缺对、重复评审编号、非 human 声明和非法选项，并保存
绑定 packet、每名单人 CSV、评审编号和合并输出的 merge report。正式 benchmark 会重新计算
这些输入；只提供一张手工拼接的 CSV 不能推进状态。
源稿与候选不逐行同构时，应人工指定各自的准确行号，
再直接调用 `prepare_tex_blind_pairs.py`。

在发出评审包前运行 `seal_tex_blind_holdout.py`，把 spec、pairs、匿名 packet、私有 key、评分表、
本版写作规则、`aigc-blind-scoring/v2` 和评分脚本一并锁定为 `SEALED_UNSCORED`。封存后不得根据该留出集改动同一 release 的
规则；若规则哈希变化，应建立新的 release 和新的未见留出集。交付评分表前及汇总评分前都运行
`audit_tex_blind_holdout.py`；任一工件或规则哈希漂移都会失败。

Do not tune repeatedly on the same held-out pairs. Keep a development set for
prompt and rule changes, and reserve a fresh set for the next release decision.
Human preference is evidence about these visible passages only; it is not proof
of human authorship or of performance against an external detector.
