#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""相关矩阵配对网格图（模板，改造自 mathmodel-figure-templates）。

视觉技法：对角线为各变量直方图 + KDE 密度曲线，下三角为散点 + 线性拟合线
及其 95% 置信带，上三角为 Pearson 相关系数色块（RdBu_r 配色 + 显著性星号），
右侧附相关系数 colorbar。

数据契约（--data，CSV，UTF-8，宽表）：
    Temperature,Humidity,WindSpeed,Pressure
    21.3,52.8,4.6,1011.2
    19.8,58.1,7.2,1013.5
    ...
    - 至少 3 个数值列，列名即变量名（非数值列自动忽略）
    - 相关系数、p 值、拟合线与置信带均由数据计算

可选 --groups CSV（两列：column,group）：
    column,group
    Temperature,气象
    Humidity,气象
    Pressure,环境
    为变量按组着色（对角直方图与轴标签同组同色）。

用法：
    python make_correlation_pairgrid.py --data corr.csv --out figs/result_q2_pairgrid
    python make_correlation_pairgrid.py --data corr.csv --groups groups.csv
    python make_correlation_pairgrid.py --demo            # 确定性模拟数据，产物带 _demo 后缀，
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

FIGURE_SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FIGURE_SCRIPTS))

from export_figure import export_figure  # noqa: E402

# Okabe-Ito 色盲安全色板（正式数据模式使用）
OKABE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#F0E442", "#000000"]

# 真实数据模式配色（Okabe-Ito 派生）；demo 模式沿用原模板配色
REAL_COLORS = {
    "scatter": "#0072B2",
    "band": "#CC79A7",
    "fit": "#D55E00",
    "kde": "#0072B2",
}
DEMO_COLORS = {
    "scatter": "#11779c",
    "band": "#e8a8d1",
    "fit": "#9a4bb3",
    "kde": "#225d78",
}

VARIABLES = [f"Variable_{idx}" for idx in range(1, 10)]


def configure_matplotlib() -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "axes.linewidth": 0.6,
            "xtick.major.width": 0.45,
            "ytick.major.width": 0.45,
            "xtick.major.size": 1.8,
            "ytick.major.size": 1.8,
        }
    )


# ---------------------------------------------------------------- 演示数据（仅 --demo）
def simulate_data(seed: int = 20260629, n_samples: int = 130) -> np.ndarray:
    rng = np.random.default_rng(seed)
    f1 = rng.normal(size=n_samples)
    f2 = rng.normal(size=n_samples)
    f3 = rng.normal(size=n_samples)
    noise = lambda scale=1.0: rng.normal(scale=scale, size=n_samples)

    data = np.column_stack(
        [
            1.00 * f1 + 0.25 * f2 + noise(0.55),
            0.20 * f1 + 0.85 * f2 + noise(0.88),
            0.95 * f1 + noise(0.55),
            0.12 * f1 + 0.18 * f3 + noise(0.95),
            0.82 * f1 + 0.12 * f2 + noise(0.50),
            -0.20 * f1 + 0.20 * f3 + noise(0.92),
            0.78 * f1 + 0.20 * f2 + noise(0.48),
            -0.24 * f1 + 0.10 * f2 + noise(0.95),
            0.84 * f1 + 0.08 * f2 + noise(0.48),
        ]
    )
    data = (data - data.mean(axis=0)) / data.std(axis=0, ddof=1)
    return data


# ---------------------------------------------------------------- 真实数据
def load_wide_csv(csv_path: Path) -> tuple[np.ndarray, list[str]]:
    import pandas as pd

    frame = pd.read_csv(csv_path)
    numeric = [str(c) for c in frame.columns if pd.api.types.is_numeric_dtype(frame[c])]
    if len(numeric) < 3:
        raise SystemExit(
            f"数值列不足：{len(numeric)} 个（至少需要 3 个）；契约见脚本头部 docstring"
        )
    frame = frame[numeric].dropna()
    if len(frame) < 3:
        raise SystemExit("有效样本不足：去除缺失值后不足 3 行，无法计算相关矩阵")
    return frame.to_numpy(dtype=float), numeric


def load_groups(csv_path: Path, columns: list[str]) -> dict[str, str]:
    import pandas as pd

    frame = pd.read_csv(csv_path)
    missing = {"column", "group"} - set(frame.columns)
    if missing:
        raise SystemExit(f"分组文件缺少必需列：{sorted(missing)}；应为两列 column,group")
    mapping = {str(row.column): str(row.group) for row in frame.itertuples(index=False)}
    unknown = [name for name in mapping if name not in columns]
    if unknown:
        raise SystemExit(f"分组文件引用了数据中不存在的列：{unknown}；可用数值列：{columns}")
    return mapping


