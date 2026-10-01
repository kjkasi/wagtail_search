from pathlib import Path

from django.test import SimpleTestCase


class AssetBuildTests(SimpleTestCase):
    def test_bootstrap_build_produces_css_and_js(self):
        static_site = Path(__file__).resolve().parents[2] / "static" / "site"
        css = static_site / "main.css"
        javascript = static_site / "main.js"

        self.assertTrue(css.is_file())
        self.assertTrue(javascript.is_file())
        self.assertTrue(css.stat().st_size > 0)
        self.assertTrue(javascript.stat().st_size > 0)
        self.assertIn(".navbar", css.read_text(encoding="utf-8"))
        self.assertIn("collapse", javascript.read_text(encoding="utf-8"))
