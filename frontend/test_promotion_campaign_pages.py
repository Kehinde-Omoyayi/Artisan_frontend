import time
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from frontend import views


class PromotionCheckoutAndMyPromotionsTests(SimpleTestCase):
    class TestSession(dict):
        modified = False

    application_id = "c8a38b40-dffe-4f11-92de-20fa2457dd19"
    campaign_id = "797c601a-2a2e-437f-90a9-04373aac13bb"
    payment_id = "17c4bd37-d00a-40e3-947b-d0267b44b61f"

    def make_request(self, method, path, *, data=None, role="artisan", session_values=None):
        factory = RequestFactory()
        request = factory.get(path) if method == "GET" else factory.post(path, data or {})
        request.session = self.TestSession({
            "api_access": "session-test-token",
            "api_user": {"id": 7, "role": role, "first_name": "Ada"},
            "api_role": role,
            "notif_unread_checked_at": time.time(),
            "notif_unread": 0,
            **(session_values or {}),
        })
        return request

    def application(self):
        return {
            "id": self.application_id,
            "status": "APPROVED",
            "promotion_type_label": "Area Promotion",
            "target": {"area": "Ikeja", "state": "Lagos", "country": "Nigeria"},
        }

    def offer(self):
        return {
            "application_id": self.application_id,
            "promotion_type": "AREA",
            "promotion_type_label": "Area Promotion",
            "target": {"label": "Ikeja, Lagos, Nigeria"},
            "plan_name": "Area Promotion",
            "price": "2750",
            "currency": "NGN",
            "duration_days": 9,
            "terms_text": "Manager-authored terms; payment is queued only after terms are accepted.",
            "terms_version": 4,
            "availability": "AVAILABLE",
            "availability_reason": "",
            "capacity": 20,
            "paid_campaigns_in_inventory": 4,
            "earliest_start_at": "2026-10-20T09:00:00Z",
            "estimated_wait": "WAITING",
            "schedule_note": "The final queue position is assigned only after Flutterwave verification.",
            "quote_token": "signed-current-quote",
            "quote_expires_in_seconds": 900,
        }

    def test_checkout_renders_backend_price_terms_duration_and_estimated_start(self):
        request = self.make_request("GET", f"/account/artisan/promotions/{self.application_id}/checkout/")
        with patch("frontend.views.APIClient") as api_client:
            api_client.return_value.get.side_effect = [
                (200, self.application(), {}),
                (200, self.offer(), {}),
            ]
            response = views.promotion_checkout(request, pk=self.application_id)

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        for text in (
            "NGN 2750", "9 days", "Ikeja, Lagos, Nigeria", "2026-10-20T09:00:00Z",
            "Manager-authored terms", "verified server-side", 'name="quote_token"',
            'name="idempotency_key"',
        ):
            self.assertIn(text, html)
        self.assertTrue(request.session[f"promotion_checkout_key:{self.application_id}"].startswith("promotion-checkout-"))

    def test_checkout_post_uses_session_idempotency_key_and_clears_it_after_api_success(self):
        key = "promotion-checkout-stable-session-key"
        request = self.make_request(
            "POST",
            f"/account/artisan/promotions/{self.application_id}/checkout/",
            data={"quote_token": "signed-current-quote", "accepted_terms": "on", "terms_version": "4"},
            session_values={f"promotion_checkout_key:{self.application_id}": key},
        )
        with (
            patch("frontend.views.APIClient") as api_client,
            patch("frontend.views.messages.success"),
        ):
            api_client.return_value.get.side_effect = [
                (200, self.application(), {}),
                (200, self.offer(), {}),
            ]
            api_client.return_value.post.return_value = (
                202,
                {"payment_id": self.payment_id, "payment_status": "INITIALIZATION_PENDING"},
                {},
            )
            response = views.promotion_checkout(request, pk=self.application_id)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"/account/artisan/promotions/me/?payment={self.payment_id}")
        api_client.return_value.post.assert_called_once_with(
            f"/promotions/applications/{self.application_id}/checkout/",
            data={"quote_token": "signed-current-quote", "accepted_terms": True, "accepted_terms_version": "4"},
            idempotency_key=key,
        )
        self.assertNotIn(f"promotion_checkout_key:{self.application_id}", request.session)

    def test_my_promotions_keeps_application_campaign_payment_schedule_and_metrics_distinct(self):
        campaign = {
            "id": self.campaign_id,
            "application": self.application_id,
            "promotion_type_label": "Area Promotion",
            "plan_name_snapshot": "Area Promotion",
            "price": "2750",
            "currency": "NGN",
            "duration_days": 9,
            "status": "SCHEDULED",
            "status_label": "Scheduled",
            "target_label": "Ikeja, Lagos, Nigeria",
            "payment_verified_at": "2026-10-14T08:15:00Z",
            "queue_position": 1,
            "scheduled_start_at": "2026-10-20T09:00:00Z",
            "expires_at": "2026-10-29T09:00:00Z",
            "paused_at": None,
            "last_action_reason": "",
            "impressions": 12,
            "profile_clicks": 2,
            "enquiries": 1,
            "payment_history": [{
                "id": self.payment_id,
                "reference": "PROMO-TEST-001",
                "amount": "2750",
                "currency": "NGN",
                "status": "VERIFIED",
                "status_label": "Verified",
                "verified_at": "2026-10-14T08:15:00Z",
                "created_at": "2026-10-14T08:10:00Z",
                "expires_at": "2026-10-14T08:40:00Z",
                "failure_reason": "",
                "authorization_url": "",
            }],
            "latest_payment": {"id": self.payment_id},
            "actions": [],
        }
        request = self.make_request("GET", "/account/artisan/promotions/me/")
        with patch("frontend.views.APIClient") as api_client:
            api_client.return_value.get.side_effect = [
                (200, [campaign], {}),
                (200, [self.application()], {}),
            ]
            response = views.my_promotions(request)

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        for text in (
            "Campaign history", "Payment history", "Application history", "PROMO-TEST-001",
            "Queue position", "Scheduled", "2026-10-20T09:00:00Z", "12", "Not available yet",
        ):
            self.assertIn(text, html)


