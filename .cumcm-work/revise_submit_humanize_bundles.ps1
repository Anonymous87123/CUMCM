$ErrorActionPreference = 'Stop'

$rewriteDir = 'F:\CUMCM\.cumcm-work\humanize-20260803-submit-rewrites-v2'

$noChangeReasons = @{
    'U-404f050b5eb9' = '本节是摘要写作的三项固定指引，原句分别承担内容、步骤与核对职责，改动会破坏quote清单边界。'
    'U-32f63fa253a0' = '本节是问题重述的三项固定指引，原句保持题意范围、写作步骤与核对职责的对应关系。'
    'U-881f5190709e' = '本节是问题分析的三项固定指引，原句区分难点识别、任务拆解与方法清单核对。'
    'U-794f247cbb79' = '本节是模型假设的三项固定指引，原句保留假设对象、计算后果与删除检验的职责边界。'
    'U-5171b9294d02' = '本节是符号说明的三项固定指引，原句维持收录范围、制表规则与一致性核对。'
    'U-04f39778ea23' = '本节是模型建立与求解的三项固定指引，原句完整覆盖输入、模型、算法步骤和交稿检查。'
    'U-88d6df6df629' = '本节是结果分析与检验的三项固定指引，原句区分数值报告、机制解释与证据核对。'
    'U-a1df26d79969' = '本节是灵敏度分析的三项固定指引，原句保持参数范围、扰动方法与结果核对的对应关系。'
    'U-c7df72c35d84' = '本节是模型评价与改进的三项固定指引，原句区分已有证据、适用边界与改进设想。'
    'U-d2dbe69570bb' = '本节是参考文献的三项固定指引，原句分别限定收录对象、引用位置与来源完整性。'
    'U-61cd6393a2c2' = '本节是附录的三项固定指引，原句保持文件入口、运行顺序与复现检查的职责关系。'
    'U-0308819b7e46' = '本节是提交前逐项检查清单，五个原句分别对应数值、模型、图表、检验和附录职责。'
    'U-ca4099b735aa' = '本节承担材料来源、阅读范围与复算边界说明，保留原句可避免改变资料责任范围。'
}

foreach ($unitId in $noChangeReasons.Keys) {
    $path = Join-Path $rewriteDir "$unitId.json"
    $bundle = Get-Content $path -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($bundle.decision -eq 'NO_CHANGE') { continue }
    $evidence = @($bundle.rewrite_intent.source_spans | ForEach-Object {
        [pscustomobject]@{
            id = $_.id
            start_line = $_.start_line
            end_line = $_.end_line
            sha256 = $_.sha256
        }
    })
    $bundle.decision = 'NO_CHANGE'
    $bundle.PSObject.Properties.Remove('masked_text')
    $bundle.PSObject.Properties.Remove('rewrite_intent')
    $bundle | Add-Member -NotePropertyName reason -NotePropertyValue $noChangeReasons[$unitId]
    $bundle | Add-Member -NotePropertyName evidence_spans -NotePropertyValue $evidence
    $bundle.keep_reasons = [pscustomobject]@{}
    $json = $bundle | ConvertTo-Json -Depth 30
    [IO.File]::WriteAllText($path, $json + "`n", [Text.UTF8Encoding]::new($false))
    Write-Output "NO_CHANGE $unitId"
}

