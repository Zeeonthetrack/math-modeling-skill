#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""题意沉浸几何/物理示意图工具箱（geometry kit）——matplotlib 后端，零新增依赖。

定位（对照国一论文范本图5-2/5-3/6-2 提炼）：
画"长出题目样子"的示意图——坐标系、题目实体（导弹/云团/圆柱体/机器人/炉膛…）、
向量、角度、轨迹分段、判定分区，全部以**真实模型参数**绘制，图上直标符号与中文。
与 draw.io 路线的分工：框线结构图（技术路线/流程/架构）走 draw.io 模板；
几何沉浸示意图走本工具箱。

用法：import 本模块，用积木函数拼装，最后 finish() 导出 PNG(300)+PDF+SVG。
画布为 2D 伪 3D（斜二测投影 proj3），所有坐标先在"题目坐标系"里想好再画。

    from geometry_kit import (new_canvas, draw_coord3d, vector, angle_arc,
                              body_circle, body_cylinder, phase_polyline,
                              annotate, finish)

QA 闭环（必须执行）：
    1. finish() 导出后用 tools/figure/scripts/visual_qa.py 的 audit_layout 抓重叠/裁切
    2. 用 Read 工具读 PNG 逐项核对 references/geometry-diagrams.md 的验收清单
    3. 发现问题回改，最多 3 轮

纪律：图中一切坐标/数值/符号必须来自题目与模型，禁止编造；符号写法与正文公式一致。

