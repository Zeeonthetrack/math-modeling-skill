#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多分类 SHAP 组合图（模板，改造自 mathmodel-figure-templates）。

视觉技法：共享 y 轴的组合面板——水平堆叠条形（各类 mean|SHAP|）叠加在
每类一个的 SHAP 蜂群子面板之上（点色映射特征值高低）+ 右侧特征值色条 +
底部类别图例。

数据契约（--data，CSV，UTF-8，长表）：
    class,feature,shap,value
    MVT,Mn,0.120,0.45
    MVT,Co,-0.031,0.12
    ...
    - class：类别名（决定蜂群面板数与条形分段数）
    - feature：特征名（决定 y 轴行数，按全局 mean|SHAP| 降序排列）
    - shap：SHAP 值（实数）；条形面板的 mean|shap| 由本脚本从该列计算
    - value：可选列，对应特征原始取值，用于蜂群着色（全表 min-max 归一化，
      High=高值 / Low=低值）；缺失时蜂群用类别色单色且不画色条

用法：
    python make_multiclass_shap_combo.py --data shap_long.csv --out figs/result_q4_shap
    python make_multiclass_shap_combo.py --demo
        # 确定性模拟数据（原模板 5 类 × 12 特征，种子 42 / 20260624），
        # 产物带 _demo 后缀，仅用于查看模板效果，不得作为交付物

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
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.patches import Patch
from matplotlib.ticker import MaxNLocator

FIGURE_SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FIGURE_SCRIPTS))

from export_figure import export_figure  # noqa: E402

# Okabe-Ito 色盲安全色板（正式数据模式用于类别色）
OKABE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#F0E442", "#000000"]

# 演示数据沿用原模板的类别与配色（仅 --demo 使用）
FEATURES = ["Mn", "Co", "Ge", "Fe", "Cd", "Sn", "In", "Pb", "Ga", "Sb", "Ag", "Cu"]
CLASSES = ["MVT", "SEDEX", "VMS", "epithermal", "skarn"]

CLASS_COLORS = {
    "MVT": "#ee8f9b",
    "SEDEX": "#f2b79e",
    "VMS": "#efcf86",
    "epithermal": "#bfd0c8",
    "skarn": "#baddea",
}

FEATURE_CMAP = LinearSegmentedColormap.from_list(
    "feature_value",
    ["#2166ac", "#1fa8c9", "#77d7c8", "#fff3a5", "#fdae61", "#d73027"],
)


@dataclass
class ShapData:
    classes: list[str]
    features: list[str]
    importances: np.ndarray  # (n_features, n_classes) mean|shap|
    shap: dict[tuple[str, str], np.ndarray]  # (class, feature) -> shap 值
    values: dict[tuple[str, str], np.ndarray] | None  # (class, feature) -> 特征值


def configure_matplotlib() -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "font.size": 10,
            "axes.linewidth": 0.8,
            "axes.spines.right": False,
            "axes.spines.top": False,
            "xtick.major.width": 0.8,
            "ytick.major.width": 0.8,
            "xtick.major.size": 4,
            "ytick.major.size": 0,
            "legend.frameon": False,
        }
    )


# ---------------------------------------------------------------- 演示数据（仅 --demo）
def importance_table() -> np.ndarray:
    """Approximate per-class mean absolute SHAP values for the reference layout."""
    return np.array(
        [
            [0.185, 0.070, 0.135, 0.035, 0.075],
            [0.050, 0.020, 0.105, 0.065, 0.210],
            [0.100, 0.035, 0.040, 0.035, 0.020],
            [0.085, 0.010, 0.045, 0.035, 0.015],
            [0.012, 0.065, 0.055, 0.035, 0.020],
            [0.010, 0.010, 0.048, 0.000, 0.083],
            [0.057, 0.035, 0.040, 0.020, 0.000],
            [0.012, 0.072, 0.010, 0.025, 0.010],
            [0.008, 0.050, 0.050, 0.043, 0.000],
            [0.006, 0.057, 0.008, 0.038, 0.010],
            [0.006, 0.013, 0.018, 0.015, 0.030],
            [0.015, 0.010, 0.020, 0.010, 0.018],
        ],
        dtype=float,
    )


