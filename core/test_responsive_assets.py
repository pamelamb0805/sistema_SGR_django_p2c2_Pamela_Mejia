from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class ResponsiveAssetTests(SimpleTestCase):
    def test_base_declara_viewport_y_carga_hoja_responsive(self):
        base = Path(settings.BASE_DIR) / "templates" / "base.html"
        contenido = base.read_text(encoding="utf-8")
        self.assertIn('name="viewport"', contenido)
        self.assertIn("sgr-responsive-overrides.css", contenido)

    def test_hoja_responsive_incluye_breakpoints_y_tablas_desplazables(self):
        css = Path(settings.BASE_DIR) / "static" / "css" / "sgr-responsive-overrides.css"
        contenido = css.read_text(encoding="utf-8")
        self.assertIn("max-width: 991.98px", contenido)
        self.assertIn("max-width: 575.98px", contenido)
        self.assertIn("overflow-x: auto", contenido)
        self.assertIn("prefers-reduced-motion", contenido)
