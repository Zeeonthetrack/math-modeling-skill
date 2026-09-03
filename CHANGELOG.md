# 更新日志

当前公开版本从 `1.0.0` 重新建立版本基线。根目录 `VERSION` 是当前版本的唯一准据。

## 1.8.5 - 2026-09-02

### 合并两位开发者的 v1.80（绘图精美化融合 + 双体系合并）

本版本合并两个并行的 v1.80 分支：分支一完成"绘图双体系合并与导出自检闭环"（删除 plot_style.py / dsh-plugin、export_figure `tight=False` + `preflight`、figure_audit 跳过灰度图）；分支二完成"绘图精美化融合"（新增质感门禁、几何示意图工具箱、棒棒糖模板、cumcm 国赛预设）。合并后保留分支一的减法（删除旧体系）与分支二的加法（新工具），冲突处以"删除旧体系"为准。

新增工具与预设（源自分支二）：

- **`tools/figure/scripts/texture_audit.py`**：成图质感门禁。墨色浓度过淡 FAIL、暗部偏浅 WARN、主色超 10 种 WARN、绿色盲模拟（Machado 2009 矩阵）主色不可分 WARN、灰度明度差 INFO、疑似过小文字 INFO；同色异桶合并+桶内均值取色消除误报。
- **`tools/schematic/scripts/geometry_kit.py`**：题意沉浸几何示意图工具箱（路径 D）——斜二测 3D 坐标系、向量、角弧、分段着色轨迹、浅灰圆柱/球体+高亮扇区、判定区域、图上直标，PNG300+PDF+SVG 三件套。
- **`tools/figure/scripts/templates/make_lollipop_stem.py`**：第 12 个高阶模板——棒棒糖图（扰动/灵敏度/序列对比），CSV 契约 `seq,value[,label]`，`--baseline` 贯穿基准线。
- **`setup_style.py`**：新增 `journal='cumcm'` 国赛质感预设——五号字号阶梯（刻度 9pt / 轴标签 10.5pt / 标题 12pt）、深色 Okabe-Ito 色环、刻度朝外、去顶右边框、图宽 4.8in（A4 版心内不缩放）。

文档纪律（源自分支二，已适配合并后体系）：

- `tools/figure/SKILL.md`：第 5 步竞赛一律 `journal='cumcm'`；第 6 步新增绘制五条纪律（一图一脚本、单一样式源、数据禁硬编码、图上直标、色深字大）；第 9 步审计改三脚本序（check_figure → texture_audit → figure_audit）；核心原则字号条款升级。
- `tools/schematic/SKILL.md`：新增路径 D（题意沉浸几何示意图走 geometry_kit，与 draw.io 框图分工）。
- `tools/schematic/references/geometry-diagrams.md`（新增）：构图六纪律、QA 闭环、七项验收清单、TikZ 可选后端（无本地 TeX 一律回退 matplotlib）。
- `template_catalog.md`：11→12 个模板，登记 lollipop-stem 契约。
- 编程手 `SKILL.md` + `质检清单.md`：产物契约加路径 D、步骤 6/7 加 cumcm 与 texture_audit、质检清单加质感勾选项。

冲突解决（以删除旧体系为准）：分支二仍引用的 `plot_style.py` 复制指令已统一改回"从 `tools/figure/scripts/` 导入"；`style_constants.py` 的 SKILL_ROOT 检测维持指向 `style_constants.py` 自身（不回退到 plot_style.py）；`export_figure.py` 维持 `tight=False` + `preflight=True` + 灰度临时文件修复。

- **测试**：合并后含分支二新增的 `test_texture_audit.py`（5 条）+ `test_geometry_kit.py`（3 条）；`test_figure_templates.py` 登记 lollipop 模板；`test_figure_tools.py` 维持分支一重写版本。

## 1.8.0 - 2026-09-02

### 绘图双体系合并与导出自检闭环（tools/figure）

针对绘图功能"双体系重叠 / tight 默认值违反尺寸原则 / 同名 export_figure 行为不一致"三类冲突的统一修复：

- **删除旧绘图体系**：移除 `references/roles/编程手/scripts/plot_style.py`（494 行向后兼容层）及整个 `dsh-plugin/` 目录（用户确认不再使用）。绘图工具统一收敛到 `tools/figure/scripts/`。
- **`visual_qa.py`**：迁入 `audit_design()`（标题过长 / 图例超 5 项 / 逐点标记 / 柱状图未从零 / 2×2 矩阵冗余 colorbar），返回类型统一为 `[(severity, msg)]`，与 `audit_layout()` 一致。
- **`style_constants.py`**：SKILL_ROOT 检测改为检查自身路径（不再依赖已删除的 plot_style.py）。
- **`export_figure.py`**：`tight` 默认 `True → False`（保持 figsize 精确尺寸，避免插入论文后二次缩放）；新增 `preflight=True`——导出前自动运行 `audit_layout + audit_design`，FAIL 级问题直接 `raise` 阻断落盘，WARN 级打印提醒不阻断。
- **`figure_audit.py`**：跳过 `_grayscale` 派生预览图（PIL 转灰度丢 DPI 元数据、无 SVG 配对，属自检辅助产物，不作独立图审计）。
- **`check_figure.py`**：strict 模式未提供 `--width-in/--height-in` 时打印 INFO，提醒启用实际尺寸一致性检查。
- **文档同步**：编程手 `SKILL.md` / `工作流程.md` 改为从 `tools/figure/scripts/` 导入（`sys.path.insert` + `from setup_style/export_figure/visual_qa import ...`），不再复制 plot_style.py；`viz_pitfalls.md`、`tools/figure/SKILL.md` 更新 tight 与 preflight 语义。
- **测试**：重写 `tests/test_figure_tools.py` 适配新 API（返回 list、list[tuple] 断言、尺寸断言对应 tight=False 精确 figsize）。绘图相关 27/27 通过。
- **已知**：全套 132 测试中 3 个失败（test_equations / test_latex_paper）为 Windows 临时目录短路径（`HARRY_~1`）与长路径比较的既有平台环境问题，与本次绘图修复无关。

## 1.7.5 - 2026-09-02

### 绘图工具链健壮性修复（tools/figure）

以实际运行与静态审计发现的 11 类 bug 为依据，统一修复 `tools/figure` 的 11 个模板脚本与 4 个核心工具脚本：

- **MPLCONFIGDIR 临时目录泄漏**：11 个模板将 `os.environ.setdefault("MPLCONFIGDIR", tempfile.mkdtemp(...))` 改为条件创建（`if not os.environ.get("MPLCONFIGDIR")`），避免环境变量已设置时仍静默创建废弃临时目录。
- **numpy 2.x 兼容**：`make_cv_roc_ci.py` 用 `_trapezoid = getattr(np, "trapezoid", None) or np.trapz` 兼容 numpy 2.x 移除 `np.trapz` 的变更。
- **`make_cv_roc_ci.py` 重构**：`add_summary_table(fig, rows, columns, *, bottom=0.035) -> float` 全行渲染（row_h=0.040、height=0.072+len(rows)*row_h、返回表区顶部），`fold_aucs_by_model` 预算复用，主轴自适应 `fig.add_axes([0.17, ax_bottom, 0.70, 0.955 - ax_bottom])`。
- **`check_figure.py`**：新增 `AUDIT_EXTS` + `_expand_directory`（os.walk 递归），支持目录参数；`--width-in/--height-in` 成对校验（is not None + 单边 WARN）。
- **`export_figure.py`**：`_grayscale_from(fig, basename, dpi, existing_png=None)`，formats 含 png 时复用已导出文件，否则用 tempfile.mkstemp 临时渲染后删除（不多写 png）。
- **`style_constants.py`**：删除与 `layout_tools.py` 同名不同签名冲突的 `add_panel_labels`。
- **`validate_figure.py`**：R 语法检查 `in_comment` 状态跳过 `#` 行注释；`check_font_family` 扩充 serif 白名单（Times/Liberation Serif/Nimbus Roman/STIX/font.family=serif 等）。
- **模板修复**：`make_correlation_pairgrid.py` 字号 4.7→6.0、`tick_params(labelbottom/labelleft=False)` 替代 `set_xticklabels([])`；`make_grouped_corr_split_violin.py` 组括号连续性校验（同组特征不相邻时显式报错）；`make_prediction_marginal_grid.py` 顶部边际分布用 `tick_params` 隐藏刻度；`make_rf_tpe_surface.py` 私有 `_axinfo` 加 `isinstance` 防护。
- `tools/figure/SKILL.md` 依赖块补 `Python>=3.10`（模板脚本使用 `zip(..., strict=True)` 等 3.10+ 语法）。
- 全量 27 条 figure 测试通过。

