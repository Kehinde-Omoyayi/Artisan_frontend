"""Phase 9 — incoming activity moved to the dashboard.

Fault repaired: the full incoming-activity experience (income summary, payout
alerts, notification previews, matching-request previews) lived only on the
artisan profile page, while the dashboard showed a thin "Your activity" set of
dialog popups. The dashboard now carries the incoming-activity section; the
profile page keeps the form and the identity surfaces.
"""
from django.test import SimpleTestCase
from django.template.loader import render_to_string


def _artisan_context():
    return {
        "role": "artisan",
        "nav_role": "artisan",
        "csrf_token": "test-only",
        "profile": {"business_name": "Test Works", "average_rating": 4.5, "completion_rate": 91.2, "cancellation_rate": 2.5},
        "profile_health": {"complete": True, "percent": 100, "completed": 6, "total": 6, "missing_labels": []},
        "services": [{"id": "s1"}],
        "requests": [
            {
                "service_name": "Ceiling fan installation",
                "category_name": "Electrical",
                "urgency": "HIGH",
                "description": "Install the new ceiling fan in the dining room.",
                "location": {"area": "Ikeja", "state": "Lagos", "country": "Nigeria"},
                "preferred_date": "2026-11-20",
            }
        ],
        "request_total": 7,
        "bookings": [],
        "booking_total": 3,
        "notifications": [
            {
                "title": "Booking accepted",
                "message": "Your booking was accepted.",
                "created_at": "2026-11-16T08:00:00Z",
                "read_at": None,
                "safe_url": "/bookings/1/",
                "safe_action_label": "Open booking",
            }
        ],
        "notification_previews": [
            {
                "title": "Notification preview item",
                "message": "Something happened.",
                "created_at": "2026-11-16T08:00:00Z",
                "read_at": None,
                "safe_url": "",
                "safe_action_label": "",
            }
        ],
        "payout_notifications": [
            {
                "title": "Payout sent",
                "message": "Your payout of NGN 45,000 was sent.",
                "created_at": "2026-11-15T09:30:00Z",
                "safe_url": "/account/payouts/",
            }
        ],
        "notification_total": 12,
        "unread_notification_count": 2,
        "income_summary": {
            "available": True,
            "this_month_amount": "120,000.00",
            "month_label": "November 2026",
            "this_month_payout_count": 3,
            "lifetime_amount": "1,450,000.00",
            "lifetime_payout_count": 18,
        },
    }


class DashboardIncomingActivityTests(SimpleTestCase):
    def render(self):
        return render_to_string("dashboard.html", _artisan_context())

    def test_dashboard_carries_the_incoming_activity_section(self):
        html = self.render()
        self.assertIn("Incoming activity", html)
        self.assertIn("artisan-profile-activity-section", html)
        # Income column, populated.
        self.assertIn("Paid this month", html)
        self.assertIn("₦120,000.00", html)
        self.assertIn("Lifetime paid out", html)
        self.assertIn("₦1,450,000.00", html)
        self.assertIn("Payout sent", html)
        # Notifications column with previews and unread badge.
        self.assertIn("Notification preview item", html)
        self.assertIn("artisan-notification-dialog", html)
        # Matching requests column.
        self.assertIn("Ceiling fan installation", html)
        self.assertIn("7 request", html)

    def test_thin_activity_hub_is_gone(self):
        html = self.render()
        for marker in (
            "dashboard-activity-hub",
            'id="dashboard-requests"',
            'id="dashboard-notifications"',
            'id="dashboard-bookings"',
            "dashboard-activity-dialog",
        ):
            self.assertNotIn(marker, html)


class ArtisanProfilePageTests(SimpleTestCase):
    def render(self):
        from frontend.forms import ArtisanProfileForm

        context = {
            "role": "artisan",
            "nav_role": "artisan",
            "csrf_token": "test-only",
            "profile": {
                "business_name": "Test Works",
                "average_rating": 4.5,
                "completion_rate": 91.2,
                "cancellation_rate": 2.5,
            },
            "form": ArtisanProfileForm(initial={}),
            "profile_picker_today": "2026-11-16",
            "profile_completion_required": False,
            "missing_profile_fields": [],
            "next_target": "",
        }
        return render_to_string("artisan/profile.html", context)

    def test_incoming_activity_is_no_longer_on_the_profile_page(self):
        html = self.render()
        self.assertNotIn("artisan-profile-activity-section", html)
        self.assertNotIn("artisan-notification-dialog", html)
        self.assertNotIn("Income summary unavailable", html)
