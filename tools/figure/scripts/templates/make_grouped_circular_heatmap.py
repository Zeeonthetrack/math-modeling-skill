#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分组环形热图（模板，改造自 mathmodel-figure-templates）。

视觉技法：极坐标多环热图——特征沿圆周排列（外圈放射状标签），最内层组环按
特征分组连续着色，每个条件一环（组色派生的双色发散色图，|v| 达峰值 82% 以上
标星号高亮），中心分组图例 + 右侧逐条件 colorbar。

数据契约（--data，宽表矩阵 CSV，UTF-8）：
    feature,condA,condB,condC
    f1,2.3,-1.1,0.4
    f2,-0.8,3.2,1.7
    f3,0.5,0.9,-2.4
  - 首列 feature：行标签（沿圆周排列，绘图时自动按组归拢），须唯一
  - 其余列：各条件/样本数值（每列渲染为一环，须为有限数值，至少 1 列）

--groups CSV（列：feature,group）：
    feature,group
    f1,Metabolism
    f2,Metabolism
    f3,Climate
  - 每个特征都必须有分组记录，驱动组环着色与扇区归拢

用法：
    python make_grouped_circular_heatmap.py --data matrix.csv --groups groups.csv --out figs/circ_heatmap
    python make_grouped_circular_heatmap.py --demo    # 确定性模拟数据，产物带 _demo 后缀，
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
from matplotlib.patches import Patch, Rectangle

FIGURE_SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FIGURE_SCRIPTS))

from export_figure import export_figure  # noqa: E402

# Okabe-Ito 色盲安全色板（正式数据模式使用）
OKABE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#F0E442", "#000000"]


# ---- 演示模式（--demo）：保留原模板的确定性模拟与配色，仅用于查看模板效果 ----
@dataclass(frozen=True)
class TraitSpec:
    name: str
    color: str
    pale: str


@dataclass(frozen=True)
class PairGroup:
    label: str
    color: str
    count: int


TRAITS_OUTER_TO_INNER = [
    TraitSpec("Insomnia", "#51448a", "#e7e4f2"),
    TraitSpec("Sleep duration", "#606766", "#ededeb"),
    TraitSpec("Long sleep", "#4e9568", "#e2f0e4"),
    TraitSpec("Short sleep", "#bd454c", "#f5dddd"),
    TraitSpec("Chronotype", "#7b54b9", "#ece3f6"),
    TraitSpec("Morningness", "#3d719b", "#e3edf5"),
    TraitSpec("Napping frequency", "#e58a50", "#f9e4d5"),
    TraitSpec("Sleepiness", "#5d6a67", "#e3e9e8"),
]


PAIR_GROUPS = [
    PairGroup("Sleep traits to cortical surface area", "#a9d9e8", 10),
    PairGroup("Sleep traits to cortical thickness", "#1f79b5", 10),
    PairGroup("Sleep traits to subcortical volume", "#9ee48e", 10),
    PairGroup("Sleep traits to longitudinal change", "#22a33a", 10),
    PairGroup("Cortical surface area to sleep traits", "#f28a9e", 12),
    PairGroup("Cortical thickness to sleep traits", "#f7ba67", 12),
    PairGroup("Subcortical volume to sleep traits", "#c8b3d8", 14),
    PairGroup("Longitudinal change to sleep traits", "#7b3db6", 14),
]


def configure_matplotlib() -> None:
    mpl.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Times", "DejaVu Serif", "serif"],
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "font.size": 10,
            "axes.linewidth": 0.8,
        }
    )


def lighten(color: str, amount: float = 0.35) -> tuple[float, float, float]:
    rgb = np.array(mpl.colors.to_rgb(color))
    return tuple(rgb + (1.0 - rgb) * amount)


def make_ring_cmap(color: str, name: str) -> mpl.colors.LinearSegmentedColormap:
    pale = lighten(color, 0.72)
    return mpl.colors.LinearSegmentedColormap.from_list(
        name,
        [(0.00, color), (0.35, pale), (0.50, "#ffffff"), (0.65, pale), (1.00, color)],
    )


def make_trait_cmap(spec: TraitSpec) -> mpl.colors.LinearSegmentedColormap:
    return mpl.colors.LinearSegmentedColormap.from_list(
        f"{spec.name.replace(' ', '_')}_magnitude",
        [
            (0.00, spec.color),
            (0.35, spec.pale),
            (0.50, "#ffffff"),
            (0.65, spec.pale),
            (1.00, spec.color),
        ],
    )


