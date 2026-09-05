#!/usr/bin/env python3
"""Re-apply the manuscript expansion to main.tex after an external overwrite.

An external process replaced main.tex with an unrelated training template at
2026-09-05 21:53:37, twenty minutes after the last good compile. This script
rebuilds the expansion from the committed 581-line base by anchored insertion,
so the same accident costs one command instead of a rewrite. Every entry asserts
its anchor: a silent no-op is impossible.
"""
from __future__ import annotations

from pathlib import Path

MAIN = Path(__file__).resolve().parent / "main.tex"

PROPS = r"""
附件 1 给出的物性列在表~\ref{tab:props}。最后一列是按 $a_i=\lambda_i/(\rho_i c_i)$ 换算的
热扩散系数，与附件 1 自带的预置列逐位一致，本文以它作为方程系数。表中第 II、IV 层的厚度
是允许区间而非定值，这两个区间就是问题二、三的决策变量取值范围。

\begin{table}[htbp]
  \centering
  \caption{附件 1 的四层物性与换算所得热扩散系数}
  \label{tab:props}
  \input{tables/tab-properties.tex}
\end{table}

值得先注意第 IV 层。它是空气层，密度只有 \SI{1.18}{kg/m^3}，因此在四层中同时具有最大的
热阻和最快的扩散：热阻大意味着它决定能挡住多少热量，扩散快意味着它几乎不延迟热量到达皮肤。
这两个性质在后面三问里反复起作用。
"""

RES = r"""按附件 2 的条件，$R=\SI{0.282105}{m^2.K/W}$。表~\ref{tab:res} 把它拆到每一层，同时给出
稳态温降与扩散时间尺度 $d_i^2/a_i$。

\begin{table}[htbp]
  \centering
  \caption{附件 2 条件下的逐层热阻、稳态温降与扩散时间尺度}
  \label{tab:res}
  \input{tables/tab-resistance.tex}
\end{table}

三件事从这张表读出来。第一，空气层占总热阻 \SI{63.3}{\percent}，单独承担
\SI{17.040}{\celsius} 温降，这解释了问题三中第 IV 层厚度为何能决定可行性。第二，
第 III 层热阻占 \SI{28.4}{\percent}，而第 II 层只占 \SI{5.7}{\percent}——第 II 层加厚
对隔热的边际贡献本来就小，这预示问题二的最优厚度会偏大。第三，四层的扩散时间尺度都在
\SI{200}{s} 以内，最长的第 II 层是 \SI{176.1}{s}；整叠的等效时间尺度取总厚与最小扩散
系数之比约为 \SI{1160}{s}，与附件 2 在第 \SI{21}{min} 进入准稳态相符。这个量级说明
三问的时间窗都长于系统的响应时间，但不等于可以用稳态代替瞬态——判据里的五分钟正好落在
响应尾段。
"""

FV = r"""把区间 $[0,L]$ 按层划分为格心控制体，第 $i$ 层分 $n_i$ 格、格宽 $h_i=d_i/n_i$。格数按层厚
分配，并令最薄的一层不少于 8 格，使 \SI{0.6}{mm} 的第 I 层与每个界面都能被分辨；本文实际
使用的总格数在 253 到 2027 之间。

离散不从式~\eqref{eq:pde} 直接差分，而从控制体的能量平衡出发。对第 $j$ 格在
$[t^n,t^{n+1}]$ 内积分式~\eqref{eq:pde}，并把左右两个面上的热流记为 $q_{j-1/2}$、
$q_{j+1/2}$，得
\begin{equation}
  \rho_j c_j h_j \frac{T_j^{n+1}-T_j^{n}}{\tau}
  = q_{j-1/2}-q_{j+1/2},
  \qquad
  q_{j+1/2}=-K_{j+1/2}\bigl(T_{j+1}-T_j\bigr).
  \label{eq:fv}
\end{equation}
这样写的好处是：无论 $\lambda$ 在界面处如何跳变，进入一格的热量与离开相邻一格的热量
用的是同一个 $q_{j+1/2}$，能量在离散层面自动守恒，不需要额外的界面方程。

界面导度 $K_{j+1/2}$ 由两个半格串联的热阻定出。从格心 $j$ 到界面的热阻是
$h_j/(2\lambda_j)$，从界面到格心 $j+1$ 是 $h_{j+1}/(2\lambda_{j+1})$，串联相加再取倒数：
\begin{equation}
  K_{j+1/2}=\left(\frac{h_j}{2\lambda_j}+\frac{h_{j+1}}{2\lambda_{j+1}}\right)^{-1}.
  \label{eq:harmonic}
\end{equation}
这正是式~\eqref{eq:interface} 的离散对应。若改用算术平均
$\tfrac12(\lambda_j+\lambda_{j+1})$，在第 III 层与第 IV 层界面处
$\lambda$ 相差 \num{1.6} 倍，界面热流会被系统性高估；本题空气层与织物层的导热系数
相差一个量级，这一选择不是精度上的微调。
"""

