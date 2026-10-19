from django import forms
from django.template.loader import render_to_string
from django.test import SimpleTestCase

from frontend.forms import PayoutAccountForm


class PayoutAccountFormTests(SimpleTestCase):
    def test_entry_is_limited_to_three_fields_and_provider_banks(self):
        form = PayoutAccountForm(banks=[
            {"code": "058", "name": "Provider Bank"},
            {"code": "044", "name": "Another Provider Bank"},
        ])

        self.assertEqual(list(form.fields), ["account_name", "bank_code", "account_number"])
        self.assertEqual(
            list(form.fields["bank_code"].choices),
            [
                ("", "Choose a supported bank"),
                ("058", "Provider Bank"),
                ("044", "Another Provider Bank"),
            ],
        )
        self.assertIsInstance(form.fields["account_number"].widget, forms.PasswordInput)
        self.assertEqual(form.fields["account_number"].widget.attrs["inputmode"], "numeric")

    def test_saved_account_displays_only_account_name_bank_and_masked_number(self):
        form = PayoutAccountForm(banks=[{"code": "058", "name": "Provider Bank"}])
        html = render_to_string(
            "payments/payout_account.html",
            {
                "form": form,
                "nav_role": "guest",
                "authenticated": False,
                "account": {
                    "account_name": "Ada Okafor",
                    "bank_name": "Provider Bank",
                    "bank_code": "058",
                    "account_number_last4": "7890",
                    "account_number": "1234567890",
                },
            },
        )

        self.assertIn("Account Name", html)
        self.assertIn("Ada Okafor", html)
        self.assertIn("Bank", html)
        self.assertIn("Provider Bank", html)
        self.assertIn("Account Number", html)
        self.assertIn("•••• 7890", html)
        self.assertNotIn("1234567890", html)
        self.assertEqual(html.count("<div><span>"), 3)
