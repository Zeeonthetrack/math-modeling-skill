import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools" / "figure" / "scripts"))

try:
    import numpy as np
    from PIL import Image

    import texture_audit

    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False


def _save(arr, path: Path) -> str:
    Image.fromarray(arr).save(path)
    return str(path)


@unittest.skipUnless(HAS_DEPS, "需要 numpy 与 Pillow")
class TextureAuditTests(unittest.TestCase):
    def test_faint_figure_fails_ink_density(self):
        with tempfile.TemporaryDirectory() as tmp:
            arr = np.full((400, 600, 3), 255, np.uint8)
            arr[200, 100:500] = (225, 228, 230)  # 一条浅灰细线
            issues, _ = texture_audit.texture_audit(_save(arr, Path(tmp) / "faint.png"))
            levels = {s for s, _ in issues}
            self.assertIn("FAIL", levels)
            self.assertTrue(any("墨色浓度" in m for s, m in issues if s == "FAIL"))

    def test_deep_palette_figure_has_no_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            arr = np.full((400, 600, 3), 255, np.uint8)
            arr[100:300, 150:250] = (0, 114, 178)    # Okabe-Ito 蓝
            arr[100:300, 350:450] = (213, 94, 0)     # Okabe-Ito 橙
            issues, _ = texture_audit.texture_audit(_save(arr, Path(tmp) / "ok.png"))
            self.assertNotIn("FAIL", {s for s, _ in issues})
            # Okabe-Ito 蓝橙明度接近是色相区分的已知可接受情形，不允许报 WARN 级灰度问题
            self.assertFalse(
                any(s == "WARN" and "灰度" in m for s, m in issues),
                issues,
            )

    def test_equal_luminance_red_green_warns_colorblind(self):
        with tempfile.TemporaryDirectory() as tmp:
            arr = np.full((400, 600, 3), 255, np.uint8)
            arr[100:300, 150:250] = (190, 80, 60)    # 等亮度红
            arr[100:300, 350:450] = (70, 140, 70)    # 等亮度绿
            issues, _ = texture_audit.texture_audit(_save(arr, Path(tmp) / "rg.png"))
            self.assertTrue(
                any(s == "WARN" and "deuteranopia" in m for s, m in issues),
                issues,
            )

    def test_shade_buckets_merge_no_false_colorblind(self):
        # 半透明蓝在白底产生的同色异桶不得触发色盲不可分
        with tempfile.TemporaryDirectory() as tmp:
            arr = np.full((400, 600, 3), 255, np.uint8)
            arr[100:300, 150:250] = (0, 114, 178)
            arr[100:300, 350:450] = (48, 144, 176)   # 同色浅阶
            issues, _ = texture_audit.texture_audit(_save(arr, Path(tmp) / "shade.png"))
            self.assertFalse(
                any("deuteranopia" in m for s, m in issues),
                issues,
            )

    def test_missing_file_fails(self):
        issues, _ = texture_audit.texture_audit("__not_exists__.png")
        self.assertIn("FAIL", {s for s, _ in issues})


if __name__ == "__main__":
    unittest.main()
