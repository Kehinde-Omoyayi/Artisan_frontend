from types import SimpleNamespace
from unittest.mock import Mock

from django.test import RequestFactory, SimpleTestCase

from frontend.api import APIClient, APIError
from frontend.api_errors import normalize_api_error


class ApiErrorFormatterTests(SimpleTestCase):
    def test_simple_message_hides_codes_and_request_ids(self):
        message = normalize_api_error({
            "message": "We could not save your changes.",
            "code": "INVALID",
            "request_id": "private-request-id",
        }, 400)
        self.assertEqual(message, "We could not save your changes.")
        self.assertNotIn("INVALID", message)
        self.assertNotIn("private-request-id", message)

    def test_main_message_is_combined_with_a_single_field_error(self):
        self.assertEqual(
            normalize_api_error({
                "message": "Validation failed.",
                "details": {"Booking": ["The booking request failed."]},
            }, 400),
            "Validation failed. · Booking: The booking request failed.",
        )

    def test_message_detail_and_error_are_combined_without_duplicates(self):
        self.assertEqual(
            normalize_api_error({
                "message": "We could not save the request.",
                "detail": "Please check the highlighted fields.",
                "error": "Please check the highlighted fields.",
                "details": {"country": ["Choose a country."]},
            }, 400),
            "We could not save the request. · Please check the highlighted fields. · Country: Choose a country.",
        )

    def test_multiple_field_errors_and_non_field_messages_are_combined(self):
        message = normalize_api_error({
            "message": "Please review the form.",
            "details": {
                "phone_number": ["Enter a valid phone number."],
                "state": ["Choose a state or region."],
                "non_field_errors": ["The location is unavailable."],
            },
        }, 400)
        self.assertEqual(
            message,
            "Please review the form. · Phone number: Enter a valid phone number. · "
            "State: Choose a state or region. · The location is unavailable.",
        )

    def test_string_details_are_shown_without_metadata(self):
        self.assertEqual(
            normalize_api_error({
                "detail": "This account is not allowed to do that.",
                "details": "Complete your profile first.",
                "trace_id": "trace-secret",
            }, 403),
            "This account is not allowed to do that. · Complete your profile first.",
        )

    def test_missing_message_uses_available_field_errors(self):
        self.assertEqual(
            normalize_api_error({
                "code": "INVALID",
                "request_id": "private-request-id",
                "phone_number": ["This field is required."],
                "country": ["This field is required."],
            }, 400),
            "Phone number: This field is required. · Country: This field is required.",
        )

    def test_machine_code_used_as_message_is_not_shown(self):
        message = normalize_api_error({"message": "PROFILE_INCOMPLETE"}, 403)
        self.assertIn("permission", message)
        self.assertNotIn("PROFILE_INCOMPLETE", message)

    def test_profile_missing_fields_are_humanized_for_the_user(self):
        self.assertEqual(
            normalize_api_error({
                "message": "Complete your customer profile before continuing.",
                "details": {
                    "profile_role": "customer",
                    "missing_fields": ["first_name", "phone_number", "state"],
                },
            }, 403),
            "Complete your customer profile before continuing. · Missing fields: First name, Phone number, State",
        )

    def test_network_server_and_trace_failures_have_safe_fallbacks(self):
        self.assertIn("couldn’t connect", normalize_api_error(None, None, network_error=True))
        server_message = normalize_api_error(
            {"detail": "Traceback (most recent call last): File \"/srv/private.py\"", "request_id": "abc"},
            500,
        )
        self.assertIn("temporarily unavailable", server_message)
        self.assertNotIn("private.py", server_message)
        self.assertNotIn("abc", server_message)

    def test_malformed_json_never_leaks_raw_html_or_body_text(self):
        request = RequestFactory().get("/api/v1/example/")
        request.session = {}
        client = APIClient(request)
        client._send = Mock(return_value=(502, "<html>private proxy response</html>", SimpleNamespace(headers={})))
        with self.assertRaises(APIError) as context:
            client.get("/example/")
        message = str(context.exception)
        self.assertIn("temporarily unavailable", message)
        self.assertNotIn("private proxy response", message)
        self.assertNotIn("<html>", message)
        self.assertEqual(context.exception.text, "")
