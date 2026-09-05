AI-CHECK EVIDENCE REPORT
========================

SCOPE: source-bound prose signals only; no authorship or detector verdict
SIGNAL LOAD: 7 / 27
CALIBRATION: low confidence for Chinese academic/CUMCM prose; genre-required structure is down-weighted

SIGNAL BREAKDOWN
----------------
A. Perplexity            0  术语和数字都落在具体模型、对象和结果上，未见脱离语境的安全套词。
B. Burstiness            1  摘要和问题分析有连续的中长句，但数学建模摘要本身允许这种压缩。
C. Hedge density         1  “可能”“未必”“若……则”均出现在边界或稳健性判断处，属于有依据的限定；仍有少量可再压实的句子。
D. Structural tells      2  五个分问的平行摘要和问题清单是明显结构信号，但这是竞赛论文的必要接口。
E. Specificity           0  1.805、1.838、0.204、3.2186、75 组测试等数字把主要判断落到了可复核对象。
F. Transitions           1  “据此”“进一步”“因此”等连接词分布在模型分析和评价段，未形成每段固定开头。
G. Punctuation           0  分号承担表格化结果并列，未见非学术语境中的破折号或标题式冒号。
H. Voice / register      1  全文维持稳定的正式论文声部，个人口吻较少；但“我们先……”“有意把……”保留了队伍判断痕迹。
I. Rhetorical scaffolding 0  段落中存在判断—计算—结果—边界的来回，但没有连续的套式收束或“不是……而是……”纠偏壳。

EVIDENCE LOG
------------
SIGNAL-B | “问题一按食性保留……问题二接收……问题三、四采用……问题五……” | severity: weak; abstract is necessarily compressed and the five-question inventory is factual.
SIGNAL-C | “若不同步推进……仍可能逐步减弱”“若要定位分岔值，仍须……” | severity: weak; both clauses state explicit scope limits rather than reflexive politeness.
SIGNAL-D | “题目提出的五个子问题依次为” followed by the five-item list | severity: moderate; this is a genre-required map, not evidence that the prose should be rewritten into a paragraph.
SIGNAL-D | Abstract repeats the five-question result order and the body later revisits the same dependency chain | severity: weak; retain the map, but remove only duplicated wording if the team confirms it is redundant.
SIGNAL-F | “据此”“进一步”“因此” at lines 57, 69, 74, 187 and 517 | severity: weak; the transitions connect explicit calculations and sensitivity decisions, not empty paragraph openers.
SIGNAL-H | Formal neutral register throughout, with limited first-person traces | severity: weak; appropriate for a CUMCM manuscript and partly offset by “我们在问题一中……” and “有意把……” judgments.

REMAINING REVIEW TARGETS
------------------------
The strongest remaining style signal is structural: the abstract inventories five questions in parallel and the introduction maps them again. A few transition words also recur, but they are attached to parameter scans, counterfactuals, or scope limits. The passage-level evidence is otherwise concrete: choices about what to collapse, what to compare, and where to stop claiming a threshold are visible in the prose.

RECOMMENDED FIXES
-----------------
1. Keep the five-question list as an interface, but avoid restating all five in the next paragraph unless the paragraph adds a different dependency or decision.
2. In the abstract, retain one semicolon-separated result cluster and move one mechanism explanation to the body if page pressure permits; do not delete the numeric anchors.
3. Before submission, have a team member read the two “若……则……” robustness paragraphs against the actual scripts and retain the hedges only where the tested range supports them.
