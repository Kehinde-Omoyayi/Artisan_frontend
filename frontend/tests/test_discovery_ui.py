from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from frontend.forms import ArtisanProfileForm


class DiscoveryUITests(SimpleTestCase):
    def test_optional_professional_links_validate_safe_http_urls_and_platform_matches(self):
        blank = ArtisanProfileForm(data={"first_name": "Ayo", "last_name": "Maker"})
        self.assertTrue(blank.is_valid(), blank.errors)

        valid = ArtisanProfileForm(data={
            "first_name": "Ayo",
            "last_name": "Maker",
            "social_media_1_platform": "INSTAGRAM",
            "social_media_1_url": "https://instagram.com/ayomaker",
            "portfolio_url": "https://portfolio.example.com/work",
        })
        self.assertTrue(valid.is_valid(), valid.errors)

        for fields in (
            {"social_media_1_platform": "INSTAGRAM", "social_media_1_url": "https://example.com/profile"},
            {"social_media_1_platform": "X", "social_media_1_url": "javascript:alert(1)"},
            {"portfolio_url": "data:text/html,unsafe"},
            {"portfolio_url": "https://example.com:0/path"},
        ):
            with self.subTest(fields=fields):
                form = ArtisanProfileForm(data={"first_name": "Ayo", "last_name": "Maker", **fields})
                self.assertFalse(form.is_valid())

    def test_discovery_uses_two_roomy_columns_then_one_mobile_column_and_flow_panel(self):
        stylesheet = (Path(settings.BASE_DIR) / "static/css/artisan-pages.css").read_text(encoding="utf-8")
        script = (Path(settings.BASE_DIR) / "static/js/pages/discovery-artisans.js").read_text(encoding="utf-8")
        template = (Path(settings.BASE_DIR) / "templates/discovery/artisans.html").read_text(encoding="utf-8")

        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr))", stylesheet)
        self.assertIn("@media (max-width: 620px)", stylesheet)
        self.assertIn("grid-template-columns: minmax(0, 1fr)", stylesheet)
        self.assertIn(".artisan-discovery-category-drawer > .artisan-discovery-category-panel", stylesheet)
        self.assertIn("drawer.contains(event.target)", script)
        self.assertIn("event.key === 'Escape'", script)
        self.assertIn("aria-expanded=\"true\"", template)
        self.assertIn("data-discovery-category-panel>", template)
        self.assertIn("name=\"institution_id\"", template)
        self.assertIn("name=\"available_anywhere\"", template)
        self.assertIn("View full artisan details", template)
        self.assertNotIn("artisan.social_media_1_url", template)
        self.assertNotIn("artisan.portfolio_url", template)
