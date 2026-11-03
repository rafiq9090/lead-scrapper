# Data quality upgrade

Date: 5 October 2026 (Asia/Dhaka)

## What changed

The upgrade targets both business contacts and technical findings. It improves extraction coverage and reduces concrete false-positive paths; it does not guarantee that every business publishes every field or that all extracted data is independently accurate.

### Public business information

- Business JSON-LD is selected by entity type rather than accepting the first page/person/product name. Graph references resolve nested addresses and contact points, arrays of emails, country objects, business names, descriptions and opening hours.
- Contact extraction reads explicit mailto/tel links, Cloudflare-obfuscated addresses, conservative `[at]`/`[dot]` text, microdata and visible phone text. Script/CSS email noise, date-like numbers and unrelated account numbers are excluded by tested fixtures.
- Phone formatting is normalized without inventing an international country code. This is plausibility checking, not proof a number can be called.
- Social links require exact provider hosts and profile paths. Share links, post/reel URLs and lookalike hosts are excluded.
- Website-published aggregate ratings retain their declared scale and distinguish review counts from rating counts. They are labeled self-reported, not Google reviews or independent verification.
- Contact and location pages are prioritized. The supplied website path and redirect destination are preserved, and the crawler checks up to eight pages by default instead of stopping after finding two emails and one phone.
- The finder preserves original website URLs, reads DuckDuckGo snippets from neighboring rows, and does not turn a requested city/country into a verified business address/country. Bangladesh and country aliases now share consistent country/city expansion data.

The supported structured fields follow [Schema.org LocalBusiness](https://schema.org/LocalBusiness). HTML parsing uses [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/bs4/doc/).

### Technical evidence

- Android app matches require an exact Google Play host/path/package or a valid smart-banner package ID published by the website. The previous first-company-word search match was removed because it could select an unrelated app.
- Chat detection checks known script/iframe hosts and initialization syntax. A blog mention of Intercom/Tidio/Drift does not establish a deployed widget. A detected widget does not prove AI capabilities.
- Both checks distinguish `detected`, `not_detected` and `unknown`. A checked page without a match is not proof of absence.
- The server measurement reuses the successful homepage response. Failures stay unknown; no fake latency or inferred hosting stack is created. Timing includes connection/redirect overhead and is one sample.
- Industry suggestions use explicit niche terms. Generic website text no longer grants every prospect a computer-vision opportunity.
- Opportunity scoring and pitch generation use current audit states. Unknown checks and unreviewed legacy records are excluded from missing-feature filters.

### Evidence, preservation and visibility

The model now records all phones, addresses, description, opening hours, discovery source, last-audited time, current check states and an `audit_report` JSON object. Evidence includes field, value, source URL, extraction method, source strength and observation time. Previously retained evidence keeps its original timestamp.

Source strength is a label for how directly a value was published: explicit structured/contact links are high; visible-text extraction is medium. It is not a calibrated confidence probability. Contact coverage reports how many of six categories were found in the latest crawl: email, phone, address, social profile, structured business name and opening hours. It is not accuracy, mailbox verification or completeness of the entire business record.

Failed re-audits retain existing contact details, workflow status, notes and prior evidence. The profile flags retained fields that were not reconfirmed. Discovery metadata survives a profile re-audit. Negative technical results are based only on the latest inspected HTML.

Click a business name for its full profile, sources, page failures, current checks and draft outreach. A staff-only POST action re-audits the record. The dashboard paginates 50 leads per page, and exports use the same active filters. CSV includes evidence/page JSON; Excel has separate lead, evidence and checked-page sheets. The `reaudit_leads` command provides sequential refreshes and a dry run.

### Transport handling

Website reads still verify TLS and reject private addresses and unsafe redirect destinations. One transient timeout or 429/502/503/504 response can be retried with a short bounded delay. A server-requested wait longer than five seconds is not ignored. The response reconstruction now avoids decompressing gzip content a second time. Body, redirect, page and elapsed-read limits remain in place.

## Database and environment

Migration `0004_lead_evidence_and_audit_states` was applied after creating `backups/db-before-quality-2026-10-05.sqlite3`. All **205 existing leads and every original field value** were compared before/after and preserved. New fields mark the existing records `unreviewed`; no mass live re-audit of those records was performed. Use a profile's Re-audit button or the documented management command to collect current evidence.

The broken virtual environment was repaired using compatible local Python 3.12.14, preserving installed packages. Its prior configuration is saved in `backups/pyvenv-before-quality.cfg`. `python manage.py check` and `pip check` work through the normal `.venv` executable. The bundled base runtime must remain available; recreate the virtual environment with an installed Python if it moves.

## Verification

- **44 offline tests pass**, including fixture-based extraction, false-positive rejection, nested structured data, link host validation, app/chat states, redirected contact crawling, challenge pages, gzip responses, transient retries, failed-refresh preservation, source exports, pagination and dry-run behavior.
- Django checks and migration drift checks pass.
- JavaScript syntax check passes.
- A live smoke test fetched two public python.org pages with HTTP 200. The crawler correctly returned `partial` when its two-page test limit left additional links unchecked. This checks real HTTP handling, not measured business-data precision/recall.
- The original lead-field digest matches after migration; the database itself necessarily has a new schema/checksum.

## Remaining limits

1. JavaScript-rendered details, CAPTCHA-protected content, non-public contacts and unpublished fields cannot be guaranteed. The tool does not bypass access challenges. Browser-rendered crawling is not implemented.
2. No benchmark against a representative set of manually verified businesses has been run. The tests establish specific behaviors, not a general accuracy percentage.
3. No SMTP/mailbox verification is performed. DNS states distinguish MX found, no MX, null MX, nonexistent domain and unknown, but do not establish deliverability.
4. Some sites publish incorrect structured data, multiple business entities, or outdated contacts. All website-provided data remains subject to review. The schema type list is practical rather than an exhaustive ontology.
5. Per-host identity can still merge branches sharing a website. Domain uniqueness is not enforced, so overlapping writes can race. Durable jobs, distributed concurrency/rate controls and strict connection-level SSRF egress controls remain deployment work.
6. Exact profile matching does not independently prove ownership. App links can point to a partner or generic platform app. The label is website-linked app rather than verified ownership.
7. Historical records retain their original pitches and values until refreshed; the profile marks them for review. The existing weak admin password still requires rotation.
8. Browser visual/accessibility behavior and production load were not tested in this change.
