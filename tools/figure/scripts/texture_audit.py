#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""成图质感审计（texture audit）——把"字小、色浅、配色脏"从肉眼抱怨变成机器门禁。

设计动机（融合自 K-Dense scientific-visualization 的 audit 思路，本地化重写）：
check_figure.py 管"文件合规"（格式/DPI/字体嵌入），visual_qa.py 管"布局硬伤"
（缺字/裁切/重叠），本脚本管第三层——**成图观感的可机器化指标**：

- INK-DENSITY（墨色浓度，WARN/FAIL）：非近白像素占比过低 → 图面空、线条颜色浅；
  暗部中位亮度过高 → 线条/文字颜色发灰不深。
- PALETTE-SIZE（主色数，WARN）：量化后的活跃彩色种数过多 → 配色脏、无主色。
- COLORBLIND（绿色盲可分性，WARN）：主色经 deuteranopia 模拟后两两距离过小 →
  红绿色盲读者无法区分（国赛打印/评审场景高发）。
- GRAYSCALE（灰度可读，WARN）：主色转灰后两两亮度差过小 → 黑白打印不可分。
- TEXT-SCALE（过小文字启发式，INFO）：暗色行带高度不足图高 0.8% → 可能存在
  过小文字，提示人工确认（启发式，不定罪）。

仅依赖 Pillow + numpy，network-free。severity 与 check_figure.py 一致：
INFO < WARN < FAIL；--strict 下任意 FAIL 退出码 2。

Usage
-----
    from texture_audit import texture_audit, print_report
    issues, info = texture_audit("figs/fig1.png")
    print_report("figs/fig1.png", issues, info)