def simulate_feature_values(rng: np.random.Generator, n_samples: int) -> np.ndarray:
    base = rng.normal(size=(n_samples, len(FEATURES)))
    trend = rng.normal(size=(n_samples, 1))
    values = 0.68 * base + 0.32 * trend
    ranks = np.argsort(np.argsort(values, axis=0), axis=0)
    return ranks / (n_samples - 1)


def simulate_shap_values(
    rng: np.random.Generator,
    feature_values: np.ndarray,
    importances: np.ndarray,
) -> list[np.ndarray]:
    n_samples, n_features = feature_values.shape
    class_ranges = np.array([5.0, 2.0, 2.5, 2.5, 2.5])
    directions = np.array(
        [
            [-1, -1, 1, 1, 1],
            [1, 1, -1, -1, 1],
            [-1, -1, 1, 1, -1],
            [1, 1, 1, -1, 1],
            [1, -1, -1, 1, 1],
            [-1, 1, 1, -1, -1],
            [1, -1, 1, 1, -1],
            [-1, 1, -1, 1, 1],
            [1, 1, -1, -1, -1],
            [-1, 1, 1, -1, 1],
            [1, -1, -1, 1, -1],
            [-1, 1, -1, 1, 1],
        ],
        dtype=float,
    )
    column_max = np.maximum(importances.max(axis=0), 1e-6)
    shap_by_class: list[np.ndarray] = []

    for class_idx, shap_range in enumerate(class_ranges):
        shap = np.zeros((n_samples, n_features), dtype=float)
        for feature_idx in range(n_features):
            strength = importances[feature_idx, class_idx] / column_max[class_idx]
            strength = np.clip(strength, 0.05, 1.0)
            centered = (feature_values[:, feature_idx] - 0.5) * 2.0
            nonlinear = 0.65 * centered + 0.35 * np.tanh(2.2 * centered)
            mode = rng.choice([-1.0, 1.0], size=n_samples, p=[0.52, 0.48])
            mode_shift = mode * shap_range * 0.13 * strength
            noise = rng.normal(scale=shap_range * (0.040 + 0.035 * strength), size=n_samples)
            weak_pull = rng.normal(scale=shap_range * 0.012, size=n_samples)
            shap[:, feature_idx] = (
                directions[feature_idx, class_idx] * nonlinear * shap_range * 0.52 * strength
                + mode_shift
                + noise
                + weak_pull
            )
        shap_by_class.append(shap)
    return shap_by_class


def beeswarm_y(
    rng: np.random.Generator,
    shap_values: np.ndarray,
    center_y: float,
    x_range: float,
) -> np.ndarray:
    density_proxy = np.exp(-0.5 * (shap_values / max(x_range * 0.35, 1e-6)) ** 2)
    spread = 0.045 + 0.105 * density_proxy
    return center_y + rng.normal(scale=spread, size=shap_values.size)


def _demo_data() -> ShapData:
    rng = np.random.default_rng(42)
    n_samples = 260
    importances = importance_table()
    feature_values = simulate_feature_values(rng, n_samples=n_samples)
    shap_by_class = simulate_shap_values(rng, feature_values, importances)

    shap: dict[tuple[str, str], np.ndarray] = {}
    values: dict[tuple[str, str], np.ndarray] = {}
    for class_idx, class_name in enumerate(CLASSES):
        for feature_idx, feature_name in enumerate(FEATURES):
            shap[(class_name, feature_name)] = shap_by_class[class_idx][:, feature_idx]
            values[(class_name, feature_name)] = feature_values[:, feature_idx]
    return ShapData(
        classes=list(CLASSES),
        features=list(FEATURES),
        importances=importances,
        shap=shap,
        values=values,
    )


