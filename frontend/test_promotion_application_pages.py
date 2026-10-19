from django.test import RequestFactory, SimpleTestCase
from unittest.mock import patch

from frontend import views


class PromotionApplicantPageTests(SimpleTestCase):
    def make_request(self, path, role):
        request = RequestFactory().get(path)
        request.session = {
            "api_access": "session-test-token",
            "api_user": {"role": role, "first_name": "Ayo"},
            "api_role": role,
            "notif_unread_checked_at": 9_999_999_999,
            "notif_unread": 0,
        }
        return request

    def test_applicant_page_uses_backend_catalogue_and_explains_eligibility(self):
        catalog = {
            "eligibility": {
                "eligible": False,
                "requirements": [{"code": "PROFILE_NOT_ACTIVE", "message": "Your artisan profile must have Active status."}],
            },
            "institutions": [{
                "id": "f19a7276-35aa-4265-bf20-60af2c1847e4",
                "name": "Supported Institute",
                "campus": "Main Campus",
                "location": {"country": "Nigeria", "state": "Lagos", "area": "Ikeja"},
            }],
            "locations": [{
                "id": "0cb95812-3f4c-4891-9f6a-1d7545f50a9f",
                "country": "Nigeria",
                "state": "Lagos",
                "area": "Ikeja",
            }],
            "offerings": [{"id": 7, "category_name": "Home Repair", "service_name": "Pipe Repair", "location": None}],
            "applications": [],
        }
        request = self.make_request("/account/artisan/promotions/", "artisan")
        with patch("frontend.views._promotion_application_catalog", return_value=catalog):
            response = views.promotion_applications(request)

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        for text in (
            "Apply for Promotion", "Institution Promotion", "Area Promotion", "State Promotion",
            "Homepage Feature", "Supported Institute", "Social accounts, a website and portfolio links are optional",
            "never asks you to enter an identity number again", "Application review and paid campaign are separate records",
        ):
            self.assertIn(text, html)

    def test_customer_support_queue_and_review_detail_render(self):
        queue_request = self.make_request("/support/promotions/", "support")
        with (
            patch("frontend.views._support_capabilities", return_value={"can_review_promotions": True}),
            patch("frontend.views.APIClient.get", return_value=(200, {"count": 0, "results": []}, {})),
        ):
            queue_response = views.support_promotion_applications(queue_request)
        self.assertEqual(queue_response.status_code, 200)
        self.assertIn("AUTHORIZED CUSTOMER SUPPORT", queue_response.content.decode())

        application_id = "918cd991-3f99-40f6-a7b8-e806f643a154"
        application = {
            "id": application_id,
            "promotion_type_label": "Area Promotion",
            "status": "PENDING_REVIEW",
            "status_label": "Pending Review",
            "business_name": "Ayo Pipe Works",
            "artisan_name": "Ayo Artisan",
            "submitted_at": "2026-10-13T10:00:00Z",
            "current_revision_snapshot": {
                "revision_number": 1,
                "submitted_at": "2026-10-13T10:00:00Z",
                "promotion_type": "AREA",
                "target": {"kind": "AREA", "country": "Nigeria", "state": "Lagos", "area": "Ikeja"},
                "promotional_description": "Reliable local pipe repair with careful workmanship for homes and small businesses.",
                "services": [{"service_name": "Pipe Repair", "category_name": "Home Repair", "location": None, "starting_price": "12000.00"}],
                "profile": {
                    "name": "Ayo Artisan", "business_name": "Ayo Pipe Works", "bio": "Experienced professional offering reliable repair work.",
                    "years_experience": 6, "profile_status": "ACTIVE", "verification_status": "VERIFIED",
                    "average_rating": "0.00", "review_count": 0,
                    "registered_location": {"country": "Nigeria", "state": "Lagos", "area": "Ikeja"},
                    "profile_photo_url": "", "portfolio_url": "", "social_links": [],
                },
            },
            "revision_history": [{
                "revision_number": 1,
                "submitted_at": "2026-10-13T10:00:00Z",
                "snapshot": {"promotional_description": "Reliable local pipe repair with careful workmanship for homes and small businesses."},
                "evidence": [],
            }],
            "decisions": [],
        }
        detail_request = self.make_request(f"/support/promotions/{application_id}/", "support")
        with (
            patch("frontend.views._support_capabilities", return_value={"can_review_promotions": True}),
            patch("frontend.views.APIClient.get", return_value=(200, application, {})),
        ):
            detail_response = views.support_promotion_application_detail(detail_request, pk=application_id)

        self.assertEqual(detail_response.status_code, 200)
        detail_html = detail_response.content.decode()
        self.assertIn("PROFILE AT SUBMISSION", detail_html)
        self.assertIn("General availability · available anywhere", detail_html)
        self.assertIn("Do not enter internal-only notes here", detail_html)
        self.assertNotIn("staff_only_note", detail_html)
