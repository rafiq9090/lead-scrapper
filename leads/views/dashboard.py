from django.core.paginator import Paginator
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from ..models import Lead, LeadSearch
from ..services.selectors import filtered_leads


@staff_member_required
@ensure_csrf_cookie
def dashboard_view(request):
    leads = filtered_leads(request.GET)
    page = Paginator(leads, 50).get_page(request.GET.get('page'))
    filters = request.GET.copy()
    filters.pop('page', None)
    links = []
    for key, label in [('needs_review', 'Needs review'), ('missing_website', 'No website listed'),
                       ('missing_app', 'App not detected'), ('missing_chatbot', 'Chat not detected'),
                       ('slow_server', 'Slow response sample'), ('high_score', 'Score 70+')]:
        values = filters.copy()
        values['gap'] = key
        links.append({'key': key, 'label': label, 'url': '?' + values.urlencode()})
    return render(request, 'leads/dashboard.html', {
        'leads': page.object_list, 'page_obj': page, 'filter_query': filters.urlencode(), 'filter_links': links,
        'total_leads': Lead.objects.count(),
        'missing_website_count': Lead.objects.filter(has_website=False, audit_status='source_only').count(),
        'missing_android_count': Lead.objects.filter(android_status='not_detected').count(),
        'missing_chatbot_count': Lead.objects.filter(chatbot_status='not_detected').count(),
        'high_opp_count': Lead.objects.filter(lead_score__gte=70, audit_status__in=['partial', 'complete']).count(),
        'contacted_count': Lead.objects.filter(status__in=['CONTACTED', 'MEETING', 'WON']).count(),
        'current_gap': request.GET.get('gap', ''), 'current_status': request.GET.get('status', ''),
        'current_country': request.GET.get('country', ''), 'search_query': request.GET.get('q', ''),
        'current_batch': request.GET.get('batch', ''),
        'batch_obj': LeadSearch.objects.filter(pk=request.GET.get('batch')).first() if request.GET.get('batch') else None,
        'available_countries': Lead.objects.exclude(country='').order_by('country').values_list('country', flat=True).distinct(),
        'recent_searches': LeadSearch.objects.all()[:5],
    })
