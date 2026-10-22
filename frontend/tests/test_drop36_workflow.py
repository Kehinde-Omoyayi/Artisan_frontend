"""Rebuilt regression coverage for explicit requests and safe in-chat guidance."""
from django.test import SimpleTestCase
from django.template.loader import render_to_string
from frontend.views import _conversation_request_payload, _private_conversation_messages


class RequestAndGuidanceRebuildTests(SimpleTestCase):
    def test_draft_payload_does_not_submit(self):
        result=_conversation_request_payload({'description':'Fix my sockets'},submit_request=False)
        self.assertIs(result['submit_request'],False)
        self.assertEqual(result['description'],'Fix my sockets')

    def test_submission_requires_explicit_submit_argument(self):
        result=_conversation_request_payload({'description':'Fix my sockets'},submit_request=True)
        self.assertIs(result['submit_request'],True)

    def test_nullable_request_details_can_be_cleared(self):
        result=_conversation_request_payload({'budget':'','preferred_date':'','budget_unknown':'true'},submit_request=False)
        self.assertIsNone(result['budget'])
        self.assertIsNone(result['preferred_date'])
        self.assertIs(result['budget_unknown'],True)
        self.assertIs(result['submit_request'],False)

    def room(self,role='customer'):
        return {'id':'12345678-1234-4234-8234-123456789abc','conversation_type':'SERVICE','viewer_role':role,'viewer_id':1,'available_actions':[],
                'guidance':{'role':role,'title':'Inspect the work' if role=='customer' else 'Wait for customer inspection','message':'<script>untrusted text</script>','steps':['Use explicit controls.'],'action':None}}

    def test_both_role_cards_render_and_untrusted_copy_is_escaped(self):
        for role in ['customer','artisan']:
            html=render_to_string('conversations/detail.html',{'conversation':self.room(role),'role':role,'nav_role':role,'csrf_token':'test-only'})
            self.assertIn('id="booking-guidance"',html)
            self.assertIn('&lt;script&gt;untrusted text&lt;/script&gt;',html)
            self.assertNotIn('<script>untrusted text</script>',html)
            self.assertIn('Guidance only.',html)

    def test_direct_room_has_no_booking_guidance_card(self):
        room=self.room();room['conversation_type']='DIRECT';room['guidance']=None
        html=render_to_string('conversations/detail.html',{'conversation':room,'role':'customer','nav_role':'customer','csrf_token':'test-only'})
        self.assertNotIn('id="booking-guidance"',html)

    def test_private_proxy_preserves_live_guidance_and_pagination(self):
        payload={'count':0,'next':None,'previous':None,'results':[],'guidance':self.room()['guidance']}
        self.assertIs(_private_conversation_messages(payload,'12345678-1234-4234-8234-123456789abc'),payload)
        self.assertEqual(payload['guidance']['role'],'customer')
        self.assertIn('results',payload)
