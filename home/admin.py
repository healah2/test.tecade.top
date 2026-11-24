from django.contrib import admin
from .models import( AdminIndex, CarouselSlide, AdminAbout, AdminInstitutionalManagement, AdminBom, AdminAcDpt,AdminNonAcDpt, Department, Course, Trainee, AdminCredentials, TraineeSession, Timetable, Session, TrainerOtherDocument, Unit, Notice, Conversation, Message, MessageReaction, UserStatus,
    LovedBook, Assignment, Submission, AttendanceRegister, Attendance,
    ExcuseRequest, Trainer, CompetencyCategory, Competency,
    EvidenceArtifact, Assessment, Reflection, PortfolioShare, PortfolioView,
)  
from .models import HOD,MainPage

@admin.register(MainPage)
class MainPageAdmin(admin.ModelAdmin):
    list_display = ('site_title', 'footer_about_title', 'footer_location', 'footer_email', 'footer_phone')
    search_fields = ('site_title', 'footer_about_title', 'footer_location', 'footer_email', 'footer_phone')

class CarouselSlideInline(admin.TabularInline):
    model = CarouselSlide
    extra = 1
    fields = ('image', 'heading', 'subheading', 'order')
    can_delete = True
    ordering = ['order']

@admin.register(AdminIndex)
class AdminIndexAdmin(admin.ModelAdmin):
    list_display = ('num_institutions', 'num_trainees', 'num_trainers', 'updated_at')
    inlines = [CarouselSlideInline]

@admin.register(CarouselSlide)
class CarouselSlideAdmin(admin.ModelAdmin):
    list_display = ('admin_index', 'heading', 'subheading', 'order')
    search_fields = ['heading', 'subheading']
    ordering = ['order']


@admin.register(AdminAbout)
class AdminAboutAdmin(admin.ModelAdmin):
    list_display = ['title', 'phone']

@admin.register(AdminInstitutionalManagement)
class AdminAdminInstitutionalManagement(admin.ModelAdmin):
    list_display = ['title', 'name']

@admin.register(AdminBom)
class AdminBomAdmin(admin.ModelAdmin):
    list_display = ['title', 'name']

@admin.register(AdminAcDpt)
class AdminAcDptAdmin(admin.ModelAdmin):
    list_display = ['name']

@admin.register(AdminNonAcDpt)
class AdminNonAcDptAdmin(admin.ModelAdmin):
    list_display = ['name']

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('name', 'department', 'level', 'date_registered', 'term1_fees', 'term2_fees', 'term3_fees', 'total_fees')
    list_filter = ('department',)

@admin.register(Trainee)
class TraineeAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'trainee_number', 'course', 'date_of_admission')
    search_fields = ('first_name', 'last_name', 'trainee_number', 'course__name')
    list_filter = ( 'course', 'department')
    readonly_fields = ('trainee_number',)

@admin.register(AdminCredentials)
class AdminCredentialsAdmin(admin.ModelAdmin):
    list_display = ('username', 'name', 'designation', 'staff_number')
    search_fields = ('username', 'name', 'staff_number')

@admin.register(TraineeSession)
class TraineeSessionAdmin(admin.ModelAdmin):
    list_display = ('trainee', 'year_of_study', 'term', 'fee_balance', 'session_period', 'date_registered')
    list_filter = ('year_of_study', 'term', 'date_registered', )
    search_fields = ('trainee__trainee_number', 'trainee__name')


from .models import CurrentSession, TrainerData

@admin.register(CurrentSession)
class CurrentSessionAdmin(admin.ModelAdmin):
    list_display = ('start_date', 'end_date', 'is_active', 'session_period')
    list_filter = ('is_active', 'start_date', 'end_date', 'session_period')
    search_fields = ('is_active',)


@admin.register(Timetable)
class TimetableAdmin(admin.ModelAdmin):
    list_display = ('name', 'course', 'level', 'start_date', 'end_date')
    list_filter = ('course', 'level')
    search_fields = ('name', 'course__name')
    date_hierarchy = 'start_date'
    ordering = ('-start_date',)
    filter_horizontal = ()
    

