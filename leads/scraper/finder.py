"""
Business Discovery Engine - High-Volume & Multi-City Expansion Engine
Capable of harvesting up to 1,000 real leads across multiple countries:
- Multi-city metropolitan expansion when broad countries or high volumes are requested
- Comprehensive directory, aggregator, and scraper exclusion
- OpenStreetMap Nominatim geo-spatial business directory
- DuckDuckGo Lite & HTML multi-paging with redirect de-cloaking
- Canonical domain verification (tldextract) & business name normalization
"""

import base64
import os
import re
import urllib.parse
from typing import List, Dict, Set, Tuple
import httpx
from bs4 import BeautifulSoup

from .validator import clean_domain, clean_business_name, sanitize_phone
from .contacts import PHONE
from .concurrency import discovery_slot, parallel_results, worker_count

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

from .discovery_data import (
    IGNORED_DOMAINS, COUNTRY_CODES, COUNTRY_MAJOR_CITIES,
    CITY_DISTRICTS, INDUSTRY_VARIATIONS,
)

def is_valid_business_domain(domain: str) -> bool:
    """Checks if domain belongs to a real private business rather than directory/social/news."""
    if not domain or len(domain) < 4 or "." not in domain:
        return False
    if domain.endswith((".gov", ".edu", ".mil")):
        return False
    for ignored in IGNORED_DOMAINS:
        if domain == ignored or domain.endswith("." + ignored):
            return False
    return True


def get_country_code(country_name: str) -> str:
    """Returns 2-letter ISO code if known, or empty string."""
    if not country_name:
        return ""
    return COUNTRY_CODES.get(country_name.strip().lower(), "")


def parse_google_url_details(raw_input: str, default_location: str = "") -> Tuple[str, str]:
    """
    Extracts actual target niche and location if a user pastes a Google Search or Google Maps URL:
    - https://www.google.com/search?q=cars+shop&udm=local... -> ('cars shop', '')
    - https://www.google.com/maps/search/cars+shop+in+chicago/ -> ('cars shop', 'chicago')
    - https://www.google.com/maps/place/Apex+Dental/... -> ('Apex Dental', '')
    - https://maps.app.goo.gl/xyz -> resolves redirect and extracts target
    """
    if not raw_input:
        return "", default_location
    raw_input = raw_input.strip()
    if not (raw_input.startswith(("http://", "https://")) and any(k in raw_input for k in ["google.", "goo.gl"])):
        return raw_input, default_location

    target_url = raw_input
    # Handle shortened Google Maps links (e.g., maps.app.goo.gl / goo.gl/maps)
    if "goo.gl" in target_url:
        try:
            with httpx.Client(headers=HEADERS, timeout=4.0, follow_redirects=True) as client:
                resp = client.head(target_url)
                if resp.url:
                    target_url = str(resp.url)
        except Exception:
            pass

    niche = raw_input
    location = default_location

    try:
        parsed = urllib.parse.urlparse(target_url)
        qs = urllib.parse.parse_qs(parsed.query)

        extracted = ""
        if "q" in qs and qs["q"]:
            extracted = qs["q"][0]
        elif "query" in qs and qs["query"]:
            extracted = qs["query"][0]
        elif "/maps/search/" in parsed.path:
            parts = parsed.path.split("/maps/search/")[1].split("/")
            extracted = urllib.parse.unquote(parts[0]).replace("+", " ")
        elif "/maps/place/" in parsed.path:
            parts = parsed.path.split("/maps/place/")[1].split("/")
            extracted = urllib.parse.unquote(parts[0]).replace("+", " ")
        elif "/search/" in parsed.path:
            parts = parsed.path.split("/search/")[1].split("/")
            extracted = urllib.parse.unquote(parts[0]).replace("+", " ")

        if extracted:
            # Clean up coordinate strings (e.g., '@41.87,-87.62,15z')
            extracted = re.sub(r'@[-\d.,]+z?', '', extracted).strip()
            # Detect location suffix: 'cars shop in Chicago' or 'dentists, Dallas'
            loc_match = re.search(r'\b(?:in|at|near)\s+([A-Za-z\s]+)$', extracted, re.I)
            if loc_match and not location:
                location = loc_match.group(1).strip()
                extracted = extracted[:loc_match.start()].strip()
            elif "," in extracted and not location:
                parts = extracted.split(",", 1)
                extracted = parts[0].strip()
                location = parts[1].strip()
            niche = extracted
    except Exception:
        pass

    return (niche or raw_input), location


