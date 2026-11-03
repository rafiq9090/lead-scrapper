# DevLead OS

A Django application for discovering business leads, extracting public contact details, suggesting technical opportunities, and drafting outreach. Findings are heuristics that require review before contacting a prospect. Pitches are generated from templates; there is no LLM integration or automatic email sending.

## Windows setup

Install Python 3.12 or newer, then run these commands from the project directory:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --noreload
```

The existing checkout now has a working Python 3.12.14 virtual environment, repaired using the locally bundled Python runtime while preserving installed packages. Skip environment creation and `createsuperuser` when using this checkout. If the bundled runtime is later removed or moved, recreate `.venv` with your installed Python.

Open [the dashboard](http://127.0.0.1:8000/) and sign in through Django's admin login. The dashboard, exports, and APIs require an active staff account. Once the environment is healthy, `run.bat` starts the local server from any working directory. `--noreload` prevents development reloads from discarding running jobs.

**Existing account action:** the audit confirmed a staff account uses the weak password published in the original README. Change it before using the application beyond your own machine:

```powershell
.\.venv\Scripts\python.exe manage.py changepassword admin
```

## Features

- Batch discovery through DuckDuckGo Lite; country/city and industry variations.
- Optional business discovery through an owned or authorized Nominatim-compatible service.
- Direct public HTTP(S) website audits, with contact and social-link extraction.
- Android-app and chat-widget detection, response-header timing, and industry opportunity suggestions.
- Lead status and notes, CSV/XLSX exports, and draft outreach text.

A source listing without a website link is not proof that the business has no website. App/chat detection does not prove absence, and a chat widget is not proof of AI functionality. Response timing is one client-side sample including connection and redirect overhead; `0` means unknown.

## Configuration

See `.env.example` for available environment variables. It is a reference file and is **not automatically loaded**. For example:

```powershell
$env:DJANGO_DEBUG = 'true'
$env:DJANGO_ALLOWED_HOSTS = 'localhost,127.0.0.1,[::1]'
$env:DJANGO_SECRET_KEY = '<your-long-random-secret>'
```

Development uses a temporary random secret if none is set, so login sessions are invalidated after a restart. Production (`DJANGO_DEBUG=false`) requires a stable secret and enables HTTPS redirects, secure cookies, and HSTS. Configure hosts, TLS, and a static-file server before deploying.

`NOMINATIM_URL` is disabled by default. Only configure an endpoint you operate or have permission to use for this workload. The public service prohibits systematic place harvesting; see the [Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/). Discovery availability and result counts depend on external sources; 1,000 is a requested cap, not a guarantee.

## Parallel scraping

New prospecting batches use **2 discovery workers** and **4 lead-audit workers** by default. Configure them before starting the server:

```powershell
$env:DISCOVERY_WORKERS = '2'
$env:SCRAPER_WORKERS = '4'
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --noreload
```

Discovery accepts 1–4 workers and lead auditing accepts 1–8, per batch. Set both to `1` for sequential execution. The app permits two active batches. Each website hostname allows one active request across batches; discovery providers have shared request pacing. Network workers return results to the batch coordinator, which saves them under a process-wide scraper write lock. Failed leads do not stop the remaining audits, and progress follows completed work.

These controls apply within one server process. They do not make SQLite or in-memory jobs suitable for a multi-process deployment. The existing `reaudit_leads` command remains sequential.

## Project layout

```text
scrapper/
├── devlead/                    # Settings, root routing, ASGI/WSGI
├── leads/
│   ├── models.py               # Lead and LeadSearch schemas
│   ├── admin.py                # Staff administration
│   ├── urls.py                 # Stable application routes
│   ├── views/                  # Dashboard, JSON API, exports
│   ├── services/               # Job coordination and export safety
│   ├── scraper/                # Discovery, crawl, audit, validation, pitches
│   │   ├── discovery_data.py   # Country/city/niche reference tables
│   │   └── network.py          # Public-only bounded website reads
│   ├── static/leads/           # CSS and JavaScript
│   ├── templates/leads/        # Dashboard and focused partials
│   ├── templatetags/           # Safe external link rendering
│   ├── tests/                  # Offline regression suite
│   └── migrations/             # Existing schema history
├── docs/
│   ├── ARCHITECTURE.md
│   └── AUDIT.md
├── .env.example
├── .editorconfig
├── .gitignore
├── requirements.txt
├── run.bat
└── manage.py
```

`db.sqlite3` holds local data. `.venv`, caches, environment secrets, and database files are ignored by Git. This checkout currently has no Git repository.

## Verification

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test leads
```

The suite uses a separate test database and mocked external calls. Review [the quality upgrade](docs/DATA_QUALITY.md) for current behavior and verification. The [original audit](docs/AUDIT.md) records the earlier baseline and deployment risks.

## Deployment limits

This is currently a single-process application. Background jobs are bounded to two concurrent batches, retained in memory, and lost on restart. Multi-worker deployment needs durable job storage and a worker queue. SQLite and synchronous direct audits also limit concurrency. Staff accounts share the lead database; this is not a tenant-isolated service. Do not treat the development server as a production deployment.

## Evidence-based lead profiles

Click a company name to see all saved emails, phone numbers, addresses, opening hours, description, social links, website-published ratings, source evidence, checked pages and technical findings. Use **Re-audit website** to refresh that record. The dashboard has pagination and a **Needs review** filter. Downloads respect the active filters; Excel includes separate evidence and checked-page sheets.

App and chat results distinguish **Detected**, **Not detected in checked pages**, and **Unknown**. Unknown/failed checks do not generate missing-feature points or unsupported outreach claims. Website ratings are self-reported. Contact coverage is the fraction of six categories found in the latest crawl, not an accuracy or deliverability score.

The schema upgrade marks older leads **Needs re-audit**. Existing data is preserved; new evidence is collected when you re-audit. For a sequential batch refresh:

```powershell
.\.venv\Scripts\python.exe manage.py reaudit_leads --dry-run --limit 10
.\.venv\Scripts\python.exe manage.py reaudit_leads --limit 10
.\.venv\Scripts\python.exe manage.py reaudit_leads --lead-id 12 --limit 1
```

The command prioritizes records never checked, then the oldest checks. It uses public website requests and does not send outreach. A database snapshot from before the schema upgrade is saved in `backups/db-before-quality-2026-10-05.sqlite3`.