def simulate_heatmap_values(seed: int = 20260629, n_traits: int = 8, n_items: int = 92) -> np.ndarray:
    rng = np.random.default_rng(seed)
    theta = np.linspace(0, 2 * np.pi, n_items, endpoint=False)
    values = np.zeros((n_traits, n_items), dtype=float)

    group_offsets = np.repeat(np.linspace(-0.85, 0.95, len(PAIR_GROUPS)), [g.count for g in PAIR_GROUPS])
    for trait_idx in range(n_traits):
        phase = trait_idx * 0.72
        wave = 1.35 * np.sin(theta * (1.0 + trait_idx % 3) + phase)
        wave += 0.95 * np.cos(theta * (2.3 + trait_idx / 6.0) - phase * 0.6)
        structured = wave + group_offsets * (0.65 - trait_idx * 0.035)
        noise = rng.normal(0, 1.25, n_items)
        values[trait_idx] = structured + noise

    strong_cells = [
        (0, 4, 4.7),
        (1, 15, -4.5),
        (2, 21, 4.3),
        (3, 31, -4.7),
        (4, 39, 4.5),
        (5, 53, -4.4),
        (6, 66, 4.2),
        (7, 74, -4.6),
        (2, 84, 4.7),
        (3, 88, -4.3),
    ]
    for trait_idx, item_idx, value in strong_cells:
        values[trait_idx, item_idx] = value

    return np.clip(values * 1.16, -5, 5)


def _demo_data() -> tuple[list[str], list[str], np.ndarray, list[tuple[str, list[str]]], list[str], list[mpl.colors.Colormap]]:
    values = simulate_heatmap_values()
    n_traits, n_items = values.shape
    features = [f"Item {i + 1:02d}" for i in range(n_items)]
    conditions = [f"Condition {k + 1}" for k in range(n_traits)]
    groups: list[tuple[str, list[str]]] = []
    start = 0
    for gi, group in enumerate(PAIR_GROUPS):
        groups.append((f"Group {chr(ord('A') + gi)}", features[start : start + group.count]))
        start += group.count
    group_colors = [group.color for group in PAIR_GROUPS]
    cmaps = [make_trait_cmap(spec) for spec in TRAITS_OUTER_TO_INNER]
    return features, conditions, values.T, groups, group_colors, cmaps  # 行=特征，列=条件


# ---------------------------------------------------------------- 真实数据
def load_matrix(csv_path: Path) -> tuple[list[str], list[str], np.ndarray]:
    import pandas as pd

    frame = pd.read_csv(csv_path)
    if frame.shape[1] < 2 or frame.iloc[:, 0].isna().any():
        raise SystemExit("数据至少需要首列 feature 外加 1 列条件数值")
    features = [str(v) for v in frame.iloc[:, 0]]
    if len(set(features)) != len(features):
        raise SystemExit("首列 feature 存在重复行标签")
    if len(features) < 2:
        raise SystemExit("至少需要 2 个特征行")
    conditions = [str(c) for c in frame.columns[1:]]
    if len(set(conditions)) != len(conditions):
        raise SystemExit("条件列存在重名列")
    values = frame[conditions].to_numpy(dtype=float)
    if not np.all(np.isfinite(values)):
        raise SystemExit("数值列存在缺失/非有限值")
    return features, conditions, values


def load_groups(csv_path: Path, features: list[str]) -> list[tuple[str, list[str]]]:
    import pandas as pd

    frame = pd.read_csv(csv_path)
    missing = {"feature", "group"} - set(frame.columns)
    if missing:
        raise SystemExit(f"分组文件缺少必需列：{sorted(missing)}（契约：feature,group）")
    mapping: dict[str, str] = {}
    for feature, group in zip(frame["feature"].astype(str), frame["group"].astype(str)):
        if feature in mapping and mapping[feature] != group:
            raise SystemExit(f"特征 {feature} 在分组文件中出现冲突的分组记录")
        mapping[feature] = group
    unknown = sorted(set(mapping) - set(features))
    if unknown:
        raise SystemExit(f"分组文件包含矩阵中不存在的特征：{unknown}")
    unmapped = [f for f in features if f not in mapping]
    if unmapped:
        raise SystemExit(f"以下特征缺少分组记录：{unmapped}")
    ordered: list[tuple[str, list[str]]] = []
    index: dict[str, int] = {}
    for feature in features:
        group = mapping[feature]
        if group not in index:
            index[group] = len(ordered)
            ordered.append((group, []))
        ordered[index[group]][1].append(feature)
    return ordered


# ---------------------------------------------------------------- 绘制
def draw_ring_cells(
    ax: plt.Axes,
    theta: np.ndarray,
    width: float,
    radius: float,
    height: float,
    values: np.ndarray,
    cmap: mpl.colors.Colormap,
    norm: mpl.colors.Normalize,
) -> None:
    colors = cmap(norm(values))
    ax.bar(
        theta,
        np.full_like(theta, height),
        width=width,
        bottom=radius,
        color=colors,
        edgecolor="white",
        linewidth=0.55,
        align="center",
    )


