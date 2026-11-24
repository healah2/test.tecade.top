from django.contrib import admin
from .models import Units, TrainerAssighnment, Classes, CourseCurriculum, CourseUnitsData, CurriculumLearningOutcome, TraineeClass
from home.models import HOD

@admin.register(Units)
class UnitsAdmin(admin.ModelAdmin):
    list_display = ('unit_competence', 'course', 'date_created')
    search_fields = ('unit_competence', 'course__name')


@admin.register(TrainerAssighnment)
class TrainerAssighnmentAdmin(admin.ModelAdmin):
    list_display = ('trainer', 'course', 'date_assigned')
    search_fields = ('trainer__first_name', 'trainer__last_name', 'course__name')
    list_filter = ('course', 'date_assigned')


@admin.register(Classes)
class ClassesAdmin(admin.ModelAdmin):
    list_display = ('course', 'intake', 'slot', 'date_created')
    search_fields = ('course__name', 'slot')
    list_filter = ('course', 'intake')
    
    def get_deleted_objects(self, objs, request):
        """Override to allow deletion with related trainer assignments."""
        deleted_objects, model_count, perms_needed, protected = super().get_deleted_objects(objs, request)
        return deleted_objects, model_count, perms_needed, protected


@admin.register(CourseCurriculum)
class CourseCurriculumAdmin(admin.ModelAdmin):
    list_display = ('course', 'file_name', 'date_uploaded')
    search_fields = ('course__name', 'file_name')
    list_filter = ('course', 'date_uploaded')
    readonly_fields = ('date_uploaded',)


@admin.register(CourseUnitsData)
class CourseUnitsDataAdmin(admin.ModelAdmin):
    list_display = ('unit_of_competency', 'unit_index', 'isced_unit_code', 'date_extracted')
    search_fields = ('isced_unit_code', 'tvet_cdacc_unit_code', 'curriculum__course__name')
    list_filter = ('curriculum__course', 'date_extracted')
    readonly_fields = ('date_extracted',)


@admin.register(CurriculumLearningOutcome)
class CurriculumLearningOutcomeAdmin(admin.ModelAdmin):
    list_display = ('curriculum_data', 'learning_outcome')
    search_fields = ('curriculum_data__isced_unit_code', 'learning_outcome')
    list_filter = ('curriculum_data__curriculum__course',)
    readonly_fields = ('curriculum_data',)


@admin.register(TraineeClass)
class TraineeClassAdmin(admin.ModelAdmin):
    list_display = ('trainee', 'course', 'class_slot', 'date_assigned')
    search_fields = ('trainee__first_name', 'trainee__last_name', 'course__name', 'class_slot__slot')
    list_filter = ('course', 'date_assigned')