CLI:
    python texture_audit.py figs/*.png
    python texture_audit.py figs/fig1.png --strict
"""
from __future__ import annotations

import argparse
import glob
import os
import sys

# Windows GBK 终端下 print 中文会 UnicodeEncodeError
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

SEVERITY = {"INFO": 0, "WARN": 1, "FAIL": 2}

# Machado (2009) deuteranopia 模拟矩阵（severity=1.0），直接作用于 sRGB
_DEUTERANOPIA = (
    (0.367322, 0.860646, -0.227968),
    (0.280085, 0.672501, 0.047413),
    (-0.011820, 0.042940, 0.968881),
)

_NEAR_WHITE_LUM = 245.0
_QUANT = 32          # RGB 量化步长
_DOMINANT_MIN = 0.003  # 主色门槛：占总像素 0.3% 以上
_MAX_SIDE = 800        # 分析前降采样上限


def _load_pixels(path: str):
    """读图 → (H, W, 3) uint8；过大则等比降采样以保速度。"""
    import numpy as np
    from PIL import Image

    img = Image.open(path).convert("RGB")
    w, h = img.size
    scale = max(w, h) / _MAX_SIDE
    if scale > 1:
        img = img.resize((max(1, round(w / scale)), max(1, round(h / scale))))
    return np.asarray(img, dtype=np.float64)


def _luminance(px):
    """相对亮度（Rec. 709），px 为 (..., 3) 数组。"""
    return 0.2126 * px[..., 0] + 0.7152 * px[..., 1] + 0.0722 * px[..., 2]


def _dominant_colors(px):
    """量化分桶取主色，桶内取**像素均值**（而非桶中心，避免量化偏移污染色觉模拟）。

    返回 [(hex, share, rgb_mean)]，按占比降序；彩色/非彩色都算。"""
    import numpy as np

    flat = px.reshape(-1, 3)
    q = (flat // _QUANT).astype(np.int64)
    keys = q[:, 0] * 1_000_000 + q[:, 1] * 1_000 + q[:, 2]
    uniq, inverse, counts = np.unique(keys, return_inverse=True, return_counts=True)
    sums = np.zeros((len(uniq), 3))
    np.add.at(sums, inverse, flat)
    means = sums / counts[:, None]
    total = counts.sum()
    order = np.argsort(-counts)
    out = []
    for idx in order:
        share = counts[idx] / total
        if share < _DOMINANT_MIN:
            break
        rgb = means[idx]
        out.append(("#%02X%02X%02X" % tuple(int(round(c)) for c in rgb),
                    float(share), rgb))
    return out


def _simulate_deuteranopia(rgb):
    import numpy as np

    m = np.array(_DEUTERANOPIA)
    return m @ np.asarray(rgb, dtype=np.float64)


def _check_ink(px):
    import numpy as np

    issues = []
    lum = _luminance(px)
    ink_mask = lum < _NEAR_WHITE_LUM
    density = float(ink_mask.mean())
    info = {"ink_density": round(density, 4)}
    if density < 0.005:
        issues.append(("FAIL",
                       f"墨色浓度仅 {density:.2%}——图面几乎空白或线条颜色过浅，"
                       "在国赛论文实际尺寸下会「看不见」。加深线条/文字颜色或增大图元素。"))
    elif density < 0.02:
        issues.append(("WARN",
                       f"墨色浓度 {density:.2%} 偏低——图面偏空或颜色偏淡，"
                       "请确认线条/文字在当前配色下足够深。"))
    if ink_mask.any():
        median_ink_lum = float(np.median(lum[ink_mask]))
        info["median_ink_luminance"] = round(median_ink_lum, 1)
        if median_ink_lum > 200:
            issues.append(("WARN",
                           f"暗部中位亮度 {median_ink_lum:.0f}/255——主体颜色整体偏浅，"
                           "建议换用深色系主色（如 Okabe-Ito #0072B2/#D55E00）。"))
    return issues, info


def _check_palette(dominant):
    issues = []
    chromatic = [d for d in dominant
                 if (max(d[2]) - min(d[2])) > 25]  # 有明显彩度
    n = len(chromatic)
    info = {"dominant_colors": [d[0] for d in dominant[:12]],
            "chromatic_count": n}
    if n > 10:
        issues.append(("WARN",
                       f"活跃彩色多达 {n} 种——配色脏、无主色。收敛到 5 个以内语义色"
                       "（全套论文共用同一色环）。"))
    return issues, info


def _check_colorblind(dominant):
    import numpy as np

    issues = []
    chromatic = [d for d in dominant if (max(d[2]) - min(d[2])) > 25][:8]
    bad_pairs = []
    for i in range(len(chromatic)):
        for j in range(i + 1, len(chromatic)):
            a = _simulate_deuteranopia(chromatic[i][2])
            b = _simulate_deuteranopia(chromatic[j][2])
            if float(np.linalg.norm(a - b)) < 25:
                bad_pairs.append((chromatic[i][0], chromatic[j][0]))
    if bad_pairs:
        pairs = "、".join(f"{a}≈{b}" for a, b in bad_pairs[:4])
        issues.append(("WARN",
                       f"绿色盲（deuteranopia）模拟下以下主色不可分：{pairs}。"
                       "换用色盲安全色环（Okabe-Ito）或加线型/marker 冗余编码。"))
    return issues


def _check_grayscale(dominant):
    issues = []
    colors = [d for d in dominant if d[1] >= 0.01][:8]  # 只看 ≥1% 的主色
    lums = [(d[0], float(_luminance(d[2]))) for d in colors]
    close = []
    for i in range(len(lums)):
        for j in range(i + 1, len(lums)):
            if abs(lums[i][1] - lums[j][1]) < 15:
                close.append((lums[i][0], lums[j][0]))
    if close:
        pairs = "、".join(f"{a}≈{b}" for a, b in close[:4])
        issues.append(("INFO",
                       f"灰度化后以下主色亮度差不足 15/255：{pairs}。"
                       "如需黑白打印可分，请拉开明度差或改用填充纹理区分（Okabe-Ito "
                       "蓝/橙本身明度接近，靠色相区分，属可接受情形）。"))
    return issues


def _check_text_scale(px):
    """启发式：暗色行带高度 < 图高 0.8% → 可能有过小文字。只报 INFO 不定罪。"""
    import numpy as np

    lum = _luminance(px)
    h = lum.shape[0]
    dark_row = (lum < 120).mean(axis=1) > 0.005
    bands = []
    run = 0
    for v in dark_row:
        run = run + 1 if v else 0
        if not v and run:
            bands.append(run)
            run = 0
    if run:
        bands.append(run)
    if bands and min(bands) < h * 0.008:
        return [("INFO",
                 f"检测到高度不足图高 0.8% 的暗色行带（最小 {min(bands)}px/{h}px），"
                 "可能存在过小文字——请在论文实际尺寸下人工确认字号 ≥ 小五。")]
    return []


def _merge_shades(dominant, tol: float = 48.0):
    """把量化误差/半透明混色造成的"同色异桶"合并为代表色（按占比加权）。

    例如 alpha=0.85 的蓝线条在白底上会同时产生 #0072B2 与 #3090B0 两个桶，
    它们是同一语义色的不同深浅，不应参与"两色不可分"判定。
    """
    import numpy as np

    merged: list[list] = []  # [hex, share, rgb]
    for hexs, share, rgb in dominant:
        hit = None
        for m in merged:
            if float(np.linalg.norm(m[2] - rgb)) < tol:
                hit = m
                break
        if hit is None:
            merged.append([hexs, share, rgb.copy()])
        else:
            total = hit[1] + share
            hit[2] = (hit[2] * hit[1] + rgb * share) / total
            hit[0] = "#%02X%02X%02X" % tuple(int(round(c)) for c in hit[2])
            hit[1] = total
    merged.sort(key=lambda m: -m[1])
    return [(m[0], m[1], m[2]) for m in merged]


def texture_audit(path: str) -> tuple[list[tuple[str, str]], dict]:
    """审计一张位图的质感指标。返回 (issues, info)。"""
    issues: list[tuple[str, str]] = []
    info: dict = {"path": path}
    if not os.path.exists(path):
        return [("FAIL", f"文件不存在: {path}")], info
    try:
        px = _load_pixels(path)
    except Exception as e:  # noqa: BLE001
        return [("FAIL", f"无法读取图像：{e}")], info

    info["analyzed_size"] = [int(px.shape[1]), int(px.shape[0])]

    sub, sub_info = _check_ink(px)
    issues.extend(sub)
    info.update(sub_info)

    dominant = _merge_shades(_dominant_colors(px))
    sub, sub_info = _check_palette(dominant)
    issues.extend(sub)
    info.update(sub_info)

    issues.extend(_check_colorblind(dominant))
    issues.extend(_check_grayscale(dominant))
    issues.extend(_check_text_scale(px))
    return issues, info


def print_report(path: str, issues: list, info: dict) -> str:
    print(f"\n--- {path} ---")
    if "analyzed_size" in info:
        print(f"  analyzed: {info['analyzed_size'][0]}x{info['analyzed_size'][1]}  "
              f"ink: {info.get('ink_density', '?')}  "
              f"colors: {info.get('chromatic_count', '?')} chromatic")
    if not issues:
        print("  [PASS] 质感指标无问题。")
        return "PASS"
    max_sev = max(SEVERITY[s] for s, _ in issues)
    verdict = {2: "FAIL", 1: "WARN", 0: "INFO"}[max_sev]
    for severity, msg in sorted(issues, key=lambda x: -SEVERITY[x[0]]):
        print(f"  [{severity}] {msg}")
    print(f"  >>> verdict: {verdict}")
    return verdict


def _cli() -> int:
    p = argparse.ArgumentParser(description="成图质感审计（墨色/主色/色盲/灰度/字号启发式）")
    p.add_argument("paths", nargs="+", help="PNG 等位图路径，可用 glob")
    p.add_argument("--strict", action="store_true", help="任意 FAIL 即 exit code 2")
    args = p.parse_args()

    expanded: list[str] = []
    for pat in args.paths:
        m = glob.glob(pat)
        expanded.extend(m if m else [pat])

    any_fail = False
    for path in expanded:
        issues, info = texture_audit(path)
        verdict = print_report(path, issues, info)
        if verdict == "FAIL":
            any_fail = True
    print()
    if args.strict and any_fail:
        print("[texture_audit] strict mode: at least one FAIL — exit 2")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
