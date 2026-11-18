"""The unified chronological timeline — ordering contract tests.

Requirement A: every conversation event (messages, quotes, bookings, payments,
add-ons, disputes, the lifecycle strip) renders in ONE stream, ordered by the
authoritative server creation timestamp, with a fixed tie-breaker, and the
order never depends on who is looking or in what sequence the client happened
to receive the payload.

These tests exercise the real interleaving function the page uses
(``frontend.views._conversation_timeline``) with synthetic event payloads.
No network or database is involved; delivery mechanics (polling, reconnect,
de-duplication) are covered by ``frontend.test_min_price_views`` and the
browser-side module ``static/js/pages/conversations-detail.js``.
"""

from datetime import datetime, timedelta, timezone

from django.test import SimpleTestCase

from frontend.views import _conversation_timeline, _parse_conversation_ts


def _ts(minutes, seconds=0):
    base = datetime(2026, 11, 18, 9, 0, 0, tzinfo=timezone.utc)
    return base + timedelta(minutes=minutes, seconds=seconds)


def _iso(value):
    return value.isoformat()


def _message(created_at, body="message", **extra):
    return {
        "id": f"msg-{body}-{created_at.isoformat()}",
        "created_at": _iso(created_at),
        "body": body,
        "message_type": "USER",
        "sender_id": 1,
        **extra,
    }


def _kinds(entries):
    return [entry["kind"] for entry in entries]


def _sort_keys(entries):
    return [entry["sort_key"] for entry in entries]


def _full_conversation(**overrides):
    conversation = {
        "state": "ACTIVE",
        "viewer_role": "customer",
        "booking": {
            "id": "booking-1",
            "status": "ACCEPTED",
            "created_at": _iso(_ts(0)),
        },
        "payment": {
            "id": "payment-1",
            "status": "HELD",
            "created_at": _iso(_ts(30)),
            "total_amount": "25000.00",
            "service_amount": "24000.00",
            "customer_fee": "1000.00",
        },
        "additional_orders": [],
        "active_offer": {
            "id": "offer-1",
            "created_at": _iso(_ts(20)),
            "total_amount": "25000.00",
        },
        "dispute_case": None,
    }
    conversation.update(overrides)
    return conversation