class PromotionSupportCaseLinkTests(SimpleTestCase):
    campaign_id = "797c601a-2a2e-437f-90a9-04373aac13bb"

    def test_existing_case_create_flow_prefills_and_posts_promotion_campaign(self):
        request = RequestFactory().post(
            f"/support/cases/?promotion_campaign={self.campaign_id}",
            {
                "promotion_campaign": self.campaign_id,
                "case_type": "REPORT",
                "priority": "MEDIUM",
                "subject": "Sponsored placement concern",
                "description": "I want support to review the sponsored placement and provide relevant evidence.",
            },
        )
        request.session = {
            "api_access": "session-test-token",
            "api_user": {"id": 7, "role": "artisan", "first_name": "Ada"},
            "api_role": "artisan",
            "notif_unread_checked_at": time.time(),
            "notif_unread": 0,
        }
        case = {"id": 42, "reference": "CASE-PROMO-001", "promotion_campaign": self.campaign_id}
        with (
            patch("frontend.views.APIClient") as api_client,
            patch("frontend.views._support_capabilities", return_value={"is_support_staff": False}),
            patch("frontend.views.messages.success"),
        ):
            api_client.return_value.post.return_value = (201, case, {})
            response = views.support_cases(request)

        self.assertEqual(response.status_code, 302)
        api_client.return_value.post.assert_called_once_with("/support/cases/", {
            "promotion_campaign": self.campaign_id,
            "case_type": "REPORT",
            "priority": "MEDIUM",
            "subject": "Sponsored placement concern",
            "description": "I want support to review the sponsored placement and provide relevant evidence.",
        })


class PublicPromotionLandingTests(SimpleTestCase):
    def test_anonymous_landing_fetches_homepage_promotions_without_authentication(self):
        from frontend.views import home

        sponsored = {
            "campaign_id": "797c601a-2a2e-437f-90a9-04373aac13bb",
            "artisan_id": "9b7f7234-7339-4c83-9868-7a0d83f81399",
            "name": "Ada Artisan",
            "business_name": "Ada Repairs",
            "profile_photo_url": "",
            "average_rating": "4.80",
            "review_count": 12,
            "artisan_url": "/discover/artisans/9b7f7234-7339-4c83-9868-7a0d83f81399/",
            "promotion_type": "HOMEPAGE",
            "description": "Careful repairs for homes and small businesses.",
            "services": [{"service_name": "Pipe Repair"}],
        }
        request = RequestFactory().get("/")
        request.session = {}
        with patch("frontend.views.APIClient") as api_client:
            api_client.return_value.get.return_value = (200, [sponsored], {})
            response = home(request)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(request.session.get("api_access"))
        self.assertIn("Sponsored · Homepage Feature", response.content.decode())
        self.assertIn("Ada Repairs", response.content.decode())
        self.assertIn("Report this sponsored placement", response.content.decode())
        self.assertEqual(
            [call.args[0] for call in api_client.return_value.get.call_args_list],
            ["/promotions/homepage/", "/promotions/market-picks/"],
        )
