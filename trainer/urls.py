# trainer/urls.py
from django.urls import path
from . import views

# app_name = 'trainer'

urlpatterns = [
    path("generate_learning_plan/", views.generate_learning_plan, name="generate_learning_plan"),
    path("learning_guides_list/", views.learning_guides_list, name="learning_guides_list"),
    path("view_learning_guide/<int:pk>/", views.view_learning_guide, name="view_learning_guide"),
    path('session_plan/<int:session_no>/', views.session_plan, name='session_plan'),
    path('generate_session_plan/', views.generate_session_plan, name='generate_session_plan'),
    path('session_plans_list/', views.session_plans_list, name='session_plans_list'),
    path('view_session_plan/<int:plan_id>/', views.view_session_plan, name='view_session_plan'),
    path("sp/", views.sp, name='sp' ),
    path('all_courses/', views.trainer_all_courses, name='trainer_all_courses'),
    path("api/unit/<int:unit_id>/outcomes/", views.trainer_os_outcomes_api, name="trainer_os_outcomes_api"),
    path('my_classes/', views.trainer_my_classes, name='trainer_my_classes'),
    path('course_units/<int:assignment_id>/', views.trainer_course_units, name='trainer_course_units'),
    path('course_units/<int:assignment_id>/curriculum/<int:unit_id>/', views.trainer_view_curriculum, name='trainer_view_curriculum'),
    path('course_units/<int:assignment_id>/curriculum/<int:unit_id>/edit/', views.trainer_edit_curriculum, name='trainer_edit_curriculum'),
    path('api/upload-os/', views.api_upload_occupational_standards, name='api_upload_occupational_standards'),

    # other added trainee registration session and other urls

    path('portfolio/', views.trainer_portfolio_overview, name='trainer_portfolio_overview'),
    path('portfolio/review/<int:trainee_user_id>/', views.trainer_review_trainee, name='trainer_review_trainee'),
    path('portfolio/history/', views.trainer_assessment_history, name='trainer_assessment_history'),
    # path('portfolio-overview/', views.trainer_portfolio_overview, name='trainer_portfolio_overview'),
    path('attendance/create/', views.create_attendance, name='create_attendance'),
    path('attendance/', views.attendance_list, name='attendance_list'),
    path('attendance/<int:attendance_id>/qrcode/', views.attendance_qrcode, name='attendance_qrcode'),
    
]   
