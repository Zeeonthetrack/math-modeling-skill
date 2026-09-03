#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""预测-真实散点与边缘分布组合图（模板，改造自 mathmodel-figure-templates）。

视觉技法：主区为预测-真实散点（空心圆，y=x 参考线）+ 指标文本框，顶部为
真实值分布（直方图 + KDE），右侧为预测值分布（水平直方图 + KDE），构成
"边缘分布 + 散点"的组合面板；多组数据时按组拆分面板并着色。

数据契约（--data，CSV，UTF-8）：
    y_true,y_pred,group
    52.3,49.8,train
    18.7,22.4,test
    ...
    - y_true/y_pred：数值列（真实值、预测值），必需
    - group：可选列；提供时每个取值一个面板（面板标题=组名），
      未提供时绘制单面板
    - 每面板的 R²、RMSE 均由数据计算

用法：
    python make_prediction_marginal_grid.py --data pred.csv --out figs/result_q3_pred
    python make_prediction_marginal_grid.py --demo            # 确定性模拟数据，产物带 _demo 后缀，
                                                                # 仅用于查看模板效果，不得作为交付物

输出（经 export_figure）：.png(300dpi) + .pdf + .svg + _grayscale.png 灰度预览。
"""
from __future__ import annotations

import argparse
import math
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
from matplotlib.gridspec import GridSpecFromSubplotSpec

FIGURE_SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FIGURE_SCRIPTS))

from export_figure import export_figure  # noqa: E402

# Okabe-Ito 色盲安全色板（正式数据模式使用）
OKABE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#F0E442", "#000000"]


@dataclass(frozen=True)
class Series:
    label: str
    y_true: np.ndarray
    y_pred: np.ndarray


@dataclass(frozen=True)
class Panel:
    name: str
    series: tuple[Series, ...]
    colors: tuple[str, ...]


# demo 模式沿用原模板的模型设定与配色（正式数据模式按组使用 Okabe-Ito）
DEMO_PANELS = [
    ("RF", "#6fb8d7", "#e5bd50", 3.8, 9.4, 0.3, 1.8),
    ("XGBoost", "#54c887", "#df8984", 3.4, 7.0, 0.1, 1.4),
    ("LightGBM", "#a86cba", "#e8c65d", 4.4, 9.8, 0.4, 1.6),
    ("CatBoost", "#d96961", "#62bcb2", 7.1, 9.5, 0.2, 1.2),
]


def configure_matplotlib() -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "font.size": 9,
            "axes.linewidth": 1.2,
            "xtick.major.width": 0.9,
            "ytick.major.width": 0.9,
            "xtick.major.size": 3.0,
            "ytick.major.size": 3.0,
            "legend.frameon": False,
        }
    )


# ---------------------------------------------------------------- 演示数据（仅 --demo）
def make_actual_values(rng: np.random.Generator, n: int) -> np.ndarray:
    low = rng.gamma(shape=2.1, scale=13.0, size=n)
    mid = rng.normal(loc=52.0, scale=14.0, size=n)
    high = rng.normal(loc=82.0, scale=11.0, size=n)
    selector = rng.choice([0, 1, 2], size=n, p=[0.46, 0.34, 0.20])
    values = np.where(selector == 0, low, np.where(selector == 1, mid, high))
    return np.clip(values, 0.0, 108.0)


def simulate_predictions(
    rng: np.random.Generator,
    actual: np.ndarray,
    noise: float,
    bias: float,
    shrink: float,
) -> np.ndarray:
    hetero = rng.normal(0.0, noise * (0.72 + 0.008 * actual), size=actual.size)
    systematic = bias + shrink * (actual - 55.0)
    pred = actual + systematic + hetero
    return np.clip(pred, -6.0, 112.0)


def _demo_panels() -> list[Panel]:
    """确定性模拟 4 模型 Train/Test 面板（演示模式专用，不代表任何真实研究）。"""
    panels = []
    for idx, (name, train_color, test_color, train_noise, test_noise, train_bias, test_bias) in enumerate(DEMO_PANELS):
        rng = np.random.default_rng(20260505 + idx * 103)
        actual_train = make_actual_values(rng, 230)
        actual_test = make_actual_values(rng, 92)
        pred_train = simulate_predictions(rng, actual_train, train_noise, train_bias, shrink=-0.018)
        pred_test = simulate_predictions(rng, actual_test, test_noise, test_bias, shrink=-0.055)
        panels.append(
            Panel(
                name,
                (
                    Series("Train", actual_train, pred_train),
                    Series("Test", actual_test, pred_test),
                ),
                (train_color, test_color),
            )
        )
    return panels


# ---------------------------------------------------------------- 真实数据
def load_panels(csv_path: Path) -> list[Panel]:
    import pandas as pd

    frame = pd.read_csv(csv_path)
    missing = {"y_true", "y_pred"} - set(frame.columns)
    if missing:
        raise SystemExit(f"数据缺少必需列：{sorted(missing)}；契约见脚本头部 docstring")
    for column in ("y_true", "y_pred"):
        values = pd.to_numeric(frame[column], errors="coerce")
        if values.notna().sum() < 2:
            raise SystemExit(f"列 {column} 有效数值不足（至少 2 行）")
        frame[column] = values

    panels: list[Panel] = []
    if "group" in frame.columns:
        frame = frame.dropna(subset=["y_true", "y_pred"])
        groups = [str(g) for g in frame["group"].unique()]
        if len(groups) > 16:
            raise SystemExit(f"group 取值过多（{len(groups)} 个）；面板布局最多支持 16 组")
        for idx, group in enumerate(groups):
            sub = frame[frame["group"].astype(str) == group]
            panels.append(
                Panel(
                    group,
                    (Series(group, sub["y_true"].to_numpy(dtype=float), sub["y_pred"].to_numpy(dtype=float)),),
                    (OKABE[idx % len(OKABE)],),
                )
            )
    else:
        frame = frame.dropna(subset=["y_true", "y_pred"])
        panels.append(
            Panel(
                "All",
                (Series("All", frame["y_true"].to_numpy(dtype=float), frame["y_pred"].to_numpy(dtype=float)),),
                (OKABE[0],),
            )
        )
    return panels


# ---------------------------------------------------------------- 统计量（由数据计算）
def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> tuple[float, float]:
    residual = y_true - y_pred
    rmse = float(np.sqrt(np.mean(residual**2)))
    ss_res = float(np.sum(residual**2))
    ss_tot = float(np.sum((y_true - y_true.mean()) ** 2))
    r2 = float("nan") if ss_tot < 1e-12 else 1.0 - ss_res / ss_tot
    return r2, rmse


# ---------------------------------------------------------------- 绘制
def kde_1d(values: np.ndarray, grid: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    std = max(np.std(values, ddof=1), 1e-3)
    span = max(float(np.ptp(grid)), 1e-3)
    bandwidth = max(1.06 * std * values.size ** (-1 / 5), 0.03 * span)
    z = (grid[:, None] - values[None, :]) / bandwidth
    density = np.exp(-0.5 * z**2).mean(axis=1) / (bandwidth * np.sqrt(2 * np.pi))
    return density


def draw_top_distribution(ax: plt.Axes, panel: Panel, lo: float, hi: float) -> None:
    bins = np.linspace(lo, hi, 20)
    grid = np.linspace(lo, hi, 240)
    for series, color in zip(panel.series, panel.colors):
        ax.hist(
            series.y_true,
            bins=bins,
            density=True,
            facecolor=mpl.colors.to_rgba(color, 0.12),
            edgecolor=mpl.colors.to_rgba(color, 0.58),
            linewidth=1.05,
        )
        density = kde_1d(series.y_true, grid)
        ax.plot(grid, density, color=color, lw=1.45, alpha=0.88)
    ax.set_xlim(lo, hi)
    ax.set_ylim(bottom=0)
    # 隐藏刻度标签用 tick_params，避免 set_xticklabels([]) 的 FixedFormatter 告警
    ax.tick_params(labelbottom=False, labelleft=False, length=0)


def draw_right_distribution(ax: plt.Axes, panel: Panel, lo: float, hi: float) -> None:
    bins = np.linspace(lo, hi, 20)
    grid = np.linspace(lo, hi, 240)
    max_density = 0.0
    for series, color in zip(panel.series, panel.colors):
        counts, edges = np.histogram(series.y_pred, bins=bins, density=True)
        max_density = max(max_density, float(counts.max()))
        centers = (edges[:-1] + edges[1:]) / 2
        heights = np.diff(edges)
        ax.barh(
            centers,
            counts,
            height=heights,
            facecolor=mpl.colors.to_rgba(color, 0.12),
            edgecolor=mpl.colors.to_rgba(color, 0.58),
            linewidth=1.05,
        )
        density = kde_1d(series.y_pred, grid)
        max_density = max(max_density, float(density.max()))
        ax.plot(density, grid, color=color, lw=1.45, alpha=0.88)
    ax.set_ylim(lo, hi)
    ax.set_xlim(0, max_density * 1.15 if max_density > 0 else 1.0)
    # 隐藏刻度标签用 tick_params，避免 set_xticklabels([]) 的 FixedFormatter 告警
    ax.tick_params(labelbottom=False, labelleft=False, length=0)


def draw_scatter_panel(ax: plt.Axes, panel: Panel, lo: float, hi: float) -> None:
    ax.plot([lo, hi], [lo, hi], color="#a5a5a5", lw=1.25, zorder=0)
    for series, color in zip(panel.series, panel.colors):
        ax.scatter(
            series.y_true,
            series.y_pred,
            s=23,
            facecolors="none",
            edgecolors=mpl.colors.to_rgba(color, 0.78),
            linewidths=1.2,
            label=series.label,
            zorder=2,
        )
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_xlabel("Actual", fontsize=12, fontweight="bold", labelpad=2)
    ax.set_ylabel("Predicted", fontsize=12, fontweight="bold", labelpad=2)
    ax.tick_params(labelsize=8)
    if len(panel.series) > 1:
        ax.legend(loc="upper left", fontsize=8, handletextpad=0.5, borderaxespad=0.45)

    metric_lines = []
    for series in panel.series:
        r2, rmse = regression_metrics(series.y_true, series.y_pred)
        metric_lines.append(f"{series.label}  R$^2$={r2:.3f}  RMSE={rmse:.3f}")
    ax.text(
        0.28,
        0.035,
        "\n".join(metric_lines),
        transform=ax.transAxes,
        fontsize=7.8,
        ha="left",
        va="bottom",
        bbox=dict(boxstyle="square,pad=0.22", facecolor="white", edgecolor="#777777", alpha=0.92),
    )


def draw_panel(fig: plt.Figure, slot, panel: Panel, lo: float, hi: float) -> None:
    sub = GridSpecFromSubplotSpec(
        2,
        2,
        subplot_spec=slot,
        height_ratios=[0.30, 1.0],
        width_ratios=[1.0, 0.34],
        hspace=0.06,
        wspace=0.06,
    )
    ax_top = fig.add_subplot(sub[0, 0])
    ax_main = fig.add_subplot(sub[1, 0])
    ax_right = fig.add_subplot(sub[1, 1], sharey=ax_main)
    ax_blank = fig.add_subplot(sub[0, 1])
    ax_blank.axis("off")

    draw_top_distribution(ax_top, panel, lo, hi)
    draw_scatter_panel(ax_main, panel, lo, hi)
    draw_right_distribution(ax_right, panel, lo, hi)
    ax_top.set_title(panel.name, fontsize=10.5, fontweight="bold", pad=5)


def make_figure(panels: list[Panel], output_stem: Path) -> list[str]:
    configure_matplotlib()

    all_values = np.concatenate(
        [np.r_[s.y_true, s.y_pred] for panel in panels for s in panel.series]
    )
    lo, hi = float(all_values.min()), float(all_values.max())
    if np.isclose(lo, hi):
        lo, hi = lo - 0.5, hi + 0.5
    pad = 0.05 * (hi - lo)
    lo, hi = lo - pad, hi + pad

    n_panels = len(panels)
    ncols = 1 if n_panels == 1 else 2
    nrows = math.ceil(n_panels / ncols)
    fig_w, fig_h = 5.2 * ncols, 4.1 * nrows  # 4 面板时即原图尺寸 10.4 x 8.2

    fig = plt.figure(figsize=(fig_w, fig_h))
    outer = fig.add_gridspec(
        nrows,
        ncols,
        left=0.055,
        right=0.982,
        bottom=0.055,
        top=0.960,
        wspace=0.22,
        hspace=0.28,
    )

    for idx, panel in enumerate(panels):
        draw_panel(fig, outer[idx // ncols, idx % ncols], panel, lo, hi)

    return export_figure(
        fig,
        str(output_stem),
        formats=["pdf", "svg", "png"],
        size_inches=(fig_w, fig_h),
        dpi=300,
        grayscale_preview=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="预测-真实散点与边缘分布组合图（真实数据驱动模板）")
    parser.add_argument("--data", type=Path, help="CSV 数据（契约见头部 docstring）")
    parser.add_argument("--out", type=Path, help="输出文件名前缀（不含扩展名）")
    parser.add_argument("--demo", action="store_true", help="确定性模拟数据演示，产物带 _demo 后缀")
    args = parser.parse_args()

    if args.demo:
        panels = _demo_panels()
        out = args.out or Path("prediction_marginal_grid_demo")
    elif args.data:
        panels = load_panels(args.data)
        out = args.out or Path("prediction_marginal_grid")
    else:
        parser.error("需要 --data <csv> 或 --demo")

    outputs = make_figure(panels, out)
    for path in outputs:
        print(path)


if __name__ == "__main__":
    main()
