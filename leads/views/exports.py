import csv
import json
from io import BytesIO
from django.http import HttpResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_GET
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from ..services.exports import HEADERS, lead_row, safe_cell
from ..services.selectors import filtered_leads


@staff_member_required
@require_GET
def export_leads_csv(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="prospects_leads.csv"'
    writer = csv.writer(response)
    writer.writerow(HEADERS + ['Evidence JSON', 'Checked Pages JSON'])
    for lead in filtered_leads(request.GET).iterator():
        writer.writerow(lead_row(lead) + [safe_cell(json.dumps(lead.audit_report.get(key, []), ensure_ascii=False)) for key in ('evidence', 'pages')])
    return response


@staff_member_required
@require_GET
def export_leads_excel(request):
    book = Workbook()
    sheet = book.active
    sheet.title = 'B2B Leads'
    sheet.append(HEADERS)
    evidence = book.create_sheet('Source Evidence')
    evidence.append(['Lead ID', 'Company', 'Field', 'Value', 'Source URL', 'Method', 'Source Strength', 'Observed At', 'Retained'])
    pages = book.create_sheet('Pages Checked')
    pages.append(['Lead ID', 'Company', 'URL', 'Status', 'HTTP Status', 'Reason'])
    for lead in filtered_leads(request.GET).iterator():
        sheet.append(lead_row(lead))
        for item in lead.audit_report.get('evidence', []):
            evidence.append([safe_cell(v) for v in [lead.pk, lead.company_name, item.get('field'), item.get('value'), item.get('url'), item.get('method'), item.get('confidence'), item.get('observed_at'), item.get('retained', False)]])
        for page in lead.audit_report.get('pages', []):
            pages.append([safe_cell(v) for v in [lead.pk, lead.company_name, page.get('url'), page.get('status'), page.get('http_status'), page.get('reason')]])
    for worksheet in book:
        worksheet.freeze_panes = 'A2'
        worksheet.auto_filter.ref = worksheet.dimensions
        for cell in worksheet[1]:
            cell.font = Font(bold=True, color='FFFFFF')
            cell.fill = PatternFill('solid', fgColor='1E293B')
        for column in worksheet.columns:
            worksheet.column_dimensions[column[0].column_letter].width = min(45, max(15, max(len(str(c.value or '')) for c in column) + 2))
    output = BytesIO()
    book.save(output)
    response = HttpResponse(output.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="prospects_leads.xlsx"'
    return response
