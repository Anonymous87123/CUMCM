#!/usr/bin/env python3
"""Positive and negative regression tests for the content-density audit."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from audit_content_density import (
    audit, category_for, corpus_hints, paragraph_category, question_number,
)


def write_aux(path: Path) -> None:
    path.write_text(
        r"\newlabel{mcm-body-start}{{1}{3}{正文}{section.1}{}}" "\n"
        r"\newlabel{mcm-q1-start}{{2}{3}{问题一}{section.2}{}}" "\n"
        r"\newlabel{mcm-q1-end}{{3}{7}{问题一结束}{section.3}{}}" "\n"
        r"\newlabel{mcm-body-end}{{4}{27}{正文结束}{section.4}{}}",
        encoding="utf-8",
    )


def write_coverage(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "questions": [
                    {
                        "id": "Q1",
                        "start_label": "mcm-q1-start",
                        "end_label": "mcm-q1-end",
                        "section_titles": ["问题一", "结果分析"],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def main() -> int:
    assert category_for(["问题一模型的建立与求解", "候选搜索与回放"]) == "solve"
    assert category_for(["结果分析、模型检验与跨问复核", "三种结果的差异"]) == "result"
    assert category_for(["结果分析、模型检验与跨问复核", "局部敏感性"]) == "validation"
    assert paragraph_category(["问题三的模型建立与求解", "求解与结果"], "采用 RK4 对状态方程积分，步长取 0.01，并按终止条件迭代。") == "solve"
    assert paragraph_category(["问题三的模型建立与求解", "求解与结果"], "图3显示峰值比基准情景下降了12%。") == "result"
    assert paragraph_category(
        ["\u95ee\u9898\u4e00\u7684\u6a21\u578b\u5efa\u7acb\u4e0e\u6c42\u89e3"],
        "\u6570\u503c\u6c42\u89e3\u91c7\u7528 RK4 \u79ef\u5206\uff0c\u6b65\u957f\u53d6 0.01\uff0c\u6309\u7ec8\u6b62\u6761\u4ef6\u8fed\u4ee3\u3002",
    ) == "solve"
    assert paragraph_category(
        ["\u95ee\u9898\u4e00", "\u6c42\u89e3\u4e0e\u7ed3\u679c"],
        "\u91c7\u7528 RK4 \u79ef\u5206\uff0c\u6b65\u957f\u53d6 0.01\uff0c\u8ba1\u7b97\u7ed3\u679c\u4e3a 3.2\u3002",
    ) == "solve"
    assert paragraph_category(
        ["\u95ee\u9898\u4e8c", "\u7ed3\u679c\u5206\u6790"],
        "\u5bf9\u53c2\u6570\u65bd\u52a0 20% \u5c40\u90e8\u6270\u52a8\uff0c\u6392\u5e8f\u7a33\u5b9a\u7387\u4ecd\u4e3a 100%\u3002",
    ) == "validation"
    assert question_number("问题五的模型建立与求解") == 5
    assert question_number("第五问模型求解") == 5
    assert question_number("问题五分析") is None
    with tempfile.TemporaryDirectory(prefix="mcm-density-") as temp_dir:
        root = Path(temp_dir)
        tex = root / "main.tex"
        aux = root / "main.aux"
        coverage = root / "coverage.json"
        write_aux(aux)
        write_coverage(coverage)

        tex.write_text(
            r"""
\label{mcm-body-start}
\section{问题重述}
题目给出的记录以设备每分钟状态为单位，因此先保留时间顺序，再统一缺失值标记。

\label{mcm-q1-start}
\section{问题一的模型建立与求解}
状态量表示相邻时刻的设备位置，边界条件由观测区间给定，状态转移关系只连接前后两个时刻。

检查原始曲线后可以看到，边界附近的变化比区间内部更快，固定步长会漏掉首次事件。

据此把状态更新写成下式，步长只在事件函数接近零时缩小，其他区间仍采用原来的尺度。
\begin{equation}x_{t+1}=x_t+h f(x_t).\end{equation}

\begin{figure}\caption{状态轨迹与事件位置}\end{figure}
\begin{table}\caption{不同步长下的首次事件}\begin{tabular}{cc}步长&时刻\\1&2\end{tabular}\end{table}

\section{结果分析}
表中首次事件时刻随步长加密逐渐稳定，最后两次计算的差值已经低于题目要求的时间精度。

