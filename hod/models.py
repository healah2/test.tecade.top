from django.db import models
from home.models import Course, TrainerData
from datetime import date
import re

class Units(models.Model):
    unit_competence = models.TextField()
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='hod_units')
    date_created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.unit_competence} ({self.course.name})"


class TrainerAssighnment(models.Model):
    trainer = models.ForeignKey(TrainerData, on_delete=models.CASCADE, related_name='unit_assignments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='trainer_unit_assignments')
    # Legacy manual units (kept for migration of existing assignments).
    units = models.ManyToManyField(Units, related_name='trainer_assignments')
    # New extracted units from curriculum PDFs.
    course_units = models.ManyToManyField('CourseUnitsData', related_name='trainer_assignments', blank=True)
    class_slot = models.ForeignKey('Classes', on_delete=models.CASCADE, related_name='trainer_assignments')
    date_assigned = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.trainer} - {self.course.name}"

    @property
    def assigned_units(self):
        """Units for this assignment (extracted curriculum units only)."""
        return self.course_units.all()


class TraineeClass(models.Model):
    trainee = models.ForeignKey('home.Trainee', on_delete=models.CASCADE, related_name='class_assignments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='trainee_class_assignments')
    class_slot = models.ForeignKey('Classes', on_delete=models.CASCADE, related_name='trainee_assignments')
    date_assigned = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_assigned']
        unique_together = ('trainee', 'class_slot')

    def __str__(self):
        return f"{self.trainee.first_name} {self.trainee.last_name} - {self.class_slot.slot}"

    @property
    def trainers(self):
        return TrainerAssighnment.objects.filter(
            course=self.course,
            class_slot=self.class_slot
        ).select_related('trainer', 'class_slot').prefetch_related('course_units')

    @property
    def trainer_units(self):
        return [
            {
                'trainer': assignment.trainer,
                'class_slot': assignment.class_slot,
                'units': list(assignment.course_units.all())
            }
            for assignment in self.trainers
        ]


class Classes(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='hod_classes')
    intake = models.DateField()
    slot = models.CharField(max_length=50, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)

    def _extract_course_abbrev(self):
        if not self.course or not self.course.name:
            return ""
        name = self.course.name or ""
        # Try to extract abbreviation from parentheses in course name
        # e.g., "L6 ICT Technician (ICT)" -> "ICT"
        match = re.search(r'\((.*?)\)', name)
        if match:
            return match.group(1).strip().upper()
        # If no parentheses, try to extract from course code
        code = self.course.code or ""
        return code.strip().upper()

    def _extract_level_code(self):
        if not self.course or not self.course.level:
            return ""
        match = re.search(r'(\d+)', self.course.level)
        if match:
            return f"L{match.group(1)}"
        if self.course.level.upper().startswith("L"):
            return self.course.level.strip().upper()
        return self.course.level.strip().upper()

    def _month_letter(self):
        if not self.intake:
            return ""
        return self.intake.strftime("%b")[0].upper()

    def save(self, *args, **kwargs):
        if self.course and self.intake:
            level_code = self._extract_level_code()
            abbrev = self._extract_course_abbrev()
            year_two = self.intake.strftime("%y")
            month_letter = self._month_letter()
            self.slot = f"{level_code}{abbrev}{year_two}{month_letter}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.course.name} - {self.intake.strftime('%Y %B')}"


class CourseCurriculum(models.Model):
    """
    Uploaded course curriculum document (usually a multi-page PDF containing all units).
    """
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='curricula')
    pdf_file = models.FileField(upload_to='curricula/')
    file_name = models.CharField(max_length=255, blank=True)
    date_uploaded = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_uploaded']

    def save(self, *args, **kwargs):
        if self.pdf_file and not self.file_name:
            self.file_name = self.pdf_file.name
        super().save(*args, **kwargs)

    def __str__(self):
        return f" {self.course.name}"


class CourseUnitsData(models.Model):
    """
    Extracted unit data from a course curriculum document.

    Note: Model name matches existing project naming in prompts ("CurricumData").
    """
    curriculum = models.ForeignKey(CourseCurriculum, on_delete=models.CASCADE, related_name='units')
    unit_index = models.PositiveIntegerField(default=0)

    isced_unit_code = models.CharField(max_length=64, blank=True, null=True)
    tvet_cdacc_unit_code = models.CharField(max_length=128, blank=True, null=True)
    total_time = models.PositiveIntegerField(blank=True, null=True)
    unit_of_competency = models.TextField(blank=True, null=True)

    date_extracted = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['unit_index', 'id']

    def __str__(self):
        return f"{self.curriculum.course.name} - {self.unit_of_competency}"

    @property
    def unit_competence(self):
        # Backwards-compatible alias for code expecting `Units.unit_competence`.
        return self.unit_of_competency


class CurriculumLearningOutcome(models.Model):
    """Learning outcomes extracted from Curriculum tables"""
    curriculum_data = models.ForeignKey(CourseUnitsData, on_delete=models.CASCADE, related_name='learning_outcomes')
    learning_outcome = models.TextField(blank=True, null=True)
    learning_expectations = models.TextField(blank=True, null=True)
    learning_assessments = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Outcome - {self.curriculum_data.isced_unit_code or 'Unit'}"