# ---------------------------------------------------------------- 真实数据
def load_shap(csv_path: Path) -> ShapData:
    import pandas as pd

    frame = pd.read_csv(csv_path)
    missing = {"class", "feature", "shap"} - set(frame.columns)
    if missing:
        raise SystemExit(f"数据缺少必需列：{sorted(missing)}；契约见脚本头部 docstring")

    frame["shap"] = pd.to_numeric(frame["shap"], errors="coerce")
    if frame["shap"].isna().any():
        raise SystemExit("列 shap 含非数值或缺失内容")

    has_value = "value" in frame.columns
    if has_value:
        frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
        if frame["value"].isna().any():
            raise SystemExit("列 value 含非数值或缺失内容")

    frame = frame.dropna(subset=["class", "feature"])
    if frame.empty:
        raise SystemExit("数据为空或 class/feature 全部缺失")
    frame["class"] = frame["class"].astype(str)
    frame["feature"] = frame["feature"].astype(str)

    classes = list(dict.fromkeys(frame["class"]))
    features_raw = list(dict.fromkeys(frame["feature"]))

    # y 轴特征按全局 mean|shap| 降序（由数据计算，不硬编码）
    mean_abs = frame.assign(_abs=frame["shap"].abs()).groupby("feature", sort=False)["_abs"].mean()
    features = sorted(features_raw, key=lambda f: -float(mean_abs.get(f, 0.0)))

    f_idx = {f: i for i, f in enumerate(features)}
    c_idx = {c: i for i, c in enumerate(classes)}
    importances = np.zeros((len(features), len(classes)))
    shap: dict[tuple[str, str], np.ndarray] = {}
    values: dict[tuple[str, str], np.ndarray] = {} if has_value else None

    for (class_name, feature_name), group in frame.groupby(["class", "feature"], sort=False):
        shap_arr = group["shap"].to_numpy(dtype=float)
        shap[(class_name, feature_name)] = shap_arr
        importances[f_idx[feature_name], c_idx[class_name]] = float(np.abs(shap_arr).mean())
        if has_value:
            values[(class_name, feature_name)] = group["value"].to_numpy(dtype=float)

    return ShapData(classes=classes, features=features, importances=importances, shap=shap, values=values)


