#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""配对云雨图（模板，改造自 mathmodel-figure-templates）。

视觉技法：两条件对称排布的"云雨图"——高斯 KDE 手绘半小提琴（云）+ 抖动
散点（雨）+ 窄箱线图 + 均值菱形连线 + 底部组括号标注的大字号出版样式。

数据契约（--data，CSV，UTF-8）：
    id,pre,post
    S01,2.74,3.60
    S02,3.00,2.65
    S03,2.20,4.05
    ...
    - id：可选列，配对样本编号（仅核对用，不参与绘图）
    - 其余必须恰好两列数值，列名即条件标签（如 pre/post，第一列绘于左侧）
    - 每行 = 一对配对观测；任一条件缺失的行自动剔除，至少需 3 行完整数据

用法：
    python make_paired_raincloud.py --data paired.csv --out figs/result_q2_raincloud
    python make_paired_raincloud.py --data paired.csv --ylabel "Sepal Width" --group-label "Treatment"
    python make_paired_raincloud.py --demo
        # 确定性模拟数据（沿袭原模板 iris 风格模拟，种子 20260624），
        # 产物带 _demo 后缀，仅用于查看模板效果，不得作为交付物

输出（经 export_figure）：.png(300dpi) + .pdf + .svg + _grayscale.png 灰度预览。
"""
from __future__ import annotations

import argparse
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

FIGURE_SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FIGURE_SCRIPTS))

from export_figure import export_figure  # noqa: E402

# Okabe-Ito 色盲安全色板（正式数据模式使用）
OKABE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#F0E442", "#000000"]

# 真实数据模式：两条件分别用 Okabe-Ito 蓝 / 橙红
REAL_PALETTE = [
    {"edge": OKABE[0], "fill": OKABE[0]},
    {"edge": OKABE[1], "fill": OKABE[1]},
]

# 演示模式沿用原模板配色
DEMO_PALETTE = [
    {"edge": "#c9253e", "fill": "#ee7f8d"},
    {"edge": "#145f86", "fill": "#6f9fba"},
]


def configure_matplotlib() -> None:
    mpl.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Times", "DejaVu Serif", "serif"],
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "axes.spines.right": False,
            "axes.spines.top": False,
            "axes.linewidth": 2.3,
            "xtick.major.width": 2.3,
            "ytick.major.width": 2.3,
            "legend.frameon": False,
        }
    )


def synthetic_sepal_width_data(seed: int = 20260624) -> dict[tuple[str, str], np.ndarray]:
    """Create iris-like paired-condition data matching the reference figure."""
    rng = np.random.default_rng(seed)
    n = 50
    data = {
        ("Pre", "Versicolor"): rng.normal(2.74, 0.31, n),
        ("Pre", "Virginica"): rng.normal(3.00, 0.36, n),
        ("Post", "Versicolor"): rng.normal(3.60, 0.35, n),
        ("Post", "Virginica"): rng.normal(2.65, 0.30, n),
    }

    # Add a few deterministic tail observations so the clouds resemble the
    # visual range of the reference without depending on external iris data.
    data[("Pre", "Versicolor")][:5] = [2.10, 2.16, 2.30, 3.35, 3.45]
    data[("Pre", "Virginica")][:5] = [2.30, 2.45, 3.55, 3.75, 3.86]
    data[("Post", "Versicolor")][:6] = [2.55, 2.78, 3.95, 4.00, 4.15, 4.22]
    data[("Post", "Virginica")][:6] = [2.08, 2.15, 2.20, 3.05, 3.25, 3.55]

    return {key: np.clip(values, 2.05, 4.35) for key, values in data.items()}


def kde_1d(values: np.ndarray, grid: np.ndarray, bw_adjust: float = 1.0, min_bw: float = 0.055) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    std = max(np.std(values, ddof=1), 1e-3)
    bandwidth = max(1.06 * std * values.size ** (-1 / 5) * bw_adjust, min_bw, 1e-9)
    z = (grid[:, None] - values[None, :]) / bandwidth
    density = np.exp(-0.5 * z**2).mean(axis=1) / (bandwidth * np.sqrt(2 * np.pi))
    return density / density.max()


def draw_half_violin(
    ax: plt.Axes,
    values: np.ndarray,
    anchor_x: float,
    side: str,
    fill_color: str,
    edge_color: str,
    width: float = 0.28,
    alpha: float = 0.74,
    zorder: int = 1,
) -> None:
    values = np.asarray(values, dtype=float)
    lo, hi = float(values.min()), float(values.max())
    pad = max((hi - lo) * 0.07, 1e-9)
    grid = np.linspace(lo - pad, hi + pad, 240)
    density = kde_1d(values, grid, bw_adjust=0.92, min_bw=(hi - lo) * 0.024) * width
    if side == "left":
        ax.fill_betweenx(
            grid,
            anchor_x - density,
            anchor_x,
            facecolor=fill_color,
            edgecolor=edge_color,
            linewidth=2.4,
            alpha=alpha,
            zorder=zorder,
        )
    else:
        ax.fill_betweenx(
            grid,
            anchor_x,
            anchor_x + density,
            facecolor=fill_color,
            edgecolor=edge_color,
            linewidth=2.4,
            alpha=alpha,
            zorder=zorder,
        )


def draw_points(
    ax: plt.Axes,
    values: np.ndarray,
    x: float,
    fill_color: str,
    edge_color: str,
    seed: int,
) -> None:
    rng = np.random.default_rng(seed)
    jitter = rng.normal(0.0, 0.022, values.size)
    ax.scatter(
        x + jitter,
        values,
        s=50,
        facecolors=mpl.colors.to_rgba(fill_color, 0.56),
        edgecolors=edge_color,
        linewidths=1.6,
        alpha=0.82,
        zorder=4,
    )


def draw_box(
    ax: plt.Axes,
    values: np.ndarray,
    x: float,
    fill_color: str,
    edge_color: str,
) -> None:
    bp = ax.boxplot(
        values,
        positions=[x],
        widths=0.095,
        patch_artist=True,
        showfliers=False,
        whis=(0, 100),
        zorder=5,
    )
    for box in bp["boxes"]:
        box.set(facecolor=mpl.colors.to_rgba(fill_color, 0.68), edgecolor=edge_color, linewidth=2.5)
    for whisker in bp["whiskers"]:
        whisker.set(color=edge_color, linewidth=2.4)
    for cap in bp["caps"]:
        cap.set(color=edge_color, linewidth=2.4)
    for median in bp["medians"]:
        median.set(color=edge_color, linewidth=2.4)


def draw_mean_trend(
    ax: plt.Axes,
    pre: np.ndarray,
    post: np.ndarray,
    pre_x: float,
    post_x: float,
    pre_color: str,
    post_color: str,
) -> None:
    ys = [float(np.mean(pre)), float(np.mean(post))]
    ax.plot([pre_x, post_x], ys, color="black", linewidth=2.4, zorder=6)
    ax.scatter(
        [pre_x, post_x],
        ys,
        marker="D",
        s=95,
        color=[pre_color, post_color],
        edgecolor=[pre_color, post_color],
        zorder=7,
    )


def draw_bottom_bracket(ax: plt.Axes, pre_x: float, post_x: float) -> None:
    transform = ax.get_xaxis_transform()
    y = -0.115
    tick_y = -0.138
    ax.plot([pre_x, post_x], [y, y], transform=transform, color="black", linewidth=3.0, clip_on=False)
    ax.plot([pre_x, pre_x], [y, tick_y], transform=transform, color="black", linewidth=3.0, clip_on=False)
    ax.plot([post_x, post_x], [y, tick_y], transform=transform, color="black", linewidth=3.0, clip_on=False)


# ---------------------------------------------------------------- 真实数据
def load_paired(csv_path: Path) -> tuple[np.ndarray, np.ndarray, str, str]:
    import pandas as pd

    frame = pd.read_csv(csv_path)
    value_cols = [c for c in frame.columns if c != "id"]
    if len(value_cols) != 2:
        raise SystemExit(
            f"数据必须恰好包含两列数值（如 pre/post），当前除 id 外共 {len(value_cols)} 列：{value_cols}；契约见脚本头部 docstring"
        )
    for col in value_cols:
        converted = pd.to_numeric(frame[col], errors="coerce")
        bad = converted.isna() & frame[col].notna()
        if bad.any():
            raise SystemExit(f"列 {col} 含非数值内容，无法解析为数值")
        frame[col] = converted
    frame = frame.dropna(subset=value_cols)
    if len(frame) < 3:
        raise SystemExit(f"有效配对样本不足：剔除缺失后仅 {len(frame)} 行（至少需要 3 行完整数据）")
    pre = frame[value_cols[0]].to_numpy(dtype=float)
    post = frame[value_cols[1]].to_numpy(dtype=float)
    if not (np.all(np.isfinite(pre)) and np.all(np.isfinite(post))):
        raise SystemExit("数值列含非有限值（inf/nan）")
    return pre, post, str(value_cols[0]), str(value_cols[1])


# ---------------------------------------------------------------- 绘制
def make_figure(
    pre: np.ndarray,
    post: np.ndarray,
    pre_label: str,
    post_label: str,
    output_stem: Path,
    *,
    palette: list[dict[str, str]],
    ylabel: str = "Value",
    group_label: str | None = None,
) -> list[str]:
    configure_matplotlib()
    fig, ax = plt.subplots(figsize=(8.2, 7.8))
    fig.subplots_adjust(left=0.13, right=0.78, bottom=0.22, top=0.90)

    pre_style, post_style = palette[0], palette[1]

    positions = {
        "pre_violin": 0.80,
        "pre_points": 1.00,
        "pre_box": 1.22,
        "post_box": 2.10,
        "post_points": 2.32,
        "post_violin": 2.52,
    }

    draw_half_violin(
        ax,
        pre,
        positions["pre_violin"],
        "left",
        pre_style["fill"],
        pre_style["edge"],
        width=0.30,
        alpha=0.76,
        zorder=1,
    )
    draw_half_violin(
        ax,
        post,
        positions["post_violin"],
        "right",
        post_style["fill"],
        post_style["edge"],
        width=0.30,
        alpha=0.76,
        zorder=1,
    )
    draw_points(ax, pre, positions["pre_points"], pre_style["fill"], pre_style["edge"], 1)
    draw_points(ax, post, positions["post_points"], post_style["fill"], post_style["edge"], 2)
    draw_box(ax, pre, positions["pre_box"], pre_style["fill"], pre_style["edge"])
    draw_box(ax, post, positions["post_box"], post_style["fill"], post_style["edge"])
    draw_mean_trend(ax, pre, post, positions["pre_box"], positions["post_box"], pre_style["edge"], post_style["edge"])

    lo = float(min(pre.min(), post.min()))
    hi = float(max(pre.max(), post.max()))
    span = max(hi - lo, 1e-9)
    ax.set_xlim(0.34, 3.00)
    ax.set_ylim(lo - 0.09 * span, hi + 0.09 * span)
    ax.yaxis.set_major_locator(mpl.ticker.MaxNLocator(6))
    ax.set_ylabel(ylabel, fontsize=20, fontweight="bold", labelpad=18)
    ax.set_xticks([])
    ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_linewidth(2.8)
    ax.tick_params(axis="y", labelsize=19, width=2.8, length=11, pad=6)

    pre_label_x = (positions["pre_violin"] + positions["pre_box"]) / 2
    post_label_x = (positions["post_box"] + positions["post_violin"]) / 2
    draw_bottom_bracket(ax, pre_label_x, post_label_x)
    transform = ax.get_xaxis_transform()
    ax.text(pre_label_x, -0.170, pre_label, transform=transform, ha="center", va="top", fontsize=20)
    ax.text(post_label_x, -0.170, post_label, transform=transform, ha="center", va="top", fontsize=20)
    if group_label:
        ax.text(
            (pre_label_x + post_label_x) / 2,
            -0.255,
            group_label,
            transform=transform,
            ha="center",
            va="top",
            fontsize=20,
            fontweight="bold",
        )

    return export_figure(
        fig,
        str(output_stem),
        formats=["pdf", "svg", "png"],
        size_inches=(8.2, 7.8),
        dpi=300,
        grayscale_preview=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="配对云雨图（真实数据驱动模板）")
    parser.add_argument("--data", type=Path, help="CSV 数据（契约见头部 docstring）")
    parser.add_argument("--out", type=Path, help="输出文件名前缀（不含扩展名）")
    parser.add_argument("--ylabel", default="Value", help="y 轴标签（默认 Value）")
    parser.add_argument("--group-label", help="可选底部组标签（如处理名称）")
    parser.add_argument("--demo", action="store_true", help="确定性模拟数据演示，产物带 _demo 后缀")
    args = parser.parse_args()

    if args.demo:
        data = synthetic_sepal_width_data()
        pre, post = data[("Pre", "Versicolor")], data[("Post", "Versicolor")]
        pre_label, post_label = "Pre", "Post"
        palette = DEMO_PALETTE
        ylabel = args.ylabel if args.ylabel != "Value" else "Sepal Width"
        group_label = args.group_label or "Fertilizer Treatment"
        out = args.out or Path("paired_raincloud_demo")
    elif args.data:
        pre, post, pre_label, post_label = load_paired(args.data)
        palette = REAL_PALETTE
        ylabel = args.ylabel
        group_label = args.group_label
        out = args.out or Path("paired_raincloud")
    else:
        parser.error("需要 --data <csv> 或 --demo")

    outputs = make_figure(
        pre,
        post,
        pre_label,
        post_label,
        out,
        palette=palette,
        ylabel=ylabel,
        group_label=group_label,
    )
    for path in outputs:
        print(path)


if __name__ == "__main__":
    main()
