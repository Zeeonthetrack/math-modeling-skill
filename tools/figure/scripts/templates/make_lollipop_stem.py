#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""棒棒糖图 / 火柴杆图（lollipop / stem）——国赛扰动·灵敏度·序列对比专用模板。

视觉技法（对照国一论文范本图5-8/5-9 提炼）：
垂线自基准线（或零线）升起、端点大圆点收束，一条深色基准横线贯穿全图；
深单色（默认 Okabe-Ito 蓝 #0072B2）、去顶右边框、刻度朝外、五号字号阶梯，
值标签直标在端点上方——"看得清清楚楚毫不费眼力"。

适用场景：蒙特卡洛扰动结果、灵敏度序列、逐样本/逐时刻对比、残差序列。
不适用：连续函数曲线（用折线图）、占比构成（用柱状图）。

数据契约（--data，CSV，UTF-8）：
    seq,value,label
    1,1.234,方案A
    2,0.987,方案B
    ...
    - seq：必选，数值或字符串，横轴位置（数值按大小排序，字符串按出现顺序）
    - value：必选，数值，纵轴值
    - label：可选，逐点标注文本（给出时直标在端点旁，字号小一档）
    - 至少 3 行数据

用法：
    python make_lollipop_stem.py --data perturb.csv --out figs/process_q1_lollipop \
        --baseline 1.400555 --xlabel "扰动序列号" --ylabel "遮蔽时长(s)"
    python make_lollipop_stem.py --demo
        # 确定性模拟数据（种子 20260902），产物带 _demo 后缀，
        # 仅用于查看模板效果，不得作为交付物

输出（经 export_figure）：.png(300dpi) + .pdf + .svg + _grayscale.png 灰度预览。
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", tempfile.mkdtemp(prefix="mpl-"))

import matplotlib as mpl

mpl.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

FIGURE_SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FIGURE_SCRIPTS))

from export_figure import export_figure  # noqa: E402
from setup_style import configure_chinese_fonts  # noqa: E402

# 深色系主色（色盲安全）：默认蓝，可用 --color 换对比色 #D55E00 / 绿 #009E73
DEFAULT_COLOR = "#0072B2"
BASELINE_COLOR = "#222222"

DEMO_SEED = 20260902


def configure_matplotlib() -> None:
    """五号字号阶梯 + 去顶右边框 + 刻度朝外（cumcm 质感）。"""
    configure_chinese_fonts()
    mpl.rcParams.update(
        {
            "font.size": 10.5,
            "axes.labelsize": 10.5,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "axes.spines.right": False,
            "axes.spines.top": False,
            "axes.linewidth": 1.0,
            "xtick.major.width": 1.0,
            "ytick.major.width": 1.0,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "axes.unicode_minus": False,
        }
    )


def load_real_data(path: Path) -> tuple[np.ndarray, np.ndarray, list[str] | None]:
    df = pd.read_csv(path)
    cols = [c.strip().lower() for c in df.columns]
    df.columns = cols
    if "seq" not in cols or "value" not in cols:
        raise ValueError("CSV 必须包含 seq 与 value 两列（label 可选），见脚本 docstring 数据契约")
    df = df.dropna(subset=["seq", "value"])
    if len(df) < 3:
        raise ValueError(f"有效数据仅 {len(df)} 行，至少需 3 行")
    seq = df["seq"].to_numpy()
    value = df["value"].astype(float).to_numpy()
    if np.issubdtype(seq.dtype, np.number):
        order = np.argsort(seq.astype(float))
        seq, value = seq[order], value[order]
        labels = df["label"].astype(str).to_numpy()[order].tolist() if "label" in cols else None
    else:
        labels = df["label"].astype(str).tolist() if "label" in cols else None
    return seq, value, labels


