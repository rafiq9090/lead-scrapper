"""Draft outreach only from current observations, with uncertainty preserved."""


def generate_cold_pitch(lead_data):
    company = lead_data.get('company_name') or 'your team'
    points = []
    if not lead_data.get('has_website', True):
        points.append('The listing I found did not include a website link. Do you have an existing website or booking page?')
    if lead_data.get('android_status') == 'not_detected':
        points.append('I did not find an Android app link on the website pages checked. Is a customer app relevant to your plans?')
    if lead_data.get('chatbot_status') == 'not_detected':
        points.append('The checked pages did not show a known chat widget. Would after-hours inquiry support be useful?')
    latency = lead_data.get('server_response_time_ms', 0)
    if latency > 800:
        points.append(f'One automated response-header sample was {latency}ms, including connection overhead. A repeated performance review could establish whether optimization would help.')
    if lead_data.get('cv_opportunity'):
        points.append('An industry idea we could explore: ' + lead_data['cv_opportunity'] + '.')
    if not points:
        points.append('I would like to understand your current software priorities before suggesting any changes.')
    subject = f'A software question for {company}'
    body = f'Hi {company} team,\n\n' + '\n\n'.join(points)
    body += '\n\nThese are preliminary observations, so please correct anything that does not reflect your current setup.\n\nWould a short discussion be useful?\n\nBest regards,\nZedan & Engineering Team'
    return subject, body
