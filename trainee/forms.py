# forms.py
from django import forms
from django.db.models import Q
from home.models import Notice, Timetable, Session, EvidenceArtifact, Reflection, Unit, Course


class NoticeForm(forms.ModelForm):
    class Meta:
        model = Notice
        fields = ['title', 'description', 'memo_image']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
        }

class TimetableForm(forms.ModelForm):
    class Meta:
        model = Timetable
        fields = ['name', 'course', 'level', 'start_date', 'end_date']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

class SessionForm(forms.ModelForm):
    class Meta:
        model = Session
        fields = ['session_type', 'course', 'title', 'location', 'trainer', 
                  'start_time', 'end_time', 'requirements', 'notes']
        widgets = {
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }  

class EvidenceArtifactForm(forms.ModelForm):
    class Meta:
        model = EvidenceArtifact
        fields = [
            'unit',
            'assessment_stage',
            'assessment_type',
            'date_of_assessment',
            'title',
            'description',
            'evidence_type',
            'file',
            'external_url',
            'competencies',
            'self_rating',
            'tags',
        ]
        widgets = {
            'unit': forms.Select(attrs={
                'class': 'form-control',
            }),
            'assessment_stage': forms.Select(attrs={
                'class': 'form-control',
            }),
            'assessment_type': forms.Select(attrs={
                'class': 'form-control',
            }),
            'date_of_assessment': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Networking Practical Report',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Briefly describe what this evidence shows...',
            }),
            'evidence_type': forms.Select(attrs={
                'class': 'form-control',
            }),
            'file': forms.FileInput(attrs={
                'class': 'form-control',
            }),
            'external_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://...',
            }),
            'competencies': forms.CheckboxSelectMultiple(),
            'self_rating': forms.Select(attrs={
                'class': 'form-control',
            }),
            'tags': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. networking, cisco, practical',
            }),
        }

    def __init__(self, *args, trainee=None, **kwargs):
        super().__init__(*args, **kwargs)

        # scope unit dropdown to course units extracted in HOD (`CourseUnitsData`) when available
        if trainee and hasattr(trainee, 'course') and trainee.course:
            # default fallback
            unit_queryset = Unit.objects.filter(course=trainee.course).order_by('term', 'name')
            try:
                from hod.models import CourseUnitsData

                cu_qs = CourseUnitsData.objects.filter(curriculum__course=trainee.course)
                if cu_qs.exists():
                    # collect unit names from extracted curriculum data
                    names = [
                        (cu.unit_of_competency or getattr(cu, 'unit_competence', '')).strip()
                        for cu in cu_qs
                        if (cu.unit_of_competency or getattr(cu, 'unit_competence', ''))
                    ]

                    if names:
                        # try exact match on name or code first
                        exact_units = Unit.objects.filter(course=trainee.course).filter(
                            Q(name__in=names) | Q(code__in=names)
                        )
                        if exact_units.exists():
                            unit_queryset = exact_units.order_by('term', 'name')
                        else:
                            # fallback to fuzzy contains matching
                            fuzzy_q = Q()
                            for n in names:
                                fuzzy_q |= Q(name__icontains=n) | Q(code__icontains=n)
                            fuzzy_units = Unit.objects.filter(course=trainee.course).filter(fuzzy_q)
                            if fuzzy_units.exists():
                                unit_queryset = fuzzy_units.order_by('term', 'name')
                # else keep default
            except Exception:
                # if hod app not present or any error, keep default course units
                pass

            self.fields['unit'].queryset = unit_queryset
        else:
            self.fields['unit'].queryset = Unit.objects.all().order_by(
                'course', 'term', 'name'
            )
        # make these fields required
        self.fields['unit'].required = True
        self.fields['assessment_stage'].required = True
        self.fields['assessment_type'].required = True
        self.fields['date_of_assessment'].required = True
        self.fields['title'].required = True
        self.fields['evidence_type'].required = True
        self.fields['self_rating'].required = True

        # make these optional
        self.fields['file'].required = False
        self.fields['external_url'].required = False
        self.fields['competencies'].required = False
        self.fields['tags'].required = False
        self.fields['description'].required = False

        # friendly empty labels
        self.fields['unit'].empty_label = '-- Select unit --'
        self.fields['assessment_stage'].empty_label = '-- Select stage --'
        self.fields['assessment_type'].empty_label = '-- Select type --'
        self.fields['self_rating'].empty_label = '-- Rate yourself --'


class ReflectionForm(forms.ModelForm):
    class Meta:
        model = Reflection
        fields = [
            'title',
            'unit_name',
            'unit_code',
            'term',
            'assessment_type',
            'content',
            'related_evidence',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Reflection on Suspension Practical',
            }),
            'unit_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Numerical skills',
            }),
            'unit_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g.AGR204',
            }),
            'term': forms.Select(attrs={
                'class': 'form-control',
            }),
            'assessment_type': forms.Select(attrs={
                'class': 'form-control',
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': 'What did you do? What did you learn? What would you do differently?',
            }),
            'related_evidence': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, trainee_user=None, **kwargs):
        super().__init__(*args, **kwargs)

        # scope related evidence to only this trainee's uploads
        if trainee_user:
            self.fields['related_evidence'].queryset = EvidenceArtifact.objects.filter(
                trainee=trainee_user
            ).order_by('-upload_date')
        else:
            self.fields['related_evidence'].queryset = EvidenceArtifact.objects.none()

        self.fields['related_evidence'].required = False
        self.fields['term'].required = False
        self.fields['unit_code'].required = False             