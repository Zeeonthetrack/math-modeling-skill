#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nature 风格弦图 / Circos 关系图（模板，改造自 mathmodel-figure-templates）。

视觉技法：类别扇区环（弧长∝类别总流量、扇区着色）+ 贝塞尔缘带连接类别对
（低流量发丝级细带高透明铺垫、高流量粗带高亮，透明度分层由流量分位数驱动）+
放射状类别标签；扇区弧长、缘带宽度与分层阈值全部由流向矩阵计算。

数据契约（--data，方阵 CSV，UTF-8，行列同序）：
    category,HTH,P_loop,GT_B
    HTH,0,2.1,0.8
    P_loop,1.4,0,3.2
    GT_B,0.6,2.8,0
  - 首列 category：类别名（唯一）
  - 其余列名须与首列类别集合一致（顺序不同自动重排），列数必须等于行数
  - M[i,j] = i → j 的流量，须为非负有限数值；对角线（自环）忽略
  - 扇区弧长由行列流量之和（总流量）计算

用法：
    python make_nature_chord_diagram.py --data flows.csv --out figs/chord
    python make_nature_chord_diagram.py --demo    # 确定性模拟数据，产物带 _demo 后缀，
                                                     # 仅用于查看模板效果，不得作为交付物

输出（经 export_figure）：.png(300dpi) + .pdf + .svg + _grayscale.png 灰度预览。
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

if not os.environ.get("MPLCONFIGDIR"):
    os.environ["MPLCONFIGDIR"] = tempfile.mkdtemp(prefix="mpl-")

import matplotlib as mpl

mpl.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.path import Path as MplPath
from matplotlib.patches import PathPatch, Wedge

FIGURE_SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FIGURE_SCRIPTS))

from export_figure import export_figure  # noqa: E402

# Okabe-Ito 色盲安全色板（正式数据模式使用）
OKABE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#F0E442", "#000000"]


# ---- 演示模式（--demo）：保留原模板的确定性模拟与配色，仅用于查看模板效果 ----
@dataclass(frozen=True)
class NodeSpec:
    label: str
    color: str
    weight: float


NODES = [
    NodeSpec("Zn β-ribbon", "#edeaf5", 1.05),
    NodeSpec("KH", "#c6c0dc", 1.05),
    NodeSpec("SHS", "#8176b0", 1.2),
    NodeSpec("TPR", "#6b248b", 1.0),
    NodeSpec("GT-B", "#6a4209", 2.0),
    NodeSpec("GT-A", "#9d5c08", 1.45),
    NodeSpec("ATP-grasp", "#d3ba73", 1.3),
    NodeSpec("AB\nhydrolase", "#ead99f", 2.7),
    NodeSpec("TIM\nbarrel", "#efe7cf", 5.2),
    NodeSpec("Hybrid", "#f4f5f4", 2.7),
    NodeSpec("Acetyltrans", "#bce7df", 1.2),
    NodeSpec("ATPase", "#7dd2c4", 0.7),
    NodeSpec("Actin", "#4fb9ac", 0.82),
    NodeSpec("NADP", "#2a948c", 0.82),
    NodeSpec("Rossmann", "#006d64", 1.0),
    NodeSpec("P-loop\nNTPase", "#007160", 4.4),
    NodeSpec("AAA lid", "#063f38", 1.1),
    NodeSpec("E-set", "#7f1d8d", 0.8),
    NodeSpec("Calycin", "#a65dad", 0.8),
    NodeSpec("Ubiquitin", "#b58ac0", 0.8),
    NodeSpec("RNase H", "#d6c5df", 0.8),
    NodeSpec("PDDEXK", "#eadcf0", 1.0),
    NodeSpec("Cupin", "#f2f2f2", 2.4),
    NodeSpec("Phage barrel", "#e5f0dd", 1.4),
    NodeSpec("Dim A-B barrel", "#a4cf95", 1.8),
    NodeSpec("RING", "#49a65a", 1.5),
    NodeSpec("Peptidase CA", "#18823a", 0.9),
    NodeSpec("Peptidase MA", "#006f38", 1.0),
    NodeSpec("β-Propeller", "#a85a02", 2.0),
    NodeSpec("HTH", "#ca7005", 2.1),
    NodeSpec("Thioredoxin", "#f19926", 1.0),
    NodeSpec("GHD", "#f6c56a", 1.0),
    NodeSpec("OB", "#f2d8a2", 1.2),
    NodeSpec("Pkinase", "#f8edd8", 1.0),
]


