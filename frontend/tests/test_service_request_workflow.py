from datetime import date, timedelta
from uuid import UUID
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse


LOCATION_ID = 'f0250929-a7a9-4f07-82ee-47bf45b139d9'
ARTISAN_ID = '9b7f7234-7339-4c83-9868-7a0d83f81399'
CONVERSATION_ID = 'f315d2c2-f71a-4b6d-9f81-712481d095f5'
BOOKING_ID = '7b436270-6921-49bc-b496-0569673cfc87'


class FakeAPIClient:
    calls = []

    def __init__(self, request):
        self.request = request

    @classmethod
    def reset(cls):
        cls.calls.clear()

    def get(self, path, params=None):
        self.calls.append(('GET', path, params or None))
        normalized = path.rstrip('/') + '/'
        if normalized == '/notifications/unread-count/':
            return 200, {'unread_count': 0}, {}
        if normalized == '/profile/customer/personal/profile/':
            return 200, {
                'first_name': 'Ada',
                'last_name': 'Customer',
                'phone_number': '+2348012345678',
                'country': 'Nigeria',
                'state': 'Lagos',
                'area': 'Yaba',
            }, {}
        if normalized == '/services/categories/':
            return 200, [{'id': 3, 'name': 'Home Repair'}], {}
        if normalized == '/services/service_cat/':
            return 200, [{'id': 8, 'name': 'Plumbing', 'category_name': 'Home Repair'}], {}
        if normalized == '/services/locations/':
            return 200, [{
                'id': LOCATION_ID,
                'country': 'Nigeria',
                'state': 'Lagos',
                'area': 'Yaba',
            }], {}
        if normalized == '/services/requests/':
            return 200, {'count': 0, 'next': None, 'previous': None, 'results': []}, {}
        if normalized == '/services/requests/42/':
            return 200, {
                'id': 42,
                'category_name': 'Home Repair',
                'service_name': 'Plumbing',
                'location': {'country': 'Nigeria', 'state': 'Lagos', 'area': 'Yaba'},
                'preferred_date': (date.today() + timedelta(days=5)).isoformat(),
                'urgency': 'NORMAL',
                'budget': '25000.00',
                'description': 'Repair a leaking kitchen tap.',
            }, {}
        if normalized == '/services/requests/42/responses/':
            return 200, {
                'count': 1,
                'next': None,
                'previous': None,
                'results': [{
                    'id': 17,
                    'status': 'INTERESTED',
                    'responded_at': '2026-10-12T09:00:00Z',
                    'artisan': {
                        'id': ARTISAN_ID,
                        'name': 'Ada Artisan',
                        'business_name': 'Ada Plumbing',
                        'bio': 'Residential plumbing and repairs.',
                        'years_experience': 6,
                        'country': 'Nigeria',
                        'state': 'Lagos',
                        'area': 'Yaba',
                        'profile_photo': None,
                        'average_rating': '4.80',
                        'completion_rate': '95.00',
                        'verification_status': 'VERIFIED',
                        'services': [{'service_name': 'Plumbing'}],
                    },
                }],
            }, {}
        if normalized == f'/booking/{BOOKING_ID}/':
            return 200, {
                'id': BOOKING_ID,
                'status': 'IN_PROGRESS',
                'price_agreed': '45000.00',
            }, {}
        if normalized == '/support/cases/':
            return 200, {
                'count': 1,
                'next': None,
                'previous': None,
                'results': [{
                    'id': 71,
                    'booking': BOOKING_ID,
                    'case_type': 'DISPUTE',
                    'reference': 'SUP-TEST-71',
                }],
            }, {}
        if normalized == '/services/artisan/requests/':
            return 200, {
                'count': 1,
                'next': None,
                'previous': None,
                'results': [{
                    'id': 42,
                    'category_name': 'Home Repair',
                    'service_name': 'Plumbing',
                    'location': {'country': 'Nigeria', 'state': 'Lagos', 'area': 'Yaba'},
                    'preferred_date': (date.today() + timedelta(days=5)).isoformat(),
                    'urgency': 'HIGH',
                    'budget': '25000.00',
                    'description': 'Repair a leaking kitchen tap.',
                    'response_status': None,
                }],
            }, {}
        raise AssertionError(f'Unexpected fake API GET: {path}')

    def post(self, path, data=None, files=None, idempotency_key=None):
        self.calls.append(('POST', path, data, idempotency_key))
        normalized = path.rstrip('/') + '/'
        if normalized == '/services/requests/':
            return 201, {'id': 91, **(data or {})}, {}
        if normalized == '/conversations/start/':
            return 201, {'id': CONVERSATION_ID}, {}
        if normalized == '/services/requests/42/responses/':
            return 201, {'id': 17, 'status': 'INTERESTED'}, {}
        if normalized == f'/booking/{BOOKING_ID}/dispute/':
            return 200, {'id': BOOKING_ID, 'status': 'DISPUTED'}, {}
        if normalized == f'/conversations/{CONVERSATION_ID}/dispute/':
            return 200, {
                'id': CONVERSATION_ID,
                'dispute_case': {'id': 71, 'reference': 'SUP-TEST-71'},
            }, {}
        if normalized == '/support/cases/71/messages/':
            return 201, {'id': 92, 'action': 'CASE_MESSAGE_SENT'}, {}
        raise AssertionError(f'Unexpected fake API POST: {path}')

    def patch(self, path, data=None, files=None, idempotency_key=None):
        self.calls.append(('PATCH', path, data))
        if path.rstrip('/') == '/services/requests/42':
            return 200, {'id': 42, **(data or {})}, {}
        raise AssertionError(f'Unexpected fake API PATCH: {path}')

    def delete(self, path):
        self.calls.append(('DELETE', path))
        if path.rstrip('/') == '/services/requests/42/responses':
            return 200, {'id': 17, 'status': 'WITHDRAWN'}, {}
        raise AssertionError(f'Unexpected fake API DELETE: {path}')


