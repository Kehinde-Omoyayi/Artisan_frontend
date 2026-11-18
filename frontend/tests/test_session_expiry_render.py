"""Regression tests for the mid-view session-expiry path that 500'd the home page.

What the user hit: an API token died mid-request (logs show 401s and a failed
token refresh), handle_api_error() wiped the session, but the role had already
been resolved, so the artisan shell rendered with an empty profile and missing
user_info. The hero template then evaluated ``default:user_info.first_name`` --
an argument that itself fails to resolve -- and the page went down with
VariableDoesNotExist.

These pin down both layers of the fix:

* templates never chain a ``default:`` fallback through a variable that might
  not exist (they use ``firstof`` / if-branches instead);
* page() bounces a workspace shell whose session died mid-view back to sign-in.
"""

from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.cache import SessionStore
from django.test import Client, RequestFactory, SimpleTestCase, TestCase
from django.template.loader import render_to_string
from django.urls import reverse

from frontend import views
from frontend.api import APIError
from frontend.views import LANDING_VISUAL_THEMES


def hero_context(**overrides):
    context = {
        "role": "artisan",
        "profile": None,
        "user_info": {},
        "nav_role": "artisan",
        "initial_hero": LANDING_VISUAL_THEMES[0],
        "hero_slides": LANDING_VISUAL_THEMES[:1],
    }
    context.update(overrides)
    return context


class HeroPartialRenderTests(SimpleTestCase):
    def test_a_dead_session_renders_the_fallback_greeting_not_a_500(self):
        html = render_to_string(
            "partials/authenticated_home_hero.html", hero_context()
        )
        self.assertIn("Welcome back, Artisan.", html)

    def test_a_signed_in_artisan_still_gets_their_business_name(self):
        html = render_to_string(
            "partials/authenticated_home_hero.html",
            hero_context(profile={"business_name": "Klag Works"}),
        )
        self.assertIn("Welcome back, Klag Works.", html)

    def test_the_user_record_is_used_when_the_profile_has_no_business_name(self):
        html = render_to_string(
            "partials/authenticated_home_hero.html",
            hero_context(user_info={"first_name": "Ada"}),
        )
        self.assertIn("Welcome back, Ada.", html)

    def test_a_customer_hero_survives_a_dead_session(self):
        html = render_to_string(
            "partials/authenticated_home_hero.html",
            hero_context(role="customer", nav_role="customer"),
        )
        self.assertIn("Your customer profile.", html)


class PageBounceTests(SimpleTestCase):
    """A workspace page must never paint without a live session."""

    def setUp(self):
        self.factory = RequestFactory()

    def _request(self, path):
        request = self.factory.get(path)
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        request.user = AnonymousUser()
        return request

    def test_an_artisan_shell_with_a_dead_session_bounces_to_sign_in(self):
        response = views.page(self._request("/"), "landing.html", role="artisan")
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)
        self.assertIn("next=%2F", response.url)

    def test_a_staff_shell_with_a_dead_session_bounces_to_sign_in(self):
        response = views.page(
            self._request("/console/overview/"), "landing.html", role="staff"
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_a_customer_shell_with_a_dead_session_bounces_to_sign_in(self):
        response = views.page(self._request("/"), "landing.html", role="customer")
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)


class FakeAPIClient:
    """Every call the view makes during a signed-out request fails with 401."""

    def __init__(self, request):
        self.session = request.session

    def get(self, *args, **kwargs):
        raise APIError(401, {})

    def post(self, *args, **kwargs):
        raise APIError(401, {})

    def patch(self, *args, **kwargs):
        raise APIError(401, {})

    def clear_session(self):
        for key in (
            "api_access", "api_refresh", "api_user", "api_role",
        ):
            self.session.pop(key, None)
        self.session.modified = True


class MidViewExpiryTests(TestCase):
    """The exact shape of what the user hit, end to end at the view layer."""

    def test_home_bounces_to_sign_in_when_the_token_dies_mid_request(self):
        client = Client()
        session = client.session
        session["api_access"] = "dead-access-token"
        session["api_refresh"] = "dead-refresh-token"
        session["api_role"] = "artisan"
        session["api_user"] = {"first_name": "Kehinde"}
        session.save()

        with patch("frontend.views.APIClient", FakeAPIClient):
            response = client.get("/")

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)