def configure_matplotlib() -> None:
    mpl.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Times", "DejaVu Serif", "serif"],
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "font.size": 11,
            "axes.linewidth": 0.8,
        }
    )


def polar_to_xy(theta_deg: float, radius: float) -> np.ndarray:
    theta = np.deg2rad(theta_deg)
    return np.array([radius * np.cos(theta), radius * np.sin(theta)])


def lighten(color: str, amount: float = 0.35) -> tuple[float, float, float]:
    rgb = np.array(mpl.colors.to_rgb(color))
    return tuple(rgb + (1.0 - rgb) * amount)


def text_rotation(theta_deg: float) -> tuple[float, str]:
    angle = theta_deg % 360
    if 90 < angle < 270:
        return theta_deg + 90, "right"
    return theta_deg - 90, "left"


def compute_layout(
    labels: list[str],
    weights: np.ndarray,
    start_angle: float = 124.0,
    gap: float = 0.92,
) -> dict[str, dict[str, float]]:
    total_gap = gap * len(labels)
    total_weight = float(np.sum(weights))
    current = start_angle
    layout: dict[str, dict[str, float]] = {}
    for label, weight in zip(labels, weights, strict=True):
        arc = (360.0 - total_gap) * weight / total_weight
        start = current
        end = current - arc
        layout[label] = {
            "start": start,
            "end": end,
            "mid": (start + end) / 2.0,
            "arc": arc,
        }
        current = end - gap
    return layout


def build_flows(nodes: list[NodeSpec]) -> list[tuple[str, str, float]]:
    # A deterministic, data-like connectivity pattern: a few strong domain
    # families plus many faint background links, as in dense Circos summaries.
    rng = np.random.default_rng(20260629)
    labels = [node.label for node in nodes]
    flows: list[tuple[str, str, float]] = [
        ("TIM\nbarrel", "Hybrid", 13.5),
        ("TIM\nbarrel", "AB\nhydrolase", 9.0),
        ("P-loop\nNTPase", "HTH", 11.0),
        ("P-loop\nNTPase", "GT-B", 8.7),
        ("P-loop\nNTPase", "Acetyltrans", 7.8),
        ("β-Propeller", "HTH", 8.2),
        ("β-Propeller", "Pkinase", 5.4),
        ("RING", "Peptidase CA", 5.8),
        ("RING", "Peptidase MA", 5.0),
        ("GT-B", "GT-A", 5.0),
        ("GT-B", "ATP-grasp", 4.6),
        ("AAA lid", "KH", 4.2),
        ("AAA lid", "SHS", 3.8),
        ("Cupin", "PDDEXK", 3.7),
        ("Cupin", "β-Propeller", 4.0),
        ("OB", "Zn β-ribbon", 3.2),
        ("Thioredoxin", "GHD", 3.1),
        ("AB\nhydrolase", "Rossmann", 4.6),
        ("Actin", "ATPase", 3.4),
        ("NADP", "Rossmann", 3.2),
        ("Dim A-B barrel", "Phage barrel", 3.9),
        ("Dim A-B barrel", "RING", 3.0),
        ("RNase H", "PDDEXK", 3.3),
        ("E-set", "Calycin", 3.2),
        ("Ubiquitin", "P-loop\nNTPase", 3.8),
    ]

    high_weight_labels = np.array([node.label for node in nodes if node.weight > 1.0])
    for _ in range(92):
        source = str(rng.choice(labels))
        if rng.random() < 0.55:
            target = str(rng.choice(high_weight_labels))
        else:
            target = str(rng.choice(labels))
        if source == target:
            continue
        weight = float(rng.gamma(shape=1.35, scale=0.75) + 0.25)
        flows.append((source, target, min(weight, 3.4)))
    return flows


def _demo_matrix() -> tuple[list[str], np.ndarray]:
    flows = build_flows(NODES)
    labels = [node.label for node in NODES]
    index = {label: i for i, label in enumerate(labels)}
    matrix = np.zeros((len(labels), len(labels)), dtype=float)
    for source, target, weight in flows:
        matrix[index[source], index[target]] += weight
    return labels, matrix


