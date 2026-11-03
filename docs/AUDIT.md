# Project audit

Date: 5 October 2026 (Asia/Dhaka)

**Historical baseline:** this report predates the subsequent quality upgrade. See [DATA_QUALITY.md](DATA_QUALITY.md) for repaired extraction issues, new evidence states, the applied schema migration, environment repair, and current verification. Database checksum statements below refer to the earlier organization task.

## Outcome and scope

The application has been reorganized and several concrete security and correctness issues repaired. It remains a local, single-process prospecting tool and is not production-ready.

Reviewed all first-party Python modules, migrations, Django routes/settings/admin, the full dashboard HTML/CSS/JavaScript, requirements, launcher, and README. Inspected SQLite counts and staff password security through read-only access. Vendored virtual-environment packages and bytecode were treated as dependencies/generated files, not first-party source. This is a source/configuration review plus offline regression verification, not a penetration test or a live external-source benchmark.

The existing database contains **205 leads**, **one active staff account**, and **zero duplicate domain groups**. Its contents were preserved. Existing migrations were preserved; no schema migration is required by the changes.

## Reorganization completed

| Area | Previous structure | Current structure |
| --- | --- | --- |
| Controllers | One `leads/views.py` | `leads/views/dashboard.py`, `api.py`, `exports.py` |
| Background tasks | Thread logic inside views | `leads/services/jobs.py` |
| Export protection | Repeated export code without cell protection | Shared `leads/services/exports.py` |
| Frontend | Inline stylesheet and script in one template | `leads/static/leads/css/` and `js/` |
| Templates | One large page | Dashboard shell plus five focused partials |
| Discovery tables | Embedded in the finder | `leads/scraper/discovery_data.py` |
| Website transport | Unrestricted individual GET calls | `leads/scraper/network.py` |
| Tests | Empty placeholder | API, scraper/pipeline, and job test modules |
| Documentation/config | README only | Architecture, audit, environment reference, ignore/editor rules |

Public URL paths and names, the lead schema, database path, and existing data are preserved. Authentication is intentionally changed: dashboard/downloads require staff login and APIs return 403 to unauthorized callers.

## Findings repaired

