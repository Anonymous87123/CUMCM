import json
from pathlib import Path


root = Path(r"F:\CUMCM\.cumcm-work\aigc-v6-real-candidate-20260820\rewrites-v2")


def replace_once(unit_id: str, line_no: int, old: str, new: str) -> None:
    path = root / f"{unit_id}.json"
    bundle = json.loads(path.read_text(encoding="utf-8"))
    lines = bundle["masked_text"].splitlines(keepends=True)
    if lines[line_no - 1].count(old) != 1:
        raise RuntimeError(f"{unit_id}:{line_no}: expected {old!r}")
    lines[line_no - 1] = lines[line_no - 1].replace(old, new)
    bundle["masked_text"] = "".join(lines)
    path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


replace_once(
    "U-e276c4b22163",
    13,
    "资源量回升并不等同于系统整体健康改善",
    "资源量回升不会自然转化为系统整体健康改善",
)
replace_once(
    "U-3644a855b083",
    4,
    "五问并不彼此独立。",
    "五问彼此关联。",
)
replace_once(
    "U-3644a855b083",
    4,
    "问题四用初值敏感性检验其长期行为",
    "问题四判断复杂轨道会不会随初值变化",
)
replace_once(
    "U-b1bac710ec42",
    4,
    "部分水域鱼类数量增长过快，水生植物和浮游动物受到过度摄食，水体浑浊、底栖植被减少",
    "部分水域鱼类数量增长过快，对水生植物和浮游动物的过度摄食导致水体浑浊、底栖植被减少",
)
replace_once(
    "U-c530201b41a9",
    2,
    "相应的结果解释落到各自资源轨迹和承压层级",
    "每类鱼的结果解释分别落到对应资源轨迹及其承压层级",
)
replace_once(
    "U-769818cb13c6",
    2,
    "这里改变的是通道损失参数和放流控制量；通道约束同时压低两类物种",
    "这里改变的是通道损失参数和放流控制量；放流项位于长江鲟方程，通道损失同时进入两类物种方程。通道约束同时压低两类物种",
)
replace_once(
    "U-706e53781d8d",
    2,
    "在总积分时长为90时",
    "在总积分时长固定为90的前提下",
)
print("release-level reasoning and semantic-marker fixes applied")