## 1.7.0 - 2026-09-02

### 格式排版规则第二轮（居中修复 + 编号铁律 + 白名单精确化 + 呈现纪律）

依据用户对重排版论文的逐项审读反馈（对照国一格式范本）：

- **修复 display 公式左对齐事故**：`paper_format.equation()` 与 `equations.py replace_with_equation()` 弃用"m:oMathPara jc=center 与编号 run 同段"的写法（Word 实测退化为左对齐），改为双制表位方案（居中制表位 4150 twips + 行内 oMath + 右制表位 8300 twips 悬挂编号），公式视觉居中、编号钉在版心右端；两处 docstring 记录该坑。更新两处测试断言（test_equations、test_paper_format）。
- **图表编号铁律**（论文格式规范/写作规范/自审框架/LaTeX格式规范同步）：图、表全文按出现先后连续编号（图1、图2…/表1、表2…），图表分编，**绝对禁止章节连字符编号**（图5-1、表3-2、图4.8 一律不许出现）；附录图表用"附表1/附图1"或延续正文序号。此前规范允许"章节制二选一"，与用户实证（优秀论文无一例外连续编号）冲突，已废除。
- **凡数学皆公式白名单精确化**：必须公式化清单补坐标元组 `(0, 200, 0)`、区间 `[8.015, 9.415] s`、含不等号片段 `y>0`（此前只列等号）；白名单收窄为仅三类——数字+单位且无数学结构、纯英文字符串、字母+非下标数字编号。
- **多行公式与多数据呈现纪律**：三条件及以上约束用 `\begin{cases}` 大花括号竖排（一行一条），连等/递推计算用 `\begin{aligned}` 等号对齐（一行一句），禁止逗号一行串联；正文 4 项及以上并列数据/映射/分配关系改用三线表、示意图（diagram_qN_*）或换行对齐呈现，判断标准为"读者 3 秒内能否读出谁对应谁"；2~3 项零碎数据允许行内逗号并列。
- `tools/docx/SKILL.md` 要点同步上述机制与纪律。
- 全部规则在豆包 2025 国赛 A 题论文上重排验证（`完整论文_重排版_v2.docx`：编号公式居中、三处 s.t. 改 cases 大括号、图1~图9/表1~表5/附表1~3 连续编号、坐标/区间/不等号全公式化、目标分配逗号堆积段改三线表）。
- 全量 132 条测试通过；同步至 dsh-plugin 内置知识库。

## 1.6.1 - 2026-09-02

### 工具链健壮性补丁（第三方 agent 实跑暴露）

以豆包桌面端装载本 skill 自动跑 2025 国赛 A 题为测试场，归因其论文格式事故时暴露的两个工具层缺口：

- `tools/docx/scripts/equations.py`：`LATEX_SYMBOLS` 补 `\bigcup`（⋃，自动享有 display nary 上下置）、`\bigcap`（⋂）、`\top`（⊤ 转置符）；此前这些常用命令报"不支持的 LaTeX 命令"。`tests/test_equations.py` 新增 `test_bigcup_transpose_symbols` 回归。
- `tools/docx/scripts/paper_format.py`：`page_number_footer()` 幂等化——页脚已含 PAGE 域（如 `论文模板.docx` 自带页码）时直接返回，不再叠加第二个页码域（此前与模板同用会出现"11""22"双页码）。
- 全量 132 条测试通过。

## 1.6.0 - 2026-09-02

### 绘图流程升级（示意图工具 + 高阶数据图模板 + diagram 审计）

整合同事在"绘图流程优化版"中的绘图增量（该版本基于本仓库 v1.4.0 开发，本次仅吸纳其绘图部分，其余部分仍以本仓库为准）。

- 新增 `tools/schematic/` 示意图工具（draw.io 路线）：技术路线图、流程图、机制示意图以 `.drawio` XML 为源文件，可编辑矢量导出（PNG + SVG/PDF 成对交付）；含 4 套版式模板（技术路线/流程/机制/对比，各附 example.json 与 preview.png）、tabler SVG 图标库（含 ATTRIBUTION.md）、`check_layout.py` 布局体检（重叠/越界/断连）、`export_figure.py` 导出、`preview_html.py` 预览；references 含 authoring/preflight-rules/self-check/replication/icons/adding-templates 六份操作文档。
- 新增 `tools/figure/scripts/templates/` 11 个高阶数据图模板：Taylor 图、和弦图、云雨图、分组环形热图、分组相关分裂小提琴、SHAP 组合图、ROC 置信区间、相关散点矩阵、预测边际网格、RF-TPE 曲面、城市公园降温组合图；统一 `--data csv` 真实数据契约 + `--demo` 演示模式（演示产物带 `_demo` 后缀，禁止交付）。
- `references/roles/编程手/scripts/figure_audit.py` 新增 diagram 类别审计：PNG 须与 SVG/PDF 矢量成对、DPI 缺失仅 WARN 不 FAIL、foreignObject 计为可编辑文本、统计输出新增 diagram_count。
- 分工与命名约定（多文档协同更新）：
  - 示意图命名 `diagram_qN_*`（全文级 `diagram_all_*`），`.drawio` 源 + PNG + 矢量成对；可计入正式图但只作补充，不替代数据图；不计入 raw/process/result 三类图配额。
  - `tools/figure/SKILL.md` 新增示意图与数据图分工段；`tools/figure/references/api-templates/template_catalog.md` 新增 11 个模板的契约表（用途/数据列/参数）。
  - 编程手 SKILL/工作流程/质检清单补示意图产出条款；`references/Subagent调度.md` W1 门禁强化"每子问题至少 1 张真实数据图"；`references/roles/论文手/SKILL.md` 明确 diagram 图引用纪律。
  - 根 `SKILL.md` 工具路由表补 schematic 入口与分工说明。
- `tests/test_figure_templates.py` 新增 10 条模板契约测试；`tests/test_figure_tools.py` 补 diagram 审计用例；全量 131 条测试通过。
- 同步至 dsh-plugin 内置知识库。

## 1.5.0 - 2026-09-01

### 论文手第三轮优化（格式排版：凡数学皆公式 + 表格五律 + display 公式体系）

以用户实跑产出（2020 国赛 A 题炉温曲线一代论文）与格式范本（同题 LaTeX 国一论文、2025 四川省一符号表）逐页对照为据，修复三个工程层的系统性排版缺陷。

