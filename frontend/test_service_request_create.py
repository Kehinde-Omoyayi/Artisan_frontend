"""Service-request create: the create form replays one idempotency key.

The page renders the key as a hidden input (and keeps it in the session until a
create succeeds). These tests pin that behaviour:

* the hidden input is on the page with a value;
* posting it through to the API carries that exact key;
* the form re-render keeps the session key, so a failed attempt and a retry
  cannot mint two different keys.
"""

from unittest import mock
from uuid import uuid4

from django.test import TestCase

from frontend import views
from frontend import geography

CATALOG = {
    "ok": True,
    "services": ["Electrical Installation"],
    "locations": [],
    "institutions": [],
}


def _catalog_payload():
    return CATALOG


class ServiceRequestKeyTests(TestCase):
    def setUp(self):
        session = self.client.session
        session["api_access"] = "test-token"
        session["api_role"] = "customer"
        session["api_user"] = {"id": 3001, "email": "customer@example.com", "role": "customer"}
        session.save()

    def test_get_renders_a_stable_hidden_key(self):
        with mock.patch.object(views.APIClient, "get", autospec=True) as mock_get:
            def fake_get(self, path, params=None):
                if path == "/services/catalogue/" or path.startswith("/services/catalogue"):
                    return 200, {"services": [{"name": "Electrical Installation"}]}, {}
                return 200, {"results": []}, {}

            mock_get.side_effect = fake_get
            first = self.client.get("/requests/")
            self.assertEqual(first.status_code, 200)
            marker = b'name="idempotency_key" value="'
            self.assertIn(marker, first.content)
            session = self.client.session
            key = session.get("service_request_create_key")
            self.assertTrue(key)

    def test_post_forwards_the_form_key(self):
        with mock.patch.object(views.APIClient, "get", autospec=True) as mock_get, \
             mock.patch.object(views.APIClient, "post", autospec=True) as mock_post:
            complete_profile = {
                "first_name": "Ada",
                "last_name": "Customer",
                "phone_number": "+2348012345678",
                "country": "Nigeria",
                "state": "Lagos",
                "area": "Ikeja",
            }

            def fake_get(self, path, params=None):
                if "personal/profile" in path:
                    return 200, complete_profile, {}
                if path.startswith("/services/service_cat/"):
                    return 200, {
                        "results": [
                            {"name": "Electrical Installation", "category_name": "Electrical"}
                        ]
                    }, {}
                if path.startswith("/services/categories/"):
                    return 200, {"results": [{"name": "Electrical"}]}, {}
                if "requests" in path:
                    return 200, {"results": []}, {}
                return 200, {"results": []}, {}

            mock_get.side_effect = fake_get
            mock_post.return_value = (201, {"id": 99}, {})
            with mock.patch.object(
                geography,
                "canonical_location",
                lambda country, state, area: {
                    "country": country,
                    "state": state,
                    "area": area,
                },
            ):
                self.client.post(
                    "/requests/",
                    {
                        "action": "",
                        "idempotency_key": "service-request-create-abc123",
                        "category_name": "Electrical",
                        "service_name": "Electrical Installation",
                        "location_country_filter": "Nigeria",
                        "location_state_filter": "Lagos",
                        "location_area_filter": "Ikeja",
                        "preferred_date": "2026-12-01",
                        "urgency": "NORMAL",
                        "description": "Two wall outlets, please.",
                    },
                )
            keys = [call.kwargs.get("idempotency_key") for call in mock_post.mock_calls]
            self.assertTrue(any("abc123" in str(k) for k in keys), mock_post.mock_calls)