# ---------------------------------------------------------------- 绘制
def plot_multiclass_shap_combo(
    data: ShapData,
    output_stem: Path,
    *,
    class_colors: dict[str, str],
) -> list[str]:
    configure_matplotlib()

    n_features = len(data.features)
    n_classes = len(data.classes)
    y_positions = np.arange(n_features)
    use_value_color = data.values is not None

    fig_w = 11.8
    fig_h = 7.2 if n_features <= 12 else min(10.5, 7.2 + 0.18 * (n_features - 12))
    fig = plt.figure(figsize=(fig_w, fig_h), constrained_layout=False)

    left, bottom, height = 0.075, 0.165, 0.735
    total_width = 0.820 if use_value_color else 0.895
    panel_gap = 0.044
    panel_width = (total_width - panel_gap * (n_classes - 1)) / n_classes

    ax_imp = fig.add_axes([left, bottom, total_width, height])
    ax_imp.set_zorder(1)
    ax_imp.patch.set_alpha(0.0)

    running_left = np.zeros(n_features)
    for class_idx, class_name in enumerate(data.classes):
        ax_imp.barh(
            y_positions,
            data.importances[:, class_idx],
            left=running_left,
            height=0.56,
            color=class_colors[class_name],
            alpha=0.48,
            edgecolor=class_colors[class_name],
            linewidth=0.45,
            zorder=1,
        )
        running_left += data.importances[:, class_idx]

    bar_max = float(running_left.max()) if n_features else 0.0
    ax_imp.set_xlim(0.0, bar_max * 1.08 if bar_max > 0 else 1.0)
    ax_imp.set_ylim(n_features - 0.22, -0.82)
    ax_imp.set_yticks(y_positions)
    y_fs = 12 if n_features <= 12 else (10 if n_features <= 20 else 8)
    ax_imp.set_yticklabels(data.features, fontsize=y_fs)
    ax_imp.tick_params(axis="y", pad=8, length=0)
    ax_imp.xaxis.tick_top()
    ax_imp.xaxis.set_label_position("top")
    ax_imp.set_xlabel("Importance value", fontsize=16, labelpad=14)
    ax_imp.xaxis.set_major_locator(MaxNLocator(5))
    ax_imp.tick_params(axis="x", labelsize=12, pad=2, bottom=False, labelbottom=False)
    ax_imp.grid(axis="x", color="#222222", alpha=0.45, linewidth=0.75)
    ax_imp.spines["left"].set_visible(False)
    ax_imp.spines["right"].set_visible(False)
    ax_imp.spines["bottom"].set_visible(False)
    ax_imp.spines["top"].set_linewidth(1.0)

    norm = None
    if use_value_color:
        all_values = np.concatenate(list(data.values.values()))
        vmin, vmax = float(all_values.min()), float(all_values.max())
        if vmax <= vmin:
            vmin, vmax = vmin - 0.5, vmax + 0.5
        norm = Normalize(vmin=vmin, vmax=vmax)

    rng = np.random.default_rng(20260624)

    for class_idx, class_name in enumerate(data.classes):
        panel_left = left + class_idx * (panel_width + panel_gap)
        ax = fig.add_axes([panel_left, bottom, panel_width, height], sharey=ax_imp)
        ax.set_zorder(3)
        ax.patch.set_alpha(0.0)
        columns = [data.shap[(class_name, f)] for f in data.features if (class_name, f) in data.shap]
        abs_max = max((float(np.abs(c).max()) for c in columns), default=0.0)
        half_range = abs_max * 1.06 if abs_max > 0 else 1.0
        ax.set_xlim(-half_range, half_range)
        ax.set_ylim(ax_imp.get_ylim())
        ax.axvline(0, color="#222222", linewidth=0.9, alpha=0.72, zorder=2)
        ax.grid(False)
        ax.spines["left"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["top"].set_visible(False)
        ax.spines["bottom"].set_linewidth(0.85)
        ax.tick_params(axis="y", left=False, labelleft=False)
        ax.xaxis.set_major_locator(MaxNLocator(3))
        ax.tick_params(axis="x", length=4, pad=2, labelsize=9)
        ax.set_xlabel("SHAP value", fontsize=11, labelpad=2)

        for feature_idx, feature_name in enumerate(data.features):
            key = (class_name, feature_name)
            if key not in data.shap:
                continue
            shap_values = data.shap[key]
            y_swarm = beeswarm_y(rng, shap_values, y_positions[feature_idx], half_range)
            order = rng.permutation(shap_values.size)
            if use_value_color:
                feature_vals = data.values[key]
                ax.scatter(
                    shap_values[order],
                    y_swarm[order],
                    c=feature_vals[order],
                    cmap=FEATURE_CMAP,
                    norm=norm,
                    s=10,
                    alpha=0.76,
                    linewidths=0,
                    rasterized=True,
                    zorder=4,
                )
            else:
                ax.scatter(
                    shap_values[order],
                    y_swarm[order],
                    color=class_colors[class_name],
                    s=10,
                    alpha=0.76,
                    linewidths=0,
                    rasterized=True,
                    zorder=4,
                )

    if use_value_color:
        cax = fig.add_axes([0.925, bottom + 0.050, 0.012, height - 0.080])
        sm = mpl.cm.ScalarMappable(norm=norm, cmap=FEATURE_CMAP)
        cbar = fig.colorbar(sm, cax=cax)
        cbar.set_ticks([])
        cbar.outline.set_linewidth(0.8)
        cbar.ax.text(2.2, 1.0, "High", transform=cbar.ax.transAxes, ha="left", va="center", fontsize=10)
        cbar.ax.text(2.2, 0.0, "Low", transform=cbar.ax.transAxes, ha="left", va="center", fontsize=10)
        cbar.ax.set_ylabel("Feature value", rotation=90, labelpad=28, fontsize=11)

    handles = [
        Patch(
            facecolor=class_colors[class_name],
            edgecolor=class_colors[class_name],
            alpha=0.48,
            label=class_name,
        )
        for class_name in data.classes
    ]
    fig.legend(
        handles=handles,
        loc="lower center",
        bbox_to_anchor=(0.50, 0.040),
        ncol=min(n_classes, 5),
        handlelength=1.8,
        columnspacing=1.6,
        fontsize=12 if n_classes <= 5 else 9,
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
    parser = argparse.ArgumentParser(description="多分类 SHAP 组合图（真实数据驱动模板）")
    parser.add_argument("--data", type=Path, help="CSV 数据（契约见头部 docstring）")
    parser.add_argument("--out", type=Path, help="输出文件名前缀（不含扩展名）")
    parser.add_argument("--demo", action="store_true", help="确定性模拟数据演示，产物带 _demo 后缀")
    args = parser.parse_args()

    if args.demo:
        data = _demo_data()
        class_colors = dict(CLASS_COLORS)
        out = args.out or Path("multiclass_shap_combo_demo")
    elif args.data:
        data = load_shap(args.data)
        class_colors = {name: OKABE[i % 7] for i, name in enumerate(data.classes)}
        out = args.out or Path("multiclass_shap_combo")
    else:
        parser.error("需要 --data <csv> 或 --demo")

    outputs = plot_multiclass_shap_combo(data, out, class_colors=class_colors)
    for path in outputs:
        print(path)


if __name__ == "__main__":
    main()