MATRIX = r"""两端按 Dirichlet 与式~\eqref{eq:robin} 的 Robin 形式并入对角。每一时间层是一个三对角系统，
按带状矩阵直接求解，无条件稳定，步长由需要的输出分辨率决定而不再由空气层决定。

把式~\eqref{eq:implicit} 写成矩阵形式便于说明两端如何并入。记
$\boldsymbol{T}^{n}=(T_1^n,\dots,T_N^n)^{\mathsf T}$，则
\begin{equation}
  \left(\mathrm{diag}\!\left(\frac{C_j}{\tau}\right)+\boldsymbol{A}\right)\boldsymbol{T}^{n+1}
  = \mathrm{diag}\!\left(\frac{C_j}{\tau}\right)\boldsymbol{T}^{n}+\boldsymbol{b},
  \label{eq:matrix}
\end{equation}
其中 $\boldsymbol{A}$ 是由各 $K_{j\pm1/2}$ 组成的三对角矩阵。外侧 Dirichlet 条件不引入
额外未知量：它以 $K_{1/2}=2\lambda_1/h_1$ 的形式加到 $\boldsymbol{A}$ 的首个对角元上，
同时把 $K_{1/2}T_{\mathrm{env}}$ 加进 $\boldsymbol{b}$ 的首项。皮肤侧的 Robin 条件同理，
只是导度取半格热阻与外部散热的串联
\begin{equation}
  K_{N+1/2}=\left(\frac{h_N}{2\lambda_4}+\frac{1}{h}\right)^{-1},
  \label{eq:robindisc}
\end{equation}
并把 $K_{N+1/2}T_{\mathrm{core}}$ 加进 $\boldsymbol{b}$ 的末项。$\boldsymbol{A}$ 的对角元
严格大于同行非对角元绝对值之和加边界导度，因此系数矩阵是不可约对角占优的，解存在且唯一，
数值上也不需要预处理。
"""

GRID = r"""残差直接暴露。

离散是否足够细需要当场验证，而不是留到检验一节。表~\ref{tab:grid} 给出 12 组网格与步长
组合下的终点温度。

\begin{table}[htbp]
  \centering
  \caption{网格与时间步长组合下的终点温度（附件 2 条件）}
  \label{tab:grid}
  \input{tables/tab-grid.tex}
\end{table}

最薄层格数由 10 加到 80、步长由 \SI{4}{s} 缩到 \SI{1}{s}，总格数从 253 变到 2027，
终点温度的相互偏差始终在 \SI{3e-9}{\celsius} 以内。偏差这么小有具体原因：
式~\eqref{eq:harmonic} 的调和平均使界面热流在离散层面精确守恒，界面不再是误差来源；
后向 Euler 又无条件稳定，步长只影响时间分辨率而不影响终态。因此后文一律用最薄层
20 格、步长 \SI{2}{s} 做厚度搜索，用 \SI{1}{s} 做与附件 2 的逐秒对比。
"""

CAL = r"""两条给出接近的值，说明式~\eqref{eq:robin} 的结构没有被拟合掩盖。
下文一律使用最小二乘值。

\begin{table}[htbp]
  \centering
  \caption{散热系数的两条标定路线}
  \label{tab:cal}
  \input{tables/tab-calibration.tex}
\end{table}

表~\ref{tab:cal} 把两条路线并列。需要强调它们的独立性：闭式路线只用一个数（末值
\SI{48.08}{\celsius}），把式~\eqref{eq:steady} 反解，完全不涉及升温过程；最小二乘路线
用全部 5401 个点，但不单独约束末值。若边界形式选错——例如把皮肤侧写成绝热或写成第二类
边界——最小二乘仍会找出一个使曲线尽量贴合的系数，而闭式路线给出的值会与它明显分离。
两者相差 \SI{1.88}{\percent} 才使“结构选对了”这一判断有依据。
"""

