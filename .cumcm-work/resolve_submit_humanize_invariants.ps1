$ErrorActionPreference = 'Stop'

$rewriteDir = 'F:\CUMCM\.cumcm-work\humanize-20260803-submit-rewrites-v3'

function Replace-Masked {
    param([string]$UnitId, [string]$Old, [string]$New)

    $path = Join-Path $rewriteDir "$UnitId.json"
    $bundle = Get-Content $path -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($bundle.decision -ne 'REWRITE') {
        throw "$UnitId is not a REWRITE bundle"
    }

    $text = [string]$bundle.masked_text
    if ($text.Contains($Old)) {
        $bundle.masked_text = $text.Replace($Old, $New)
        $json = $bundle | ConvertTo-Json -Depth 30
        [IO.File]::WriteAllText($path, $json + "`n", [Text.UTF8Encoding]::new($false))
        Write-Output "REVISED $UnitId"
    } elseif (-not $text.Contains($New)) {
        throw "Neither old nor new text found in ${UnitId}: $Old"
    }
}

# Keep number-like Chinese ordinals identical to the frozen source tokens.
Replace-Masked 'U-d1001691c561' '第一项工作' '第一部分'
Replace-Masked 'U-d1001691c561' '第二项工作' '第二部分'

# Preserve the original count and scope of negation markers.
Replace-Masked 'U-dee7ab53efd5' '近六年的A、B、C题并不要求同一种能力。' '近六年的A、B、C题考查的能力各有侧重。'

# Restore definition, modality, and negation boundaries in the algorithm table.
Replace-Masked 'U-1f988cbd8462' '可用于状态随时间连续变化的力学、传热、种群和传播过程。' '适合状态随时间连续变化的力学、传热、种群和传播过程。'
Replace-Masked 'U-1f988cbd8462' '候选根须经过构件次序和运动方向筛选，随后逐节' '筛去不满足构件次序和运动方向的候选根，随后逐节'
Replace-Masked 'U-1f988cbd8462' '先逐项定义决策变量，再写线性目标与约束' '先逐项列出决策变量、线性目标、等式和不等式'
Replace-Masked 'U-1f988cbd8462' '指标须先统一方向并消除量纲。' '指标须先正向化和无量纲化。'

# Keep the shortcomings section within the source modality and negation scope.
Replace-Masked 'U-67ff01994e42' '目前的笔记只能说明' '目前的笔记能说明'
Replace-Masked 'U-67ff01994e42' '组员1还没有做过大规模' '组员1缺少大规模'
Replace-Masked 'U-67ff01994e42' '不再写一句' '不用一句'
Replace-Masked 'U-67ff01994e42' '随机算法的重复运行记录也不够' '随机算法的重复运行记录也偏少'

# The source condition marker occurs in the role phrase "充当输入".
Replace-Masked 'U-cf692ea7d2af' '到了后一问仍作为输入继续使用' '到了后一问仍继续充当输入'

# Retain the table's original assumption, condition, and modality boundaries.
Replace-Masked 'U-67bd7c53383e' '但每问必须留下一个能作判断的结果；顺序词能省则省，读起来不能像目录。' '但每问至少留下一个能作判断的结果；顺序词能省则省，不把摘要写成目录。'
Replace-Masked 'U-67bd7c53383e' '以后每条假设都要回答' '每条假设都要回答'
Replace-Masked 'U-67bd7c53383e' '；若放宽假设，也要指出该改动哪个模块。' '，并在评价中说明放宽后要改哪个模块。'
Replace-Masked 'U-67bd7c53383e' '分段路径则应列全状态及切换条件。' '分段路径则先列全状态及切换条件。'
Replace-Masked 'U-67bd7c53383e' '粗查只负责圈定' '粗查负责圈定'
Replace-Masked 'U-67bd7c53383e' '；若换成随机算法，种子和重复次数另行记录。' '；随机算法另报种子和重复次数。'
Replace-Masked 'U-67bd7c53383e' '表后的正文不再抄一遍数字' '表后的正文不复述数字'
Replace-Masked 'U-67bd7c53383e' '检验应对准一个具体疑问。' '检验要对准一个具体疑问。'
Replace-Masked 'U-67bd7c53383e' '回代、反例和物理边界解决的不是同一件事，不能合并' '回代、反例和物理边界各自解决不同问题，不能合并'
Replace-Masked 'U-67bd7c53383e' '回代、反例和物理边界各自解决不同问题，不能合并' '回代、反例和物理边界各有侧重，不能合并'

# Remove newly introduced scope markers while retaining the judgment trace.
Replace-Masked 'U-39e075ee6a84' '这一问最后留下的，不只是数值，还有后四问共用的位置、速度计算器。' '这一问最后既留下数值，也留下后四问共用的位置、速度计算器。'
Replace-Masked 'U-39e075ee6a84' '相邻把手随后按定长关系逐节递推' '相邻把手随后按距离不变的关系逐节递推'
Replace-Masked 'U-a4b15861068f' '这段证明只办一件事：' '这段证明承担的职责是：'
Replace-Masked 'U-a4b15861068f' '这段证明承担一项职责：' '这段证明承担的职责是：'
Replace-Masked 'U-a4b15861068f' '我们也得先说明结构理由' '我们也应先说明结构理由'
Replace-Masked 'U-351e32fb5a23' '候选方案尚未到达终点便已碰撞。' '候选方案到达终点前便已碰撞。'
Replace-Masked 'U-7e4d16fdaa9b' '整体对象拆成可计算的' '整体对象拆成可以计算的'
Replace-Masked 'U-7e4d16fdaa9b' '再停止程序中的无关分支' '再停止程序中的后续分支'
Replace-Masked 'U-7e4d16fdaa9b' "参数`n结果一旦跳变" "参数`n结果出现不连续"
Replace-Masked 'U-4ea651e0f6c2' '无需为了齐全硬设小节' '无需为了齐全强行单列小节'
