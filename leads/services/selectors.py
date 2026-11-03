"""One filter definition for the dashboard and downloadable lead data."""
from django.db.models import Q
from ..models import Lead


def filtered_leads(params):
    leads = Lead.objects.all()
    if params.get('batch'):
        leads = leads.filter(search_batch_id=params['batch'])
    if params.get('country'):
        leads = leads.filter(country__iexact=params['country'])
    if params.get('status'):
        leads = leads.filter(status=params['status'])
    if params.get('q'):
        query = params['q']
        leads = leads.filter(Q(company_name__icontains=query) | Q(domain__icontains=query)
                             | Q(niche__icontains=query) | Q(primary_email__icontains=query))
    gap = params.get('gap')
    if gap == 'missing_website':
        leads = leads.filter(has_website=False, audit_status='source_only')
    elif gap == 'missing_app':
        leads = leads.filter(android_status='not_detected')
    elif gap == 'missing_chatbot':
        leads = leads.filter(chatbot_status='not_detected')
    elif gap == 'slow_server':
        leads = leads.filter(audit_report__checks__server__status='measured', server_response_time_ms__gt=800)
    elif gap == 'high_score':
        leads = leads.filter(audit_status__in=['partial', 'complete'], lead_score__gte=70)
    elif gap == 'needs_review':
        leads = leads.filter(audit_status__in=['unreviewed', 'failed', 'partial', 'source_only'])
    return leads.order_by('-lead_score', '-created_at', '-pk')