- `tools/docx/scripts/equations.py`（LaTeX→OMML 转换器）：
  - 数学 run 统一注入 Latin Modern Math 字体与 12pt 字号（不再继承 docDefaults 11pt 导致公式小一号、不再显式 Cambria Math）；
  - 正体规则：`\text{}`/`\operatorname{}` 输出带 `m:sty="p"` 的正体 run，CJK 字符自动正体（修复"公式内中文斜体"事故）；min/max/lim/log/ln/sin/cos/argmin/argmax 等算子正体输出，新增 `\sup`/`\inf`/`\det`/`\gcd`；
  - `latex2omml(latex, display=True)`：display 模式下 `\sum`/`\prod` 升级为 m:nary（上下限正上/正下，自动吞入后随操作数避免空占位框）、`\min`/`\max`/`\lim` 升级为 m:limLow（下极限正下方）；`\int` 按中国教材惯例保持侧置；行内公式全部保持侧置；分式内部按 textstyle 处理；
  - `replace_with_equation(para, omml, number=)`：oMathPara 加 `m:jc=center` display 居中，编号以右制表位悬挂版心右端；`replace_placeholder` 对整段占位与行内占位分别使用 display/inline 转换。
- `tools/docx/scripts/paper_format.py`：
  - `equation(latex, number=)`：display 居中 + 编号右端 + 公式段单倍行距；
  - 新增 `body_rich()`/`_add_rich()` 混排基础设施：正文、图题、表题、表格单元格均支持 `("text", …)`/`("math", latex)` segments——"凡数学皆公式"的总开关；
  - `three_line_table()` 重写为"表格五律"：顶/底线 1pt（原 1.5pt 过粗）、单元格单倍行距（原误继承正文 1.5 倍导致"肥大"）、水平+垂直双居中、首行 tblHeader 跨页自动重复、行 cantSplit 不跨页断裂、列宽按内容分配（可 `col_widths` 覆盖）、字号默认五号、单元格支持混排公式；
  - 新增 `code_block()`：Consolas 等宽 9pt、语法着色（关键字蓝/注释绿/字符串暗红）、行号、单倍行距、细灰边框（段落 pBdr 整框合并，不占表格名额）；支持 python/matlab；
  - 新增 `reference_entry()`：五号、悬挂缩进 2 字符、1.15 倍紧凑行距；
  - 正文默认行距 1.5→1.35；heading1/2/3 段距修正为 12/6、8/4、6/3 递减并加 keep_with_next（落实 v1.4.0 规范条款）；插图默认宽 11→12.5cm。
- 规范文档：
  - `论文格式规范.md`：行距默认 1.35；公式行与"公式"节扩为"凡数学皆公式（判定规则 + 简单值白名单）+ 公式八条"；"表"节扩为"表格五律"（细线磅数/紧凑/双居中/不折行/跨页完整）+ 符号表三列纪律 + 科学计数法写法；附录支撑文件列表定为两列三线表；构建函数清单补新 API；图宽区间改 60~90%。
  - `写作规范.md`：新增"数学字块排版纪律"（禁止 Unicode 上下标/下划线/程序式科学计数法冒充公式）；标题短语化条款强化；图题表题不堆参数。
  - `自审框架.md`：文档结构节新增六组勾选项（凡数学皆公式扫描、大公式 display 排版、表格五律、代码块四要素、行距与参考文献紧凑、图宽）。
  - `章节模板.md`：符号说明节扩为四列排版纪律（符号列公式、说明列精简一行、单位列正体、表格五律）。
  - `LaTeX格式规范.md`：补公式排版纪律（display/`\text{}`/`\operatorname{}`/行内公式化），与 Word 分支同位准。
  - `tools/docx/SKILL.md`：推荐流程示例更新为新 API（body_rich、equation number、表格混排、code_block）。
  - `tools/latex/assets/templates/cumcm/main.tex`：`\linespread` 1.5→1.3（LaTeX 语义下与 Word 1.35 倍及范本实测观感一致）。
- `tests/test_equations.py` 新增 8 条回归用例（字体字号注入、正体规则、nary/limLow、inline/∫ 侧置、空 m:e 防护、整段替换 display 居中）；`tests/test_paper_format.py` 新增 3 条（表格五律结构断言、display 编号公式、代码块非表格）；全量 121 条测试通过。
- 同步至 dsh-plugin 内置知识库。

## 1.4.0 - 2026-09-01

### 论文手第二轮优化（摘要方法论 + 去 AI 味 + 官方硬约束 + 2025 最新实测）

- `references/roles/论文手/references/写作规范.md`：
  - 摘要节系统升级：篇幅基准改为 750~1000 汉字 / 3~6 段（2020—2025 国一实测）；新增"方法—答案闭环五要素链"（任务/瓶颈→决定性处理→核心模型→关键结果→结论/验证，结果紧跟方法）；"评委判断门"数字纪律（保留正文原精度、口径冲突宁省）；S/A/B/C 信息分级与信息损失六类自查；任务单元组织软化（默认逐问，允许递进/合并）；题型主干表（机理/优化/预测/评价/分类/统计/运筹 7 类）；结尾按价值决定有无；交叉验证与负结果可进摘要；加粗纪律细化为短语级。
  - 摘要"详见表X"指引删除规则及唯一例外：赛题显式指定的输出文件（如 resultN.xlsx）必须在摘要相应问末尾点名（2025 国赛两篇实测印证）。
  - "文病三反"扩充为"去 AI 味：文病三反 + 深度痕迹清单"：新增同义词轮换、系词回避、悬浮式"从而/进而"、成对转折收束、虚假范围、公式化挑战段；破折号每段 ≤1 个；冒号只禁 3 项以上串联长列举；新增受保护片段五类、反编造铁律、改写落点三级对照。
  - 国赛专项规则补 2025 最新实测：问题分析两式并存（段落式/小节式）+ 章首各问题关系图；每问末尾"模型汇总"小段（max/min + s.t. 总成）；约束逐条命名加粗；伪代码与附录代码带行号；附录清单含《AI工具使用详情》（2025 标配）；参考文献 AI 工具条目实测样例；总述段新增"公共基础式"开法。
- `references/roles/论文手/references/论文格式规范.md`：CUMCM 官方硬约束从 2 条扩为 2026 版执行摘要 12 条（纸质版页序、页码从摘要页起页脚居中、电子版首页摘要页、单文件 ≤20MB、支撑材料 ZIP ≤20MB、无目录、正文 ≤30 页口径、附录两必含、无程序/无支撑材料两声明、匿名性含元数据）；附录代码收窄为等宽 8~9pt 单倍行距带行号；标题段距递减（12/6、8/4、6/3）且与下段同页；表题保持居中并注明左对齐变体；公式编号注明连续制为主流、章节制可选但全篇统一。
- `references/roles/论文手/references/自审框架.md`：官方规则节补无目录/页码/匿名性/附录两声明勾选项；摘要勾选项更新为五要素闭环 + 信息损失六类 + 数字口径；新增深度 AI 痕迹扫描勾选项；附录勾选项补行号与 AI 详情清单。
- `references/roles/论文手/references/章节模板.md`：摘要段补组织灵活性与题型主干指引；问题分析补两式并存；模型建立补约束命名与模型汇总；附录补行号、AI 详情清单与两声明。
- `references/roles/论文手/SKILL.md`：完成门禁新增可选文本扫描说明。
- 新增 `tools/docx/scripts/aigc_scan.py`：移植自网络公开 skill "cumcm-aigc-reduce-skill" 的 AIGC 特征扫描器（9 维启发式），作为交付前辅助扫描，仅提示人工判定位置，不作否决依据。
- 优化依据：用户提供的群聊痛点记录、论文修订实录、十篇国一论文精读、网络三个论文写作 skill 精选（摘要重构/降 AI 率/排版），以及 2025 年最新 A 题题目与两篇最新完赛论文（摘要点名 resultN.xlsx、附录 AI 使用详情、代码带行号等实测特征）；网络 skill 部分规则已与官网 2026 格式规范 PDF 交叉核验一致。
- 同步至 dsh-plugin 内置知识库。

