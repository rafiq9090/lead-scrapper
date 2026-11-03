"""Ground-truth fixtures exercise extraction precision and failed-refresh behavior."""
import csv
import gzip
import json
from io import BytesIO, StringIO
from unittest.mock import Mock, patch

import httpx
from bs4 import BeautifulSoup
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.core.management import call_command
from openpyxl import load_workbook

from leads.models import Lead
from leads.scraper.contacts import extract_page, social_profile
from leads.scraper.crawler import crawl_website, discover_contact_links
from leads.scraper.auditor import audit_android_app, audit_chatbot_and_agents, match_computer_vision_opportunity
from leads.scraper.finder import search_duckduckgo_city
from leads.scraper.network import fetch_public
from leads.scraper.pipeline import process_single_lead
from leads.scraper.validator import sanitize_phone, verify_domain_mx, is_valid_email_deep

BUSINESS = {
    '@context': 'https://schema.org', '@graph': [
        {'@type': 'WebPage', 'name': 'Wrong page title'},
        {'@type': 'Person', 'name': 'Wrong person', 'email': 'person@acmeclinic.com'},
        {'@type': 'Dentist', 'name': 'Acme Clinic', 'legalName': 'Acme Dental Ltd',
         'url': 'https://www.acmeclinic.com', 'address': {'@id': '#address'},
         'contactPoint': {'@id': '#contact'}, 'sameAs': ['https://www.instagram.com/acmeclinic/'],
         'openingHoursSpecification': {'dayOfWeek': ['https://schema.org/Monday'], 'opens': '09:00', 'closes': '17:00'}},
        {'@id': '#address', '@type': 'PostalAddress', 'streetAddress': '1 High Street',
         'addressLocality': 'London', 'postalCode': 'AB1 2CD', 'addressCountry': {'@type': 'Country', 'name': 'GB'}},
        {'@id': '#contact', '@type': 'ContactPoint', 'telephone': '+44 (20) 7946 0123', 'email': ['info@acmeclinic.com', 'office@acmeclinic.com']},
    ]
}


