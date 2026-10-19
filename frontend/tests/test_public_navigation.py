from urllib.parse import urlencode
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from frontend.api import APIError


ARTISAN_ID = '9b7f7234-7339-4c83-9868-7a0d83f81399'
LOCATION_ID = 'f0250929-a7a9-4f07-82ee-47bf45b139d9'
CONVERSATION_ID = 'f315d2c2-f71a-4b6d-9f81-712481d095f5'


class PublicNavigationAPIClient:
    calls = []
    catalog_unavailable = False
    profile_complete = False
    homepage_promotions = []
    market_picks = []

    def __init__(self, request):
        self.request = request

    def clear_session(self):
        for key in (
            'api_access', 'api_refresh', 'api_user', 'api_role',
            'reset_token', 'reset_email', 'staff_reset_token', 'staff_reset_email',
            'staff_security_gate', 'staff_security_email', 'manager_values_reveal_once',
            'staff_mfa_challenge_id', 'staff_mfa_masked_email', 'staff_mfa_resend_after',
        ):
            self.request.session.pop(key, None)
        self.request.session.modified = True

    @classmethod
    def reset(cls):
        cls.calls.clear()
        cls.catalog_unavailable = False
        cls.profile_complete = False
        cls.homepage_promotions = []
        cls.market_picks = []

    @staticmethod
    def _artisan(artisan_id, *, name, business_name, service_name, category_name, state='Lagos', area='Ikeja'):
        return {
            'id': artisan_id,
            'name': name,
            'business_name': business_name,
            'bio': f'{service_name} services for homes and businesses.',
            'years_experience': 7,
            'country': 'Nigeria',
            'state': state,
            'area': area,
            'profile_photo': None,
            'average_rating': '4.80',
            'completion_rate': 92.0,
            'cancellation_rate': 2.0,
            'verification_status': 'VERIFIED',
            'services': [{
                'service_id': 17,
                'service_name': service_name,
                'category_name': category_name,
                'location': {'country': 'Nigeria', 'state': state, 'area': area},
                'starting_price': '15000.00',
            }],
        }

    def get(self, path, params=None):
        self.calls.append(('GET', path, params or None))
        normalized = path.rstrip('/') + '/'
        if normalized == '/promotions/homepage/':
            return 200, type(self).homepage_promotions, {}
        if normalized == '/promotions/market-picks/':
            return 200, type(self).market_picks, {}
        if normalized == '/promotions/discovery/':
            return 200, {'count': 0, 'display_limit': 3, 'results': []}, {}
        if normalized == '/services/categories/':
            if self.catalog_unavailable:
                raise APIError(503, {'detail': 'Category catalogue temporarily unavailable.'})
            return 200, [
                {'id': 1, 'name': 'Home Repair'},
                {'id': 2, 'name': 'Tailoring'},
            ], {}
        if normalized == '/services/service_cat/':
            if self.catalog_unavailable:
                raise APIError(503, {'detail': 'Service catalogue temporarily unavailable.'})
            return 200, [
                {'id': 11, 'name': 'Plumbing', 'category_name': 'Home Repair', 'is_active': True, 'description': 'Repairs and installation.'},
                {'id': 12, 'name': 'Garment Alterations', 'category_name': 'Tailoring', 'is_active': True, 'description': 'Clothing adjustments.'},
            ], {}
        if normalized == '/profile/artisan/details/':
            items = [
                self._artisan(
                    ARTISAN_ID,
                    name='Ayo Artisan',
                    business_name='Ayo Plumbing Works',
                    service_name='Plumbing',
                    category_name='Home Repair',
                ),
                self._artisan(
                    'ea4b70f1-c2bc-4b3c-bd39-0439e8306a16',
                    name='Bisi Tailor',
                    business_name='Bisi Stitch House',
                    service_name='Garment Alterations',
                    category_name='Tailoring',
                    state='Ogun',
                    area='Abeokuta',
                ),
            ]
            query = params or {}
            if query.get('q'):
                needle = query['q'].casefold()
                def search_text(item):
                    values = [item['name'], item['business_name'], item['bio'], item['state'], item['area']]
                    for offer in item.get('services', []):
                        values.extend((offer.get('service_name', ''), offer.get('category_name', '')))
                    return ' '.join(values).casefold()
                items = [item for item in items if needle in search_text(item)]
            for field in ('country', 'state', 'area'):
                if query.get(field):
                    needle = query[field].casefold()
                    items = [item for item in items if needle in str(item.get(field) or '').casefold() or any(offer.get('location') and needle in str(offer['location'].get(field) or '').casefold() for offer in item.get('services', []))]
            if query.get('category_name'):
                needle = query['category_name'].casefold()
                items = [item for item in items if any(needle == str(offer.get('category_name') or '').casefold() for offer in item.get('services', []))]
            if query.get('service_name'):
                needle = query['service_name'].casefold()
                items = [item for item in items if any(offer['service_name'].casefold() == needle for offer in item.get('services', []))]
            total = len(items)
            limit = int(query.get('limit', 20))
            start = int(query.get('offset', 0))
            results = items[start:start + limit]
            return 200, {
                'count': total,
                'next': None,
                'previous': None,
                'results': results,
            }, {}
        if normalized == f'/profile/artisan/details/{ARTISAN_ID}/':
            return 200, self._artisan(
                ARTISAN_ID,
                name='Ayo Artisan',
                business_name='Ayo Plumbing Works',
                service_name='Plumbing',
                category_name='Home Repair',
            ), {}
        if normalized == '/profile/customer/personal/profile/':
            if self.profile_complete:
                return 200, {
                    'first_name': 'Ada',
                    'last_name': 'Customer',
                    'phone_number': '+2348012345678',
                    'country': 'Nigeria',
                    'state': 'Lagos',
                    'area': 'Ikeja',
                }, {}
            return 200, {
                'first_name': '',
                'last_name': '',
                'phone_number': '',
                'country': '',
                'state': '',
                'area': '',
            }, {}
        if normalized == '/services/locations/':
            return 200, [{
                'id': LOCATION_ID,
                'country': 'Nigeria',
                'state': 'Lagos',
                'area': 'Ikeja',
            }], {}
        if normalized == '/services/institutions/':
            return 200, [], {}
        if normalized == '/services/requests/':
            return 200, {'count': 0, 'next': None, 'results': []}, {}
        if normalized == '/notifications/':
            return 200, {'count': 0, 'results': []}, {}
        if normalized == '/notifications/unread-count/':
            return 200, {'unread_count': 0}, {}
        raise AssertionError(f'Unexpected fake API GET: {path}')

    def post(self, path, data=None, files=None, idempotency_key=None):
        self.calls.append(('POST', path, data, idempotency_key))
        normalized = path.rstrip('/') + '/'
        if normalized == '/login/':
            return 200, {
                'access': 'test-access-token',
                'refresh': 'test-refresh-token',
                'user': {'email': 'ada@example.test', 'role': 'customer'},
            }, {}
        if normalized == f'/conversations/direct/artisan/{ARTISAN_ID}/':
            return 201, {'id': CONVERSATION_ID}, {}
        raise AssertionError(f'Unexpected fake API POST: {path}')

    def patch(self, path, data=None, files=None, idempotency_key=None):
        self.calls.append(('PATCH', path, data))
        if path.rstrip('/') == '/profile/customer/personal/profile':
            type(self).profile_complete = True
            return 200, {
                'first_name': 'Ada',
                'last_name': 'Customer',
                'phone_number': '+2348012345678',
                'country': 'Nigeria',
                'state': 'Lagos',
                'area': 'Ikeja',
            }, {}
        raise AssertionError(f'Unexpected fake API PATCH: {path}')


