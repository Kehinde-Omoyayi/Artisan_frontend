from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse


MANAGER_KPI_KEYS = """
active_escrow_kobo artisans_active artisans_new_30d artisans_pending_verification
artisans_total artisans_unverified artisans_verified booking_cancellation_rate
booking_completion_rate booking_conversion_rate_30d booking_dispute_rate bookings_30d
bookings_active bookings_completed bookings_total cancellation_reviews_pending
categories_total customer_collections_30d_kobo customer_collections_lifetime_kobo
customer_collections_month_kobo customers_active customers_new_30d customers_total
emergency_requests_30d messages_30d offer_acceptance_rate_30d paid_payments_30d
paid_payments_total paid_volume_30d_kobo paid_volume_lifetime_kobo paid_volume_month_kobo
payments_failed_count payments_pending_count payments_total_count payouts_30d_kobo
payouts_lifetime_kobo payouts_month_kobo payouts_pending_count payouts_pending_kobo
platform_fees_30d_kobo platform_fees_lifetime_kobo platform_fees_month_kobo refunds_30d_kobo
refunds_failed_count refunds_lifetime_kobo refunds_month_kobo refunds_pending_count
refunds_pending_kobo refunds_unknown_count risk_customers_flagged service_requests_30d
service_requests_total services_active support_cases_open support_cases_review
support_cases_urgent support_disputes_open support_disputes_total user_security_alerts
""".split()


class AuthenticatedHomeAPIClient:
    calls = []

    @classmethod
    def reset(cls):
        cls.calls.clear()

    def __init__(self, request):
        self.request = request

    def get(self, path, params=None):
        normalized = path.rstrip('/') + '/'
        type(self).calls.append(('GET', normalized, params or None))
        if normalized == '/notifications/unread-count/':
            return 200, {'unread_count': 2}, {}
        if normalized == '/notifications/':
            return 200, {'count': 2, 'results': []}, {}
        if normalized == '/profile/artisan/personal/profile/':
            return 200, {
                'business_name': 'Ayo Plumbing Works',
                'first_name': 'Ayo',
                'profile_photo': 'https://images.example.test/ayo.webp',
                'average_rating': '4.8',
                'completion_rate': 92,
                'cancellation_rate': 2,
                'profile_status': 'ACTIVE',
            }, {}
        if normalized == '/booking/':
            return 200, [], {}
        if normalized == '/services/get_artisan_services/':
            return 200, [{'id': 21, 'service_name': 'Plumbing'}], {}
        if normalized == '/services/artisan/requests/':
            return 200, {
                'count': 1,
                'results': [{
                    'id': 71,
                    'service_name': 'Plumbing',
                    'category_name': 'Home Repair',
                    'urgency': 'HIGH',
                    'description': 'Repair a leaking kitchen tap.',
                    'location': {'area': 'Ikeja', 'state': 'Lagos'},
                    'preferred_date': '2026-11-05',
                }],
            }, {}
        if normalized == '/profile/customer/personal/profile/':
            return 200, {
                'first_name': 'Ada',
                'last_name': 'Customer',
                'email': 'ada@example.test',
                'phone_number': '+2348012345678',
                'country': 'Nigeria',
                'state': 'Lagos',
                'area': 'Ikeja',
            }, {}
        if normalized == '/services/requests/':
            return 200, {'count': 3, 'results': []}, {}
        if normalized == '/manager/overview/':
            return 200, {
                'generated_at': '2026-10-12T09:30:00Z',
                'snapshot': {'status': 'SUCCEEDED', 'frequency': 'DAILY', 'timezone': 'Africa/Lagos'},
                'snapshot_schedule': {
                    'frequency': 'DAILY',
                    'timezone': 'Africa/Lagos',
                    'next_run_at': '2026-10-15T09:30:00+01:00',
                    'last_success_at': '2026-10-14T09:30:00+01:00',
                    'last_error': '',
                    'history': [{
                        'actor_name': 'Ayo Manager',
                        'created_at': '2026-10-13T09:30:00+01:00',
                        'reason': 'Align reports with weekly operations review.',
                        'before': {'frequency': 'DAILY'},
                        'after': {'frequency': 'WEEKLY'},
                    }],
                },
                'kpis': {key: 0 for key in MANAGER_KPI_KEYS},
                'activity_trend': [],
                'promotions': {
                    'active_geographic_by_type': {'INSTITUTION': 2, 'AREA': 3, 'STATE': 1},
                    'active_homepage_placements': 1,
                    'pending_paid_campaigns': {
                        'paid_waiting_for_placement': 4,
                        'awaiting_payment': 2,
                        'payment_review': 1,
                    },
                    'review_statistics': {
                        'pending_review': 5,
                        'changes_required': 2,
                        'approved': 7,
                        'rejected': 1,
                        'decisions_last_30_days': 4,
                    },
                    'upcoming_expirations_7d': 1,
                    'upcoming_expirations': [{
                        'promotion_type': 'AREA',
                        'target_label': 'Ikeja, Lagos, Nigeria',
                        'expires_at': '2026-10-14T13:00:00+01:00',
                    }],
                    'performance': {'last_30_days': {
                        'impressions': 120,
                        'profile_visits': 18,
                        'useful_rate_percent': 15.0,
                    }},
                    'inventory': [{
                        'promotion_type': 'AREA',
                        'target_label': 'Ikeja, Lagos, Nigeria',
                        'capacity': 12,
                        'active_count': 4,
                        'remaining_capacity': 8,
                        'scheduled_count': 2,
                        'queued_count': 1,
                    }],
                    'plans': [{
                        'name': 'Area placement',
                        'promotion_type': 'AREA',
                        'is_enabled': True,
                        'currency': 'NGN',
                        'price_kobo': 250000,
                        'duration_days': 14,
                        'version': 2,
                    }],
                },
            }, {}
        raise AssertionError(f'Unexpected authenticated-home API GET: {path}')