# ---------------------------------------------------------------- 真实数据
def load_flow_matrix(csv_path: Path) -> tuple[list[str], np.ndarray]:
    import pandas as pd

    frame = pd.read_csv(csv_path)
    if frame.shape[1] < 2 or frame.iloc[:, 0].isna().any():
        raise SystemExit("流向矩阵至少需要 2 个类别（首列 category + 数值列）")
    labels = [str(v) for v in frame.iloc[:, 0]]
    if len(set(labels)) != len(labels):
        raise SystemExit("首列类别名存在重复")
    columns = [str(c) for c in frame.columns[1:]]
    if len(columns) != len(labels):
        raise SystemExit(f"流向矩阵必须是方阵：当前 {len(labels)} 行 × {len(columns)} 数值列")
    if set(columns) != set(labels):
        missing = sorted(set(labels) - set(columns))
        extra = sorted(set(columns) - set(labels))
        raise SystemExit(f"数值列名与首列类别集合不一致（缺 {missing}，多 {extra}）")
    if columns != labels:
        frame = frame[[frame.columns[0]] + labels]
    matrix = frame[labels].to_numpy(dtype=float)
    if not np.all(np.isfinite(matrix)):
        raise SystemExit("流向矩阵存在缺失/非有限值")
    if matrix.min() < 0:
        raise SystemExit("流向矩阵必须非负（M[i,j] = i→j 流量）")
    return labels, matrix


def flows_from_matrix(matrix: np.ndarray) -> list[tuple[int, int, float]]:
    n = matrix.shape[0]
    return [(i, j, float(matrix[i, j])) for i in range(n) for j in range(n) if i != j and matrix[i, j] > 0]


# ---------------------------------------------------------------- 绘制
def ribbon_patch(
    start_angle: float,
    end_angle: float,
    width: float,
    color: str,
    radius: float = 0.805,
    alpha: float = 0.26,
    zorder: int = 2,
) -> PathPatch:
    width = min(max(width, 0.20), 8.0)
    s1, s2 = start_angle - width / 2, start_angle + width / 2
    e1, e2 = end_angle + width / 2, end_angle - width / 2

    p0 = polar_to_xy(s1, radius)
    p1 = polar_to_xy(e1, radius)
    p2 = polar_to_xy(e2, radius)
    p3 = polar_to_xy(s2, radius)
    c0 = polar_to_xy(s1, radius * 0.20)
    c1 = polar_to_xy(e1, radius * 0.20)
    c2 = polar_to_xy(e2, radius * 0.20)
    c3 = polar_to_xy(s2, radius * 0.20)

    vertices = [
        p0,
        c0,
        c1,
        p1,
        p2,
        c2,
        c3,
        p3,
        p0,
    ]
    codes = [
        MplPath.MOVETO,
        MplPath.CURVE4,
        MplPath.CURVE4,
        MplPath.CURVE4,
        MplPath.LINETO,
        MplPath.CURVE4,
        MplPath.CURVE4,
        MplPath.CURVE4,
        MplPath.CLOSEPOLY,
    ]
    return PathPatch(MplPath(vertices, codes), facecolor=color, edgecolor="none", alpha=alpha, zorder=zorder)


def draw_sector_ring(ax: plt.Axes, layout: dict[str, dict[str, float]], labels: list[str], colors: list[str]) -> None:
    ax.add_patch(Wedge((0, 0), 1.075, 0, 360, width=0.105, facecolor="#eeeeee", edgecolor="none", alpha=0.85, zorder=0))
    for label, color in zip(labels, colors, strict=True):
        item = layout[label]
        ax.add_patch(
            Wedge(
                (0, 0),
                1.000,
                theta1=item["end"],
                theta2=item["start"],
                width=0.115,
                facecolor=color,
                edgecolor="#3a3a3a",
                linewidth=0.38,
                zorder=5,
            )
        )
        ax.add_patch(
            Wedge(
                (0, 0),
                0.885,
                theta1=item["end"],
                theta2=item["start"],
                width=0.006,
                facecolor="#e8e8e8",
                edgecolor="none",
                zorder=5,
            )
        )


