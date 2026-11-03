"""Discover, enrich and preserve leads with explicit evidence and audit outcomes."""
import hashlib
import logging
from urllib.parse import urlsplit

from django.db import transaction
from django.utils import timezone
from leads.models import Lead, LeadSearch
from .finder import discover_businesses
from .crawler import crawl_website
from .auditor import run_full_tech_audit
from .pitch_generator import generate_cold_pitch
from .concurrency import SCRAPER_WRITE_LOCK, parallel_results, worker_count

logger = logging.getLogger(__name__)


def prepare_lead_input(raw_info, lead_id=None, fast_mode=False):
    """Read prior values on the caller thread; workers receive plain data only."""
    website = (raw_info.get('website') or '').strip()
    if website and not website.startswith(('http://', 'https://')):
        website = 'https://' + website
    company_name = (raw_info.get('company_name') or '').strip()
    # Preserve meaningful subdomains. Registered domains are still used for email ranking.
    domain = (urlsplit(website).hostname or '').lower().removeprefix('www.') if website else raw_info.get('domain', '')
    if not domain:
        if not company_name:
            return None
        identity = '|'.join(str(raw_info.get(k, '')) for k in ('company_name', 'address', 'location', 'country'))
        domain = hashlib.sha256(identity.encode()).hexdigest()[:24] + '.local'
    with SCRAPER_WRITE_LOCK:
        previous = Lead.objects.get(pk=lead_id) if lead_id is not None else Lead.objects.filter(domain=domain).first()
        snapshot = {key: getattr(previous, key) for key in ('website', 'company_name', 'niche', 'source_name', 'source_url')} if previous else {}
    return {'raw_info': dict(raw_info), 'website': website, 'company_name': company_name,
            'domain': domain, 'previous': snapshot, 'lead_id': lead_id, 'fast_mode': fast_mode}


def enrich_lead(task):
    """Network/HTML work only; never open a database connection here."""
    raw_info, previous = task['raw_info'], task['previous']
    website, company_name, domain = task['website'], task['company_name'], task['domain']
    fast_mode = task.get('fast_mode', False)
    website = website or (previous.get('website', '') if previous else '') or ''
    niche = raw_info.get('niche') or (previous.get('niche', '') if previous else '')
    crawl = crawl_website(website, fast_mode=fast_mode) if website else {}
    tech = run_full_tech_audit(company_name, domain, website, crawl.get('combined_html', ''), niche, crawl_result=crawl) if website else {}
    now = timezone.now()
    source_url = raw_info.get('source_url') or website
    evidence = [{**entry, 'observed_at': now.isoformat()} for entry in crawl.get('evidence', [])]
    for field in ('phone', 'address', 'country'):
        if raw_info.get(field) and source_url:
            evidence.append({'field': field, 'value': raw_info[field], 'url': source_url,
                             'method': 'discovery_listing', 'confidence': 'medium', 'observed_at': now.isoformat()})
    socials = crawl.get('social_links', {})
    candidates = {
        'company_name': crawl.get('legal_name') or (previous.get('company_name', '') if previous else '') or company_name,
        'website': crawl.get('final_url') or website,
        'niche': niche, 'location': raw_info.get('location', ''),
        'country': crawl.get('country') or raw_info.get('country', ''),
        'address': crawl.get('structured_address') or raw_info.get('address', ''),
        'phone': crawl.get('phone') or raw_info.get('phone', ''),
        'primary_email': crawl.get('primary_email', ''),
        'all_emails': crawl.get('all_emails', []), 'all_phones': crawl.get('all_phones', []),
        'addresses': crawl.get('addresses', []), 'opening_hours': crawl.get('opening_hours', []),
        'description': crawl.get('description', ''),
        'source_name': raw_info.get('source') or (previous.get('source_name', '') if previous else '') or ('Direct audit' if website else 'Listing'),
        'source_url': raw_info.get('source_url') or (previous.get('source_url', '') if previous else '') or source_url,
        **{f'{key}_url': socials.get(key, '') for key in ('linkedin', 'facebook', 'instagram', 'twitter')},
    }
    if candidates['phone'] and candidates['phone'] not in candidates['all_phones']:
        candidates['all_phones'].insert(0, candidates['phone'])
    if candidates['address'] and candidates['address'] not in candidates['addresses']:
        candidates['addresses'].insert(0, candidates['address'])
    return {'task': task, 'crawl': crawl, 'tech': tech, 'now': now,
            'evidence': evidence, 'socials': socials, 'candidates': candidates, 'website': website}


