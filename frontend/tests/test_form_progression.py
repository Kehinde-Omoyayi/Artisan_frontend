from django.test import SimpleTestCase

from frontend.forms import CustomerProfileForm, ServiceRequestForm
from frontend.views import cleaned_payload


class ProfilePhoneFieldTests(SimpleTestCase):
    def test_blank_new_profile_country_defaults_to_nigeria_and_calling_code(self):
        form = CustomerProfileForm(initial={"country": "", "phone_number": ""})
        self.assertEqual(form.initial["country"], "Nigeria")
        self.assertEqual(form.initial["phone_country_calling_code"], "+234")

    def test_unchanged_stored_phone_is_preserved_without_rewriting(self):
        stored = "08031234567"
        form = CustomerProfileForm({
            "first_name": "Ada", "last_name": "Customer", "phone_number": "8031234567",
            "phone_country_calling_code": "+234", "country": "Nigeria", "state": "Lagos",
            "area": "Yaba", "gender": "N",
        }, initial={"phone_number": stored, "country": "Nigeria"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["phone_number"], stored)
        self.assertTrue(form.cleaned_data["_phone_number_unchanged"])
        self.assertNotIn("phone_number", cleaned_payload(form.cleaned_data))

    def test_nigerian_national_number_with_or_without_domestic_zero_is_normalized(self):
        for national in ("08031234567", "8031234567"):
            with self.subTest(national=national):
                form = CustomerProfileForm({
                    "first_name": "Ada", "last_name": "Customer", "phone_number": national,
                    "phone_country_calling_code": "+234", "country": "Nigeria", "state": "Lagos",
                    "area": "Yaba", "gender": "N",
                })
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(form.cleaned_data["phone_number"], "+2348031234567")
                self.assertFalse(form.cleaned_data["_phone_number_unchanged"])

    def test_selected_international_calling_code_is_used_and_bad_numbers_are_rejected(self):
        form = CustomerProfileForm({
            "first_name": "Ada", "last_name": "Customer", "phone_number": "7400123456",
            "phone_country_calling_code": "+44", "country": "United Kingdom", "state": "England",
            "area": "Leeds", "gender": "N",
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["phone_number"], "+447400123456")

        invalid = CustomerProfileForm({
            "first_name": "Ada", "last_name": "Customer", "phone_number": "123",
            "phone_country_calling_code": "+234", "country": "Nigeria", "state": "Lagos",
            "area": "Yaba", "gender": "N",
        })
        self.assertFalse(invalid.is_valid())
        self.assertIn("phone_number", invalid.errors)


class CatalogueLocationFormTests(SimpleTestCase):
    def test_service_request_location_choices_are_only_existing_catalogue_records(self):
        locations = [{"id": "loc-1", "country": "Nigeria", "state": "Lagos", "area": "Yaba"}]
        form = ServiceRequestForm(
            categories=[{"name": "Plumbing"}],
            services=[{"name": "Pipe repair", "category_name": "Plumbing"}],
            locations=locations,
        )
        self.assertEqual(form.initial["location_country_filter"], "Nigeria")
        self.assertIn(("loc-1", "Yaba, Lagos, Nigeria"), form.fields["location_id"].choices)
        self.assertNotIn("invented-area", [value for value, _label in form.fields["location_id"].choices])
