#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""泰勒图（模板，改造自 mathmodel-figure-templates）。

视觉技法：多面板泰勒图——标准差同心弧栅格 + 相关系数辐条 + 围绕参考点的
中心化 RMS 差虚线等值弧 + 观测参考点 + 面板字母标注（单面板不标注）。

数据契约（--data，CSV，UTF-8，长表）：
    model,std,corr,rmse,split
    XGBoost,1.020,0.985,0.180,training
    ANN,0.930,0.970,0.225,training
    ...
    - model：模型名（跨面板同名同色）
    - std：模型预测值序列的标准差（与参考同量纲，或归一化后的值，必须为正）
    - corr：与参考序列的皮尔逊相关系数，必须 ∈[-1,1]；负相关按 0 处理
      （第一象限泰勒图不表达负相关）
    - rmse：可选列，与参考的均方根误差，提供时附在图例标签中
    - split：可选列，数据子集名（如 training/testing/full dataset），
      提供时按取值分面板（保持出现顺序）；缺失时绘制单面板

归一化口径：参考点位于 x 轴 (ref_std, 0)。若 std 为原始物理单位，用
--ref-std 传入观测序列的标准差；若 std 已按观测标准差归一化（观测 = 1），
用 --ref-std 1.0。默认取数据中 std 的最大值（假定最优模型的方差接近观测）。
图中 RMS 等值弧以 ref_std 为圆心。

用法：
    python make_taylor_diagram.py --data taylor.csv --out figs/result_q3_taylor
    python make_taylor_diagram.py --data taylor.csv --ref-std 1.0
    python make_taylor_diagram.py --demo
        # 确定性模拟数据（原模板 5 模型 × 3 子集），产物带 _demo 后缀，
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

FIGURE_SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FIGURE_SCRIPTS))

from export_figure import export_figure  # noqa: E402

# Okabe-Ito 色盲安全色板（正式数据模式使用，黑色保留给 Observed 参考点）
OKABE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#F0E442", "#000000"]


@dataclass(frozen=True)
class TaylorPoint:
    model: str
    std: float
    corr: float
    rmse: float | None = None


# 演示数据与配色（原模板 5 模型 × 3 子集，仅 --demo 使用）
DEMO_COLORS = {
    "XGBoost": "#f2a51a",
    "ANN": "#d7191c",
    "GPR": "#2222a0",
    "NGBoost(normal)": "#36a852",
    "NGBoost(Log-normal)": "#0b6b20",
    "Observed": "#000000",
}

DEMO_PANELS: dict[str, list[TaylorPoint]] = {
    "training": [
        TaylorPoint("XGBoost", 1.020, 0.985),
        TaylorPoint("ANN", 0.930, 0.970),
        TaylorPoint("GPR", 1.080, 0.955),
        TaylorPoint("NGBoost(normal)", 0.980, 0.982),
        TaylorPoint("NGBoost(Log-normal)", 0.950, 0.974),
    ],
    "testing": [
        TaylorPoint("XGBoost", 1.000, 0.975),
        TaylorPoint("ANN", 0.960, 0.965),
        TaylorPoint("GPR", 1.060, 0.960),
        TaylorPoint("NGBoost(normal)", 1.020, 0.972),
        TaylorPoint("NGBoost(Log-normal)", 0.975, 0.968),
    ],
    "full dataset": [
        TaylorPoint("XGBoost", 1.010, 0.984),
        TaylorPoint("ANN", 0.940, 0.966),
        TaylorPoint("GPR", 1.085, 0.952),
        TaylorPoint("NGBoost(normal)", 0.990, 0.980),
        TaylorPoint("NGBoost(Log-normal)", 0.960, 0.972),
    ],
}


def configure_matplotlib() -> None:
    mpl.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Times", "DejaVu Serif", "serif"],
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "font.size": 8,
            "axes.linewidth": 0.7,
            "legend.frameon": True,
        }
    )