def save_enrichment(result, search_batch=None):
    """Persist on the coordinator thread, serializing scraper writes across batches."""
    task, crawl, tech = result['task'], result['crawl'], result['tech']
    now, evidence, socials = result['now'], result['evidence'], result['socials']
    candidates, website = result['candidates'], result['website']
    lead_id, domain, company_name = task['lead_id'], task['domain'], task['company_name']
    # Network work happens outside the transaction. Merge against the latest row inside it.
    with SCRAPER_WRITE_LOCK, transaction.atomic():
        if lead_id is not None:
            lead = Lead.objects.get(pk=lead_id)
        else:
            lead, _ = Lead.objects.get_or_create(domain=domain, defaults={'company_name': company_name or domain})
        lead = Lead.objects.select_for_update().get(pk=lead.pk)
        retained = []
        for field, value in candidates.items():
            old = getattr(lead, field)
            if isinstance(value, list):
                if any(item not in value for item in old):
                    retained.append(field)
                value = list(dict.fromkeys(value + old))[:100]
            elif not value and old:
                retained.append(field)
                continue
            if value:
                model_field = Lead._meta.get_field(field)
                if isinstance(value, str) and model_field.max_length:
                    value = value[:model_field.max_length]
                setattr(lead, field, value)
        lead.has_website = bool(lead.website)
        lead.audit_status = crawl.get('audit_status', 'failed') if website else 'source_only'
        lead.android_status = tech.get('android_status', 'unknown')
        lead.chatbot_status = tech.get('chatbot_status', 'unknown')
        # Preserve last known positives on unknown checks; expose current status separately.
        for status, fields in ((lead.android_status, ('has_android_app', 'android_app_name', 'android_app_url')),
                               (lead.chatbot_status, ('has_chatbot', 'detected_chat_widget'))):
            if status != 'unknown':
                for field in fields:
                    setattr(lead, field, tech.get(field, False if field.startswith('has_') else ''))
            else:
                retained.extend(field for field in fields if getattr(lead, field))
        checks = tech.get('checks', {})
        if checks.get('server', {}).get('status') == 'measured':
            for field in ('server_response_time_ms', 'server_type', 'ssl_active'):
                setattr(lead, field, tech[field])
        else:
            retained.extend(field for field in ('server_response_time_ms', 'server_type', 'ssl_active') if getattr(lead, field))
        lead.cv_opportunity = tech.get('cv_opportunity', '') if lead.audit_status in ('complete', 'partial') else ''
        lead.last_audited_at = now
        rating = crawl.get('rating', {})
        if rating:
            lead.rating = rating['value']
            if 'review_count' in rating:
                lead.reviews_count = rating['review_count']
        # Earlier evidence is retained with its original timestamp, without relabeling it as fresh.
        old_evidence = lead.audit_report.get('evidence', [])
        current_keys = {(e['field'], e['value'], e['url']) for e in evidence}
        historic = [{**e, 'retained': True} for e in old_evidence
                    if (e.get('field'), e.get('value'), e.get('url')) not in current_keys]
        report = {'version': 2, 'pages': crawl.get('pages', []), 'evidence': (evidence + historic)[:400],
                  'checks': checks, 'warnings': crawl.get('warnings', []),
                  'email_dns': crawl.get('email_dns', {'status': 'not_checked'}),
                  'retained_fields': sorted(set(retained)), 'cms': tech.get('detected_cms', 'Unknown'),
                  'rating': rating}
        coverage = {'email': bool(crawl.get('primary_email')), 'phone': bool(crawl.get('phone')),
                    'address': bool(crawl.get('structured_address')),
                    'social profile': any(socials.values()), 'business name': bool(crawl.get('legal_name')),
                    'opening hours': bool(crawl.get('opening_hours'))}
        report['missing_fields'] = [key for key, found in coverage.items() if not found]
        report['contact_coverage'] = round(100 * sum(coverage.values()) / len(coverage))
        lead.audit_report = report
        if search_batch is not None:
            lead.search_batch = search_batch
        lead.calculate_score()
        lead.pitch_subject, lead.pitch_email = generate_cold_pitch({
            'company_name': lead.company_name, 'niche': lead.niche, 'location': lead.location,
            'has_website': lead.has_website, 'android_status': lead.android_status,
            'chatbot_status': lead.chatbot_status, 'audit_status': lead.audit_status,
            'server_response_time_ms': tech.get('server_response_time_ms', 0),
            'cv_opportunity': lead.cv_opportunity,
        })
        lead.pitch_subject = lead.pitch_subject[:255]
        lead.save()
    return lead


