import os
import threading
from unittest.mock import patch

from django.db import connections
from django.test import SimpleTestCase, TestCase

from leads.models import Lead
from leads.scraper.concurrency import parallel_results, website_slot, worker_count
from leads.scraper.finder import discover_businesses
from leads.scraper.pipeline import run_prospecting_batch


class WorkerTests(SimpleTestCase):
    @patch.dict(os.environ, {'SCRAPER_WORKERS': '999'})
    def test_worker_setting_is_bounded_and_invalid_values_fall_back(self):
        self.assertEqual(worker_count('SCRAPER_WORKERS', 4, 8), 8)
        with patch.dict(os.environ, {'SCRAPER_WORKERS': 'invalid'}):
            self.assertEqual(worker_count('SCRAPER_WORKERS', 4, 8), 4)
        with patch.dict(os.environ, {'SCRAPER_WORKERS': '0'}):
            self.assertEqual(worker_count('SCRAPER_WORKERS', 4, 8), 1)

    def test_early_close_does_not_enqueue_the_entire_input(self):
        consumed = []
        def items():
            for i in range(100):
                consumed.append(i)
                yield i
        results = parallel_results(lambda value: value, items(), 2)
        next(results)
        results.close()
        self.assertEqual(consumed, [0, 1])

    def test_worker_failure_does_not_drop_other_results(self):
        def work(value):
            if value == 2:
                raise ValueError('Test failure')
            return value * 2
        results = list(parallel_results(work, range(5), 2))
        self.assertEqual(len(results), 5)
        self.assertEqual(sorted(value for _, value, error in results if error is None), [0, 2, 6, 8])
        self.assertEqual(sum(error is not None for _, _, error in results), 1)

    def test_one_request_per_website_but_other_hosts_can_overlap(self):
        active, peak = {}, {}
        mutex = threading.Lock()
        first_entered, release = threading.Event(), threading.Event()
        same_host_entered, other_entered = threading.Event(), threading.Event()
        def work(item):
            with website_slot(item):
                key = 'same' if 'acme' in item else 'other'
                with mutex:
                    active[key] = active.get(key, 0) + 1
                    peak[key] = max(peak.get(key, 0), active[key])
                if item.endswith('/first'):
                    first_entered.set()
                    if not release.wait(3):
                        raise RuntimeError('Timed out waiting for test release')
                elif key == 'same':
                    same_host_entered.set()
                else:
                    other_entered.set()
                    release.set()
                with mutex:
                    active[key] -= 1
        first = threading.Thread(target=work, args=('https://acme.com/first',))
        first.start()
        try:
            self.assertTrue(first_entered.wait(3))
            list(parallel_results(work, ['https://www.acme.com/second', 'https://other.com/'], 2))
            self.assertTrue(other_entered.is_set())
            self.assertTrue(same_host_entered.is_set())
            self.assertEqual(peak['same'], 1)
        finally:
            release.set()
            first.join(3)

    @patch.dict(os.environ, {'DISCOVERY_WORKERS': '2', 'NOMINATIM_URL': ''})
    def test_discovery_runs_queries_in_parallel_and_merges_duplicates(self):
        barrier = threading.Barrier(2)
        threads = set()
        def query(task):
            threads.add(threading.get_ident())
            barrier.wait(3)
            return [{'website': 'https://www.shared.com', 'domain': 'shared.com'},
                    {'website': f'https://{task[1]}.com', 'domain': f'{task[1]}.com'}]
        tasks = [('duckduckgo', 'alpha', '', '', 3), ('duckduckgo', 'beta', '', '', 3)]
        with patch('leads.scraper.finder._discovery_queries', return_value=iter(tasks)), patch('leads.scraper.finder._discover_query', side_effect=query):
            leads = discover_businesses('Dental', max_results=3)
        self.assertEqual(len(threads), 2)
        self.assertEqual(len(leads), 3)
        self.assertEqual(sum(lead['domain'] == 'shared.com' for lead in leads), 1)

    @patch.dict(os.environ, {'DISCOVERY_WORKERS': '2', 'NOMINATIM_URL': ''})
    def test_discovery_enforces_result_cap_and_stops_submitting(self):
        consumed = []
        def tasks(*args):
            for i in range(100):
                consumed.append(i)
                yield ('duckduckgo', str(i), '', '', 1)
        def query(task):
            return [{'website': f'https://clinic{task[1]}.com'}]
        with patch('leads.scraper.finder._discovery_queries', side_effect=tasks), patch('leads.scraper.finder._discover_query', side_effect=query):
            leads = discover_businesses('Dental', max_results=1)
        self.assertEqual(len(leads), 1)
        self.assertEqual(consumed, [0, 1])


class ParallelBatchTests(TestCase):
    @patch.dict(os.environ, {'SCRAPER_WORKERS': '4'})
    def test_parallel_network_work_has_no_database_connection_and_saves_on_caller(self):
        barrier = threading.Barrier(4)
        caller = threading.get_ident()
        worker_ids, callback_ids, progress = set(), [], []
        candidates = [{'company_name': f'Clinic {i}', 'website': f'https://clinic{i}.com'} for i in range(8)]
        def crawl(url):
            self.assertIsNone(connections['default'].connection)
            worker_ids.add(threading.get_ident())
            barrier.wait(5)
            return {'audit_status': 'complete', 'combined_html': '<p>A business website with information.</p>'}
        def on_progress(current, harvested, target, name):
            callback_ids.append(threading.get_ident())
            progress.append(current)
        with patch('leads.scraper.pipeline.discover_businesses', return_value=candidates), patch('leads.scraper.pipeline.crawl_website', side_effect=crawl):
            batch, leads = run_prospecting_batch('Dental', '', max_results=8, progress_callback=on_progress)
        self.assertEqual(len(worker_ids), 4)
        self.assertNotIn(caller, worker_ids)
        self.assertEqual(set(callback_ids), {caller})
        self.assertEqual(progress, list(range(9)))
        self.assertEqual(len(leads), 8)
        self.assertEqual(Lead.objects.count(), 8)
        batch.refresh_from_db()
        self.assertEqual(batch.total_found, 8)

    @patch.dict(os.environ, {'SCRAPER_WORKERS': '2'})
    def test_failed_candidate_still_advances_progress_and_saves_other_leads(self):
        candidates = [{'company_name': str(i), 'website': f'https://clinic{i}.com'} for i in range(3)]
        def crawl(url):
            if 'clinic1' in url:
                raise RuntimeError('Fixture failure')
            return {'audit_status': 'failed'}
        progress = []
        with patch('leads.scraper.pipeline.discover_businesses', return_value=candidates), patch('leads.scraper.pipeline.crawl_website', side_effect=crawl), self.assertLogs('leads.scraper.pipeline', level='ERROR'):
            batch, leads = run_prospecting_batch('Dental', '', max_results=3, progress_callback=lambda current, *args: progress.append(current))
        self.assertEqual(len(leads), 2)
        self.assertEqual(batch.total_found, 2)
        self.assertEqual(progress, [0, 1, 2, 3])
