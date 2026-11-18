"""Conversation message send: no unrelated GETs, backend is the authority.

Before the repair, sending a message through the page fired a
``GET /conversations/<id>/`` (to resolve the viewer role) and a profile GET,
all before the POST. Any transient failure of those reads produced a 503 to
the customer even though the message never reached the API. These tests pin:

* the message POST happens with no preceding conversation GET;
* a backend PROFILE_INCOMPLETE 403 redirects to the right profile page with
  the send stashed for resume (not an opaque 503);
* any other backend error re-renders/redirects with the standard handler.
"""

import uuid
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from frontend import views
from frontend.api import APIError

CONVERSATION_ID = uuid.uuid4()
DETAIL_URL = f"/discover/conversations/{CONVERSATION_ID}/"


class MessageSendTests(TestCase):
    def setUp(self):
        session = self.client.session
        session["api_access"] = "test-token"
        session["api_role"] = "customer"
        session["api_user"] = {"id": 2001, "email": "customer@example.com", "role": "customer"}
        session.save()

    def _post(self, post_exc=None, post_return=(201, {"id": "msg-1"}, {})):
        with mock.patch.object(views.APIClient, "get", autospec=True) as mock_get, \
             mock.patch.object(views.APIClient, "post", autospec=True) as mock_post:
            if post_exc is not None:
                mock_post.side_effect = post_exc
            else:
                mock_post.return_value = post_return
            response = self.client.post(DETAIL_URL, {"action": "message", "body": "Hello there"})
            return response, mock_get, mock_post

    def test_send_does_not_prefetch_the_conversation_before_posting(self):
        response, mock_get, mock_post = self._post()
        # No GET at all before the POST: the page no longer probes for the role.
        self.assertEqual(mock_get.call_count, 0)
        self.assertEqual(mock_post.call_count, 1)
        self.assertIn(response.status_code, (302, 200))

    def test_profile_incomplete_redirects_to_profile_and_stashes_the_send(self):
        exc = APIError(
            403,
            {
                "code": "PROFILE_INCOMPLETE",
                "message": "Complete your customer profile before sending a marketplace message.",
                "details": {"profile_role": "customer", "missing_fields": ["phone_number", "country"]},
            },
        )
        response, mock_get, mock_post = self._post(post_exc=exc)
        self.assertEqual(response.status_code, 302)
        self.assertIn("customer", response["Location"])
        self.assertEqual(mock_get.call_count, 0)
        session = self.client.session
        pending = session.get("pending_protected_action") or {}
        self.assertEqual(pending.get("kind"), "conversation_message")
        self.assertEqual(str(pending.get("conversation_id")), str(CONVERSATION_ID))
        self.assertEqual(pending.get("body"), "Hello there")

    def test_other_backend_error_uses_standard_handler(self):
        exc = APIError(503, None, network_error=True)
        response, mock_get, mock_post = self._post(post_exc=exc)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], DETAIL_URL)
