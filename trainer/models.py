from django.db import models

from django.db import models
import json
from hod.models import TrainerAssighnment, CourseUnitsData, Units
from home.models import TrainerData
from django.conf import settings
from django.urls import reverse

class LearningGuide(models.Model):
    unit_code = models.CharField(max_length=50, null=True, blank=True)
    unit_competence = models.TextField(null=True, blank=True)
    trainer_name = models.CharField(max_length=100, null=True, blank=True)
    course = models.CharField(max_length=100, null=True, blank=True)
    institution = models.CharField(max_length=100, null=True, blank=True)

    date_preparation = models.DateField(null=True, blank=True)
    date_revision = models.DateField(null=True, blank=True)

    term = models.CharField(max_length=50, null=True, blank=True)
    trainees = models.CharField(max_length=200, null=True, blank=True)  # comma-separated list
    class_name = models.CharField(max_length=50, null=True, blank=True)
    total_time = models.IntegerField(null=True, blank=True)  # in hours

    # Stores sessions as JSON string
    sessions_json = models.TextField(null=True, blank=True)

    level = models.CharField(max_length=50, null=True, blank=True)  # trainee level or program level

    date_created = models.DateTimeField(null=True, blank=True,)

    def __str__(self):
        return f"{self.unit_code} - {self.trainer_name}"

    @property
    def sessions(self):
        """
        Returns the session list as Python objects.
        Handles both JSONField style & raw text JSON safely.
        """
        if not self.sessions_json:
            return []
        try:
            return json.loads(self.sessions_json)
        except:
            return []

class SavedSessionPlan(models.Model):
    unit = models.ForeignKey('LearningGuide', on_delete=models.CASCADE)

    # Core info
    session_title = models.CharField(max_length=255)
    duration = models.PositiveIntegerField(null=True, blank=True)  # in minutes
    presenter_name = models.CharField(max_length=255)
    date = models.DateField()

    # Form fields
    bridge_in = models.CharField(max_length=50, blank=True)
    pre_assessment = models.CharField(max_length=50, blank=True)
    post_assessment = models.CharField(max_length=50, blank=True)
    summary = models.CharField(max_length=255, blank=True)
    time = models.TextField(blank=True)  # stored as newline text

    # Auto-populated / dynamic fields
    expectation = models.TextField(blank=True)
    trainer_activities = models.TextField(blank=True)   # stored as newline text
    trainee_activities = models.TextField(blank=True)   # stored as newline text
    resources = models.TextField(blank=True)            # stored as newline text

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.session_title} - {self.unit.unit_competence}"
    

class OccupationalStandards(models.Model):
    """Model to store uploaded Occupational Standards PDFs for units"""
    trainer = models.ForeignKey(TrainerData, on_delete=models.CASCADE, related_name='occupational_standards')
    # Keep pointing at legacy Units until we finish migrating trainer assignments/units.
    unit = models.ForeignKey(Units, on_delete=models.CASCADE, related_name='os_documents')
    assignment = models.ForeignKey(TrainerAssighnment, on_delete=models.CASCADE, related_name='os_documents')
    
    pdf_file = models.FileField(upload_to='occupational_standards/')
    file_name = models.CharField(max_length=255, blank=True)
    
    # Extracted text from PDF (for later processing)
    extracted_text = models.TextField(blank=True, null=True)
    
    date_uploaded = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Occupational Standards"
        verbose_name_plural = "Occupational Standards"
        ordering = ['-date_uploaded']
    
    def save(self, *args, **kwargs):
        if self.pdf_file and not self.file_name:
            self.file_name = self.pdf_file.name
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"OS - {self.unit.unit_competence} ({self.trainer.first_name} {self.trainer.last_name})"


class OSData(models.Model):
    """Model to store extracted data from Occupational Standards PDFs"""
    occupational_standard = models.OneToOneField(OccupationalStandards, on_delete=models.CASCADE, related_name='os_data')
    
    # Structured fields extracted from the PDF
    unit_code = models.CharField(max_length=50, blank=True, null=True)
    unit_competence = models.TextField(blank=True, null=True)
    total_time = models.PositiveIntegerField(blank=True, null=True)
    
    date_extracted = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"OS Data - {self.occupational_standard.unit.unit_competence}"

class Attendance(models.Model):
    trainer = models.ForeignKey(TrainerData, on_delete=models.CASCADE, related_name='attendances')
    assignment = models.ForeignKey(TrainerAssighnment, on_delete=models.CASCADE, related_name='attendances')
    unit = models.ForeignKey(CourseUnitsData, on_delete=models.CASCADE, related_name='attendances')
    session_plan = models.ForeignKey('SavedSessionPlan', on_delete=models.CASCADE, related_name='attendances')

    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Active', 'Active'),
        ('Attended', 'Attended'),
        ('Unattended', 'Unattended'),
    ]
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='Pending')

    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField(blank=True, null=True)
    venue = models.CharField(max_length=255, blank=True)
    
    # Unique attendance link and QR code
    attendance_code = models.CharField(max_length=64, unique=True, blank=True, null=True, db_index=True)
    qr_code = models.ImageField(upload_to='attendance_qrcodes/', blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-start_time']

    def generate_attendance_code(self):
        import uuid
        if not self.attendance_code:
            self.attendance_code = str(uuid.uuid4())
            self.save()
        return self.attendance_code

    def get_attendance_link(self):
        if not self.attendance_code:
            self.generate_attendance_code()

        base_url = getattr(settings, 'SITE_URL', 'http://localhost:8000').rstrip('/')
        attendance_path = reverse('trainee:attendance_qr_confirm', args=[self.attendance_code])
        return f"{base_url}{attendance_path}"

    def generate_qr_code(self):
        if not self.attendance_code:
            self.generate_attendance_code()
        
        try:
            import qrcode
            from io import BytesIO
            from django.core.files.base import ContentFile

            attendance_payload = self.get_attendance_link()
            
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(attendance_payload)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Save to model
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            
            filename = f"attendance_{self.attendance_code}.png"
            self.qr_code.save(filename, ContentFile(buffer.getvalue()), save=True)
        except Exception as e:
            print(f"Error generating QR code: {e}")

    def get_current_status(self):
        from datetime import datetime as dt
        from django.utils import timezone

        now = timezone.localtime()
        tz = timezone.get_current_timezone()

        if not self.date or not self.start_time:
            return self.status or 'Pending'

        start_dt = dt.combine(self.date, self.start_time)
        if timezone.is_naive(start_dt):
            start_dt = timezone.make_aware(start_dt, tz)

        if now < start_dt:
            return 'Pending'

        if self.end_time:
            end_dt = dt.combine(self.date, self.end_time)
            if timezone.is_naive(end_dt):
                end_dt = timezone.make_aware(end_dt, tz)

            if now >= end_dt:
                return 'Attended' if self.status == 'Attended' else 'Unattended'

        return 'Attended' if self.status == 'Attended' else 'Active'

    def __str__(self):
        session_title = self.session_plan.session_title if self.session_plan else 'Session'
        return f"{self.trainer} - {session_title} ({self.date})"
