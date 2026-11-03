"""Business contact extraction with field-level source evidence."""
import json
import math
import re
from urllib.parse import parse_qs, unquote, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup
from .validator import decode_cloudflare_email, is_valid_email_deep, sanitize_phone

EMAIL = re.compile(r"[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE = re.compile(r"(?<!\w)(?:\+|00)?\d[\d () .-]{5,}\d(?:\s*(?:ext\.?|x)\s*\d{1,6})?", re.I)
BUSINESS_TYPES = set('Organization Corporation LocalBusiness MedicalOrganization Dentist Physician MedicalClinic Hospital LegalService ProfessionalService RealEstateAgent Restaurant CafeOrCoffeeShop Hotel Store AutoRepair EducationalOrganization TravelAgency AccountingService FinancialService InsuranceAgency NGO'.split())
NON_BUSINESS_TYPES = set('Person Product Article NewsArticle WebPage WebSite Review BreadcrumbList BlogPosting ListItem'.split())


def as_list(value):
    return value if isinstance(value, list) else [value] if value is not None else []


def text_value(value):
    if isinstance(value, dict):
        return text_value(value.get('name', value.get('@value', '')))
    return str(value).strip() if isinstance(value, (str, int, float)) else ''


def social_profile(raw_url, base_url=''):
    if not isinstance(raw_url, str):
        return None
    try:
        parsed = urlsplit(urljoin(base_url, raw_url.strip()))
        if parsed.scheme not in ('http', 'https') or parsed.username or parsed.password:
            return None
        host = (parsed.hostname or '').lower().removeprefix('www.').removeprefix('m.')
        parts = [p for p in parsed.path.split('/') if p]
        if not parts:
            return None
        first = parts[0].lower()
        provider = {'linkedin.com': 'linkedin', 'facebook.com': 'facebook', 'instagram.com': 'instagram', 'twitter.com': 'twitter', 'x.com': 'twitter'}.get(host)
        if not provider:
            return None
        if provider == 'linkedin' and (first not in ('company', 'school') or len(parts) != 2):
            return None
        if provider == 'facebook':
            if first in ('sharer', 'sharer.php', 'share.php', 'plugins', 'login', 'dialog', 'watch', 'reel', 'groups'):
                return None
            if first == 'profile.php':
                profile_id = parse_qs(parsed.query).get('id', [''])[0]
                return (provider, f'https://www.facebook.com/profile.php?id={profile_id}') if profile_id.isdigit() else None
            if len(parts) != 1 and first != 'pages':
                return None
        if provider in ('instagram', 'twitter') and (len(parts) != 1 or first in ('p', 'reel', 'reels', 'explore', 'accounts', 'intent', 'share', 'search', 'home', 'i', 'login')):
            return None
        return provider, urlunsplit(('https', parsed.netloc.lower(), parsed.path.rstrip('/'), '', ''))
    except ValueError:
        return None


def _nodes(value, depth=0):
    if depth > 12:
        return
    if isinstance(value, dict):
        yield value
        for child in value.values():
            if isinstance(child, (list, dict)):
                yield from _nodes(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            yield from _nodes(child, depth + 1)


def extract_page(html, source_url):
    soup = BeautifulSoup(html, 'html.parser')
    evidence, seen = [], set()
    details = {'legal_name': '', 'description': '', 'country': '', 'opening_hours': [], 'addresses': [], 'rating': {}}

    def record(field, value, method, confidence='high'):
        if not value or not isinstance(value, str) or len(value) > 2000:
            return
        if field == 'email':
            value = unquote(value).removeprefix('mailto:').split('?')[0].strip().lower().rstrip('.,;')
            if not is_valid_email_deep(value):
                return
        if field == 'phone':
            value = sanitize_phone(value)
            if not value:
                return
        key = (field, value, method)
        if key not in seen:
            seen.add(key)
            evidence.append({'field': field, 'value': value, 'url': source_url, 'method': method, 'confidence': confidence})

    nodes = []
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            nodes.extend(_nodes(json.loads(script.string or script.get_text())))
        except (ValueError, TypeError, RecursionError):
            continue
    index = {node['@id']: node for node in nodes if isinstance(node.get('@id'), str)}

    def resolve(value):
        return {**index.get(value['@id'], {}), **value} if isinstance(value, dict) and isinstance(value.get('@id'), str) else value

    def business(node):
        kinds = {text_value(t).rsplit('/', 1)[-1] for t in as_list(node.get('@type'))}
        if kinds & NON_BUSINESS_TYPES and not kinds & BUSINESS_TYPES:
            return False
        candidate_url = text_value(node.get('url'))
        if source_url and candidate_url.startswith(('https://', 'http://')):
            try:
                same_host = (urlsplit(candidate_url).hostname or '').removeprefix('www.') == (urlsplit(source_url).hostname or '').removeprefix('www.')
            except ValueError:
                return False
            if not same_host:
                return False
        return bool(kinds & BUSINESS_TYPES or any(t.endswith(('Business', 'Store')) for t in kinds)
                    or (node.get('address') and node.get('telephone') and node.get('name') and not kinds & NON_BUSINESS_TYPES))

    businesses = sorted((node for node in nodes if business(node)), key=lambda n: (not bool(n.get('legalName')), not bool(n.get('address'))))
    for node in businesses:
        name = text_value(node.get('legalName') or node.get('name'))
        if name and not details['legal_name']:
            details['legal_name'] = name[:255]
            record('company_name', details['legal_name'], 'json_ld')
        description = text_value(node.get('description'))
        if description and not details['description']:
            details['description'] = description[:2000]
            record('description', details['description'], 'json_ld')
        rating = resolve(node.get('aggregateRating'))
        if isinstance(rating, dict) and not details['rating']:
            try:
                value = float(rating['ratingValue'])
                best = float(rating['bestRating']) if rating.get('bestRating') is not None else None
                worst = float(rating['worstRating']) if rating.get('worstRating') is not None else None
                if not math.isfinite(value) or value < 0 or (best is not None and (not math.isfinite(best) or value > best)) or (worst is not None and (not math.isfinite(worst) or value < worst)):
                    raise ValueError
                result = {'value': value, 'best': best, 'worst': worst, 'source': 'Website JSON-LD (self-reported)', 'url': source_url}
                for raw_key, key in (('reviewCount', 'review_count'), ('ratingCount', 'rating_count')):
                    count = str(rating.get(raw_key, ''))
                    if count.isdigit():
                        result[key] = min(int(count), 2147483647)
                details['rating'] = result
                record('rating', json.dumps(result, ensure_ascii=False), 'json_ld')
            except (ValueError, TypeError, KeyError, OverflowError):
                pass
        for contact in [node] + [resolve(c) for c in as_list(node.get('contactPoint'))]:
            if isinstance(contact, dict):
                for field, key in (('email', 'email'), ('phone', 'telephone')):
                    for value in as_list(contact.get(key)):
                        record(field, text_value(value), 'json_ld')
        for address in as_list(node.get('address')):
            address = resolve(address)
            if isinstance(address, dict):
                country = text_value(address.get('addressCountry'))
                formatted = ', '.join(filter(None, [text_value(address.get(k)) for k in ('streetAddress', 'addressLocality', 'addressRegion', 'postalCode', 'addressCountry')]))
                if country and not details['country']:
                    details['country'] = country[:100]
                    record('country', country, 'json_ld')
            else:
                formatted = text_value(address)
            if formatted and formatted not in details['addresses']:
                details['addresses'].append(formatted)
                record('address', formatted, 'json_ld')
        hours = [text_value(h) for h in as_list(node.get('openingHours')) if text_value(h)]
        for spec in as_list(node.get('openingHoursSpecification')):
            spec = resolve(spec)
            if isinstance(spec, dict):
                days = ', '.join(text_value(d).rsplit('/', 1)[-1] for d in as_list(spec.get('dayOfWeek')))
                opens, closes = text_value(spec.get('opens')), text_value(spec.get('closes'))
                if days and opens and closes:
                    hours.append(f'{days}: {opens}–{closes}')
        for value in hours:
            if value not in details['opening_hours']:
                details['opening_hours'].append(value)
                record('opening_hours', value, 'json_ld')
        for link in as_list(node.get('sameAs')):
            profile = social_profile(link, source_url)
            if profile:
                record(profile[0], profile[1], 'json_ld')

    for anchor in soup.select('a[href]'):
        href = anchor.get('href', '').strip()
        if href.lower().startswith('mailto:'):
            for value in re.split('[,;]', unquote(href[7:]).split('?')[0]):
                record('email', value, 'mailto')
        elif href.lower().startswith('tel:'):
            record('phone', unquote(href[4:]), 'tel')
        else:
            profile = social_profile(href, source_url)
            if profile:
                record(profile[0], profile[1], 'website_link')
    for element in soup.select('[data-cfemail]'):
        record('email', decode_cloudflare_email(element.get('data-cfemail', '')), 'cloudflare_email')
    for element in soup.select('[itemprop="email"], [itemprop="telephone"]'):
        value = element.get('content') or element.get('href') or element.get_text(' ', strip=True)
        record('email' if element.get('itemprop') == 'email' else 'phone', value.removeprefix('tel:'), 'microdata')
    for element in soup.select('address'):
        value = element.get_text(' ', strip=True)
        if value and len(value) < 500 and value not in details['addresses']:
            details['addresses'].append(value)
            record('address', value, 'address_element', 'medium')
    if not details['description']:
        meta = soup.find('meta', attrs={'name': re.compile('^description$', re.I)})
        if meta and meta.get('content'):
            details['description'] = meta['content'].strip()[:2000]
            record('description', details['description'], 'meta_description', 'medium')
    for element in soup.select('script, style, noscript, template, [hidden], [aria-hidden="true"]'):
        element.decompose()
    visible = soup.get_text('\n', strip=True)
    deobfuscated = re.sub(r'\s*[\[(]\s*at\s*[\])]\s*', '@', visible, flags=re.I)
    deobfuscated = re.sub(r'\s*[\[(]\s*dot\s*[\])]\s*', '.', deobfuscated, flags=re.I)
    for match in EMAIL.findall(deobfuscated):
        record('email', match, 'visible_text', 'medium')
    lines = visible.splitlines()
    for position, line in enumerate(lines):
        previous = lines[position - 1] if position else ''
        # Only carry a standalone label over a line break, never a previous number.
        context = line
        if re.fullmatch(r'(?:phone|tel|telephone|call(?: us)?|mobile|hotline|fax)\s*:?', previous, re.I):
            context = previous + ' ' + line
        for match in PHONE.finditer(line):
            value = match.group().strip()
            if value.startswith(('+', '00')) or re.search(r'\b(phone|tel|telephone|call|mobile|hotline|fax)\b', context, re.I):
                record('phone', value, 'visible_text', 'medium')
    return {**details, 'evidence': evidence, 'visible_text': visible}