HIST = r"""  \caption{皮肤外侧温度：模型与附件 2 实测对比及残差}
  \label{fig:q1fit}
\end{figure}

表~\ref{tab:hist} 取几个时刻列出模型给出的皮肤外侧温度，图~\ref{fig:q1prof} 则给出同一次
运行的层内温度剖面。剖面图上竖线是层界。第 \SI{1}{min} 时热量还集中在前两层，
第 \SI{5}{min} 时第 III 层开始升温，第 \SI{21}{min} 与第 \SI{90}{min} 的两条曲线几乎重合，
说明系统此时已进入准稳态。剖面在空气层内的陡降对应表~\ref{tab:res} 里那
\SI{17.040}{\celsius}，这是全叠温降的主要来源。

\begin{table}[htbp]
  \centering
  \caption{模型给出的皮肤外侧温度演化（附件 2 条件）}
  \label{tab:hist}
  \input{tables/tab-history.tex}
\end{table}

\begin{figure}[htbp]
  \centering
  \includegraphics[width=0.84\textwidth]{figures/fig-q1-profile.pdf}
  \caption{四层内的温度剖面随时间演化，竖线为层界}
  \label{fig:q1prof}
\end{figure}

本问还剩一处边界要交代。式~\eqref{eq:robin} 的散热系数只由 \SI{75}{\celsius} 这一次实验
定出，本问不涉及外推，因此它在本问是标定量而非假设；但问题二、三要在 \SI{65}{\celsius} 与
\SI{80}{\celsius} 下沿用同一个值，那时它就变成一个未经验证的外推。另外假设三把第 I 层外
表面温度直接取为环境温度，这在升温初段偏强，其代价由下节的分段残差给出，本文不作修正，
也因此不宣称模型在最初十分钟内可用。
"""

FRONT_TAB_OLD = r"""  \label{tab:front}
  \begin{tabular}{cccccccc}
    \toprule
    $d_4$/\si{mm} & 3.8 & 4.2 & 4.6 & 5.0 & 5.4 & 6.0 & 6.4 \\
    \midrule
    $d_2^{*}$/\si{mm} & 24.988 & 24.375 & 23.773 & 23.177 & 22.599 & 21.747 & 21.188 \\
    峰值/\si{\celsius} & 45.046 & 45.001 & 44.958 & 44.918 & 44.876 & 44.815 & 44.775 \\
    \bottomrule
  \end{tabular}
\end{table}
"""

FRONT_TAB_NEW = r"""  \label{tab:front}
  \input{tables/tab-front.tex}
\end{table}
"""

FRONT_PROSE = r"""仍低于 \SI{47}{\celsius} 上限——与问题二一样，紧的是五分钟预算。

图~\ref{fig:q3front} 把整张表画出来。左侧阴影区是第 IV 层薄于可行性边界时的不可行带，
右侧曲线近似为直线，斜率约 $-1.5$：第 IV 层每增厚 \SI{1}{mm}，第 II 层可减薄约
\SI{1.5}{mm}。这个交换率不是题面给的，而是本模型算出来的，它正是把双目标收缩成单目标时
本应先取得的信息。

\begin{figure}[htbp]
  \centering
  \includegraphics[width=0.84\textwidth]{figures/fig-q3-front.pdf}
  \caption{问题三前沿与不可行带}
  \label{fig:q3front}
\end{figure}

两点需要说清。第一，前沿的斜率来自热阻关系而非拟合：由表~\ref{tab:res}，
空气层的 $\lambda_4=\SI{0.028}{W/(m.K)}$ 远小于第 II 层的 $\lambda_2=\SI{0.37}{W/(m.K)}$，
单位厚度的热阻之比约为 $0.37/0.028\approx13$，因此在等热阻意义下第 IV 层增厚 \SI{1}{mm}
可以换掉第 II 层十几毫米；实际交换率只有 $1.5$，是因为可行性由越阈时刻而非总热阻决定，
瞬态过程削弱了这一比值。第二，可行性边界与题面示例的量级不符：题面在问题一中给出的
第 IV 层厚度是 \SI{5}{mm}，而问题三要求 \SI{80}{\celsius} 下工作三十分钟，
此时第 IV 层不得薄于约 \SI{3.8}{mm}，余量并不宽裕。
"""

