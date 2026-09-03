#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分组相关矩阵 + 特征半边小提琴图（模板，改造自 mathmodel-figure-templates）。

视觉技法：左侧下三角相关矩阵（方块边长∝|r|、RdBu_r 发散着色、弱相关格中心
加点、矩阵右侧组括号标注特征分组），右侧每个特征一张半边小提琴（KDE 密度
轮廓 + 四分位虚线）：左半 = 该特征与同组特征的相关系数分布（组色着色），
右半 = 与异组特征的相关系数分布；全部统计量由 CSV 相关矩阵计算。

数据契约（--data，宽表对称相关矩阵 CSV，UTF-8）：
    feature,infP,infC,MLSS,pH
    infP,1.00,0.42,0.15,-0.08
    infC,0.42,1.00,0.21,0.05
    MLSS,0.15,0.21,1.00,0.33
    pH,-0.08,0.05,0.33,1.00
  - 首列 feature：特征名（唯一）；数值必须在 [-1,1]，矩阵须对称
  - 数值列数必须等于行数，且列名集合与首列特征集合一致（顺序不同自动重排）

--groups CSV（列：feature,group）：
    feature,group
    infP,Substrate
    MLSS,Biomass
    pH,Operation
  - 每个矩阵特征都必须有分组记录，驱动组括号与半边小提琴着色
  - 同一分组的特征必须在矩阵中连续排列（组括号按连续区间绘制）

用法：
    python make_grouped_corr_split_violin.py --data corr.csv --groups groups.csv --out figs/corr_violin
    python make_grouped_corr_split_violin.py --demo    # 确定性模拟数据，产物带 _demo 后缀，
                                                          # 仅用于查看模板效果，不得作为交付物