class TimelineInterleavingTests(SimpleTestCase):
    def test_quotation_card_is_placed_at_its_creation_time(self):
        messages = [_message(_ts(10), "before the quote"), _message(_ts(40), "after the quote")]
        entries = _conversation_timeline(_full_conversation(), messages)
        kinds = _kinds(entries)
        self.assertEqual(
            kinds,
            ["booking", "message", "offer", "payment", "journey", "message"],
        )
        offer_index = kinds.index("offer")
        # The quote card goes right where it was created: after the message that
        # preceded it and above everything that came after.
        self.assertEqual(kinds[:3], ["booking", "message", "offer"])

    def test_offer_stays_above_twenty_subsequent_messages(self):
        conversation = _full_conversation(
            booking=None,
            payment=None,
            active_offer={"id": "offer-1", "created_at": _iso(_ts(0))},
        )
        messages = [_message(_ts(index + 1), f"m{index}") for index in range(20)]
        entries = _conversation_timeline(conversation, messages)
        kinds = _kinds(entries)
        self.assertEqual(kinds[0], "offer")
        self.assertEqual(kinds[1:], ["message"] * 20)

    def test_transaction_card_lands_after_existing_messages(self):
        conversation = _full_conversation(
            booking=None,
            payment={"id": "payment-1", "status": "HELD", "created_at": _iso(_ts(50))},
            active_offer=None,
        )
        messages = [_message(_ts(index * 10), f"m{index}") for index in range(5)]  # 0..40
        entries = _conversation_timeline(conversation, messages)
        kinds = _kinds(entries)
        self.assertEqual(kinds, ["message"] * 5 + ["payment", "journey"])

    def test_add_on_card_sits_after_the_five_messages_that_preceded_it(self):
        conversation = _full_conversation(
            booking={"id": "b", "status": "IN_PROGRESS", "created_at": _iso(_ts(0))},
            payment={"id": "p", "status": "HELD", "created_at": _iso(_ts(10))},
            active_offer=None,
            additional_orders=[
                {
                    "id": "addon-1",
                    "created_at": _iso(_ts(70)),
                    "status": "NEGOTIATING",
                    "current_offer": {"amount": "5000.00", "revision": 1},
                    "offers": [],
                }
            ],
        )
        messages = [_message(_ts(20 + index * 10), f"m{index}") for index in range(5)]  # 20..60
        entries = _conversation_timeline(conversation, messages)
        kinds = _kinds(entries)
        self.assertEqual(
            kinds,
            ["booking", "payment", "journey", "message", "message", "message", "message", "message", "addon"],
        )

    def test_multiple_event_types_interleave_chronologically(self):
        conversation = _full_conversation()  # booking 0, offer 20, payment 30, journey visible
        messages = [_message(_ts(10), "a"), _message(_ts(25), "b"), _message(_ts(40), "c")]
        entries = _conversation_timeline(conversation, messages)
        self.assertEqual(
            _kinds(entries),
            ["booking", "message", "offer", "message", "payment", "journey", "message"],
        )

    def test_refresh_persistence_same_payload_same_order(self):
        conversation = _full_conversation()
        messages = [_message(_ts(10), "a"), _message(_ts(25), "b"), _message(_ts(40), "c")]
        first = [(entry["kind"], entry["sort_key"]) for entry in _conversation_timeline(conversation, messages)]
        second = [(entry["kind"], entry["sort_key"]) for entry in _conversation_timeline(conversation, messages)]
        self.assertEqual(first, second)

    def test_order_does_not_depend_on_input_message_sequence(self):
        conversation = _full_conversation()
        forward = [_message(_ts(10), "a"), _message(_ts(25), "b"), _message(_ts(40), "c")]
        backwards = list(reversed(forward))
        self.assertEqual(
            _kinds(_conversation_timeline(conversation, forward)),
            _kinds(_conversation_timeline(conversation, backwards)),
        )

    def test_timeline_does_not_depend_on_the_viewer(self):
        customer = _conversation_timeline(_full_conversation(viewer_role="customer"), [_message(_ts(10), "a")])
        artisan = _conversation_timeline(_full_conversation(viewer_role="artisan"), [_message(_ts(10), "a")])
        self.assertEqual(_kinds(customer), _kinds(artisan))
        self.assertEqual(_sort_keys(customer), _sort_keys(artisan))

    def test_same_instant_events_break_ties_deterministically(self):
        moment = _ts(15)
        conversation = {
            "state": "PENDING",  # no journey strip: keeps the tie set explicit
            "booking": None,
            "payment": {"id": "p", "status": "HELD", "created_at": _iso(moment)},
            "additional_orders": [
                {
                    "id": "a",
                    "created_at": _iso(moment),
                    "status": "NEGOTIATING",
                    "current_offer": {"amount": "100.00", "revision": 1},
                    "offers": [],
                }
            ],
            "active_offer": {"id": "o", "created_at": _iso(moment)},
            "dispute_case": {"id": "d", "created_at": _iso(moment), "reference": "SUP-1", "status": "OPEN", "subject": "Help"},
        }
        messages = [_message(moment, "instant")]
        entries = _conversation_timeline(conversation, messages)
        # Fixed kind order for identical timestamps: booking, dispute, offer,
        # payment, addon, journey, message.
        self.assertEqual(
            _kinds(entries),
            ["dispute_case", "offer", "payment", "addon", "message"],
        )

    def test_entries_without_timestamps_sink_to_the_end(self):
        conversation = {
            "state": "COMPLETED",
            "booking": None,
            "payment": None,
            "additional_orders": [],
            "active_offer": {"id": "undated", "created_at": None},
            "dispute_case": None,
        }
        messages = [_message(_ts(10), "dated")]
        entries = _conversation_timeline(conversation, messages)
        kinds = _kinds(entries)
        self.assertEqual(kinds[0], "message")
        # Timed entries first, then the undated ones in fixed kind order.
        self.assertEqual(kinds[-2:], ["offer", "journey"])

    def test_paginated_slice_preserves_relative_order(self):
        conversation = _full_conversation()
        messages = [_message(_ts(index * 5), f"m{index}") for index in range(1, 25)]  # 5..120
        full = _kinds(_conversation_timeline(conversation, messages))
        window = _kinds(_conversation_timeline(conversation, messages[-20:]))

        def subsequence(narrower, wider):
            iterator = iter(wider)
            return all(any(item == candidate for item in iterator) for candidate in narrower)

        self.assertTrue(subsequence(window, full))

    def test_every_entry_carries_a_sort_key_for_the_client(self):
        conversation = _full_conversation()
        entries = _conversation_timeline(conversation, [_message(_ts(10), "a")])
        for entry in entries:
            self.assertIn("sort_key", entry)


class TimelineTimestampParsingTests(SimpleTestCase):
    def test_iso_with_z_suffix_is_parsed(self):
        parsed = _parse_conversation_ts("2026-11-18T09:30:00Z")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.utcoffset(), timedelta(0))

    def test_iso_with_numeric_offset_is_parsed(self):
        parsed = _parse_conversation_ts("2026-11-18T10:30:00+01:00")
        self.assertEqual(parsed.utcoffset(), timedelta(hours=1))

    def test_naive_values_are_read_as_utc(self):
        parsed = _parse_conversation_ts("2026-11-18T09:30:00")
        self.assertEqual(parsed.utcoffset(), timedelta(0))

    def test_garbage_returns_none_instead_of_raising(self):
        self.assertIsNone(_parse_conversation_ts("not a timestamp"))
        self.assertIsNone(_parse_conversation_ts(""))
        self.assertIsNone(_parse_conversation_ts(None))
