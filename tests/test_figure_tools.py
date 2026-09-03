import importlib.util
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
FIGURE_SCRIPTS = SKILL_ROOT / "tools" / "figure" / "scripts"
PROGRAMMER_SCRIPTS = SKILL_ROOT / "references" / "roles" / "编程手" / "scripts"
sys.path.insert(0, str(FIGURE_SCRIPTS))
sys.path.insert(0, str(PROGRAMMER_SCRIPTS))

import figure_audit
import setup_style
import export_figure
import visual_qa
import style_constants
import layout_tools


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    payload = kind + data
    return struct.pack(">I", len(data)) + payload + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)


def _write_png(path: Path, dpi: int, with_dpi: bool = True) -> None:
    pixels_per_meter = round(dpi / 0.0254)
    content = [
        figure_audit.PNG_SIGNATURE,
        _png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)),
    ]
    if with_dpi:
        content.append(
            _png_chunk(b"pHYs", struct.pack(">IIB", pixels_per_meter, pixels_per_meter, 1))
        )
    content.extend([
        _png_chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00\x00")),
        _png_chunk(b"IEND", b""),
    ])
    path.write_bytes(b"".join(content))


def _write_svg(path: Path, with_text: bool = True) -> None:
    body = '<text x="1" y="8">label</text>' if with_text else '<path d="M0 0 L1 1"/>'
    path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg">{body}</svg>', encoding="utf-8")