## 未发布

### 完善算法资料与建模方法论

- 01-优化 重写灰狼优化（GWO）与免疫算法代码为完整可运行版本，消除 `pass`/`# ...` 占位；GWO/鲸鱼/麻雀在 Rastrigin 测试收敛到最优（免疫算法为算法固有收敛特性，示例可运行）。
- 01-优化 修正 Metropolis 文献错标（原误写 VLSI 设计，改为正确论文标题）。
- 02-预测 修正插值两个"2.3"编号错乱（样条改 2.2）；Prophet 章节加"已停止维护"提示并推荐 statsmodels/chronos。
- 03-评价 新增第 12 章模糊综合评价（FCE）：原理、隶属度矩阵、加权平均合成、使用条件与坑、可运行代码（修复选择指南断链）。
- 04-图论 补 TSP（动态规划+最近邻）、中国邮递员、A* 完整可运行代码（真实数据验证通过）。
- 06-综合 重写博弈反应函数假图为真实最优响应计算（含纯策略纳什均衡返回）。
- 03/06 修正文本错别字（"箺法介绍"→"算法介绍"、"排荐系统"→"推荐系统"）。
- 建模设计理论新增"CUMCM / MCM 题型映射"：CUMCM A/B/C 与 MCM/ICM 各题型打法、机理题/数据题/决策题通用判读，并补充五段式摘要、25 页上限等竞赛硬约束。
- 建模手工作流程"假设及依据"补**关键假设 vs 可放宽假设**分级（关键 ≤3 条、可放宽 ≤7 条，附放宽复验方式）。
- 大数据/图像题的数据探索（EDA：缺失、异常、分布、相关性、预处理）已在编程手"读取输入"与质检清单覆盖，不另设独立文档，避免冗余。
- 同步至 dsh-plugin 内置知识库。

### 补充论文手评阅人抓分方法论

- `references/roles/论文手/references/写作规范.md` 扩充为两部分：格式与一致性规范 + "评阅人抓分方法论"。
- 抓分方法论含 5 节：摘要四段式+埋定量结果、结论段"一图一数一句"、评阅人快速抓分路径表、反模式对照自查（摘要/结果/选型/假设符号四类）、创新性信号（对应建模创造性权重）。
- 基于通用评审原则（假设合理性/建模创造性/结果表述/格式/文献五维权重），覆盖 CUMCM/MCM-ICM/APMCM，不限定国内竞赛。
- 论文手 SKILL.md"何时加载"补抓分检查入口；自审框架补摘要与结论抓分检查项。
- 同步至 dsh-plugin 内置知识库。

### 补充编程手求解稳健性

- `references/roles/编程手/references/工作流程.md` 新增"求解稳健性（跨竞赛通用）"专节，共 9 项：
  数值稳定性写法（log-sum-exp、gammaln）、无量纲化与归一化、矩阵病态检查（cond>10⁷ 换 lstsq/pinv）、
  优化器选型与尺度对齐（含求解器选型与超时降级）、随机性与多初始值、误差与收敛控制、
  数据规模与计算资源边界、结果 sanity check、跨平台可复现。
- 不限定国内竞赛赛题类型，覆盖 CUMCM/MCM-ICM/APMCM 及机理/数据/优化/仿真各类赛题。
- `references/roles/编程手/references/质检清单.md` 补求解稳健性检查项，与专节呼应。
- 同步至 dsh-plugin 内置知识库。

### 扩充机器学习算法并拉平权重

- `assets/07-机器学习算法说明.md` 从 3 个算法扩充至 8 个：新增逻辑回归、决策树、KNN、朴素贝叶斯、SVM 分类，每个算法含原理、使用条件与常见坑、真实数据可验证的 sklearn 示例。
- 与 02 预测（SVR/XGBoost/线性回归）、05 统计（聚类/PCA）交叉引用去重，明确分类与回归视角的区分。
- `assets/README.md` 机器学习类目拉平到与其他六类算法同权：核心算法表与详情段落扩充至 8 个算法，补充按需使用说明。
- 同步至 dsh-plugin 内置知识库。

### 新增前置使用指南

- 新增根目录 `使用指南.md`：说明本 Skill 的定位（辅助工具）、交付物使用边界、生成文件清单、提交前人工核对事项；不展开学术诚信与竞赛规则，聚焦交付物使用边界。
- 根 `SKILL.md` 头部新增指引：使用前先阅读并复制 `使用指南.md` 到工作区。
- 同步脚本 `sync_dsh_plugin.py` 支持同步 `使用指南.md` 到 dsh-plugin 内置知识库。

## 1.3.0 - 2026-08-31

### 论文手按国赛国一论文实测重做（内容与结构）

- `references/roles/论文手/references/写作规范.md` 全文重排为三部分：
  - 新增"读者模型与语言纪律"：评委画像（数模专家、非领域专家、限时阅读）、语言三铁律（平实质朴/严密专业/自然流畅）、术语随用随解释、密度纪律（每问仅 1~3 个关键数值做多维讨论、段落超 6 个数字收进表格）、机器视角清零（表格播报腔/元指令泄露/占位符/工作日志式标题/机器自述）、文病三反（宏大动词/套娃长定语/机械排比）。
  - 摘要改为分竞赛范式：CUMCM 用国赛叙事链（总述段 + 逐问"针对问题X，考虑…建立…采用…得到…（1~2 个关键数值）"，600~1000 字独立第一页，关键词 3~5 个），MCM/ICM 沿用四段式。
  - 反模式自查新增结构类（两段式建模、中间产物搬运、独立敏感性大章、附录无代码）、机器视角类、语言病类。
  - 新增"国赛专项规则"：八股骨架与各章篇幅锚点、按问题联动（禁两段式、公共底座 ≤1.5 页）、每问"建立→求解→结果与分析"内部范式、灵敏度并入末节或 ≤2 页小章、诚实负面结果写入局限、附录三大件、AI 使用合规三件事（正文角标 + 参考文献 AI 工具条目 + 《AI工具使用详情》）、高频句式库。
- `references/roles/论文手/references/章节模板.md` 重排为国赛八股骨架逐章模板（每章给篇幅锚点、组织范式与常见错误）。
- `references/roles/论文手/references/自审框架.md` 检查单扩充：摘要分竞赛检查、按问题联动、假设精炼、术语解释、密度纪律、机器视角清零、附录三大件、正文/附录精度分层、AI 合规、图表题注位置与编号一致性、图密度与颜色纪律。
- `references/roles/论文手/SKILL.md`、`references/roles/论文手/references/工作流程.md`：CUMCM 篇幅质量目标由"约 15000 字词单位"改为"典型 9,000~15,000 字词单位（近年国一实测约 9,000~16,000，9000 为硬下限预警，禁止凑字数填充）"；W1 门禁补"按问题联动 + 摘要国赛叙事链"核对项。
- `tools/docx/SKILL.md`、`tools/latex/SKILL.md`、`README.md` 篇幅口径同步更新。

### 国赛排版基线（无官方模板时的构建基线）

