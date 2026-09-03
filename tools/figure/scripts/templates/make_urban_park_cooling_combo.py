#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""城市公园降温效应多面板组合图（模板，改造自 mathmodel-figure-templates）。

视觉技法：横向堆叠计数条形 + 分组云雨图（KDE 云 + 抖动散点 + 横向箱线）+
逐城市竖向箱线图（中位数/均值标记/1.5IQR 触须/均值连线）三级组合版式，
左列为堆叠条形面板与城市索引/图例面板，右侧为按指标排布的两列面板网格。

数据契约（--data，CSV，UTF-8，长表，必需）：
    city,group,metric,value
    Shanghai,Megacity,PCM,2.85
    Shanghai,Megacity,PCM,3.02
    Shanghai,Megacity,PCD,142.5
    Hangzhou,Large City,PCM,3.40
    ...
    - city：城市/样本名（建议唯一；同名同组会被合并为同一城市，同名跨组报错）
    - group：分组名（按首次出现顺序作为云雨图行序，建议 ≤8 组）
    - metric：指标名（按首次出现顺序；每个指标生成一张云雨图 + 一张逐城市
      箱线图，在右侧两列网格依次排布）
    - value：有限数值（不允许 NaN/Inf）；每个 城市×指标 至少 5 条观测
      （KDE 与箱线统计的最低要求）

可选 --stacked（CSV，UTF-8，宽表，绘制左上角堆叠计数条形面板）：
    city,Show a cooling effect,No significant cooling effect
    Shanghai,314,46
    Hangzhou,139,39
    ...
    - city：名称（按 CSV 行序绘制；独立面板，无需与 --data 一一对应）
    - 其余各列：每列为一个堆叠分段，列名即图例文本，值为非负计数
    - 未提供时左上角堆叠条形面板省略，城市索引/图例面板扩展至整个左列

用法：
    python make_urban_park_cooling_combo.py --data park_metrics.csv --stacked park_counts.csv --out figs/fig1
    python make_urban_park_cooling_combo.py --data park_metrics.csv        # 省略堆叠条形面板
    python make_urban_park_cooling_combo.py --demo                        # 确定性模拟数据，默认输出名带 _demo 后缀，
                                                                           # 仅查看模板效果，不得作为交付物

输出（经 export_figure）：<stem>.png(300dpi) + <stem>.pdf + <stem>.svg +
<stem>_grayscale.png 灰度预览（色盲安全检查）。真实模式下全部统计量（KDE、
分位数、均值、坐标范围）均由 CSV 数据计算，无硬编码。
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
from matplotlib.patches import Patch, Rectangle

FIGURE_SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FIGURE_SCRIPTS))

from export_figure import export_figure  # noqa: E402

# Okabe-Ito 色盲安全色板（真实数据模式使用）
OKABE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#F0E442", "#000000"]


@dataclass(frozen=True)
class CitySpec:
    name: str
    group: str


@dataclass(frozen=True)
class StackedData:
    cities: list[str]
    segments: list[str]
    counts: list[list[float]]  # 与 cities 对齐；每行与 segments 对齐


@dataclass(frozen=True)
class Palette:
    groups: dict[str, str]  # group -> 颜色（云雨图与箱线图填充）
    segments: list[str]  # 堆叠条形各分段颜色
    mean_marker: str  # 均值三角标记
    mean_line: str  # 均值连线
    median_line: str  # 中位数线


def configure_matplotlib() -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "font.size": 9,
            "axes.linewidth": 0.75,
            "xtick.major.width": 0.65,
            "ytick.major.width": 0.65,
            "legend.frameon": False,
        }
    )


