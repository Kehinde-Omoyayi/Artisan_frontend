"""Page-level ₦100.00 minimum-price pre-checks, exercised through the real view.

Requirement B is enforced twice on this page, independently:

* the browser blocks the submit and shows the platform-standard inline
  message (static/js/min-price.js, covered by code review — this project has
  no browser automation harness);
* this Django view re-validates every amount before any network call and
  re-renders the form with 400 and the same message when something is off.

The API behind the page is mocked: these tests prove the page never forwards
a sub-₦100 price, blocks the action locally, and keeps the artisan's entries.
Backend enforcement itself is covered by the backend suite
(``conversations.test_min_price``), not re-tested here.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest import mock

from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from frontend import views
from frontend.pricing import MIN_INDIVIDUAL_PRICE_MESSAGE

CONVERSATION_ID = uuid.uuid4()
DETAIL_URL = f"/discover/conversations/{CONVERSATION_ID}/"


def _conversation_payload(role="artisan"):
    return {
        "id": str(CONVERSATION_ID),
        "conversation_type": "SERVICE",
        "state": "NEGOTIATING",
        "viewer_role": role,
        "viewer_id": 1001,
        "title": "Ada Customer",
        "unread_count": 0,
        "counterparty": {
            "profile_photo": "",
            "first_name": "Ada",
        },
        "available_actions": ["SEND_OFFER"],
        "active_offer": None,
        "booking": None,
        "payment": None,
        "additional_orders": [],
        "dispute_case": None,
        "journey": [],
    }


def _messages_payload():
    return {"results": []}


def _get_side_effect(request):
    conversation = _conversation_payload()
    messages = _messages_payload()

    def fake_get(path, params=None):
        if path == f"/conversations/{CONVERSATION_ID}/":
            return 200, conversation, {}
        if path == f"/conversations/{CONVERSATION_ID}/messages/":
            return 200, messages, {}
        if path == f"/conversations/{CONVERSATION_ID}/offers/":
            return 200, {"results": []}, {}
        return 200, {}, {}

    return fake_get


def _offer_post(**overrides):
    scheduled = (datetime.now(timezone.utc) + timedelta(days=3)).replace(microsecond=0)
    data = {
        "action": "offer",
        "labour_amount": "25000.00",
        "materials_amount": "0",
        "materials_json": "[]",
        "transport_amount": "0",
        "additional_amount": "0",
        "scheduled_start": scheduled.isoformat(),
        "duration_value": "2",
        "duration_unit": "DAYS",
        "urgency": "NORMAL",
        "idempotency_key": "test-offer-key",
    }
    data.update(overrides)
    return data


@override_settings(ARTISAN_API_TRANSPORT="inprocess")
class OfferPreCheckTests(TestCase):
    def setUp(self):
        session = self.client.session
        session["api_access"] = "test-token"
        session["api_role"] = "artisan"
        session["api_user"] = {"id": 1001, "email": "artisan@example.com", "role": "artisan"}
        session.save()
        # The middleware and the page both need a CSRF token match for POST; the
        # test client handles that with enforce_csrf_checks disabled by default.

    def _post(self, data):
        with mock.patch.object(views.APIClient, "get", autospec=True) as mock_get, \
             mock.patch.object(views.APIClient, "post", autospec=True) as mock_post:
            mock_get.side_effect = lambda self, path, params=None: _get_side_effect(None)(path, params)
            mock_post.return_value = (201, {"id": "offer-1", "status": "PENDING"}, {})
            response = self.client.post(DETAIL_URL, data)
            return response, mock_post

    def test_labour_below_the_minimum_blocks_the_offer_and_names_the_field(self):
        response, mock_post = self._post(_offer_post(labour_amount="50.00"))
        self.assertEqual(response.status_code, 400)
        mock_post.assert_not_called()
        self.assertContains(response, MIN_INDIVIDUAL_PRICE_MESSAGE, status_code=400)

    def test_labour_at_ninety_nine_ninety_nine_is_rejected(self):
        response, mock_post = self._post(_offer_post(labour_amount="99.99"))
        self.assertEqual(response.status_code, 400)
        mock_post.assert_not_called()

    def test_labour_exactly_one_hundred_is_accepted(self):
        response, mock_post = self._post(_offer_post(labour_amount="100.00"))
        self.assertEqual(response.status_code, 302)
        mock_post.assert_called_once()

    def test_a_single_bad_material_row_rejects_the_whole_submission(self):
        materials = json.dumps(
            [
                {"name": "Sand", "quantity": "1", "unit": "bag", "unit_price": "500.00"},
                {"name": "Gravel", "quantity": "2", "unit": "bag", "unit_price": "40.00"},
            ]
        )
        response, mock_post = self._post(_offer_post(materials_json=materials, materials_amount="580.00"))
        self.assertEqual(response.status_code, 400)
        mock_post.assert_not_called()
        self.assertContains(response, MIN_INDIVIDUAL_PRICE_MESSAGE, status_code=400)

    def test_all_materials_at_the_minimum_or_above_pass(self):
        materials = json.dumps(
            [
                {"name": "Sand", "quantity": "1", "unit": "bag", "unit_price": "100.00"},
                {"name": "Gravel", "quantity": "2", "unit": "bag", "unit_price": "150.00"},
            ]
        )
        response, mock_post = self._post(_offer_post(materials_json=materials, materials_amount="400.00"))
        self.assertEqual(response.status_code, 302)
        mock_post.assert_called_once()

    def test_unused_transport_and_additional_charges_may_stay_zero(self):
        response, mock_post = self._post(
            _offer_post(transport_amount="0", additional_amount="0")
        )
        self.assertEqual(response.status_code, 302)
        mock_post.assert_called_once()

    def test_transport_below_the_minimum_is_rejected(self):
        response, mock_post = self._post(_offer_post(transport_amount="50"))
        self.assertEqual(response.status_code, 400)
        mock_post.assert_not_called()

    def test_additional_charge_below_the_minimum_is_rejected(self):
        response, mock_post = self._post(_offer_post(additional_amount="99.99"))
        self.assertEqual(response.status_code, 400)
        mock_post.assert_not_called()

    def test_counter_offer_uses_the_same_minimum(self):
        response, mock_post = self._post(
            _offer_post(action="counter", labour_amount="10.00", parent_offer_id="offer-1")
        )
        self.assertEqual(response.status_code, 400)
        mock_post.assert_not_called()

    def test_addon_proposal_below_the_minimum_never_reaches_the_api(self):
        with mock.patch.object(views.APIClient, "get", autospec=True) as mock_get, \
             mock.patch.object(views.APIClient, "post", autospec=True) as mock_post:
            conversation = _conversation_payload()
            conversation["booking"] = {"id": "booking-1", "status": "IN_PROGRESS", "created_at": "2026-11-18T09:00:00+00:00"}
            mock_get.side_effect = lambda self, path, params=None: (
                (200, conversation, {})
                if path == f"/conversations/{CONVERSATION_ID}/"
                else (200, _messages_payload(), {})
                if path == f"/conversations/{CONVERSATION_ID}/messages/"
                else (200, {"results": []}, {})
            )
            response = self.client.post(
                DETAIL_URL,
                {
                    "action": "additional_order_propose",
                    "amount": "25.00",
                    "description": "Supply and fit a ceiling fan.",
                },
            )
            self.assertEqual(response.status_code, 302)  # redirected back with a message
            mock_post.assert_not_called()


@override_settings(ARTISAN_API_TRANSPORT="inprocess")
class TimelineRenderSmokeTests(TestCase):
    """The server-rendered page must carry every record card inside the
    unified timeline — the client never invents positions."""

    def setUp(self):
        session = self.client.session
        session["api_access"] = "test-token"
        session["api_role"] = "artisan"
        session["api_user"] = {"id": 1001, "email": "artisan@example.com", "role": "artisan"}
        session.save()

    def _get(self, conversation, messages_results, offers_results=None):
        with mock.patch.object(views.APIClient, "get", autospec=True) as mock_get:
            def fake_get(self, path, params=None):
                if path == f"/conversations/{CONVERSATION_ID}/":
                    return 200, conversation, {}
                if path == f"/conversations/{CONVERSATION_ID}/messages/":
                    return 200, {"results": messages_results}, {}
                if path == f"/conversations/{CONVERSATION_ID}/offers/":
                    return 200, {"results": offers_results or []}, {}
                return 200, {}, {}

            mock_get.side_effect = fake_get
            return self.client.get(DETAIL_URL)

    def _rich_conversation(self):
        return {
            "id": str(CONVERSATION_ID),
            "conversation_type": "SERVICE",
            "state": "ACTIVE",
            "viewer_role": "artisan",
            "viewer_id": 1001,
            "title": "Ada Customer",
            "unread_count": 0,
            "counterparty": {"profile_photo": "", "first_name": "Ada"},
            "available_actions": [],
            "booking": {
                "id": "b2f6a4e5-6f6c-4f79-92f6-62b56f3389aa",
                "status": "IN_PROGRESS",
                "created_at": "2026-11-18T08:00:00+00:00",
                "price_agreed": "25000.00",
                "scheduled_start": "2026-11-19T09:00:00+00:00",
                "scheduled_end": "2026-11-19T17:00:00+00:00",
                "artisan_name": "Tunde",
                "customer_name": "Ada",
            },
            "payment": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "HELD",
                "created_at": "2026-11-18T08:30:00+00:00",
                "total_amount": "25500.00",
                "service_amount": "25000.00",
                "customer_fee": "500.00",
                "verified_at": "2026-11-18T08:35:00+00:00",
            },
            "additional_orders": [
                {
                    "id": "addon-1",
                    "status": "NEGOTIATING",
                    "created_at": "2026-11-18T09:15:00+00:00",
                    "current_offer": {
                        "id": "addon-offer-1",
                        "amount": "5000.00",
                        "description": "Replace the tap head too",
                        "revision": 1,
                        "status": "PROPOSED",
                        "created_by_id": 1001,
                        "created_at": "2026-11-18T09:15:00+00:00",
                    },
                    "offers": [],
                    "can_pay": False,
                    "payment": None,
                }
            ],
            "active_offer": None,
            "dispute_case": None,
            "journey": [],
        }

    def test_get_renders_reviewable_timeline_with_payment_and_addon(self):
        messages = [
            {
                "id": "message-1",
                "created_at": "2026-11-18T09:05:00+00:00",
                "body": "On my way with the tools",
                "message_type": "USER",
                "sender_id": 1001,
                "attachments": [],
                "event_code": None,
            }
        ]
        response = self._get(self._rich_conversation(), messages)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn('data-timeline-kind="booking"', content)
        self.assertIn('data-timeline-kind="payment"', content)
        self.assertIn('data-timeline-kind="addon"', content)
        self.assertIn('data-timeline-kind="journey"', content)
        self.assertIn("On my way with the tools", content)
        # No fixed home for the record cards: they all live inside the stream.
        stream_start = content.index('id="conversation-stream"')
        self.assertIn('data-timeline-kind="payment"', content[stream_start:])

    def test_get_renders_offer_card_inside_the_stream(self):
        conversation = self._rich_conversation()
        conversation["active_offer"] = {
            "id": "offer-1",
            "version": 1,
            "created_at": "2026-11-18T07:00:00+00:00",
            "total_amount": "25000.00",
            "labour_amount": "24000.00",
            "materials_amount": "1000.00",
            "transport_amount": "0.00",
            "additional_amount": "0.00",
            "materials_included": False,
            "materials": [],
            "duration_label": "2 days",
            "creator_id": 1001,
            "status": "ACCEPTED",
            "notification_delivered": True,
        }
        response = self._get(conversation, [])
        self.assertEqual(response.status_code, 200)
        self.assertIn('data-timeline-kind="offer"', response.content.decode("utf-8"))
