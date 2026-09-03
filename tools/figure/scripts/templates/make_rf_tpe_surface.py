#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""超参调优 3D 响应曲面图（模板，改造自 mathmodel-figure-templates）。

视觉技法：将调参试验点（两超参数 + 目标值）经反距离加权（IDW）插值成
光滑 3D 曲面（coolwarm 配色、透明面板、细网格），并标记数据中的最优点
（星标 + 垂直虚线 + 数值标注），右侧附目标值 colorbar。

数据契约（--data，CSV，UTF-8）：
    max_depth,n_estimators,RMSE
    12.0,85.0,0.512
    33.5,142.0,0.398
    ...
    - 恰好 3 个数值列：前两列 = 两个超参数，第三列 = 目标值；
      列名直接用作坐标轴标签（非数值列自动忽略）
    - 默认目标值越小越好（如 RMSE/损失）；越大越好时加 --maximize
    - 曲面插值与最优点均由数据计算

用法：
    python make_rf_tpe_surface.py --data trials.csv --out figs/result_q4_surface
    python make_rf_tpe_surface.py --data trials.csv --maximize
    python make_rf_tpe_surface.py --demo            # 确定性模拟数据，产物带 _demo 后缀，
                                                        # 仅用于查看模板效果，不得作为交付物

输出（经 export_figure）：.png(450dpi) + .pdf + .svg + _grayscale.png 灰度预览。
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

# Okabe-Ito 色盲安全色板（最优点标记使用其中的橙色）
OKABE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#F0E442", "#000000"]
BEST_MARKER = OKABE[1]

DEMO_COLUMNS = ["max_depth", "n_estimators", "RMSE"]


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


# ---------------------------------------------------------------- 演示数据（仅 --demo）
def true_rmse_surface(max_depth: np.ndarray, n_estimators: np.ndarray) -> np.ndarray:
    x = np.asarray(max_depth, dtype=float)
    y = np.asarray(n_estimators, dtype=float)

    base = 0.505
    broad_slope = 0.018 * np.exp(-x / 9.0) + 0.010 * np.cos(y / 32.0)
    red_ridge = 0.165 * np.exp(-((x - 6.0) / 5.2) ** 2 - ((y - 162.0) / 34.0) ** 2)
    red_cap = 0.045 * np.exp(-((x - 3.0) / 3.5) ** 2 - ((y - 190.0) / 24.0) ** 2)
    warm_hump = 0.052 * np.exp(-((x - 22.0) / 5.5) ** 2 - ((y - 96.0) / 21.0) ** 2)
    cool_basin = -0.116 * np.exp(-((x - 30.0) / 8.5) ** 2 - ((y - 112.0) / 29.0) ** 2)
    narrow_trough = -0.047 * np.exp(-((x - 34.5) / 3.2) ** 2 - ((y - 124.0) / 9.5) ** 2)
    ripples = 0.011 * np.sin(x * 0.70 + y * 0.055) + 0.007 * np.cos(x * 1.50 - y * 0.035)
    return np.clip(base + broad_slope + red_ridge + red_cap + warm_hump + cool_basin + narrow_trough + ripples, 0.375, 0.655)


def simulate_tpe_trials(seed: int = 20260505, n_trials: int = 210) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    depth_trials = []
    estimator_trials = []
    rmse_trials = []

    for trial in range(n_trials):
        if trial < 65:
            depth = rng.uniform(1, 40)
            estimators = rng.uniform(5, 200)
        elif trial < 150:
            # TPE-like exploitation: sample more often near the low-RMSE basin.
            depth = rng.normal(30, 7.0)
            estimators = rng.normal(116, 28.0)
            if rng.random() < 0.24:
                depth = rng.uniform(8, 40)
                estimators = rng.uniform(70, 170)
        else:
            depth = rng.normal(34, 4.5)
            estimators = rng.normal(120, 17.0)
            if rng.random() < 0.15:
                depth = rng.uniform(1, 18)
                estimators = rng.uniform(130, 195)

        depth = float(np.clip(depth, 1, 40))
        estimators = float(np.clip(estimators, 5, 200))
        noise = rng.normal(0.0, 0.008 + 0.00003 * estimators)
        rmse = float(true_rmse_surface(depth, estimators) + noise)
        depth_trials.append(depth)
        estimator_trials.append(estimators)
        rmse_trials.append(rmse)

    return np.array(depth_trials), np.array(estimator_trials), np.array(rmse_trials)


