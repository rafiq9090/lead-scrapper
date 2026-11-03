"""Evidence-based technical checks. A negative scan never proves absence."""
import re
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
from bs4 import BeautifulSoup
from .network import fetch_public

HEADERS = {'User-Agent': 'DevLead/1.0 (business website technical research)'}
WIDGET_HOSTS = {
    'intercom.io': 'Intercom', 'intercomcdn.com': 'Intercom', 'tidio.co': 'Tidio',
    'tidiochat.com': 'Tidio', 'zdassets.com': 'Zendesk', 'zopim.com': 'Zendesk/Zopim',
    'driftt.com': 'Drift', 'crisp.chat': 'Crisp', 'livechatinc.com': 'LiveChat',
    'freshchat.com': 'Freshchat', 'tawk.to': 'Tawk.to', 'chaport.com': 'Chaport',
    'chatwoot.com': 'Chatwoot', 'botpress.cloud': 'Botpress', 'voiceflow.com': 'Voiceflow',
    'gorgias.chat': 'Gorgias', 'olark.com': 'Olark', 'beacon-v2.helpscout.net': 'HelpScout',
    'qualified.com': 'Qualified', 'smartsuppchat.com': 'Smartsupp', 'landbot.io': 'Landbot',
    'userlike.com': 'Userlike', 'reamaze.com': 'Re:amaze', 'trengo.eu': 'Trengo',
    'collect.chat': 'Collect.chat', 'ada.support': 'Ada', 'salesiq.zoho.com': 'Zoho SalesIQ',
}
CMS_SIGNATURES = {'wp-content/': 'WordPress', 'cdn.shopify.com': 'Shopify', 'wixstatic.com': 'Wix',
                  'assets.squarespace.com': 'Squarespace', 'webflow.js': 'Webflow',
                  '/_next/': 'Next.js', '/_nuxt/': 'Nuxt.js', 'woocommerce': 'WooCommerce'}


def _play_url(value):
    try:
        parsed = urlsplit(value)
        package = parse_qs(parsed.query).get('id', [''])[0]
        if parsed.scheme in ('https', 'http') and parsed.hostname == 'play.google.com' and parsed.path == '/store/apps/details' and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+', package):
            return 'https://play.google.com/store/apps/details?' + urlencode({'id': package})
    except ValueError:
        pass
    return ''


def audit_android_app(company_name, domain, html_corpus=''):
    result = {'has_android_app': False, 'android_app_name': '', 'android_app_url': '',
              'status': 'not_detected' if html_corpus else 'unknown',
              'evidence': 'No app link in checked HTML.' if html_corpus else 'No readable website pages.'}
    soup = BeautifulSoup(html_corpus, 'html.parser')
    for anchor in soup.select('a[href]'):
        app_url = _play_url(anchor.get('href', ''))
        if app_url:
            return {**result, 'has_android_app': True, 'android_app_name': f'{company_name} website-linked app',
                    'android_app_url': app_url, 'status': 'detected', 'evidence': 'Google Play link published on the business website.'}
    for meta in soup.find_all('meta', attrs={'name': re.compile('^google-play-app$', re.I)}):
        match = re.search(r'app-id\s*=\s*([A-Za-z0-9_.]+)', meta.get('content', ''))
        app_url = _play_url('https://play.google.com/store/apps/details?id=' + match.group(1)) if match else ''
        if app_url:
            return {**result, 'has_android_app': True, 'android_app_name': f'{company_name} website-linked app',
                    'android_app_url': app_url, 'status': 'detected', 'evidence': 'Valid Android app ID in the website smart banner.'}
    return result


def audit_chatbot_and_agents(html_content):
    result = {'has_chatbot': False, 'detected_chat_widget': '',
              'status': 'not_detected' if html_content else 'unknown',
              'evidence': 'No known widget in checked HTML; client-rendered tools may be missed.' if html_content else 'No readable website pages.'}
    soup = BeautifulSoup(html_content, 'html.parser')
    for element in soup.select('script[src], iframe[src]'):
        src = element.get('src', '')
        try:
            host = (urlsplit('https:' + src if src.startswith('//') else src).hostname or '').lower()
        except ValueError:
            continue
        for domain, name in WIDGET_HOSTS.items():
            if host == domain or host.endswith('.' + domain):
                return {**result, 'has_chatbot': True, 'detected_chat_widget': name, 'status': 'detected',
                        'evidence': f'Widget resource: {src}'}
    # Specific initialization syntax, excluding JSON-LD and ordinary page text.
    for script in soup.find_all('script'):
        if script.get('type', '').lower() == 'application/ld+json':
            continue
        value = script.string or ''
        for pattern, name in ((r'\bIntercom\s*\(', 'Intercom'), (r'\bTawk_API\s*=', 'Tawk.to'),
                              (r'\bcrisp\s*\.\s*push\s*\(', 'Crisp'), (r'\bchatwootSDK\s*\.\s*run\s*\(', 'Chatwoot')):
            if re.search(pattern, value):
                return {**result, 'has_chatbot': True, 'detected_chat_widget': name, 'status': 'detected',
                        'evidence': f'{name} initialization script found.'}
    return result


