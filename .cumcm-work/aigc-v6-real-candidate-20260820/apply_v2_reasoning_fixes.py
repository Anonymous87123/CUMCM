import json
from pathlib import Path


ROOT = Path(r"F:\CUMCM\.cumcm-work\aigc-v6-real-candidate-20260820\rewrites-v2")


def replace_once(unit_id: str, line_no: int, old: str, new: str) -> None:
    path = ROOT / f"{unit_id}.json"
    bundle = json.loads(path.read_text(encoding="utf-8"))
    lines = bundle["masked_text"].splitlines(keepends=True)
    line = lines[line_no - 1]
    if line.count(old) != 1:
        raise RuntimeError(f"{unit_id}:{line_no}: expected one occurrence of {old!r}")
    lines[line_no - 1] = line.replace(old, new)
    bundle["masked_text"] = "".join(lines)
    path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


replace_once(
    "U-e276c4b22163",
    7,
    "以综合生态状态指数调节中层猎物承载力，并设置",
    "以综合生态状态指数调节中层猎物承载力，建立珍稀物种种群响应模型，并设置",
)
replace_once(
    "U-e276c4b22163",
    9,
    "问题三、四共用Hastings-Powell三级食物链。",
    "问题三、四采用统一的Hastings-Powell三级食物链模型。",
)
replace_once(
    "U-e276c4b22163",
    11,
    "熵权与CRITIC权重取平均后得到",
    "采用熵权-CRITIC组合赋权模型，取两组权重平均后得到",
)
replace_once(
    "U-c530201b41a9",
    2,
    "若把四大家鱼合并为单一消费者，并把水草、浮游植物、浮游动物和底栖饵料压成一个资源总量，2025年的1.8倍总量仍能匹配",
    "2025年的1.8倍总量是一项观测事实。若把四大家鱼合并为单一消费者，并把水草、浮游植物、浮游动物和底栖饵料压成一个资源总量，这一总量仍能匹配",
)
replace_once(
    "U-c530201b41a9",
    2,
    "因此，食性配对必须留在模型中，用各自的资源轨迹判断哪一层较早承压。",
    "因此，食性配对必须留在模型中，相应的结果解释落到各自资源轨迹和承压层级。",
)
replace_once(
    "U-769818cb13c6",
    2,
    "通道约束同时压低两类物种，放流变化主要落在长江鲟上。",
    "这里改变的是通道损失参数和放流控制量；通道约束同时压低两类物种，放流变化主要落在长江鲟上。",
)
replace_once(
    "U-8f28215ff44b",
    4,
    "问题五中，污染情景的部分食源过程量短时上升",
    "问题五已经说明，污染情景的部分食源过程指标短时上升",
)
replace_once(
    "U-0801ec99dfa8",
    38,
    "组合权重经2000次",
    "组合权重经2000 次",
)
print("reasoning and unit-sequence fixes applied")