def make_demo_data() -> tuple[np.ndarray, np.ndarray, list[str] | None, float]:
    """20 次扰动序列，基准 1.40，带正负波动——复刻范本图5-8 形态。"""
    rng = np.random.default_rng(DEMO_SEED)
    seq = np.arange(1, 21)
    value = 1.40 + rng.normal(0, 0.35, 20)
    return seq, value, None, 1.40


def draw_lollipop(
    seq: np.ndarray,
    value: np.ndarray,
    labels: list[str] | None,
    *,
    baseline: float | None,
    xlabel: str,
    ylabel: str,
    color: str,
    value_labels: bool,
) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(4.8, 3.2), layout="constrained")

    x = np.arange(len(value))
    base = 0.0 if baseline is None else float(baseline)

    # 垂线 + 端点（棒棒糖本体）
    ax.vlines(x, base, value, color=color, linewidth=1.4, alpha=0.85, zorder=2)
    ax.plot(x, value, "o", color=color, markersize=7,
            markeredgecolor="white", markeredgewidth=1.0, zorder=3)

    # 基准横线贯穿全图
    if baseline is not None:
        ax.axhline(base, color=BASELINE_COLOR, linewidth=1.2, zorder=1)
        ax.text(len(value) - 0.4, base, f"基准 {base:g}", ha="right",
                va="bottom" if value.mean() >= base else "top",
                fontsize=9, color=BASELINE_COLOR)

    # 直标：逐点 label 或数值
    span = max(float(value.max() - value.min()), 1e-9)
    offset = span * 0.04
    if labels is not None:
        for xi, yi, text in zip(x, value, labels):
            ax.text(xi, yi + offset, text, ha="center", va="bottom", fontsize=8)
    elif value_labels:
        for xi, yi in zip(x, value):
            ax.text(xi, yi + offset, f"{yi:g}", ha="center", va="bottom", fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels([str(s) for s in seq])
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.margins(x=0.03)
    return fig


def main() -> int:
    p = argparse.ArgumentParser(description="棒棒糖图/火柴杆图模板（国赛扰动·灵敏度专用）")
    p.add_argument("--data", type=Path, help="CSV 数据文件（seq,value[,label]）")
    p.add_argument("--out", default="figs/lollipop", help="输出路径前缀（不含扩展名）")
    p.add_argument("--baseline", type=float, default=None, help="基准值；给出则画贯穿基准横线")
    p.add_argument("--xlabel", default="序号")
    p.add_argument("--ylabel", default="数值")
    p.add_argument("--color", default=DEFAULT_COLOR, help="主色（默认 Okabe-Ito 蓝 #0072B2）")
    p.add_argument("--value-labels", action="store_true", help="端点直标数值（无 label 列时）")
    p.add_argument("--demo", action="store_true", help="演示模式：模拟数据，产物带 _demo 后缀")
    args = p.parse_args()

    if not args.demo and args.data is None:
        p.error("真实数据模式必须提供 --data；查看模板效果请用 --demo")

    configure_matplotlib()

    if args.demo:
        seq, value, labels, auto_base = make_demo_data()
        baseline = args.baseline if args.baseline is not None else auto_base
        out = args.out if args.out.endswith("_demo") else args.out + "_demo"
        if args.xlabel == "序号":
            args.xlabel = "扰动序列号"
        if args.ylabel == "数值":
            args.ylabel = "遮蔽时长(s)"
    else:
        seq, value, labels = load_real_data(args.data)
        baseline = args.baseline
        out = args.out

    fig = draw_lollipop(seq, value, labels, baseline=baseline,
                        xlabel=args.xlabel, ylabel=args.ylabel,
                        color=args.color, value_labels=args.value_labels)
    written = export_figure(fig, out, formats=["png", "pdf", "svg"],
                            size_inches=(4.8, 3.2), dpi=300, grayscale_preview=True)
    for w in written:
        print(f"  written: {w}")
    if args.demo:
        print("[demo] 演示产物带 _demo 后缀，仅用于查看模板效果，禁止作为交付物。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