class AuthenticatedHomePresentationTests(TestCase):
    def setUp(self):
        AuthenticatedHomeAPIClient.reset()
        self.enterContext(patch('frontend.views.APIClient', AuthenticatedHomeAPIClient))
        self.enterContext(patch('frontend.context_processors.APIClient', AuthenticatedHomeAPIClient))

    def sign_in_as(self, role):
        session = self.client.session
        session['api_access'] = 'test-access-token'
        session['api_role'] = role
        session['api_user'] = {'first_name': 'Ada', 'last_name': 'Customer', 'role': role}
        session.save()

    def assert_shared_home_shell(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['is_landing_page'])
        self.assertEqual(len(response.context['hero_slides']), 6)
        content = response.content.decode()
        self.assertEqual(content.count('data-carousel-slide'), 6)
        self.assertNotIn('data-hero-controls', content)
        self.assertNotIn('data-hero-previous', content)
        self.assertNotIn('data-hero-next', content)
        self.assertNotIn('data-hero-pause', content)
        self.assertIn('authenticated-home-page', content)
        self.assertIn('authenticated-home-hero', content)
        if response.context['nav_role'] == 'artisan' or response.context.get('platform_manager'):
            self.assertIn('Log Out', content)
        else:
            self.assertIn('Log out', content)
        self.assertIn('data-confirm-logout', content)
        self.assertIn('csrfmiddlewaretoken', content)
        self.assertIn(f'data-tour-role="{response.context["nav_role"]}"', content)
        self.assertIn('id="site-onboarding-tour"', content)
        self.assertIn('/static/js/pages/landing.js', content)
        if response.context['nav_role'] in {'customer', 'artisan'}:
            categories_url = reverse('categories')
            self.assertIn(f'href="{categories_url}"', content)

    def test_artisan_home_keeps_dashboard_data_and_uses_landing_carousel(self):
        self.sign_in_as('artisan')
        with patch('frontend.views._support_capabilities', return_value={}):
            response = self.client.get(reverse('home'))

        self.assert_shared_home_shell(response)
        self.assertContains(response, 'Welcome back, Ayo Plumbing Works.')
        self.assertContains(response, 'View matching requests')
        self.assertContains(response, 'Matching requests')
        self.assertContains(response, 'Repair a leaking kitchen tap.')
        self.assertContains(response, 'Ayo Plumbing Works')
        self.assertContains(response, 'class="nav-account-avatar"')
        self.assertContains(response, 'src="https://images.example.test/ayo.webp"')
        content = response.content.decode()
        nav_start = content.index('<nav id="landing-navigation"')
        nav = content[nav_start:content.index('</nav>', nav_start)]
        ordered_items = ['Dashboard', 'Account', 'Artisan Profile', 'Verification', 'Payout Account', 'Log Out', 'My Services', 'Customer requests', 'Find artisans', 'My service requests', 'Bookings', 'Messages', 'Notifications', 'Support']
        positions = [nav.index(item) for item in ordered_items]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(nav.count(f'href="{reverse("artisan-services")}"'), 1)
        self.assertLess(content.index('Profile Health'), content.index('Matched to your services'))
        self.assertTrue(any(call[1] == '/services/artisan/requests/' for call in AuthenticatedHomeAPIClient.calls))

    def test_customer_home_renders_profile_activity_instead_of_redirecting_away(self):
        self.sign_in_as('customer')
        with patch('frontend.views._support_capabilities', return_value={}):
            response = self.client.get(reverse('home'))

        self.assert_shared_home_shell(response)
        self.assertContains(response, 'Welcome back, Ada Customer.')
        self.assertContains(response, 'Personal details')
        self.assertContains(response, 'Notifications')
        self.assertContains(response, 'Requests')
        self.assertEqual(response.context['role'], 'customer')
        self.assertTrue(response.context['home_dashboard'])

    def test_manager_home_keeps_analytics_unloaded_until_an_authorized_reveal(self):
        self.sign_in_as('staff')
        with patch('frontend.views._support_capabilities', return_value={'is_superuser': True, 'can_review_promotions': True}):
            response = self.client.get(reverse('home'))

        self.assert_shared_home_shell(response)
        self.assertContains(response, 'Manager overview')
        self.assertContains(response, 'Open support desk')
        self.assertContains(response, 'Platform analytics are protected by default')
        self.assertContains(response, 'Analytics remain unloaded until you request them')
        self.assertContains(response, 'Reveal values')
        self.assertContains(response, reverse('frontend-manager-values-reveal'))
        self.assertNotContains(response, 'Marketplace and financial headline metrics')
        self.assertNotContains(response, 'Snapshot frequency')
        self.assertNotContains(response, '₦2,500.00')
        self.assertNotContains(response, 'Ayo Manager')
        self.assertNotContains(response, 'data-manager-sensitive-value')
        self.assertEqual(response.context['manager_analytics_ready'], False)
        self.assertFalse(response.context['manager_values_revealed'])
        self.assertFalse(any(call[1] == '/manager/overview/' for call in AuthenticatedHomeAPIClient.calls))
        self.assertEqual(response.headers['Cache-Control'], 'no-store, no-cache, must-revalidate, private')
        self.assertEqual(response.content.decode().count('class="support-operation-shortcut"'), 1)
        content = response.content.decode()
        nav_start = content.index('<nav id="landing-navigation"')
        nav = content[nav_start:content.index('</nav>', nav_start)]
        ordered_items = ['Manager Overview', 'Support Operations', 'Case Queue', 'Refunds', 'Support Team', 'Log Out']
        positions = [nav.index(item) for item in ordered_items]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn('Find artisans', nav)
        self.assertNotIn('Artisan Profile', nav)
        self.assertNotIn('data-onboarding-open', nav)
        self.assertIn('data-tour-auto="false"', content)

    def test_manager_reveal_is_one_use_server_authorized_and_not_cached(self):
        self.sign_in_as('staff')
        target = reverse('home')
        with patch('frontend.views._support_capabilities', return_value={'is_superuser': True, 'can_review_promotions': True}):
            reveal_response = self.client.post(reverse('frontend-manager-values-reveal'), {
                'scope': 'manager',
                'next': target,
            })
        self.assertEqual(reveal_response.status_code, 302)
        self.assertEqual(reveal_response['Location'], target)

        with patch('frontend.views._support_capabilities', return_value={'is_superuser': True, 'can_review_promotions': True}):
            response = self.client.get(target)

        self.assert_shared_home_shell(response)
        self.assertContains(response, 'Marketplace and financial headline metrics')
        self.assertContains(response, 'Snapshot frequency')
        self.assertContains(response, 'Recent schedule changes')
        self.assertContains(response, 'Align reports with weekly operations review.')
        self.assertContains(response, 'Promotions &amp; placements')
        self.assertContains(response, 'Paid campaigns awaiting placement')
        self.assertContains(response, 'Review applications')
        self.assertContains(response, 'Campaign settings')
        self.assertContains(response, 'Upcoming expirations')
        self.assertContains(response, 'Target inventory &amp; capacity')
        self.assertContains(response, 'Configured plans')
        self.assertContains(response, '₦2,500.00')
        self.assertContains(response, 'data-manager-privacy-hide')
        self.assertContains(response, 'manager-privacy.js')
        self.assertNotContains(response, 'data-manager-sensitive-value')
        self.assertEqual(response.headers['Cache-Control'], 'no-store, no-cache, must-revalidate, private')
        self.assertTrue(response.context['manager_analytics_ready'])
        self.assertTrue(response.context['manager_values_revealed'])
        self.assertEqual(sum(call[1] == '/manager/overview/' for call in AuthenticatedHomeAPIClient.calls), 1)

        # A normal page reload consumes no reveal token and does not request the report again.
        with patch('frontend.views._support_capabilities', return_value={'is_superuser': True, 'can_review_promotions': True}):
            masked_again = self.client.get(target)
        self.assertContains(masked_again, 'Platform analytics are protected by default')
        self.assertNotContains(masked_again, '₦2,500.00')
        self.assertFalse(masked_again.context['manager_values_revealed'])
        self.assertEqual(sum(call[1] == '/manager/overview/' for call in AuthenticatedHomeAPIClient.calls), 1)

    def test_support_staff_cannot_request_manager_analytics_reveal(self):
        self.sign_in_as('staff')
        capabilities = {'is_support_staff': True, 'is_superuser': False, 'can_review_promotions': True}
        with patch('frontend.views._support_capabilities', return_value=capabilities):
            response = self.client.post(reverse('frontend-manager-values-reveal'), {
                'scope': 'manager',
                'next': reverse('home'),
            })
        self.assertEqual(response.status_code, 403)
        self.assertNotIn('manager_values_reveal_once', self.client.session)

    def test_manager_snapshot_schedule_form_forwards_frequency_and_audit_reason(self):
        self.sign_in_as('staff')
        with (
            patch('frontend.views._support_capabilities', return_value={'is_superuser': True}),
            patch('frontend.views.APIClient') as api_client,
        ):
            api_client.return_value.patch.return_value = (200, {'frequency': 'WEEKLY'}, {})
            response = self.client.post(reverse('frontend-manager-snapshot-schedule'), {
                'frequency': 'WEEKLY',
                'reason': 'Align reports with weekly operations review.',
            })

        self.assertEqual(response.status_code, 302)
        api_client.return_value.patch.assert_called_once_with(
            '/manager/snapshot-schedule/',
            data={
                'frequency': 'WEEKLY',
                'reason': 'Align reports with weekly operations review.',
            },
        )

    def test_support_home_keeps_permissioned_workspace_and_uses_landing_carousel(self):
        self.sign_in_as('staff')
        capabilities = {
            'is_support_staff': True,
            'is_superuser': False,
            'can_view_refunds': True,
            'can_manage_staff': True,
        }
        support_data = {
            'support_capabilities': capabilities,
            'support_dashboard_ready': True,
            'support_cases': [],
            'support_refunds': [],
            'support_case_total': 0,
            'support_refund_total': 0,
            'open_case_count': 0,
            'review_case_count': 0,
            'urgent_case_count': 0,
            'dispute_case_count': 0,
            'requested_refund_count': 0,
            'approved_refund_count': 0,
            'processing_refund_count': 0,
            'processing_unknown_refund_count': 0,
            'case_status_metrics': [],
            'refund_status_metrics': [],
        }
        with (
            patch('frontend.views._support_capabilities', return_value=capabilities),
            patch('frontend.views._support_dashboard_data', return_value=support_data),
        ):
            response = self.client.get(reverse('home'))

        self.assert_shared_home_shell(response)
        self.assertContains(response, 'Support operations')
        self.assertContains(response, 'Open case queue')
        self.assertContains(response, 'Refund operations')
        self.assertContains(response, 'Support team')
        self.assertContains(response, 'Live support queue metrics')
        self.assertEqual(response.content.decode().count('class="support-operation-shortcut"'), 1)
