"""Explicit, sequential refresh of existing website leads."""
from collections import Counter
from django.core.management.base import BaseCommand, CommandError
from django.db.models import F
from leads.models import Lead
from leads.scraper.pipeline import process_single_lead


class Command(BaseCommand):
    help = 'Re-audit existing website leads, preserving their IDs, notes and status.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=10)
        parser.add_argument('--lead-id', type=int, action='append', dest='lead_ids')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        if not 1 <= options['limit'] <= 1000:
            raise CommandError('--limit must be between 1 and 1000.')
        leads = Lead.objects.exclude(website='').exclude(website__isnull=True)
        if options['lead_ids']:
            leads = leads.filter(pk__in=options['lead_ids'])
        leads = list(leads.order_by(F('last_audited_at').asc(nulls_first=True), 'pk')[:options['limit']])
        counts = Counter()
        for lead in leads:
            if options['dry_run']:
                self.stdout.write(f'{lead.pk}: {lead.company_name} — {lead.website}')
                continue
            try:
                refreshed = process_single_lead({'company_name': lead.company_name, 'website': lead.website,
                                                 'domain': lead.domain, 'niche': lead.niche}, lead_id=lead.pk)
                counts[refreshed.audit_status] += 1
                self.stdout.write(f'{lead.pk}: {refreshed.get_audit_status_display()}')
            except Exception as exc:
                counts['save_error'] += 1
                self.stderr.write(f'{lead.pk}: re-audit could not be saved ({type(exc).__name__})')
        self.stdout.write(f'{len(leads)} selected. ' + ('Dry run; no requests or changes.' if options['dry_run'] else str(dict(counts))))