SCAN = r"""前沿单调：第 IV 层每增厚 \SI{1}{mm}，第 II 层可减薄约 \SI{1.5}{mm}。若以总厚最小为附加偏好，
则取 $d_4=\SI{6.4}{mm}$、$d_2=\SI{21.188}{mm}$，总厚 \SI{27.588}{mm}；此时 $d_4$ 位于
附件 1 给的上界。注意前沿上每点的峰值都在 \SI{44.8}{\celsius} 到 \SI{45.0}{\celsius} 之间，
仍低于 \SI{47}{\celsius} 上限——与问题二一样，紧的是五分钟预算。

前沿的求法写清如下，它只是把问题二的一维搜索放进一层外循环。对给定的 $d_4$，
可行性判断仍由式~\eqref{eq:crit} 给出；由于固定 $d_4$ 后峰值对 $d_2$ 仍单调不增
（机理与问题二相同：加厚织物层只增加串联热阻），内层用同一段二分。外层按
\SI{0.4}{mm} 步长扫描 $d_4\in[0.6,6.4]$，共 15 个点。外层不需要二分：可行性边界
只需定位到扫描分辨率，而边界附近的 $d_2^{*}$ 已经贴近上界 \SI{25}{mm}，
再细分不会改变结论的性质。整个过程调用仿真器约 $15\times12$ 次，
在最薄层 20 格、步长 \SI{4}{s} 下可在数分钟内完成。
"""

VERDICT = r"""\SI{48.08}{\celsius} 与本文式~\eqref{eq:steady} 的结果逐项一致，其稳态代数部分是正确的。

表~\ref{tab:verdict} 把三组对照汇总。三行的失效方式并不相同：问题二那一行没有越过温度上限，
败在越阈时长——\SI{3256}{s} 是 \SI{300}{s} 预算的十倍以上；问题三两行则直接越过
\SI{47}{\celsius} 硬上限，分别高出 \SI{1.97}{\celsius} 与 \SI{1.01}{\celsius}。
两种失效对应两条不同的约束，说明不是某一条判据写法上的分歧，而是模型缺少时间维之后
两条约束都失去了控制。

\begin{table}[htbp]
  \centering
  \caption{参考论文报告厚度代入本文模型后的判定}
  \label{tab:verdict}
  \input{tables/tab-verdict.tex}
\end{table}

还有一处跨问接口需要明确写出，否则读者无法判断三问的结果能否互相引用。
表~\ref{tab:iface} 列出每问冻结了什么、新开放了什么、以及输出进入了哪里。
三问共享同一个仿真器与同一个散热系数，因此问题二、三的厚度结论继承问题一的全部标定
不确定性；反过来，问题一的验证结论不因问题二、三换了环境温度而自动成立。

\begin{table}[htbp]
  \centering
  \caption{三问之间的冻结量、新开放量与输出接口}
  \label{tab:iface}
  \begin{tabular}{cllc}
    \toprule
    问 & 冻结 & 新开放 & 输出 \\
    \midrule
    一 & 附件 1 物性、附件 2 实测 & 散热系数 $h$ & $h$、温度分布 Excel \\
    二 & 仿真器、$h$、$d_4=\SI{5.5}{mm}$ & $d_2$ & $d_2^{*}$、越阈时刻 \\
    三 & 仿真器、$h$ & $d_2$、$d_4$ & 前沿 $d_2^{*}(d_4)$、可行性边界 \\
    \bottomrule
  \end{tabular}
\end{table}
"""

RESID = r"""由于问题二、三的判据由平台附近的越阈时刻决定，该偏差不改变本文结论的方向，
但它是最先应该被改进的地方。

表~\ref{tab:resid} 把残差按时段拆开，可以看清偏差的结构而不只是一个总量。

\begin{table}[htbp]
  \centering
  \caption{模型与附件 2 的残差按时段分解}
  \label{tab:resid}
  \input{tables/tab-residual.tex}
\end{table}

三点值得读出来。第一，偏差不是随机噪声：前十分钟的平均偏差为
$+\SI{1.1767}{\celsius}$，符号一致，说明模型系统性地升温过快，这与“外表面瞬间达到
环境温度”的假设方向吻合。第二，进入准稳态后偏差迅速消失，第 \SI{21}{min} 之后各段
残差均方根都在 \SI{0.25}{\celsius} 以内，最后三十分钟只有 \SI{0.1453}{\celsius}；
这说明稳态部分的热阻链和散热系数是可靠的。第三，最大绝对偏差
\SI{1.7972}{\celsius} 出现在前十分钟内，而不在末段，因此它不影响以平台为判据的结论。

至此四层验证的对象、证据与结论可以并列写出：内部正确性以解析稳态解为参照，
离散无关性以 12 组网格步长组合为证据，量纲与参数以附件 1 的预置列为对账基准，
预测能力以附件 2 的分段残差为证据。四层各自针对一个不同的主张，
其中没有任何一层能替代另一层——例如离散无关性再好也不说明散热系数标定正确，
残差再小也不说明模型能外推到别的环境温度。
"""