- `references/roles/论文手/references/论文格式规范.md` 新增"国赛排版基线"专节：字体字号对齐体系表（标题黑体三号居中 / 摘 要黑体四号居中 / 一级标题黑体四号居中 / 二三级标题小四加粗顶格 / 正文宋体小四首行缩进 2 字符两端对齐约 1.5 倍行距 / 图题图下五号居中 / 表题表上五号居中 / 公式居中编号右端连续 / 页码页脚居中）、全文文字纯黑纪律、图表编号二选一全篇一致、图宽版心 60~75%、建模部分 0.6~1 幅/页、默认三线表（密集大表可全框线）、正文 4~6 位小数与附录全精度分层、附录版式（索引页+支撑文件清单+语法着色代码）。
- `tools/docx/scripts/paper_format.py` 默认值与基线对齐：标题 14→16pt（黑体）、摘要标题独立为黑体 14pt、一级标题改黑体 14pt 居中并取消强制另起一页、二级标题改黑体 12pt、正文行距 1.25→1.5 且两端对齐、图题 10→10.5pt、新增 `table_caption()` 与 `page_number_footer()`（页脚居中自动页码）、插图默认宽 12→11cm、CUMCM 篇幅质量目标 15000→9000 字词单位。
- `tools/docx/scripts/self_check.py` 断言同步更新（一级标题不强制分页、黑体四号居中；二级标题黑体小四）。
- `references/roles/论文手/references/论文模板.docx` 用更新后的构建基线重生成：国赛八股骨架、摘要独立第一页、页脚居中页码、符号三列三线表。
- `tools/latex/assets/templates/cumcm/main.tex`：新增 `\ctexset`（一级标题黑体四号居中、中文数字编号、二三级标题小四左对齐）、1.5 倍行距与 2em 首行缩进；章节骨架改为八股（问题重述/问题分析/模型假设/符号说明/模型的建立与求解/模型评价）并附附录三大件注释。
- `tests/test_paper_format.py` 篇幅断言同步为 9000。
- 同步至 dsh-plugin 内置知识库。

## 1.2.0 - 2026-08-10

### 科研可视化工具融合

- 新增 `tools/figure/` 子 skill，融合 nature-figure 的图表契约/后端路由架构与 scipilot-figure-skill 的数据剖析/选图决策/自检闭环，支持 Python 和 R 双后端。
- 新增 9 个可视化脚本：`profile_data.py`（数据剖析）、`setup_style.py`（期刊预设）、`export_figure.py`（多格式导出）、`visual_qa.py`（程序自检）、`layout_tools.py`（子图对齐）、`check_figure.py`（文件审计）、`validate_figure.py`（源码审计）、`nature_figure_backend.py`（后端路由）、`style_constants.py`（常量与工具函数）。
- 新增 18 份参考文档并分为 5 个子文件夹：`chart-types/`（图表类型与选择）、`design/`（设计理论与避坑）、`api-templates/`（API 与模板）、`quality/`（质量检查与期刊规范）、`guides/`（教程与规范指南）。
- 精简 `plot_style.py`：移除已被新工具替代的 `apply_publication_style`、`export_figure`、`audit_layout`、`audit_design` 函数，保留 `PALETTE`、`COLOR_SEQUENCE`、`WIDTHS_IN`、`choose_font`、`figure_size`、`publication_subplots`、`add_panel_labels`、`resolve_output_stem` 向后兼容。
- 删除已迁移的文档：`可视化规范.md`、`图表选择与避坑.md`、`常见模式.md`；`可视化面板模板.html` 迁移到 `tools/figure/assets/`。
- 可视化面板模板侧边栏导航改用 flexbox 布局，图表类型 badge 改为由 CSS `::after` 伪元素根据 `data-chart` 属性自动生成。
- 更新编程手 SKILL.md、工作流程、质检清单、references/README.md、根 SKILL.md 和 README.md 中的可视化相关引用。

### LaTeX 论文改为可选

- 默认只生成 Word 论文（`完整论文.docx`），LaTeX 论文改为用户显式要求时才生成。
- LaTeX 环境配置繁琐且不是所有用户都需要，将其从默认交付物中移除，降低使用门槛。
- 更新论文手工作流程、自审框架、Subagent 调度和质检清单中的相关描述。

## 1.1.1 - 2026-07-29

### 绘图路径与 LaTeX 稳定性

- 修复 `plot_style.py` 复制到 `PROJECT_ROOT/utils/` 后仍按固定父目录层级推导 `SKILL_ROOT`、导致合法图形输出被全部拒绝的问题；改为识别数学建模 Skill 的真实目录标记，同时继续禁止写回真实 Skill。
- 修复 `\\[0.4em]` 等 LaTeX 换行间距被误识别为 `\[` 行间公式起始符的问题，并按连续反斜杠奇偶数识别合法分隔符，避免虚增、漏计和错误的不平衡报告。
- 构建前实际执行 `latexmk --version`；Windows/MiKTeX 仅存在不可执行包装器时，对无外部参考文献的项目自动回退到两次所选 TeX 引擎编译，含外部文献时仍明确阻断。

### 正文页数与资源一致性

- CUMCM 页数上限改为校验正文页数，不再直接比较 PDF 总页数；默认排除摘要页，自动尝试定位附录起始页，也支持通过 `--body-start-page` 和 `--appendix-start-page` 明确传入实际页码。附录参数必须与源码结构和自动定位结果一致；MCM/ICM 与通用配置仍按 PDF 总页数校验。
- 新增 `latex_paper.py bind`，把 `PROJECT_ROOT` 中的权威代码、数据或图表与 LaTeX 项目内任意目录的资源副本建立 SHA-256 绑定；源码校验和编译都会拦截缺失、未绑定或已经漂移的资源，不再依赖固定目录名。
- 增加对应回归测试，并同步更新 README、论文手流程和 LaTeX 工具说明。

## 1.1.0 - 2026-07-24

### 图表数量门禁

- 编程手的原始数据图、模型运行过程图和模型最终结果图由“每类至少一张”提高为每类至少 3 张逻辑候选图、合计至少 9 张，并由 `figure_audit.py --strict` 确定性拦截数量不足。
- 新增按子问题覆盖门禁：用 `raw_q1_*`、`process_q1_*`、`result_q1_*` 等命名，每个子问题在三类中各至少 1 张；审计命令必须通过 `--questions` 显式传入题目全部子问题，防止只为问题一集中出图。
- Word 与 LaTeX 论文统一采用至少 8 幅图的默认质量基线，MCM/ICM 等其他竞赛不再低于 CUMCM；当届官方规则或用户明确要求仍可覆盖默认值。

### Subagent 默认质检与可选协作

- 将质检从主 Agent 的阶段末自评改为作者自检、确定性脚本与独立 Subagent 验收三层门禁，禁止等全流程结束后才首次派发。
- 新增 `M1` 建模终检、`P1` 最小可运行结果、`P2` 编程终检、`W1` 证据大纲和 `W2` 论文终检；在全量计算和长篇排版前提前暴露模型漂移与证据缺口。
- 统一 Subagent 的只读边界、输入快照、`PASS/FAIL/BLOCKED` 回执、证据格式、返工归属、产物变更失效和修后复验规则。
- 明确默认只运行固定质检 Subagent；规则核验、附件盘点、文献与模型调研、算法原型、独立实验、双语言对照和术语核验仅在用户明确选择后运行。
- 为可选协作补充输入输出、隔离执行和权威产物边界，同时禁止多人并写权威产物或重复已有脚本的机械检查。
- 保持公开版本基线为 `1.0.0`，不增加第四个固定角色或额外交付物。

### 出版级科学可视化

