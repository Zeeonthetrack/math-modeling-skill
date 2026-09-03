#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交叉验证 ROC 曲线与置信区间图（模板，改造自 mathmodel-figure-templates）。

视觉技法：K 折折线（细、低透明度）+ 均值±SD 置信带 + 对角参考线 + 等比例坐标轴，
可选底部指标汇总表。

数据契约（--data，CSV，UTF-8，长表）：
    fold,model,fpr,tpr
    1,LR,0.0,0.0
    1,LR,0.02,0.31
    ...
    - fold：折编号（int）
    - model：模型名（任意列数，每个模型至少 2 折）
    - fpr/tpr：[0,1] 内假阳性率/真阳性率，每折需含 (0,0) 与 (1,1) 端点（缺失时自动补）

可选 --metrics CSV（宽表）：首列 model，其余数值列将渲染进底部指标表；
未提供时表格显示由 ROC 数据计算的 AUC mean±SD。

用法：
    python make_cv_roc_ci.py --data cv_roc.csv --out figs/result_q1_roc
    python make_cv_roc_ci.py --demo            # 确定性模拟数据，产物带 _demo 后缀，
                                                # 仅用于查看模板效果，不得作为交付物

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

# numpy >= 2.0 将 trapz 更名为 trapezoid；按可用性选择，兼容 1.x 与 2.x
_trapezoid = getattr(np, "trapezoid", None) or np.trapz

# Okabe-Ito 色盲安全色板（正式数据模式使用）
OKABE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#F0E442", "#000000"]

GRID = np.linspace(0.0, 1.0, 101)


def configure_matplotlib() -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "font.size": 10,
            "axes.linewidth": 0.75,
            "legend.frameon": True,
        }
    )


def interpolate_fold(fpr: np.ndarray, tpr: np.ndarray, grid: np.ndarray) -> np.ndarray:
    interp = np.interp(grid, fpr, tpr)
    interp[0] = 0.0
    interp[-1] = 1.0
    return interp


# ---------------------------------------------------------------- 演示数据（仅 --demo）
def _demo_specs() -> list[dict]:
    return [
        {"name": "LR", "auc_mean": 0.889, "auc_std": 0.026, "noise": 0.030},
        {"name": "RF", "auc_mean": 0.906, "auc_std": 0.029, "noise": 0.026},
        {"name": "XGBoost", "auc_mean": 0.895, "auc_std": 0.032, "noise": 0.030},
        {"name": "LightGBM", "auc_mean": 0.902, "auc_std": 0.039, "noise": 0.035},
        {"name": "SVM", "auc_mean": 0.861, "auc_std": 0.043, "noise": 0.042},
    ]


def _demo_curves() -> dict[str, list[tuple[np.ndarray, np.ndarray]]]:
    """确定性模拟 5 模型 × 5 折 ROC 曲线（演示模式专用，不代表任何真实研究）。"""
    curves: dict[str, list[tuple[np.ndarray, np.ndarray]]] = {}
    for idx, spec in enumerate(_demo_specs()):
        rng = np.random.default_rng(814 + idx * 17)
        offsets = np.array([-1.20, -0.45, 0.05, 0.55, 1.05])
        offsets = (offsets - offsets.mean()) / offsets.std(ddof=1)
        fold_curves = []
        for delta in offsets * spec["auc_std"]:
            target = float(np.clip(spec["auc_mean"] + delta, 0.72, 0.98))
            exponent = np.clip(target, 0.60, 0.985) / (1.0 - np.clip(target, 0.60, 0.985))
            low = np.sort(rng.beta(0.72, 4.6, size=22))
            high = np.sort(rng.uniform(0.22, 1.0, size=9))
            fpr = np.unique(np.r_[0.0, low, high, 1.0])
            tpr = 1.0 - (1.0 - fpr) ** exponent
            tpr = np.clip(tpr + rng.normal(0.0, spec["noise"], size=fpr.size), 0.0, 1.0)
            tpr = np.maximum.accumulate(tpr)
            tpr[0], tpr[-1] = 0.0, 1.0
            fold_curves.append((fpr, tpr))
        curves[spec["name"]] = fold_curves
    return curves