| Priority | Finding and evidence | Repair |
| --- | --- | --- |
| High | Dashboard, mutation APIs, exports and job logs were anonymously accessible (`leads/views.py`). | Active staff access checks; job polling also checks task ownership. Lead data remains shared among staff. |
| High | All three mutation views used `csrf_exempt`. | Removed exemptions; rendered token and `X-CSRFToken` headers. Regression test verifies actual middleware rejection and acceptance. |
| High | Arbitrary domain audits could fetch private addresses and follow unchecked redirects. | Public-address validation, allowed scheme/port checks and per-hop redirect validation for crawler/server-audit requests. DNS rebinding remains a production concern below. |
| High | Crawler and server auditor used `verify=False`. | HTTPX certificate verification restored; these clients ignore environment proxy overrides. See [HTTPX verification options](https://www.python-httpx.org/api/). |
| High | Untrusted scraped strings entered CSV and XLSX without formula protection. | Prefix dangerous spreadsheet text with an apostrophe in web exports and admin CSV exports; integration tests inspect exported values and XLSX cell types. |
| Medium | Hardcoded Django secret, unconditional debug mode and unsuitable host configuration. | Environment-based settings; random temporary development key; stable production key required; HTTPS cookie/redirect/HSTS settings when debug is disabled. |
| Medium | Invalid JSON/types/counts/statuses reached generic 500 responses; missing leads also became 500s. | Explicit validation, 400 responses, preserved 404 handling, and generic server error responses for direct audit failures. |
| Medium | Unbounded daemon-thread creation, unowned polling, mutable shared task state and no DB connection cleanup. | Two running batch slots, full UUIDs, owner checks, locked deep-copy snapshots, bounded logs/history, expiry on subsequent job starts, and connection cleanup. Durable job storage is still required for deployment. |
| Medium | Re-auditing a lead that previously lacked a website did not set `has_website=True`. | Website branch explicitly updates the flag while retaining status and notes. |
| Medium | Failed server requests were fabricated as 1,400ms latency and an unoptimized legacy server. | Failure records unknown latency (`0`) and unknown server. Successful timing stops at headers rather than after the full body. This is still an approximate client measurement. |
| Medium | Unlimited response bodies could consume memory. | Crawler/server-audit bodies capped at 2MB decoded data, with redirect and elapsed-read limits. Network timeouts also apply; this is not a strict whole-job deadline. |
| Medium | Public Nominatim was used in repeated city/industry harvesting loops. | Disabled by default; configurable owned/authorized endpoint. The [public service policy](https://operations.osmfoundation.org/policies/nominatim/) prohibits systematic place harvesting and also imposes rate limits, caching and identification requirements. |
| Medium | No-website identity used company-name slugs, merging same-name branches. | OSM candidates now use stable OSM object identity. Existing stored leads are not rewritten. |
| Medium | DuckDuckGo redirect-wrapper URLs could be discarded as search-engine domains. | Decode the `uddg` destination before domain filtering. |
| Medium | MX checks reduced email subdomains to registered domains and treated any A-record resolution as successful MX verification. Also changed the global socket timeout. | Query the actual email domain; remove misleading socket fallback and global timeout mutation. MX presence alone still does not guarantee a deliverable mailbox. |
| Medium | Outreach claimed prototypes/previews already existed, Google listing/review facts, definite app absence and a contact-form setup without evidence. | Removed invented work/source claims and softened scan findings in generated drafts. Existing stored pitches were not rewritten. |
| Low | Dashboard rendered untrusted URLs as clickable links. | HTTP(S)-only template filter plus external-link `noopener noreferrer`. |
| Low | Background failures were displayed as successful completion in the browser. | Separate failed/unavailable job handling; report failed status updates. |
| Low | tldextract could fetch suffix data or write an external cache at runtime; contact ordering was nondeterministic. | Use packaged suffix data and deterministic email/phone/contact-route ordering. |
| Low | Launcher depended on the caller's working directory and advertised weak credentials. | Change to script directory, check the interpreter and Django configuration, remove printed credentials, and use `--noreload` for process-local jobs. |
| Low | Requirements had unrestricted future upgrades; generated/local data had no ignore rules. | Add dependency upper bounds, `.gitignore`, `.editorconfig`, and setup/configuration documentation. No reproducible lockfile has been generated. |

CSRF implementation follows [Django's documented AJAX protection](https://docs.djangoproject.com/en/4.2/howto/csrf/).

## Remaining findings and follow-up order

### High: existing weak staff password

Read-only verification confirmed that the active staff account still accepts the weak password published in the original README. Removing the documentation does not rotate the password. Credentials were not changed during this file organization/audit task. With a working environment, run:

```powershell
.\.venv\Scripts\python.exe manage.py changepassword admin
```

Review existing accounts and replace any reused credentials before exposing the application.

### High for public deployment: residual SSRF and resource controls

`leads/scraper/network.py` checks DNS before connection, but HTTPX performs its own resolution. A hostile domain can change DNS answers between those operations. Use network egress restrictions or a controlled fetching service to block private/metadata destinations at connection time. Batch caps do not throttle synchronous direct audits, DNS resolution, or requests to fixed discovery/Play Store endpoints. Apply shared concurrency/rate limits and a whole-task deadline before allowing untrusted users. The bounded body helper currently covers crawling/server auditing, not every external discovery request.

### Medium: fragile job execution and SQLite concurrency

`leads/services/jobs.py` stores tasks in memory. Restart/reload loses jobs; daemon threads can stop midway; multi-worker polling can return 404. There is no cancellation, durable retry, overall timeout or recovery. Expired completed tasks are cleared when another job starts, and retained history is capped. Use a durable queue plus persisted task state for deployment. SQLite write contention is still possible with overlapping batches/direct audits despite its increased busy timeout.

### Medium: missing database uniqueness and weak business identity

`Lead.domain` is indexed but not unique while the pipeline uses `update_or_create(domain=...)`. Concurrent inserts can create duplicates, later causing `MultipleObjectsReturned`. No duplicates currently exist, but enforcing uniqueness needs a reviewed data migration and a decision on branch identity. Registered-domain collapsing can merge branches or unrelated tenants on hosted domains. Several discovery paths replace the original website with the registered domain, losing meaningful subdomains/paths or forcing HTTPS onto HTTP-only businesses.

### Medium: confidence and failed-audit state are not modeled

Models store app/chat/SSL as booleans. Failed/blocked fetches and a genuine negative cannot be distinguished; zero latency means unknown but SSL false still conflates absence with an unsuccessful check. Client-rendered widgets may be missed. Play Store matching uses only the first company-name word, so it can identify an unrelated app. CV matching scans broad keyword substrings and supplies a generic opportunity by default, increasing scores for almost every website. Add explicit audit status/evidence/confidence and timestamps; keep suggestions separate from confirmed facts. Existing stored audit/pitch values retain previous behavior until re-audited.

### Medium: pipeline update and completion semantics

A no-website re-audit can retain older contact/app/social fields because that update branch does not clear every enrichment field. Conversely, failed website re-audits can overwrite good contacts with empty values. Crawled legal name and structured address are collected but not incorporated into saved enrichment. Batch processing catches individual failures and still reports completed; logs are the only per-candidate failure evidence. Store per-candidate results, preserve good data when a check fails, and report saved/failed/skipped counts separately.

### Medium: external-source reliability

Discovery relies on HTML structures and public search availability. There is no structured retry/backoff, caching, consistent source rate limiting or robots handling. No live discovery run was performed during the audit. A 1,000-lead request can make many sequential calls and is not a result guarantee. Country aliases do not consistently share metropolitan expansion tables; Bangladesh appears in the UI without a country code or city table. DuckDuckGo snippets are in separate rows, but the finder looks for snippets in the same row as the result link, reducing available contact extraction.

### Low/Medium: contact quality and extraction claims

Social discovery uses substring checks rather than strict provider hostname/path classification. The safe-link filter prevents script-scheme navigation but does not prove a social URL belongs to the prospect. JSON-LD parsing can discard a node when address fields use nested objects. `PHONE_TEXT_REGEX` exists but is not used to extract plain-text phones. Email validation is a practical filter rather than full RFC/mailbox validation; the 85-character limit and placeholder filters can reject real addresses. Treat all harvested contact data as unverified until reviewed.

### Low: dashboard scale, accessibility and frontend behavior

The dashboard shows only the first 100 leads without pagination; exports include all leads regardless of visible filters. Gap links reset other filters. Polls use overlapping async intervals and continue after repeated transient network errors. Success reload closes the direct-audit pitch modal after 2.5 seconds. Several inputs have unassociated labels, hidden country checkboxes are inaccessible by keyboard, modal focus is not trapped/restored, and CSS has no responsive breakpoints. Clipboard/localStorage failures lack user feedback. Static asset extraction preserves the existing visual design; no browser visual/mobile/accessibility verification was performed.

### Low: release reproducibility and deployment documentation

Dependencies now have upper bounds but no exact transitive lockfile, vulnerability scan, CI, or formatter configuration. The local installed Django identifies itself as 6.1.1; the dependency range alone does not establish compatibility with every allowed Django/Python combination. This directory has no Git repository. Set up version control and CI, lock a tested dependency set, then run a dependency security scan and test the actual target deployment. Production HTTPS settings need a correctly configured TLS proxy/static-file setup; a deployment check cannot validate infrastructure.

## Verification

Offline verification uses bundled Python 3.12.14 with the checkout's existing site-packages, because `.venv/Scripts/python.exe` points to a missing Python 3.12 installation. The environment was not deleted or silently rebuilt.

- Django `check`: passes, zero reported issues.
- Migration drift `makemigrations --check --dry-run`: passes, no changes detected.
- Regression suite: **23 tests pass** using a separate test database and mocked network calls.
- JavaScript `node --check`: passes.
- Production configuration `check --deploy`: passes with debug disabled and a supplied test secret, zero reported issues. This does not verify a deployed server.
- Database SHA256 before edits: `7dd94ea29c80408aabbe8ffe1ed1e020e24f5fcee0eaaaad3bcfdaaee517fe50`.

Tests cover access control, actual CSRF enforcement, bad request handling, valid/busy prospecting dispatch, lead updates/404s, combined filters, formula-safe downloads, private addresses/redirects/body limits, failed timing, domain/MX behavior, honest pitches, safe links, disabled public Nominatim, DuckDuckGo wrapper decoding, website re-audit state, task ownership/capacity/snapshot isolation, and worker connection cleanup.

Not verified: live scraping accuracy/availability, browser visual interactions, high-load concurrency, target-host deployment, dependency vulnerability status, and compatibility across all versions in the dependency ranges. Existing database contents were not re-audited or modified.

Final database SHA256 matches the original checksum: the existing 205-lead database was unchanged. All first-party Python files also pass AST syntax parsing.
