from unittest.mock import patch
from django.test import SimpleTestCase
from leads.services import jobs


class JobTests(SimpleTestCase):
    def setUp(self):
        jobs._tasks.clear()

    def tearDown(self):
        jobs._tasks.clear()

    @patch('leads.services.jobs.threading.Thread')
    def test_capacity_ownership_and_snapshot_isolation(self, thread):
        task_id = jobs.start_job('Dental', '', [], 10, 1)
        self.assertIsNone(jobs.get_job(task_id, 2))
        snapshot = jobs.get_job(task_id, 1)
        snapshot['logs'].append('External change')
        self.assertNotIn('External change', jobs.get_job(task_id, 1)['logs'])
        jobs.start_job('Dental', '', [], 10, 1)
        with self.assertRaises(RuntimeError):
            jobs.start_job('Dental', '', [], 10, 1)

    @patch('leads.services.jobs.close_old_connections')
    @patch('leads.services.jobs.run_prospecting_batch', return_value=(None, [1, 2]))
    @patch('leads.services.jobs.threading.Thread')
    def test_worker_completes_and_closes_connections(self, thread, batch, close):
        task_id = jobs.start_job('Dental', '', [], 10, 1)
        jobs._worker(task_id, 'Dental', '', [], 10)
        snapshot = jobs.get_job(task_id, 1)
        self.assertTrue(snapshot['completed'])
        self.assertEqual(snapshot['total_found'], 2)
        self.assertEqual(close.call_count, 2)