@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('title', 'timetable', 'session_type', 'start_time', 'location')
    list_filter = ('timetable', 'session_type', 'start_time')
    search_fields = ('title', 'timetable__name', 'location')
    date_hierarchy = 'start_time'
    ordering = ('-start_time',)    
    
@admin.register(TrainerData)
class TrainerDataAdmin(admin.ModelAdmin):    
    list_display = ('first_name', 'last_name',  'department')
    search_fields = ('first_name', 'last_name', 'department__name')
    list_filter = ('department',)

@admin.register(TrainerOtherDocument)
class TrainerOtherDocumentAdmin(admin.ModelAdmin):
    list_display = ('trainer', 'document')
    search_fields = ('trainer', 'document')
    list_filter = ('trainer', 'document')

from django.contrib import admin
from .models import HOD

@admin.register(HOD)
class HODAdmin(admin.ModelAdmin):
    list_display = (
        'first_name',
        'middle_name',
        'last_name',
        'phone',
        'id_number',
        'email',
        'staff_number',
        'department',
    )

    search_fields = (
        'first_name',
        'middle_name',
        'last_name',
        'email',
        'staff_number',
        'id_number',
    )

    list_filter = ('department',)


from django.contrib import admin
from .models import CourseApplication


@admin.register(CourseApplication)
class CourseApplicationAdmin(admin.ModelAdmin):
    # ===== LIST VIEW =====
    list_display = (
        "application_reference",
        "full_name",
        "department_name",
        "course",
        "status",
        "submitted_date",
    )
    list_filter = (
        "status",
        "department_name",
        "course_type",
        "intake_period",
        "submitted_date",
    )
    search_fields = (
        "application_reference",
        "full_name",
        "email",
        "phone",
        "kcse_index",
        "department_name",
        "course",
    )
    ordering = ("-submitted_date",)
    list_per_page = 25

    # ===== READONLY FIELDS =====
    readonly_fields = (
        "application_reference",
        "submitted_date",
        "updated_date",
    )

    # ===== FORM LAYOUT =====
    fieldsets = (
        ("Department Information", {
            "fields": (
                "department_id",
                "department_name",
            )
        }),

        ("Personal Information", {
            "fields": (
                "full_name",
                "id_type",
                "id_number",
                "date_of_birth",
                "gender",
                "marital_status",
                "address",
                "phone",
                "email",
                "county",
            )
        }),

        ("KCPE Information", {
            "classes": ("collapse",),
            "fields": (
                "kcpe_index",
                "kcpe_marks",
                "kcpe_mean_grade",
                "kcpe_year",
                "kcpe_school",
            )
        }),

        ("KCSE Information", {
            "fields": (
                "kcse_index",
                "kcse_mean_grade",
                "kcse_year",
                "kcse_school",
            )
        }),

        ("Qualifications & Experience", {
            "classes": ("collapse",),
            "fields": (
                "qualifications",
                "work_experience",
            )
        }),

        ("Course Selection", {
            "fields": (
                "intake_period",
                "course_type",
                "course",
                "sponsorship",
                "reason_application",
            )
        }),

        ("Additional Information", {
            "classes": ("collapse",),
            "fields": (
                "employment_status",
                "disability",
                "disability_description",
                "referral_source",
            )
        }),

        ("Next of Kin", {
            "fields": (
                "next_of_kin_name",
                "next_of_kin_phone",
                "next_of_kin_relation",
            )
        }),

        ("Uploaded Documents", {
            "classes": ("collapse",),
            "fields": (
                "id_document",
                "kcse_certificate",
            )
        }),

        ("Application Status", {
            "fields": (
                "application_reference",
                "status",
                "submitted_date",
                "updated_date",
            )
        }),
    )

    # ===== QUICK ACTIONS =====
    actions = ["mark_as_reviewing", "mark_as_approved", "mark_as_rejected"]

    def mark_as_reviewing(self, request, queryset):
        queryset.update(status="reviewing")
        self.message_user(request, "Selected applications marked as UNDER REVIEW.")

    def mark_as_approved(self, request, queryset):
        queryset.update(status="approved")
        self.message_user(request, "Selected applications APPROVED.")

    def mark_as_rejected(self, request, queryset):
        queryset.update(status="rejected")
        self.message_user(request, "Selected applications REJECTED.")

    mark_as_reviewing.short_description = "Mark selected as Under Review"
    mark_as_approved.short_description = "Approve selected applications"
    mark_as_rejected.short_description = "Reject selected applications"

