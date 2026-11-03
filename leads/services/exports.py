"""Spreadsheet-safe, consistent exports of lead data and audit state."""
import re

HEADERS = ['Company Name', 'Country', 'Domain', 'Website', 'Primary Email', 'All Emails',
           'Primary Phone', 'All Phones', 'Address', 'All Addresses', 'Opening Hours', 'Description',
           'LinkedIn', 'Facebook', 'Instagram', 'X / Twitter', 'Industry', 'Search Location',
           'Discovery Source', 'Source URL', 'Audit Status', 'Last Checked', 'Contact Coverage (%)',
           'Android Check', 'App URL', 'Chat Check', 'Widget', 'Response Sample (ms)', 'Server',
           'CMS', 'HTTPS Check', 'Email DNS Status', 'Industry Suggestion', 'Opportunity Score',
           'Website Rating', 'Rating Scale', 'Website Review Count', 'Pipeline Status', 'Notes', 'Pitch Subject', 'Pitch Body', 'Missing Fields', 'Retained Fields']


def safe_cell(value):
    if isinstance(value, str):
        value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', value)
        if value.lstrip().startswith(('=', '+', '-', '@')):
            return "'" + value
    return value


def lead_row(lead):
    report = lead.audit_report
    measured = report.get('checks', {}).get('server', {}).get('status') == 'measured'
    return [safe_cell(value) for value in [
        lead.company_name, lead.country, lead.domain, lead.website, lead.primary_email,
        '; '.join(lead.all_emails), lead.phone, '; '.join(lead.all_phones), lead.address,
        '; '.join(lead.addresses), '; '.join(lead.opening_hours), lead.description,
        lead.linkedin_url, lead.facebook_url, lead.instagram_url, lead.twitter_url,
        lead.niche, lead.location, lead.source_name, lead.source_url, lead.get_audit_status_display(),
        lead.last_audited_at.isoformat() if lead.last_audited_at else '', report.get('contact_coverage', ''),
        lead.get_android_status_display(), lead.android_app_url if lead.android_status == 'detected' else '',
        lead.get_chatbot_status_display(), lead.detected_chat_widget if lead.chatbot_status == 'detected' else '',
        lead.server_response_time_ms if measured else '', lead.server_type if measured else '',
        report.get('cms', ''), ('Yes' if lead.ssl_active else 'No') if measured else 'Unknown',
        report.get('email_dns', {}).get('status', 'not_checked'), lead.cv_opportunity,
        lead.lead_score if lead.audit_status != 'unreviewed' else '',
        report.get('rating', {}).get('value', ''), report.get('rating', {}).get('best', 'Unspecified'),
        report.get('rating', {}).get('review_count', ''), lead.status, lead.notes,
        lead.pitch_subject, lead.pitch_email, '; '.join(report.get('missing_fields', [])),
        '; '.join(report.get('retained_fields', [])),
    ]]
