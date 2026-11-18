"""Phase 5 regression: the add-on payment card has full transfer parity.

The booking escrow payment and an approved add-on's independent payment are the
same engine with different scope. The card the payer uses to pay must offer the
same things in both places: one route to the money at a time, the dedicated
transfer account in place, and the confirm button wired to the add-on's own
``additional_order_pay_transfer[_check]`` actions — never the booking's.
"""

from django.test import SimpleTestCase
from django.template.loader import render_to_string


def _room(addon):
    return {
        "id": "12345678-1234-4234-8234-123456789abc",
        "conversation_type": "SERVICE",
        "viewer_role": "customer",
        "viewer_id": 1,
        "available_actions": [],
        "journey": [],
        "title": "Emeka",
        "booking": {
            "id": "12345678-1234-4234-8234-123456789abc",
            "status": "IN_PROGRESS",
            "price_agreed": "45000.00",
        },
        "additional_orders": [addon],
    }


def _addon(**overrides):
    addon = {
        "id": "order-1",
        "status": "APPROVED",
        "can_pay": True,
        "current_offer": {
            "id": "offer-1",
            "created_by_id": 99,
            "amount": "12000.00",
            "description": "Fit the extra socket in the hallway.",
            "revision": 1,
            "status": "ACCEPTED",
            "created_at": "15 Nov, 10:00",
        },
        "offers": [],
        "payment": {
            "id": "12345678-1234-4234-8234-123456789abc",
            "status": "PAYMENT_PENDING",
            "total_amount": "12400.00",
        },
        "payment_status_url": "/payments/12345678-1234-4234-8234-123456789abc/status/",
        "payment_checkout_url": "",
        "bank_transfer": {},
    }
    addon.update(overrides)
    return addon


class AddonTransferCardRenderTests(SimpleTestCase):
    def render(self, addon, **extra):
        context = {
            "conversation": _room(addon),
            "role": "customer",
            "nav_role": "customer",
            "csrf_token": "test-only",
            "current_phase": {
                "step": 4,
                "key": "PROGRESS",
                "title": "Work in Progress",
                "description": "The artisan is on site.",
            },
            "request_brief": {},
            "message_key": "conversation-message-test",
        }
        context.update(extra)
        return render_to_string("conversations/detail.html", context)

    def test_gate_offers_transfer_with_addon_actions(self):
        html = self.render(_addon())
        self.assertIn('value="additional_order_pay_transfer"', html)
        self.assertIn('name="order_id" value="order-1"', html)
        self.assertIn('name="payment_id" value="12345678-1234-4234-8234-123456789abc"', html)

    def test_live_account_hides_the_pay_button_and_renders_the_card(self):
        addon = _addon(
            bank_transfer={
                "live": True,
                "status": "READY",
                "account_number": "1234567890",
                "bank": "Test Bank",
                "beneficiary_name": "Artisan Market Checkout",
                "amount": "12400.00",
                "expires_at": "2026-11-19T12:00:00+00:00",
                "seconds_left": 3400,
            }
        )
        html = self.render(addon)
        # The card is present with the add-on's own confirm wiring...
        self.assertIn("data-transfer-card", html)
        self.assertIn('value="additional_order_pay_transfer_check"', html)
        self.assertIn('name="payment_id" value="12345678-1234-4234-8234-123456789abc"', html)
        self.assertIn('name="order_id" value="order-1"', html)
        self.assertIn("1234567890", html)
        # ...and the start control is inert while the account is open.
        self.assertIn('data-pay-live="true"', html)

    def test_card_context_is_addon_not_payment(self):
        addon = _addon(
            bank_transfer={
                "live": True,
                "status": "READY",
                "account_number": "1234567890",
                "bank": "Test Bank",
                "amount": "12400.00",
                "expires_at": "2026-11-19T12:00:00+00:00",
                "seconds_left": 3400,
            }
        )
        html = self.render(addon)
        self.assertIn('data-transfer-context="addon"', html)
        # The addon confirm form posts to the page, never to a payment URL.
        self.assertNotIn('action="pay_transfer_check"', html)

    def test_card_fallback_link_is_offered_only_with_a_live_checkout(self):
        html = self.render(_addon(payment_checkout_url="https://checkout.example/live"))
        self.assertIn("Pay by card instead", html)
        self.assertIn("https://checkout.example/live", html)
        html = self.render(_addon())
        self.assertNotIn("Pay by card instead", html)

    def test_baton_changes_after_transfer_expiry_label(self):
        # A closed account still shows the payment link wording on the button.
        addon = _addon(
            payment={"id": "12345678-1234-4234-8234-123456789abc", "status": "PAYMENT_PENDING", "total_amount": "12400.00"},
            bank_transfer={
                "status": "READY",
                "account_number": "1234567890",
                "live": False,
                "seconds_left": 0,
                "expires_at": "2026-11-01T12:00:00+00:00",
            },
        )
        html = self.render(addon)
        self.assertIn("Request for payment link", html)

    def test_failed_payment_reads_as_retry(self):
        addon = _addon(
            payment={"id": "12345678-1234-4234-8234-123456789abc", "status": "FAILED", "total_amount": "12400.00"},
        )
        html = self.render(addon)
        self.assertIn("Retry secure payment", html)


