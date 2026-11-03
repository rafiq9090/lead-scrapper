from django.db import models


class LeadSearch(models.Model):
    """Tracks prospecting search batches."""
    query = models.CharField(max_length=255, help_text="e.g. Logistics, Dental Clinics, Warehouse")
    location = models.CharField(max_length=255, help_text="e.g. Chicago, London, Dubai")
    countries = models.CharField(max_length=255, blank=True, default='', help_text="Comma-separated country names/codes")
    total_found = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.query} in {self.location} ({self.total_found} leads)"


class Lead(models.Model):
    """Enriched B2B Lead with software agency gap analysis."""
    STATUS_CHOICES = [
        ('NEW', 'New'),
        ('CONTACTED', 'Contacted'),
        ('MEETING', 'Meeting Scheduled'),
        ('WON', 'Won Client'),
        ('ARCHIVED', 'Archived'),
    ]
    CHECK_CHOICES = [('unknown', 'Unknown'), ('detected', 'Detected'),
                     ('not_detected', 'Not detected in checked pages')]
    AUDIT_CHOICES = [('unreviewed', 'Needs re-audit'), ('source_only', 'Listing only'),
                     ('failed', 'Website check failed'), ('partial', 'Partial crawl'),
                     ('complete', 'Crawl completed')]

    # Business Information
    company_name = models.CharField(max_length=255)
    website = models.URLField(max_length=500, blank=True, null=True)
    domain = models.CharField(max_length=255, db_index=True)
    phone = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    niche = models.CharField(max_length=255, blank=True)
    location = models.CharField(max_length=255, blank=True)
    country = models.CharField(max_length=100, blank=True, default='')
    rating = models.FloatField(default=0.0)
    reviews_count = models.IntegerField(default=0)

    # Discovered Contact Information
    primary_email = models.CharField(max_length=255, blank=True)
    all_emails = models.JSONField(default=list, blank=True)
    all_phones = models.JSONField(default=list, blank=True)
    addresses = models.JSONField(default=list, blank=True)
    description = models.TextField(blank=True)
    opening_hours = models.JSONField(default=list, blank=True)
    source_name = models.CharField(max_length=100, blank=True)
    source_url = models.URLField(max_length=2000, blank=True)
    audit_status = models.CharField(max_length=20, choices=AUDIT_CHOICES, default='unreviewed')
    android_status = models.CharField(max_length=20, choices=CHECK_CHOICES, default='unknown')
    chatbot_status = models.CharField(max_length=20, choices=CHECK_CHOICES, default='unknown')
    audit_report = models.JSONField(default=dict, blank=True)
    last_audited_at = models.DateTimeField(null=True, blank=True)
    linkedin_url = models.URLField(max_length=500, blank=True)
    facebook_url = models.URLField(max_length=500, blank=True)
    instagram_url = models.URLField(max_length=500, blank=True)
    twitter_url = models.URLField(max_length=500, blank=True)

    # Tech Gaps (Your Software Services)
    has_website = models.BooleanField(default=True)
    has_android_app = models.BooleanField(default=False)
    android_app_name = models.CharField(max_length=255, blank=True)
    android_app_url = models.URLField(max_length=500, blank=True)

    has_chatbot = models.BooleanField(default=False)
    detected_chat_widget = models.CharField(max_length=255, blank=True)

    server_response_time_ms = models.IntegerField(default=0, help_text="TTFB in milliseconds")
    server_type = models.CharField(max_length=100, blank=True)
    ssl_active = models.BooleanField(default=True)

    cv_opportunity = models.TextField(blank=True, help_text="Recommended Computer Vision use-case")

    # Outreach & Cold Pitch
    pitch_subject = models.CharField(max_length=255, blank=True)
    pitch_email = models.TextField(blank=True)
    lead_score = models.IntegerField(default=0, help_text="0-100 score based on missing services")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='NEW')
    notes = models.TextField(blank=True)

    search_batch = models.ForeignKey(
        LeadSearch, on_delete=models.SET_NULL, null=True, blank=True, related_name='leads'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-lead_score', '-created_at']

    def __str__(self):
        return f"{self.company_name} ({self.domain})"

    def calculate_score(self):
        """Calculates opportunity score for this lead based on gaps."""
        score = 20
        if self.audit_status == 'source_only' and not self.has_website:
            score += 15  # A listing omission is a tentative opportunity, not proof.
        if self.android_status == 'not_detected':
            score += 25
        if self.chatbot_status == 'not_detected':
            score += 20
        if self.audit_report.get('checks', {}).get('server', {}).get('status') == 'measured' and self.server_response_time_ms > 800:
            score += 15
        if self.audit_status in ('complete', 'partial') and self.cv_opportunity:
            score += 10  # Industry suggestion, not a verified technical gap.
        self.lead_score = min(score, 100)
        return self.lead_score