def draw_group_ring(
    ax: plt.Axes,
    theta: np.ndarray,
    width: float,
    radius: float,
    height: float,
    colors: list[str],
) -> None:
    for angle, color in zip(theta, colors, strict=True):
        ax.bar(
            angle,
            height,
            width=width,
            bottom=radius,
            color=color,
            edgecolor="white",
            linewidth=0.55,
            align="center",
        )


def text_rotation(angle_deg: float) -> tuple[float, str]:
    normalized = angle_deg % 360
    if 90 < normalized < 270:
        return angle_deg + 90, "right"
    return angle_deg - 90, "left"


def draw_outer_labels(
    ax: plt.Axes,
    theta: np.ndarray,
    radius: float,
    labels: list[str],
    start_angle: float,
    step_angle: float,
) -> None:
    for idx, (angle, label) in enumerate(zip(theta, labels, strict=True)):
        angle_deg = start_angle + (idx + 0.5) * step_angle
        rotation, ha = text_rotation(angle_deg)
        ax.text(
            angle,
            radius,
            label,
            rotation=rotation,
            rotation_mode="anchor",
            ha=ha,
            va="center",
            fontsize=6.5,
            color="#111111",
        )


def draw_stars(
    ax: plt.Axes,
    theta: np.ndarray,
    values: np.ndarray,
    ring_radii_inner_to_outer: list[float],
    ring_height: float,
    threshold: float,
) -> None:
    outer_to_inner_index = list(reversed(range(values.shape[0])))
    candidates = np.argwhere(np.abs(values) > threshold)
    for ring_outer_idx, item_idx in candidates:
        inner_order_idx = outer_to_inner_index[ring_outer_idx]
        radius = ring_radii_inner_to_outer[inner_order_idx] + ring_height * 0.50
        ax.text(theta[item_idx], radius, "*", ha="center", va="center", color="#f8f8f8", fontsize=11, fontweight="bold")


def add_colorbar_stack(
    fig: plt.Figure,
    ring_names: list[str],
    cmaps: list[mpl.colors.Colormap],
    norm: mpl.colors.Normalize,
    vmax: float,
) -> None:
    n = len(ring_names)
    left = 0.735
    bottom_top = 0.764
    width = 0.095
    height = 0.014
    gap = 0.035 if n <= 8 else max(0.012, 0.75 / n)
    label_fs = 11 if gap >= 0.03 else max(6.0, gap * 300)
    gradient = np.linspace(-vmax, vmax, 300).reshape(1, -1)
    tick_labels = [f"{value:.2g}" for value in (-vmax, 0.0, vmax)]

    fig.patches.append(
        Rectangle(
            (left - 0.010, bottom_top - (n - 1) * gap - 0.010),
            0.245,
            (n - 1) * gap + height + 0.030,
            transform=fig.transFigure,
            facecolor="white",
            edgecolor="none",
            zorder=2,
        )
    )

    for idx, (name, cmap) in enumerate(zip(ring_names, cmaps, strict=True)):
        bottom = bottom_top - idx * gap
        cax = fig.add_axes([left, bottom, width, height])
        cax.set_zorder(3)
        cax.imshow(gradient, aspect="auto", cmap=cmap, norm=norm, extent=(-vmax, vmax, 0, 1))
        cax.axvline(0, color="#333333", lw=0.8, ls=(0, (3, 2)))
        cax.set_yticks([])
        cax.set_xticks([-vmax, 0.0, vmax])
        cax.set_xticklabels(tick_labels, fontsize=8)
        cax.tick_params(axis="x", length=0, pad=1)
        for spine in cax.spines.values():
            spine.set_color("#111111")
            spine.set_linewidth(0.8)
        fig.text(left + width + 0.014, bottom + height / 2, name, va="center", ha="left", fontsize=label_fs, zorder=3)


def add_center_legend(fig: plt.Figure, groups: list[tuple[str, str]]) -> None:
    left, bottom, width, height = 0.372, 0.410, 0.295, 0.205
    ax = fig.add_axes([left, bottom, width, height])
    ax.set_zorder(4)
    ax.axis("off")
    ax.text(0.00, 1.02, "Feature groups", fontsize=10, fontweight="bold", ha="left", va="bottom")

    handles = [Patch(facecolor=color, edgecolor="white", label=name) for name, color in groups]
    fontsize = 8.3 if len(groups) <= 8 else max(5.0, 8.3 * 8 / len(groups))
    ax.legend(
        handles=handles,
        loc="upper left",
        bbox_to_anchor=(0.00, 0.98),
        frameon=False,
        fontsize=fontsize,
        handlelength=1.2,
        handleheight=1.2,
        borderaxespad=0,
        labelspacing=0.55,
    )


