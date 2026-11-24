from django.urls import path
from . import views

urlpatterns = [
    path('', views.hod_dashboard, name='hod_dashboard'),
    # path('dashboard/', views.hod_dashboard, name='hod_dashboard'),
    path('upload_curriculum/', views.upload_course_curriculum, name='upload_course_curriculum'),
    path('all_courses/', views.hod_all_courses, name='hod_all_courses'),
    path('all_trainers/', views.hod_all_trainers, name='hod_all_trainers'),
    path('add_unit/', views.hod_add_unit, name='hod_add_unit'),
    path('courses/<int:course_id>/units/', views.hod_course_units, name='hod_course_units'),
    path('assign_trainer/', views.hod_assign_trainer, name='hod_assign_trainer'),
    path('assign_trainee_class/', views.hod_assign_trainee_class, name='hod_assign_trainee_class'),
    path('api/trainee/<int:trainee_id>/course/', views.hod_trainee_course_api, name='hod_trainee_course_api'),
    path('api/trainer/<int:trainer_id>/course-units/', views.hod_trainer_course_units_api, name='hod_trainer_course_units_api'),
    path('api/trainer-course/<int:course_id>/units/', views.hod_course_units_api, name='hod_course_units_api'),
    path('add_class/', views.hod_add_class, name='hod_add_class'),
    path('classes/', views.hod_classes_list, name='hod_classes_list'),
    path('api/course/<int:course_id>/classes/', views.hod_course_classes_api, name='hod_course_classes_api'),
]