class StyleConstantsTests(unittest.TestCase):
    def test_palette_is_unique_and_colorblind_oriented(self):
        self.assertEqual(len(style_constants.COLOR_SEQUENCE), len(set(style_constants.COLOR_SEQUENCE)))
        self.assertEqual(style_constants.PALETTE["primary"], "#0072B2")
        width, height = style_constants.figure_size("report")
        self.assertEqual(width, 6.3)
        self.assertAlmostEqual(height, 3.906)

    def test_refuses_output_inside_skill_root(self):
        with self.assertRaisesRegex(ValueError, "PROJECT_ROOT"):
            style_constants.resolve_output_stem(style_constants.SKILL_ROOT / "figures" / "result_demo")

    def test_copied_helper_allows_output_inside_project_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            copied = project / "utils" / "a" / "b" / "style_constants.py"
            copied.parent.mkdir(parents=True)
            copied.write_bytes((FIGURE_SCRIPTS / "style_constants.py").read_bytes())
            spec = importlib.util.spec_from_file_location("copied_style_constants", copied)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            try:
                resolved = module.resolve_output_stem(project / "figures" / "result_q1")
            except ValueError as error:
                self.fail(f"复制到 PROJECT_ROOT 后不应误判为 SKILL_ROOT：{error}")

            self.assertEqual(resolved, (project / "figures" / "result_q1").resolve())

    def test_copied_helper_still_refuses_the_real_skill_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / "project" / "utils" / "a" / "b" / "style_constants.py"
            copied.parent.mkdir(parents=True)
            copied.write_bytes((FIGURE_SCRIPTS / "style_constants.py").read_bytes())
            spec = importlib.util.spec_from_file_location("guarded_copied_style_constants", copied)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            with self.assertRaisesRegex(ValueError, "PROJECT_ROOT"):
                module.resolve_output_stem(SKILL_ROOT / "forbidden")

    @unittest.skipUnless(importlib.util.find_spec("matplotlib"), "需要 matplotlib")
    def test_real_export_passes_file_audit(self):
        import matplotlib

        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt

        with tempfile.TemporaryDirectory() as tmp:
            setup_style.setup_style(journal="nature", lang="en")
            fig, axis = plt.subplots()
            axis.plot([0, 1], [0, 1])
            axis.set(xlabel="Time (s)", ylabel="Value")
            outputs = export_figure.export_figure(
                fig, str(Path(tmp) / "result_demo"),
                formats=["svg", "png"], dpi=300, size_inches=(3.5, 2.625),
                grayscale_preview=True, preflight=False,
            )
            plt.close(fig)

            report = figure_audit.audit_figure_directory(tmp, require_categories=False)

        self.assertTrue(report["ok"], report["issues"])
        self.assertTrue(any("_grayscale" in Path(p).name for p in outputs))
        metadata = report["files"]["result_demo.png"]
        # tight=False 默认保持精确 figsize：3.5×2.625 in @ 300dpi = 1050×787 px
        self.assertEqual(metadata["width_px"], 1050)
        self.assertEqual(metadata["height_px"], 787)
        # DPI 元数据经 ppm 取整存在微小浮点误差，尺寸断言放宽到 2 位小数
        self.assertAlmostEqual(metadata["width_in"], 3.5, places=2)
        self.assertAlmostEqual(metadata["height_in"], 2.625, places=2)

    @unittest.skipUnless(importlib.util.find_spec("matplotlib"), "需要 matplotlib")
    def test_layout_audit_detects_overlapping_ticks(self):
        import matplotlib

        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt

        fig, axis = plt.subplots(figsize=(2, 1.5), constrained_layout=False)
        axis.set_xticks(range(8), [f"very-long-category-{index}" for index in range(8)])
        issues = visual_qa.audit_layout(fig)
        plt.close(fig)

        self.assertTrue(any("刻度标签重叠" in msg for _sev, msg in issues), issues)

    @unittest.skipUnless(importlib.util.find_spec("matplotlib"), "需要 matplotlib")
    def test_publication_subplots_preserves_declared_panel_hierarchy(self):
        import matplotlib

        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt

        fig, axes = style_constants.publication_subplots(
            1, 2, width="double", aspect=0.5, width_ratios=[1.8, 1]
        )
        ratios = axes[0].get_subplotspec().get_gridspec().get_width_ratios()
        plt.close(fig)

        self.assertEqual(ratios, [1.8, 1])
        self.assertEqual(tuple(fig.get_size_inches()), (7.2, 3.6))

    @unittest.skipUnless(importlib.util.find_spec("matplotlib"), "需要 matplotlib")
    def test_design_audit_rejects_dense_markers_and_nonzero_bar_baseline(self):
        import matplotlib

        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(1, 2)
        axes[0].plot(range(30), range(30), marker="o")
        axes[1].bar(["A", "B"], [10, 12])
        axes[1].set_ylim(8, 14)
        issues = visual_qa.audit_design(fig)
        plt.close(fig)

        messages = "\n".join(msg for _sev, msg in issues)
        self.assertIn("逐点绘制标记", messages)
        self.assertIn("柱状图未从零开始", messages)

    @unittest.skipUnless(importlib.util.find_spec("matplotlib"), "需要 matplotlib")
    def test_design_audit_reads_left_title_negative_bars_and_figure_legend(self):
        import matplotlib

        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt

        setup_style.setup_style(journal="nature", lang="en")
        fig, axes = plt.subplots(1, 2)
        axes[0].set_title("This panel title is deliberately much too long", loc="left")
        axes[0].bar(["A", "B"], [-10, -12])
        axes[0].set_ylim(-14, -8)
        for index in range(6):
            axes[1].plot([0, 1], [index, index + 1], label=f"series-{index}")
        handles, labels = axes[1].get_legend_handles_labels()
        fig.legend(handles, labels)
        issues = visual_qa.audit_design(fig)
        plt.close(fig)

        messages = "\n".join(msg for _sev, msg in issues)
        self.assertIn("标题过长", messages)
        self.assertIn("柱状图未从零开始", messages)
        self.assertIn("整图共享图例超过 5 项", messages)

    @unittest.skipUnless(importlib.util.find_spec("matplotlib"), "需要 matplotlib")
    def test_design_audit_rejects_redundant_colorbar_for_annotated_2x2_matrix(self):
        import matplotlib

        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt
        import numpy as np

        fig, axis = plt.subplots()
        image = axis.imshow(np.array([[12, 3], [2, 9]]))
        for row in range(2):
            for column in range(2):
                axis.text(column, row, "1")
        fig.colorbar(image, ax=axis)
        issues = visual_qa.audit_design(fig)
        plt.close(fig)

        self.assertTrue(any("冗余 colorbar" in msg for _sev, msg in issues), issues)

    @unittest.skipUnless(importlib.util.find_spec("matplotlib"), "需要 matplotlib")
    def test_design_audit_associates_colorbar_with_its_own_image(self):
        import matplotlib

        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt
        import numpy as np

        fig, axes = plt.subplots(1, 2)
        axes[0].imshow(np.array([[12, 3], [2, 9]]))
        for row in range(2):
            for column in range(2):
                axes[0].text(column, row, "1")
        continuous = axes[1].imshow(np.arange(100).reshape(10, 10))
        fig.colorbar(continuous, ax=axes[1])
        issues = visual_qa.audit_design(fig)
        plt.close(fig)

        self.assertFalse(any("冗余 colorbar" in msg for _sev, msg in issues), issues)

    def test_matlab_export_uses_design_audit(self):
        matlab_scripts = SKILL_ROOT / "references" / "roles" / "编程手" / "scripts"
        audit = (matlab_scripts / "audit_publication_figure.m").read_text(encoding="utf-8")
        exporter = (matlab_scripts / "export_publication_figure.m").read_text(encoding="utf-8")

        self.assertIn("MarkerIndices", audit)
        self.assertIn("柱状图未从零开始", audit)
        self.assertIn("limits(2) < -tolerance", audit)
        self.assertIn('isprop(ax, "Colorbar")', audit)
        self.assertIn("TightInset", audit)
        self.assertIn("audit_publication_figure(fig)", exporter)