class ExtractionQualityTests(SimpleTestCase):
    def test_nested_business_schema_selects_business_and_resolves_references(self):
        result = extract_page('<script type="application/ld+json">' + json.dumps(BUSINESS) + '</script>', 'https://www.acmeclinic.com/')
        self.assertEqual(result['legal_name'], 'Acme Dental Ltd')
        self.assertEqual(result['addresses'], ['1 High Street, London, AB1 2CD, GB'])
        self.assertEqual(result['country'], 'GB')
        self.assertEqual(result['opening_hours'], ['Monday: 09:00–17:00'])
        emails = {e['value'] for e in result['evidence'] if e['field'] == 'email'}
        self.assertEqual(emails, {'info@acmeclinic.com', 'office@acmeclinic.com'})
        self.assertTrue(all(e['url'] == 'https://www.acmeclinic.com/' for e in result['evidence']))

    def test_text_contacts_ignore_analytics_images_and_nonphone_numbers(self):
        html = '''<script>let tracker="analytics@acmeclinic.com"; const account=123456789;</script>
        <style>.foo { content: "css@acmeclinic.com"; }</style><img src="logo@2x.png">
        <p>Contact: hello [at] acmeclinic [dot] com</p><p>Phone: +44 (20) 7946 0123</p>
        <p>Account: 987654321</p><p>Established: 2024-10-05</p>
        <a href="mailto:office%40acmeclinic.com?subject=Hi">Email us</a>
        <a href="tel:+442079460123">Telephone</a>'''
        result = extract_page(html, 'https://acmeclinic.com/contact')
        self.assertEqual({e['value'] for e in result['evidence'] if e['field'] == 'email'},
                         {'hello@acmeclinic.com', 'office@acmeclinic.com'})
        self.assertEqual({e['value'] for e in result['evidence'] if e['field'] == 'phone'}, {'+442079460123'})

    def test_social_links_require_real_host_and_profile_path(self):
        for value in ['https://linkedin.com.evil.test/company/acme', 'https://evil.test/linkedin.com/company/acme',
                      'javascript:alert(1)//facebook.com/acme', 'https://instagram.com/p/abc',
                      'https://facebook.com/sharer.php?u=acme', 'https://x.com/acme/status/123']:
            with self.subTest(value=value):
                self.assertIsNone(social_profile(value))
        self.assertEqual(social_profile('https://facebook.com/profile.php?id=123&utm_source=x')[1], 'https://www.facebook.com/profile.php?id=123')

    def test_phone_normalization_keeps_extension_without_inventing_country(self):
        self.assertEqual(sanitize_phone('020 7946 0123 ext. 45'), '02079460123 ext. 45')
        self.assertEqual(sanitize_phone('0044 20 7946 0123'), '+442079460123')
        self.assertEqual(sanitize_phone('2024-10-05'), '')
        self.assertEqual(sanitize_phone({'bad': 'type'}), '')

    def test_real_long_email_is_not_removed_by_arbitrary_85_character_limit(self):
        self.assertTrue(is_valid_email_deep('a' * 60 + '@' + 'b' * 40 + '.com'))
        self.assertFalse(is_valid_email_deep('bad..dots@acmeclinic.com'))

    def test_contact_links_keep_path_and_prioritize_contact(self):
        soup = BeautifulSoup('<a href="/about">About</a><a href="contact?lang=en">Contact</a><a href="https://evil.test/contact">External</a>', 'html.parser')
        links = discover_contact_links(soup, 'https://www.acmeclinic.com/en/')
        self.assertEqual(links[0], 'https://www.acmeclinic.com/en/contact')
        self.assertEqual(len(links), 2)

    @patch('leads.scraper.crawler.verify_domain_mx', return_value={'status': 'mx_found', 'has_mx': True, 'provider': 'Mail'})
    @patch('leads.scraper.crawler.fetch_public')
    def test_crawl_follows_redirected_contact_pages_and_preserves_requested_path(self, fetch, mx):
        responses = [
            httpx.Response(200, headers={'content-type': 'text/html'}, text='<p>Welcome to Acme Clinic, offering dental care.</p><a href="contact">Contact</a>', request=httpx.Request('GET', 'https://www.acmeclinic.com/en/')),
            httpx.Response(200, headers={'content-type': 'text/html'}, text='<p>Our contact page for Acme Clinic</p><a href="mailto:info@acmeclinic.com">Email</a>', request=httpx.Request('GET', 'https://www.acmeclinic.com/en/contact')),
        ]
        fetch.side_effect = responses
        result = crawl_website('http://acmeclinic.com/en/')
        self.assertEqual(fetch.call_args_list[0].args[1], 'http://acmeclinic.com/en/')
        self.assertEqual(fetch.call_args_list[1].args[1], 'https://www.acmeclinic.com/en/contact')
        self.assertEqual(result['audit_status'], 'complete')
        self.assertEqual(result['primary_email'], 'info@acmeclinic.com')
        self.assertEqual(result['evidence'][0]['url'], 'https://www.acmeclinic.com/en/contact')

    @patch('leads.scraper.crawler.fetch_public')
    def test_access_challenge_is_failed_instead_of_empty_success(self, fetch):
        fetch.return_value = httpx.Response(200, headers={'content-type': 'text/html'}, text='<title>Just a moment...</title><p>Verify</p>', request=httpx.Request('GET', 'https://acmeclinic.com'))
        result = crawl_website('https://acmeclinic.com')
        self.assertEqual(result['audit_status'], 'failed')
        self.assertEqual(result['combined_html'], '')
        self.assertIn('challenge', result['pages'][0]['reason'])

    def test_app_links_validate_exact_store_host_and_package(self):
        self.assertEqual(audit_android_app('Acme', 'acme.com', '<a href="https://play.google.com.evil.test/store/apps/details?id=com.acme.app">App</a>')['status'], 'not_detected')
        self.assertEqual(audit_android_app('Acme', 'acme.com', '')['status'], 'unknown')
        result = audit_android_app('Acme', 'acme.com', '<meta name="google-play-app" content="app-id=com.acme.app">')
        self.assertEqual(result['status'], 'detected')
        self.assertEqual(result['android_app_url'], 'https://play.google.com/store/apps/details?id=com.acme.app')

    def test_chat_blog_mentions_do_not_count_as_widget(self):
        self.assertEqual(audit_chatbot_and_agents('<p>We compare Intercom, Tidio and Drift.</p>')['status'], 'not_detected')
        self.assertEqual(audit_chatbot_and_agents('')['status'], 'unknown')
        self.assertEqual(audit_chatbot_and_agents('<script src="https://embed.tawk.to/site/default"></script>')['status'], 'detected')
        self.assertEqual(audit_chatbot_and_agents('<script src="https://embed.tawk.to.evil.test/x"></script>')['status'], 'not_detected')

    def test_generic_html_does_not_invent_cv_opportunity(self):
        self.assertEqual(match_computer_vision_opportunity('Software', '<p>car health store dental</p>'), '')
        self.assertIn('Package', match_computer_vision_opportunity('Logistics'))

    def test_rating_stays_self_reported_and_rating_count_is_not_review_count(self):
        html = '<script type="application/ld+json">' + json.dumps({
            '@type': 'Dentist', 'name': 'Acme', 'aggregateRating': {
                'ratingValue': '4.7', 'bestRating': '5', 'ratingCount': '12'}}) + '</script>'
        result = extract_page(html, 'https://acmeclinic.com')
        self.assertEqual(result['rating']['value'], 4.7)
        self.assertEqual(result['rating']['rating_count'], 12)
        self.assertNotIn('review_count', result['rating'])
        self.assertIn('self-reported', result['rating']['source'])

    @patch('leads.scraper.network.validate_public_url', side_effect=lambda url: url)
    @patch('leads.scraper.network.time.sleep')
    def test_gzip_and_transient_retry(self, sleep, validate):
        calls = []
        def handler(request):
            calls.append(request)
            if len(calls) == 1:
                return httpx.Response(503, headers={'retry-after': '0'})
            return httpx.Response(200, headers={'content-encoding': 'gzip'}, content=gzip.compress(b'hello'))
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            self.assertEqual(fetch_public(client, 'https://acmeclinic.com').text, 'hello')
        self.assertEqual(len(calls), 2)

    @patch('leads.scraper.validator.dns.resolver.Resolver')
    def test_null_mx_does_not_claim_mail_delivery(self, resolver):
        resolver.return_value.resolve.return_value = [Mock(preference=0, exchange='.')]
        result = verify_domain_mx('acmeclinic.com')
        self.assertFalse(result['has_mx'])
        self.assertEqual(result['status'], 'null_mx')

    def test_discovery_preserves_website_and_does_not_invent_business_country(self):
        client = Mock()
        client.post.return_value = httpx.Response(200, text='<tr><td><a class="result-link" href="http://branch.acmeclinic.com/en/">Acme</a></td></tr><tr><td class="result-snippet">Call +44 20 7946 0123</td></tr>')
        lead = search_duckduckgo_city('dentist', 'London', 'UK', client, set(), 1)[0]
        self.assertEqual(lead['website'], 'http://branch.acmeclinic.com/en/')
        self.assertEqual(lead['phone'], '+442079460123')
        self.assertEqual(lead['country'], '')
        self.assertEqual(lead['address'], '')


class QualityPersistenceTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user('staff', is_staff=True)
        self.client.force_login(user)

    @patch('leads.scraper.pipeline.crawl_website', return_value={'audit_status': 'failed', 'pages': [{'url': 'https://acmeclinic.com', 'status': 'failed'}]})
    def test_failed_refresh_keeps_contacts_but_does_not_create_gap_score(self, crawl):
        lead = Lead.objects.create(company_name='Acme', domain='acmeclinic.com', website='https://acmeclinic.com',
                                   phone='+442079460123', primary_email='info@acmeclinic.com', all_emails=['info@acmeclinic.com'],
                                   status='WON', notes='Keep this', has_android_app=True)
        result = process_single_lead({'company_name': 'Acme', 'website': lead.website}, lead_id=lead.pk)
        self.assertEqual(result.pk, lead.pk)
        self.assertEqual(result.primary_email, lead.primary_email)
        self.assertEqual(result.phone, lead.phone)
        self.assertEqual(result.status, 'WON')
        self.assertEqual(result.notes, 'Keep this')
        self.assertEqual(result.android_status, 'unknown')
        self.assertEqual(result.chatbot_status, 'unknown')
        self.assertEqual(result.lead_score, 20)
        self.assertIn('primary_email', result.audit_report['retained_fields'])
        self.assertNotIn('did not find an Android', result.pitch_email)

    @patch('leads.scraper.pipeline.crawl_website')
    def test_structured_fields_are_saved_and_exported_with_evidence(self, crawl):
        crawl.return_value = {'audit_status': 'complete', 'legal_name': 'Acme Dental Ltd', 'country': 'GB',
                             'structured_address': '1 High Street', 'addresses': ['1 High Street'],
                             'opening_hours': ['Monday: 09:00–17:00'], 'description': 'Dental clinic',
                             'all_phones': ['+442079460123'], 'phone': '+442079460123',
                             'combined_html': '<p>Acme Clinic provides dental care.</p>',
                             'evidence': [{'field': 'phone', 'value': '+442079460123', 'url': 'https://acmeclinic.com/contact', 'method': 'tel', 'confidence': 'high'}]}
        lead = process_single_lead({'company_name': 'Search title', 'website': 'https://acmeclinic.com', 'niche': 'Dental'})
        self.assertEqual(lead.company_name, 'Acme Dental Ltd')
        self.assertEqual(lead.address, '1 High Street')
        self.assertEqual(lead.opening_hours, ['Monday: 09:00–17:00'])
        self.assertEqual(lead.android_status, 'not_detected')
        response = self.client.get(f'/lead/{lead.pk}/')
        self.assertContains(response, '1 High Street')
        self.assertContains(response, 'https://acmeclinic.com/contact')
        book = load_workbook(BytesIO(self.client.get('/export/excel/').content))
        self.assertEqual(book.sheetnames, ['B2B Leads', 'Source Evidence', 'Pages Checked'])
        self.assertEqual(book['Source Evidence']['C2'].value, 'phone')

    def test_unreviewed_leads_do_not_appear_in_negative_gap_filters(self):
        lead = Lead.objects.create(company_name='Legacy', domain='legacy.com', lead_score=100)
        self.assertEqual(list(self.client.get('/?gap=missing_app').context['leads']), [])
        self.assertEqual(list(self.client.get('/?gap=high_score').context['leads']), [])
        self.assertContains(self.client.get(f'/lead/{lead.pk}/'), 'Needs re-audit')

    def test_pagination_and_filtered_exports_include_all_matching_records(self):
        Lead.objects.bulk_create([Lead(company_name=f'Clinic {i}', domain=f'clinic{i}.com', country='GB') for i in range(55)])
        Lead.objects.create(company_name='Other', domain='other.com', country='US')
        page = self.client.get('/?country=GB&page=2')
        self.assertEqual(len(page.context['leads']), 5)
        rows = list(csv.reader(StringIO(self.client.get('/export/csv/?country=GB').content.decode())))
        self.assertEqual(len(rows), 56)
        self.assertNotIn('Other', [row[0] for row in rows[1:]])

    @patch('leads.views.detail.process_single_lead')
    def test_reaudit_is_staff_only_post_and_keeps_existing_record_identity(self, process):
        lead = Lead.objects.create(company_name='Acme', domain='acmeclinic.com', website='https://acmeclinic.com')
        self.assertEqual(self.client.get(f'/lead/{lead.pk}/reaudit/').status_code, 405)
        response = self.client.post(f'/lead/{lead.pk}/reaudit/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(process.call_args.kwargs['lead_id'], lead.pk)

    @patch('leads.management.commands.reaudit_leads.process_single_lead')
    def test_bulk_reaudit_dry_run_never_fetches_or_changes_records(self, process):
        lead = Lead.objects.create(company_name='Acme', domain='acmeclinic.com', website='https://acmeclinic.com')
        output = StringIO()
        call_command('reaudit_leads', '--dry-run', '--limit', '1', stdout=output)
        process.assert_not_called()
        lead.refresh_from_db()
        self.assertEqual(lead.audit_status, 'unreviewed')
        self.assertIn('Dry run; no requests or changes.', output.getvalue())
