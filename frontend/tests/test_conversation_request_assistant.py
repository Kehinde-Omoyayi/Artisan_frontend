from pathlib import Path
from unittest.mock import Mock, patch
from uuid import UUID

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from frontend.api import APIError


CONVERSATION_ID = "f315d2c2-f71a-4b6d-9f81-712481d095f5"
LOCATION_ID = "f0250929-a7a9-4f07-82ee-47bf45b139d9"


def conversation_payload():
    request_options = {
        "categories": [{
            "id": "Electrical",
            "name": "Electrical",
            "services": [{
                "id": "3",
                "name": "Electrical Repairs",
                "category_id": "Electrical",
                "category_name": "Electrical",
                "locations": [{
                    "id": LOCATION_ID,
                    "country": "Nigeria",
                    "state": "Lagos",
                    "area": "Ikeja",
                    "label": "Ikeja, Lagos, Nigeria",
                }],
            }],
        }],
        "services": [{
            "id": "3",
            "name": "Electrical Repairs",
            "category_id": "Electrical",
            "category_name": "Electrical",
            "locations": [{
                "id": LOCATION_ID,
                "country": "Nigeria",
                "state": "Lagos",
                "area": "Ikeja",
                "label": "Ikeja, Lagos, Nigeria",
            }],
        }],
        "locations": [{
            "id": LOCATION_ID,
            "country": "Nigeria",
            "state": "Lagos",
            "area": "Ikeja",
            "label": "Ikeja, Lagos, Nigeria",
            "service_ids": ["3"],
        }],
    }
    return {
        "id": CONVERSATION_ID,
        "conversation_type": "SERVICE",
        "title": "Lagos Spark Electrical",
        "state": "OPEN",
        "viewer_role": "customer",
        "viewer_id": 11,
        "unread_count": 0,
        "counterparty": {
            "id": 12,
            "first_name": "Tomi",
            "last_name": "Ade",
            "business_name": "Lagos Spark Electrical",
            "profile_photo": None,
            "role": "artisan",
        },
        "participants": [
            {"id": 11, "first_name": "Nia", "last_name": "Customer", "business_name": "", "role": "customer"},
            {"id": 12, "first_name": "Tomi", "last_name": "Ade", "business_name": "Lagos Spark Electrical", "role": "artisan"},
        ],
        "assistant": {
            "mode": "collecting_details",
            "reply": "Choose a service from this artisan’s real catalogue.",
            "prompt": {"field": "service", "text": "Choose a service.", "optional": False},
            "suggestions": ["I’ll correct a detail"],
            "request_state": {
                "status": "draft",
                "values": {
                    "service_id": "3",
                    "category_id": "Electrical",
                    "description": "Replace the damaged socket.",
                    "location_id": LOCATION_ID,
                    "country": "Nigeria",
                    "state": "Lagos",
                    "area": "Ikeja",
                    "preferred_date": "2026-10-20",
                    "preferred_time_start": "09:00",
                    "preferred_time_end": "11:00",
                    "preferred_time_note": "Before work",
                    "urgency": "NORMAL",
                    "budget": "",
                    "budget_unknown": True,
                    "additional_details": "Call on arrival.",
                },
                "missing_fields": [],
                "complete": True,
                "ready_to_submit": False,
            },
            "request_options": request_options,
        },
        "service_request": None,
        "request_draft": {
            "category_id": "Electrical",
            "category_name": "Electrical",
            "service_id": "3",
            "service_name": "Electrical Repairs",
            "description": "Replace the damaged socket.",
            "location_id": LOCATION_ID,
            "country": "Nigeria",
            "state": "Lagos",
            "area": "Ikeja",
            "location_label": "Ikeja, Lagos",
            "preferred_date": "2026-10-20",
            "preferred_time_start": "09:00",
            "preferred_time_end": "11:00",
            "preferred_time_note": "Before work",
            "urgency": "NORMAL",
            "budget_unknown": True,
            "additional_details": "Call on arrival.",
        },
        "active_offer": None,
        "available_actions": ["SEND_MESSAGE", "EDIT_REQUEST"],
        "booking": None,
        "payment": None,
        "dispute_case": None,
        "journey": [],
    }


