import os
import socket
from unittest.mock import patch, Mock

import httpx
from django.test import SimpleTestCase, TestCase

from leads.models import Lead
from leads.scraper.auditor import audit_server_and_speed
from leads.scraper.finder import search_duckduckgo_city, search_nominatim_city
from leads.scraper.network import fetch_public, validate_public_url
from leads.scraper.pipeline import process_single_lead
from leads.scraper.pitch_generator import generate_cold_pitch
from leads.scraper.validator import clean_domain, verify_domain_mx
from leads.templatetags.lead_links import safe_external_url


class NetworkTests(SimpleTestCase):
    def test_private_and_unsafe_urls_are_rejected(self):
        for url in ('file:///etc/passwd', 'http://localhost', 'http://user:pass@acme.com', 'http://acme.com:8000'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_public_url(url)
        for address in ('127.0.0.1', '10.0.0.1', '169.254.169.254', '::1'):
            with patch('leads.scraper.network.socket.getaddrinfo', return_value=[(socket.AF_INET, 1, 6, '', (address, 80))]):
                with self.assertRaises(ValueError):
                    validate_public_url('http://acme.com')

    @patch('leads.scraper.network.socket.getaddrinfo', return_value=[(socket.AF_INET, 1, 6, '', ('8.8.8.8', 443))])
    def test_public_domain_is_normalized(self, resolve):
        self.assertEqual(validate_public_url('acme.com'), 'https://acme.com')

    @patch('leads.scraper.network.validate_public_url', side_effect=lambda url: url)
    def test_fetch_follows_redirect_and_bounds_body(self, validate):
        def handler(request):
            if request.url.path == '/':
                return httpx.Response(302, headers={'location': '/about'})
            return httpx.Response(200, text='abc')
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            response = fetch_public(client, 'https://acme.com')
            self.assertEqual(response.text, 'abc')
            self.assertEqual(str(response.url), 'https://acme.com/about')
            self.assertIn('headers_elapsed_ms', response.extensions)
            with self.assertRaises(ValueError):
                fetch_public(client, 'https://acme.com', max_bytes=2)

    def test_redirect_to_private_destination_is_blocked(self):
        def validate(url):
            if '127.0.0.1' in url:
                raise ValueError('Private')
            return url
        with patch('leads.scraper.network.validate_public_url', side_effect=validate):
            with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(302, headers={'location': 'http://127.0.0.1/'}))) as client:
                with self.assertRaises(ValueError):
                    fetch_public(client, 'https://acme.com')

    @patch('leads.scraper.auditor.fetch_public', side_effect=ValueError('Failed'))
    def test_failed_fetch_does_not_invent_latency(self, fetch):
        result = audit_server_and_speed('https://acme.com')
        self.assertEqual(result['server_response_time_ms'], 0)
        self.assertFalse(result['ssl_active'])


class ScraperTests(SimpleTestCase):
    def test_registered_domain_uses_local_suffix_data(self):
        self.assertEqual(clean_domain('https://www.clinic.co.uk/contact'), 'clinic.co.uk')

    @patch('leads.scraper.validator.dns.resolver.Resolver')
    def test_mx_check_preserves_email_subdomain_and_no_socket_fallback(self, resolver):
        resolver.return_value.resolve.side_effect = Exception('No MX')
        result = verify_domain_mx('mail.clinic.co.uk')
        resolver.return_value.resolve.assert_called_once_with('mail.clinic.co.uk', 'MX')
        self.assertFalse(result['has_mx'])

    def test_pitches_do_not_claim_prototypes_already_exist(self):
        for has_website in (True, False):
            _, body = generate_cold_pitch({'company_name': 'Clinic', 'has_website': has_website})
            self.assertNotIn('already put together', body)
            self.assertNotIn('actually created', body)
            self.assertNotIn('great reviews', body)

    def test_unsafe_scraped_links_are_not_rendered(self):
        self.assertEqual(safe_external_url('javascript:alert(1)//linkedin.com/company/x'), '#')
        self.assertEqual(safe_external_url('https://linkedin.com/company/x'), 'https://linkedin.com/company/x')

    @patch.dict(os.environ, {}, clear=True)
    def test_public_nominatim_is_not_used_by_default(self):
        client = Mock()
        self.assertEqual(search_nominatim_city('dentist', 'London', 'UK', client, set(), 10), [])
        client.get.assert_not_called()

    def test_duckduckgo_redirect_link_is_unwrapped(self):
        client = Mock()
        client.post.return_value = httpx.Response(200, text='<tr><td><a class="result-link" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Facme.com">Acme</a></td></tr>')
        leads = search_duckduckgo_city('dentist', 'London', 'UK', client, set(), 1)
        self.assertEqual(leads[0]['domain'], 'acme.com')


class PipelineTests(TestCase):
    @patch('leads.scraper.pipeline.run_full_tech_audit', return_value={})
    @patch('leads.scraper.pipeline.crawl_website', return_value={})
    def test_website_flag_is_updated_without_losing_status_and_notes(self, crawl, audit):
        Lead.objects.create(company_name='Acme', domain='acme.com', has_website=False, status='WON', notes='Keep')
        lead = process_single_lead({'company_name': 'Acme', 'website': 'https://acme.com'})
        self.assertTrue(lead.has_website)
        self.assertEqual(lead.status, 'WON')
        self.assertEqual(lead.notes, 'Keep')