def parse_google_search_url(raw_input: str) -> str:
    """Extracts clean query from Google search or Google maps URL."""
    clean_niche, _ = parse_google_url_details(raw_input)
    return clean_niche


def generate_query_variations(query: str) -> List[str]:
    """Generates intelligent search variations for the industry."""
    clean_q = parse_google_search_url(query).strip()
    lower_q = clean_q.lower()

    if lower_q in INDUSTRY_VARIATIONS:
        return INDUSTRY_VARIATIONS[lower_q]

    for key, variations in INDUSTRY_VARIATIONS.items():
        if key in lower_q:
            return variations

    variations = [clean_q]
    if lower_q.endswith("s") and len(lower_q) > 4:
        variations.append(lower_q[:-1])
    return variations


def extract_phone_from_text(text: str) -> str:
    """Extracts and sanitizes phone number from snippet text."""
    if not text:
        return ""
    for match in PHONE.finditer(text):
        value = sanitize_phone(match.group())
        if value:
            return value
    return ""


_DDG_UNAVAILABLE = False
NOMINATIM_DEFAULT_ENDPOINT = "https://nominatim.openstreetmap.org"


def search_duckduckgo_city(query_term: str, city: str, country_name: str, client: httpx.Client, seen_domains: Set[str], max_needed: int, fast_mode: bool = False) -> List[Dict]:
    """Searches DuckDuckGo Lite for a specific city and query term with fast-fail circuit breaker."""
    global _DDG_UNAVAILABLE
    if _DDG_UNAVAILABLE or fast_mode:
        return []

    leads = []
    search_term = f"{query_term} {city} {country_name}".strip()

    offsets = [0, 30] if max_needed >= 10 else [0]
    for offset in offsets:
        if len(leads) >= max_needed:
            break
        try:
            with discovery_slot("duckduckgo", fast_mode=fast_mode):
                resp = client.post("https://lite.duckduckgo.com/lite/", data={"q": search_term, "s": str(offset)}, timeout=3.5)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                rows = soup.select("tr")
                found_on_page = 0
                for tr in rows:
                    link_elem = tr.select_one(".result-link")
                    snippet_elem = tr.select_one(".result-snippet")
                    if snippet_elem is None and link_elem is not None:
                        for sibling in tr.find_next_siblings('tr', limit=3):
                            if sibling.select_one('.result-link'):
                                break
                            snippet_elem = sibling.select_one('.result-snippet')
                            if snippet_elem is not None:
                                break
                    if not link_elem:
                        continue

                    target_url = urllib.parse.urljoin("https://duckduckgo.com", link_elem.get("href", ""))
                    redirect_target = urllib.parse.parse_qs(urllib.parse.urlparse(target_url).query).get('uddg')
                    if redirect_target:
                        target_url = redirect_target[0]
                    title = link_elem.get_text(strip=True)
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""

                    if not target_url.startswith("http"):
                        continue

                    domain = clean_domain(target_url)
                    identity = (urllib.parse.urlsplit(target_url).hostname or '').lower().removeprefix('www.')
                    if not is_valid_business_domain(domain) or identity in seen_domains:
                        continue

                    seen_domains.add(identity)
                    found_on_page += 1
                    clean_name = clean_business_name(title)

                    leads.append({
                        "company_name": clean_name or domain.capitalize(),
                        "website": target_url,
                        "domain": domain,
                        "has_website": True,
                        "niche": query_term,
                        "location": city or country_name,
                        "country": "",
                        "target_country": country_name,
                        "address": "",
                        "phone": extract_phone_from_text(snippet),
                        "source": "DuckDuckGo search",
                        "source_url": "https://duckduckgo.com/?" + urllib.parse.urlencode({"q": search_term}),
                    })

                    if len(leads) >= max_needed:
                        return leads

                if found_on_page == 0:
                    break
        except (httpx.ConnectTimeout, httpx.NetworkError):
            _DDG_UNAVAILABLE = True
            break
        except Exception as e:
            print(f"[Finder] DDG error for {city}: {e}")
            break

    return leads


