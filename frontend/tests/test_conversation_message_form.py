"""Phase 4 regression: the chat composer is idempotent and answers AJAX with JSON.

* The message form renders a hidden ``idempotency_key`` minted by the view; the
  backend replays the stored message for a reused key, so a double tap on Send
  (or a retry after a network failure) can never mint two messages.
* A successful AJAX send returns a small JSON envelope instead of the whole
  re-rendered page.
* A failed AJAX send returns the JSON error envelope with the API's status —
  never a redirect-followed HTML document the browser would mistake for
  success.
"""

import json
from unittest.mock import patch

from django.test import SimpleTestCase, RequestFactory
from django.template.loader import render_to_string

from frontend import views


class ComposerKeyRenderTests(SimpleTestCase):
    def room(self):
        return {
            "id": "12345678-1234-4234-8234-123456789abc",
            "conversation_type": "SERVICE",
            "viewer_role": "customer",
            "viewer_id": 1,
            "available_actions": [],
            "journey": [],
        }

    def render(self, **extra):
        context = {
            "conversation": self.room(),
            "role": "customer",
            "nav_role": "customer",
            "csrf_token": "test-only",
            "current_phase": {
                "step": 1,
                "key": "REQUEST",
                "title": "Request & Chat",
                "description": "Open the chat and agree the request details.",
            },
            "request_brief": {},
            "message_key": "conversation-message-test-key-123",
        }
        context.update(extra)
        return render_to_string("conversations/detail.html", context)

    def test_composer_renders_the_hidden_idempotency_key(self):
        html = self.render()
        self.assertIn('name="idempotency_key"', html)
        self.assertIn('value="conversation-message-test-key-123"', html)

    def test_composer_key_still_renders_when_empty(self):
        html = self.render(message_key="")
        self.assertIn('name="idempotency_key"', html)


class AjaxSendContractTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _post(self, **kwargs):
        body = {
            "action": "message",
            "body": "The socket still sparks.",
            "idempotency_key": "conversation-message-test-1",
        }
        body.update(kwargs)
        request = self.factory.post(
            "/discover/conversations/12345678-1234-4234-8234-123456789abc/",
            body,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )
        request.session = {"api_access": "token", "api_refresh": "refresh-token"}
        return request

    def test_successful_ajax_send_returns_the_json_envelope(self):
        class FakeClient:
            def __init__(self, request):
                pass

            def get(self, path, params=None):
                return 200, {"viewer_role": "customer"}, {}

            def post(self, path, data=None, files=None, idempotency_key=None, headers=None):
                assert idempotency_key == "conversation-message-test-1"
                return 201, {"id": "m-1"}, {}

        with patch.object(views, "APIClient", FakeClient), patch.object(
            views, "_ensure_action_profile_complete", return_value=None
        ):
            response = views.conversation_detail(
                self._post(), "12345678-1234-4234-8234-123456789abc"
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"].split(";")[0], "application/json")
        self.assertEqual(json.loads(response.content), {"status": "ok"})

    def test_failed_ajax_send_returns_the_error_envelope_with_status(self):
        class FakeClient:
            def __init__(self, request):
                pass

            def get(self, path, params=None):
                return 200, {"viewer_role": "customer"}, {}

            def post(self, path, data=None, files=None, idempotency_key=None, headers=None):
                raise views.APIError(400, {"detail": "The message is too long."}, "text")

        with patch.object(views, "APIClient", FakeClient), patch.object(
            views, "_ensure_action_profile_complete", return_value=None
        ):
            response = views.conversation_detail(
                self._post(), "12345678-1234-4234-8234-123456789abc"
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response["Content-Type"].split(";")[0], "application/json")
        self.assertIn("too long", response.content.decode())

    def test_ajax_error_does_not_flash_a_message(self):
        """The JSON client shows the error itself; a flash would land unseen."""
        class FakeClient:
            def __init__(self, request):
                pass

            def get(self, path, params=None):
                return 200, {"viewer_role": "customer"}, {}

            def post(self, path, data=None, files=None, idempotency_key=None, headers=None):
                raise views.APIError(400, {"detail": "Nope."}, "text")

        request = self._post()
        with patch.object(views, "APIClient", FakeClient), patch.object(
            views, "_ensure_action_profile_complete", return_value=None
        ), patch.object(views, "handle_api_error") as flash:
            response = views.conversation_detail(
                request, "12345678-1234-4234-8234-123456789abc"
            )
        self.assertEqual(response.status_code, 400)
        flash.assert_not_called()