# ---------------------------------------------------------------- 真实数据
def load_curves(csv_path: Path) -> dict[str, list[tuple[np.ndarray, np.ndarray]]]:
    import pandas as pd

    frame = pd.read_csv(csv_path)
    missing = {"fold", "model", "fpr", "tpr"} - set(frame.columns)
    if missing:
        raise SystemExit(f"数据缺少必需列：{sorted(missing)}；契约见脚本头部 docstring")
    for column in ("fpr", "tpr"):
        values = frame[column].to_numpy(dtype=float)
        if not (np.all(np.isfinite(values)) and values.min() >= 0.0 and values.max() <= 1.0):
            raise SystemExit(f"列 {column} 必须是 [0,1] 内的有限数值")

    curves: dict[str, list[tuple[np.ndarray, np.ndarray]]] = {}
    for model, group in frame.groupby("model", sort=False):
        fold_curves = []
        for _, fold in group.groupby("fold", sort=True):
            fpr = fold["fpr"].to_numpy(dtype=float)
            tpr = fold["tpr"].to_numpy(dtype=float)
            order = np.argsort(fpr)
            fpr, tpr = fpr[order], tpr[order]
            if fpr[0] > 0.0:  # 自动补 (0,0) 与 (1,1) 端点
                fpr, tpr = np.r_[0.0, fpr], np.r_[0.0, tpr]
            if fpr[-1] < 1.0:
                fpr, tpr = np.r_[fpr, 1.0], np.r_[tpr, 1.0]
            fold_curves.append((fpr, tpr))
        if len(fold_curves) < 2:
            raise SystemExit(f"模型 {model} 只有 {len(fold_curves)} 折；交叉验证图至少需要 2 折")
        curves[str(model)] = fold_curves
    return curves


def load_metrics(csv_path: Path) -> list[list[str]]:
    import pandas as pd

    frame = pd.read_csv(csv_path)
    return [[str(v) for v in row] for row in frame.itertuples(index=False)]


# ---------------------------------------------------------------- 绘制
def summarize(curves: dict[str, list[tuple[np.ndarray, np.ndarray]]]) -> dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]]:
    stats = {}
    for model, fold_curves in curves.items():
        matrix = np.vstack([interpolate_fold(fpr, tpr, GRID) for fpr, tpr in fold_curves])
        mean_tpr = matrix.mean(axis=0)
        std_tpr = matrix.std(axis=0, ddof=1) if len(fold_curves) > 1 else np.zeros_like(mean_tpr)
        mean_tpr[0], mean_tpr[-1] = 0.0, 1.0
        stats[model] = (mean_tpr, np.clip(mean_tpr - std_tpr, 0.0, 1.0), np.clip(mean_tpr + std_tpr, 0.0, 1.0))
    return stats


def add_summary_table(fig: plt.Figure, rows: list[list[str]], columns: list[str], *, bottom: float = 0.035) -> float:
    """底部指标汇总表：渲染表头与全部数据行，返回表区顶部位置（figure 坐标）。

    表高随行数自适应；此前仅渲染首行（rows[:1]）导致多模型指标静默丢失。
    """
    row_h = 0.040
    height = 0.072 + len(rows) * row_h
    table_ax = fig.add_axes([0.045, bottom, 0.91, height])
    table_ax.axis("off")
    slots = len(rows) + 1
    xs = np.linspace(0.0, 0.92, len(columns))
    table_ax.plot([0, 1], [1.0, 1.0], color="#b8b8b8", linewidth=0.8)
    table_ax.plot([0, 1], [1.0 - 1.0 / slots, 1.0 - 1.0 / slots], color="#b8b8b8", linewidth=0.8)
    header_y = 1.0 - 0.5 / slots
    for x, label in zip(xs, columns):
        table_ax.text(x, header_y, label, fontsize=7.5, fontweight="bold", ha="left", va="center")
    for i, row in enumerate(rows):
        y = 1.0 - (i + 1.5) / slots
        for x, value in zip(xs, row):
            table_ax.text(x, y, value, fontsize=7.3, color="#555555", ha="left", va="center")
    table_ax.set_xlim(0, 1)
    table_ax.set_ylim(0, 1)
    return bottom + height


