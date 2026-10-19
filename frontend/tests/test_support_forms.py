from django.test import SimpleTestCase

from frontend.forms import SupportCaseForm


class SupportDescriptionFormTests(SimpleTestCase):
    def make_data(self, description):
        return {
            "case_type": "REPORT",
            "priority": "MEDIUM",
            "subject": "Review a marketplace issue",
            "description": description,
        }

    def test_fewer_than_six_words_and_punctuation_only_are_rejected(self):
        for description in ("Please help with this issue.", " !!! ... --- ??? "):
            with self.subTest(description=description):
                form = SupportCaseForm(data=self.make_data(description))
                self.assertFalse(form.is_valid())
                self.assertIn("six meaningful words", str(form.errors["description"]))

    def test_valid_description_is_trimmed_without_changing_internal_spacing(self):
        original = "  The details here preserve   internal spacing as provided.  "
        form = SupportCaseForm(data=self.make_data(original))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["description"], original.strip())