# ---------------------------------------------------------------- 绘制
def kde_1d(values: np.ndarray, grid: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    std = max(np.std(values, ddof=1), 1e-4)
    span = max(float(np.ptp(values)), 1e-4)
    bandwidth = max(1.06 * std * values.size ** (-1 / 5), 0.02 * span)
    z = (grid[:, None] - values[None, :]) / bandwidth
    density = np.exp(-0.5 * z**2).mean(axis=1) / (bandwidth * np.sqrt(2 * np.pi))
    return density


def fit_line_with_ci(x: np.ndarray, y: np.ndarray, x_grid: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    slope, intercept = np.polyfit(x, y, deg=1)
    y_hat = slope * x_grid + intercept

    fitted = slope * x + intercept
    residuals = y - fitted
    n = x.size
    s_err = math.sqrt(np.sum(residuals**2) / max(n - 2, 1))
    x_mean = x.mean()
    ssx = np.sum((x - x_mean) ** 2)
    se_mean = s_err * np.sqrt(1.0 / n + (x_grid - x_mean) ** 2 / max(ssx, 1e-12))
    ci = 1.96 * se_mean
    return y_hat, y_hat - ci, y_hat + ci


def fisher_p_value(r: float, n: int) -> float:
    clipped = float(np.clip(r, -0.999999, 0.999999))
    z = 0.5 * math.log((1 + clipped) / (1 - clipped)) * math.sqrt(max(n - 3, 1))
    return math.erfc(abs(z) / math.sqrt(2.0))


def stars_for_p(p_value: float) -> str:
    if p_value < 0.001:
        return "***"
    if p_value < 0.01:
        return "**"
    if p_value < 0.05:
        return "*"
    return ""


def padded_limits(values: np.ndarray) -> tuple[float, float]:
    lo, hi = float(np.min(values)), float(np.max(values))
    if np.isclose(lo, hi):
        lo, hi = lo - 0.5, hi + 0.5
    pad = 0.05 * (hi - lo)
    return lo - pad, hi + pad


def style_small_axes(ax: plt.Axes, row: int, col: int, n_vars: int) -> None:
    for spine in ax.spines.values():
        spine.set_color("#737373")
        spine.set_linewidth(0.45)
    # 6 pt 为 SKILL.md 声明的最小可读字号；隐藏内圈刻度标签用 tick_params，
    # 避免 set_xticklabels([]) 触发 FixedFormatter/FixedLocator 告警
    ax.tick_params(labelsize=6.0, pad=0.5)
    if row < n_vars - 1:
        ax.tick_params(labelbottom=False)
    if col > 0:
        ax.tick_params(labelleft=False)


def draw_scatter_cell(
    ax: plt.Axes,
    x: np.ndarray,
    y: np.ndarray,
    xlabel: str,
    ylabel: str,
    xlim: tuple[float, float],
    ylim: tuple[float, float],
    colors: dict[str, str],
) -> None:
    ax.scatter(x, y, s=8, color=colors["scatter"], alpha=0.78, edgecolors="none", zorder=2)
    x_grid = np.linspace(x.min(), x.max(), 120)
    y_fit, y_low, y_high = fit_line_with_ci(x, y, x_grid)
    ax.fill_between(x_grid, y_low, y_high, color=colors["band"], alpha=0.36, linewidth=0, zorder=1)
    ax.plot(x_grid, y_fit, color=colors["fit"], lw=1.0, zorder=3)
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)
    ax.set_xlabel(xlabel, fontsize=6.0, labelpad=1)
    ax.set_ylabel(ylabel, fontsize=6.0, labelpad=1)


def draw_hist_cell(
    ax: plt.Axes,
    values: np.ndarray,
    xlabel: str,
    xlim: tuple[float, float],
    hist_color: str,
    hist_edge: str,
    colors: dict[str, str],
) -> None:
    counts, _, _ = ax.hist(values, bins=12, color=hist_color, edgecolor=hist_edge, linewidth=0.55, alpha=0.90)
    span = float(np.ptp(values))
    grid = np.linspace(values.min() - 0.05 * span, values.max() + 0.05 * span, 180)
    density = kde_1d(values, grid)
    scaled = density / density.max() * max(counts) if density.max() > 0 else density
    ax.plot(grid, scaled, color=colors["kde"], lw=1.0)
    ax.set_xlim(xlim)
    ax.set_xlabel(xlabel, fontsize=6.0, labelpad=1)
    ax.set_ylabel("Count", fontsize=6.0, labelpad=1)


def draw_corr_cell(
    ax: plt.Axes,
    r: float,
    p_value: float,
    cmap: mpl.colors.Colormap,
    norm: mpl.colors.Normalize,
) -> None:
    ax.set_facecolor(cmap(norm(r)))
    for spine in ax.spines.values():
        spine.set_color("white")
        spine.set_linewidth(1.6)
    ax.set_xticks([])
    ax.set_yticks([])
    text_color = "white" if abs(r) >= 0.55 else "#1f1f1f"
    ax.text(0.5, 0.46, f"{r:.2f}", ha="center", va="center", fontsize=6.7, color=text_color, transform=ax.transAxes)
    star_text = stars_for_p(p_value)
    if star_text:
        ax.text(0.5, 0.68, star_text, ha="center", va="center", fontsize=6.4, fontweight="bold", color=text_color, transform=ax.transAxes)


def make_figure(
    data: np.ndarray,
    columns: list[str],
    output_stem: Path,
    *,
    group_of: dict[str, str] | None = None,
    colors: dict[str, str] | None = None,
) -> list[str]:
    configure_matplotlib()
    colors = colors or REAL_COLORS
    corr = np.corrcoef(data, rowvar=False)
    n_vars = data.shape[1]
    n_samples = data.shape[0]
    limits = [padded_limits(data[:, j]) for j in range(n_vars)]

    group_palette: dict[str, str] = {}
    if group_of:
        for idx, group in enumerate(sorted(set(group_of.values()))):
            group_palette[group] = OKABE[idx % len(OKABE)]

    cmap = mpl.colormaps["RdBu_r"]
    norm = mpl.colors.Normalize(vmin=-1.0, vmax=1.0)

    fig = plt.figure(figsize=(9.2, 8.6))
    grid = fig.add_gridspec(
        n_vars,
        n_vars,
        left=0.055,
        right=0.905,
        bottom=0.055,
        top=0.965,
        wspace=0.08,
        hspace=0.08,
    )

    for row in range(n_vars):
        for col in range(n_vars):
            ax = fig.add_subplot(grid[row, col])
            if row > col:
                draw_scatter_cell(
                    ax, data[:, col], data[:, row], columns[col], columns[row], limits[col], limits[row], colors
                )
                style_small_axes(ax, row, col, n_vars)
            elif row == col:
                if group_of and columns[col] in group_of:
                    hist_color = mpl.colors.to_rgba(group_palette[group_of[columns[col]]], 0.45)
                    hist_edge = group_palette[group_of[columns[col]]]
                    label_color = group_palette[group_of[columns[col]]]
                else:
                    hist_color = mpl.colors.to_rgba(OKABE[5], 0.45)
                    hist_edge = OKABE[0]
                    label_color = "#000000"
                draw_hist_cell(ax, data[:, col], columns[col], limits[col], hist_color, hist_edge, colors)
                ax.set_xlabel(columns[col], fontsize=6.0, labelpad=1, color=label_color)
                style_small_axes(ax, row, col, n_vars)
            else:
                r = corr[row, col]
                p = fisher_p_value(r, n_samples)
                draw_corr_cell(ax, r, p, cmap, norm)

    cax = fig.add_axes([0.925, 0.145, 0.028, 0.79])
    sm = mpl.cm.ScalarMappable(norm=norm, cmap=cmap)
    cbar = fig.colorbar(sm, cax=cax)
    ticks = np.linspace(-1.0, 1.0, 9)
    cbar.set_ticks(ticks)
    cbar.set_ticklabels([f"{tick:.2f}" for tick in ticks])
    cbar.ax.tick_params(labelsize=6, width=0.45, length=2)
    cbar.outline.set_linewidth(0.45)

    return export_figure(
        fig,
        str(output_stem),
        formats=["pdf", "svg", "png"],
        size_inches=(9.2, 8.6),
        dpi=300,
        grayscale_preview=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="相关矩阵配对网格图（真实数据驱动模板）")
    parser.add_argument("--data", type=Path, help="宽表数值 CSV（契约见头部 docstring）")
    parser.add_argument("--groups", type=Path, help="可选变量分组 CSV（两列：column,group）")
    parser.add_argument("--out", type=Path, help="输出文件名前缀（不含扩展名）")
    parser.add_argument("--demo", action="store_true", help="确定性模拟数据演示，产物带 _demo 后缀")
    args = parser.parse_args()

    if args.demo:
        data = simulate_data()
        columns = VARIABLES
        group_of = None
        colors = DEMO_COLORS
        out = args.out or Path("correlation_pairgrid_demo")
    elif args.data:
        data, columns = load_wide_csv(args.data)
        group_of = load_groups(args.groups, columns) if args.groups else None
        colors = REAL_COLORS
        out = args.out or Path("correlation_pairgrid")
    else:
        parser.error("需要 --data <csv> 或 --demo")

    outputs = make_figure(data, columns, out, group_of=group_of, colors=colors)
    for path in outputs:
        print(path)


if __name__ == "__main__":
    main()
