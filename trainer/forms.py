from django import forms
from .models import OccupationalStandards
from hod.models import CourseUnitsData, CurriculumLearningOutcome


class OccupationalStandardsForm(forms.ModelForm):
    class Meta:
        model = OccupationalStandards
        fields = ['pdf_file']
        widgets = {
            'pdf_file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf',
                'required': True,
            })
        }
    
    def clean_pdf_file(self):
        pdf_file = self.cleaned_data.get('pdf_file')
        if pdf_file:
            # Check file size (max 10MB)
            if pdf_file.size > 10 * 1024 * 1024:
                raise forms.ValidationError("File size must not exceed 10MB.")
            
            # Check file type
            if not pdf_file.name.lower().endswith('.pdf'):
                raise forms.ValidationError("Only PDF files are allowed.")
        
        return pdf_file


class CourseUnitsDataForm(forms.ModelForm):
    class Meta:
        model = CourseUnitsData
        fields = ["isced_unit_code", "tvet_cdacc_unit_code", "total_time", "unit_of_competency"]
        widgets = {
            "isced_unit_code": forms.TextInput(attrs={"class": "form-control"}),
            "tvet_cdacc_unit_code": forms.TextInput(attrs={"class": "form-control"}),
            "total_time": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "unit_of_competency": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }


class CurriculumLearningOutcomeForm(forms.ModelForm):
    class Meta:
        model = CurriculumLearningOutcome
        fields = ["learning_outcome", "learning_expectations", "learning_assessments"]
        widgets = {
            "learning_outcome": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "learning_expectations": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "learning_assessments": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }
        