def kde_1d(values: np.ndarray, grid: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    std = max(np.std(values, ddof=1), 1e-6)
    bandwidth = max(1.06 * std * values.size ** (-1 / 5), std * 0.16, 1e-5)
    z = (grid[:, None] - values[None, :]) / bandwidth
    density = np.exp(-0.5 * z**2).mean(axis=1) / (bandwidth * np.sqrt(2 * np.pi))
    return density / density.max() if density.max() > 0 else density


def nice_bounds(values: np.ndarray) -> tuple[float, float]:
    """由数据计算"整齐"的坐标范围（真实模式禁止硬编码轴限）。"""
    lo, hi = float(np.min(values)), float(np.max(values))
    if hi <= lo:
        pad = max(abs(lo), 1.0) * 0.5
        lo, hi = lo - pad, hi + pad
    span = hi - lo
    step = 10.0 ** math.floor(math.log10(span))
    while span / step < 2.5:
        step /= 2.0
    lo_n = math.floor(lo / step) * step
    hi_n = math.ceil(hi / step) * step
    if lo_n > 0 and lo_n < 0.2 * hi_n:
        lo_n = 0.0
    return lo_n, hi_n


# ---------------------------------------------------------------- 演示数据（仅 --demo，确定性模拟）
DEMO_METRICS = ["PCM", "PCD", "PCI", "PCG"]

GROUP_ORDER = ["Megacity", "Large City", "Medium City I", "Medium City II", "Small City"]
GROUP_COLORS = {
    "Megacity": "#34485b",
    "Large City": "#557280",
    "Medium City I": "#759b9d",
    "Medium City II": "#95bdae",
    "Small City": "#c8ded4",
}


CITY_SPECS = [
    CitySpec("Shanghai", "Megacity"),
    CitySpec("Hangzhou", "Large City"),
    CitySpec("Nanjing", "Large City"),
    CitySpec("Suzhou", "Large City"),
    CitySpec("Hefei", "Medium City I"),
    CitySpec("Ningbo", "Large City"),
    CitySpec("Wuxi", "Large City"),
    CitySpec("Changzhou", "Medium City I"),
    CitySpec("Shaoxing", "Medium City I"),
    CitySpec("Nantong", "Medium City I"),
    CitySpec("Yangzhou", "Medium City II"),
    CitySpec("Yancheng", "Medium City II"),
    CitySpec("Taizhou", "Medium City I"),
    CitySpec("Wuhu", "Medium City II"),
    CitySpec("Jiaxing", "Medium City I"),
    CitySpec("Taizhou", "Medium City I"),
    CitySpec("Ma'anshan", "Medium City II"),
    CitySpec("Zhenjiang", "Medium City II"),
    CitySpec("Jinhua", "Medium City II"),
    CitySpec("Huzhou", "Medium City II"),
    CitySpec("Anqing", "Small City"),
    CitySpec("Zhoushan", "Small City"),
    CitySpec("Tongling", "Small City"),
    CitySpec("Chuzhou", "Medium City II"),
    CitySpec("Chizhou", "Small City"),
    CitySpec("Xuancheng", "Small City"),
]


BAR_COUNTS = [
    ("Shanghai", 314, 46),
    ("Hangzhou", 139, 39),
    ("Nanjing", 110, 37),
    ("Suzhou", 89, 29),
    ("Ningbo", 77, 34),
    ("Wuxi", 61, 22),
    ("Hefei", 67, 12),
    ("Yangzhou", 48, 27),
    ("Changzhou", 53, 8),
    ("Nantong", 39, 7),
    ("Shaoxing", 34, 11),
    ("Jiaxing", 32, 4),
    ("Taizhou", 19, 1),
    ("Huzhou", 19, 0),
    ("Taizhou", 23, 1),
    ("Zhenjiang", 22, 1),
    ("Ma'anshan", 21, 4),
    ("Jinhua", 14, 1),
    ("Yancheng", 17, 6),
    ("Wuhu", 16, 2),
    ("Chuzhou", 17, 1),
    ("Xuancheng", 13, 1),
    ("Tongling", 8, 1),
    ("Anqing", 8, 0),
    ("Zhoushan", 8, 0),
    ("Chizhou", 8, 0),
]


def simulate_city_metric_data(seed: int = 20260629) -> dict[str, list[np.ndarray]]:
    rng = np.random.default_rng(seed)
    group_offsets = {
        "Megacity": {"PCM": 3.0, "PCD": 150.0, "PCI": 0.019, "PCG": 0.95},
        "Large City": {"PCM": 2.8, "PCD": 155.0, "PCI": 0.020, "PCG": 0.95},
        "Medium City I": {"PCM": 3.1, "PCD": 150.0, "PCI": 0.019, "PCG": 0.98},
        "Medium City II": {"PCM": 3.2, "PCD": 145.0, "PCI": 0.018, "PCG": 0.96},
        "Small City": {"PCM": 3.6, "PCD": 160.0, "PCI": 0.020, "PCG": 1.05},
    }
    ranges = {
        "PCM": (0.0, 8.8, 0.85),
        "PCD": (10.0, 340.0, 36.0),
        "PCI": (0.001, 0.060, 0.0075),
        "PCG": (0.05, 2.45, 0.28),
    }

    data: dict[str, list[np.ndarray]] = {metric: [] for metric in DEMO_METRICS}
    for city_idx, city in enumerate(CITY_SPECS):
        n = 42 + int(52 * (np.sin(city_idx * 0.57) + 1) / 2)
        phase = np.sin(city_idx / 3.1)
        secondary = np.cos(city_idx / 2.0)
        for metric in DEMO_METRICS:
            low, high, spread = ranges[metric]
            base = group_offsets[city.group][metric]
            if metric == "PCM":
                mean = base + 0.45 * phase + 0.018 * city_idx
                values = rng.normal(mean, spread, n)
            elif metric == "PCD":
                mean = base + 20.0 * phase + 11.0 * secondary
                values = rng.normal(mean, spread, n)
            elif metric == "PCI":
                mean = base + 0.0035 * phase - 0.00008 * city_idx
                values = rng.normal(mean, spread, n)
            else:
                mean = base + 0.16 * phase + 0.05 * secondary
                values = rng.normal(mean, spread, n)
            data[metric].append(np.clip(values, low, high))
    return data


def _demo_data() -> tuple[list[CitySpec], list[str], dict[str, list[np.ndarray]], StackedData]:
    """确定性模拟数据（演示模式专用，不代表任何真实研究；含种子）。"""
    metric_data = simulate_city_metric_data()
    observations = {metric: list(metric_data[metric]) for metric in DEMO_METRICS}
    stacked = StackedData(
        cities=[name for name, _, _ in BAR_COUNTS],
        segments=["Show a cooling effect", "No significant cooling effect"],
        counts=[[float(effect), float(no_effect)] for _, effect, no_effect in BAR_COUNTS],
    )
    return list(CITY_SPECS), list(DEMO_METRICS), observations, stacked


def demo_palette() -> Palette:
    """演示模式保留原模板配色。"""
    return Palette(
        groups=dict(GROUP_COLORS),
        segments=["#315f5e", "#9a9a9a"],
        mean_marker="#d44d5d",
        mean_line="#2f6791",
        median_line="#315f5e",
    )


# ---------------------------------------------------------------- 真实数据
def load_observations(csv_path: Path) -> tuple[list[CitySpec], list[str], dict[str, list[np.ndarray]]]:
    import pandas as pd

    frame = pd.read_csv(csv_path)
    missing = {"city", "group", "metric", "value"} - set(frame.columns)
    if missing:
        raise SystemExit(f"--data 缺少必需列：{sorted(missing)}；契约见脚本头部 docstring")
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    if frame["value"].isna().any():
        raise SystemExit("value 列存在非数值或缺失（NaN）数据")

    cities: list[CitySpec] = []
    city_index: dict[str, int] = {}
    metrics: list[str] = []
    buckets: dict[tuple[int, str], list[float]] = {}
    for row in frame.itertuples(index=False):
        city, group, metric = str(row.city), str(row.group), str(row.metric)
        value = float(row.value)
        idx = city_index.get(city)
        if idx is None:
            idx = len(cities)
            city_index[city] = idx
            cities.append(CitySpec(city, group))
        elif cities[idx].group != group:
            raise SystemExit(f"城市 {city} 对应的 group 不一致：{cities[idx].group} / {group}；一个城市只能属于一个组")
        if metric not in metrics:
            metrics.append(metric)
        buckets.setdefault((idx, metric), []).append(value)

    if not cities or not metrics:
        raise SystemExit("--data CSV 无有效数据行")

    observations: dict[str, list[np.ndarray]] = {}
    for metric in metrics:
        per_city = []
        for idx, city in enumerate(cities):
            bucket = buckets.get((idx, metric))
            if bucket is None or len(bucket) < 5:
                raise SystemExit(
                    f"城市 {city.name}×指标 {metric} 仅 {0 if bucket is None else len(bucket)} 条观测；"
                    "每个 城市×指标 至少需要 5 条（KDE/箱线统计要求）"
                )
            per_city.append(np.asarray(bucket, dtype=float))
        observations[metric] = per_city
    return cities, metrics, observations


def load_stacked(csv_path: Path) -> StackedData:
    import pandas as pd

    frame = pd.read_csv(csv_path)
    if "city" not in frame.columns:
        raise SystemExit("--stacked CSV 缺少 city 列；契约见脚本头部 docstring")
    segments = [column for column in frame.columns if column != "city"]
    if not segments:
        raise SystemExit("--stacked CSV 除 city 外至少还需要一个计数列")
    if frame.empty:
        raise SystemExit("--stacked CSV 无数据行")
    matrix = frame[segments].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    if not np.all(np.isfinite(matrix)) or (matrix < 0).any():
        raise SystemExit("--stacked CSV 的计数列必须是非负有限数值")
    cities = [str(v) for v in frame["city"].tolist()]
    counts = [[float(v) for v in row] for row in matrix]
    return StackedData(cities, segments, counts)


def real_palette(groups: list[str], n_segments: int) -> Palette:
    return Palette(
        groups={group: OKABE[i % len(OKABE)] for i, group in enumerate(groups)},
        segments=[OKABE[i % len(OKABE)] for i in range(n_segments)],
        mean_marker=OKABE[1],
        mean_line=OKABE[0],
        median_line="#000000",
    )


# ---------------------------------------------------------------- 绘制
def style_axis(ax: plt.Axes) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(length=2.5, color="#333333", labelcolor="#111111")


def draw_panel_a(ax: plt.Axes, stacked: StackedData, palette: Palette, letter: str) -> None:
    counts = np.asarray(stacked.counts, dtype=float)
    totals = counts.sum(axis=1)
    x_max = nice_bounds(totals)[1]
    y = np.arange(len(stacked.cities))

    left = np.zeros(len(stacked.cities))
    for si, segment in enumerate(stacked.segments):
        color = palette.segments[si % len(palette.segments)]
        widths = counts[:, si]
        ax.barh(y, widths, left=left, color=color, edgecolor="white", linewidth=0.45, height=0.74)
        for yi, width, offset in zip(y, widths, left):
            if width <= 0:
                continue
            if width >= 0.035 * x_max:
                ax.text(offset + width / 2, yi, f"{width:g}", ha="center", va="center", color="white", fontsize=8)
            else:
                ax.text(offset + width + 0.012 * x_max, yi, f"{width:g}", ha="left", va="center", color=color, fontsize=7)
        left = left + widths

    ax.set_yticks(y)
    ax.set_yticklabels(stacked.cities, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlim(0, x_max)
    ax.tick_params(axis="y", length=0, pad=1)
    ax.grid(axis="x", color="#e1e1e1", lw=0.45)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_linewidth(0.65)

    header = Rectangle((0, -1.48), x_max, 0.94, facecolor="#b9b9b9", edgecolor="#444444", linewidth=0.7, clip_on=False)
    ax.add_patch(header)
    ax.text(x_max / 2, -1.02, "Counts by City", ha="center", va="center", fontsize=10)

    handles = [
        Patch(facecolor=palette.segments[si % len(palette.segments)], edgecolor="white", label=segment)
        for si, segment in enumerate(stacked.segments)
    ]
    ax.legend(handles=handles, title="Legend", loc="lower right", bbox_to_anchor=(0.98, 0.01), fontsize=8, title_fontsize=9)
    ax.text(-0.052, 1.02, letter, transform=ax.transAxes, fontsize=11)


def draw_horizontal_box(ax: plt.Axes, values: np.ndarray, y: float, color: str) -> None:
    q1, med, q3 = np.percentile(values, [25, 50, 75])
    iqr = q3 - q1
    lo = np.min(values[values >= q1 - 1.5 * iqr])
    hi = np.max(values[values <= q3 + 1.5 * iqr])
    box_h = 0.18
    ax.plot([lo, hi], [y, y], color="#3f3f3f", lw=0.6, zorder=3)
    ax.plot([lo, lo], [y - box_h / 2, y + box_h / 2], color="#3f3f3f", lw=0.6, zorder=3)
    ax.plot([hi, hi], [y - box_h / 2, y + box_h / 2], color="#3f3f3f", lw=0.6, zorder=3)
    ax.add_patch(
        Rectangle((q1, y - box_h / 2), q3 - q1, box_h, facecolor=color, edgecolor="#3f3f3f", linewidth=0.55, zorder=4)
    )
    ax.plot([med, med], [y - box_h / 2, y + box_h / 2], color="white", lw=0.8, zorder=5)


def draw_raincloud(
    ax: plt.Axes,
    grouped_values: dict[str, np.ndarray],
    groups: list[str],
    metric: str,
    palette: Palette,
    x_range: tuple[float, float],
    *,
    rng_seed: int,
    show_ylabels: bool,
) -> None:
    x_min, x_max = x_range
    grid = np.linspace(x_min, x_max, 320)
    rng = np.random.default_rng(rng_seed)
    n_groups = len(groups)
    y_min, y_max = -0.55, n_groups - 0.22
    y_span = y_max - y_min

    for row, group in enumerate(groups):
        y = n_groups - 1 - row
        values = grouped_values[group]
        color = palette.groups[group]
        density = kde_1d(values, grid) * 0.53
        ax.fill_between(grid, y, y + density, color=color, alpha=0.96, linewidth=0)
        ax.plot(grid, y + density, color="#53666a", lw=0.65)
        ax.hlines(y, x_min, x_max, color="#cfcfcf", lw=0.6)
        sample = values if values.size < 330 else rng.choice(values, 330, replace=False)
        jitter = rng.uniform(-0.24, -0.08, size=sample.size)
        ax.scatter(sample, y + jitter, s=2.0, color="#333333", alpha=0.46, linewidths=0, zorder=2)
        draw_horizontal_box(ax, values, y + 0.08, color)
        mean = float(np.mean(values))
        ax.axvline(mean, ymin=(y + 0.03 - y_min) / y_span, ymax=(y + 0.52 - y_min) / y_span, color="white", lw=0.6, ls=(0, (2, 2)))

    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.set_title(metric, fontsize=9, fontweight="bold", pad=5)
    ax.grid(axis="x", color="#ececec", lw=0.45)
    ax.set_axisbelow(True)
    ax.set_yticks(range(n_groups))
    ax.set_yticklabels(list(reversed(groups)) if show_ylabels else [], fontsize=8)
    ax.tick_params(axis="y", length=0, pad=2)
    style_axis(ax)


def draw_vertical_boxplot_panel(
    ax: plt.Axes,
    metric: str,
    cities: list[CitySpec],
    per_city_values: list[np.ndarray],
    palette: Palette,
    y_range: tuple[float, float],
) -> None:
    means = []
    for idx, (city, values) in enumerate(zip(cities, per_city_values, strict=True), start=1):
        color = palette.groups[city.group]
        q1, med, q3 = np.percentile(values, [25, 50, 75])
        iqr = q3 - q1
        lo = np.min(values[values >= q1 - 1.5 * iqr])
        hi = np.max(values[values <= q3 + 1.5 * iqr])
        means.append(float(np.mean(values)))

        ax.plot([idx, idx], [lo, hi], color="#a0a0a0", lw=0.65, zorder=1)
        ax.plot([idx - 0.17, idx + 0.17], [lo, lo], color="#a0a0a0", lw=0.65, zorder=1)
        ax.plot([idx - 0.17, idx + 0.17], [hi, hi], color="#a0a0a0", lw=0.65, zorder=1)
        ax.add_patch(
            Rectangle(
                (idx - 0.32, q1),
                0.64,
                q3 - q1,
                facecolor=color,
                edgecolor="white",
                linewidth=0.5,
                alpha=0.78,
                zorder=2,
            )
        )
        ax.plot([idx - 0.30, idx + 0.30], [med, med], color=palette.median_line, lw=1.0, zorder=3)
        ax.scatter(idx, means[-1], marker="^", s=14, color=palette.mean_marker, edgecolor="white", linewidth=0.25, zorder=4)

    ax.plot(np.arange(1, len(cities) + 1), means, color=palette.mean_line, lw=0.75, alpha=0.72, zorder=3)
    ax.set_xlim(0.3, len(cities) + 0.7)
    ax.set_ylim(*y_range)
    ax.set_ylabel(metric, fontsize=9)
    ax.set_xticks(np.arange(1, len(cities) + 1))
    ax.set_xticklabels([str(i) for i in range(1, len(cities) + 1)], fontsize=7)
    ax.tick_params(axis="x", length=0, pad=1)
    ax.tick_params(axis="y", labelsize=8)
    ax.grid(axis="y", color="#efefef", lw=0.45)
    for spine in ax.spines.values():
        spine.set_linewidth(0.75)


def add_city_and_legend_panel(
    ax: plt.Axes,
    cities: list[CitySpec],
    groups: list[str],
    palette: Palette,
    letter: str,
    *,
    tall: bool,
) -> None:
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_autoscale_on(False)
    ax.text(-0.05, 1.03, letter, transform=ax.transAxes, fontsize=11)

    n = len(cities)
    rows_per_col = max(1, math.ceil(n / 3))
    if tall:  # 无堆叠面板时左列整体交给本面板，内容适当拉开
        top, city_bottom, y0, scale, max_gap = 0.985, 0.55, 0.38, 1.2, 0.065
    else:
        top, city_bottom, y0, scale, max_gap = 0.96, 0.56, 0.31, 1.0, 0.05
    row_spacing = min(max_gap, (top - city_bottom) / (rows_per_col - 1)) if rows_per_col > 1 else max_gap

    x_positions = [0.00, 0.36, 0.70]
    for col in range(3):
        start = col * rows_per_col
        for row, city in enumerate(cities[start : start + rows_per_col]):
            ax.text(x_positions[col], top - row * row_spacing, f"{start + row + 1:02d}.{city.name}", ha="left", va="top", fontsize=8)

    # 箱线图元素图例（左半）
    ax.add_patch(Rectangle((0.00, y0), 0.09, 0.035, facecolor="white", edgecolor="#333333", linewidth=0.7))
    ax.text(0.12, y0 + 0.017, "25%-75%", va="center", fontsize=8)
    ax.plot([0.00, 0.09], [y0 - 0.050 * scale, y0 - 0.050 * scale], color=palette.median_line, lw=2.0)
    ax.text(0.12, y0 - 0.050 * scale, "Median Line", va="center", fontsize=8)
    ax.scatter(0.045, y0 - 0.105 * scale, marker="^", s=16, color=palette.mean_marker, edgecolor="white", linewidth=0.3)
    ax.text(0.12, y0 - 0.105 * scale, "Mean", va="center", fontsize=8)
    ax.plot([0.00, 0.09], [y0 - 0.160 * scale, y0 - 0.160 * scale], color="#777777", lw=0.8)
    ax.plot([0.00, 0.00], [y0 - 0.177 * scale, y0 - 0.143 * scale], color="#777777", lw=0.8)
    ax.plot([0.09, 0.09], [y0 - 0.177 * scale, y0 - 0.143 * scale], color="#777777", lw=0.8)
    ax.text(0.12, y0 - 0.160 * scale, "Range with 1.5IQR", va="center", fontsize=8)
    ax.plot([0.00, 0.09], [y0 - 0.215 * scale, y0 - 0.215 * scale], color=palette.mean_line, lw=0.9)
    ax.text(0.12, y0 - 0.215 * scale, "Connecting line Mean", va="center", fontsize=8)

    # 分组颜色图例（右半）
    n_groups = len(groups)
    swatch_spacing = min(0.054, 0.30 / (n_groups - 1)) if n_groups > 1 else 0.054
    for idx, group in enumerate(groups):
        y = y0 - idx * swatch_spacing
        ax.add_patch(Rectangle((0.57, y), 0.09, 0.035, facecolor=palette.groups[group], edgecolor="white", linewidth=0.5))
        ax.text(0.69, y + 0.017, group, va="center", fontsize=8)


def make_figure(
    cities: list[CitySpec],
    metrics: list[str],
    observations: dict[str, list[np.ndarray]],
    output_stem: Path,
    *,
    stacked: StackedData | None = None,
    palette: Palette | None = None,
) -> list[str]:
    configure_matplotlib()
    groups: list[str] = []
    for city in cities:
        if city.group not in groups:
            groups.append(city.group)
    if palette is None:
        palette = real_palette(groups, len(stacked.segments) if stacked is not None else 0)

    grouped_values = {
        metric: {
            group: np.concatenate(
                [values for city, values in zip(cities, observations[metric], strict=True) if city.group == group]
            )
            for group in groups
        }
        for metric in metrics
    }
    metric_ranges = {metric: nice_bounds(np.concatenate(observations[metric])) for metric in metrics}

    fig = plt.figure(figsize=(13.0, 10.0), facecolor="white")
    letters = iter("abcdef")

    if stacked is not None:
        ax_a = fig.add_axes([0.055, 0.455, 0.295, 0.500])
        draw_panel_a(ax_a, stacked, palette, next(letters))

    rain_letter = next(letters)
    rows = max(1, math.ceil(len(metrics) / 2))
    rain_h = (0.490 - 0.040 * (rows - 1)) / rows  # 4 指标（2 行）时与原模板完全一致
    box_h = (0.365 - 0.025 * (rows - 1)) / rows
    col_specs = [(0.405, 0.315), (0.765, 0.215)]

    for mi, metric in enumerate(metrics):
        r, c = divmod(mi, 2)
        x, w = col_specs[c]
        ax_r = fig.add_axes([x, 0.945 - r * (rain_h + 0.040) - rain_h, w, rain_h])
        draw_raincloud(
            ax_r,
            grouped_values[metric],
            groups,
            metric,
            palette,
            metric_ranges[metric],
            rng_seed=101 * (mi + 1),
            show_ylabels=(c == 0),
        )
        if mi == 0:
            ax_r.text(-0.10, 1.06, rain_letter, transform=ax_r.transAxes, fontsize=11)

        ax_b = fig.add_axes([x, 0.435 - r * (box_h + 0.025) - box_h, w, box_h])
        draw_vertical_boxplot_panel(ax_b, metric, cities, observations[metric], palette, metric_ranges[metric])

    legend_rect = [0.055, 0.070, 0.295, 0.885] if stacked is None else [0.055, 0.070, 0.295, 0.335]
    ax_c_legend = fig.add_axes(legend_rect)
    add_city_and_legend_panel(ax_c_legend, cities, groups, palette, next(letters), tall=stacked is None)

    return export_figure(
        fig,
        str(output_stem),
        formats=["pdf", "svg", "png"],
        size_inches=(13.0, 10.0),
        dpi=300,
        grayscale_preview=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="城市公园降温效应多面板组合图（真实数据驱动模板）")
    parser.add_argument("--data", type=Path, help="长表 CSV（city,group,metric,value），契约见头部 docstring")
    parser.add_argument("--stacked", type=Path, help="可选宽表 CSV（首列 city，其余列为计数分段），绘制左上角堆叠条形面板")
    parser.add_argument("--out", type=Path, help="输出文件名前缀（不含扩展名）")
    parser.add_argument("--demo", action="store_true", help="确定性模拟数据演示，默认输出名带 _demo 后缀，不得作为交付物")
    args = parser.parse_args()

    if args.demo:
        cities, metrics, observations, stacked = _demo_data()
        palette = demo_palette()
        out = args.out or Path("urban_park_cooling_combo_demo")
    elif args.data:
        cities, metrics, observations = load_observations(args.data)
        stacked = load_stacked(args.stacked) if args.stacked else None
        palette = None
        out = args.out or Path("urban_park_cooling_combo")
    else:
        parser.error("需要 --data <csv> 或 --demo")

    outputs = make_figure(cities, metrics, observations, out, stacked=stacked, palette=palette)
    for path in outputs:
        print(path)


if __name__ == "__main__":
    main()
