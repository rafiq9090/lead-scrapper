"""Validated staff-only JSON endpoints."""
import json
import logging
from functools import wraps

from django.http import JsonResponse
from django.urls import reverse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from ..models import Lead
from ..scraper.pipeline import process_single_lead
from ..scraper.validator import clean_domain
from ..scraper.network import validate_public_url
from ..services.jobs import get_job, start_job

logger = logging.getLogger(__name__)


def staff_api(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_active or not request.user.is_staff:
            return JsonResponse({'success': False, 'error': 'Staff login required.'}, status=403)
        return view(request, *args, **kwargs)
    return wrapped


def payload(request):
    try:
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST.dict()
    except (ValueError, UnicodeDecodeError):
        raise ValueError('Invalid JSON body.') from None
    if not isinstance(data, dict):
        raise ValueError('Request body must be an object.')
    return data


def text_field(data, key, default='', limit=255):
    value = data.get(key, default)
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError(f'{key} must be text with at most {limit} characters.')
    return value.strip()


def invalid(exc):
    return JsonResponse({'success': False, 'error': str(exc)}, status=400)


@staff_api
@require_POST
def api_start_prospecting(request):
    try:
        from ..scraper.finder import parse_google_url_details
        data = payload(request)
        query = text_field(data, 'query', limit=2048)
        location = text_field(data, 'location')
        if not query:
            raise ValueError('Query is required.')
        clean_query, clean_loc = parse_google_url_details(query, location)
        query = clean_query
        if not location and clean_loc:
            location = clean_loc
        countries = data.get('countries', [])
        if isinstance(countries, str):
            countries = [c.strip() for c in countries.split(',') if c.strip()]
        if not isinstance(countries, list) or any(not isinstance(c, str) or len(c) > 100 for c in countries):
            raise ValueError('countries must be a list of country names.')
        countries = list(dict.fromkeys(c.strip() for c in countries if c.strip()))
        if len(', '.join(countries)) > 255:
            raise ValueError('Combined country names must be at most 255 characters.')
        count = data.get('max_results', 10)
        if isinstance(count, bool) or not isinstance(count, (str, int)):
            raise ValueError('max_results must be an integer.')
        try:
            count = int(count)
        except ValueError:
            raise ValueError('max_results must be an integer.') from None
        fast_mode = bool(data.get('fast_mode', True))
    except ValueError as exc:
        return invalid(exc)
    try:
        task_id = start_job(query, location, countries, count, request.user.pk, fast_mode=fast_mode)
    except RuntimeError as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=429)
    return JsonResponse({'success': True, 'task_id': task_id, 'max_results': count, 'fast_mode': fast_mode})


@staff_api
@require_GET
def api_task_status(request, task_id):
    task = get_job(task_id, request.user.pk)
    if task is None:
        return JsonResponse({'success': False, 'error': 'Task not found.'}, status=404)
    return JsonResponse({'success': True, **task})


@staff_api
@require_POST
def api_audit_single_domain(request):
    try:
        data = payload(request)
        url = text_field(data, 'url', limit=500)
        niche = text_field(data, 'niche', default='Software & B2B')
        if not url:
            raise ValueError('Website URL is required.')
        url = validate_public_url(url)
    except ValueError as exc:
        return invalid(exc)
    domain = clean_domain(url)
    try:
        lead = process_single_lead({
            'company_name': domain.split('.')[0].capitalize(), 'website': url,
            'domain': domain, 'niche': niche, 'location': 'Direct Audit',
        })
        if not lead:
            return invalid(ValueError('Could not process domain.'))
    except Exception:
        logger.exception('Direct domain audit failed')
        return JsonResponse({'success': False, 'error': 'Audit failed. Check the server logs.'}, status=500)
    fields = ('company_name', 'domain', 'website', 'primary_email', 'all_emails', 'phone',
              'linkedin_url', 'has_android_app', 'android_app_name', 'android_app_url',
              'has_chatbot', 'detected_chat_widget', 'server_response_time_ms', 'server_type',
              'cv_opportunity', 'lead_score', 'status', 'pitch_subject', 'pitch_email',
              'all_phones', 'addresses', 'address', 'description', 'opening_hours', 'source_name', 'source_url',
              'audit_status', 'android_status', 'chatbot_status', 'audit_report', 'last_audited_at')
    return JsonResponse({'success': True, 'lead': {'id': lead.pk, **{key: getattr(lead, key) for key in fields},
        'detail_url': reverse('leads:detail', args=[lead.pk]),
        'has_android_app': lead.has_android_app if lead.android_status != 'unknown' else None,
        'has_chatbot': lead.has_chatbot if lead.chatbot_status != 'unknown' else None}})


@staff_api
@require_POST
def api_update_lead_status(request, lead_id):
    lead = get_object_or_404(Lead, pk=lead_id)
    try:
        data = payload(request)
        if 'status' in data:
            status = text_field(data, 'status', limit=20)
            if status not in dict(Lead.STATUS_CHOICES):
                raise ValueError('Invalid lead status.')
            lead.status = status
        if 'notes' in data:
            lead.notes = text_field(data, 'notes', limit=10000)
    except ValueError as exc:
        return invalid(exc)
    lead.save(update_fields=['status', 'notes', 'updated_at'])
    return JsonResponse({'success': True, 'status': lead.status})