def make_figure(
    curves: dict[str, list[tuple[np.ndarray, np.ndarray]]],
    output_stem: Path,
    *,
    metrics: list[list[str]] | None = None,
    caption: str | None = None,
    palette: list[str] | None = None,
) -> list[str]:
    configure_matplotlib()
    stats = summarize(curves)
    palette = palette or OKABE

    fig = plt.figure(figsize=(7.4, 7.8))

    # 每模型各折 AUC（图例与默认指标表共用，只算一次）
    fold_aucs_by_model = {
        model: [_trapezoid(interpolate_fold(fpr, tpr, GRID), GRID) for fpr, tpr in fold_curves]
        for model, fold_curves in curves.items()
    }

    # 底部指标表：外部 --metrics 优先，否则由 ROC 数据计算 AUC 摘要（禁止硬编码统计量）
    if metrics:
        table_columns = [str(v) for v in metrics[0]]
        table_rows = [[str(v) for v in row] for row in metrics[1:]]
    else:
        table_columns = ["Model", "AUC (mean)", "AUC (SD)"]
        table_rows = [
            [model, f"{np.mean(aucs):.3f}", f"{np.std(aucs, ddof=1):.3f}"]
            for model, aucs in fold_aucs_by_model.items()
        ]
    table_top = add_summary_table(fig, table_rows, table_columns)

    # 表区与可选图注自下而上排布，主绘图区随之自适应抬升
    ax_bottom = table_top + 0.03
    if caption:
        caption_ax = fig.add_axes([0.06, ax_bottom, 0.88, 0.05])
        caption_ax.axis("off")
        caption_ax.text(0.0, 0.70, caption, fontsize=8.5, color="#4b4b4b", ha="left", va="center")
        ax_bottom += 0.075

    ax = fig.add_axes([0.17, ax_bottom, 0.70, 0.955 - ax_bottom])

    legend_handles, legend_labels = [], []
    for idx, (model, fold_curves) in enumerate(curves.items()):
        color = palette[idx % len(palette)]
        mean_tpr, lower, upper = stats[model]
        for fpr, tpr in fold_curves:
            ax.step(fpr, tpr, where="post", color=color, alpha=0.13, linewidth=0.65, zorder=1)
        ax.fill_between(GRID, lower, upper, step="post", color=color, alpha=0.14, linewidth=0, zorder=2)
        (line,) = ax.step(GRID, mean_tpr, where="post", color=color, linewidth=1.15, zorder=4)
        legend_handles.append(line)
        auc = _trapezoid(mean_tpr, GRID)
        fold_aucs = fold_aucs_by_model[model]
        spread = np.std(fold_aucs, ddof=1) if len(fold_aucs) > 1 else 0.0
        legend_labels.append(f"{model}: AUC = {auc:.3f} ± {spread:.3f}")

    ax.plot([0, 1], [0, 1], linestyle="--", color="#a34545", linewidth=0.8, alpha=0.78, zorder=0)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("False Positive Rate", fontsize=10)
    ax.set_ylabel("True Positive Rate", fontsize=10)
    ax.set_xticks(np.arange(0.0, 1.01, 0.1))
    ax.set_yticks(np.arange(0.0, 1.01, 0.1))
    ax.tick_params(labelsize=8.5, length=3, width=0.7)
    ax.grid(True, color="#bcbcbc", alpha=0.28, linewidth=0.6)
    ax.legend(
        legend_handles,
        legend_labels,
        loc="lower right",
        fontsize=9,
        framealpha=0.72,
        facecolor="white",
        edgecolor="#d9d9d9",
        handlelength=2.1,
        labelspacing=0.65,
        borderpad=0.45,
    )

    return export_figure(
        fig,
        str(output_stem),
        formats=["pdf", "svg", "png"],
        size_inches=(7.4, 7.8),
        dpi=300,
        grayscale_preview=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="交叉验证 ROC 曲线与置信区间图（真实数据驱动模板）")
    parser.add_argument("--data", type=Path, help="CSV 数据（契约见头部 docstring）")
    parser.add_argument("--metrics", type=Path, help="可选指标表 CSV（首行为表头，首列 model）")
    parser.add_argument("--caption", help="可选图注文本")
    parser.add_argument("--out", type=Path, help="输出文件名前缀（不含扩展名）")
    parser.add_argument("--demo", action="store_true", help="确定性模拟数据演示，产物带 _demo 后缀")
    args = parser.parse_args()

    if args.demo:
        curves = _demo_curves()
        out = args.out or Path("cv_roc_ci_demo")
    elif args.data:
        curves = load_curves(args.data)
        out = args.out or Path("cv_roc_ci")
    else:
        parser.error("需要 --data <csv> 或 --demo")

    metrics = load_metrics(args.metrics) if args.metrics else None
    outputs = make_figure(curves, out, metrics=metrics, caption=args.caption)
    for path in outputs:
        print(path)


if __name__ == "__main__":
    main()