SENS_TAB_OLD = r"""  \caption{问题二最优厚度对散热系数的敏感性}
  \label{tab:sens}
  \begin{tabular}{cccccccc}
    \toprule
    $h$ 相对偏移 & $-20\%$ & $-10\%$ & $-5\%$ & $-2\%$ & $+2\%$ & $+5\%$ & $+20\%$ \\
    \midrule
    $h$/\si{W/(m^2.K)} & 7.0192 & 7.8965 & 8.3352 & 8.5985 & 8.9494 & 9.2126 & 10.5287 \\
    $d_2^{*}$/\si{mm} & 整区间不可行 & 22.47 & 20.52 & 19.19 & 17.04 & 14.90 & 下界即可行 \\
    \bottomrule
  \end{tabular}
\end{table}
"""

SENS_TAB_NEW = r"""  \caption{问题二最优厚度对散热系数的敏感性，并列出对应的平台温度}
  \label{tab:sens}
  \input{tables/tab-sensitivity.tex}
\end{table}
"""

SLOPE = r"""在近乎水平的曲线上，平台移动零点几度就把越阈时刻推移数分钟，进而要求厚度大幅改变。

表~\ref{tab:slope} 给出最优点处皮肤温度曲线的逐段斜率。第 \SI{5}{min} 时曲线还在以
每分钟半度以上的速度上升，到第 \SI{55}{min} 只剩 \SI{0.0112}{\celsius\per\minute}，
相差近两个量级。约束要求的穿越时刻恰好落在最平的那一段，这是病态性的直接来源：
若阈值定在升温初段（例如要求不得在第 \SI{5}{min} 前越过某温度），同样的参数扰动
只会引起很小的厚度变化。

\begin{table}[htbp]
  \centering
  \caption{最优点处皮肤外侧温度的逐段斜率（\SI{65}{\celsius}，$d_2=\SI{18.16}{mm}$）}
  \label{tab:slope}
  \input{tables/tab-slope.tex}
\end{table}

表~\ref{tab:sens} 的第三、四列把这件事说得更直接：$h$ 每变动 \SI{2}{\percent}，
平台温度改变约 \SI{0.11}{\celsius}，而平台与阈值之差本身只有 \SI{0.1425}{\celsius}。
也就是说，标定精度与判据余量是同一量级——这不是模型不够精细，
而是这道约束在这组条件下本身没有留出可辨识的余量。
"""

SUMMARY = r"""界面导度取调和平均使热流连续在离散层面精确成立，这是终点温度对网格几乎不敏感的原因。

表~\ref{tab:sum} 汇总三问的条件、结论与紧约束。三问的紧约束都是五分钟预算，
这本身是一个可以核对的结论：它意味着若把题面的 \SI{47}{\celsius} 上限改成
\SI{46}{\celsius} 或 \SI{48}{\celsius}，本文的厚度结果都不会改变；
真正敏感的是 \SI{44}{\celsius} 这条阈值和五分钟这个预算。

\begin{table}[htbp]
  \centering
  \caption{三问结论汇总}
  \label{tab:sum}
  \input{tables/tab-summary.tex}
\end{table}
"""

