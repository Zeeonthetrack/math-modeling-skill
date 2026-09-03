import py_compile
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
KIT = REPO_ROOT / "tools" / "schematic" / "scripts" / "geometry_kit.py"
GUIDE = REPO_ROOT / "tools" / "schematic" / "references" / "geometry-diagrams.md"


class GeometryKitTests(unittest.TestCase):
    def test_kit_compiles(self):
        py_compile.compile(str(KIT), doraise=True)

    def test_guide_exists_and_mentions_qa_loop(self):
        text = GUIDE.read_text(encoding="utf-8")
        self.assertIn("geometry_kit", text)
        self.assertIn("QA 闭环", text)
        self.assertIn("texture_audit", text)

    @unittest.skipUnless(
        subprocess.run(
            [sys.executable, "-c", "import matplotlib, numpy"],
            capture_output=True,
        ).returncode
        == 0,
        "需要 matplotlib 与 numpy",
    )
    def test_demo_produces_three_formats(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "diagram_demo"
            proc = subprocess.run(
                [sys.executable, str(KIT), "--demo", "--out", str(out)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
            for ext in ("png", "pdf", "svg"):
                self.assertTrue(
                    Path(f"{out}.{ext}").is_file(),
                    f"缺少 demo 产物 {out}.{ext}",
                )


if __name__ == "__main__":
    unittest.main()
