from typing import ClassVar
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase
from django.urls import reverse


class ArtisanActivationAPIClient:
    calls: ClassVar[list[tuple[object, ...]]] = []

    @classmethod
    def reset(cls):
        cls.calls.clear()

    def __init__(self, request):
        self.request = request

    def get(self, path, params=None):
        self.calls.append(("GET", path, params))
        if path == "/notifications/unread-count/":
            return 200, {"unread_count": 0}, {}
        raise AssertionError(f"Unexpected activation-page API GET: {path}")

    def post(self, path, data=None, **kwargs):
        self.calls.append(("POST", path, data, kwargs))
        return 200, {"message": "Artisan activation updated."}, {}


class ArtisanActivationPageTests(TestCase):
    def setUp(self):
        ArtisanActivationAPIClient.reset()
        self.enterContext(patch("frontend.views.APIClient", ArtisanActivationAPIClient))
        self.enterContext(patch("frontend.context_processors.APIClient", ArtisanActivationAPIClient))
        self.artisan_id = uuid4()
        session = self.client.session
        session["api_access"] = "temporary-test-access-token"
        session["api_role"] = "staff"
        session["api_user"] = {
            "first_name": "Ada",
            "last_name": "Manager",
            "role": "staff",
            "is_superuser": True,
        }
        session.save()

    def test_activation_page_keeps_manager_navigation_restricted(self):
        response = self.client.get(reverse("artisan-activate", kwargs={"pk": self.artisan_id}))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        nav_start = content.index('<nav id="site-navigation"')
        nav = content[nav_start:content.index("</nav>", nav_start)]
        items = ["Manager Overview", "Support Operations", "Case Queue", "Refunds", "Support Team", "Log Out"]
        positions = [nav.index(item) for item in items]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("Promotions", nav)
        self.assertNotIn("Find artisans", nav)
        self.assertNotIn("My Services", nav)
        self.assertContains(response, "Return to Manager Overview")
        self.assertContains(response, 'name="activate" value="1"')
        self.assertContains(response, 'name="activate" value="0"')

    def test_activation_submission_calls_the_api_and_returns_to_manager_overview(self):
        response = self.client.post(
            reverse("artisan-activate", kwargs={"pk": self.artisan_id}),
            {"activate": "1"},
        )

        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.assertIn(
            (
                "POST",
                f"/services/artisan/profile/{self.artisan_id}/activate/",
                {"activate": True},
                {},
            ),
            ArtisanActivationAPIClient.calls,
        )