class ConversationRequestAssistantTests(TestCase):
    def setUp(self):
        session = self.client.session
        session["api_access"] = "unit-test-session-token"
        session["api_user"] = {"id": 11, "first_name": "Nia", "role": "customer"}
        session["api_role"] = "customer"
        session.save()

    def fake_get(self, conversation):
        def get(path, params=None):
            if path == f"/conversations/{CONVERSATION_ID}/":
                return 200, conversation, {}
            if path == f"/conversations/{CONVERSATION_ID}/messages/":
                return 200, {"count": 0, "results": []}, {}
            if path == f"/conversations/{CONVERSATION_ID}/offers/":
                return 200, {"count": 0, "results": []}, {}
            if path == "/notifications/unread-count/":
                return 200, {"unread_count": 0}, {}
            raise AssertionError(f"Unexpected API GET: {path} {params}")
        return get

    @patch("frontend.views.APIClient")
    @patch("frontend.context_processors.APIClient")
    def test_customer_conversation_renders_catalogue_backed_review_and_offline_draft(self, context_api, view_api):
        conversation = conversation_payload()
        api = Mock()
        api.get.side_effect = self.fake_get(conversation)
        view_api.return_value = api
        context_api.return_value = api

        response = self.client.get(reverse("conversation-detail", args=[UUID(CONVERSATION_ID)]))

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('id="request-assistant-form"', html)
        self.assertIn('id="conversation-assistant"', html)
        self.assertIn('data-assistant-enabled="true"', html)
        self.assertIn("Artisan Market guided request helper", html)
        self.assertIn("not a live AI service", html)
        self.assertIn("Nothing is submitted until you review and choose Submit request", html)
        self.assertIn('name="category_id"', html)
        self.assertIn('name="service_id"', html)
        self.assertIn('name="location_id"', html)
        self.assertIn('type="date" name="preferred_date"', html)
        self.assertIn('type="time" name="preferred_time_start"', html)
        self.assertIn('data-request-review', html)
        self.assertIn("Review before submitting", html)
        self.assertIn(reverse("offline-request-assistant"), html)
        self.assertIn("data-location-select", html)
        self.assertIn('<details class="request-assistant-card" id="request-assistant-card"', html)
        page_js = Path(settings.BASE_DIR / "static/js/request-assistant.js").read_text(encoding="utf-8")
        self.assertIn("localStorage", page_js)
        self.assertIn("ArtisanApiErrors", page_js)
        self.assertIn("request_submit", page_js)
        self.assertIn("server_saved_at", page_js)
        self.assertIn("submittedFields", page_js)
        self.assertIn("requestSubmitted", page_js)
        self.assertIn("submitInFlight", page_js)
        self.assertIn("const nextDirtyFields = new Set(dirtyFields)", page_js)
        self.assertIn("valuesEqual(name, current[name], serverValues[name])", page_js)
        self.assertIn("artisan:assistant-state", page_js)
        message_js = Path(settings.BASE_DIR / "static/js/pages/conversations-detail.js").read_text(encoding="utf-8")
        self.assertIn("readAsDataURL", message_js)
        self.assertIn("formatSchedule", message_js)
        self.assertIn("data-assistant-date", message_js)
        self.assertIn("assistantControlAdd", message_js)
        self.assertIn("artisan:assistant-state", message_js)
        self.assertIn("data-attachment-index", message_js)
        self.assertIn("syncFileInput", message_js)
        self.assertIn("Remove", message_js)
        self.assertIn('accept="image/*,.pdf"', html)

    @patch("frontend.context_processors.APIClient")
    @patch("frontend.views.APIClient")
    def test_request_draft_post_calls_existing_conversation_api_and_marks_it_unsent(self, api_client, context_api):
        context_api.return_value.get.return_value = (200, {"unread_count": 0}, {})
        api = Mock()
        api.patch.return_value = (200, {
            "id": CONVERSATION_ID,
            "request_draft": {"service_id": "3", "description": "Repair the socket."},
            "service_request": None,
        }, {})
        api_client.return_value = api

        response = self.client.post(
            reverse("conversation-detail", args=[UUID(CONVERSATION_ID)]),
            {
                "action": "request_draft",
                "category_id": "Electrical",
                "service_id": "3",
                "description": "Repair the socket.",
                "location_id": LOCATION_ID,
                "country": "Nigeria",
                "state": "Lagos",
                "area": "Ikeja",
                "preferred_date": "2026-10-20",
                "preferred_time_start": "09:00",
                "preferred_time_end": "11:00",
                "preferred_time_note": "Before work",
                "urgency": "NORMAL",
                "budget": "",
                "budget_unknown": "true",
                "additional_details": "Call on arrival.",
            },
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertIsNone(response.json()["service_request"])
        api.patch.assert_called_once()
        self.assertEqual(api.patch.call_args.args[0], f"/conversations/{CONVERSATION_ID}/request/")
        payload = api.patch.call_args.args[1]
        self.assertFalse(payload["submit_request"])
        self.assertTrue(payload["budget_unknown"])
        self.assertIsNone(payload["budget"])
        self.assertEqual(payload["preferred_time_start"], "09:00")
        self.assertEqual(payload["additional_details"], "Call on arrival.")

    @patch("frontend.context_processors.APIClient")
    @patch("frontend.views.APIClient")
    def test_rejected_submit_returns_safe_field_errors_and_never_reports_success(self, api_client, context_api):
        context_api.return_value.get.return_value = (200, {"unread_count": 0}, {})
        api = Mock()
        api.patch.side_effect = APIError(400, {"preferred_date": ["Choose a preferred date."]})
        api_client.return_value = api

        response = self.client.post(
            reverse("conversation-detail", args=[UUID(CONVERSATION_ID)]),
            {"action": "request_submit", "description": "Repair the socket."},
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertNotIn("ok", payload)
        self.assertEqual(payload["field_errors"]["preferred_date"], "Choose a preferred date.")
        self.assertIn("preferred date", payload["message"].lower())

    @patch("frontend.context_processors.APIClient")
    def test_offline_shell_and_worker_are_public_and_do_not_require_api_calls(self, context_api):
        context_api.return_value.get.return_value = (200, {"unread_count": 0}, {})
        response = self.client.get(reverse("offline-request-assistant"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("Keep your request moving offline", html)
        self.assertIn("data-offline-assistant", html)
        self.assertIn("Sync draft now", html)
        self.assertIn("offline-request-assistant.js", html)

        offline_js = Path(settings.BASE_DIR / "static/js/pages/offline-request-assistant.js").read_text(encoding="utf-8")
        self.assertIn("renderServices();", offline_js)
        self.assertIn("savedLocationId", offline_js)
        self.assertIn("submittedFields", offline_js)

        worker = self.client.get(reverse("service-worker"))
        self.assertEqual(worker.status_code, 200)
        self.assertEqual(worker["Service-Worker-Allowed"], "/")
        self.assertIn("artisan-market-offline-v1", worker.content.decode())
        self.assertIn(r"\/discover\/conversations", worker.content.decode())
