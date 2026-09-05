% 要求使用LaTeX2e的特定版本
\NeedsTeXFormat{LaTeX2e}
% 定义MathorCupmodeling文档类，版本为1.0
\ProvidesClass{MMCStyle}[2020/01/14 version 1.0]

% 加载ctexart文档类，设置纸张为A4纸，行距为1.25倍，默认字号为小4
\LoadClass[oneside,a4paper,UTF8,linespread=1.25,zihao=-4]{ctexart}

% 设置章节格式
\ctexset{
    % 设置章节标题格式
    section={
        format={\zihao{4}\heiti\centering},
        name={,、},
        aftername={\hspace{0pt}},
        number=\chinese{section},
    },
    % 设置子章节标题格式
    subsection={
        format={\zihao{-4}\heiti\raggedright},
        name={},
        aftername={\hspace{5bp}},
        number={\arabic{section}.\arabic{subsection}},
    },
    % 设置子子章节标题格式
    subsubsection={
        format={\zihao{-4}\heiti\raggedright},
        name={},
        aftername={\hspace{5bp}},
        number={\arabic{section}.\arabic{subsection}.\arabic{subsubsection}},
    },
    % 设置附录格式
    appendix={
        name={附录,：},
        number=\arabic{section},
    }
}
% \setCJKmainfont[Mapping=fullwidth-stop]{SimSun}
\setmainfont{Times New Roman}

\def\bianhao#1{\gdef\@bianhao{#1}}
\def\tihao#1{\gdef\@tihao{#1}}
\def\timu#1{\gdef\@timu{#1}}
\def\keyword#1{\gdef\@keyword{#1}}
\newlength{\mmcfirstpageheaderraise}
\setlength{\mmcfirstpageheaderraise}{1.8\baselineskip}
\renewenvironment{abstract}%
{%
\vspace*{-\mmcfirstpageheaderraise}
\hspace*{\fill}\begin{tabularx}{7.82cm}{|Y|Y|}
	\hline
	队伍编号 & \@bianhao \\
	\hline
	题号 & \@tihao \\
	\hline
\end{tabularx}\hspace*{\fill}\\
\phantom{1}\\
\rule{\textwidth}{1.5pt}\\
\phantom{1}\\
\phantom{1}\hfill{\zihao{4}\@timu}\hfill\phantom{1}\\
\phantom{1}\hfill{\label{zy}摘\quad{}要}\hfill\phantom{1}\pdfbookmark[1]{摘要}{zy}\par%
}{\\\phantom{1}\\关键词：\@keyword\thispagestyle{fancy}
\newpage\thispagestyle{fancy}
}


\renewcommand*{\textfraction}{0.05}
\renewcommand*{\topfraction}{0.9}
\renewcommand*{\bottomfraction}{0.8}
\renewcommand*{\floatpagefraction}{0.85}

\RequirePackage[top=2.5cm,bottom=2.5cm,left=2.5cm,right=2.5cm]{geometry}
\RequirePackage{fancyhdr,lastpage}
\pagestyle{fancy}
\fancyhf{}
\renewcommand\headrulewidth{0pt}
\fancyfoot[C]{第 \thepage{} 页~~共 \pageref{LastPage} 页}
\RequirePackage{titletoc}
\RequirePackage{titlesec}
\titlecontents{section}[0pt]{\addvspace{2pt}\filright}%
{\heiti\contentspush{\thecontentslabel\ }}%
{}{\titlerule*[8pt]{.}\contentspage}
% \AtBeginDocument{
% % ---------- 目录样式设置 ----------
% % 1. section 级别：粗体，较大字距，引导点使用居中圆点，间距舒适
% \titlecontents{section}
%     [2em]                       % 左缩进 2em
%     {\addvspace{0.8ex}\bfseries\large}  % 整体格式：粗体、大号，上方增加间距
%     {\contentslabel{1.5em}}     % 带编号时，编号占 1.5em 宽度
%     {}                          % 无编号时，无额外标签
%     {\titlerule*[1.2pc]{$\cdot$}\contentspage}  % 引导点：居中点，间距 0.8pc，后跟页码

% % 2. subsection 级别：正常字体，稍小缩进，引导点使用细点（默认点），页码正常
% \titlecontents{subsection}
%     [3.8em]                     % 左缩进 = 2em + 1.8em
%     {\addvspace{0.4ex}\normalsize}
%     {\contentslabel{2em}}
%     {}
%     {\titlerule*[0.8pc]{.}\contentspage}

% % 3. subsubsection 级别：更小缩进，斜体或浅灰色（可选），引导点更密
% \titlecontents{subsubsection}
%     [5.5em]                     % 左缩进 = 3.8em + 1.7em
%     {\addvspace{0.2ex}\small\itshape}
%     {\contentslabel{2.5em}}
%     {}
%     {\titlerule*[0.5pc]{.}\contentspage}

% % 4. 可选：调整“目录”标题的样式（使用 titlesec）
% \titleformat{\section}
%     {\centering\zihao{3}\bfseries}{\thesection}{3em}{}
% % 如果希望目录标题单独设置，可以：
% \titleformat{name=\contentsname}
%     {\centering\zihao{3}\bfseries}{}{0em}{}
% }

