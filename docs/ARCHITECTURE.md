# Architecture

## Request flow

Django root routing delegates to `leads.urls`. Views are separated into dashboard rendering, staff-only JSON endpoints, and downloads. `leads.views` re-exports the public view functions, preserving the original URL names and paths.

The dashboard template includes navigation, metrics, prospecting controls, the lead table, and the pitch modal. Django static files supply CSS and JavaScript. Server-generated route attributes let JavaScript call APIs without template syntax in static assets. A hidden CSRF token supplies the required header on mutations.

## Prospecting flow

1. The API validates query, location, countries, and result count, then checks job capacity.
2. The process-local runner starts a daemon thread, associates the job with its staff owner, and closes thread-local database connections before and after execution.
3. The pipeline creates a search batch and asks the finder for business candidates. A bounded discovery pool runs source queries and merges unique results on the coordinator thread.
4. The coordinator prepares plain-data lead snapshots. A bounded enrichment pool crawls and audits candidates without ORM access. The coordinator merges evidence, assigns template pitches and saves results under a process-wide scraper write lock; source listings without website links use a shorter path.
5. The model calculates the opportunity score. Existing contact status and notes are retained on website re-audit.
6. The browser polls job snapshots. Completed and failed jobs have distinct UI handling.

## Boundaries

- `models.py`: persistence and scoring; no HTTP calls.
- `views/`: request handling, access checks, validation, responses.
- `services/jobs.py`: bounded job lifecycle and polling snapshots.
- `services/exports.py`: neutralization of spreadsheet formula prefixes, reused by web and admin CSV exports.
- `scraper/finder.py`: external discovery orchestration; reference tables live in `discovery_data.py`.
- `scraper/concurrency.py`: bounded worker pools, per-host request serialization, provider pacing and scraper write lock.
- `scraper/crawler.py`: bounded page crawling and contact extraction.
- `scraper/auditor.py`: app/widget detection, response timing, industry suggestions.
- `scraper/network.py`: public address validation, explicit redirect checks, response bounds, verified TLS through HTTPX defaults.
- `scraper/validator.py`: local public-suffix parsing, contact syntax and advisory MX checks.
- `scraper/pitch_generator.py`: deterministic draft text.

## Persistence and operational constraints

The SQLite database path and existing migrations remain intact. Migration `0004_lead_evidence_and_audit_states` adds contact enrichment, source evidence, current check states and a last-checked timestamp. Legacy rows default to unreviewed. `Lead.domain` is indexed but not unique. Scraper writes are serialized within one process, but other processes or write paths still need database-level uniqueness and concurrency handling. Registered-domain grouping also merges branches and may merge unrelated businesses hosted beneath one domain. Website-less OSM candidates now use an OSM object identifier rather than a company-name slug.

Job state is local to one Python process. A restart loses progress; another worker cannot retrieve the job. Two batches may run at once, each with 2 discovery workers (configurable 1–4) and 4 enrichment workers (configurable 1–8). Pools submit only a bounded number of tasks, isolate individual failures and report completion order. Early discovery completion cancels pending tasks and waits for already-running requests.

Requests to the same website hostname are serialized across batches and direct audits; different hosts can overlap. DuckDuckGo permits two in-flight queries, custom Nominatim one, with request starts spaced at least one second apart per provider. Waiting for a website slot is excluded from response timing. All locks and pacing are process-local. Durable jobs, user cancellation, cross-process limits and database uniqueness need a deliberate follow-up design.

DNS checks reduce SSRF exposure but are separated from HTTP connection resolution. Enforce outbound network restrictions in a production environment to handle DNS rebinding. Scraped findings and links must remain untrusted.

## Configuration

Django reads environment variables directly. The `.env.example` file documents them without adding a dotenv dependency. Development defaults to loopback hosts. Production requires a stable secret and HTTPS; a reverse proxy needs explicit, trustworthy forwarded-header configuration if TLS terminates before Django. Never trust arbitrary forwarded headers.


## Quality and provenance

`contacts.py` parses business JSON-LD graphs and references, explicit mail/tel links, visible-text contacts and strict social profile URLs. The crawler preserves the supplied path and final redirect origin, prioritizes contact/location pages, and records per-page outcomes within an eight-page default and a time budget. It saves no raw HTML in the database.

`audit_report` stores field evidence with observation timestamps, checked-page outcomes, current technical checks, warnings, missing/retained fields, email-domain DNS evidence, contact coverage and self-reported rating metadata. Contact coverage uses six categories and is not an accuracy probability. Status fields distinguish unknown from a completed negative scan. Existing contacts are merged and retained across failures; historical evidence remains labeled with its original timestamp.

The server audit reuses the crawler's homepage response. Android detection accepts exact Google Play links or validated smart-banner package IDs. Chat checks inspect widget resource hosts and initialization syntax. CV ideas use explicit industry terms and do not infer an opportunity from generic page text.

`services/selectors.py` shares filters between pagination and exports. `views/detail.py` renders all details and offers a CSRF-protected staff re-audit action. The `reaudit_leads` management command performs bounded sequential refreshes and supports a no-network dry run. It preserves record IDs, notes, workflow status and discovery metadata.

The environment was repaired against a compatible local Python 3.12.14 runtime without clearing installed packages. Normal `.venv/Scripts/python.exe` commands now work on this machine. The bundled Python path must remain present, or the environment must be recreated.
