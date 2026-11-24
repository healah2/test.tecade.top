# forms.py

from django import forms
from .models import Department, BlogPost

# class DepartmentForm(forms.ModelForm):
#     class Meta:
#         model = Department
#         fields = ['title', 'description', 'image']


class BlogPostForm(forms.ModelForm):
    class Meta:
        model = BlogPost
        fields = ['name', 'email', 'title', 'content', 'uploaded_image']
        widgets = {
            'content': forms.Textarea(attrs={'class': 'ckeditor'}),
        }