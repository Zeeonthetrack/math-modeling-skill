import py_compile
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = REPO_ROOT / "tools" / "figure" / "scripts" / "templates"

EXPECTED_SCRIPTS = (
    "make_correlation_pairgrid.py",
    "make_cv_roc_ci.py",
    "make_grouped_circular_heatmap.py",
    "make_grouped_corr_split_violin.py",
    "make_lollipop_stem.py",
    "make_multiclass_shap_combo.py",
    "make_nature_chord_diagram.py",
    "make_paired_raincloud.py",
    "make_prediction_marginal_grid.py",
    "make_rf_tpe_surface.py",
    "make_taylor_diagram.py",
    "make_urban_park_cooling_combo.py",
)


class FigureTemplateTests(unittest.TestCase):
    def test_all_eleven_templates_present_and_compile(self):
        for name in EXPECTED_SCRIPTS:
            path = TEMPLATES / name
            self.assertTrue(path.is_file(), f"缺少模板脚本：{name}")
            py_compile.compile(str(path), doraise=True)

    def test_catalog_lists_every_template(self):
        catalog = (
            REPO_ROOT / "tools" / "figure" / "references" / "api-templates" / "template_catalog.md"
        ).read_text(encoding="utf-8")
        for name in EXPECTED_SCRIPTS:
            self.assertIn(name, catalog)

    @unittest.skipUnless(
        subprocess.run(
            [sys.executable, "-c", "import matplotlib"],
            capture_output=True,
        ).returncode
        == 0,
        "需要 matplotlib",
    )
    def test_cv_roc_ci_real_data_end_to_end(self):
        import numpy as np
        import pandas as pd

        with tempfile.TemporaryDirectory() as tmp:
            rows = []
            rng = np.random.default_rng(7)
            for model, exponent in [("LR", 3.5), ("RF", 5.0)]:
                for fold in range(1, 6):
                    for fpr in np.linspace(0.0, 1.0, 21):
                        tpr = 1 - (1 - fpr) ** (exponent / (1 + exponent)) + rng.normal(0, 0.01)
                        rows.append(
                            {
                                "fold": fold,
                                "model": model,
                                "fpr": fpr,
                                "tpr": float(np.clip(tpr, 0.0, 1.0)),
                            }
                        )
            csv_path = Path(tmp) / "roc.csv"
            pd.DataFrame(rows).to_csv(csv_path, index=False)
            stem = Path(tmp) / "roc_real"

            result = subprocess.run(
                [sys.executable, str(TEMPLATES / "make_cv_roc_ci.py"),
                 "--data", str(csv_path), "--out", str(stem)],
                capture_output=True,
                text=True,
                cwd=str(TEMPLATES),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            for suffix in (".png", ".pdf", ".svg", "_grayscale.png"):
                output = Path(str(stem) + suffix)
                self.assertTrue(output.is_file() and output.stat().st_size > 0, str(output))

    @unittest.skipUnless(
        subprocess.run(
            [sys.executable, "-c", "import matplotlib"],
            capture_output=True,
        ).returncode
        == 0,
        "需要 matplotlib",
    )
    def test_paired_raincloud_demo_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            stem = Path(tmp) / "raincloud_demo"
            result = subprocess.run(
                [sys.executable, str(TEMPLATES / "make_paired_raincloud.py"),
                 "--demo", "--out", str(stem)],
                capture_output=True,
                text=True,
                cwd=str(TEMPLATES),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            for suffix in (".png", ".pdf", ".svg", "_grayscale.png"):
                output = Path(str(stem) + suffix)
                self.assertTrue(output.is_file() and output.stat().st_size > 0, str(output))


if __name__ == "__main__":
    unittest.main()