# ---------------------------------------------------------------- 真实数据
def load_trials_csv(csv_path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    import pandas as pd

    frame = pd.read_csv(csv_path)
    numeric = [str(c) for c in frame.columns if pd.api.types.is_numeric_dtype(frame[c])]
    if len(numeric) != 3:
        raise SystemExit(
            f"需要恰好 3 个数值列（前两列=超参数，第三列=目标值），实际 {len(numeric)} 个；"
            "契约见脚本头部 docstring"
        )
    frame = frame[numeric].dropna()
    if len(frame) < 5:
        raise SystemExit("有效样本不足：插值曲面至少需要 5 行无缺失数据")
    values = frame.to_numpy(dtype=float)
    return values[:, 0], values[:, 1], values[:, 2], numeric


# ---------------------------------------------------------------- 插值
def idw_response_surface(
    x_trials: np.ndarray,
    y_trials: np.ndarray,
    z_trials: np.ndarray,
    x_grid: np.ndarray,
    y_grid: np.ndarray,
) -> np.ndarray:
    """反距离加权插值：纯由试验点数据计算响应曲面。"""
    x_scale = float(np.ptp(x_trials)) or 1.0
    y_scale = float(np.ptp(y_trials)) or 1.0
    surface = np.empty_like(x_grid, dtype=float)

    trial_x = x_trials / x_scale
    trial_y = y_trials / y_scale
    grid_x = x_grid / x_scale
    grid_y = y_grid / y_scale

    for row in range(x_grid.shape[0]):
        dx = grid_x[row, :, None] - trial_x[None, :]
        dy = grid_y[row, :, None] - trial_y[None, :]
        dist2 = dx * dx + dy * dy + 0.0045
        weights = 1.0 / (dist2**2.15)
        local = (weights @ z_trials) / weights.sum(axis=1)
        surface[row, :] = local
    return surface


# ---------------------------------------------------------------- 绘制
def make_figure(
    x_trials: np.ndarray,
    y_trials: np.ndarray,
    z_trials: np.ndarray,
    columns: list[str],
    output_stem: Path,
    *,
    maximize: bool = False,
) -> list[str]:
    configure_matplotlib()

    x_lin = np.linspace(x_trials.min(), x_trials.max(), 115)
    y_lin = np.linspace(y_trials.min(), y_trials.max(), 125)
    x_grid, y_grid = np.meshgrid(x_lin, y_lin)
    z_grid = idw_response_surface(x_trials, y_trials, z_trials, x_grid, y_grid)

    z_lo, z_hi = float(z_grid.min()), float(z_grid.max())
    if np.isclose(z_lo, z_hi):
        z_lo, z_hi = z_lo - 0.5, z_hi + 0.5
    z_pad = 0.05 * (z_hi - z_lo)

    fig = plt.figure(figsize=(9.2, 7.2))
    ax = fig.add_axes([0.02, 0.05, 0.78, 0.88], projection="3d")
    norm = mpl.colors.Normalize(vmin=z_lo, vmax=z_hi)
    surf = ax.plot_surface(
        x_grid,
        y_grid,
        z_grid,
        cmap="coolwarm",
        norm=norm,
        linewidth=0,
        antialiased=True,
        shade=True,
        rstride=1,
        cstride=1,
        alpha=0.96,
    )

    ax.set_xlabel(columns[0], fontsize=13, labelpad=10)
    ax.set_ylabel(columns[1], fontsize=13, labelpad=10)
    ax.set_zlabel(columns[2], fontsize=12, labelpad=8)
    ax.set_xlim(x_trials.min(), x_trials.max())
    ax.set_ylim(y_trials.max(), y_trials.min())  # 保留原模板的 y 轴反转
    ax.set_zlim(z_lo - z_pad, z_hi + z_pad)
    ax.xaxis.set_major_locator(mpl.ticker.MaxNLocator(8))
    ax.yaxis.set_major_locator(mpl.ticker.MaxNLocator(8))
    ax.zaxis.set_major_locator(mpl.ticker.MaxNLocator(6))
    ax.tick_params(labelsize=8, pad=2)
    ax.view_init(elev=31, azim=42)
    ax.set_box_aspect((1.18, 1.45, 0.72))

    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.pane.set_facecolor((1, 1, 1, 0))
        axis.pane.set_edgecolor("#d0d0d0")
        # 网格样式经私有 _axinfo 设置：仅在其可用时应用；matplotlib 未来版本
        # 若移除该结构，退回默认网格样式而不是崩溃
        grid_info = getattr(axis, "_axinfo", None)
        if isinstance(grid_info, dict) and isinstance(grid_info.get("grid"), dict):
            grid_info["grid"]["color"] = (0.72, 0.72, 0.72, 0.65)
            grid_info["grid"]["linewidth"] = 0.6

    # 最优点标记：由试验数据计算（默认目标值最小者为最优）
    best_idx = int(np.argmax(z_trials)) if maximize else int(np.argmin(z_trials))
    bx, by, bz = float(x_trials[best_idx]), float(y_trials[best_idx]), float(z_trials[best_idx])
    ax.plot(
        [bx, bx],
        [by, by],
        [z_lo - z_pad, bz],
        color=BEST_MARKER,
        linestyle="--",
        linewidth=0.9,
        alpha=0.85,
    )
    ax.scatter(
        [bx],
        [by],
        [bz],
        color=BEST_MARKER,
        s=60,
        marker="*",
        edgecolors="white",
        linewidths=0.5,
        depthshade=False,
        zorder=10,
    )
    ax.text(
        bx,
        by,
        bz + 0.06 * (z_hi - z_lo),
        f" best {columns[2]}={bz:.4g}",
        color=BEST_MARKER,
        fontsize=9,
        ha="left",
        va="bottom",
    )

    cax = fig.add_axes([0.84, 0.23, 0.028, 0.48])
    cbar = fig.colorbar(surf, cax=cax)
    cbar.set_label(columns[2], fontsize=11, labelpad=10)
    cbar.set_ticks(np.linspace(z_lo, z_hi, 5))
    cbar.ax.tick_params(labelsize=8)
    cbar.outline.set_linewidth(0.75)

    return export_figure(
        fig,
        str(output_stem),
        formats=["pdf", "svg", "png"],
        size_inches=(9.2, 7.2),
        dpi=450,
        grayscale_preview=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="超参调优 3D 响应曲面图（真实数据驱动模板）")
    parser.add_argument("--data", type=Path, help="调参试验 CSV（契约见头部 docstring）")
    parser.add_argument("--maximize", action="store_true", help="目标值越大越好（默认越小越好）")
    parser.add_argument("--out", type=Path, help="输出文件名前缀（不含扩展名）")
    parser.add_argument("--demo", action="store_true", help="确定性模拟数据演示，产物带 _demo 后缀")
    args = parser.parse_args()

    if args.demo:
        x_trials, y_trials, z_trials = simulate_tpe_trials()
        columns = DEMO_COLUMNS
        out = args.out or Path("rf_tpe_surface_demo")
    elif args.data:
        x_trials, y_trials, z_trials, columns = load_trials_csv(args.data)
        out = args.out or Path("rf_tpe_surface")
    else:
        parser.error("需要 --data <csv> 或 --demo")

    outputs = make_figure(x_trials, y_trials, z_trials, columns, out, maximize=args.maximize)
    for path in outputs:
        print(path)


if __name__ == "__main__":
    main()
