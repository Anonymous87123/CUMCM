from __future__ import annotations

import csv
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".cumcm-work"
REPORT = ROOT / "assignment.tex"
UNCONFIRMED = "未检出（严格 OCR 阈值下不补字）"


FEATURES = [
    ("摘要", "摘要_page"),
    ("问题分析", "问题分析_page"),
    ("模型求解", "模型求解_page"),
    ("结果解释", "结果分析_page"),
    ("模型检验", "模型检验_page"),
    ("灵敏度分析", "灵敏度分析_page"),
    ("模型评价", "模型评价_page"),
    ("参考文献", "参考文献_page"),
    ("附录", "附录_page"),
]


# Canonical leaf nodes transcribed from 1.png. Each regex points to the report's
# spelling, allowing Chinese/English aliases without treating OCR errors as facts.
ALGORITHMS = [
    ("数据前处理与探索", "缺失值处理", "均值填充", "组员2", r"均值/中位数"),
    ("数据前处理与探索", "缺失值处理", "插值填充", "组员2", r"插值"),
    ("数据前处理与探索", "缺失值处理", "KNN 填充", "组员2", r"KNN"),
    ("数据前处理与探索", "缺失值处理", "删除法", "组员2", r"删除"),
    ("数据前处理与探索", "异常值处理", "3σ 准则", "组员2", r"3\\sigma"),
    ("数据前处理与探索", "异常值处理", "箱线图", "组员2", r"箱线图"),
    ("数据前处理与探索", "异常值处理", "Isolation Forest", "组员2", r"Isolation Forest"),
    ("数据前处理与探索", "重复值处理", "去重", "组员2", r"重复样本删除"),
    ("数据前处理与探索", "重复值处理", "重复样本合并", "组员2", r"重复样本删除/合并"),
    ("数据前处理与探索", "尺度处理", "标准化", "组员2", r"Z-score 标准化"),
    ("数据前处理与探索", "尺度处理", "Min-Max 归一化", "组员2", r"Min--Max 归一化"),
    ("数据前处理与探索", "分类变量处理", "独热编码", "组员2", r"one-hot"),
    ("数据前处理与探索", "分类变量处理", "标签编码", "组员2", r"label 编码"),
    ("数据前处理与探索", "连续变量离散化", "等宽分箱", "组员2", r"等宽/等频分箱"),
    ("数据前处理与探索", "连续变量离散化", "等频分箱", "组员2", r"等宽/等频分箱"),
    ("数据前处理与探索", "相关性分析", "Pearson", "组员2", r"Pearson"),
    ("数据前处理与探索", "相关性分析", "Spearman", "组员2", r"Spearman"),
    ("数据前处理与探索", "相关性分析", "Kendall", "组员2", r"Kendall"),
    ("数据前处理与探索", "聚类分析", "K-Means", "组员2", r"K-Means"),
    ("数据前处理与探索", "聚类分析", "DBSCAN", "组员2", r"DBSCAN"),
    ("数据前处理与探索", "聚类分析", "层次聚类", "组员2", r"层次聚类"),
    ("数据前处理与探索", "聚类分析", "谱聚类", "组员2", r"谱聚类"),
    ("数据前处理与探索", "插值拟合", "Lagrange 插值", "组员2", r"Lagrange"),
    ("数据前处理与探索", "插值拟合", "三次样条插值", "组员2", r"三次样条"),
    ("数据前处理与探索", "插值拟合", "Kriging 插值", "组员2", r"Kriging"),
    ("数据前处理与探索", "降维算法", "PCA", "组员2", r"PCA"),
    ("数据前处理与探索", "降维算法", "t-SNE", "组员2", r"t-SNE"),
    ("数据前处理与探索", "降维算法", "UMAP", "组员2", r"UMAP"),
    ("数据前处理与探索", "样本筛选", "Monte Carlo 随机抽样", "组员2/组员1交叉", r"Monte Carlo 随机抽样"),
    ("机理分析法", "动力学模型", "Newton 运动定律", "队长", r"牛顿第二定律"),
    ("机理分析法", "动力学模型", "弹簧阻尼振动", "队长", r"弹簧.阻尼"),
    ("机理分析法", "种群模型", "Logistic 增长", "队长", r"Logistic 方程"),
    ("机理分析法", "种群模型", "捕食者-猎物模型", "队长", r"捕食.被捕食"),
    ("机理分析法", "传热/冷却模型", "Newton 冷却定律", "队长", r"Newton 冷却"),
    ("机理分析法", "药物与传播", "药物代谢", "队长", r"药物.*代谢"),
    ("机理分析法", "药物与传播", "SIR", "队长", r"SIR/SIS"),
    ("机理分析法", "药物与传播", "SIS", "队长", r"SIR/SIS"),
    ("机理分析法", "PDE", "热传导方程", "队长", r"热传导方程"),
    ("机理分析法", "PDE", "波动方程", "队长", r"波动"),
    ("机理分析法", "PDE", "扩散方程", "队长", r"扩散"),
    ("机理分析法", "PDE", "流体渗流", "队长", r"多孔介质渗流"),
    ("经典物理机理", "力学", "刚体平衡", "队长", r"刚体平衡"),
    ("经典物理机理", "力学", "摩擦力", "队长", r"摩擦"),
    ("经典物理机理", "力学", "万有引力", "队长", r"重力"),
    ("经典物理机理", "电学", "Ohm 定律", "队长", r"Ohm 定律"),
    ("经典物理机理", "电学", "Kirchhoff 电路模型", "队长", r"Kirchhoff"),
    ("经典物理机理", "流体", "Bernoulli 方程", "队长", r"Bernoulli"),
    ("经典物理机理", "流体", "流量/质量守恒", "队长", r"质量守恒"),
    ("经典物理机理", "热力学", "理想气体状态方程", "队长", r"理想气体"),
    ("机理模型求解", "数值积分", "Euler 法", "队长", r"Euler"),
    ("机理模型求解", "数值积分", "RK4", "队长", r"RK4"),
    ("机理模型求解", "空间离散", "FDM", "队长", r"FDM"),
    ("机理模型求解", "空间离散", "FEM", "队长", r"FEM"),
    ("评价与决策", "主观评价", "AHP", "组员2", r"AHP"),
    ("评价与决策", "主观评价", "模糊综合评价", "组员2", r"模糊综合评价"),
    ("评价与决策", "主观评价", "FAHP", "组员2", r"FAHP"),
    ("评价与决策", "客观评价", "灰色关联分析", "组员2", r"灰色关联"),
    ("评价与决策", "客观评价", "PCA", "组员2", r"PCA"),
    ("评价与决策", "客观评价", "因子分析", "组员2", r"因子分析"),
    ("评价与决策", "客观权重", "熵权法", "组员2", r"熵权"),
    ("评价与决策", "客观权重", "CRITIC 权重法", "组员2", r"CRITIC"),
    ("评价与决策", "客观权重", "变异系数法", "组员2", r"变异系数"),
    ("评价与决策", "综合评价", "TOPSIS", "组员2", r"TOPSIS"),
    ("评价与决策", "综合评价", "VIKOR", "组员2", r"VIKOR"),
    ("评价与决策", "综合评价", "灰色综合评价", "组员2", r"灰色综合评价"),
    ("评价与决策", "综合评价", "物元可拓模型", "组员2", r"物元可拓"),
    ("评价与决策", "组合赋权", "熵权-AHP", "组员2", r"熵权--AHP"),
    ("评价与决策", "组合赋权", "CRITIC-TOPSIS", "组员2", r"CRITIC--TOPSIS"),
    ("优化模型", "规划分类", "线性规划", "组员1", r"连续线性规划"),
    ("优化模型", "规划分类", "非线性规划", "组员1", r"非线性规划"),
    ("优化模型", "规划分类", "二次规划", "组员1", r"二次规划"),
    ("优化模型", "规划分类", "整数规划", "组员1", r"整数规划"),
    ("优化模型", "规划分类", "混合整数规划", "组员1", r"混合整数线性规划"),
    ("优化模型", "规划分类", "0-1 规划", "组员1", r"0--1 规划"),
    ("优化模型", "目标分类", "单目标规划", "组员1", r"单目标与多目标"),
    ("优化模型", "目标分类", "多目标规划", "组员1", r"单目标与多目标"),
    ("优化模型", "不确定性分类", "随机规划", "组员1", r"随机规划"),
    ("优化模型", "不确定性分类", "确定规划", "组员1", r"确定性与随机性"),
    ("智能优化", "基础算法", "GA", "组员1", r"遗传算法"),
    ("智能优化", "基础算法", "PSO", "组员1", r"粒子群"),
    ("智能优化", "基础算法", "SA", "组员1", r"模拟退火"),
    ("智能优化", "基础算法", "ACO", "组员1", r"蚁群"),
    ("智能优化", "基础算法", "DE", "组员1", r"差分进化"),
    ("智能优化", "基础算法", "贪心算法", "组员1", r"贪心"),
    ("智能优化", "多目标优化", "NSGA-II", "组员1", r"NSGA-II"),
    ("智能优化", "多目标优化", "MOPSO", "组员1", r"MOPSO"),
    ("智能优化", "新型元启发", "MFO", "组员1", r"蛾火焰优化"),
    ("智能优化", "新型元启发", "WOA", "组员1", r"鲸鱼优化"),
    ("智能优化", "新型元启发", "SSA", "组员1", r"麻雀搜索"),
    ("图与网络", "最短路径", "Dijkstra", "组员1", r"Dijkstra"),
    ("图与网络", "最短路径", "Floyd", "组员1", r"Floyd"),
    ("图与网络", "最短路径", "SPFA", "组员1", r"SPFA"),
    ("图与网络", "最小生成树", "Prim", "组员1", r"Prim"),
    ("图与网络", "最小生成树", "Kruskal", "组员1", r"Kruskal"),
    ("图与网络", "网络流", "最大流", "组员1", r"最大流"),
    ("图与网络", "网络流", "最小费用流", "组员1", r"最小费用流"),
    ("图与网络", "其他", "路径规划", "组员1", r"路径规划"),
    ("图与网络", "其他", "二分图匹配", "组员1", r"二分图匹配"),
    ("图与网络", "其他", "网络节点重要度", "组员1", r"节点重要性"),
    ("预测与分类", "传统时序", "ARIMA", "组员2", r"ARIMA"),
    ("预测与分类", "传统时序", "SARIMA", "组员2", r"SARIMA"),
    ("预测与分类", "传统时序", "指数平滑", "组员2", r"指数平滑"),
    ("预测与分类", "传统时序", "VAR", "组员2", r"VAR"),
    ("预测与分类", "传统时序", "GM(1,1)", "组员2", r"GM\(1,1\)"),
    ("预测与分类", "传统时序", "灰色 Markov", "组员2", r"灰色--Markov"),
    ("预测与分类", "传统时序", "长期预测", "组员2", r"长期预测"),
    ("预测与分类", "机器学习时序", "Prophet", "组员2", r"Prophet"),
    ("预测与分类", "机器学习时序", "XGBoost 时序", "组员2", r"XGBoost"),
    ("预测与分类", "机器学习时序", "LightGBM 时序", "组员2", r"LightGBM"),
    ("预测与分类", "深度学习时序", "BP 神经网络", "组员2", r"BP"),
    ("预测与分类", "深度学习时序", "RNN", "组员2", r"RNN"),
    ("预测与分类", "深度学习时序", "LSTM", "组员2", r"LSTM"),
    ("预测与分类", "深度学习时序", "TCN", "组员2", r"TCN"),
    ("预测与分类", "深度学习时序", "GRU", "组员2", r"GRU"),
    ("预测与分类", "基础回归", "Logistic 预测模型", "组员2", r"Logistic 预测模型"),
    ("预测与分类", "基础回归", "多元线性回归", "组员2", r"多元线性"),
    ("预测与分类", "基础回归", "Ridge", "组员2", r"Ridge"),
    ("预测与分类", "基础回归", "Lasso", "组员2", r"Lasso"),
    ("预测与分类", "机器学习回归", "SVR", "组员2", r"SVR"),
    ("预测与分类", "机器学习回归", "随机森林回归", "组员2", r"随机森林"),
    ("预测与分类", "机器学习回归", "XGBoost 回归", "组员2", r"XGBoost"),
    ("预测与分类", "机器学习回归", "CatBoost 回归", "组员2", r"CatBoost"),
    ("预测与分类", "传统分类", "Logistic 二分类", "组员2", r"Logistic"),
    ("预测与分类", "传统分类", "朴素 Bayes", "组员2", r"朴素 Bayes"),
    ("预测与分类", "机器学习分类", "SVM", "组员2", r"SVM"),
    ("预测与分类", "机器学习分类", "决策树", "组员2", r"决策树"),
    ("预测与分类", "机器学习分类", "随机森林", "组员2", r"随机森林"),
    ("预测与分类", "机器学习分类", "AdaBoost", "组员2", r"AdaBoost"),
    ("预测与分类", "图像/特征分类", "CNN", "组员2", r"CNN"),
    ("实现与检验", "编程语言", "MATLAB", "三人交叉", r"MATLAB"),
    ("实现与检验", "编程语言", "Python", "三人交叉", r"Python"),
    ("实现与检验", "误差分析", "MAE", "三人交叉", r"MAE"),
    ("实现与检验", "误差分析", "MSE", "三人交叉", r"MSE"),
    ("实现与检验", "误差分析", "RMSE", "三人交叉", r"RMSE"),
    ("实现与检验", "误差分析", "MAPE", "三人交叉", r"MAPE"),
    ("实现与检验", "验证方法", "K 折交叉验证", "三人交叉", r"K 折"),
    ("实现与检验", "验证方法", "留出法", "三人交叉", r"留出"),
    ("实现与检验", "验证方法", "训练集/测试集划分", "三人交叉", r"训练测试"),
    ("实现与检验", "稳健性", "灵敏度分析", "三人交叉", r"灵敏度分析"),
    ("实现与检验", "稳健性", "参数扰动分析", "三人交叉", r"参数扰动"),
]