def process_single_lead(raw_info, search_batch=None, lead_id=None):
    task = prepare_lead_input(raw_info, lead_id)
    return save_enrichment(enrich_lead(task), search_batch) if task else None


def run_prospecting_batch(query, location, countries=None, max_results=10, log_callback=None, progress_callback=None, fast_mode=True):
    from .finder import parse_google_url_details
    clean_query, detected_loc = parse_google_url_details(query, location)
    clean_loc = location or detected_loc
    country_str = ', '.join(countries) if isinstance(countries, list) else (countries or '')
    with SCRAPER_WRITE_LOCK:
        batch = LeadSearch.objects.create(query=clean_query, location=clean_loc, countries=country_str)
    default_workers = 8 if fast_mode else 4
    max_workers = 12 if fast_mode else 8
    workers = worker_count('SCRAPER_WORKERS', default_workers, max_workers)
    if log_callback:
        mode_desc = "Fast Scrape Batch" if fast_mode else "Batch"
        log_callback(f'{mode_desc}: searching for {clean_query} in {clean_loc or country_str or "selected region"}...')
    candidates = discover_businesses(clean_query, clean_loc, countries=countries, max_results=max_results,
                                    log_callback=log_callback, fast_mode=fast_mode)
    processed, failed, completed = [], 0, 0
    if log_callback:
        log_callback(f'Found {len(candidates)} candidates; auditing with {workers} parallel workers.')
    if progress_callback:
        progress_callback(0, len(candidates), max_results, 'Starting parallel audits')

    def tasks():
        for raw in candidates:
            task = prepare_lead_input(raw, fast_mode=fast_mode)
            if task:
                yield task

    results = parallel_results(enrich_lead, tasks(), workers)
    try:
        for task, result, error in results:
            name = task['company_name'] or task['domain']
            saved_lead = None
            try:
                if error:
                    raise error
                saved_lead = save_enrichment(result, batch)
                processed.append(saved_lead)
                if log_callback:
                    log_callback(f'{name}: {saved_lead.get_audit_status_display()}')
            except Exception:
                failed += 1
                logger.exception('Candidate enrichment failed')
                if log_callback:
                    log_callback(f'Could not save {name}; see server logs.')
            finally:
                completed += 1
                if progress_callback:
                    progress_callback(completed, len(candidates), max_results, name, lead=saved_lead, batch_id=batch.id)
    finally:
        results.close()
    with SCRAPER_WRITE_LOCK:
        batch.total_found = len(processed)
        batch.save(update_fields=['total_found'])
    if log_callback:
        incomplete = sum(lead.audit_status in ('partial', 'failed', 'source_only') for lead in processed)
        log_callback(f'Saved {len(processed)} leads ({incomplete} incomplete website checks); {failed} save failures.')
    return batch, processed