- 将 Nature Skills 的图表契约、证据映射和出版级交付思想，与 SciPilot 的数据剖析、图型决策、科研绘图避坑和成图复核闭环按数学建模场景重新设计后融入编程手，不直接照搬外部 Skill。
- 根据 CUMCM 实际运行产物补齐视觉层级：每张图先写一句话结论并选择叙事原型，显式声明主面板、辅助证据、非对称比例和图例策略，避免把 Nature/SCI 简化为字体、色板与 DPI。
- 为 Python 与 MATLAB 增加出版设计预检，默认拦截长标题、超量图例、稠密逐点标记、非零基线柱状图和已标数值 2×2 小矩阵的冗余 colorbar。
- 补充分组经验率、少量点估计、PR 曲线、混淆矩阵和特征重要性的选图规则，修正锯齿折线、巨型纹理柱、面板机械等分和仪表盘式布局。
- 恢复并明确 Nature/SCI 风格为默认可视化基线，同时声明目标竞赛、学校或期刊的当届官方规范优先，不把通用风格误写成官方认证。
- 新增 Python `plot_style.py` 和 MATLAB 出版样式/导出工具，统一色觉友好配色、字体、线宽、最终尺寸、无网格线基线、可编辑 SVG 与 300 DPI PNG 双格式输出。
- 新增标准库 `figure_audit.py`，自动检查 `raw_`、`process_`、`result_` 三类图、SVG/PNG 配对、SVG 可编辑文本、PNG DPI、JPEG 和嵌入位图风险。
- 补齐导出前缺字/越界/刻度重叠预检与灰度预览，移除会改变最终物理尺寸的 `bbox_inches="tight"`，并在审计报告中记录 PNG 的实际英寸尺寸。
- 新增图表选择与避坑指南，覆盖分布、比较、趋势、优化、预测、分类、评价、空间网络和物理模型，同时保留多生成候选图、由用户和论文手选择的策略。
- 将视觉验收改为“生成 → 文件审计 → 实际打开预览 → 修改源代码 → 重绘复核”的闭环，并补充 README 中的可视化能力说明与 SciPilot 致谢。

### 模板驱动的 LaTeX 论文支持

- 新增 `doctor` 环境诊断，按所选引擎、BibTeX/Biber 后端、Pandoc 与 PDF 审计能力动态检查 `latexmk`、TeX 引擎、`pypdf`、`pdfimages` 和 `pdftoppm`，缺项时在写作前明确阻塞。
- 初始化项目新增 `latex-project.json`，支持子目录主入口和 `generic` 官方模板，并记录模板 URL、适用届次、目录哈希与唯一主入口。
- 构建新增 `.build.json`，绑定当前源码、PDF、项目模板哈希，记录工具路径与版本、实际命令、返回码、耗时、告警、覆盖理由和复现命令；无清单、旧源码或被替换的 PDF 均不能通过校验。
- LaTeX 改为在系统临时目录的完整项目副本中编译，原始源码不作为编译写入目标；编译后同时核对副本和原项目哈希，动态控制序列造成的文件写入也无法污染真实项目或绕过发布门禁。
- PDF/DOCX 与对应 JSON 清单改为成对替换；覆盖旧版本时先备份，任一替换失败自动回滚，避免留下无绑定产物或丢失上一套有效文件。
- 构建输出固定为项目根目录 `build/`，拒绝会混入源码哈希的任意输出目录；显式传入不存在的 PDF 现在始终失败。
- 编译错误、未解析引用、LaTeX/宏包/文档类、Overfull/Underfull 和字体告警默认阻断 PDF 发布；只允许通过精确正则和具体理由覆盖已核对告警，默认拒绝覆盖既有发布产物。
- 修复 `$$...$$` 被重复计数；新增分隔符配对检查、空图/空表拦截、图表题注与环境外正文引用检查，避免仅堆叠空环境绕过数量门禁。
- 质量校验要求通过 `--questions` 声明全部子问题，并以 `fig:q1-*` 等标签检查正式图覆盖；阈值禁止负数，降低默认目标必须记录官方条款或用户要求。
- 安全编译链只直接接受 PDF、PNG、JPG/JPEG，明确拒绝依赖 shell escape 的 SVG/EPS 编译期转换；新增 PDF 空白页、页面尺寸、字体嵌入与内嵌位图 DPI 检查。
- 完整 LaTeX→DOCX 转换会递归展开项目内 `\input`/`\include`，拒绝越界和循环包含；Pandoc 警告默认阻断 DOCX 发布，并生成绑定输入、输出、模板、版本、命令和覆盖理由的 `.conversion.json`。
- 新增 `verify-conversion`，交付前重新验证 LaTeX/Markdown 源文件、全部项目资源、参考模板、DOCX、清单哈希和完整字段类型；注释与字面量环境保持原样，`verbatim`/`\verb` 内伪命令和百分号不会掩盖后续真实命令，`\nocite{*}` 不再造成误报。
- LaTeX 与 DOCX 命令行统一强制 UTF-8 输出，编译/转换超时可配置；新增针对空图表、旧 PDF、阈值绕过、公式计数、子问题覆盖、嵌套入口、SVG、告警发布和递归转换的回归测试。
- 将 Skill 遵循要求改为可观察的强制执行协议：首次更新回显激活与路径，禁止绕过内置工具，环境缺失时明确阻塞，最终回复必须提供实际命令、退出码和质量指标。
- 新增 DOCX 命令行完成门禁，并将 LaTeX 布局、宏包、文档类和字体预警纳入失败条件，防止篇幅不足或带编译预警的论文被错误宣布完成。
- 论文手默认同时生成内容一致的 DOCX 与 LaTeX/PDF；用户明确只要一种格式时仍可只运行对应分支，两种格式分别生成并校验哈希绑定的质量报告。
- 新增完整 LaTeX 论文转 DOCX：复用 Pandoc 将 `.tex`、相对图片和公式转换为 Word，支持官方 DOCX 参考模板、OMML 公式、转换警告、原子发布与覆盖保护。
- 新增独立 `tools/latex`，支持复制当届官方 LaTeX 模板项目并显式选择多入口模板的主文件；无官方模板时可选择 CUMCM 中文或 MCM/ICM 英文构建基线。
- 新增 `latex_paper.py`，提供模板初始化、XeLaTeX/LuaLaTeX/pdfLaTeX 编译、编译日志诊断、完整项目依赖哈希和 PDF 实际页数检查。
- 增加 LaTeX 论文结构与质量校验：检测占位符、篇幅、公式、图表文件、重复标签、图表正文引用、BibTeX/正文引用对应和官方页数上限。
- 论文手支持按用户要求生成 Word、LaTeX，或默认同时生成两种格式；当届官方提交要求仍决定实际可提交的版本。
- LaTeX 分支交付完整源码项目和由其实际编译的 PDF，不把缺少 `.cls/.sty/.bib` 依赖的单个 `.tex` 文件视为完整交付。
- 编译默认禁用 shell escape、忽略项目级 `.latexmkrc`、限制文件读写范围并拒绝符号链接；缺少引擎或宏包时明确失败，不自动安装或静默换引擎。
- 新增 LaTeX 回归测试，覆盖内置/官方模板复制、覆盖保护、递归源码检查、图表与文献关联、路径越界和编译环境缺失。

## 1.0.0 - 2026-07-10

本版本由 **GPT 5.6 Sol 进行全面检查和完善**。在保留数学建模完整工作流的基础上，对角色职责、论文检索、公式转换、DOCX/Excel 工具、Python/MATLAB 支持、复现机制、路径规则和参考资料进行了系统性修正，并从 `1.0.0` 重新建立公开版本基线。

### 工作流与交付物