def write_paper_matrix() -> dict[str, int]:
    with (WORK / "paper_summary.csv").open(encoding="utf-8-sig", newline="") as handle:
        summaries = list(csv.DictReader(handle))
    with (WORK / "evidence_ledger.csv").open(encoding="utf-8-sig", newline="") as handle:
        ledger = list(csv.DictReader(handle))

    overviews = {
        (row["year"], row["problem"], row["paper"]): row
        for row in ledger
        if row["evidence_type"] == "paper_overview"
    }
    output_rows = []
    for row in summaries:
        key = (row["year"], row["problem"], row["paper"])
        overview = overviews[key]
        result = {
            "year": row["year"],
            "problem": row["problem"],
            "paper": row["paper"],
            "pages": row["pages"],
            "section_sequence": row["section_sequence"] or UNCONFIRMED,
            "model_chain": row["models_in_chain"] or UNCONFIRMED,
            "model_chain_status": "已定位" if row["models_in_chain"] else UNCONFIRMED,
            "writing_feature": overview["writing_feature"] or UNCONFIRMED,
            "original_position": overview["original_position"],
            "unconfirmed_pages": row["unconfirmed_pages"],
        }
        for label, column in FEATURES:
            result[label] = f"p.{row[column]}" if row[column] else UNCONFIRMED
        output_rows.append(result)

    output_path = WORK / "paper_feature_matrix.csv"
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)
    return {
        "rows": len(output_rows),
        "unique_papers": len({(r["year"], r["problem"], r["paper"]) for r in output_rows}),
        "pages": sum(int(r["pages"]) for r in output_rows),
        "model_chains_located": sum(r["model_chain_status"] == "已定位" for r in output_rows),
        "model_chains_unconfirmed": sum(r["model_chain_status"] != "已定位" for r in output_rows),
    }


