import time
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse


CAPABILITIES_MANAGER = {
    'is_support_staff': True,
    'is_superuser': True,
    'can_review_promotions': True,
    'roles': [],
}


class PromotionManagementPageTests(TestCase):
    campaign_id = '797c601a-2a2e-437f-90a9-04373aac13bb'
    plan_id = '95d4690d-61d6-4e22-8815-52d2d9a11f38'
    inventory_id = '9bfcc5d3-d07e-4818-9957-0d97dcae617c'

    def setUp(self):
        session = self.client.session
        session['api_access'] = 'promotion-manager-test-token'
        session['api_role'] = 'staff'
        session['api_user'] = {'id': 9, 'role': 'staff', 'first_name': 'Ayo'}
        session['notif_unread_checked_at'] = time.time()
        session['notif_unread'] = 0
        session.save()

    @classmethod
    def campaign(cls):
        return {
            'id': cls.campaign_id,
            'artisan_name': 'Ada Artisan',
            'artisan_email': 'ada@example.test',
            'business_name': 'Ada Repairs',
            'promotion_type': 'AREA',
            'target_label': 'Ikeja, Lagos, Nigeria',
            'plan_name_snapshot': 'Area Promotion',
            'price': '2000.00',
            'currency': 'NGN',
            'status': 'SUSPENDED',
            'status_label': 'Suspended pending review',
            'payment_reference': 'PROMO-TEST-001',
            'payment_verified_at': '2026-10-14T08:15:00Z',
            'scheduled_start_at': None,
            'started_at': None,
            'expires_at': None,
            'paused_at': '2026-10-14T09:00:00Z',
            'last_action_reason': 'Pending evidence review.',
            'impressions': 12,
            'profile_clicks': 2,
            'profile_visits': 2,
            'profile_visit_rate_percent': 16.67,
            'performance_data_available': True,
            'enquiries': 1,
            'support_cases': [{
                'id': 42,
                'reference': 'CASE-PROMO-001',
                'subject': 'Sponsored listing concern',
                'status': 'UNDER_REVIEW',
                'created_at': '2026-10-14T08:30:00Z',
            }],
            'actions': [{
                'id': '33333333-3333-4333-8333-333333333333',
                'action': 'SUSPENDED',
                'action_label': 'Suspended',
                'status_before': 'ACTIVE',
                'status_after': 'SUSPENDED',
                'actor_name': 'Mina Supervisor',
                'created_at': '2026-10-14T09:00:00Z',
                'reason': 'Temporarily suspend while support reviews the evidence.',
                'evidence_summary': 'Evidence has not confirmed a policy violation.',
                'support_case_id': 42,
                'metadata': {},
            }],
        }

    @classmethod
    def plan(cls):
        return {
            'id': cls.plan_id,
            'promotion_type': 'AREA',
            'name': 'Area Promotion',
            'is_enabled': True,
            'price': '2500.00',
            'price_kobo': 250000,
            'currency': 'NGN',
            'duration_days': 14,
            'refund_policy': 'PRO_RATA',
            'terms_text': 'Customer-facing promotion terms are maintained on the manager-controlled plan.',
            'version': 3,
            'updated_at': '2026-10-13T12:00:00Z',
            'updated_by_name': 'Ayo Manager',
        }

    @classmethod
    def inventory(cls):
        return {
            'id': cls.inventory_id,
            'promotion_type': 'AREA',
            'target_key': 'AREA:1',
            'target_label': 'Ikeja, Lagos, Nigeria',
            'capacity': 12,
            'active_count': 4,
            'remaining_capacity': 8,
            'scheduled_count': 2,
            'queued_count': 1,
            'updated_at': '2026-10-13T12:00:00Z',
        }

    @classmethod
    def audit_event(cls):
        return {
            'id': '8c3c5e3b-60c1-4b65-a04b-6ed3c12b0c7d',
            'action': 'PROMOTION_PLAN_CONFIGURED',
            'resource_type': 'PromotionPlan',
            'resource_id': cls.plan_id,
            'actor_name': 'Ayo Manager',
            'created_at': '2026-10-14T10:00:00Z',
            'reason': 'Updated the plan after the pricing review.',
            'details': {
                'before': {
                    'name': 'Area Promotion',
                    'price_kobo': 200000,
                    'duration_days': 7,
                    'is_enabled': True,
                    'refund_policy': 'NONE',
                    'terms_text': 'Previous customer-facing promotion terms.',
                },
                'after': {
                    'name': 'Area Promotion',
                    'price_kobo': 250000,
                    'duration_days': 14,
                    'is_enabled': True,
                    'refund_policy': 'PRO_RATA',
                    'terms_text': 'Revised customer-facing promotion terms.',
                },
            },
        }

    def test_support_navigation_remains_toggle_accessible_across_761_to_960px(self):
        frontend_root = Path(__file__).resolve().parents[2]
        site_css = (frontend_root / 'static/css/site.css').read_text()
        home_css = (frontend_root / 'static/css/authenticated-home.css').read_text()
        navbar = (frontend_root / 'templates/partials/navbar.html').read_text()

        self.assertIn('data-menu-toggle', navbar)
        self.assertIn('data-landing-menu', navbar)
        self.assertIn('@media(max-width:960px)', site_css)
        self.assertIn('.site-nav-ready .menu-toggle{display:inline-flex}', site_css)
        self.assertIn('.site-nav-ready .nav.open{display:flex}', site_css)
        self.assertIn('@media (max-width: 1080px)', home_css)
        self.assertIn('.authenticated-home-page .landing-menu-toggle { display: inline-flex; }', home_css)
        self.assertIn('.authenticated-home-page.landing-nav-ready .landing-nav--authenticated.is-open { display: grid; }', home_css)

    def test_manager_values_are_not_embedded_until_an_explicit_authorized_reveal(self):
        with (
            patch('frontend.views._support_capabilities', return_value=CAPABILITIES_MANAGER),
            patch('frontend.views.APIClient') as api_client,
        ):
            api_client.return_value.get.return_value = (200, [self.campaign()], {})
            response = self.client.get(reverse('support-promotion-campaign-management'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'support/promotion_campaign_management.html')
        for text in (
            'Prices, terms &amp; target capacity',
            'Manager-controlled plan settings, capacity figures, and audit details are not loaded',
            'Reveal values',
            'Review a support case and manage this campaign',
            'Immutable campaign history',
            'Mina Supervisor',
            'Temporarily suspend while support reviews the evidence.',
            'Evidence has not confirmed a policy violation.',
            'CASE-PROMO-001',
        ):
            self.assertContains(response, text)
        for private_value in (
            'ada@example.test', '2000.00', 'PROMO-TEST-001', '2500.00',
            'Previous customer-facing promotion terms.', 'Revised customer-facing promotion terms.',
            'Updated the plan after the pricing review.', 'Ayo Manager',
        ):
            self.assertNotContains(response, private_value)
        self.assertContains(response, 'Privileged promotion values are hidden by default.')
        self.assertContains(response, reverse('frontend-manager-values-reveal'))
        self.assertNotContains(response, 'data-manager-sensitive-value')
        self.assertNotContains(response, 'data-manager-real-input')
        self.assertContains(response, 'manager-privacy.js')
        self.assertEqual(response.headers['Cache-Control'], 'no-store, no-cache, must-revalidate, private')
        self.assertEqual(
            [call.args[0] for call in api_client.return_value.get.call_args_list],
            ['/promotions/management/campaigns/'],
        )

    def test_authorized_promotion_reveal_loads_private_details_for_one_request(self):
        target = reverse('support-promotion-campaign-management')
        with patch('frontend.views._support_capabilities', return_value=CAPABILITIES_MANAGER):
            reveal_response = self.client.post(reverse('frontend-manager-values-reveal'), {
                'scope': 'promotion',
                'next': target,
            })
        self.assertEqual(reveal_response.status_code, 302)
        self.assertEqual(reveal_response['Location'], target)

        with (
            patch('frontend.views._support_capabilities', return_value=CAPABILITIES_MANAGER),
            patch('frontend.views.APIClient') as api_client,
        ):
            api_client.return_value.get.side_effect = [
                (200, [self.campaign()], {}),
                (200, [self.plan()], {}),
                (200, [self.inventory()], {}),
                (200, {'count': 1, 'results': [self.audit_event()]}, {}),
            ]
            response = self.client.get(target)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['promotion_values_revealed'])
        self.assertTrue(response.context['manager_values_revealed'])
        for text in (
            'Ayo Manager',
            'Updated the plan after the pricing review.',
            'View customer-facing terms before and after',
            'Previous customer-facing promotion terms.',
            'Revised customer-facing promotion terms.',
            'Review a support case and manage this campaign',
            'Mina Supervisor',
            'Temporarily suspend while support reviews the evidence.',
            'Evidence has not confirmed a policy violation.',
            'CASE-PROMO-001',
            'ada@example.test',
            'PROMO-TEST-001',
        ):
            self.assertContains(response, text)
        self.assertNotContains(response, 'data-manager-sensitive-value')
        self.assertContains(response, 'data-manager-privacy-hide')
        self.assertContains(response, 'value="2500.00"')
        self.assertContains(response, 'value="12"')
        self.assertEqual(response.headers['Cache-Control'], 'no-store, no-cache, must-revalidate, private')
        self.assertEqual(
            [call.args[0] for call in api_client.return_value.get.call_args_list],
            [
                '/promotions/management/campaigns/',
                '/promotions/management/plans/',
                '/promotions/management/inventories/',
                '/promotions/management/audit-events/',
            ],
        )

    def test_support_agent_gets_campaign_operations_but_not_global_prices_or_capacity(self):
        agent_capabilities = {
            'is_support_staff': True,
            'is_superuser': False,
            'can_review_promotions': True,
            'roles': ['CUSTOMER_SUPPORT_AGENT'],
        }
        with (
            patch('frontend.views._support_capabilities', return_value=agent_capabilities),
            patch('frontend.views.APIClient') as api_client,
        ):
            api_client.return_value.get.return_value = (200, [], {})
            response = self.client.get(reverse('support-promotion-campaign-management'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Campaigns')
        self.assertNotContains(response, 'Prices, terms &amp; durations')
        self.assertNotContains(response, 'Target capacity')
        self.assertNotContains(response, 'promotion-inventory-capacity')
        self.assertEqual(api_client.return_value.get.call_count, 1)

    def test_manager_plan_form_forwards_the_reason_to_the_authorized_api(self):
        with (
            patch('frontend.views._support_capabilities', return_value=CAPABILITIES_MANAGER),
            patch('frontend.views.APIClient') as api_client,
        ):
            api_client.return_value.patch.return_value = (200, self.plan(), {})
            response = self.client.post(reverse('support-promotion-campaign-management'), {
                'action': 'plan',
                'plan_id': self.plan_id,
                'name': 'Area Promotion',
                'price': '2500',
                'duration_days': '14',
                'is_enabled': 'on',
                'refund_policy': 'PRO_RATA',
                'terms_text': 'Customer-facing promotion terms are maintained on the manager-controlled plan.',
                'reason': 'Approved after the quarterly pricing review.',
                'idempotency_key': 'promotion-plan-change-key',
            })

        self.assertEqual(response.status_code, 302)
        api_client.return_value.patch.assert_called_once()
        path, = api_client.return_value.patch.call_args.args
        payload = api_client.return_value.patch.call_args.kwargs['data']
        self.assertEqual(path, f'/promotions/management/plans/{self.plan_id}/')
        self.assertEqual(payload['price'], '2500')
        self.assertEqual(payload['reason'], 'Approved after the quarterly pricing review.')
        self.assertEqual(api_client.return_value.patch.call_args.kwargs['idempotency_key'], 'promotion-plan-change-key')

    def test_capacity_form_forwards_the_reason_to_the_authorized_api(self):
        with (
            patch('frontend.views._support_capabilities', return_value=CAPABILITIES_MANAGER),
            patch('frontend.views.APIClient') as api_client,
        ):
            api_client.return_value.patch.return_value = (200, self.inventory(), {})
            response = self.client.post(reverse('support-promotion-campaign-management'), {
                'action': 'capacity',
                'inventory_id': self.inventory_id,
                'capacity': '16',
                'reason': 'Increase the target capacity after the inventory review.',
                'idempotency_key': 'promotion-capacity-change-key',
            })

        self.assertEqual(response.status_code, 302)
        api_client.return_value.patch.assert_called_once()
        path, = api_client.return_value.patch.call_args.args
        payload = api_client.return_value.patch.call_args.kwargs['data']
        self.assertEqual(path, f'/promotions/management/inventories/{self.inventory_id}/capacity/')
        self.assertEqual(payload, {
            'capacity': '16',
            'reason': 'Increase the target capacity after the inventory review.',
        })
        self.assertEqual(api_client.return_value.patch.call_args.kwargs['idempotency_key'], 'promotion-capacity-change-key')
