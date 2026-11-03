"""Bounded, process-local job runner for single-process development."""
import copy
import logging
import threading
import time
import uuid

from django.db import close_old_connections

from ..scraper.pipeline import run_prospecting_batch

logger = logging.getLogger(__name__)
_tasks = {}
_lock = threading.RLock()
MAX_RUNNING = 2
RETENTION_SECONDS = 3600


def start_job(query, location, countries, max_results, owner_id, fast_mode=True):
    with _lock:
        expired = [key for key, value in _tasks.items()
                   if value['completed'] and value.get('finished_at') and time.monotonic() - value['finished_at'] > RETENTION_SECONDS]
        for key in expired:
            del _tasks[key]
        # Limit retained history even when many short jobs finish within an hour.
        completed = [key for key, value in _tasks.items() if value['completed']]
        for key in completed[:-98]:
            del _tasks[key]
        if sum(not task['completed'] for task in _tasks.values()) >= MAX_RUNNING:
            raise RuntimeError('Two prospecting jobs are already running. Try again later.')
        task_id = str(uuid.uuid4())
        now_mono = time.monotonic()
        now_time = time.time()
        mode_prefix = "⚡ Fast Scrap" if fast_mode else "Standard Prospecting"
        _tasks[task_id] = {
            'task_id': task_id, 'owner_id': owner_id, 'status': 'running',
            'progress': 0, 'total': max_results, 'target_total': max_results,
            'harvested_count': 0, 'current_lead': '', 'leads_found': 0,
            'logs': [f'{mode_prefix} initialized...'], 'completed': False,
            'error': None, 'total_found': 0, 'fast_mode': fast_mode,
            'started_at': now_time, 'started_monotonic': now_mono,
            'finished_at': None, 'elapsed_seconds': 0.0,
            'duration_display': '00:00',
            'batch_id': None,
            'new_leads': [],
        }
        try:
            threading.Thread(target=_worker, args=(task_id, query, location, countries, max_results, fast_mode),
                             daemon=True).start()
        except Exception:
            del _tasks[task_id]
            raise
    return task_id


def get_job(task_id, owner_id):
    with _lock:
        task = _tasks.get(task_id)
        if not task or task['owner_id'] != owner_id:
            return None
        started_mono = task.get('started_monotonic', time.monotonic())
        if task['completed'] and task.get('finished_at'):
            elapsed = max(0.0, round(task['finished_at'] - started_mono, 1))
        else:
            elapsed = max(0.0, round(time.monotonic() - started_mono, 1))
        mins, secs = divmod(int(elapsed), 60)
        task['elapsed_seconds'] = elapsed
        task['duration_display'] = f"{mins:02d}:{secs:02d}"

        snapshot = copy.deepcopy(task)
        snapshot.pop('owner_id', None)
        snapshot.pop('started_monotonic', None)
        snapshot.pop('finished_at', None)
        return snapshot


def _worker(task_id, query, location, countries, max_results, fast_mode=True):
    close_old_connections()

    def log(message):
        with _lock:
            task = _tasks[task_id]
            task['logs'] = (task['logs'] + [message])[-80:]

    def progress(current, harvested, target, name, lead=None, batch_id=None):
        with _lock:
            task = _tasks[task_id]
            if batch_id and not task.get('batch_id'):
                task['batch_id'] = batch_id
            if lead:
                task.setdefault('new_leads', []).append({
                    'id': lead.pk,
                    'company_name': lead.company_name,
                    'website': lead.website or '',
                    'domain': lead.domain or '',
                    'country': lead.country or '',
                    'has_website': lead.has_website,
                    'primary_email': lead.primary_email or '',
                    'phone': lead.phone or '',
                    'linkedin_url': lead.linkedin_url or '',
                    'audit_status_display': lead.get_audit_status_display(),
                    'android_status': lead.android_status,
                    'chatbot_status': lead.chatbot_status,
                    'detected_chat_widget': lead.detected_chat_widget or '',
                    'server_response_time_ms': lead.server_response_time_ms,
                    'server_status': lead.audit_report.get('checks', {}).get('server', {}).get('status', '') if hasattr(lead, 'audit_report') and isinstance(lead.audit_report, dict) else '',
                    'cv_opportunity': lead.cv_opportunity or '',
                    'lead_score': lead.lead_score,
                    'status': lead.status,
                    'pitch_subject': lead.pitch_subject or '',
                    'pitch_email': lead.pitch_email or '',
                    'detail_url': f"/leads/{lead.pk}/",
                })
            task.update(progress=current, harvested_count=harvested,
                        target_total=target, total=harvested,
                        current_lead=name, leads_found=current)

    try:
        batch, leads = run_prospecting_batch(query, location, countries, max_results, log, progress, fast_mode=fast_mode)
        with _lock:
            _tasks[task_id].update(status='completed', total_found=len(leads), batch_id=batch.id if batch else None)
    except Exception:
        logger.exception('Prospecting job %s failed', task_id)
        with _lock:
            _tasks[task_id].update(status='error', error='Prospecting failed. Check the server logs.')
    finally:
        with _lock:
            finished_mono = time.monotonic()
            started_mono = _tasks[task_id].get('started_monotonic', finished_mono)
            elapsed = max(0.0, round(finished_mono - started_mono, 1))
            mins, secs = divmod(int(elapsed), 60)
            _tasks[task_id].update(completed=True, finished_at=finished_mono,
                                   elapsed_seconds=elapsed, duration_display=f"{mins:02d}:{secs:02d}")
        close_old_connections()