def polar_to_xy(std: float | np.ndarray, corr: float | np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    corr_arr = np.asarray(corr)
    std_arr = np.asarray(std)
    theta = np.arccos(np.clip(corr_arr, 0.0, 1.0))
    return std_arr * np.cos(theta), std_arr * np.sin(theta)


def _nice_step(raw: float) -> float:
    if raw <= 0:
        return 0.25
    exponent = np.floor(np.log10(raw))
    base = 10.0**exponent
    for mult in (1, 2, 2.5, 5, 10):
        if base * mult >= raw:
            return base * mult
    return base * 10


def draw_taylor_grid(ax: plt.Axes, ref_std: float, rmax: float, step: float) -> None:
    theta = np.linspace(0, np.pi / 2, 300)
    grid_color = "#cfcfcf"
    light_color = "#dedede"

    for radius in np.arange(step, rmax + step * 0.01, step):
        ax.plot(radius * np.cos(theta), radius * np.sin(theta), color=grid_color, lw=0.45, zorder=0)

    corr_ticks = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99]
    for corr in corr_ticks:
        x, y = polar_to_xy(rmax, corr)
        ax.plot([0, x], [0, y], color=light_color, lw=0.45, zorder=0)

    # Centered RMS-difference contours around the observed reference point.
    phi = np.linspace(0, np.pi, 400)
    for rms in [step * i for i in range(1, 6)]:
        x = ref_std + rms * np.cos(phi)
        y = rms * np.sin(phi)
        mask = (x >= 0) & (y >= 0) & (x**2 + y**2 <= rmax**2)
        ax.plot(x[mask], y[mask], ls="--", color="#bdbdbd", lw=0.45, alpha=0.85, zorder=0)

    ax.plot(ref_std * np.cos(theta), ref_std * np.sin(theta), ls="--", color="#cc7c8f", lw=0.65, alpha=0.75)
    ax.plot(rmax * np.cos(theta), rmax * np.sin(theta), color="#999999", lw=0.75)

    ax.set_xlim(0, rmax)
    ax.set_ylim(0, rmax)
    ax.set_aspect("equal", adjustable="box")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_color("#777777")
    ax.spines["left"].set_color("#777777")
    ax.set_xlabel("Standard Deviation", fontsize=8, labelpad=8)
    ax.set_ylabel("Standard Deviation", fontsize=8, labelpad=2)
    ticks = np.arange(0.0, rmax + step * 0.01, step)
    ax.set_xticks(ticks)
    ax.set_yticks(ticks)
    ax.set_xticklabels([f"{t:g}" for t in ticks], fontsize=6.2)
    ax.set_yticklabels([f"{t:g}" for t in ticks], fontsize=6.2)
    ax.tick_params(length=2.0, width=0.55, pad=1)

    for corr in corr_ticks:
        x, y = polar_to_xy(rmax * 1.02, corr)
        angle = np.degrees(np.arccos(corr)) - 90
        label = f"{corr:.2f}" if corr >= 0.95 else f"{corr:.1f}"
        ax.text(x, y, label, fontsize=6.2, ha="center", va="center", rotation=angle, rotation_mode="anchor")

    label_x, label_y = polar_to_xy(rmax * 0.94, 0.68)
    ax.text(
        label_x,
        label_y,
        "Correlation",
        fontsize=7.2,
        rotation=-43,
        rotation_mode="anchor",
        ha="center",
        va="center",
    )
    ax.text(ref_std, -0.034 * rmax, "Observed", fontsize=6.4, ha="center", va="top")


def draw_panel(
    ax: plt.Axes,
    points: list[TaylorPoint],
    color_map: dict[str, str],
    *,
    ref_std: float,
    rmax: float,
    step: float,
    letter: str | None = None,
    show_rmse: bool = False,
) -> None:
    draw_taylor_grid(ax, ref_std=ref_std, rmax=rmax, step=step)

    handles = []
    labels = []
    for point in points:
        x, y = polar_to_xy(point.std, point.corr)
        handle = ax.scatter(
            x, y, s=18, marker="o", facecolor=color_map[point.model], edgecolor="black", lw=0.35, zorder=5
        )
        label = point.model
        if show_rmse and point.rmse is not None:
            label = f"{point.model} (RMSE={point.rmse:.3g})"
        handles.append(handle)
        labels.append(label)
    obs_x, obs_y = polar_to_xy(ref_std, 1.0)
    handles.append(
        ax.scatter(
            obs_x, obs_y, s=18, marker="o", facecolor=color_map.get("Observed", "#000000"),
            edgecolor="black", lw=0.35, zorder=5,
        )
    )
    labels.append("Observed")

    legend_fontsize = 5.4 if len(labels) >= 6 else 6.5
    ax.legend(
        handles,
        labels,
        loc="upper right",
        bbox_to_anchor=(1.02, 1.10),
        fontsize=legend_fontsize,
        labelspacing=0.12,
        handlelength=0.9,
        handletextpad=0.25,
        borderpad=0.25,
        framealpha=0.86,
        edgecolor="#999999",
        facecolor="white",
        fancybox=False,
    )
    if letter:
        ax.text(0.50, -0.22, f"({letter})", transform=ax.transAxes, fontsize=9, ha="center", va="center")