def search_nominatim_city(query_term: str, city: str, country_name: str, client: httpx.Client, seen_domains: Set[str], max_needed: int, fast_mode: bool = False) -> List[Dict]:
    """Queries OpenStreetMap Nominatim for real physical businesses in a specific city."""
    leads = []
    endpoint = os.environ.get('NOMINATIM_URL', NOMINATIM_DEFAULT_ENDPOINT).rstrip('/')
    if not endpoint:
        return leads
    country_code = get_country_code(country_name)
    search_term = f"{query_term} {city}".strip()

    limit = min(max_needed * 2, 50) if fast_mode else min(max_needed, 25)
    url = (
        f"{endpoint}/search?"
        f"q={urllib.parse.quote_plus(search_term)}&format=json&addressdetails=1&extratags=1&limit={limit}"
    )
    if country_code:
        url += f"&countrycodes={country_code}"

    try:
        with discovery_slot("nominatim", fast_mode=fast_mode):
            resp = client.get(url, headers={"User-Agent": "DevLeadOS-Prospector/2.0 (contact@devlead.local)"})
        if resp.status_code == 200:
            for item in resp.json():
                extratags = item.get("extratags") or {}
                raw_website = extratags.get("website") or extratags.get("contact:website") or ""
                raw_phone = extratags.get("phone") or extratags.get("contact:phone") or ""
                phone = sanitize_phone(raw_phone)
                name = item.get("name") or item.get("display_name", "").split(",")[0]
                clean_name = clean_business_name(name)
                address = item.get("display_name", "")

                addr_details = item.get("address") or {}
                detected_country = addr_details.get("country") or ""

                if raw_website:
                    raw_website = raw_website if raw_website.startswith(('http://', 'https://')) else 'https://' + raw_website
                    domain = clean_domain(raw_website)
                    identity = (urllib.parse.urlsplit(raw_website).hostname or '').lower().removeprefix('www.')
                    if is_valid_business_domain(domain) and identity not in seen_domains:
                        seen_domains.add(identity)
                        leads.append({
                            "company_name": clean_name,
                            "website": raw_website,
                            "domain": domain,
                            "has_website": True,
                            "niche": query_term,
                            "location": city or country_name,
                            "country": detected_country,
                            "address": address,
                            "phone": phone,
                            "source": "OpenStreetMap",
                            "source_url": f"https://www.openstreetmap.org/{item.get('osm_type', 'node')}/{item.get('osm_id', '')}",
                        })
                else:
                    slug = re.sub(r'[^a-zA-Z0-9]', '', clean_name).lower()[:30]
                    identity = f"osm-{item.get('osm_type', 'place')}-{item.get('osm_id', item.get('place_id'))}"
                    if slug and identity not in seen_domains:
                        seen_domains.add(identity)
                        leads.append({
                            "company_name": clean_name,
                            "website": "",
                            "domain": f"{identity}.local",
                            "has_website": False,
                            "niche": query_term,
                            "location": city or country_name,
                            "country": detected_country,
                            "address": address,
                            "phone": phone,
                            "source": "OpenStreetMap (No Website)",
                            "source_url": f"https://www.openstreetmap.org/{item.get('osm_type', 'node')}/{item.get('osm_id', '')}",
                        })

                if len(leads) >= max_needed:
                    break
    except Exception as e:
        print(f"[Finder] OSM error for {city}: {e}")

    return leads


def decode_bing_url(url: str) -> str:
    """Decodes Bing click-tracking redirect URL to the real canonical destination URL."""
    if not url:
        return ""
    if "/ck/a?!&&p=" in url:
        try:
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            if "u" in qs and qs["u"]:
                raw_u = qs["u"][0]
                if raw_u.startswith("a1"):
                    raw_u = raw_u[2:]
                rem = len(raw_u) % 4
                if rem:
                    raw_u += "=" * (4 - rem)
                return base64.b64decode(raw_u).decode("utf-8", errors="ignore")
        except Exception:
            pass
    return url