class PublicNavigationTests(TestCase):
    def setUp(self):
        PublicNavigationAPIClient.reset()
        self.enterContext(patch('frontend.views.APIClient', PublicNavigationAPIClient))
        self.enterContext(patch('frontend.context_processors.APIClient', PublicNavigationAPIClient))

    def test_homepage_restores_six_static_slides_and_visual_themes(self):
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertContains(response, 'Carpentry, in focus.')
        self.assertContains(response, 'Craft, in focus.')
        self.assertContains(response, 'Illustrative stock photography')
        self.assertContains(response, 'Browse artisans')
        self.assertContains(response, 'Browse services')
        self.assertContains(response, 'Visual themes')
        self.assertContains(response, 'Browse live categories')
        categories_url = reverse('categories')
        self.assertContains(response, f'href="{categories_url}"')
        self.assertEqual(content.count('data-carousel-slide'), 6)
        self.assertNotIn('data-hero-controls', content)
        self.assertNotIn('data-hero-previous', content)
        self.assertNotIn('data-hero-next', content)
        self.assertNotIn('data-hero-pause', content)
        self.assertEqual(content.count('class="landing-theme-card__image"'), 6)
        for trade in ('carpentry', 'electrical', 'electronics', 'tailoring', 'painting', 'plumbing'):
            self.assertIn(f'trade-{trade}-640.webp', content)
            self.assertIn(f'trade-{trade}-1440.webp', content)
        self.assertEqual(len(response.context['visual_themes']), 6)
        self.assertFalse(response.context['authenticated'])
        self.assertEqual(PublicNavigationAPIClient.calls, [('GET', '/promotions/homepage/', None), ('GET', '/promotions/market-picks/', None)])
        self.assertNotContains(response, 'Live service catalogue')
        self.assertNotContains(response, 'active service records')

    def test_anonymous_homepage_displays_paid_promotions_separately_from_editorial_themes(self):
        PublicNavigationAPIClient.homepage_promotions = [{
            'campaign_id': '797c601a-2a2e-437f-90a9-04373aac13bb',
            'artisan_id': ARTISAN_ID,
            'name': 'Ayo Artisan',
            'business_name': 'Ayo Plumbing Works',
            'profile_photo_url': '',
            'average_rating': '4.80',
            'review_count': 12,
            'artisan_url': f'/discover/artisans/{ARTISAN_ID}/',
            'promotion_type': 'HOMEPAGE',
            'description': 'Careful repairs for homes and businesses.',
            'services': [{'service_name': 'Plumbing'}],
        }]
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['authenticated'])
        self.assertContains(response, 'Sponsored · Homepage Feature')
        self.assertContains(response, 'Ayo Plumbing Works')
        self.assertContains(response, 'Report this sponsored placement')
        self.assertContains(response, f'promotion_campaign={PublicNavigationAPIClient.homepage_promotions[0]["campaign_id"]}')
        self.assertEqual(PublicNavigationAPIClient.calls, [('GET', '/promotions/homepage/', None), ('GET', '/promotions/market-picks/', None)])

    def test_anonymous_homepage_keeps_editorial_market_picks_separate_from_paid_features(self):
        PublicNavigationAPIClient.homepage_promotions = [{
            'campaign_id': '797c601a-2a2e-437f-90a9-04373aac13bb',
            'artisan_id': ARTISAN_ID,
            'name': 'Ayo Artisan',
            'business_name': 'Ayo Plumbing Works',
            'profile_photo_url': '',
            'average_rating': '4.80',
            'review_count': 12,
            'artisan_url': f'/discover/artisans/{ARTISAN_ID}/',
            'promotion_type': 'HOMEPAGE',
            'description': 'Careful repairs for homes and businesses.',
            'services': [{'service_name': 'Plumbing'}],
        }]
        PublicNavigationAPIClient.market_picks = [{
            'id': '4be601b2-ad55-4d78-8b83-eed0dcdca189',
            'artisan_id': '13980c84-2e79-42cc-bb28-8b6a679c16bc',
            'name': 'Bola Maker',
            'business_name': 'Bola Wood Studio',
            'description': 'Thoughtful woodwork with careful finishing.',
            'profile_photo_url': '',
            'average_rating': '4.70',
            'review_count': 6,
            'main_service': 'Furniture repair',
            'services': [{'service_name': 'Furniture repair'}],
            'artisan_url': '/discover/artisans/13980c84-2e79-42cc-bb28-8b6a679c16bc/',
            'placement_type': 'ARTISAN_MARKET_PICK',
        }]
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Editorial · Platform-selected')
        self.assertContains(response, 'Market Pick')
        self.assertContains(response, 'Sponsored · Homepage Feature')
        self.assertContains(response, 'Ayo Plumbing Works')
        self.assertContains(response, 'Bola Wood Studio')
        content = response.content.decode()
        self.assertLess(content.index('artisan-market-picks'), content.index('featured-artisans'))

    def test_category_and_service_catalogue_pages_are_public_and_filterable(self):
        categories = self.client.get(reverse('categories'))
        self.assertEqual(categories.status_code, 200)
        self.assertContains(categories, 'Home Repair')
        self.assertContains(categories, 'Find artisans')
        self.assertRegex(categories.content.decode(), r'category_name=Home(?:\+|%20)Repair')

        services = self.client.get(reverse('services'), {'category_name': 'Home Repair'})
        self.assertEqual(services.status_code, 200)
        self.assertContains(services, 'Plumbing')
        self.assertContains(services, 'Find artisans')
        self.assertContains(services, 'All service categories')
        self.assertContains(services, 'option value="Home Repair" selected')
        self.assertContains(services, 'option value="Tailoring"')
        self.assertContains(services, 'id="service-category-filter"')
        service_call = next(
            call for call in PublicNavigationAPIClient.calls
            if call[0] == 'GET' and call[1] == '/services/service_cat/'
            and call[2] == {'category_name': 'Home Repair'}
        )
        self.assertEqual(service_call[2], {'category_name': 'Home Repair'})

    def test_anonymous_artisan_search_and_filters_render_marketplace_results(self):
        response = self.client.get(reverse('artisans'), {
            'q': 'plumbing',
            'category_name': 'Home Repair',
            'service_name': 'Plumbing',
            'state': 'Lagos',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ayo Plumbing Works')
        self.assertNotContains(response, 'Bisi Stitch House')
        self.assertContains(response, 'Home Repair')
        self.assertTrue(response.context['has_active_filters'])
        self.assertFalse(response.context['authenticated'])

    def test_public_artisan_profile_displays_intended_information_and_preserves_action_return(self):
        profile_url = reverse('artisan-detail', kwargs={'pk': ARTISAN_ID})
        query = 'source=homepage&term=plumbing'
        response = self.client.get(f'{profile_url}?{query}')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ayo Plumbing Works')
        self.assertContains(response, 'Ikeja, Lagos, Nigeria')
        self.assertContains(response, 'Plumbing')
        self.assertContains(response, 'Message Artisan')
        self.assertContains(response, 'Sign in to request Plumbing')
        self.assertNotContains(response, 'account_balance')
        self.assertNotContains(response, 'payout_account')
        self.assertIn(f'value="{profile_url}?source=homepage&amp;term=plumbing"', response.content.decode())

        return_to = f'{profile_url}?{query}'
        response = self.client.post(reverse('start-direct-conversation', kwargs={'pk': ARTISAN_ID}), {
            'next': return_to,
            'initial_message': 'Please help me repair a leaking tap.',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response['Location'],
            f"{reverse('login')}?{urlencode({'next': return_to})}",
        )
        pending = self.client.session['pending_protected_action']
        self.assertEqual(pending['return_to'], return_to)
        self.assertEqual(pending['initial_message'], 'Please help me repair a leaking tap.')
        self.assertFalse(any(call[0] == 'POST' for call in PublicNavigationAPIClient.calls))

    def test_pending_action_survives_login_and_required_profile_completion(self):
        profile_url = reverse('artisan-detail', kwargs={'pk': ARTISAN_ID})
        return_to = f'{profile_url}?source=homepage'
        guest_response = self.client.post(reverse('start-direct-conversation', kwargs={'pk': ARTISAN_ID}), {
            'next': return_to,
            'initial_message': 'Please help me repair a leaking tap.',
        })
        self.assertEqual(guest_response.status_code, 302)

        login_response = self.client.post(reverse('login'), {
            'email': 'ada@example.test',
            'password': 'not-a-real-password',
            'next': return_to,
        })
        completion_url = f"{reverse('customer-profile')}?{urlencode({'next': return_to})}"
        self.assertEqual(login_response.status_code, 302)
        self.assertEqual(login_response['Location'], completion_url)

        completion_page = self.client.get(completion_url)
        self.assertEqual(completion_page.status_code, 200)
        self.assertTrue(completion_page.context['profile_completion_required'])
        self.assertTrue(completion_page.context['form'].fields['phone_number'].required)
        self.assertIn(f'value="{return_to}"', completion_page.content.decode())

        response = self.client.post(reverse('customer-profile'), {
            'next': return_to,
            'first_name': 'Ada',
            'last_name': 'Customer',
            'phone_number': '+2348012345678',
            'date_of_birth': '',
            'country': 'Nigeria',
            'state': 'Lagos',
            'area': 'Ikeja',
            'gender': 'N',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response['Location'],
            reverse('conversation-detail', kwargs={'conversation_id': CONVERSATION_ID}),
        )
        self.assertTrue(any(
            call[0] == 'POST' and call[1] == f'/conversations/direct/artisan/{ARTISAN_ID}/'
            for call in PublicNavigationAPIClient.calls
        ))
        self.assertNotIn('pending_protected_action', self.client.session)

    def test_guest_service_request_draft_resumes_after_login_and_profile_completion(self):
        request_values = {
            'category_name': 'Home Repair',
            'service_name': 'Plumbing',
            'location_id': LOCATION_ID,
            'preferred_date': '2026-12-15',
            'urgency': 'HIGH',
            'budget': '45000.00',
            'description': 'Please replace a leaking kitchen pipe.',
        }
        guest_response = self.client.post(reverse('service-requests'), request_values)
        resume_url = f"{reverse('service-requests')}?resume=draft"
        self.assertEqual(guest_response.status_code, 302)
        self.assertEqual(
            guest_response['Location'],
            f"{reverse('login')}?{urlencode({'next': resume_url})}",
        )
        self.assertEqual(
            self.client.session['pending_service_request_draft'],
            {key: str(value) for key, value in request_values.items()},
        )

        login_response = self.client.post(reverse('login'), {
            'email': 'ada@example.test',
            'password': 'not-a-real-password',
            'next': resume_url,
        })
        completion_url = f"{reverse('customer-profile')}?{urlencode({'next': resume_url})}"
        self.assertEqual(login_response.status_code, 302)
        self.assertEqual(login_response['Location'], completion_url)

        completion_response = self.client.post(reverse('customer-profile'), {
            'next': resume_url,
            'first_name': 'Ada',
            'last_name': 'Customer',
            'phone_number': '+2348012345678',
            'date_of_birth': '',
            'country': 'Nigeria',
            'state': 'Lagos',
            'area': 'Ikeja',
            'gender': 'N',
        })
        self.assertEqual(completion_response.status_code, 302)
        self.assertEqual(completion_response['Location'], resume_url)

        resumed = self.client.get(resume_url)
        self.assertEqual(resumed.status_code, 200)
        self.assertEqual(resumed.context['form']['category_name'].value(), 'Home Repair')
        self.assertEqual(resumed.context['form']['service_name'].value(), 'Plumbing')
        self.assertEqual(resumed.context['form']['description'].value(), request_values['description'])
        self.assertEqual(resumed.context['form']['budget'].value(), '45000.00')

    def test_login_rejects_external_redirects_but_keeps_safe_internal_next(self):
        login_url = reverse('login')
        unsafe = self.client.get(login_url, {'next': 'https://attacker.example/'} )
        self.assertEqual(unsafe.status_code, 200)
        self.assertEqual(unsafe.context['next_target'], '')
        self.assertNotIn('login_next', self.client.session)

        target = f"{reverse('artisans')}?q=plumbing&state=Lagos"
        safe = self.client.get(login_url, {'next': target})
        self.assertEqual(safe.status_code, 200)
        self.assertEqual(safe.context['next_target'], target)
        self.assertEqual(self.client.session['login_next'], target)
        self.assertContains(safe, 'name="next"')

        register = self.client.get(reverse('register'), {'next': target})
        self.assertEqual(register.status_code, 200)
        self.assertEqual(register.context['next_target'], target)
        self.assertContains(register, 'name="next"')
        self.assertContains(register, 'Already have an account?')

    def test_successful_login_requires_explicit_payment_notice_acknowledgement(self):
        with (
            patch('frontend.views._continue_pending_protected_action', return_value=None),
            patch('frontend.views._support_capabilities', return_value={}),
            patch('frontend.views.current_role', return_value='customer'),
        ):
            login_response = self.client.post(reverse('login'), {
                'email': 'ada@example.test',
                'password': 'not-a-real-password',
            })

        self.assertEqual(login_response.status_code, 302)
        self.assertTrue(self.client.session.get('payment_notice_pending'))
        signed_in_page = self.client.get(reverse('services'))
        self.assertTrue(signed_in_page.context['payment_notice_auto_offer'])
        self.assertContains(signed_in_page, 'Payment follows agreement')
        self.assertContains(signed_in_page, 'I understand — continue')

        acknowledged = self.client.post(reverse('acknowledge-payment-notice'), {
            'next': reverse('services'),
        })
        self.assertEqual(acknowledged.status_code, 302)
        self.assertEqual(acknowledged['Location'], reverse('services'))
        self.assertNotIn('payment_notice_pending', self.client.session)

        next_page = self.client.get(reverse('services'))
        self.assertFalse(next_page.context['payment_notice_auto_offer'])
        self.assertContains(next_page, 'data-payment-notice-auto="false"')

    def test_customer_login_defaults_to_signed_in_home(self):
        with (
            patch('frontend.views._continue_pending_protected_action', return_value=None),
            patch('frontend.views._support_capabilities', return_value={}),
            patch('frontend.views.current_role', return_value='customer'),
        ):
            response = self.client.post(reverse('login'), {
                'email': 'ada@example.test',
                'password': 'not-a-real-password',
            })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('home'))

    def test_homepage_is_independent_of_catalogue_database_or_api_availability(self):
        PublicNavigationAPIClient.catalog_unavailable = True
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'trade-carpentry-1440.webp')
        self.assertEqual(response.content.decode().count('data-carousel-slide'), 6)
        self.assertEqual(response.context['visual_themes'], response.context['hero_slides'])
        self.assertEqual(PublicNavigationAPIClient.calls, [('GET', '/promotions/homepage/', None), ('GET', '/promotions/market-picks/', None)])
        self.assertNotContains(response, 'temporarily unavailable')
        self.assertNotContains(response, 'Live service catalogue')