\RequirePackage{amsmath}
\RequirePackage{amsfonts} 
\RequirePackage{amsthm}
\RequirePackage{amssymb}
\let\lvert\relax\let\rvert\relax\let\lVert\relax\let\rVert\relax
\RequirePackage{newtxmath}
\RequirePackage{esint}
\DeclareSymbolFont{CMlargesymbols}{OMX}{cmex}{m}{n}
\let\sum\relax\let\prod\relax
\DeclareMathSymbol{\sum}{\mathop}{CMlargesymbols}{"50}
\DeclareMathSymbol{\prod}{\mathop}{CMlargesymbols}{"51}

% 扩展的数学宏包, 可根据自己的需求载入
% \RequirePackage{bm} %用\bm{}命令生成伪粗体
% \RequirePackage{upgreek}%用\uppi 调用正体的圆周率
% \RequirePackage{mathrsfs}%\mathscr{}调用傅里叶变换,拉普拉斯变换的符号

\RequirePackage{physics,siunitx}

% % 设置虚数,自然底数,微分符号
% \def\ee{\mathrm{e}}
% \def\ii{\mathrm{i}}
% \def\leq{\leqslant}
% \def\geq{\geqslant}

% 载入表格宏包和插图宏包
\RequirePackage{booktabs,tabularx,multirow,longtable,makecell,array}
\newcolumntype{Y}{>{\centering\arraybackslash}X}
\RequirePackage{graphicx}
% 设置图片路径
\graphicspath{{figures/}}
\RequirePackage{caption}
\RequirePackage[section]{placeins}
% 扩展的表格宏包和插图宏包
% \RequirePackage{subfig}
% \RequirePackage{longtable}

\captionsetup{format=hang}% 设置浮动体标题悬挂缩进
\DeclareCaptionLabelSeparator*{sspace}{\ \ }
\captionsetup[figure]{labelsep=sspace}
\captionsetup[table]{labelsep=sspace}
\DeclareCaptionFont{heiti}{\heiti}
\DeclareCaptionFont{5hao}{\zihao{5}}
\captionsetup{labelfont={heiti,5hao},textfont={heiti,5hao}}

% 载入颜色宏包
\RequirePackage{color,xcolor}

% 载入参考文献宏包，设置引用格式
\makeatletter
\AtEndPreamble{%
  \@ifpackageloaded{biblatex}{}{%
    \RequirePackage{natbib}%
    \setcitestyle{square,super}%
  }%
}
\makeatother

% 载入代码宏包
\RequirePackage{listings}
% 设置代码的默认样式
\lstset{
	frame=none,% 取消边框
	breaklines=true,% 允许自动断行
	% breakatwhitespace=true,% 使用此命令仅允许在空格处自动断行
	showstringspaces=false,% 不显示字符串中的空格
	basicstyle=\small\ttfamily,% 设置代码基本样式
	flexiblecolumns=true,% 改善字母间距
	keywordstyle=\color{blue},% 设置关键词样式
	stringstyle=\color[rgb]{0.75,0,0.75},% 设置字符串样式
	commentstyle=\songti\color[rgb]{0,0.5,0},% 设置注释样式
	tabsize=4,% 设置制表符缩进
}

% 设置matlab代码环境
\lstnewenvironment{matlab}[1][]{
	\lstset{
		language=Matlab,
		% deletekeywords={disp},% 可在此行去除特定关键词的语法高亮		
		keywordstyle=\color{blue},% 设置关键词样式
		stringstyle=\color[rgb]{0.75,0,0.75},% 设置字符串样式
		commentstyle=\songti\color[rgb]{0,0.5,0},% 设置注释样式
		#1
	}
}{}

% 设置python代码环境
\lstnewenvironment{python}[1][]{
	\lstset{
		language=Python,
		keywordstyle=\color[RGB]{255,119,0},% 设置Keywords样式
		morekeywords={as},% 将特定单词加入Kewords中
		deletekeywords={print},%从 keywords中去除特定单词
		keywordstyle=[2]\color[RGB]{144,0,144},% 设置Builtins样式
		morekeywords=[2]{print},% 将特定单词加入Builtins中
		stringstyle=\color[RGB]{0,170,0},% 设置字符串样式
		commentstyle=\songti\color[RGB]{221,0,0},% 设置注释样式	
		#1
	}
}{}



% 载入超链接宏包
\RequirePackage{hyperref}
\hypersetup{breaklinks,colorlinks}% 允许超链接断行,取消超链接的边框,使链接文字带颜色
\hypersetup{hidelinks,bookmarksnumbered=true,bookmarksopen=true,pdfstartview=Fit}% 取消超链接的颜色，书签目录增加编号

\RequirePackage{cleveref}% 载入自动引用宏包
\crefname{figure}{图}{图}
\crefname{table}{表}{表}
\crefname{equation}{式}{式}
\renewcommand{\eqref}[1]{\labelcref{#1}~\namecref{#1}}
