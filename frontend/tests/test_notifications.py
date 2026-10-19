import time
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from frontend.api import APIError


class FakeNotificationsAPI:
    calls = []
    failure = None

    def __init__(self, request):
        self.request = request

    @classmethod
    def reset(cls):
        cls.calls.clear()
        cls.failure = None

    def get(self, path, params=None):
        self.calls.append(("GET", path, params))
        if path == "/notifications/":
            return 200, {
                "count": 1,
                "results": [{
                    "id": 41,
                    "title": "Booking update",
                    "message": "Your service conversation has a new reply.",
                    "created_at": "2026-10-14T09:15:00Z",
                    "read_at": None,
                    "data": {"action_url": "/discover/conversations/", "action_label": "Open conversation"},
                }],
            }, {}
        return 200, {"count": 0, "results": []}, {}

    def post(self, path, data=None):
        self.calls.append(("POST", path, data))
        return 200, {"status": "read"}, {}

    def delete(self, path):
        self.calls.append(("DELETE", path, None))
        if self.failure:
            raise self.failure
        if path.endswith("delete-all/"):
            return 200, {"status": "deleted", "deleted": 1}, {}
        return 204, {}, {}


class NotificationPageTests(TestCase):
    def setUp(self):
        FakeNotificationsAPI.reset()
        session = self.client.session
        session["api_access"] = "fake-access"
        session["api_user"] = {"first_name": "Ada", "role": "customer"}
        session["notif_unread_checked_at"] = time.time()
        session["notif_unread"] = 1
        session.save()

    def test_notification_cards_show_distinct_content_and_safe_previous_link(self):
        with patch("frontend.views.APIClient", FakeNotificationsAPI), patch("frontend.context_processors.APIClient", FakeNotificationsAPI):
            response = self.client.get(
                reverse("notifications-page"),
                HTTP_REFERER=f"http://testserver{reverse('customer-profile')}",
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Booking update")
        self.assertContains(response, "Your service conversation has a new reply.")
        self.assertContains(response, "14 Oct 2026, 10:15 AM")
        self.assertContains(response, f'href="{reverse("customer-profile")}"')
        self.assertContains(response, 'class="notification-item unread"')
        self.assertContains(response, 'class="notification-delete-button"')
        self.assertContains(response, "Delete all")
        self.assertContains(response, "js-confirm-form")

    def test_delete_actions_call_the_api_and_report_success_only_after_success(self):
        with patch("frontend.views.APIClient", FakeNotificationsAPI), patch("frontend.context_processors.APIClient", FakeNotificationsAPI):
            response = self.client.post(reverse("notifications-page"), {
                "action": "delete",
                "notification_id": "41",
                "back_to": reverse("customer-profile"),
            })

        self.assertEqual(response.status_code, 302)
        self.assertIn(("DELETE", "/notifications/41/", None), FakeNotificationsAPI.calls)
        with patch("frontend.views.APIClient", FakeNotificationsAPI), patch("frontend.context_processors.APIClient", FakeNotificationsAPI):
            page = self.client.get(response["Location"])
        self.assertContains(page, "Notification deleted.")

        FakeNotificationsAPI.failure = APIError(503, {"detail": "The service is temporarily unavailable."})
        with patch("frontend.views.APIClient", FakeNotificationsAPI), patch("frontend.context_processors.APIClient", FakeNotificationsAPI):
            failed = self.client.post(reverse("notifications-page"), {
                "action": "delete_all",
                "back_to": reverse("customer-profile"),
            })
        self.assertEqual(failed.status_code, 302)
        with patch("frontend.views.APIClient", FakeNotificationsAPI), patch("frontend.context_processors.APIClient", FakeNotificationsAPI):
            failed_page = self.client.get(failed["Location"])
        self.assertContains(failed_page, "temporarily unavailable")
        self.assertNotContains(failed_page, "notification deleted")

    def test_external_back_destinations_fall_back_to_an_internal_page(self):
        with patch("frontend.views.APIClient", FakeNotificationsAPI), patch("frontend.context_processors.APIClient", FakeNotificationsAPI):
            response = self.client.get(
                reverse("notifications-page"),
                {"next": "https://attacker.example/"},
                HTTP_REFERER="https://attacker.example/",
            )
        self.assertContains(response, f'href="{reverse("home")}"')
        self.assertNotContains(response, "attacker.example")
