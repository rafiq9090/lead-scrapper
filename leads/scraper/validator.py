"""
Deep Knowledge Validation & Verification Engine
Provides high-accuracy verification for business contacts:
- Cloudflare email de-obfuscation
- DNS MX-record verification (verifies if the domain can actually receive emails)
- RFC 5322 strict email syntax & placeholder elimination
- International phone sanitization
- Clean domain & public suffix extraction (tldextract)
"""

import re
import urllib.parse
from typing import Optional
import tldextract

DOMAIN_EXTRACTOR = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)

try:
    import dns.resolver
    HAS_DNS = True
except ImportError:
    HAS_DNS = False

# Strict RFC 5322 compliant email regex
EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+"
)

# Common asset filenames and fake patterns mistaken for emails
INVALID_EMAIL_ENDINGS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js",
    ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".mov", ".zip", ".pdf"
}

# Known spam, vendor, template, and disposable domains
DISPOSABLE_OR_NOISE_DOMAINS = {
    "example.com", "domain.com", "yourdomain.com", "test.com", "sample.com",
    "sentry.io", "wixpress.com", "cloudflare.com", "crisp.chat", "zendesk.com",
    "intercom.io", "drift.com", "hubspot.com", "gravatar.com", "wordpress.org",
    "themeforest.net", "envato.com", "shopify.com", "mailinator.com", "10minutemail.com",
    "tempmail.com", "guerrillamail.com", "yopmail.com", "trashmail.com"
}

# Common placeholder local parts
PLACEHOLDER_NAMES = {
    "yourname", "username", "name", "email", 
    "firstname", "test", "myemail", "admin@domain", "info@domain"
}


def decode_cloudflare_email(cf_hex: str) -> str:
    """
    Decodes emails obfuscated with Cloudflare Email Protection.
    Cloudflare uses a 1-byte XOR cipher encoded in hex.
    """
    if not cf_hex or len(cf_hex) < 4:
        return ""
    try:
        key = int(cf_hex[:2], 16)
        email = "".join(
            chr(int(cf_hex[i:i + 2], 16) ^ key)
            for i in range(2, len(cf_hex), 2)
        )
        return email.strip()
    except Exception:
        return ""


def clean_domain(url_or_domain: str) -> str:
    """
    Extracts the canonical registered domain e.g., 'example.co.uk' or 'clinic.com'
    using the packaged public suffix list (tldextract).
    """
    if not url_or_domain:
        return ""
    try:
        ext = DOMAIN_EXTRACTOR(url_or_domain)
        if ext.domain and ext.suffix:
            return f"{ext.domain}.{ext.suffix}".lower()
    except Exception:
        pass
    
    # Fallback to urllib
    try:
        if not url_or_domain.startswith(("http://", "https://")):
            url_or_domain = "https://" + url_or_domain
        parsed = urllib.parse.urlparse(url_or_domain)
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc.split(":")[0]
    except Exception:
        return ""


def verify_domain_mx(domain: str, timeout: float = 3.0) -> dict:
    """MX evidence only. Timeout, no MX and null MX have distinct outcomes."""
    result = {"has_mx": False, "status": "unknown", "provider": "Unknown", "mx_host": ""}
    clean_d = domain.strip().lower().rstrip('.')
    if not HAS_DNS or not clean_d or '.' not in clean_d:
        return result
    try:
        resolver = dns.resolver.Resolver()
        resolver.timeout = timeout
        resolver.lifetime = timeout
        answers = sorted(resolver.resolve(clean_d, 'MX'), key=lambda record: record.preference)
        if not answers:
            return {**result, 'status': 'no_mx'}
        host = str(answers[0].exchange).lower().rstrip('.')
        if not host:
            return {**result, 'status': 'null_mx', 'provider': 'Domain does not accept email'}
        provider = 'Mail server'
        for marker, name in (('google', 'Google Workspace'), ('outlook', 'Microsoft 365'), ('zoho', 'Zoho'), ('proton', 'ProtonMail')):
            if marker in host:
                provider = name
                break
        return {'has_mx': True, 'status': 'mx_found', 'provider': provider, 'mx_host': host}
    except dns.resolver.NXDOMAIN:
        return {**result, 'status': 'domain_not_found'}
    except dns.resolver.NoAnswer:
        return {**result, 'status': 'no_mx'}
    except Exception:
        return result


def is_valid_email_deep(email: str, verify_mx: bool = False) -> bool:
    """
    Performs deep validation on an email address:
    1. RFC 5322 regex format check
    2. File extension / image asset check
    3. Noise / Disposable vendor check
    4. Placeholder name check
    5. Optional live DNS MX check
    """
    if not email or len(email) > 254 or "@" not in email:
        return False

    clean_email = email.lower().strip(".,;:()<>[]\"' ")

    # Check for image/font endings e.g. logo@2x.png
    for ext in INVALID_EMAIL_ENDINGS:
        if clean_email.endswith(ext):
            return False

    # Check length and parts
    parts = clean_email.split("@")
    if len(parts) != 2:
        return False
    local_part, domain_part = parts[0], parts[1]

    if not 1 <= len(local_part) <= 64 or len(domain_part) < 4 or "." not in domain_part:
        return False

    if local_part.startswith(".") or local_part.endswith(".") or ".." in local_part:
        return False

    # Filter placeholder names
    if local_part in PLACEHOLDER_NAMES:
        return False

    # Filter noise/vendor domains
    for noise in DISPOSABLE_OR_NOISE_DOMAINS:
        if domain_part == noise or domain_part.endswith("." + noise):
            return False

    # Regex test
    if not EMAIL_REGEX.fullmatch(clean_email):
        return False

    # Live MX check if requested
    if verify_mx:
        mx_res = verify_domain_mx(domain_part)
        if not mx_res["has_mx"]:
            return False

    return True


def sanitize_phone(phone: str, country: str = "") -> str:
    """Normalize a plausible number; never infer a country code or dialability."""
    if not isinstance(phone, str) or len(phone) > 100:
        return ""
    phone = urllib.parse.unquote(phone).strip().removeprefix('tel:')
    match = re.search(r'(?:;ext=|\bext\.?\s*|\bx\s*)(\d{1,6})$', phone, re.I)
    extension = match.group(1) if match else ''
    if match:
        phone = phone[:match.start()].strip()
    if re.search(r'[^0-9+() .-]', phone) or re.fullmatch(r'\d{4}[-/.]\d{1,2}[-/.]\d{1,2}', phone):
        return ''
    digits = re.sub(r'\D', '', phone)
    if not 7 <= len(digits) <= 15 or len(set(digits)) <= 2:
        return ''
    if phone.startswith('00'):
        number = '+' + digits[2:]
    else:
        number = ('+' if phone.startswith('+') else '') + digits
    return number + (f' ext. {extension}' if extension else '')


def clean_business_name(raw_name: str) -> str:
    """
    Normalizes business titles by stripping SEO keywords, locations, and slogans:
    'Dental Care Clinic - Best Dentist in Chicago | Book Online' -> 'Dental Care Clinic'
    """
    if not raw_name:
        return ""
    
    # Split on common SEO separators: |, -, –, —, •, :
    for sep in [" | ", " - ", " – ", " — ", " • ", " :: ", " : "]:
        if sep in raw_name:
            parts = raw_name.split(sep)
            if len(parts[0].strip()) >= 3:
                raw_name = parts[0]
                break

    # Strip trailing corporate abbreviations if wanted, or tidy whitespace
    raw_name = re.sub(r"\s+", " ", raw_name).strip()
    return raw_name
