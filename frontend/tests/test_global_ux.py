from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase
from django.urls import reverse

from frontend.views import home


class GlobalUXTests(TestCase):
    def test_shared_shell_has_reusable_logout_and_tour_dialogs_and_footer(self):
        response = self.client.get(reverse('home'))
        html = response.content.decode('utf-8')

        self.assertEqual(response.status_code, 200)
        self.assertIn('data-confirm-dialog', html)
        self.assertIn('Sign out of Artisan Market?', (Path(settings.BASE_DIR) / 'static/js/site.js').read_text())
        self.assertIn('id="site-onboarding-tour"', html)
        self.assertEqual(html.count('data-tour-card'), 1)
        self.assertIn('Step 1 of 5', html)
        self.assertIn('data-tour-next', html)
        self.assertIn('data-tour-previous', html)
        self.assertIn('data-tour-skip', html)
        self.assertIn('data-tour-finish', html)
        self.assertIn('data-onboarding-open', html)
        self.assertIn('data-tour-role="guest"', html)
        self.assertIn('data-tour-auto="true"', html)
        self.assertIn('data-payment-notice-auto="false"', html)
        self.assertIn('data-payment-notice-dialog', html)
        self.assertIn('Artisans receive payout only after service completion is confirmed.', html)
        self.assertIn('A marketplace for artisan work in Nigeria', html)

    def test_shared_flash_message_is_dismissible_and_scoped_to_django_messages(self):
        request = RequestFactory().get(reverse('home'))
        SessionMiddleware(lambda _request: None).process_request(request)
        request.session.save()
        request._messages = FallbackStorage(request)
        messages.success(request, 'A temporary success notice for the shared shell.')

        response = home(request)
        html = response.content.decode('utf-8')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(html.count('data-flash-message'), 1)
        self.assertEqual(html.count('data-flash-dismiss'), 1)
        self.assertIn('data-flash-stack', html)
        self.assertIn('role="status"', html)
        self.assertIn('A temporary success notice for the shared shell.', html)

    def test_shared_behavior_uses_five_second_timers_safe_submission_and_a_five_step_cap(self):
        js = (Path(settings.BASE_DIR) / 'static/js/site.js').read_text(encoding='utf-8')
        css = (Path(settings.BASE_DIR) / 'static/css/site.css').read_text(encoding='utf-8')
        conversation = (Path(settings.BASE_DIR) / 'templates/conversations/detail.html').read_text(encoding='utf-8')

        self.assertIn('5000', js)
        self.assertIn('new MutationObserver', js)
        self.assertIn('requestSubmit', js)
        self.assertIn("const MAX_TOUR_STEPS = 5", js)
        self.assertIn('slice(0, MAX_TOUR_STEPS)', js)
        self.assertIn('data-confirm-logout', (Path(settings.BASE_DIR) / 'templates/partials/navbar.html').read_text())
        self.assertIn('body{min-height:100vh;min-height:100dvh;display:flex;flex-direction:column}', css)
        self.assertIn('body>#main-content{width:100%;min-width:0;flex:1 0 auto}', css)
        self.assertIn('body>.site-footer,body>.landing-footer{width:100%;flex:0 0 auto}', css)
        self.assertIn('A marketplace for artisan work in Nigeria', (Path(settings.BASE_DIR) / 'templates/partials/footer.html').read_text())
        self.assertNotIn('{% block site_footer %}', conversation)
        self.assertIn('data-onboarding-open', conversation)
        self.assertIn('aria-label="Conversation messages"', conversation)
        self.assertNotIn('data-flash-message', conversation)

    def test_role_specific_tour_copy_keeps_customer_and_artisan_workflows_separate(self):
        js = (Path(settings.BASE_DIR) / 'static/js/site.js').read_text(encoding='utf-8')
        self.assertIn("if (userRole === 'customer')", js)
        self.assertIn("if (userRole === 'artisan')", js)
        self.assertIn('Your customer profile holds the contact and location details', js)
        self.assertIn('Use Account to maintain your artisan details, verification status and payout information.', js)
        self.assertIn("title: 'Payment follows agreement'", js)
        self.assertIn("target: 'payment-agreement'", js)
        self.assertNotIn('Compare profiles and services', js)
        self.assertEqual(js.count('paymentAgreement,'), 4)
        self.assertIn("'[data-tour-target=\\\"payment-agreement\\\"]'", js)
        self.assertIn('MAX_TOUR_STEPS = 5', js)