def search_bing_city(query_term: str, city: str, country_name: str, client: httpx.Client, seen_domains: Set[str], max_needed: int, fast_mode: bool = False) -> List[Dict]:
    """Queries Bing Search for verified local business websites and contact information."""
    leads = []
    search_term = f"{query_term} {city} {country_name}".strip()
    country_code = get_country_code(country_name)
    mkt_param = f"&cc={country_code.upper()}" if country_code else ""
    url = f"https://www.bing.com/search?q={urllib.parse.quote_plus(search_term)}{mkt_param}"

    try:
        with discovery_slot("bing", fast_mode=fast_mode):
            resp = client.get(url, timeout=4.5 if fast_mode else 8.0)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for li in soup.select("li.b_algo"):
                h2 = li.find("h2")
                a = h2.find("a") if h2 else None
                if not a:
                    continue
                raw_url = a.get("href", "")
                final_url = decode_bing_url(raw_url)
                if not final_url or not final_url.startswith(("http://", "https://")):
                    continue

                domain = clean_domain(final_url)
                identity = (urllib.parse.urlsplit(final_url).hostname or "").lower().removeprefix("www.")
                if not is_valid_business_domain(domain) or identity in seen_domains:
                    continue

                seen_domains.add(identity)
                title = clean_business_name(a.get_text(strip=True))
                caption = li.select_one(".b_caption")
                snip = caption.get_text(strip=True) if caption else ""
                phone = extract_phone_from_text(snip)

                leads.append({
                    "company_name": title or domain.capitalize(),
                    "website": final_url,
                    "domain": domain,
                    "has_website": True,
                    "niche": query_term,
                    "location": city or country_name,
                    "country": country_name,
                    "target_country": country_name,
                    "address": f"{city}, {country_name}" if city else country_name,
                    "phone": phone,
                    "source": "Web Search (Bing)",
                    "source_url": url,
                })
                if len(leads) >= max_needed:
                    break
    except Exception as e:
        print(f"[Finder] Bing error for {city}: {e}")

    return leads


def search_photon_city(query_term: str, city: str, country_name: str, client: httpx.Client, seen_domains: Set[str], max_needed: int, fast_mode: bool = False) -> List[Dict]:
    """Queries OpenStreetMap Komoot Photon geo-API for physical verified business establishments."""
    leads = []
    search_term = f"{query_term} {city} {country_name}".strip()
    url = f"https://photon.komoot.io/api/?q={urllib.parse.quote_plus(search_term)}&limit={min(max_needed * 2, 25)}"

    try:
        with discovery_slot("photon", fast_mode=fast_mode):
            resp = client.get(url, timeout=4.0 if fast_mode else 7.0)
        if resp.status_code == 200:
            data = resp.json()
            for feat in data.get("features", []):
                props = feat.get("properties", {})
                name = props.get("name")
                if not name:
                    continue
                clean_name = clean_business_name(name)
                detected_city = props.get("city") or city
                detected_country = props.get("country") or country_name
                street = props.get("street") or ""
                housenumber = props.get("housenumber") or ""
                address_parts = [p for p in [housenumber, street, detected_city, detected_country] if p]
                address = ", ".join(address_parts)
                osm_id = props.get("osm_id", "")
                osm_type = props.get("osm_type", "N")
                osm_url = f"https://www.openstreetmap.org/{osm_type}/{osm_id}" if osm_id else ""

                extra = props.get("extra") or {}
                raw_website = extra.get("website") or extra.get("contact:website") or ""
                phone = sanitize_phone(extra.get("phone") or extra.get("contact:phone") or "")

                if raw_website:
                    if not raw_website.startswith(("http://", "https://")):
                        raw_website = "https://" + raw_website
                    domain = clean_domain(raw_website)
                    identity = (urllib.parse.urlsplit(raw_website).hostname or "").lower().removeprefix("www.")
                    if is_valid_business_domain(domain) and identity not in seen_domains:
                        seen_domains.add(identity)
                        leads.append({
                            "company_name": clean_name,
                            "website": raw_website,
                            "domain": domain,
                            "has_website": True,
                            "niche": query_term,
                            "location": detected_city or city or country_name,
                            "country": detected_country,
                            "target_country": country_name,
                            "address": address,
                            "phone": phone,
                            "source": "OpenStreetMap",
                            "source_url": osm_url,
                        })
                else:
                    identity = f"osm-{osm_type}-{osm_id}" if osm_id else f"osm-{re.sub(r'[^a-zA-Z0-9]', '', clean_name).lower()[:20]}"
                    if identity not in seen_domains:
                        seen_domains.add(identity)
                        leads.append({
                            "company_name": clean_name,
                            "website": "",
                            "domain": f"{identity}.local",
                            "has_website": False,
                            "niche": query_term,
                            "location": detected_city or city or country_name,
                            "country": detected_country,
                            "target_country": country_name,
                            "address": address,
                            "phone": phone,
                            "source": "OpenStreetMap (No Website)",
                            "source_url": osm_url,
                        })

                if len(leads) >= max_needed:
                    break
    except Exception as e:
        print(f"[Finder] Photon OSM error for {city}: {e}")

    return leads


