"""Only render navigable HTTP(S) links from scraped database fields."""
from urllib.parse import urlsplit
from django import template

register = template.Library()


@register.filter
def safe_external_url(value):
    try:
        parsed = urlsplit(value or '')
        if parsed.scheme in ('http', 'https') and parsed.hostname and not parsed.username:
            return value
    except ValueError:
        pass
    return '#'