# (anchor, replacement) -- anchor 必须唯一命中，替换即插入
EDITS: list[tuple[str, str]] = [
    (r"""    $T_{\mathrm{w}}$ & 工作时长，问题二为 \num{3600}、问题三为 \num{1800} & \si{s} \\
    \bottomrule
  \end{tabular}
\end{table}
""",
     r"""    $T_{\mathrm{w}}$ & 工作时长，问题二为 \num{3600}、问题三为 \num{1800} & \si{s} \\
    \bottomrule
  \end{tabular}
\end{table}
""" + PROPS),
    (r"""按附件 2 的条件，$R=\SI{0.282105}{m^2.K/W}$。四层的稳态温降依次为
\num{0.698}、\num{1.547}、\num{7.634}、\SI{17.040}{\celsius}：空气层单独承担了总温降的六成，
这也解释了问题三中第 IV 层厚度为何能决定可行性。
""", RES),
    (r"""把区间 $[0,L]$ 按层划分为格心控制体，第 $i$ 层分 $n_i$ 格、格宽 $h_i=d_i/n_i$。格数按层厚
分配，并令最薄的一层不少于 8 格，使 \SI{0.6}{mm} 的第 I 层与每个界面都能被分辨；本文实际
使用的总格数在 253 到 2027 之间。相邻两格之间的界面导度取两侧半格热阻的调和平均
\begin{equation}
  K_{j+1/2}=\left(\frac{h_j}{2\lambda_j}+\frac{h_{j+1}}{2\lambda_{j+1}}\right)^{-1}.
  \label{eq:harmonic}
\end{equation}
这一步是式~\eqref{eq:interface} 的离散对应：无论界面两侧 $\lambda$ 差多少倍，
通过界面的热流在离散层面都严格相等，不需要额外的界面方程。
""", FV),
    (r"""两端按 Dirichlet 与式~\eqref{eq:robin} 的 Robin 形式并入对角。每一时间层是一个三对角系统，
按带状矩阵直接求解，无条件稳定，步长由需要的输出分辨率决定而不再由空气层决定。
""", MATRIX),
    ("残差直接暴露。\n", GRID),
    (r"""两条给出接近的值，说明式~\eqref{eq:robin} 的结构没有被拟合掩盖。
下文一律使用最小二乘值。
""", CAL),
    (r"""  \caption{皮肤外侧温度：模型与附件 2 实测对比及残差}
  \label{fig:q1fit}
\end{figure}
""", HIST),
    (FRONT_TAB_OLD, FRONT_TAB_NEW),
    ("仍低于 \\SI{47}{\\celsius} 上限——与问题二一样，紧的是五分钟预算。\n", FRONT_PROSE),
    (r"""前沿单调：第 IV 层每增厚 \SI{1}{mm}，第 II 层可减薄约 \SI{1.5}{mm}。若以总厚最小为附加偏好，
则取 $d_4=\SI{6.4}{mm}$、$d_2=\SI{21.188}{mm}$，总厚 \SI{27.588}{mm}；此时 $d_4$ 位于
附件 1 给的上界。注意前沿上每点的峰值都在 \SI{44.8}{\celsius} 到 \SI{45.0}{\celsius} 之间，
仍低于 \SI{47}{\celsius} 上限——与问题二一样，紧的是五分钟预算。
""", SCAN),
    (r"""\SI{48.08}{\celsius} 与本文式~\eqref{eq:steady} 的结果逐项一致，其稳态代数部分是正确的。
""", VERDICT),
    (r"""由于问题二、三的判据由平台附近的越阈时刻决定，该偏差不改变本文结论的方向，
但它是最先应该被改进的地方。
""", RESID),
    (SENS_TAB_OLD, SENS_TAB_NEW),
    (r"""在近乎水平的曲线上，平台移动零点几度就把越阈时刻推移数分钟，进而要求厚度大幅改变。
""", SLOPE),
    (r"""界面导度取调和平均使热流连续在离散层面精确成立，这是终点温度对网格几乎不敏感的原因。
""", SUMMARY),
]


def main() -> int:
    text = MAIN.read_text(encoding="utf-8")
    for index, (anchor, replacement) in enumerate(EDITS, start=1):
        count = text.count(anchor)
        if count != 1:
            raise SystemExit(f"edit {index}: anchor matched {count} times, expected 1\n"
                             f"anchor head: {anchor[:60]!r}")
        text = text.replace(anchor, replacement, 1)
    MAIN.write_text(text, encoding="utf-8")
    print(f"applied {len(EDITS)} edits; main.tex now {len(text.splitlines())} lines")
    for name in ("tab-properties", "tab-resistance", "tab-grid", "tab-history", "tab-front",
                 "tab-sensitivity", "tab-slope", "tab-verdict", "tab-residual",
                 "tab-calibration", "tab-summary"):
        assert f"tables/{name}.tex" in text, name
    print("all 11 generated tables referenced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
