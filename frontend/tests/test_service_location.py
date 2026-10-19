from urllib.parse import parse_qs, urlparse

from django.test import SimpleTestCase

from frontend.forms import ArtisanServiceForm
from frontend.views import _artisan_service_payload, _discovery_categories, _location_id_for_service


class ArtisanServiceLocationControlTests(SimpleTestCase):
    locations = [
        {'id': 'loc-ikeja', 'country': 'Nigeria', 'state': 'Lagos', 'area': 'Ikeja'},
        {'id': 'loc-yaba', 'country': 'Nigeria', 'state': 'Lagos', 'area': 'Yaba'},
    ]
    categories = [{'name': 'Plumbing'}]
    services = [{'name': 'Pipe repair', 'category_name': 'Plumbing'}]

    def test_new_service_form_defaults_to_nigeria_and_funaab_without_fabricating_locations(self):
        form = ArtisanServiceForm(categories=self.categories, services=self.services, locations=self.locations)

        self.assertEqual(form['location_country_filter'].value(), 'Nigeria')
        self.assertEqual(form['institution'].value(), 'FUNAAB')
        self.assertEqual(form.fields['location_id'].choices[1][0], '__anywhere__')
        self.assertIn(('loc-ikeja', 'Ikeja, Lagos, Nigeria'), form.fields['location_id'].choices)
        self.assertNotIn(('Abeokuta', 'Abeokuta'), form.fields['location_id'].choices)

    def test_editing_preserves_registered_location_and_does_not_apply_new_default_institution(self):
        form = ArtisanServiceForm(
            categories=self.categories,
            services=self.services,
            locations=self.locations,
            initial={'location_id': 'loc-yaba'},
        )

        self.assertEqual(form['location_id'].value(), 'loc-yaba')
        self.assertEqual(form['location_country_filter'].value(), 'Nigeria')
        self.assertEqual(form['location_state_filter'].value(), 'Lagos')
        self.assertEqual(form['location_area_filter'].value(), 'Yaba')
        self.assertFalse(form['institution'].value())

    def test_anywhere_uses_existing_null_location_contract(self):
        form = ArtisanServiceForm(
            data={
                'category_name': 'Plumbing',
                'service_name': 'Pipe repair',
                'location_id': '__anywhere__',
                'starting_price': '12000',
            },
            categories=self.categories,
            services=self.services,
            locations=self.locations,
        )

        self.assertTrue(form.is_valid(), form.errors)
        payload = _artisan_service_payload(form.cleaned_data, self.locations)
        self.assertEqual(payload['service_name'], 'Pipe repair')
        self.assertIsNone(payload['location'])
        self.assertEqual(_location_id_for_service(None, self.locations), '__anywhere__')

    def test_registered_location_payload_stays_exactly_within_existing_api_contract(self):
        form = ArtisanServiceForm(
            data={
                'category_name': 'Plumbing',
                'service_name': 'Pipe repair',
                'location_id': 'loc-yaba',
                'location_country_filter': 'Nigeria',
                'location_state_filter': 'Lagos',
                'location_area_filter': 'Yaba',
                'institution': '',
            },
            categories=self.categories,
            services=self.services,
            locations=self.locations,
        )

        self.assertTrue(form.is_valid(), form.errors)
        payload = _artisan_service_payload(form.cleaned_data, self.locations)
        self.assertEqual(payload['location'], {'country': 'Nigeria', 'state': 'Lagos', 'area': 'Yaba'})

    def test_service_filter_links_preserve_location_and_send_filter_state_to_api_search(self):
        categories = _discovery_categories(
            [{'name': 'Home Repair'}],
            [{'name': 'Plumbing', 'category_name': 'Home Repair'}],
            {
                'q': 'pipe repair',
                'state': 'Lagos',
                'area': 'Ikeja',
                'sort_by': 'rating',
                'sort_then': '',
                'min_rating': '',
                'verified_only': '',
                'availability': 'local',
                'category_name': '',
                'service_name': '',
                'country': 'Nigeria',
            },
        )

        service_url = categories[0]['services'][0]['url']
        query = parse_qs(urlparse(service_url).query)
        self.assertEqual(query['category_name'], ['Home Repair'])
        self.assertEqual(query['service_name'], ['Plumbing'])
        self.assertEqual(query['state'], ['Lagos'])
        self.assertEqual(query['area'], ['Ikeja'])
        self.assertEqual(query['availability'], ['local'])
        self.assertEqual(query['sort_by'], ['rating'])