- 将完整流程统一为“建模手 → 编程手 → 论文手”三个独立阶段，既支持顺序执行，也支持按需单独执行。
- 固定建模手交付物为 `题目分析报告.md` 和 `术语表格.md`。
- 固定编程手交付物为 Python/MATLAB 代码，以及代码运行产生的表格、原始数据图、模型运行过程图和模型运行结果图。
- 固定论文手交付物为 `.docx` 格式的完整论文，并规定论文仅供参考，论文内容、结构和格式必须服从目标竞赛当届官方规则与官方模板。
- 完善阶段反馈闭环：下游阶段发现模型、数据、程序或论证问题时，返回对应上游阶段修正，不在后续产物中掩盖问题。

### 建模与算法规范

- 调整模型选择逻辑：先理解题目与数据，再确定结论所需的模型；每个子问题最多使用两个独立模型体系，物理题中同一机理的不同近似和精度展开按一个模型族计数。
- 鼓励在合理、可解释和可验证的前提下避免常见简单模型，以体现建模创新性。
- 修正常见建模模式、算法说明和示例，移除不合理的固定阈值说明、硬编码规则及“同一结论的两个模型必须删一个”等限制。
- 统一可视化要求，允许提供更丰富的候选图；修正双子图示例、HTML 相关说明和算法库示例，并统一取消示例图网格线。

### 论文检索与资料核验

- 实现 OpenAlex + AnySearch 真正的双引擎论文搜索，分别执行检索后汇总结果。
- 优先使用 DOI 归并重复文献；无 DOI 时按规范化题名交叉核验，并保留来源、作者、年份和链接等追溯信息。
- 修正算法资料与引用说明，移除“优秀论文库”相关声明，避免把非官方资料误写成固定依据。

### 公式、DOCX 与 Excel 工具

- 完善 LaTeX、MathML 与 Word OMML 之间的公式转换流程，增加转换校验与失败处理，降低公式丢失、错位和不可编辑风险。
- 改进模板驱动的 DOCX 论文生成方式：优先继承官方模板的页面、样式与章节设置，再填充正文、公式、图表和参考文献。
- 完善 DOCX 生成后的结构检查、公式检查和渲染抽检，确保关键内容在 Word 中可编辑、可见且版式稳定。
- 完善 Excel 表格读写、格式处理和结果导出说明，合并 DOCX 与 XLSX 工具中的重复资源，修正相关 Markdown 文档。

### Python、MATLAB 与复现能力

- 在既有 Python 支持基础上补全 MATLAB 的建模、绘图、结果导出、依赖检查和运行规范。
- 改为根据选中的模型和功能动态检查依赖，不再要求安装与当前任务无关的完整工具集合。
- 统一记录随机种子、输入文件 SHA-256、运行环境与依赖版本、关键参数和唯一复现命令。
- 明确程序必须真实运行，并把对应表格和图形作为论文写作的可追溯输入。

### 路径、资源与文档治理

- 显式区分 `SKILL_ROOT` 与 `PROJECT_ROOT`：所有 Skill 内置资源只从前者读取，所有任务产物只写入后者。
- 默认禁止任务运行过程覆盖 Skill 自身文件，统一并修正全部相对路径。
- 完善渐进式加载，只在当前任务需要时读取相应角色规范、算法资料、工具说明和模板资源。
- 更新根目录 README、`references/README.md`、版本规则和验证说明，同时完整保留版本号重置前的历史更新记录。

### 实际任务测试反馈修正

- 扩充 OMML 公式引擎的常用 LaTeX 命令，补齐 `\nu`、`\mu`、`\approx`、`\arcsin`、`\arccos`、`\arctan` 及更多希腊字母、关系符号和函数。
- 扩展 `validate_paper_structure()`：统计中英文混排篇幅、可编辑公式、图和表，检查图表编号连续性、正文引用、参考文献双向对应，并接收渲染页数。
- 将 CUMCM 的约 15000 字词单位、约 20 页明确为可覆盖的完整度质量目标；依据 2026 年官方规范，将正文不超过 30 页作为当前已核验的硬约束，禁止混淆二者。
- 为 OpenAlex + AnySearch 融合结果增加查询词覆盖率过滤、相关性优先重排和同题名预印本/正式版折叠，减少物理、材料与光学专题中的高被引无关结果与重复结果。
- 增加无隐式表头推断的 XLSX 读取工具和预期行数断言，防止第一行数据被 `pandas` 默认 `header=0` 吞作列名。
- 增加图表题注—正文引用检查，识别孤儿图表、缺失编号和编号跳跃。
- 修正物理建模的模型数量口径：同一控制机理的基础模型与高精度展开属于一个模型族，不机械占用两个模型名额。

## 版本规则

采用语义化版本 `MAJOR.MINOR.PATCH`：

- `MAJOR`：不兼容变更，例如修改固定交付物、目录契约、命令参数或复现清单结构。
- `MINOR`：向后兼容的新能力，例如新增算法类别、工具功能或竞赛配置。
- `PATCH`：向后兼容的修复，例如错误修正、文档校正和测试补充。

预发布版本使用 `1.2.0-beta.1`；Git 标签使用 `v1.1.1`。

## 版本号重置前的历史记录

> 以下内容保留编号重置前的开发历史，仅说明当时版本发生过什么，不代表当前版本仍保留相同文件、规则或能力。

### v2.4 (2026-05)

#### 🏗️ 重大架构更新：角色子Skill + 渐进式加载

原三个单文件角色文档重构为独立子Skill体系，每个角色自包含入口 SKILL.md + 细分引用文件，按阶段渐进加载，大幅降低单次对话上下文负担。

**角色文件迁移**：
```
旧（单文件）                   新（子Skill + 渐进式加载）
references/roles/
├── 建模手说明.md    →    references/roles/建模手/{SKILL.md + 4个引用}
├── 编程手说明.md    →    references/roles/编程手/{SKILL.md + 4个引用}
└── 论文手说明.md    →    references/roles/论文手/{SKILL.md + 7个引用}
```

#### 🎯 建模手：新增 Model Contract + 常见模式 + 缺失输入处理

- **Model Contract（前置合同）**：在分析前建立核心结论→证据链→方案评审→交付规格的完整规划框架
- **11种建模常见模式**：按优化/预测/评价/综合分类，含模型组合决策树
- **缺失输入处理规则**：数据不足、模型不适用、问题类型不明确时的标准化处理流程
- **防冗余原则**：每个模型承载独特分析维度，避免重复建模

#### 🎨 编程手：SCI/Nature 级可视化规范 + 环境检查 + 图表常见模式

- **Figure Contract**：绘图前先定核心结论→证据链→面板映射→评审风险检查
- **完整颜色体系**：语义调色板 PALETTE + 低饱和度 PALETTE_NMI_PASTEL，跨面板统一色系
- **SVG + PNG 双格式输出**：强制 `svg.fonttype='none'` 保持文本可编辑，dpi=300
- **HTML 可视化导航面板**：左侧导航栏 + SVG 渲染 + 导出 + 缩放控制
- **环境检查步骤**：在编码前检查运行时和依赖包，不因环境问题切换语言
- **11种图表常见模式**：分组柱状图、趋势+CI、热力图、气泡图、箱线图等，含代码模板
- **无网格线 / 仅左+下spines / 面板标签规范 / 统计标注规则**

#### 📝 论文手：论证驱动写作 + 章节架构模式 + 自审框架 + 英文化工作流