def audit_server_and_speed(url, timeout=8.0, observation=None, fetch=True):
    result = {'server_response_time_ms': 0, 'server_type': 'Unknown', 'detected_cms': 'Unknown',
              'ssl_active': False, 'status': 'unknown', 'evidence': 'No successful homepage response.'}
    if observation is None and fetch:
        try:
            with httpx.Client(headers=HEADERS, timeout=timeout, follow_redirects=False, trust_env=False) as client:
                response = fetch_public(client, url)
                observation = {'url': str(response.url), 'headers': dict(response.headers), 'html': response.text,
                               'response_time_ms': response.extensions['headers_elapsed_ms']}
        except (httpx.HTTPError, ValueError, OSError):
            return result
    if not observation:
        return result
    header = observation.get('headers', {}).get('server', '')
    result.update(server_response_time_ms=observation.get('response_time_ms', 0),
                  server_type=header[:100] or 'Not disclosed', ssl_active=observation['url'].startswith('https://'),
                  status='measured', evidence='One response-header sample, including connection/redirect overhead.')
    html = observation.get('html', '').lower()
    for signature, cms in CMS_SIGNATURES.items():
        if signature in html:
            result['detected_cms'] = cms
            break
    return result


def match_computer_vision_opportunity(niche, html_corpus=''):
    # Only explicit industry input: generic page words and script names do not establish industry.
    niche = niche.lower()
    rules = [
        (r'\b(dental|dentals|dentist|dentists|orthodontist)\b', 'Dental imaging workflow assistance (requires clinical validation)'),
        (r'\b(logistics|freight|warehouse|shipping|courier|trucking)\b', 'Package label OCR and visual defect inspection'),
        (r'\b(real estate|property management|architecture)\b', 'Property photo organization and floorplan digitization'),
        (r'\b(retail|ecommerce|fashion|apparel)\b', 'Visual product search and inventory image analysis'),
        (r'\b(automotive|dealership|auto repair)\b', 'Vehicle damage photo assessment'),
        (r'\b(manufacturing|factory|industrial|construction)\b', 'Visual quality inspection and safety workflow assistance'),
        (r'\b(restaurant|restaurants|catering|hotel|hotels)\b', 'Food waste and occupancy analysis'),
    ]
    return next((suggestion for pattern, suggestion in rules if re.search(pattern, niche)), '')


def run_full_tech_audit(company_name, domain, website_url, html_content='', niche='', crawl_result=None):
    android = audit_android_app(company_name, domain, html_content)
    chatbot = audit_chatbot_and_agents(html_content)
    server = audit_server_and_speed(website_url, observation=(crawl_result or {}).get('homepage'), fetch=crawl_result is None)
    checks = {'android': {k: android[k] for k in ('status', 'evidence')},
              'chatbot': {k: chatbot[k] for k in ('status', 'evidence')},
              'server': {k: server[k] for k in ('status', 'evidence')}}
    for value in checks.values():
        value['url'] = (crawl_result or {}).get('final_url', website_url)
    for page in (crawl_result or {}).get('html_pages', []):
        if android['status'] == 'detected' and audit_android_app(company_name, domain, page['html'])['status'] == 'detected':
            checks['android']['url'] = page['url']
            break
    for page in (crawl_result or {}).get('html_pages', []):
        if chatbot['status'] == 'detected' and audit_chatbot_and_agents(page['html'])['status'] == 'detected':
            checks['chatbot']['url'] = page['url']
            break
    return {'has_android_app': android['has_android_app'], 'android_app_name': android['android_app_name'],
            'android_app_url': android['android_app_url'], 'android_status': android['status'],
            'has_chatbot': chatbot['has_chatbot'], 'detected_chat_widget': chatbot['detected_chat_widget'],
            'chatbot_status': chatbot['status'], **{k: server[k] for k in ('server_response_time_ms', 'server_type', 'detected_cms', 'ssl_active')},
            'cv_opportunity': match_computer_vision_opportunity(niche), 'checks': checks}