输出（经 export_figure）：.png(300dpi) + .pdf + .svg + _grayscale.png 灰度预览。
"""
from __future__ import annotations

import argparse
import math
import os
import sys
import tempfile
from pathlib import Path

if not os.environ.get("MPLCONFIGDIR"):
    os.environ["MPLCONFIGDIR"] = tempfile.mkdtemp(prefix="mpl-")

import matplotlib as mpl

mpl.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

FIGURE_SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FIGURE_SCRIPTS))

from export_figure import export_figure  # noqa: E402

# Okabe-Ito 色盲安全色板（正式数据模式使用）
OKABE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#F0E442", "#000000"]

# ---- 演示模式（--demo）：保留原模板的确定性模拟与配色，仅用于查看模板效果 ----
DEMO_FEATURES = [
    "infP", "infC", "infAC", "infpro", "infS",
    "MLSS", "MLVSS", "VSS/TSS",
    "volum", "ana-time", "pH", "T", "salinity",
]
DEMO_GROUPS = [
    ("Substrate", ["infP", "infC", "infAC", "infpro", "infS"]),
    ("Biomass", ["MLSS", "MLVSS", "VSS/TSS"]),
    ("Operation", ["volum", "ana-time", "pH", "T", "salinity"]),
]
DEMO_GROUP_COLORS = ["#2f7e91", "#c7474d", "#3f9d54"]
DEMO_INTRA_COLOR = "#2f7fa7"
DEMO_INTER_COLOR = "#b4162d"


def configure_matplotlib() -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "font.size": 8,
            "axes.linewidth": 0.8,
            "xtick.major.width": 0.7,
            "ytick.major.width": 0.7,
            "legend.frameon": False,
        }
    )


def simulate_feature_data(seed: int = 20260506, n_train: int = 170, n_test: int = 84) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)

    def latent_samples(n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        substrate = rng.normal(size=n)
        biomass = rng.normal(size=n)
        operation = rng.normal(size=n)
        shared = rng.normal(size=n)
        return substrate, biomass, operation, shared

    def build(n: int, shift: float = 0.0) -> np.ndarray:
        s, b, o, h = latent_samples(n)
        noise = lambda scale=1.0: rng.normal(0.0, scale, size=n)

        infp = np.clip(10 + 3.3 * s + 0.8 * h + noise(2.2) + shift, 0.2, 34)
        infc = np.clip(78 + 18 * s + 9 * h + noise(12), 24, 175)
        infac = np.clip(62 + 13 * s - 5 * o + noise(9), 8, 112)
        infpro = np.clip(16 + 7.5 * s + noise(8.5), 0.6, 86)
        infs = np.clip(190 + 46 * s + 14 * h + noise(40), 4, 720)

        mlss = np.clip(7.7 + 2.2 * b + 0.6 * s + noise(2.0), 1.0, 22)
        mlvss = np.clip(4.7 + 1.35 * b + 0.35 * s + noise(1.15), 0.5, 9.0)
        vss_tss = np.clip(0.62 + 0.12 * b + 0.06 * s - 0.04 * o + noise(0.08), 0.04, 0.94)

        volume = np.exp(np.clip(1.70 + 0.95 * o - 0.20 * s + noise(0.75), -2.0, 4.8))
        ana_time = np.exp(np.clip(1.55 + 0.75 * o - 0.20 * b + noise(0.62), -2.0, 4.5))
        ph = np.clip(7.55 + 0.20 * o - 0.16 * b + noise(0.20), 6.6, 8.55)
        temp = np.clip(27.4 + 2.5 * o + 0.8 * b + noise(1.75), 19.0, 35.6)
        salinity = np.exp(np.clip(-0.58 + 0.62 * o - 0.32 * s + noise(0.82), -2.6, 1.25))

        return np.column_stack(
            [infp, infc, infac, infpro, infs, mlss, mlvss, vss_tss, volume, ana_time, ph, temp, salinity]
        )

    train = build(n_train, shift=0.0)
    test = build(n_test, shift=0.25)
    return train, test


def rank_columns(data: np.ndarray) -> np.ndarray:
    ranked = np.empty_like(data, dtype=float)
    for col in range(data.shape[1]):
        order = np.argsort(data[:, col], kind="mergesort")
        ranks = np.empty(data.shape[0], dtype=float)
        ranks[order] = np.arange(1, data.shape[0] + 1)
        ranked[:, col] = ranks
    return ranked


def spearman_corr(data: np.ndarray) -> np.ndarray:
    ranks = rank_columns(data)
    return np.corrcoef(ranks, rowvar=False)


def kde_1d(values: np.ndarray, grid: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    std = max(np.std(values, ddof=1), 1e-6)
    bandwidth = max(1.06 * std * values.size ** (-1 / 5), std * 0.16, 1e-4)
    z = (grid[:, None] - values[None, :]) / bandwidth
    density = np.exp(-0.5 * z**2).mean(axis=1) / (bandwidth * np.sqrt(2 * np.pi))
    return density / density.max() if density.max() > 0 else density


# ---------------------------------------------------------------- 真实数据
def load_corr_matrix(csv_path: Path) -> tuple[list[str], np.ndarray]:
    import pandas as pd

    frame = pd.read_csv(csv_path)
    if frame.shape[1] < 3 or frame.iloc[:, 0].isna().any():
        raise SystemExit("相关矩阵至少需要首列 feature 外加 2 个特征列（至少 2×2 方阵）")
    features = [str(v) for v in frame.iloc[:, 0]]
    if len(set(features)) != len(features):
        raise SystemExit("首列 feature 存在重复特征名")
    columns = [str(c) for c in frame.columns[1:]]
    if len(columns) != len(features):
        raise SystemExit(f"相关矩阵必须是方阵：当前 {len(features)} 行 × {len(columns)} 数值列")
    if set(columns) != set(features):
        missing = sorted(set(features) - set(columns))
        extra = sorted(set(columns) - set(features))
        raise SystemExit(f"数值列名与首列特征集合不一致（缺 {missing}，多 {extra}）")
    if columns != features:
        frame = frame[features]
    corr = frame[features].to_numpy(dtype=float)
    if not np.all(np.isfinite(corr)):
        raise SystemExit("相关矩阵存在缺失/非有限值")
    if corr.min() < -1.001 or corr.max() > 1.001:
        raise SystemExit("数值必须在 [-1,1] 区间内（应为相关系数）")
    if np.abs(corr - corr.T).max() > 0.01:
        raise SystemExit("相关矩阵不对称：请提供对称矩阵（M[i,j] == M[j,i]）")
    return features, corr


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
    for feature in features:  # 组序按组在矩阵特征顺序中的首次出现
        group = mapping[feature]
        if group not in index:
            index[group] = len(ordered)
            ordered.append((group, []))
        ordered[index[group]][1].append(feature)
    # 组括号按连续区间绘制：同一分组的特征必须在矩阵中相邻排列，
    # 否则括号会横跨其他组的行/列（此前静默画错，现在显式拒绝）
    position = {feature: i for i, feature in enumerate(features)}
    for name, members in ordered:
        idx = sorted(position[m] for m in members)
        if idx[-1] - idx[0] != len(members) - 1:
            raise SystemExit(
                f"分组 {name} 的特征在矩阵中不连续（{members}）；"
                "请调整矩阵行列顺序使同组特征相邻后重试"
            )
    return ordered


# ---------------------------------------------------------------- 绘制
def draw_group_bracket(ax: plt.Axes, start: float, end: float, x: float, color: str, label: str) -> None:
    ax.plot([x, x], [start, end], color=color, lw=1.3, clip_on=False)
    ax.plot([x - 0.95, x], [start, start], color=color, lw=1.3, clip_on=False)
    ax.plot([x - 0.95, x], [end, end], color=color, lw=1.3, clip_on=False)
    ax.text(x + 0.20, (start + end) / 2, label, color=color, fontsize=8, fontweight="bold", fontstyle="italic", va="center")


def draw_lower_corr(
    ax: plt.Axes,
    corr: np.ndarray,
    features: list[str],
    groups: list[tuple[str, list[str]]],
    group_colors: list[str],
) -> None:
    n = len(features)
    cmap = mpl.colormaps["RdBu_r"]
    norm = mpl.colors.Normalize(vmin=-1, vmax=1)

    label_space = 0.25 + max(len(name) for name, _ in groups) * 0.16
    x_max = n + 0.15 + (len(groups) - 1) * 0.55 + label_space
    ax.set_xlim(-0.5, x_max)
    ax.set_ylim(n - 0.5, -0.5)
    ax.set_aspect("equal")
    ax.set_facecolor("white")
    ax.set_xticks(np.arange(n))
    ax.set_xticklabels(features, rotation=90, fontsize=7, fontweight="bold")
    ax.set_yticks(np.arange(n))
    ax.set_yticklabels(features, fontsize=8, fontweight="bold")
    ax.yaxis.tick_right()
    ax.tick_params(axis="both", length=0, pad=1)
    for spine in ax.spines.values():
        spine.set_visible(False)

    for row in range(n):
        for col in range(row):
            value = corr[row, col]
            size = 0.12 + 0.70 * abs(value)
            rect = plt.Rectangle(
                (col - size / 2, row - size / 2),
                size,
                size,
                facecolor=cmap(norm(value)),
                edgecolor="#222222",
                linewidth=0.55,
            )
            ax.add_patch(rect)

    # Subtle cell centers make weak correlations visible without cluttering the matrix.
    for row in range(n):
        for col in range(row):
            if abs(corr[row, col]) < 0.10:
                ax.plot(col, row, marker="s", ms=1.4, color="#333333", alpha=0.75)

    for k, (name, members) in enumerate(groups):
        first = features.index(members[0])
        last = features.index(members[-1])
        draw_group_bracket(ax, start=first - 0.35, end=last + 0.35, x=n + 0.15 + k * 0.55, color=group_colors[k], label=name)


def draw_split_violin(
    ax: plt.Axes,
    intra: list[float],
    inter: list[float],
    label: str,
    intra_color: str,
    inter_color: str,
) -> None:
    grid = np.linspace(-1.05, 1.05, 240)
    for values, color, side in ((intra, intra_color, -1), (inter, inter_color, 1)):
        values = np.asarray(values, dtype=float)
        if values.size == 0:
            continue
        if values.size >= 2:
            density = kde_1d(values, grid) * 0.40
            ax.fill_betweenx(grid, side * density, 0.0, facecolor="none", edgecolor=color, linewidth=1.1)
            ax.plot(side * density, grid, color=color, lw=1.25)
        ax.hlines(np.percentile(values, [25, 50, 75]), side * 0.04, side * 0.33, color=color, linestyles="--", linewidth=0.75)
    ax.axvline(0, color=inter_color, lw=0.75, alpha=0.9)

    ax.set_xlim(-0.45, 0.45)
    ax.set_ylim(-1.05, 1.05)
    ax.set_yticks([-1.0, 0.0, 1.0])
    ax.set_xticks([])
    ax.set_ylabel(label, fontsize=7, fontweight="bold", labelpad=1)
    ax.tick_params(axis="y", labelsize=6, length=2, width=0.6, pad=1)
    for spine in ax.spines.values():
        spine.set_linewidth(0.8)
        spine.set_color("#333333")


def make_figure(
    features: list[str],
    corr: np.ndarray,
    groups: list[tuple[str, list[str]]],
    output_stem: Path,
    *,
    group_colors: list[str] | None = None,
    intra_legend_color: str | None = None,
    inter_color: str = "#000000",
) -> list[str]:
    configure_matplotlib()
    n = len(features)
    group_colors = list(group_colors) if group_colors else [OKABE[k % len(OKABE)] for k in range(len(groups))]
    intra_legend_color = intra_legend_color or group_colors[0]
    group_index = {feature: gi for gi, (_, members) in enumerate(groups) for feature in members}

    fig = plt.figure(figsize=(13.8, 4.6))
    cax = fig.add_axes([0.024, 0.165, 0.018, 0.72])
    ax_corr = fig.add_axes([0.075, 0.135, 0.355, 0.77])
    draw_lower_corr(ax_corr, corr, features, groups, group_colors)

    sm = mpl.cm.ScalarMappable(norm=mpl.colors.Normalize(-1, 1), cmap=mpl.colormaps["RdBu_r"])
    cbar = fig.colorbar(sm, cax=cax)
    cbar.set_label("Correlation", fontsize=9, fontweight="bold", labelpad=6)
    cbar.set_ticks(np.linspace(-1, 1, 9))
    cbar.ax.tick_params(labelsize=7, length=2)
    cbar.outline.set_linewidth(0.7)

    right_left = 0.520
    right_right = 0.985
    right_bottom = 0.110
    right_top = 0.905
    cols = min(5, n)
    rows = math.ceil(n / cols)
    gap_x = 0.030
    gap_y = 0.050
    cell_w = (right_right - right_left - gap_x * (cols - 1)) / cols
    cell_h = (right_top - right_bottom - gap_y * (rows - 1)) / rows

    for idx, feature in enumerate(features):
        row = idx // cols
        col = idx % cols
        left = right_left + col * (cell_w + gap_x)
        bottom = right_top - (row + 1) * cell_h - row * gap_y
        ax = fig.add_axes([left, bottom, cell_w, cell_h])
        gi = group_index[feature]
        intra = [corr[idx, j] for j in range(n) if j != idx and group_index[features[j]] == gi]
        inter = [corr[idx, j] for j in range(n) if j != idx and group_index[features[j]] != gi]
        draw_split_violin(ax, intra, inter, feature, group_colors[gi], inter_color)

    handles = [
        Line2D([0], [0], color=intra_legend_color, lw=1.5, label="Intra-group ρ (left)"),
        Line2D([0], [0], color=inter_color, lw=1.5, label="Inter-group ρ (right)"),
    ]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.725, 0.022), ncol=2, fontsize=8, frameon=False)

    return export_figure(
        fig,
        str(output_stem),
        formats=["pdf", "svg", "png"],
        size_inches=(13.8, 4.6),
        dpi=300,
        grayscale_preview=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="分组相关矩阵 + 特征半边小提琴图（真实数据驱动模板）")
    parser.add_argument("--data", type=Path, help="对称相关矩阵宽表 CSV（契约见头部 docstring）")
    parser.add_argument("--groups", type=Path, help="特征分组 CSV（列：feature,group）")
    parser.add_argument("--out", type=Path, help="输出文件名前缀（不含扩展名）")
    parser.add_argument("--demo", action="store_true", help="确定性模拟数据演示，产物带 _demo 后缀")
    args = parser.parse_args()

    if args.demo:
        train, test = simulate_feature_data()
        corr = spearman_corr(np.vstack([train, test]))
        features = list(DEMO_FEATURES)
        groups = [(name, list(members)) for name, members in DEMO_GROUPS]
        group_colors = list(DEMO_GROUP_COLORS)
        intra_legend_color = DEMO_INTRA_COLOR
        inter_color = DEMO_INTER_COLOR
        out = args.out or Path("grouped_corr_split_violin_demo")
    elif args.data:
        if args.groups is None:
            parser.error("--data 模式必须同时提供 --groups <csv>")
        features, corr = load_corr_matrix(args.data)
        groups = load_groups(args.groups, features)
        group_colors = [OKABE[k % len(OKABE)] for k in range(len(groups))]
        intra_legend_color = group_colors[0]
        inter_color = "#000000"
        out = args.out or Path("grouped_corr_split_violin")
    else:
        parser.error("需要 --data <csv>（配合 --groups）或 --demo")

    outputs = make_figure(
        features,
        corr,
        groups,
        out,
        group_colors=group_colors,
        intra_legend_color=intra_legend_color,
        inter_color=inter_color,
    )
    for path in outputs:
        print(path)


if __name__ == "__main__":
    main()