def _discovery_queries(query, location, countries, max_results, fast_mode=False):
    clean_query, detected_loc = parse_google_url_details(query, location)
    effective_loc = location or detected_loc
    variations = generate_query_variations(clean_query)

    for country in countries:
        if effective_loc:
            districts = CITY_DISTRICTS.get(effective_loc.strip().lower(), []) if max_results > 15 else []
            locations = [effective_loc] + [f'{district}, {effective_loc}' for district in districts]
        else:
            locations = COUNTRY_MAJOR_CITIES.get(country.lower(), [''])

        for city in locations:
            for term in variations:
                yield ('bing', term, city, country, min(max_results, 30), fast_mode)
                yield ('photon', term, city, country, min(max_results, 30), fast_mode)
                yield ('nominatim', term, city, country, min(max_results, 30), fast_mode)
                if not fast_mode and not _DDG_UNAVAILABLE:
                    yield ('duckduckgo', term, city, country, min(max_results, 30), fast_mode)


def _discover_query(task):
    provider, term, city, country, limit, fast_mode = task
    if provider == 'bing':
        function = search_bing_city
    elif provider == 'photon':
        function = search_photon_city
    elif provider == 'nominatim':
        function = search_nominatim_city
    else:
        function = search_duckduckgo_city

    timeout = 4.5 if fast_mode else 8.0
    with httpx.Client(headers=HEADERS, timeout=timeout, follow_redirects=True) as client:
        return function(term, city, country, client, set(), max_needed=limit, fast_mode=fast_mode)


def discover_businesses(query, location='', countries=None, max_results=15, log_callback=None, fast_mode=False):
    if max_results <= 0:
        return []
    if isinstance(countries, str):
        countries = countries.split(',')
    countries = list(dict.fromkeys(str(c).strip() for c in (countries or ['']) if str(c).strip())) or ['']
    default_workers = 6 if fast_mode else 4
    max_workers = 8 if fast_mode else 6
    workers = worker_count('DISCOVERY_WORKERS', default_workers, max_workers)
    if log_callback:
        mode_prefix = "Fast Scrape Discovery" if fast_mode else "Discovery"
        log_callback(f'{mode_prefix}: {workers} workers, query routing active.')
    results = parallel_results(_discover_query, _discovery_queries(query, location, countries, max_results, fast_mode), workers)
    leads, seen = [], set()
    try:
        for task, found, error in results:
            if error:
                if log_callback:
                    log_callback(f'Discovery query failed for {task[2] or task[3]}; continuing.')
                continue
            for candidate in found:
                website = candidate.get('website', '')
                if website:
                    identity = (urllib.parse.urlsplit(website).hostname or '').lower().removeprefix('www.')
                else:
                    identity = candidate.get('domain', '')
                if identity and identity not in seen:
                    seen.add(identity)
                    leads.append(candidate)
                    if len(leads) >= max_results:
                        break
            if log_callback:
                log_callback(f'Discovery: {len(leads)} unique candidates found (target {max_results}).')
            if len(leads) >= max_results:
                break
    finally:
        results.close()
    return leads