CLI: ``python geometry_kit.py --demo`` 生成一张投影判定风格示意图（_demo 后缀，禁交付）。
"""
from __future__ import annotations

import math
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", tempfile.mkdtemp(prefix="mpl-"))

import matplotlib as mpl

mpl.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Arc, Circle, Ellipse, FancyArrowPatch, Polygon, Wedge

# 复用 figure 工具的中文字体配置与导出器（同在 skill 内）
_FIGURE_SCRIPTS = Path(__file__).resolve().parents[2] / "figure" / "scripts"
if _FIGURE_SCRIPTS.is_dir():
    sys.path.insert(0, str(_FIGURE_SCRIPTS))

# 浅灰几何体 + 克制高亮色（范本实测配色）
BODY_FACE = "#E3E7EB"      # 浅灰蓝填充
BODY_EDGE = "#4A5568"      # 深灰描边
HIDDEN_LS = (0, (4, 3))    # 虚线隐藏轮廓
HIGHLIGHT = "#3182CE"      # 高亮蓝
WARN_RED = "#C53030"
OK_GREEN = "#2F855A"
ORANGE = "#DD6B20"
AXIS_COLOR = "#1A202C"


def _setup_fonts() -> None:
    try:
        from setup_style import configure_chinese_fonts
        configure_chinese_fonts()
    except Exception:  # noqa: BLE001 - 字体兜底不阻塞绘图
        mpl.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    mpl.rcParams.update({
        "axes.unicode_minus": False,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "font.size": 10.5,
    })


# ---------------------------------------------------------------------------
# 画布与坐标系
# ---------------------------------------------------------------------------

def new_canvas(xlim=(0, 10), ylim=(0, 7), width_in=6.0):
    """白底 2D 画布：隐藏坐标轴、等比、按题意坐标系定界。"""
    _setup_fonts()
    aspect = (ylim[1] - ylim[0]) / (xlim[1] - xlim[0])
    fig, ax = plt.subplots(figsize=(width_in, width_in * aspect), layout="constrained")
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect("equal")
    ax.axis("off")
    return fig, ax


def proj3(x, y, z, y_deg=210, y_scale=0.5):
    """斜二测投影：3D 题意坐标 → 2D 画布坐标。

    X 轴水平向右，Z 轴竖直向上，Y 轴按 y_deg（默认 210°，左下）以 y_scale 压缩。
    """
    rad = math.radians(y_deg)
    return (x + y * y_scale * math.cos(rad),
            z + y * y_scale * math.sin(rad))


def draw_coord3d(ax, origin=(0, 0, 0), lengths=(4, 3, 3), labels=("X", "Y", "Z"),
                 y_deg=210, y_scale=0.5, lw=1.6):
    """手绘风三维坐标轴（箭头 + 斜体轴名 + 原点 O）。返回投影函数。"""
    _setup_fonts()
    o = proj3(*origin, y_deg, y_scale)
    ends = [
        proj3(origin[0] + lengths[0], origin[1], origin[2], y_deg, y_scale),
        proj3(origin[0], origin[1] + lengths[1], origin[2], y_deg, y_scale),
        proj3(origin[0], origin[1], origin[2] + lengths[2], y_deg, y_scale),
    ]
    for end, name in zip(ends, labels):
        ax.add_patch(FancyArrowPatch(o, end, arrowstyle="-|>", mutation_scale=16,
                                     lw=lw, color=AXIS_COLOR, zorder=5))
        ax.text(end[0] + 0.12, end[1] + 0.05, name, style="italic",
                fontsize=13, fontweight="bold", color=AXIS_COLOR)
    ax.text(o[0] - 0.18, o[1] - 0.28, "O", fontsize=12, color=AXIS_COLOR)
    return lambda p: proj3(p[0], p[1], p[2], y_deg, y_scale)


def draw_coord2d(ax, origin=(0, 0), x_len=8, y_len=5, labels=("x", "y"),
                 lw=1.6):
    """二维箭头坐标轴。"""
    _setup_fonts()
    ox, oy = origin
    for end, name in (((ox + x_len, oy), labels[0]), ((ox, oy + y_len), labels[1])):
        ax.add_patch(FancyArrowPatch(origin, end, arrowstyle="-|>", mutation_scale=16,
                                     lw=lw, color=AXIS_COLOR, zorder=5))
        ax.text(end[0] + 0.10, end[1] + 0.05, name, style="italic",
                fontsize=13, fontweight="bold", color=AXIS_COLOR)
    ax.text(ox - 0.22, oy - 0.30, "O", fontsize=12, color=AXIS_COLOR)


# ---------------------------------------------------------------------------
# 向量 / 角度 / 轨迹
# ---------------------------------------------------------------------------

def vector(ax, p0, p1, label=None, color=HIGHLIGHT, lw=1.8, ls="-",
           label_offset=(0.12, 0.12), mutation=15):
    """带箭头向量；label 用斜体（数学符号请传 mathtext，如 r'$\\vec{v}$'）。"""
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=mutation,
                                 lw=lw, ls=ls, color=color, zorder=6))
    if label:
        mid = ((p0[0] + p1[0]) / 2 + label_offset[0],
               (p0[1] + p1[1]) / 2 + label_offset[1])
        ax.text(mid[0], mid[1], label, fontsize=11, color=color, zorder=7)


def angle_arc(ax, vertex, pa, pb, radius=0.8, label=None, color=WARN_RED,
              lw=1.4, label_r=1.35):
    """顶点 vertex 处从 pa 到 pb 的角弧 + 标注（如 r'$\\varepsilon$'）。"""
    a0 = math.degrees(math.atan2(pa[1] - vertex[1], pa[0] - vertex[0]))
    a1 = math.degrees(math.atan2(pb[1] - vertex[1], pb[0] - vertex[0]))
    if a1 < a0:
        a0, a1 = a1, a0
    ax.add_patch(Arc(vertex, radius * 2, radius * 2, angle=0,
                     theta1=a0, theta2=a1, lw=lw, color=color, zorder=6))
    mid = math.radians((a0 + a1) / 2)
    if label:
        ax.text(vertex[0] + radius * label_r * math.cos(mid),
                vertex[1] + radius * label_r * math.sin(mid),
                label, fontsize=11, color=color, ha="center", va="center", zorder=7)


def phase_polyline(ax, pts, phases, node_size=52, lw=2.0, label_dy=0.30):
    """分段着色轨迹：pts 为点列，phases 为 [(段名, 颜色, 起点索引), ...]。

    每一段一种颜色，节点白边圆点，段名直标在段中点上方——复刻范本图5-2 的分阶段表达。
    """
    for k, (name, color, start) in enumerate(phases):
        end = phases[k + 1][2] + 1 if k + 1 < len(phases) else len(pts)
        seg = pts[start:end]
        if len(seg) >= 2:
            xs, ys = zip(*seg)
            ax.plot(xs, ys, color=color, lw=lw, zorder=4, solid_capstyle="round")
            ax.scatter(xs, ys, s=node_size, color=color, edgecolor="white",
                       linewidth=1.0, zorder=5)
            mid = len(seg) // 2
            ax.text(xs[mid], ys[mid] + label_dy, name, fontsize=10.5,
                    color=color, ha="center", zorder=7)


# ---------------------------------------------------------------------------
# 几何体（浅灰填充 + 深色描边 + 可高亮）
# ---------------------------------------------------------------------------

def body_circle(ax, center, r, face=BODY_FACE, edge=BODY_EDGE, lw=1.4,
                highlight_wedge=None, hidden_arc=None, z=3):
    """圆/球截面。highlight_wedge=(θ1, θ2, color) 叠加高亮扇区；
    hidden_arc=(θ1, θ2) 画虚线隐藏轮廓。"""
    ax.add_patch(Circle(center, r, facecolor=face, edgecolor=edge, lw=lw, zorder=z))
    if highlight_wedge:
        t1, t2, color = highlight_wedge
        ax.add_patch(Wedge(center, r, t1, t2, facecolor=color, alpha=0.35,
                           edgecolor=color, lw=1.0, zorder=z + 1))
    if hidden_arc:
        t1, t2 = hidden_arc
        ax.add_patch(Arc(center, r * 2, r * 2, theta1=t1, theta2=t2,
                         ls=HIDDEN_LS, lw=1.0, color=edge, zorder=z + 1))


def body_cylinder(ax, center_bottom, rx, ry, h, face=BODY_FACE, edge=BODY_EDGE,
                  lw=1.4, z=3):
    """斜二测圆柱体：顶/底椭圆 + 两侧母线，底椭圆后半画虚线（被遮轮廓）。"""
    cx, cy = center_bottom
    ax.add_patch(Polygon([(cx - rx, cy), (cx - rx, cy + h), (cx + rx, cy + h),
                          (cx + rx, cy)], closed=True,
                         facecolor=face, edgecolor="none", zorder=z))
    ax.add_patch(Ellipse((cx, cy + h), rx * 2, ry * 2, facecolor=face,
                         edgecolor=edge, lw=lw, zorder=z + 1))
    ax.add_patch(Arc((cx, cy), rx * 2, ry * 2, theta1=180, theta2=360,
                     lw=lw, color=edge, zorder=z + 1))
    ax.add_patch(Arc((cx, cy), rx * 2, ry * 2, theta1=0, theta2=180,
                     ls=HIDDEN_LS, lw=1.0, color=edge, zorder=z + 1))
    for sx in (-rx, rx):
        ax.plot([cx + sx, cx + sx], [cy, cy + h], lw=lw, color=edge, zorder=z + 1)


def region(ax, verts, face=HIGHLIGHT, alpha=0.10, edge=None, ls="--", z=2):
    """半透明判定区域（如遮挡锥/可达域）。"""
    ax.add_patch(Polygon(verts, closed=True, facecolor=face, alpha=alpha,
                         edgecolor=edge or face, ls=ls, lw=1.0, zorder=z))


def annotate(ax, xy, text, fontsize=10.5, color="#2D3748", ha="left", **kw):
    """中文图上直标（阶段名/判定分区/关键说明）。"""
    ax.text(xy[0], xy[1], text, fontsize=fontsize, color=color, ha=ha,
            va="center", zorder=8, **kw)


def point(ax, xy, label=None, color=WARN_RED, size=42, dx=0.14, dy=0.14, z=9):
    """关键点 + 标签（如 目标P、导弹M）。"""
    ax.scatter([xy[0]], [xy[1]], s=size, color=color, edgecolor="white",
               linewidth=1.0, zorder=z)
    if label:
        ax.text(xy[0] + dx, xy[1] + dy, label, fontsize=11, color=color, zorder=z)


# ---------------------------------------------------------------------------
# 导出
# ---------------------------------------------------------------------------

def finish(fig, out_stem, formats=("png", "pdf", "svg"), dpi=300):
    """导出 PNG(300)+PDF+SVG 三件套；返回写出的文件列表。"""
    out = Path(out_stem)
    out.parent.mkdir(parents=True, exist_ok=True)
    written = []
    try:
        from export_figure import export_figure
        written = export_figure(fig, str(out), formats=list(formats), dpi=dpi)
    except Exception:  # noqa: BLE001 - figure 工具不可用时的兜底
        for fmt in formats:
            p = f"{out}.{fmt}"
            fig.savefig(p, dpi=dpi, bbox_inches="tight")
            written.append(p)
    for w in written:
        print(f"  written: {w}")
    return written


# ---------------------------------------------------------------------------
# demo：投影判定风格示意图（复刻范本图6-2 的构图语言）
# ---------------------------------------------------------------------------

def _demo(out_stem: str) -> None:
    fig, ax = new_canvas(xlim=(-1, 11), ylim=(-1.5, 8), width_in=6.2)
    P = draw_coord3d(ax, origin=(0, 0, 0), lengths=(6.5, 4.5, 5.5))

    # 题目实体：目标圆柱 P、烟幕云团球 C、导弹 M（示例坐标）
    body_cylinder(ax, P((0.6, 0, 0)), rx=0.45, ry=0.28, h=1.5)
    c3 = (3.2, 0.8, 2.4)
    c2 = P(c3)
    m2 = P((6.0, 1.6, 4.6))
    tp = P((0.6, 0, 1.2))
    # 高亮扇区朝向导弹方向（可见轮廓侧）
    theta_m = math.degrees(math.atan2(m2[1] - c2[1], m2[0] - c2[0]))
    body_circle(ax, c2, 0.85, highlight_wedge=(theta_m - 30, theta_m + 30, HIGHLIGHT))
    annotate(ax, (c2[0] - 1.05, c2[1] + 1.15), "烟幕云团中心 $C_S(t)$", ha="right")
    point(ax, m2, label="导弹 $M$", color=WARN_RED, dx=0.2, dy=0.18)
    annotate(ax, (tp[0] + 0.1, tp[1] + 0.75), "真目标 $P$", color=OK_GREEN)

    # 视线与向量（标签沿各自垂直方向错开，防叠字）
    vector(ax, m2, tp, label=r"$\overrightarrow{P_M P}$", color=AXIS_COLOR, lw=1.5,
           label_offset=(0.05, -0.42))
    vector(ax, m2, c2, label=r"$\overrightarrow{P_M C_S}$", color=HIGHLIGHT, lw=1.8,
           label_offset=(0.30, 0.42))
    angle_arc(ax, m2, tp, c2, radius=1.5, label=r"$\varepsilon$", label_r=1.75)

    # 遮挡锥区域 + 判定分区直标
    region(ax, [tp, P((3.2, 0.8, 3.25)), P((3.2, 0.8, 1.55))], face=HIGHLIGHT)
    annotate(ax, (7.6, 6.6), "遮挡：$\\varepsilon \\in (0,1]$", color=HIGHLIGHT)
    annotate(ax, (7.6, 6.0), "临界：$\\varepsilon = 0$", color=ORANGE)
    annotate(ax, (7.6, 5.4), "不遮挡：$\\varepsilon \\leq 0$ 或 $\\varepsilon > 1$",
             color="#2D3748")

    finish(fig, out_stem)
    print("[demo] 演示产物带 _demo 后缀，仅用于查看工具箱效果，禁止作为交付物。")


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="题意沉浸几何示意图工具箱")
    p.add_argument("--demo", action="store_true")
    p.add_argument("--out", default="figs/diagram_geometry")
    args = p.parse_args()
    if args.demo:
        out = args.out if args.out.endswith("_demo") else args.out + "_demo"
        _demo(out)
    else:
        p.print_help()
