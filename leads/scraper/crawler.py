"""Bounded first-party crawl with per-page outcomes and contact provenance."""
import time
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup
from .contacts import extract_page
from .network import fetch_public
from .validator import clean_domain, verify_domain_mx

HEADERS = {'User-Agent': 'DevLead/1.0 (business website contact research)',
           'Accept': 'text/html,application/xhtml+xml', 'Accept-Language': 'en-US,en;q=0.9'}


def _same_site(first, second):
    return (urlsplit(first).hostname or '').lower().removeprefix('www.') == (
        urlsplit(second).hostname or '').lower().removeprefix('www.')


def discover_contact_links(soup, base_url):
    candidates = {}
    for anchor in soup.select('a[href]'):
        try:
            url = urljoin(base_url, anchor.get('href', ''))
            parsed = urlsplit(url)
            if parsed.scheme not in ('http', 'https') or not _same_site(url, base_url):
                continue
            label = f'{parsed.path} {anchor.get_text(" ", strip=True)}'.lower()
            rank = next((i for i, word in enumerate(('contact', 'location', 'about', 'team', 'connect', 'kontakt', 'contacto')) if word in label), None)
            if rank is not None:
                query = parsed.query if not parsed.path.strip('/') or 'page=' in parsed.query else ''
                cleaned = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ''))
                candidates[cleaned] = rank
        except ValueError:
            continue
    return sorted(candidates, key=lambda url: (candidates[url], url))[:12]


def crawl_website(url, timeout=8.0, max_pages=8, fast_mode=False):
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    if fast_mode:
        max_pages = min(int(max_pages), 2)
        timeout = min(float(timeout), 4.0)
    else:
        max_pages = max(1, min(int(max_pages), 12))
    started = time.monotonic()
    max_budget = 12 if fast_mode else 60
    queue, visited, pages, evidence, corpus = [url], set(), [], [], []
    html_pages = []
    warnings, addresses, hours = [], [], []
    legal_name = description = country = ''
    homepage = None
    rating = {}
    site_url = url
    with httpx.Client(headers=HEADERS, timeout=timeout, follow_redirects=False, trust_env=False) as client:
        while queue and len(visited) < max_pages:
            if time.monotonic() - started > max_budget:
                warnings.append('Crawl time budget reached; some pages were not checked.')
                break
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            try:
                response = fetch_public(client, current)
                final_url = str(response.url)
                if current == url:
                    site_url = final_url
                elif not _same_site(final_url, site_url):
                    raise ValueError('Contact page redirected outside the business website.')
                if 'html' not in response.headers.get('content-type', '').lower():
                    raise ValueError('Response is not HTML.')
                html = response.text
                soup = BeautifulSoup(html, 'html.parser')
                title = soup.title.get_text(' ', strip=True).lower() if soup.title else ''
                if any(marker in title for marker in ('just a moment', 'access denied', 'verify you are human', 'attention required')):
                    raise ValueError('Website returned a challenge or access-denied page.')
                extracted = extract_page(html, final_url)
                if len(extracted['visible_text'].strip()) < 30 and not extracted['evidence']:
                    raise ValueError('Insufficient readable content; page may require JavaScript.')
                pages.append({'url': final_url, 'status': 'ok', 'http_status': response.status_code})
                corpus.append(html)
                html_pages.append({'url': final_url, 'html': html})
                evidence.extend(extracted['evidence'])
                legal_name = legal_name or extracted['legal_name']
                description = description or extracted['description']
                country = country or extracted['country']
                rating = rating or extracted['rating']
                addresses.extend(a for a in extracted['addresses'] if a not in addresses)
                hours.extend(h for h in extracted['opening_hours'] if h not in hours)
                if current == url:
                    homepage = {'url': final_url, 'headers': dict(response.headers), 'html': html,
                                'response_time_ms': response.extensions.get('headers_elapsed_ms', 0)}
                for link in discover_contact_links(soup, final_url):
                    if link not in visited and link not in queue:
                        queue.append(link)
                if current == url and not queue:
                    queue.extend(urljoin(final_url, path) for path in ('/contact', '/contact-us', '/about', '/about-us'))
            except (httpx.HTTPError, ValueError, OSError) as exc:
                code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
                pages.append({'url': current, 'status': 'failed', 'http_status': code, 'reason': str(exc)[:240]})
        if queue:
            warnings.append(f'Crawl stopped at its page/time budget; additional links were not checked.')

    target_domain = clean_domain(site_url)
    def rank(item):
        is_email = item['field'] == 'email'
        same_domain = is_email and clean_domain(item['value'].split('@')[-1]) == target_domain
        role = is_email and item['value'].split('@')[0] in ('info', 'contact', 'hello', 'office', 'sales', 'enquiries')
        return (not same_domain if is_email else False, item['confidence'] != 'high', not role, item['value'])

    evidence.sort(key=rank)
    emails = list(dict.fromkeys(e['value'] for e in evidence if e['field'] == 'email'))
    phones = list(dict.fromkeys(e['value'] for e in evidence if e['field'] == 'phone'))
    socials = {name: next((e['value'] for e in evidence if e['field'] == name), '')
               for name in ('linkedin', 'facebook', 'instagram', 'twitter')}
    mx = verify_domain_mx(emails[0].split('@')[1]) if emails else {'status': 'not_checked', 'provider': '', 'has_mx': False}
    success_count = sum(page['status'] == 'ok' for page in pages)
    status = 'failed' if not success_count else 'partial' if warnings or any(p['status'] == 'failed' for p in pages) else 'complete'
    return {'primary_email': emails[0] if emails else '', 'all_emails': emails,
            'phone': phones[0] if phones else '', 'all_phones': phones,
            'legal_name': legal_name, 'structured_address': addresses[0] if addresses else '',
            'addresses': addresses, 'country': country, 'description': description,
            'opening_hours': hours, 'social_links': socials, 'combined_html': '\n'.join(corpus),
            'mail_provider': mx.get('provider', ''), 'email_dns': mx, 'pages': pages,
            'evidence': evidence, 'warnings': warnings, 'audit_status': status,
            'homepage': homepage, 'final_url': site_url, 'html_pages': html_pages, 'rating': rating}


def parse_json_ld_metadata(soup):
    result = extract_page(str(soup), '')
    records = [item for item in result['evidence'] if item['method'] == 'json_ld']
    return {'legal_name': result['legal_name'], 'address': next(iter(result['addresses']), ''),
            'emails': {e['value'] for e in records if e['field'] == 'email'},
            'phones': {e['value'] for e in records if e['field'] == 'phone'},
            'socials': {e['field']: e['value'] for e in records if e['field'] in ('linkedin', 'facebook', 'instagram', 'twitter')}}
