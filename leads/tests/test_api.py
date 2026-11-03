import csv
from io import BytesIO, StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from openpyxl import load_workbook

from leads.models import Lead


class ApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user('reviewer', is_staff=True)
        cls.lead = Lead.objects.create(company_name='=HYPERLINK("https://bad.invalid")', domain='acme.com')

    def setUp(self):
        self.client.force_login(self.staff)

    def test_anonymous_endpoints_are_protected(self):
        client = Client()
        self.assertEqual(client.get('/').status_code, 302)
        self.assertEqual(client.get('/export/csv/').status_code, 302)
        self.assertEqual(client.get('/export/excel/').status_code, 302)
        self.assertEqual(client.post('/api/prospect/', '{}', content_type='application/json').status_code, 403)

    def test_non_staff_cannot_access_api(self):
        user = get_user_model().objects.create_user('ordinary')
        self.client.force_login(user)
        self.assertEqual(self.client.get('/api/task/abc/').status_code, 403)

    def test_csrf_is_enforced_and_dashboard_supplies_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.staff)
        url = reverse('leads:api_update_status', args=[self.lead.pk])
        self.assertEqual(client.post(url, '{}', content_type='application/json').status_code, 403)
        response = client.get('/')
        self.assertContains(response, '/static/leads/js/dashboard.js')
        token = client.cookies['csrftoken'].value
        response = client.post(url, {'status': 'WON'}, content_type='application/json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, 'WON')

    def test_bad_input_returns_400_without_starting_worker(self):
        cases = [[], {'query': 12}, {'query': 'x', 'countries': [4]},
                 {'query': 'x', 'max_results': 'NaN'}, {'query': 'x', 'max_results': 0},
                 {'query': 'x', 'max_results': 1.5}, {'query': 'x', 'max_results': True}]
        with patch('leads.views.api.start_job') as start:
            for case in cases:
                with self.subTest(case=case):
                    self.assertEqual(self.client.post('/api/prospect/', case, content_type='application/json').status_code, 400)
            start.assert_not_called()
        self.assertEqual(self.client.post('/api/prospect/', '{', content_type='application/json').status_code, 400)

    @patch('leads.views.api.start_job', return_value='task-id')
    def test_valid_prospecting_request(self, start):
        response = self.client.post('/api/prospect/', {'query': 'Dental', 'countries': ['UK'], 'max_results': '10'}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        start.assert_called_once_with('Dental', '', ['UK'], 10, self.staff.pk)

    @patch('leads.views.api.start_job', side_effect=RuntimeError('Busy'))
    def test_busy_runner_returns_429(self, start):
        self.assertEqual(self.client.post('/api/prospect/', {'query': 'Dental'}, content_type='application/json').status_code, 429)

    def test_status_validation_and_missing_lead(self):
        url = reverse('leads:api_update_status', args=[self.lead.pk])
        self.assertEqual(self.client.post(url, {'status': 'INVALID'}, content_type='application/json').status_code, 400)
        self.assertEqual(self.client.post(url, {'notes': []}, content_type='application/json').status_code, 400)
        self.assertEqual(self.client.post('/api/lead/9999/status/', {}, content_type='application/json').status_code, 404)

    def test_formula_injection_is_neutralized_in_both_exports(self):
        csv_response = self.client.get('/export/csv/')
        rows = list(csv.reader(StringIO(csv_response.content.decode())))
        self.assertTrue(rows[1][0].startswith("'="))
        xlsx_response = self.client.get('/export/excel/')
        book = load_workbook(BytesIO(xlsx_response.content))
        self.assertEqual(book.active['A2'].data_type, 's')
        self.assertTrue(book.active['A2'].value.startswith("'="))

    def test_combined_dashboard_filters(self):
        Lead.objects.create(company_name='UK Dental', domain='dental.co.uk', country='UK', has_android_app=False, android_status='not_detected')
        Lead.objects.create(company_name='US Dental', domain='dental.com', country='US', has_android_app=False, android_status='not_detected')
        response = self.client.get('/?country=UK&gap=missing_app&q=Dental')
        self.assertEqual([lead.company_name for lead in response.context['leads']], ['UK Dental'])