def draw_labels(ax: plt.Axes, layout: dict[str, dict[str, float]], labels: list[str]) -> None:
    for idx, label in enumerate(labels):
        mid = layout[label]["mid"]
        rotation, ha = text_rotation(mid)
        arc = layout[label]["arc"]
        radius = 1.145
        if arc < 7.0:
            radius += (idx % 3) * 0.045
        size = 11.8 if arc > 7.0 else 9.6
        if len(label.replace("\n", "")) > 11:
            size -= 0.7
        ax.text(
            *polar_to_xy(mid, radius),
            label,
            rotation=rotation,
            rotation_mode="anchor",
            ha=ha,
            va="center",
            fontsize=size,
            color="#090909",
            zorder=8,
        )


def make_figure(
    labels: list[str],
    matrix: np.ndarray,
    output_stem: Path,
    *,
    colors: list[str] | None = None,
) -> list[str]:
    configure_matplotlib()
    n = len(labels)
    colors = list(colors) if colors else [OKABE[k % len(OKABE)] for k in range(n)]

    off_diagonal = matrix.copy()
    np.fill_diagonal(off_diagonal, 0.0)
    flows = flows_from_matrix(off_diagonal)
    if not flows:
        raise SystemExit("流向矩阵无非对角正值，没有可绘制的流")
    weights = off_diagonal.sum(axis=1) + off_diagonal.sum(axis=0)
    gap = min(0.92, 340.0 / n)
    layout = compute_layout(labels, weights, start_angle=124.0, gap=gap)

    flow_values = np.array([weight for _, _, weight in flows])
    q50 = float(np.quantile(flow_values, 0.50))
    q90 = float(np.quantile(flow_values, 0.90))
    max_w = float(flow_values.max())
    scale = q90 if q90 > 0 else max_w

    fig, ax = plt.subplots(figsize=(10.6, 10.6), facecolor="white")
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(-1.38, 1.38)
    ax.set_ylim(-1.34, 1.39)

    # First draw faint hairline links to create the dense Nature-style chord texture.
    sorted_flows = sorted(flows, key=lambda item: item[2])
    angle_rng = np.random.default_rng(9817)
    for source, target, weight in sorted_flows:
        s_arc = layout[labels[source]]["arc"]
        t_arc = layout[labels[target]]["arc"]
        s_mid = layout[labels[source]]["mid"] + angle_rng.uniform(-0.34 * s_arc, 0.34 * s_arc)
        t_mid = layout[labels[target]]["mid"] + angle_rng.uniform(-0.34 * t_arc, 0.34 * t_arc)
        source_color = colors[source]
        if weight > q90:  # 强流：粗带高亮
            alpha, zorder = 0.26, 3
            ribbon_width = 0.55 + 1.60 * (weight / max_w)
        elif weight > q50:  # 中等流：细带
            alpha, zorder = 0.14, 1
            ribbon_width = 0.20 + 0.40 * (weight / scale)
        else:  # 背景发丝带
            alpha, zorder = 0.08, 1
            ribbon_width = 0.20 + 0.40 * (weight / scale)
        patch = ribbon_patch(
            s_mid,
            t_mid,
            ribbon_width,
            lighten(source_color, amount=0.18),
            alpha=alpha,
            zorder=zorder,
        )
        ax.add_patch(patch)

    draw_sector_ring(ax, layout, labels, colors)
    draw_labels(ax, layout, labels)

    return export_figure(
        fig,
        str(output_stem),
        formats=["pdf", "svg", "png"],
        size_inches=(10.6, 10.6),
        dpi=300,
        grayscale_preview=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Nature 风格弦图 / Circos 关系图（真实数据驱动模板）")
    parser.add_argument("--data", type=Path, help="流向方阵 CSV（契约见头部 docstring）")
    parser.add_argument("--out", type=Path, help="输出文件名前缀（不含扩展名）")
    parser.add_argument("--demo", action="store_true", help="确定性模拟数据演示，产物带 _demo 后缀")
    args = parser.parse_args()

    if args.demo:
        labels, matrix = _demo_matrix()
        colors = [node.color for node in NODES]
        out = args.out or Path("nature_chord_diagram_demo")
    elif args.data:
        labels, matrix = load_flow_matrix(args.data)
        colors = None
        out = args.out or Path("nature_chord_diagram")
    else:
        parser.error("需要 --data <csv> 或 --demo")

    outputs = make_figure(labels, matrix, out, colors=colors)
    for path in outputs:
        print(path)


if __name__ == "__main__":
    main()