def make_figure(
    features: list[str],
    conditions: list[str],
    values: np.ndarray,
    groups: list[tuple[str, list[str]]],
    output_stem: Path,
    *,
    group_colors: list[str] | None = None,
    cmaps: list[mpl.colors.Colormap] | None = None,
) -> list[str]:
    configure_matplotlib()
    n_items = len(features)
    n_rings = len(conditions)
    group_colors = list(group_colors) if group_colors else [OKABE[k % len(OKABE)] for k in range(len(groups))]
    if cmaps is None:
        cmaps = [make_ring_cmap(OKABE[k % len(OKABE)], f"ring_{k}") for k in range(n_rings)]

    # 扇区按组归拢排列（组间按组首次出现顺序，组内保持数据原序）
    order = [feature for _, members in groups for feature in members]
    position = {feature: i for i, feature in enumerate(features)}
    matrix = values[[position[feature] for feature in order], :].T  # 行=条件（环），列=重排后特征（扇区）
    sector_colors = [group_colors[gi] for gi, (_, members) in enumerate(groups) for _ in members]

    vmax = float(np.abs(matrix).max())
    if not np.isfinite(vmax) or vmax <= 0:
        vmax = 1.0
    norm = mpl.colors.Normalize(vmin=-vmax, vmax=vmax)

    start_angle = 82.0
    span_angle = 322.0
    step_angle = span_angle / n_items
    theta = np.deg2rad(start_angle + (np.arange(n_items) + 0.5) * step_angle)
    width = np.deg2rad(step_angle * 0.96)

    fig = plt.figure(figsize=(13.6, 12.6), facecolor="white")
    ax = fig.add_axes([0.005, 0.025, 0.805, 0.950], projection="polar")
    ax.set_theta_zero_location("E")
    ax.set_theta_direction(1)
    ax.set_axis_off()
    ax.set_facecolor("white")

    group_radius = 1.25
    group_height = 0.110
    ring_gap = 0.012
    heatmap_radius = 1.50
    total_span = 8 * 0.115 + 7 * ring_gap  # 与原模板 8 环总径向跨度一致
    ring_height = min(0.115, (total_span - (n_rings - 1) * ring_gap) / n_rings)
    ring_radii = [heatmap_radius + i * (ring_height + ring_gap) for i in range(n_rings)]
    outer_radius = ring_radii[-1] + ring_height
    ax.set_ylim(0, outer_radius + 0.70)

    draw_group_ring(ax, theta, width, group_radius, group_height, sector_colors)

    for ring_idx in range(n_rings):
        radius = ring_radii[n_rings - 1 - ring_idx]  # 条件 1 在最外环
        draw_ring_cells(ax, theta, width, radius, ring_height, matrix[ring_idx], cmaps[ring_idx], norm)

    for radius in [group_radius, group_radius + group_height, heatmap_radius - 0.075, outer_radius]:
        angles = np.linspace(np.deg2rad(start_angle), np.deg2rad(start_angle + span_angle), 700)
        ax.plot(angles, np.full_like(angles, radius), color="white", lw=1.0, zorder=5)

    draw_stars(ax, theta, matrix, ring_radii, ring_height, threshold=0.82 * vmax)
    draw_outer_labels(ax, theta, outer_radius + 0.265, order, start_angle, step_angle)
    add_center_legend(fig, [(name, group_colors[gi]) for gi, (name, _) in enumerate(groups)])
    add_colorbar_stack(fig, conditions, cmaps, norm, vmax)

    return export_figure(
        fig,
        str(output_stem),
        formats=["pdf", "svg", "png"],
        size_inches=(13.6, 12.6),
        dpi=300,
        grayscale_preview=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="分组环形热图（真实数据驱动模板）")
    parser.add_argument("--data", type=Path, help="宽表矩阵 CSV（首列 feature，其余列为条件数值）")
    parser.add_argument("--groups", type=Path, help="特征分组 CSV（列：feature,group）")
    parser.add_argument("--out", type=Path, help="输出文件名前缀（不含扩展名）")
    parser.add_argument("--demo", action="store_true", help="确定性模拟数据演示，产物带 _demo 后缀")
    args = parser.parse_args()

    if args.demo:
        features, conditions, values, groups, group_colors, cmaps = _demo_data()
        out = args.out or Path("grouped_circular_heatmap_demo")
    elif args.data:
        if args.groups is None:
            parser.error("--data 模式必须同时提供 --groups <csv>")
        features, conditions, values = load_matrix(args.data)
        groups = load_groups(args.groups, features)
        group_colors = [OKABE[k % len(OKABE)] for k in range(len(groups))]
        cmaps = None
        out = args.out or Path("grouped_circular_heatmap")
    else:
        parser.error("需要 --data <csv>（配合 --groups）或 --demo")

    outputs = make_figure(features, conditions, values, groups, out, group_colors=group_colors, cmaps=cmaps)
    for path in outputs:
        print(path)


if __name__ == "__main__":
    main()
