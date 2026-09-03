# 题意沉浸几何/物理示意图（geometry kit 路线）

> 什么时候读：要画的示意图里出现**题目实体**（导弹/云团/圆柱体/无人机/炉膛/机器人…）、
> **空间关系**（轨迹、遮蔽、投影、受力、区域划分）或**数学对象**（向量、夹角、判定分区）时。
> 框线结构图（技术路线/流程/架构）不要走这条路线，走 draw.io 模板（A/B/C 路径）。

## 一、这类图为什么加分

国一论文范本实测：最出彩的图（如 2025A 题图5-2 轨迹分阶段示意、图6-2 投影法判定示意）
都不是通用框图，而是"长出题目样子"的几何示意图——坐标系 + 题目实体 + 向量夹角 +
判定分区 + 图上直标。评审一眼看懂模型的几何本质，且证明作者真的理解了自己的模型。

## 二、入口

```python
import sys
sys.path.insert(0, "<SKILL_ROOT>/tools/schematic/scripts")
from geometry_kit import (new_canvas, draw_coord2d, draw_coord3d, proj3,
                          vector, angle_arc, phase_polyline,
                          body_circle, body_cylinder, region, point, annotate,
                          finish)
```

先跑一遍 demo 建立手感：`python geometry_kit.py --demo`（产物带 `_demo` 后缀，禁交付）。

## 三、构图纪律（六条）

1. **先坐标系后实体再标注**：先 `draw_coord3d`/`draw_coord2d` 立坐标系，再画题目实体
   （`body_circle`/`body_cylinder`/`point`），最后叠加向量/角度/直标。图层顺序即思考顺序。
2. **一切数值来自题目与模型**：坐标、半径、角度、轨迹点列必须取自题目条件或真实
   运行结果，禁止"差不多画一下"。轨迹类图优先用求解代码输出的真实轨迹点。
3. **符号与正文公式一致**：图上写 $\overrightarrow{P_M C_S}$ 就在正文用同一符号；
   数学符号一律 mathtext（`r'$\varepsilon$'`），中文直标用 `annotate()`。
4. **图上直标优先于图例**：阶段名、判定分区、关键数值直接写在图元素旁边
   （`phase_polyline` 的段名直标、`annotate` 的分区注记），读者不回正文找解释。
5. **配色克制**：浅灰几何体（BODY_FACE）+ 每图 1~2 个高亮色（HIGHLIGHT 蓝 /
   WARN_RED 红 / OK_GREEN 绿 / ORANGE 橙），不超 5 个语义色；隐藏轮廓一律虚线。
6. **密度适中偏疏**：元素间留白充足；标注互相遮挡时调 `label_offset`/`label_r`，
   宁删次要标注不叠字。

## 四、QA 闭环（与数据图同构，必须执行）

```python
# 1. finish() 导出后，程序自检布局硬伤（重叠/裁切/缺字）
sys.path.insert(0, "<SKILL_ROOT>/tools/figure/scripts")
from visual_qa import audit_layout
issues = audit_layout(fig)          # WARN/FAIL 必须逐条处理

# 2. 质感门禁
python "<SKILL_ROOT>/tools/figure/scripts/texture_audit.py" <out>.png

# 3. AI 读图：用 Read 工具读 PNG，对照下方验收清单逐项核对
```

**验收清单**（对照范本提炼）：
- [ ] 坐标系轴名、原点 O 齐全且为斜体；
- [ ] 题目实体一眼可辨（谁是谁有直标）；
- [ ] 向量/角度的符号与正文公式完全一致；
- [ ] 判定分区/阶段名图上直标，无歧义；
- [ ] 无标注互相遮挡、无文字压线压点；
- [ ] 配色 ≤5 个语义色，隐藏轮廓为虚线；
- [ ] PNG 300dpi + PDF/SVG 矢量成对导出。

发现问题 → 回改 → 重渲 → 再读，最多 3 轮。

## 五、TikZ 可选后端

几何示意图也可用 TikZ 绘制（精确度更高，适合纯平面几何）。**前提**：本机有 TeX 环境
（`xelatex` 可用）。路线：`standalone` 文档类写 .tex → `xelatex` 编译 PDF →
`pdftoppm -png -r 300` 转 PNG 预览 → 走同一 QA 闭环。无 TeX 环境时不得硬走此路，
回退 geometry_kit（matplotlib）。两后端的验收清单与纪律完全相同。

## 六、与 draw.io 路线的分工

| 图的性质 | 路线 |
|---|---|
| 技术路线图 / 研究框架 / 算法流程 / 系统架构 | draw.io 模板（A/B/C 路径） |
| 轨迹 / 遮蔽 / 投影 / 受力 / 区域判定 / 几何关系 | **geometry_kit（本路线）** |
| 数据驱动的任何图 | tools/figure |

命名仍为 `diagram_qN_*`，产物 PNG+PDF+SVG 成对，审计口径不变（计入正式图、
只补充不替代数据图）。