这个差值只检验离散误差，不能说明机理假设本身正确，因此结论限定在当前边界条件内。
\label{mcm-q1-end}
\section{模型评价与改进}
现有实现保留了事件附近的局部加密，后续仍需用另一组初值检查事件次序是否改变。
\label{mcm-body-end}
""",
            encoding="utf-8",
        )
        good = audit(tex, aux, coverage, "A", None)
        body = good["body"]
        question = good["questions"][0]
        if good["status"] != "pass" or question["pages"] != 5:
            print("FAIL: valid question span was not measured", good)
            return 1
        if body["tables"] != 1 or body["tabular_blocks"] != 1:
            print("FAIL: table float and tabular block were not separated", body)
            return 1
        if question["formulas"] < 1 or question["result_explanations"] < 1:
            print("FAIL: substantive question signals were not counted", question)
            return 1
        if (
            question["action_distribution"]["model"]["paragraphs"] < 1
            or question["action_distribution"]["solve"]["paragraphs"] < 1
            or question["action_distribution"]["result"]["paragraphs"] < 1
        ):
            print("FAIL: per-question action distribution did not separate model, solve and result", question)
            return 1
        if (
            question["action_evidence"]["model"]["paragraphs"] < 1
            or question["action_evidence"]["solve"]["paragraphs"] < 1
            or question["action_evidence"]["result"]["paragraphs"] < 1
            or question["action_evidence"]["validation"]["paragraphs"] < 1
        ):
            print("FAIL: overlapping per-question action evidence is incomplete", question)
            return 1
        for category in ("model", "result", "evaluation"):
            if body["categories"][category]["han_chars"] == 0:
                print(f"FAIL: {category} heading was not mapped to its own prose", body)
                return 1
        if body["action_evidence"]["solve"]["paragraphs"] < 1:
            print("FAIL: whole-document overlapping action evidence is missing", body)
            return 1

        inferred_aux = root / "inferred.aux"
        inferred_aux.write_text(
            r"\@writefile{toc}{\contentsline {section}{\numberline {一、}问题一的模型建立与求解}{5}{section.1}}" "\n"
            r"\@writefile{toc}{\contentsline {section}{\numberline {二、}问题二的模型建立与求解}{8}{section.2}}" "\n"
            r"\@writefile{toc}{\contentsline {section}{\numberline {三、}结论}{11}{section.3}}",
            encoding="utf-8",
        )
        tex.write_text(
            r"""
\section{问题一的模型建立与求解}
检查边界后采用数值积分推进状态变量，并在步长减半后重新运行一次。

\subsection{求解与结果}
图一显示两次计算已趋于一致，最大差值低于给定精度。
\section{问题二的模型建立与求解}
根据变量范围建立约束，并采用网格搜索计算可行方案。
\section{结论}
两个分问均已给出相应结果及其适用条件。
""",
            encoding="utf-8",
        )
        inferred = audit(tex, inferred_aux, None, "A", None)
        if [item["id"] for item in inferred["questions"]] != ["Q1", "Q2"]:
            print("FAIL: conventional Chinese question headings were not inferred", inferred)
            return 1
        if inferred["questions"][0]["pages"] != 3 or inferred["questions"][1]["pages"] != 3:
            print("FAIL: inferred question page spans were not measured from AUX", inferred)
            return 1

        # Standard TeX document boundaries are sufficient when the optional
        # MCM body labels are absent; the audit must not emit a false warning.
        tex.write_text(
            r"\documentclass{article}\begin{document}" +
            "\\section{闂涓€}\n" +
            "鎹嵁鏁版嵁璁板綍鎺ㄨ繘璁＄畻锛岀粨鏋滃湪姝ｅ父鑼冨洿鍐呯ǔ瀹氥€?\n" +
            r"\end{document}",
            encoding="utf-8",
        )
        standard_bound = audit(tex, None, None, "A", None)
        if any(item["code"] == "BODY_MARKER_MISSING" for item in standard_bound["findings"]):
            print("FAIL: standard document boundaries were treated as missing body markers", standard_bound)
            return 1
        if standard_bound["body_boundary"]["method"] != "document-environment":
            print("FAIL: standard document boundary method was not recorded", standard_bound)
            return 1

        stats = root / "stats.json"
        stats.write_text(json.dumps({
            "section_by_problem_type": {
                "A": {"result": {"share_of_paper_han": {"q1": 0.08, "q3": 0.12}}}
            }
        }), encoding="utf-8")
        hints = corpus_hints({
            "han_chars": 1000,
            "categories": {"result": {"han_chars": 500}},
        }, stats, "A")
        if not any("结果堆叠" in hint for hint in hints) or any("背景或通用评价" in hint for hint in hints):
            print("FAIL: category-specific corpus hint regressed", hints)
            return 1

        tex.write_text(
            r"\label{mcm-body-start}\label{mcm-q1-start}问题一"
            r"\label{mcm-q2-start}问题二\label{mcm-q1-end}"
            r"\label{mcm-q2-end}\label{mcm-body-end}",
            encoding="utf-8",
        )
        coverage.write_text(json.dumps({
            "questions": [
                {"id": "Q1", "start_label": "mcm-q1-start", "end_label": "mcm-q1-end"},
                {"id": "Q2", "start_label": "mcm-q2-start", "end_label": "mcm-q2-end"},
            ]
        }), encoding="utf-8")
        overlap = audit(tex, aux, coverage, "A", None)
        if not any(item["code"] == "QUESTION_SCOPE_OVERLAP" for item in overlap["findings"]):
            print("FAIL: content density accepted overlapping question spans", overlap)
            return 1
        write_coverage(coverage)

        filler = "本节内容较为简单，下面进行进一步说明和讨论分析。"
        repeated = "这一部分继续围绕前述内容展开说明，相关文字仅用于补充篇幅，并没有增加新的对象、关系或数值依据。"
        tex.write_text(
            "\\label{mcm-body-start}\n\\section{问题一}\n"
            + ("\n\n".join([filler] * 10 + [repeated] * 5))
            + "\n\\vspace{8cm}\n\\vfill\n\\label{mcm-body-end}\n",
            encoding="utf-8",
        )
        padded = audit(tex, aux, coverage, "A", None)
        codes = {item["code"] for item in padded["findings"]}
        required = {"REPEATED_PROSE", "LOW_INFORMATION_PROSE", "LAYOUT_PADDING_SIGNAL"}
        if not required.issubset(codes):
            print("FAIL: padded prose signals were not all reported", padded)
            return 1

    print("PASS: content density, disjoint question spans, table counting, repetition and padding signals are enforced.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
