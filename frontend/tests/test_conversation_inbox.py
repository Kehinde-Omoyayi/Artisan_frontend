from pathlib import Path
from unittest.mock import Mock, patch
from uuid import UUID

from django.conf import settings
from django.test import TestCase
from django.urls import reverse


CONVERSATION_ID = "f315d2c2-f71a-4b6d-9f81-712481d095f5"


def inbox_item(*, unread_count=3):
    return {
        "id": CONVERSATION_ID,
        "conversation_type": "SERVICE",
        "viewer_role": "artisan",
        "title": "Lagos Spark Electrical",
        "counterparty": {
            "id": 12,
            "first_name": "Tomi",
            "last_name": "Ade",
            "business_name": "Lagos Spark Electrical",
            "profile_photo": None,
            "role": "artisan",
        },
        "participants": [],
        "state": "OPEN",
        "unread": unread_count > 0,
        "unread_count": unread_count,
        "last_message_at": "2026-10-14T16:22:00+01:00",
        "last_message_preview": "Nia Customer: Attached the new specifications for your review.",
        "created_at": "2026-10-14T15:00:00+01:00",
        "updated_at": "2026-10-14T16:22:00+01:00",
    }


class ConversationInboxTests(TestCase):
    def setUp(self):
        session = self.client.session
        session["api_access"] = "unit-test-session-token"
        session["api_user"] = {"id": 11, "first_name": "Nia", "role": "artisan"}
        session["api_role"] = "artisan"
        session.save()

    @staticmethod
    def fake_get(items):
        def get(path, params=None):
            if path == "/conversations/inbox/":
                return 200, {"count": len(items), "results": items}, {}
            if path == "/notifications/unread-count/":
                return 200, {"unread_count": 0}, {}
            raise AssertionError(f"Unexpected API GET: {path} {params}")
        return get

    @patch("frontend.context_processors.APIClient")
    @patch("frontend.views.APIClient")
    def test_inbox_card_uses_real_participant_details_preview_time_and_numeric_count(self, view_api, context_api):
        api = Mock()
        api.get.side_effect = self.fake_get([inbox_item(unread_count=3)])
        view_api.return_value = api
        context_api.return_value = api

        response = self.client.get(reverse("conversation-inbox"))

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("Tomi Ade", html)
        self.assertIn("Lagos Spark Electrical", html)
        self.assertIn("Attached the new specifications for your review.", html)
        self.assertIn('data-utc-time="2026-10-14T16:22:00+01:00"', html)
        self.assertIn('aria-label="3 unread messages">3</span>', html)
        self.assertNotIn("class=\"unread-dot\"", html)
        inbox_js = Path(settings.BASE_DIR / "static/js/pages/conversations-inbox.js").read_text(encoding="utf-8")
        self.assertIn("Intl.DateTimeFormat", inbox_js)
        css = Path(settings.BASE_DIR / "static/css/conversations.css").read_text(encoding="utf-8")
        self.assertIn("grid-template-columns: 72px minmax(0, 1fr) auto", css)
        self.assertIn("@media (max-width: 620px)", css)

    @patch("frontend.context_processors.APIClient")
    @patch("frontend.views.APIClient")
    def test_read_conversation_does_not_render_an_unread_badge(self, view_api, context_api):
        api = Mock()
        api.get.side_effect = self.fake_get([inbox_item(unread_count=0)])
        view_api.return_value = api
        context_api.return_value = api

        response = self.client.get(reverse("conversation-inbox"))

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("Tomi Ade", html)
        self.assertNotIn("unread-count-badge", html)
        self.assertNotIn("3 unread messages", html)