function Replace-Masked {
    param([string]$UnitId, [string]$Old, [string]$New)
    $path = Join-Path $rewriteDir "$UnitId.json"
    $bundle = Get-Content $path -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($bundle.decision -ne 'REWRITE') { throw "$UnitId is not a REWRITE bundle" }
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

Replace-Masked 'U-d1001691c561' '这份报告是本队本轮训练的结算记录。我们依照' '这份报告是本队现阶段训练的结算记录。第一项工作依照'
Replace-Masked 'U-d1001691c561' "；随后选取`n2024" "；第二项工作选取`n2024"
Replace-Masked 'U-d1001691c561' '报告中所谓的' '文中的'
Replace-Masked 'U-d1001691c561' "，只表示目前能够复述原理、讲明步骤并列出代码逻辑；至于能否在`n比赛时限内独立复现，还要留给后续训练检验。" "指目前能够复述原理、讲明步骤并列出代码逻辑，不等同于已经`n完成全部算法的限时独立复现。"

Replace-Masked 'U-dee7ab53efd5' '我们没有按算法名称平均分配任务：' '分工按任务侧重展开：'
Replace-Masked 'U-dee7ab53efd5' '一项内容要记入本阶段成果，至少过三关：' '一项内容要记入本阶段成果，须满足三项要求：'
Replace-Masked 'U-dee7ab53efd5' "本轮先把`n十三个单元做实" "这次先完成`n十三个单元的原理与代码入口梳理"

Replace-Masked 'U-1f988cbd8462' '先把空间区域、初始条件和边界条件落到网格上' '空间区域、初始条件和边界条件先落到网格上'
Replace-Masked 'U-1f988cbd8462' '每个粒子都保留位置、速度、个体最好解和群体最好解；一次迭代包含' '每个粒子都保留位置、速度、个体最好解和群体最好解；迭代时包含'
Replace-Masked 'U-1f988cbd8462' '面对连续响应，先做线性、Ridge和Lasso基线；面对类别响应，先做Logistic基线。' '连续响应以线性、Ridge和Lasso为基线；类别响应以Logistic为基线。'

Replace-Masked 'U-58ced89d4882' '读A053时，我们也没有停在目录层面' '读A053时，笔记也没有停在目录层面'
Replace-Masked 'U-58ced89d4882' '这条顺序已经整理成一份可以逐项核对' '这条顺序已经整理成一份可逐项核对'

Replace-Masked 'U-67ff01994e42' '还不能证明谁都能在比赛时限内独立把代码跑通' '还不能证明三人都能在比赛时限内独立把代码跑通'
Replace-Masked 'U-67ff01994e42' '具体短板也很清楚：' '几处短板也逐渐暴露：'
Replace-Masked 'U-67ff01994e42' '下一阶段就用真题产物逐项验收' '下一阶段就用真题产物逐项核对'

Replace-Masked 'U-a6366210ec1d' '再补一个二维扩散FDM算例' '再完成一个二维扩散FDM算例'
Replace-Masked 'U-a6366210ec1d' '选一题完成36小时压缩训练，中途不更换结果口径。' '选一题完成36小时压缩训练，并统一结果口径。'
Replace-Masked 'U-a6366210ec1d' '按正式节奏做一次72小时完整训练' '按正式节奏开展72小时完整训练'

Replace-Masked 'U-cf692ea7d2af' '我们选它，并不是' '选择这篇论文，并不是'

Replace-Masked 'U-67bd7c53383e' '本队先把输入输出关系画清，再决定方法' '本队把输入输出关系画清后，再决定方法'
Replace-Masked 'U-67bd7c53383e' '分段路径则先把状态及切换条件列全' '分段路径则应列全状态及切换条件'

Replace-Masked 'U-39e075ee6a84' '不只是一组数值' '不只是数值'
Replace-Masked 'U-39e075ee6a84' '问题五沿用前面的运动模型，只把问题四所得的各把手速度改写成上限约束；粒子群在这里仅负责' '问题五不另建运动模型，只把问题四所得的各把手速度改写成上限约束；粒子群在这里只负责'

Replace-Masked 'U-49a4f84db22d' '我们看重的不是一句' '这里值得看重的不是一句'
Replace-Masked 'U-49a4f84db22d' '，而是正文的每一步都能在代码循环中找到。' '，而是正文的每一步都能同代码的一次循环对上。'

Replace-Masked 'U-a4b15861068f' '。有了这个结论，程序才可以只查与龙头有关的候选对象。' '。有了这个结论，程序才有理由只查与龙头有关的候选对象。'

Replace-Masked 'U-351e32fb5a23' "因此，时间推进不是可有可无的计算细节，而是可行性判断的一部分。" '读者可据此判断模型为何需要保留时间推进。'

Replace-Masked 'U-3852cd5e8be9' "速度在12--13秒突然抬升，论文没有先怪数值误差，而是比较同一时间内相邻节点走过的`n路程，再回到小圆弧附近的路径形状找原因。" "当速度在12--13秒突然抬升时，论文比较同一时间内相邻节点走过的`n路程，并沿小圆弧附近的路径形状查找原因。"
Replace-Masked 'U-3852cd5e8be9' '本队以后看到曲线尖峰，也先查状态切换和约束变化。' '本队以后看到曲线尖峰，也先查状态切换和约束变化，不急于归为数值噪声。'

Replace-Masked 'U-7e4d16fdaa9b' '从A053真正能学走的' 'A053可供借鉴的'
Replace-Masked 'U-7e4d16fdaa9b' "整体对象先拆成可计算的`n局部关系，数学解随后接受物理次序筛选；事件缩域先证明不会漏检，程序才停止无关分支" "整体对象拆成可计算的`n局部关系，再说明数学解怎样受物理次序筛选；先证明事件缩域不会漏检，再停止程序中的无关分支"
Replace-Masked 'U-7e4d16fdaa9b' '首次触发对象' '第一次触发对象'

Replace-Masked 'U-4ea651e0f6c2' '大标题不随意改名' '大标题名称保持固定'
Replace-Masked 'U-4ea651e0f6c2' '每个分问大体沿着' '每个分问沿着'
Replace-Masked 'U-4ea651e0f6c2' '推进；某个环节没有独立内容，就接在相邻段落里，不必为了齐全硬设小节。' '推进；没有独立结果的环节接在相邻段落里，无需为了齐全硬设小节。'