class ServiceRequestWorkflowTests(TestCase):
    def setUp(self):
        FakeAPIClient.reset()
        self.client_patches = [
            patch('frontend.views.APIClient', FakeAPIClient),
            patch('frontend.context_processors.APIClient', FakeAPIClient),
        ]
        for client_patch in self.client_patches:
            client_patch.start()
            self.addCleanup(client_patch.stop)
        session = self.client.session
        session['api_access'] = 'unit-test-session-token'
        session['api_user'] = {'id': 1, 'email': 'customer@example.test', 'role': 'customer'}
        session['api_role'] = 'customer'
        session.save()

    def test_customer_request_list_renders_catalog_backed_form(self):
        response = self.client.get('/requests/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Create a request')
        self.assertTrue(response.context['catalog_ready'])
        self.assertContains(response, 'Home Repair')
        self.assertContains(response, 'Plumbing')

    def test_create_request_maps_catalog_location_to_api_contract(self):
        preferred_date = (date.today() + timedelta(days=8)).isoformat()
        response = self.client.post('/requests/', {
            'category_name': 'Home Repair',
            'service_name': 'Plumbing',
            'location_id': LOCATION_ID,
            'preferred_date': preferred_date,
            'urgency': 'HIGH',
            'budget': '45000.00',
            'description': 'Replace a damaged kitchen pipe.',
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('service-request-detail', kwargs={'pk': 91}))
        created = next(call for call in FakeAPIClient.calls if call[0] == 'POST' and call[1] == '/services/requests/')
        payload = created[2]
        self.assertEqual(payload['category_name'], 'Home Repair')
        self.assertEqual(payload['service_name'], 'Plumbing')
        self.assertEqual(payload['location'], {'country': 'Nigeria', 'state': 'Lagos', 'area': 'Yaba'})
        self.assertEqual(payload['preferred_date'], preferred_date)
        self.assertEqual(payload['budget'], '45000.00')

    def test_customer_can_clear_optional_budget_when_editing_request(self):
        preferred_date = (date.today() + timedelta(days=5)).isoformat()
        response = self.client.post('/requests/42/', {
            'action': 'update',
            'category_name': 'Home Repair',
            'service_name': 'Plumbing',
            'location_id': LOCATION_ID,
            'preferred_date': preferred_date,
            'urgency': 'NORMAL',
            'budget': '',
            'description': 'Repair a leaking kitchen tap.',
        })
        self.assertEqual(response.status_code, 302)
        patch_call = next(call for call in FakeAPIClient.calls if call[0] == 'PATCH' and call[1] == '/services/requests/42/')
        self.assertIsNone(patch_call[2]['budget'])

    def test_customer_can_review_responders_and_start_selected_artisan_chat(self):
        response = self.client.get('/requests/42/responders/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ada Plumbing')
        self.assertContains(response, 'Start a conversation')
        self.assertEqual(response.context['responder_total'], 1)

        response = self.client.post('/requests/42/responders/', {
            'action': 'start_conversation',
            'artisan_id': ARTISAN_ID,
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('conversation-detail', kwargs={'conversation_id': UUID(CONVERSATION_ID)}))
        start = next(call for call in FakeAPIClient.calls if call[0] == 'POST' and call[1] == '/conversations/start/')
        self.assertEqual(start[2], {'artisan_id': ARTISAN_ID, 'service_request_id': 42})

    def test_artisan_board_passes_filters_and_posts_response_action(self):
        query = '?category_name=Home+Repair&service_name=Plumbing&location_state=Lagos&preferred_date_from=2026-10-15&min_budget=10000&ordering=urgency'
        response = self.client.get('/account/artisan/requests/' + query)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Repair a leaking kitchen tap.')
        board_get = next(call for call in FakeAPIClient.calls if call[0] == 'GET' and call[1] == '/services/artisan/requests/')
        self.assertEqual(board_get[2]['category_name'], 'Home Repair')
        self.assertEqual(board_get[2]['service_name'], 'Plumbing')
        self.assertEqual(board_get[2]['location_state'], 'Lagos')
        self.assertEqual(board_get[2]['preferred_date_from'], '2026-10-15')
        self.assertEqual(board_get[2]['min_budget'], '10000')
        self.assertEqual(board_get[2]['ordering'], 'urgency')

        response = self.client.post('/account/artisan/requests/' + query, {
            'action': 'respond',
            'request_id': '42',
            'return_to': '/account/artisan/requests/' + query,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/account/artisan/requests/' + query)
        self.assertTrue(any(call[0] == 'POST' and call[1] == '/services/requests/42/responses/' for call in FakeAPIClient.calls))

    def test_artisan_can_withdraw_active_response(self):
        response = self.client.post('/account/artisan/requests/', {
            'action': 'withdraw',
            'request_id': '42',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(any(call[0] == 'DELETE' and call[1] == '/services/requests/42/responses/' for call in FakeAPIClient.calls))

    def test_conversation_dispute_sends_the_report_as_a_support_case_message(self):
        message = 'The service remains incomplete and I need support to review it.'
        response = self.client.post(f'/discover/conversations/{CONVERSATION_ID}/', {
            'action': 'dispute',
            'reason': message,
            'support_message_key': 'conversation-dispute-message-test-key',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('support-case-detail', kwargs={'pk': 71}) + '#latest-message')
        self.assertTrue(any(
            call[0] == 'POST'
            and call[1] == f'/conversations/{CONVERSATION_ID}/dispute/'
            and call[2] == {'reason': message}
            for call in FakeAPIClient.calls
        ))
        support_message = next(
            call for call in FakeAPIClient.calls
            if call[0] == 'POST' and call[1] == '/support/cases/71/messages/'
        )
        self.assertEqual(support_message[2], {'message': message})
        self.assertEqual(support_message[3], 'conversation-dispute-message-test-key')

    def test_booking_dispute_posts_a_public_message_to_customer_support(self):
        message = 'The repair is incomplete and I need help resolving the outstanding issue.'
        path = f'/bookings/{BOOKING_ID}/dispute/'
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Send a message to customer support')

        response = self.client.post(path, {
            'message': message,
            'dispute_idempotency_key': 'booking-dispute-test-key',
            'support_message_key': 'dispute-message-test-key',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('support-case-detail', kwargs={'pk': 71}) + '#latest-message')
        self.assertTrue(any(
            call[0] == 'POST'
            and call[1] == f'/booking/{BOOKING_ID}/dispute/'
            and call[2] == {'reason': message}
            for call in FakeAPIClient.calls
        ))
        support_message = next(
            call for call in FakeAPIClient.calls
            if call[0] == 'POST' and call[1] == '/support/cases/71/messages/'
        )
        self.assertEqual(support_message[2], {'message': message})