class AddonDeepLinkRenderTests(SimpleTestCase):
    def test_addon_card_carries_the_notification_anchor(self):
        from frontend.tests.test_addon_transfer_card import _addon, _room
        from django.template.loader import render_to_string

        context = {
            "conversation": _room(_addon()),
            "role": "customer",
            "nav_role": "customer",
            "csrf_token": "test-only",
            "current_phase": {
                "step": 4,
                "key": "PROGRESS",
                "title": "Work in Progress",
                "description": "The artisan is on site.",
            },
            "request_brief": {},
            "message_key": "conversation-message-test",
        }
        html = render_to_string("conversations/detail.html", context)
        # Notification action URLs deep-link to #additional-order-<id>; the
        # target must exist or the anchor is a dead end.
        self.assertIn('id="additional-order-order-1"', html)


class AddonPopupParserTests(SimpleTestCase):
    """The popup parser is vanilla JS (no JS test runner in this environment);
    these assert the add-on decision path is present so a future cleanup that
    drops it fails loudly."""

    def _source(self):
        import pathlib

        base = pathlib.Path(__file__).resolve().parents[2] / "static" / "js" / "booking-events.js"
        return base.read_text(encoding="utf-8")

    def test_addon_decision_events_are_recognised(self):
        src = self._source()
        self.assertIn("additional_order_proposed", src)
        self.assertIn("additional_order_countered", src)
        self.assertIn("isAddonDecision", src)

    def test_addon_inline_accept_uses_additional_order_respond(self):
        src = self._source()
        self.assertIn("additional_order_respond", src)
        self.assertIn("response_action", src)
        self.assertIn("order_id", src)

    def test_notification_amount_fallback(self):
        src = self._source()
        self.assertIn("data.offer_amount || data.amount", src)


