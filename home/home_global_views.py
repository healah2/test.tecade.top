from django.shortcuts import render, redirect
from django.shortcuts import get_object_or_404
from django.shortcuts import render, redirect
from .models import AdminIndex, CarouselSlide, AdminAbout, AdminInstitutionalManagement, AdminAcDpt, AdminNonAcDpt, Trainee
# Create your views here.
from django.shortcuts import render
from .models import AdminIndex, CarouselSlide, AdminBom
from django.db.models import Count, Q
from django.http import JsonResponse
from django.db.models import Count
from .models import Trainee, Course
from collections import defaultdict
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import AdminCredentials
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from .models import Trainee, Department, Course
from django.http import JsonResponse
from datetime import datetime
from django.contrib import messages
import re
from django.utils import timezone
# views.py
from django.http import JsonResponse
from .models import Trainee, CurrentSession, TraineeSession, TrainerData

@ensure_csrf_cookie
def admin_login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        staff_number = request.POST.get('staff_number')
        user_type = request.POST.get('user_type', '').strip().lower()
        designation = request.POST.get('designation', '').strip()

        if user_type == 'sysadmin':
            designation = 'system admin'

        try:
            # Query database to find matching admin credentials with the selected designation
            if designation:
                admin = AdminCredentials.objects.get(
                    username=username,
                    staff_number=staff_number,
                    designation__iexact=designation
                )
            else:
                admin = AdminCredentials.objects.get(username=username, staff_number=staff_number)
                designation = admin.designation.strip()

            request.session['admin_id'] = admin.id
            request.session['admin_name'] = admin.name
            request.session['designation'] = designation.strip().lower()
            request.session['profile_image_url'] = (
                admin.profile_image.url if admin.profile_image else '/static/dist/img/user2-160x160.jpg'
            )
            request.session.save()

            normalized_designation = designation.strip().lower()
            if normalized_designation == 'registrar academics':
                return redirect('registrar_academics_dashboard')
            elif normalized_designation == 'hod':
                return redirect('hod_dashboard')
            elif normalized_designation == 'dp academics':
                return redirect('dp_academics_dashboard')
            elif normalized_designation == 'dp admin':
                return redirect('dp_admin_dashboard')
            elif normalized_designation == 'finance':
                return redirect('finance_dashboard')
            elif normalized_designation == 'system admin':
                return redirect('system_admin_dashboard')
            else:
                messages.error(request, 'Dashboard for this designation is not yet configured.')
        except AdminCredentials.DoesNotExist:
            messages.error(request, 'Invalid username, staff number, or designation.')

    return render(request, 'logins/login_page.html')
    
@ensure_csrf_cookie
def get_courses(request, dept_id):
    courses = Course.objects.filter(department_id=dept_id).values('id', 'name')
    return JsonResponse(list(courses), safe=False)



from django.views.decorators.http import require_GET

@require_GET
def get_trainee_info(request):
    trainee_number = request.GET.get('trainee_number', '').strip()

    if not trainee_number:
        return JsonResponse({'error': 'Trainee number is required.'})

    try:
        trainee = Trainee.objects.get(trainee_number=trainee_number)
    except Trainee.DoesNotExist:
        return JsonResponse({'error': 'Trainee not registered in current session.'})

    try:
        current_session = CurrentSession.objects.get(is_active=True)
    except CurrentSession.DoesNotExist:
        return JsonResponse({'error': 'No active session currently.'})

    # Check if trainee is enrolled in current session
    try:
        trainee_session = TraineeSession.objects.get(
            trainee=trainee,
            current_session=current_session
        )
        data = {
            'name': f"{trainee.first_name} {trainee.last_name}",
            'session': f"Year: {trainee_session.get_year_of_study_display()}, Term: {trainee_session.get_term_display()}",
            'balance': float(trainee_session.fee_balance)
        }
    except TraineeSession.DoesNotExist:
        data = {'error': 'Trainee is not enrolled in the current active session.'}

    return JsonResponse(data)

from django.shortcuts import redirect
from django.contrib import messages
from home.models import TrainerData, HOD

@ensure_csrf_cookie
def staff_login(request):
    if request.method == "POST":
        identifier = request.POST.get("staff_id_or_email")
        password = request.POST.get("password")

        # Try Trainer
        trainer = TrainerData.objects.filter(staff_number=identifier).first() or \
                  TrainerData.objects.filter(email=identifier).first()
        if trainer and trainer.staff_number == password:
            request.session.update({'staff_type': 'trainer', 'staff_id': trainer.id})
            return redirect(request, 'trainer/staff_dashboard.html')

        # Try HOD
        hod = HOD.objects.filter(staff_number=identifier).first() or \
              HOD.objects.filter(email=identifier).first()
        if hod and hod.id_number == password:
            request.session.update({'staff_type': 'hod', 'staff_id': hod.id})
            return redirect('hod_dashboard')

        messages.error(request, "Invalid credentials.")
    return redirect(request,'trainee/login.html')