# ---------------------------------------------------------------- 真实数据
def load_taylor(csv_path: Path) -> tuple[list[tuple[str | None, list[TaylorPoint]]], bool]:
    import pandas as pd

    frame = pd.read_csv(csv_path)
    missing = {"model", "std", "corr"} - set(frame.columns)
    if missing:
        raise SystemExit(f"数据缺少必需列：{sorted(missing)}；契约见脚本头部 docstring")

    std = pd.to_numeric(frame["std"], errors="coerce")
    corr = pd.to_numeric(frame["corr"], errors="coerce")
    if std.isna().any() or corr.isna().any():
        raise SystemExit("列 std/corr 含非数值或缺失内容")
    if not corr.between(-1.0, 1.0).all():
        raise SystemExit("列 corr 必须在 [-1, 1] 范围内")
    if not (std > 0).all():
        raise SystemExit("列 std 必须为正数")

    has_rmse = "rmse" in frame.columns
    if has_rmse:
        rmse = pd.to_numeric(frame["rmse"], errors="coerce")
        if rmse.isna().any():
            raise SystemExit("列 rmse 含非数值或缺失内容")
        frame["rmse"] = rmse

    has_split = "split" in frame.columns
    if has_split:
        if frame["split"].isna().any():
            raise SystemExit("split 列存在但含缺失值；每个模型必须归属一个子集")
        frame["split"] = frame["split"].astype(str)

    frame["model"] = frame["model"].astype(str)
    panels: dict[str | None, list[TaylorPoint]] = {}
    for row in frame.itertuples(index=False):
        row_dict = row._asdict()
        point = TaylorPoint(
            model=row_dict["model"],
            std=float(row_dict["std"]),
            corr=float(row_dict["corr"]),
            rmse=float(row_dict["rmse"]) if has_rmse else None,
        )
        key = row_dict["split"] if has_split else None
        panels.setdefault(key, []).append(point)
    return list(panels.items()), has_rmse


# ---------------------------------------------------------------- 绘制
def make_figure(
    panels: list[tuple[str | None, list[TaylorPoint]]],
    color_map: dict[str, str],
    output_stem: Path,
    *,
    ref_std: float,
    rmax: float | None = None,
    show_rmse: bool = False,
) -> list[str]:
    configure_matplotlib()
    if rmax is None:
        max_std = max((p.std for _, points in panels for p in points), default=ref_std)
        rmax = max(ref_std, max_std) * 1.6
    step = _nice_step(rmax / 7.0)

    n_panels = len(panels)
    fig_w = 4.54 + 3.132 * (n_panels - 1)
    fig_h = 5.7
    fig = plt.figure(figsize=(fig_w, fig_h))

    for idx, (_, points) in enumerate(panels):
        ax = fig.add_axes([(1.242 + idx * 3.132) / fig_w, 0.16, 2.322 / fig_w, 0.59])
        letter = chr(ord("a") + idx) if n_panels > 1 else None
        draw_panel(
            ax,
            points,
            color_map,
            ref_std=ref_std,
            rmax=rmax,
            step=step,
            letter=letter,
            show_rmse=show_rmse,
        )

    return export_figure(
        fig,
        str(output_stem),
        formats=["pdf", "svg", "png"],
        size_inches=(fig_w, fig_h),
        dpi=300,
        grayscale_preview=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="泰勒图（真实数据驱动模板）")
    parser.add_argument("--data", type=Path, help="CSV 数据（契约见头部 docstring）")
    parser.add_argument("--out", type=Path, help="输出文件名前缀（不含扩展名）")
    parser.add_argument("--ref-std", type=float, help="参考（观测）标准差；默认取数据中 std 最大值")
    parser.add_argument("--demo", action="store_true", help="确定性模拟数据演示，产物带 _demo 后缀")
    args = parser.parse_args()

    if args.demo:
        panels = [(key, list(points)) for key, points in DEMO_PANELS.items()]
        color_map = dict(DEMO_COLORS)
        ref_std = 1.0
        rmax = 1.75
        show_rmse = False
        out = args.out or Path("taylor_diagram_demo")
    elif args.data:
        panels, show_rmse = load_taylor(args.data)
        if not panels:
            raise SystemExit("数据为空")
        all_std = [p.std for _, points in panels for p in points]
        ref_std = args.ref_std if args.ref_std is not None else max(all_std)
        if ref_std <= 0:
            raise SystemExit("--ref-std 必须为正数")
        model_order: list[str] = []
        for _, points in panels:
            for point in points:
                if point.model not in model_order:
                    model_order.append(point.model)
        color_map = {model: OKABE[i % 7] for i, model in enumerate(model_order)}
        color_map["Observed"] = OKABE[7]
        rmax = None
        out = args.out or Path("taylor_diagram")
    else:
        parser.error("需要 --data <csv> 或 --demo")

    outputs = make_figure(
        panels,
        color_map,
        out,
        ref_std=ref_std,
        rmax=rmax,
        show_rmse=show_rmse,
    )
    for path in outputs:
        print(path)


if __name__ == "__main__":
    main()
