from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class BrandOverrideTests(SimpleTestCase):
    def read(self, relative_path):
        return (Path(settings.BASE_DIR) / relative_path).read_text(encoding="utf-8")

    def test_brand_layer_loads_after_route_specific_styles(self):
        template = self.read("templates/base.html")
        self.assertLess(template.index("{% block head %}"), template.index("css/brand-overrides.css"))
        self.assertIn("--artisan-cream: #faf7f1", self.read("static/css/brand-overrides.css"))
        self.assertIn("--artisan-brand: #74432f", self.read("static/css/brand-overrides.css"))

    def test_dropdowns_keep_native_controls_and_warm_accessible_motion(self):
        css = self.read("static/css/brand-overrides.css")
        self.assertIn("select:not([multiple]):not([size])", css)
        self.assertIn("select[multiple]", css)
        self.assertIn("select:not([multiple]):not([size]):focus-visible", css)
        self.assertIn("@keyframes artisan-dropdown-in", css)
        self.assertIn(".nav-group:focus-within .dropdown", css)
        self.assertIn("prefers-reduced-motion: reduce", css)

    def test_support_and_manager_theme_and_wrapping_are_warm_and_horizontal(self):
        css = self.read("static/css/brand-overrides.css")
        self.assertIn(".support-workspace-hero", css)
        self.assertIn(".support-case-page", css)
        self.assertIn("writing-mode: horizontal-tb !important", css)
        self.assertIn(".manager-dashboard .manager-kpi-card--blue", css)
        self.assertIn("linear-gradient(122deg, #3e2b22", css)
        self.assertNotIn("#425bd6", css)
        self.assertIn(".site-footer__links .nav-logout", css)

    def test_services_category_filter_is_a_native_get_dropdown(self):
        template = self.read("templates/discovery/services.html")
        css = self.read("static/css/brand-overrides.css")
        self.assertIn('name="category_name"', template)
        self.assertIn('<select id="service-category-filter"', template)
        self.assertIn('method="get"', template)
        self.assertIn(".services-filter-form__field select", css)