@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'course', 'term', 'trainer', 'hours')
    list_filter = ('term', 'course')
    search_fields = ('name', 'code')

@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display = ('title', 'created_at')
    search_fields = ('title',)

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'updated_at')
    filter_horizontal = ('participants',)

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'conversation', 'timestamp', 'is_read')
    list_filter = ('is_read',)
    search_fields = ('sender__username', 'content')

@admin.register(MessageReaction)
class MessageReactionAdmin(admin.ModelAdmin):
    list_display = ('message', 'user', 'emoji', 'created_at')

@admin.register(UserStatus)
class UserStatusAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_online', 'last_seen')
    list_filter = ('is_online',)

@admin.register(LovedBook)
class LovedBookAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'author', 'department', 'created_at')
    search_fields = ('title', 'author')
    list_filter = ('department',)

@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'instructor_name', 'due_date', 'max_points', 'created_at')
    list_filter = ('course',)
    search_fields = ('title', 'instructor_name')

@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ('assignment', 'trainee', 'status', 'grade', 'submitted_at')
    list_filter = ('status',)
    search_fields = ('trainee__first_name', 'trainee__last_name', 'assignment__title')

@admin.register(AttendanceRegister)
class AttendanceRegisterAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'department', 'date', 'trainer_name')
    list_filter = ('course', 'department', 'date')
    search_fields = ('trainer_name',)

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('trainee', 'register', 'status', 'checked')
    list_filter = ('status',)
    search_fields = ('trainee__first_name', 'trainee__last_name')

@admin.register(ExcuseRequest)
class ExcuseRequestAdmin(admin.ModelAdmin):
    list_display = ('trainee', 'date', 'session', 'status', 'created_at')
    list_filter = ('status', 'session')
    search_fields = ('trainee__first_name', 'trainee__last_name')

@admin.register(Trainer)
class TrainerAdmin(admin.ModelAdmin):
    list_display = ('user',)
    filter_horizontal = ('courses',)
    search_fields = ('user__username', 'user__first_name', 'user__last_name')

@admin.register(CompetencyCategory)
class CompetencyCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'order')
    ordering = ('order',)

@admin.register(Competency)
class CompetencyAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'order')
    list_filter = ('category',)
    search_fields = ('name',)

@admin.register(EvidenceArtifact)
class EvidenceArtifactAdmin(admin.ModelAdmin):
    list_display = ('title', 'trainee', 'evidence_type', 'assessment_stage', 'upload_date')
    list_filter = ('evidence_type', 'assessment_stage', 'assessment_type')
    search_fields = ('title', 'trainee__username')
    filter_horizontal = ('competencies',)

@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ('evidence', 'assessor', 'status', 'score', 'max_score', 'assessment_date')
    list_filter = ('status',)
    search_fields = ('evidence__title', 'assessor__username')

@admin.register(Reflection)
class ReflectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'trainee', 'assessment_type', 'term', 'date')
    list_filter = ('assessment_type', 'term')
    search_fields = ('title', 'trainee__username')

@admin.register(PortfolioShare)
class PortfolioShareAdmin(admin.ModelAdmin):
    list_display = ('trainee', 'scope', 'is_active', 'created_at', 'expires_at')
    list_filter = ('is_active', 'scope')

@admin.register(PortfolioView)
class PortfolioViewAdmin(admin.ModelAdmin):
    list_display = ('share', 'viewed_by', 'viewed_at')
    search_fields = ('viewed_by',)