def write_mindmap_coverage() -> dict[str, int | list[str]]:
    lines = REPORT.read_text(encoding="utf-8").splitlines()
    output_rows = []
    missing = []
    for group, branch, item, owner, pattern in ALGORITHMS:
        hit = next(
            ((number, text.strip()) for number, text in enumerate(lines, start=1) if re.search(pattern, text)),
            None,
        )
        if hit is None:
            missing.append(item)
            output_rows.append(
                {
                    "group": group,
                    "branch": branch,
                    "algorithm_or_model": item,
                    "owner": owner,
                    "report_line": "",
                    "report_evidence": "",
                    "status": "未覆盖",
                }
            )
        else:
            output_rows.append(
                {
                    "group": group,
                    "branch": branch,
                    "algorithm_or_model": item,
                    "owner": owner,
                    "report_line": hit[0],
                    "report_evidence": hit[1],
                    "status": "已覆盖",
                }
            )

    output_path = WORK / "mindmap_coverage.csv"
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)
    return {
        "items": len(output_rows),
        "covered": len(output_rows) - len(missing),
        "missing": missing,
    }


def main() -> int:
    paper = write_paper_matrix()
    mindmap = write_mindmap_coverage()
    report_text = REPORT.read_text(encoding="utf-8")
    problem_rows = re.findall(r"^202[0-5] & [ABC] &", report_text, flags=re.MULTILINE)
    audit = {
        "paper_feature_matrix": paper,
        "mindmap_coverage": mindmap,
        "problem_rows_2020_2025_abc": len(problem_rows),
        "pass": (
            paper["rows"] == 59
            and paper["unique_papers"] == 59
            and paper["pages"] == 2892
            and mindmap["covered"] == mindmap["items"]
            and len(problem_rows) == 18
        ),
    }
    (WORK / "completion_evidence.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 0 if audit["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
