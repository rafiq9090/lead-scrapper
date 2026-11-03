"""Public-only HTTP reads with explicit redirects and a bounded response size.

DNS validation is defense in depth; production must also restrict outbound
traffic at the network layer to protect against DNS rebinding.
"""
import ipaddress
import socket
import time
from urllib.parse import urljoin, urlsplit

import httpx
from .concurrency import website_slot

MAX_RESPONSE_BYTES = 2_000_000


def validate_public_url(url):
    if '://' not in url:
        url = 'https://' + url
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname:
            raise ValueError
        if parsed.username is not None or parsed.password is not None:
            raise ValueError
        if parsed.port not in (None, 80, 443):
            raise ValueError
        host = parsed.hostname
        if host == 'localhost' or host.endswith(('.localhost', '.local')):
            raise ValueError
        addresses = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == 'https' else 80),
                                       type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
            raise ValueError
    except (ValueError, OSError):
        raise ValueError('Use a public HTTP(S) website on port 80 or 443.') from None
    return url


def fetch_public(client, url, max_bytes=MAX_RESPONSE_BYTES):
    """Retry one timeout or transient HTTP failure within a bounded wait."""
    for attempt in range(2):
        try:
            return _fetch_public(client, url, max_bytes)
        except httpx.HTTPStatusError as exc:
            if attempt or exc.response.status_code not in (429, 502, 503, 504):
                raise
            try:
                delay = float(exc.response.headers.get('retry-after', '1'))
            except ValueError:
                delay = 1
            if not 0 <= delay <= 5:
                raise
            time.sleep(delay)
        except httpx.TimeoutException:
            if attempt:
                raise
            time.sleep(0.5)


def _fetch_public(client, url, max_bytes):
    started = time.perf_counter()
    for _ in range(6):
        url = validate_public_url(url)
        queued_at = time.perf_counter()
        with website_slot(url):
            # Waiting for another batch's request is not website response latency.
            started += time.perf_counter() - queued_at
            with client.stream('GET', url, follow_redirects=False) as response:
                if response.is_redirect:
                    location = response.headers.get('location')
                    if not location:
                        raise ValueError('Redirect has no destination.')
                    url = urljoin(str(response.url), location)
                    continue
                response.raise_for_status()
                response.extensions['headers_elapsed_ms'] = int((time.perf_counter() - started) * 1000)
                content = bytearray()
                for chunk in response.iter_bytes():
                    content.extend(chunk)
                    if len(content) > max_bytes:
                        raise ValueError('Website response exceeds the size limit.')
                    if time.perf_counter() - started > 30:
                        raise ValueError('Website response exceeds the time limit.')
                # iter_bytes has decompressed the body already; avoid decoding it twice.
                headers = {key: value for key, value in response.headers.items()
                           if key.lower() not in ('content-encoding', 'content-length')}
                return httpx.Response(response.status_code, headers=headers,
                                      content=bytes(content), request=response.request,
                                      extensions=response.extensions)
    raise ValueError('Too many redirects.')