class CardPlacementTests(SimpleTestCase):
    """Phase 7: the journey-status, booking and add-on cards render in the
    conversation flow (after the messages, before Service tools), not hidden behind it."""

    def render(self, addon, **overrides):
        from django.template.loader import render_to_string

        room = _room(addon)
        room["state"] = "ACTIVE"
        room["conversation_type"] = "SERVICE"
        room["booking"] = {
            "id": "12345678-1234-4234-8234-123456789abc",
            "status": "IN_PROGRESS",
            "price_agreed": "45000.00",
            "scheduled_start": "2026-11-16T09:00:00Z",
            "scheduled_end": "2026-11-16T13:00:00Z",
        }
        room["payment"] = {
            "id": "12345678-1234-4234-8234-123456789abc",
            "status": "HELD",
            "total_amount": "45000.00",
        }
        room.update(overrides)
        context = {
            "conversation": room,
            "role": room.get("viewer_role", "customer"),
            "nav_role": room.get("viewer_role", "customer"),
            "csrf_token": "test-only",
            "current_phase": {
                "step": 4,
                "key": "PROGRESS",
                "title": "Work in Progress",
                "description": "The artisan is on site.",
            },
            "request_brief": {},
            "message_key": "conversation-message-test",
            "payment_id": room["payment"]["id"],
            "payment_status_url": "/payments/x/status/",
            "bank_transfer": {},
        }
        return render_to_string("conversations/detail.html", context)

    def test_journey_status_and_booking_card_are_before_service_tools(self):
        html = self.render(_addon())
        tools = html.index('id="chat-service-tools"')
        scroll = html.index('id="conversation-scroll-area"')
        journey = html.index('class="journey-status active"')
        booking = html.index('workflow-card booking-card')
        self.assertGreater(journey, scroll)
        self.assertGreater(booking, scroll)
        self.assertLess(journey, tools)
        self.assertLess(booking, tools)

    def test_addon_cards_are_before_service_tools(self):
        html = self.render(_addon())
        tools = html.index('id="chat-service-tools"')
        addon_card = html.index('id="additional-order-order-1"')
        scroll = html.index('id="conversation-scroll-area"')
        self.assertGreater(addon_card, scroll)
        self.assertLess(addon_card, tools)

    def test_addon_proposal_form_stays_inside_service_tools(self):
        # Artisan, booking in progress, escrow held: the *create* form is a
        # back-office action and stays behind the toggle; decisions moved out.
        html = self.render(_addon(), viewer_role="artisan")
        tools = html.index('id="chat-service-tools"')
        create = html.index("additional-order-create-card")
        self.assertGreater(create, tools)


class ServiceToolsBadgeTests(SimpleTestCase):
    def _render(self, pending):
        from django.template.loader import render_to_string

        context = {
            "conversation": _room(_addon()),
            "role": "artisan",
            "nav_role": "artisan",
            "csrf_token": "test-only",
            "current_phase": {
                "step": 2,
                "key": "OFFER",
                "title": "Offer",
                "description": "Prepare the itemised quote.",
            },
            "request_brief": {},
            "message_key": "conversation-message-test",
        }
        if pending is not None:
            context["service_tools_pending"] = pending
        return render_to_string("conversations/detail.html", context)

    def test_badge_renders_the_count_when_items_wait(self):
        html = self._render(2)
        self.assertIn('class="chat-tools-badge"', html)
        self.assertIn(">2</span>", html)
        self.assertIn('data-pending="true"', html)
        self.assertIn("2 items waiting", html)

    def test_badge_is_absent_when_nothing_waits(self):
        for pending in (0, None):
            html = self._render(pending)
            self.assertNotIn('class="chat-tools-badge"', html)
            self.assertNotIn('data-pending="true"', html)


class ServiceToolsPendingHelperTests(SimpleTestCase):
    def test_counts_only_quote_work_behind_the_toggle(self):
        from frontend.views import _service_tools_pending

        # Payment and booking lifecycle actions live in the conversation now;
        # they must not inflate the count.
        self.assertEqual(_service_tools_pending({"available_actions": ["PAY"]}), 0)
        self.assertEqual(_service_tools_pending({"available_actions": ["START_BOOKING"]}), 0)
        self.assertEqual(_service_tools_pending({"available_actions": ["CONFIRM_COMPLETION"]}), 0)
        self.assertEqual(_service_tools_pending({"available_actions": ["ACCEPT_OFFER"]}), 0)
        self.assertEqual(_service_tools_pending({"available_actions": ["SEND_OFFER"]}), 1)
        self.assertEqual(_service_tools_pending({"available_actions": ["COUNTER_OFFER"]}), 1)
        self.assertEqual(_service_tools_pending({"available_actions": ["REVISE_OFFER"]}), 1)
        self.assertEqual(
            _service_tools_pending({"available_actions": ["SEND_OFFER", "COUNTER_OFFER"]}),
            2,
        )
        self.assertEqual(_service_tools_pending({}), 0)