class FigureAuditTests(unittest.TestCase):
    def test_accepts_three_candidates_per_category_with_svg_png_pairs(self):
        with tempfile.TemporaryDirectory() as tmp:
            figures = Path(tmp)
            for prefix in ("raw", "process", "result"):
                for question in ("q1", "q2", "q3"):
                    stem = f"{prefix}_{question}_candidate"
                    _write_svg(figures / f"{stem}.svg")
                    _write_png(figures / f"{stem}.png", 300)

            report = figure_audit.audit_figure_directory(
                figures,
                questions=("q1", "q2", "q3"),
            )

        self.assertTrue(report["ok"], report["issues"])
        self.assertEqual(report["questions"], ["q1", "q2", "q3"])
        self.assertEqual(report["issues"], [])

    def test_rejects_global_shortage_and_uncovered_questions(self):
        with tempfile.TemporaryDirectory() as tmp:
            figures = Path(tmp)
            for stem in ("raw_q1_data", "process_q1_loss", "result_q1_solution"):
                _write_svg(figures / f"{stem}.svg")
                _write_png(figures / f"{stem}.png", 300)

            report = figure_audit.audit_figure_directory(
                figures,
                questions=("q1", "q2"),
            )

        self.assertFalse(report["ok"])
        messages = "\n".join(item["message"] for item in report["issues"])
        self.assertIn("raw_ 类候选图仅 1 张，低于每类最低 3 张", messages)
        self.assertIn("process_ 类候选图仅 1 张，低于每类最低 3 张", messages)
        self.assertIn("result_ 类候选图仅 1 张，低于每类最低 3 张", messages)
        self.assertIn("子问题 q2 缺少 raw_ 类候选图", messages)
        self.assertIn("子问题 q2 缺少 process_ 类候选图", messages)
        self.assertIn("子问题 q2 缺少 result_ 类候选图", messages)

    def test_requires_explicit_complete_question_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            figures = Path(tmp)
            for prefix in ("raw", "process", "result"):
                for index in range(3):
                    stem = f"{prefix}_q1_candidate_{index + 1}"
                    _write_svg(figures / f"{stem}.svg")
                    _write_png(figures / f"{stem}.png", 300)

            report = figure_audit.audit_figure_directory(figures)

        self.assertFalse(report["ok"])
        self.assertTrue(any("未提供全部子问题标识" in item["message"] for item in report["issues"]))

    def test_rejects_low_dpi_and_missing_editable_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            figures = Path(tmp)
            _write_svg(figures / "result_solution.svg", with_text=False)
            _write_png(figures / "result_solution.png", 96)

            report = figure_audit.audit_figure_directory(figures, require_categories=False)

        messages = "\n".join(item["message"] for item in report["issues"])
        self.assertFalse(report["ok"])
        self.assertIn("可编辑文本", messages)
        self.assertIn("低于 300 DPI", messages)

    def test_rejects_missing_format_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            figures = Path(tmp)
            _write_svg(figures / "raw_data.svg")

            report = figure_audit.audit_figure_directory(figures, require_categories=False)

        self.assertFalse(report["ok"])
        self.assertIn("缺少配对格式", report["issues"][0]["message"])

    def test_diagram_png_pdf_pair_passes_and_does_not_count_as_data_categories(self):
        with tempfile.TemporaryDirectory() as tmp:
            figures = Path(tmp)
            for prefix in ("raw", "process", "result"):
                for question in ("q1", "q2", "q3"):
                    stem = f"{prefix}_{question}_candidate"
                    _write_svg(figures / f"{stem}.svg")
                    _write_png(figures / f"{stem}.png", 300)
            # drawio 默认导出组合：PNG（DPI 元数据偏低）+ 矢量 PDF
            _write_png(figures / "diagram_q1_flow.png", 96)
            (figures / "diagram_q1_flow.pdf").write_bytes(b"%PDF-1.4\n%dummy\n")

            report = figure_audit.audit_figure_directory(
                figures,
                questions=("q1", "q2", "q3"),
            )

        self.assertTrue(report["ok"], report["issues"])
        self.assertEqual(report["diagram_count"], 1)
        self.assertTrue(
            any(
                item["severity"] == "WARN" and "DPI" in item["message"]
                for item in report["issues"]
            ),
            report["issues"],
        )

    def test_diagram_png_svg_pair_at_full_dpi_has_no_issue(self):
        with tempfile.TemporaryDirectory() as tmp:
            figures = Path(tmp)
            _write_svg(figures / "diagram_all_roadmap.svg")
            _write_png(figures / "diagram_all_roadmap.png", 300)

            report = figure_audit.audit_figure_directory(figures, require_categories=False)

        self.assertTrue(report["ok"], report["issues"])
        self.assertEqual(report["issues"], [])
        self.assertEqual(report["diagram_count"], 1)

    def test_diagram_without_dpi_metadata_warns_but_does_not_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            figures = Path(tmp)
            _write_png(figures / "diagram_q1_flow.png", 300, with_dpi=False)
            (figures / "diagram_q1_flow.pdf").write_bytes(b"%PDF-1.4\n%dummy\n")

            report = figure_audit.audit_figure_directory(figures, require_categories=False)

        self.assertTrue(report["ok"], report["issues"])
        self.assertTrue(
            any("缺少 DPI 元数据" in item["message"] for item in report["issues"]),
            report["issues"],
        )

    def test_rejects_diagram_missing_vector_partner(self):
        with tempfile.TemporaryDirectory() as tmp:
            figures = Path(tmp)
            _write_png(figures / "diagram_q1_flow.png", 300)

            report = figure_audit.audit_figure_directory(figures, require_categories=False)

        self.assertFalse(report["ok"])
        self.assertTrue(
            any("矢量格式" in item["message"] for item in report["issues"]),
            report["issues"],
        )

    def test_rejects_diagram_missing_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            figures = Path(tmp)
            _write_svg(figures / "diagram_q1_flow.svg")

            report = figure_audit.audit_figure_directory(figures, require_categories=False)

        self.assertFalse(report["ok"])
        self.assertTrue(
            any("PNG" in item["message"] for item in report["issues"]),
            report["issues"],
        )

    def test_diagram_svg_with_foreign_object_text_counts_as_editable(self):
        with tempfile.TemporaryDirectory() as tmp:
            figures = Path(tmp)
            body = '<foreignObject width="10" height="10"><div>流程</div></foreignObject>'
            (figures / "diagram_q1_flow.svg").write_text(
                f'<svg xmlns="http://www.w3.org/2000/svg">{body}</svg>', encoding="utf-8"
            )
            _write_png(figures / "diagram_q1_flow.png", 300)

            report = figure_audit.audit_figure_directory(figures, require_categories=False)

        self.assertTrue(report["ok"], report["issues"])


if __name__ == "__main__":
    unittest.main()