- **Argument-first 写作法**：一句话论证模板 + 核心论证要素 + Claim-Evidence 显式映射
- **摘要六要素架构**：context→gap→approach→result→implication→boundary
- **引言五要素架构**：field scale→bottleneck→prior attempts→gap→present study
- **结果证据阶梯**：system→validation→main result→comparison→analysis→application
- **Discussion 架构**：advance→evidence→relation→constraints→future
- **Related Work 主题综合法**（美赛专用）：按技术主题组织，非逐篇罗列
- **四轮自审框架**：论证逻辑→章节结构→表述质量→格式规范，含反方测试
- **英文化工作流**：三阶段转换（理解→写作→校准）+ 动词强度谱系 + 句式转换表
- **段落流检查**：一段一消息三步检查法
- **正式输出格式**：草稿 + 大纲 + 假设 + Claim-Evidence 映射 + 结构说明

#### 📦 其他

- 所有角色文档路径从 `roles/` 迁移至 `references/roles/`
- 新增 `references/roles/建模手/references/建模设计理论.md`
- 新增 `references/roles/编程手/references/可视化面板模板.html`
- 新增 `references/roles/论文手/references/论文模板.docx`
- 整体 README 和 CLAUDE.md 同步更新

#### 🔬 可视化面板科研化重设计

- **配色升级**：采用项目可视化规范 PALETTE 色系（学术蓝 `#0F4D92` + 金色 `#FFD700` 激活态）
- **新增导出 PNG**：SVG 渲染为高分辨率 PNG（2x DPR）下载
- **图表元信息栏**：Figure 编号 + 描述，模拟论文图表标题格式
- **键盘快捷键**：`Ctrl+=`/`-` 缩放、`Ctrl+E` 导出、`↑↓` 切换、`F11` 全屏
- **Ctrl+滚轮缩放 + 缩放百分比指示器**

#### 🔎 Paper Search 双引擎并行搜索

- **AnySearch Academic 集成**：直接通过 JSON-RPC 2.0 调用 AnySearch API，无需外部依赖
- **混合搜索引擎 `hybrid_scholar.py`**：ThreadPoolExecutor 并行调用 OpenAlex + AnySearch
- **交叉验证机制**：DOI 精确去重 + 标题模糊去重，结果分三区展示（交叉验证 / OpenAlex 独有 / AnySearch 独有）
- **兼容原参数**：支持 `--openalex-only`、`--anysearch-only` 单源模式，JSON 输出
- 新增 `anysearch_academic.py`、`hybrid_scholar.py`，更新 `SKILL.md` 和 README 配置说明

#### 🏆 适配竞赛列表

- 完整列出 6 大适配竞赛（美赛 MCM/ICM、亚太赛 APMCM、国赛 CUMCM、MathorCup、认证杯、数维杯）

### v2.0 (2025-02)

#### ✨ 重大更新：论文AI味去除系统

针对AI生成论文容易被检测工具识别的问题，本次更新在 `references/roles/论文手/references/写作规范.md` 中加入了完整的**去AI味写作指南**，基于Wikipedia的"Signs of AI writing"研究整理：

**七大类AI痕迹识别与去除：**

1. **内容模式去AI化**

   - 消除"标志着/重要的是/关键作用"等过度强调词汇
   - 去除"独立报道/专家认为"等模糊归因
   - 避免"不仅...而且..."等公式化平行结构
   - 删除"突破性的/令人惊叹的"等广告式宣传语
2. **语言语法规范化**

   - 控制"此外/关键的/深入探讨"等AI高频词汇使用
   - 避免"拥有/具有"等复杂结构替代简单系动词
   - 破除强行分组的"三法则"套路
   - 消除同义词过度替换（"模型/算法/方法/方案"循环）
3. **写作风格真实化**

   - 减少破折号和粗体的过度使用
   - 避免内联标题垂直列表（**准确性：** 95%）
   - 删除表情符号和装饰性元素
   - 用具体数据替代模糊积极结论
4. **数学建模论文专用规范**

   - 禁用"深入探讨/充分展示/具有重要意义"等空泛表达
   - 用"准确率达到95.6%，比基准方法高8.2%"替代"结果令人振奋"
   - 要求每句话都有具体数据或信息支撑
   - 承认复杂性和局限性，注入真实分析思考

**完整自查清单**（论文手必须遵守）：

- [ ] 是否使用了AI高频词汇？
- [ ] 是否过度使用破折号、粗体？
- [ ] 是否有"不仅...而且..."结构？
- [ ] 是否强行将内容分成三组？
- [ ] 是否有模糊的"专家认为"？
- [ ] 是否有公式化的"挑战与展望"？
- [ ] 每句话是否都有具体数据支撑？

---

#### 🛠️ 新增四个专业子Skill

原 `scripts/` 目录已移除，功能由以下专业子Skill替代：

| 子Skill                  | 功能                      | 使用场景                       |
| ------------------------ | ------------------------- | ------------------------------ |
| 📑`tools/pdf`          | PDF文档读取、文本表格提取 | 读取比赛题目、学习优秀论文     |
| 📊`tools/xlsx`         | Excel表格处理、公式计算   | 处理题目数据、输出结果表格     |
| 📘`tools/docx`         | Word文档生成、模板编辑    | 生成标准格式论文               |
| 🔎`tools/paper_search` | OpenAlex+AnySearch双引擎学术搜索 | 交叉验证式参考文献搜索（需配置邮箱，AnySearch API Key可选） |

**⚠️ Paper Search 配置提醒**：使用 `paper_search skill` 前需配置 OpenAlex 邮箱（必填），AnySearch API Key 可选但建议配置，详见上方【⚙️ 配置说明】部分。

**三角色必须正确使用对应skill：**

- 🧠 **建模手**：使用 `pdf skill` 读题目、`xlsx skill` 分析数据、`paper_search skill` 搜索文献
- 💻 **编程手**：使用 `xlsx skill` 处理Excel数据；普通结果汇总用 CSV，指定 Excel 模板保留结构和公式
- ✍️ **论文手**：使用 `docx skill` 生成.docx格式论文、使用 `paper_search skill` 交叉验证文献

---

#### 🏆 优秀论文资源库扩充

新增 `references/Outstanding Thesis/` 目录：

**🇨🇳 国赛优秀论文 (CUMCM)** - 9篇

- 🚛 RGV动态调度优化系列（3篇）
- 👥 百货商场会员画像描绘系列（2篇）
- 🚗 汽车总装线配置系列（3篇）
- 🌡️ 高温作业专用服装设计（1篇）

**🌍 美赛O奖论文 (2017MCM ICM)** - 27篇

- 📈 A题连续型（4篇）
- 📊 B题离散型（5篇）
- 💡 C题数据洞察（4篇）
- 🕸️ D题运筹网络（5篇）
- 🌱 E题环境科学（5篇）
- 📋 F题政策分析（4篇）

---

#### 📚 三角色说明文档全面增强

| 角色文档                    | 新增内容                                                                                                        |
| --------------------------- | --------------------------------------------------------------------------------------------------------------- |
| 🧠**建模手说明.md**   | 增加pdf/xlsx/paper_search skill详细使用方法、文献记录要求、算法资源库索引                                       |
| 💻**编程手说明.md**   | 增加xlsx skill公式处理、Python/MATLAB库速查表、SCI/Nature可视化标准                                             |
| ✍️**论文手说明.md** | **重点增加去AI味写作指南**、docx skill使用教程、图文并茂规范（每张图≥100字分析）、人称约束、叙述方式规范 |

---

#### 🔧 算法文档改进

- ✅ 修正了所有算法文档中的文献引用格式
- 🔎 新增 `paper_search skill` 支持通过OpenAlex API自动搜索学术论文
- 📖 优化了 `assets/README.md` 算法快速索引

---

### 🎉 v1.0 (2025-01)

- 🎊 初始版本发布
- 🔄 基础三阶段工作流程：建模分析 → 代码实现 → 论文撰写
- 📚 7大类60+算法资源库
- 👥 基础角色分工文档

---
