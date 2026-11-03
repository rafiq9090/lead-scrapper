"""Full lead profile, source evidence, and explicit single-lead re-audits."""
import logging
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST
from ..models import Lead
from ..scraper.pipeline import process_single_lead

logger = logging.getLogger(__name__)


@staff_member_required
@require_GET
def lead_detail(request, lead_id):
    lead = get_object_or_404(Lead, pk=lead_id)
    return render(request, 'leads/detail.html', {'lead': lead})


@staff_member_required
@require_POST
def reaudit_lead(request, lead_id):
    lead = get_object_or_404(Lead, pk=lead_id)
    if not lead.website:
        messages.error(request, 'Add a website in the admin panel before running a website audit.')
    else:
        try:
            process_single_lead({'company_name': lead.company_name, 'website': lead.website,
                                 'domain': lead.domain, 'niche': lead.niche}, lead_id=lead.pk)
            messages.success(request, 'Website check finished. Review the status, sources and any retained information below.')
        except Exception:
            logger.exception('Lead re-audit failed')
            messages.error(request, 'The re-audit could not be saved. Existing information is preserved.')
    return redirect('leads:detail', lead_id=lead.pk)
