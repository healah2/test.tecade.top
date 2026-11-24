from django.shortcuts import render, redirect
from django.shortcuts import get_object_or_404
from django.shortcuts import render, redirect
from .models import AdminIndex, CarouselSlide, AdminAbout, AdminInstitutionalManagement, AdminAcDpt, AdminNonAcDpt, Trainee, CourseApplication
# Create your views here.
from django.shortcuts import render
from .models import AdminIndex, CarouselSlide, AdminBom
from django.db.models import Count, Q
from django.http import JsonResponse
from django.db.models import Count
from .models import Trainee, Course, TraineeSession
from collections import defaultdict
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import AdminCredentials
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_protect
from .models import Trainee, Department, Course
from django.http import JsonResponse
from datetime import datetime
from django.contrib import messages
import re, uuid
from django.utils import timezone
from . import home_global_views
from django.urls import reverse
from django.shortcuts import render
from django.core.exceptions import ValidationError
from .models import Trainee, TraineeSession, CurrentSession, MainPage
from finance.models import FeeStatement 

def home(request):
    # Fetch the single AdminIndex instance (assuming only one is used)
    admin_data = AdminIndex.objects.first()

    # Get the carousel slides associated with that AdminIndex
    slides = CarouselSlide.objects.filter(admin_index=admin_data).order_by('order')

    team_members = AdminInstitutionalManagement.objects.all()

    # Prepare fact items for looping in the template
    fact_items = []
    if admin_data:
        fact_items = [
            {
                'title': 'Partner Institutions',
                'count': admin_data.num_institutions,
                'icon_class': 'fa fa-university',
                'bg_color': 'bg-primary'
            },
            {
                'title': 'Trainees Managed',
                'count': admin_data.num_trainees,
                'icon_class': 'fa fa-user-graduate',
                'bg_color': 'bg-light'
            },
            {
                'title': 'Trainers Engaged',
                'count': admin_data.num_trainers,
                'icon_class': 'fa fa-chalkboard-teacher',
                'bg_color': 'bg-primary'
            }
        ]

    

    return render(request, 'clientside/index.html', {
        'slides': slides,
        'fact_items': fact_items
        ,'team_members': team_members
    })


def about(request):

    return render(request, 'clientside/about.html')

def contact(request):
    return render(request, 'clientside/contact.html')

# sarts here
def system_admin_dashboard(request):
    designation = request.session.get('designation', '').strip().lower()
    if designation != 'system admin':
        return redirect('admin_login')

    context = {
        'courses_count': Course.objects.count(),
        'depts_count': Department.objects.count(),
        'trainers_count': TrainerData.objects.count(),
        'admins_count': AdminCredentials.objects.count(),
        'apps_count': CourseApplication.objects.count(),
    }
    return render(request, 'adminpages/system_admin_dashboard.html', context)

def system_admin_dashboard(request):
    designation = request.session.get('designation', '').strip().lower()
    if designation != 'system admin':
        return redirect('admin_login')

    from .models import Course, Department, TrainerData, AdminCredentials, CourseApplication
    context = {
        'courses_count': Course.objects.count(),
        'depts_count': Department.objects.count(),
        'trainers_count': TrainerData.objects.count(),
        'admins_count': AdminCredentials.objects.count(),
        'apps_count': CourseApplication.objects.count(),
    }
    return render(request, 'adminpages/system_admin_dashboard.html', context)


def system_admin_credentials(request):
    """
    Unified credential manager for System Admin.
    Handles: AdminCredentials (management staff) + TrainerData + HOD accounts.
    """
    designation = request.session.get('designation', '').strip().lower()
    if designation != 'system admin':
        return redirect('admin_login')

    # ── Handle POST actions ──
    if request.method == 'POST':
        action = request.POST.get('action')

        # ── CREATE Admin Credential ──
        if action == 'create_admin':
            username   = request.POST.get('username', '').strip()
            name       = request.POST.get('name', '').strip()
            desig      = request.POST.get('designation', '').strip()
            staff_num  = request.POST.get('staff_number', '').strip()

            if username and name and desig and staff_num:
                if AdminCredentials.objects.filter(username=username).exists():
                    messages.error(request, f"Username '{username}' already exists.")
                elif AdminCredentials.objects.filter(staff_number=staff_num).exists():
                    messages.error(request, f"Staff number '{staff_num}' already exists.")
                else:
                    AdminCredentials.objects.create(
                        username=username,
                        name=name,
                        designation=desig,
                        staff_number=staff_num,
                    )
                    messages.success(request, f"Admin account for '{name}' created. Password = staff number.")
            else:
                messages.error(request, "All fields are required to create an admin account.")
            return redirect('system_admin_credentials')

        # ── EDIT Admin Credential ──
        elif action == 'edit_admin':
            cred_id   = request.POST.get('cred_id')
            cred      = get_object_or_404(AdminCredentials, id=cred_id)
            new_sn    = request.POST.get('staff_number', '').strip()

            cred.name        = request.POST.get('name', cred.name).strip()
            cred.designation = request.POST.get('designation', cred.designation).strip()

            # Only update staff_number if changed & unique
            if new_sn and new_sn != cred.staff_number:
                if AdminCredentials.objects.filter(staff_number=new_sn).exclude(id=cred.id).exists():
                    messages.error(request, f"Staff number '{new_sn}' is already in use.")
                    return redirect('system_admin_credentials')
                cred.staff_number = new_sn

            cred.save()
            messages.success(request, f"Account for '{cred.name}' updated.")
            return redirect('system_admin_credentials')

        # ── DELETE Admin Credential ──
        elif action == 'delete_admin':
            cred_id = request.POST.get('cred_id')
            cred    = get_object_or_404(AdminCredentials, id=cred_id)
            name    = cred.name
            cred.delete()
            messages.success(request, f"Admin account for '{name}' deleted.")
            return redirect('system_admin_credentials')

        # ── RESET Admin Password (set staff_number back as password) ──
        elif action == 'reset_admin_password':
            cred_id  = request.POST.get('cred_id')
            new_pass = request.POST.get('new_password', '').strip()
            cred     = get_object_or_404(AdminCredentials, id=cred_id)

            if new_pass:
                cred.staff_number = new_pass
                cred.save()
                messages.success(request, f"Password reset for '{cred.name}'. New password = '{new_pass}'.")
            else:
                messages.error(request, "New password cannot be empty.")
            return redirect('system_admin_credentials')

        # ── RESET Trainer Password ──
        elif action == 'reset_trainer_password':
            trainer_id = request.POST.get('trainer_id')
            new_pass   = request.POST.get('new_password', '').strip()
            trainer    = get_object_or_404(TrainerData, id=trainer_id)

            if new_pass:
                trainer.staff_number = new_pass
                trainer.save()
                messages.success(request, f"Password reset for trainer '{trainer.first_name} {trainer.last_name}'.")
            else:
                messages.error(request, "New password cannot be empty.")
            return redirect('system_admin_credentials')

        # ── RESET HOD Password ──
        elif action == 'reset_hod_password':
            hod_id   = request.POST.get('hod_id')
            new_pass = request.POST.get('new_password', '').strip()
            hod      = get_object_or_404(HOD, id=hod_id)

            if new_pass:
                hod.staff_number = new_pass
                hod.save()
                messages.success(request, f"Password reset for HOD '{hod.first_name} {hod.last_name}'.")
            else:
                messages.error(request, "New password cannot be empty.")
            return redirect('system_admin_credentials')

        # ── TOGGLE Trainer active status (future-proof placeholder) ──
        elif action == 'delete_trainer':
            trainer_id = request.POST.get('trainer_id')
            trainer    = get_object_or_404(TrainerData, id=trainer_id)
            name       = f"{trainer.first_name} {trainer.last_name}"
            trainer.delete()
            messages.success(request, f"Trainer account for '{name}' deleted.")
            return redirect('system_admin_credentials')

        elif action == 'delete_hod':
            hod_id = request.POST.get('hod_id')
            hod    = get_object_or_404(HOD, id=hod_id)
            name   = f"{hod.first_name} {hod.last_name}"
            hod.delete()
            messages.success(request, f"HOD account for '{name}' deleted.")
            return redirect('system_admin_credentials')

    # ── GET: load all accounts ──
    admin_credentials = AdminCredentials.objects.all().order_by('designation', 'name')
    trainers          = TrainerData.objects.select_related('department').order_by('department', 'last_name')
    hods              = HOD.objects.select_related('department').order_by('department', 'last_name')

    DESIGNATION_CHOICES = [
        'Registrar Academics',
        'DP Academics',
        'DP Admin',
        'Finance',
        'System Admin',
    ]

    context = {
        'admin_credentials'  : admin_credentials,
        'trainers'           : trainers,
        'hods'               : hods,
        'designation_choices': DESIGNATION_CHOICES,
        'total_admins'       : admin_credentials.count(),
        'total_trainers'     : trainers.count(),
        'total_hods'         : hods.count(),
    }
    return render(request, 'adminpages/system_admin_credentials.html', context)
# system admin credentials ends here

def trainee_dashboard(request):
    return render(request, 'trainee/trainee_dashboard.html')

# def staff_dashboard(request):
#     return render(request, 'staff/staff_dashboard.html')

def mailbox(request):
    return render(request, 'mailbox.html')

def simple_tables(request):
    return render(request, 'simple_tables.html')

def data_tables(request):
    return render(request, 'data_tables.html')

# def login(request):
#     if request.method == 'POST':
#         user_type = request.POST.get('user_type')  # 'trainee' or 'staff'

#         # You can also fetch and process credentials here
#         email_or_id = request.POST.get('email') or request.POST.get('staff_id')
#         password = request.POST.get('password')

#         # redirecting based on form type
#         if user_type == 'trainee':
#             return redirect('trainee_dashboard')
#         elif user_type == 'staff':
#             return redirect('staff_dashboard')

#     return render(request, 'logins/login.html')
def login_page(request):
    return render(request, 'logins/login_page.html')



def academic_departments(request):
    departments = AdminAcDpt.objects.all()
    return render(request, 'clientside/academic_departments.html', {'departments': departments})

def non_academic(request):
    departments = AdminNonAcDpt.objects.all()
    return render(request, 'clientside/non_academic.html', {'departments': departments})

def academic_dpt_details(request, pk):
    dept = get_object_or_404(AdminAcDpt, pk=pk)
    return render(request, 'clientside/academic_dpt_details.html', {'dept': dept})

def non_academic_details(request, pk):
    dept = get_object_or_404(AdminNonAcDpt, pk=pk)
    return render(request, 'clientside/non_academic_details.html', {'dept': dept})

def academic_courses(request):
    return render(request, 'clientside/academic_courses.html')

def bom(request):
    bom_members = AdminBom.objects.all()
    return render(request, 'clientside/bom.html', {'bom_members': bom_members})

def institutional(request):
    team_members = AdminInstitutionalManagement.objects.all()
    return render(request, 'clientside/institutional.html', {'team_members': team_members})

def apply_levels(request):
    return render(request, 'clientside/apply_levels.html')

def apply_departments(request):
    departments = AdminAcDpt.objects.all()
    return render(request, 'clientside/apply_departments.html', {'departments': departments})

# def apply_courses(request, pk):
#     dept = get_object_or_404(AdminAcDpt, pk=pk)  # or AdminAcDpt
#     return render(request, 'clientside/apply_courses.html', {'dept': dept})


def apply_courses(request, pk):
    dept = get_object_or_404(AdminAcDpt, pk=pk)
    
    if request.method == 'POST':
        # ============================================
        # HANDLE FORM SUBMISSION (POST Request)
        # ============================================
        
        try:
            # Generate unique application reference
            app_reference = f"APP-{timezone.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
            
            # Get qualifications as comma-separated string
            qualifications = request.POST.getlist('qualifications')
            qualifications_str = ','.join(qualifications) if qualifications else ''
            
            # Create CourseApplication record
            application = CourseApplication.objects.create(
                # Department Info
                department_id=request.POST.get('dept_id'),
                department_name=request.POST.get('dept_name'),
                
                # Section 1: Personal Information
                full_name=request.POST.get('fullName'),
                id_type=request.POST.get('idType'),
                id_number=request.POST.get('idNumber'),
                date_of_birth=request.POST.get('dateOfBirth'),
                gender=request.POST.get('gender'),
                marital_status=request.POST.get('maritalStatus'),
                address=request.POST.get('address'),
                phone=request.POST.get('phone'),
                email=request.POST.get('email'),
                county=request.POST.get('county'),
                
                # Section 2: Academic Information
                # KCPE
                kcpe_index=request.POST.get('kcpeIndex', ''),
                kcpe_marks=request.POST.get('kcpeMarks', None),
                kcpe_mean_grade=request.POST.get('kcpeMeanGrade', ''),
                kcpe_year=request.POST.get('kcpeYear', None),
                kcpe_school=request.POST.get('kcpeSchool', ''),
                
                # KCSE
                kcse_index=request.POST.get('kcseIndex'),
                kcse_mean_grade=request.POST.get('kcseMeanGrade'),
                kcse_year=request.POST.get('kcseYear'),
                kcse_school=request.POST.get('kcseSchool'),
                
                # Qualifications
                qualifications=qualifications_str,
                work_experience=request.POST.get('workExperience', ''),
                
                # Section 3: Course Selection
                intake_period=request.POST.get('intakePeriod'),
                course_type=request.POST.get('courseType'),
                course=request.POST.get('course'),
                sponsorship=request.POST.get('sponsorship'),
                reason_application=request.POST.get('reasonApplication'),
                
                # Section 4: Additional Information
                employment_status=request.POST.get('employmentStatus'),
                disability=request.POST.get('disability'),
                disability_description=request.POST.get('disabilityDescription', ''),
                referral_source=request.POST.get('referralSource', ''),
                
                # Next of Kin
                next_of_kin_name=request.POST.get('nextOfKinName'),
                next_of_kin_phone=request.POST.get('nextOfKinPhone'),
                next_of_kin_relation=request.POST.get('nextOfKinRelation'),
                
                # Documents
                id_document=request.FILES.get('idUpload'),
                kcse_certificate=request.FILES.get('kcseUpload'),
                
                # System Fields
                application_reference=app_reference,
                status='submitted'
            )
            
            # Success message
            messages.success(
                request,
                f'✓ Application submitted successfully!\n\n'
                f'Reference: {app_reference}\n'
                f'We will review your application and contact you soon.'
            )
            
            # Redirect to success page or confirmation page
            return redirect('application_success', app_id=application.id)
            
        except Exception as e:
            messages.error(request, f'Error submitting application: {str(e)}')
            return render(request, 'clientside/apply_courses.html', {'dept': dept})
    
    else:
        # ============================================
        # HANDLE FORM DISPLAY (GET Request)
        # ============================================
        return render(request, 'clientside/apply_courses.html', {'dept': dept})

def application_success(request, app_id):
    """Show success page after application submission"""
    
    application = get_object_or_404(CourseApplication, id=app_id)
    
    return render(request, 'clientside/application_success.html', {
        'application': application
    })

# -----------------------------------------------

# CourseApplication views Ends here

# -----------------------------------------------

def heads_of_departments(request):
    return render(request, 'clientside/heads_of_departments.html')


def admin_index(request):
    admin_data, created = AdminIndex.objects.get_or_create(pk=1)

    if request.method == 'POST':
        # Update Facts Section
        admin_data.num_institutions = request.POST.get('partners', admin_data.num_institutions)
        admin_data.num_trainees = request.POST.get('trainees', admin_data.num_trainees)
        admin_data.num_trainers = request.POST.get('trainers', admin_data.num_trainers)
        admin_data.save()

        # Handle new Carousel Slide addition
        image = request.FILES.get('carousel_image')
        subtitle = request.POST.get('carousel_subtitle')
        title = request.POST.get('carousel_title')

        if image and subtitle and title:
            CarouselSlide.objects.create(
                admin_index=admin_data,
                image=image,
                heading=title,
                subheading=subtitle
            )

        return redirect('admin_index')

    slides = CarouselSlide.objects.filter(admin_index=admin_data).order_by('order')

    return render(request, 'adminpages/admin_index.html', {
    'admin_data': admin_data,
    'adminindex_items': [admin_data],  # <-- make it a list so the template can loop through it
    'slides': slides
})




def update_adminindex(request, pk):
    admin_data = get_object_or_404(AdminIndex, pk=pk)

    if request.method == 'POST':
        # Update logic
        admin_data.num_institutions = request.POST.get('partners', admin_data.num_institutions)
        admin_data.num_trainees = request.POST.get('trainees', admin_data.num_trainees)
        admin_data.num_trainers = request.POST.get('trainers', admin_data.num_trainers)
        admin_data.save()
        return redirect('admin_index')

    return render(request, 'adminpages/update_adminindex.html', {'admin_data': admin_data})


def delete_slide(request, slide_id):
    if request.method == 'POST':
        slide = get_object_or_404(CarouselSlide, id=slide_id)
        slide.delete()
    return redirect('admin_index')



def about(request):
    about_data = AdminAbout.objects.first()
    team_members = AdminInstitutionalManagement.objects.all()
    return render(request, 'clientside/about.html', {'about_data': about_data, 'team_members': team_members})


def admin_about(request):
    # Get or create the primary AdminAbout instance (used for the form)
    about_data, created = AdminAbout.objects.get_or_create(pk=1)

    if request.method == 'POST':
        about_data.title = request.POST.get('title')
        about_data.paragraph1 = request.POST.get('paragraph1')
        about_data.paragraph2 = request.POST.get('paragraph2')
        about_data.paragraph3 = request.POST.get('paragraph3')
        about_data.phone = request.POST.get('phone')

        if 'image' in request.FILES:
            about_data.image = request.FILES['image']

        about_data.save()
        return redirect('admin_about')

    # Pass both the form instance and all AdminAbout records for the table
    all_about_entries = AdminAbout.objects.all()

    return render(request, 'adminpages/admin_about.html', {
        'about': about_data,
        'adminabout_items': all_about_entries
    })

def update_admin_about(request, pk):
    about = get_object_or_404(AdminAbout, pk=pk)

    if request.method == 'POST':
        about.title = request.POST.get('title')
        about.paragraph1 = request.POST.get('paragraph1')
        about.paragraph2 = request.POST.get('paragraph2')
        about.paragraph3 = request.POST.get('paragraph3')
        about.phone = request.POST.get('phone')

        if 'image' in request.FILES:
            about.image = request.FILES['image']

        about.save()
        return redirect('admin_about')

    return render(request, 'adminpages/update_admin_about.html', {'about': about})



def admin_inst_mgt(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        title = request.POST.get('title')
        twitter = request.POST.get('twitter')
        facebook = request.POST.get('facebook')
        linkedin = request.POST.get('linkedin')
        image = request.FILES.get('image')

        if name and title and image:
            AdminInstitutionalManagement.objects.create(
                name=name,
                title=title,
                twitter=twitter,
                facebook=facebook,
                linkedin=linkedin,
                image=image
            )
            return redirect('admin_inst_mgt')

    managers = AdminInstitutionalManagement.objects.all()
    return render(request, 'adminpages/admin_inst_mgt.html', {'managers': managers})

def update_inst_member(request, manager_id):
    manager = get_object_or_404(AdminInstitutionalManagement, id=manager_id)

    if request.method == 'POST':
        manager.name = request.POST.get('name')
        manager.title = request.POST.get('title')
        manager.twitter = request.POST.get('twitter')
        manager.facebook = request.POST.get('facebook')
        manager.linkedin = request.POST.get('linkedin')

        if 'image' in request.FILES:
            manager.image = request.FILES['image']

        manager.save()
        return redirect('admin_inst_mgt')

    return render(request, 'adminpages/update_inst_member.html', {'manager': manager})

def admin_bom(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        title = request.POST.get('title')
        twitter = request.POST.get('twitter')
        facebook = request.POST.get('facebook')
        linkedin = request.POST.get('linkedin')
        image = request.FILES.get('image')

        if name and title and image:
            AdminBom.objects.create(
                name=name,
                title=title,
                twitter=twitter,
                facebook=facebook,
                linkedin=linkedin,
                image=image
            )
            return redirect('admin_bom')

    managers = AdminBom.objects.all()
    return render(request, 'adminpages/admin_bom.html', {'managers': managers})

def admin_academic_departments(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        heading = request.POST.get('heading')
        description = request.POST.get('description')
        read_more_link = request.POST.get('read_more_link')
        image = request.FILES.get('image')

        AdminAcDpt.objects.create(
            name=name,
            heading=heading,
            description=description,
            read_more_link=read_more_link,
            image=image
        )
        return redirect('admin_academic_departments')  # replace with your actual view name

    departments = AdminAcDpt.objects.all()
    return render(request, 'adminpages/admin_acdpts.html', {'departments': departments})

def admin_non_academic_departments(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        heading = request.POST.get('heading')
        description = request.POST.get('description')
        read_more_link = request.POST.get('read_more_link')
        image = request.FILES.get('image')

        AdminNonAcDpt.objects.create(
            name=name,
            heading=heading,
            description=description,
            read_more_link=read_more_link,
            image=image
        )
        return redirect('admin_non_academic_departments')  # replace with your actual view name

    departments = AdminNonAcDpt.objects.all()
    return render(request, 'adminpages/admin_non_acdpts.html', {'departments': departments})

def admin_dashboard(request):
    return render(request, 'adminpages/admin_dashboard.html')


@csrf_protect
def trainee_registration(request):
    if request.method == 'POST':
        admission_date_str = request.POST.get('date_of_admission')
        try:
            admission_date = datetime.strptime(admission_date_str, '%Y-%m-%d').date()
        except ValueError:
            admission_date = None

        passport_image = request.FILES.get('passport_image')  # ✅ handle image file

        trainee = Trainee.objects.create(
            first_name=request.POST.get('first_name'),
            middle_name=request.POST.get('middle_name'),
            last_name=request.POST.get('last_name'),
            gender=request.POST.get('gender'),
            age=request.POST.get('age'),
            date_of_admission=admission_date,
            course=Course.objects.get(id=request.POST.get('course')),
            department=Department.objects.get(id=request.POST.get('department')),
            
            kcse_index=request.POST.get('kcse_index'),
            kcse_grade=request.POST.get('kcse_grade'),
            kcse_year=request.POST.get('kcse_year'),
            kcpe_index=request.POST.get('kcpe_index'),
            kcpe_grade=request.POST.get('kcpe_grade'),
            kcpe_year=request.POST.get('kcpe_year'),
            county=request.POST.get('county'),
            sub_county=request.POST.get('sub_county'),
            division=request.POST.get('division'),
            location=request.POST.get('location'),
            phone=request.POST.get('phone'),
            id_number=request.POST.get('id_number'),
            email=request.POST.get('email'),
            guardian_name=request.POST.get('guardian_name'),
            guardian_phone=request.POST.get('guardian_phone'),
            guardian_id=request.POST.get('guardian_id'),
            passport_image=passport_image if passport_image else None  # ✅ optional
        )

        messages.success(request, "Trainee registered successfully!")
        return redirect('trainee_profile', trainee_id=trainee.id)

    departments = Department.objects.all()
    
    return render(request, 'registrar_academics/trainee_reg.html', {
        'departments': departments,
        
    })


def registrar_register_session(request):
    warning = None
    errors = []

    if request.method == 'POST':
        trainee_number = request.POST.get('trainee_number')

        try:
            trainee = Trainee.objects.get(trainee_number=trainee_number)

            try:
                current_session = CurrentSession.objects.get(is_active=True)
            except CurrentSession.DoesNotExist:
                errors.append("No active session available.")
                current_session = None

            if current_session:
                if TraineeSession.objects.filter(
                    trainee=trainee,
                    session_period=current_session.session_period
                ).exists():
                    warning = f"{trainee} is already registered for {current_session.session_period}."
                else:
                    last_session = TraineeSession.objects.filter(
                        trainee=trainee
                    ).order_by('-created_at').first()

                    if last_session:
                        year_of_study = int(last_session.year_of_study)
                        term = int(last_session.term)
                        if term < 3:
                            term += 1
                        else:
                            term = 1
                            year_of_study += 1
                    else:
                        year_of_study, term = 1, 1

                    session = TraineeSession(
                        trainee=trainee,
                        current_session=current_session,
                        session_period=current_session.session_period,
                        year_of_study=year_of_study,
                        term=term,
                    )
                    try:
                        session.save()

                        # ✅ Create FeeStatement DEBIT entry
                        debit_payment_id = f"INV-DEBIT-{session.id}"
                        FeeStatement.objects.create(
                            trainee=trainee,
                            transaction_type="DEBIT",
                            amount=session.fee_balance,   # total charge (including carry forward)
                            balance_after=session.fee_balance,
                            invoice_number=debit_payment_id,
                            reference=debit_payment_id,
                            session_period=session.session_period,
                            year_of_study=session.year_of_study,   # ✅ store year
                            term=session.term                      # ✅ store term
                        )

                        warning = f"{trainee} successfully registered for {current_session.session_period} (Year {year_of_study} Term {term})."
                    except ValidationError as ve:
                        for field, messages in ve.message_dict.items():
                            errors.extend(messages)

        except Trainee.DoesNotExist:
            errors.append("Trainee not found.")

    return render(request, 'registrar_academics/register_session.html', {
        'warning': warning,
        'errors': errors
    })




def create_current_session(request):
    if request.method == 'POST':
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')

        try:
            # Convert strings to date objects
            from datetime import datetime
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()

            # Expire all old sessions
            CurrentSession.objects.filter(end_date__lt=timezone.now().date()).update(is_active=False)

            # Create new current session
            current_session = CurrentSession(start_date=start_date_obj, end_date=end_date_obj)
            current_session.full_clean()  # run model validations
            current_session.save()
            messages.success(request, "Current session created successfully.")
            return redirect('create_current_session')

        except Exception as e:
            messages.error(request, f"Error creating session: {e}")

    return render(request, 'registrar_academics/create_current_session.html')



def trainees_in_session(request):
    # Get the active current session based on today's date
    today = timezone.now().date()
    current_session = CurrentSession.objects.filter(
        start_date__lte=today,
        end_date__gte=today,
        is_active=True
    ).first()

    trainees = []
    if current_session:
        # Fetch all TraineeSession records registered within the current session
        trainees = TraineeSession.objects.filter(
            date_registered__range=(current_session.start_date, current_session.end_date)
        ).select_related('trainee', 'trainee__course')

    context = {
        'current_session': current_session,
        'trainees': trainees
    }
    return render(request, 'registrar_academics/trainees_in_session.html', context)





def edit_trainee(request, trainee_id):
    trainee = get_object_or_404(Trainee, id=trainee_id)

    if request.method == 'POST':
        admission_date_str = request.POST.get('date_of_admission')
        try:
            admission_date = datetime.strptime(admission_date_str, '%Y-%m-%d').date()
        except ValueError:
            admission_date = None

        # Extract number part from existing trainee_number
        match = re.search(r'/(\d{4})/', trainee.trainee_number)
        number_part = match.group(1) if match else None

        # Update fields
        trainee.first_name = request.POST.get('first_name')
        trainee.middle_name = request.POST.get('middle_name')
        trainee.last_name = request.POST.get('last_name')
        trainee.gender = request.POST.get('gender')
        trainee.age = request.POST.get('age')
        trainee.date_of_admission = admission_date
        trainee.course = Course.objects.get(id=request.POST.get('course'))
        trainee.department = Department.objects.get(id=request.POST.get('department'))
        trainee.level = request.POST.get('level')
        trainee.kcse_index = request.POST.get('kcse_index')
        trainee.kcse_grade = request.POST.get('kcse_grade')
        trainee.kcse_year = request.POST.get('kcse_year')
        trainee.kcpe_index = request.POST.get('kcpe_index')
        trainee.kcpe_grade = request.POST.get('kcpe_grade')
        trainee.kcpe_year = request.POST.get('kcpe_year')
        trainee.county = request.POST.get('county')
        trainee.sub_county = request.POST.get('sub_county')
        trainee.division = request.POST.get('division')
        trainee.location = request.POST.get('location')
        trainee.phone = request.POST.get('phone')
        trainee.id_number = request.POST.get('id_number')
        trainee.email = request.POST.get('email')
        trainee.guardian_name = request.POST.get('guardian_name')
        trainee.guardian_phone = request.POST.get('guardian_phone')
        trainee.guardian_id = request.POST.get('guardian_id')

        # ✅ Handle passport photo update
        if request.FILES.get('passport_image'):
            trainee.passport_image = request.FILES['passport_image']

        # Regenerate trainee number with old count
        trainee.trainee_number = trainee.generate_trainee_number(number_part)
        trainee.save()

        messages.success(request, "Trainee profile updated successfully!")
        return redirect('trainee_profile', trainee_id=trainee.id)

    departments = Department.objects.all()
    return render(request, 'registrar_academics/edit_trainee_profile.html', {
        'trainee': trainee,
        'departments': departments,
    })



def get_courses(request, dept_id):
    courses = Course.objects.filter(department_id=dept_id).values('id', 'name')
    return JsonResponse(list(courses), safe=False)

def trainee_profile(request, trainee_id):
    trainee = get_object_or_404(Trainee, id=trainee_id)
    return render(request, 'registrar_academics/trainees_profile.html', {'trainee': trainee})


def all_trainees(request):
    trainees = Trainee.objects.all()
    return render(request, 'registrar_academics/all_trainees.html', {'trainees': trainees})



def admin_logout(request):
    # Clear all session data
    request.session.flush()
    
    # Redirect to the login page
    return redirect('admin_login')


# def registrar_academics_dashboard(request):
#     if request.session.get('designation') != 'Registrar Academics':
#         return redirect('admin_login')

    
#     return render(request, 'registrar_academics/registrar_academics_dashboard.html')


# ------------------------------------------------------

# changes for registrar academics dashboard starts here

# ------------------------------------------------------

from .models import CourseApplication


def registrar_academics_dashboard(request):
    # Security check - normalize designation to lowercase for consistency
    designation = request.session.get('designation', '').strip().lower()
    if designation != 'registrar academics':
        return redirect('admin_login')

    # Fetch applications
    applications = CourseApplication.objects.all()

    # Pass context to template
    context = {
        'applications': applications
    }

    return render(
        request,
        'registrar_academics/registrar_academics_dashboard.html',
        context
    )


def delete_application(request, app_id):
    """
    Delete application (Registrar action)
    """
    application = get_object_or_404(CourseApplication, id=app_id)
    application.delete()
    messages.success(request, "Application deleted successfully.")
    return redirect('registrar_academics_dashboard')

# ------------------------------------------------------

# changes for registrar academics dashboard ends here

# ------------------------------------------------------

def dp_admin_dashboard(request):
    designation = request.session.get('designation', '').strip().lower()
    if designation != 'dp admin':
        return redirect('admin_login')
    return render(request, 'dp_admin/dp_admin_dashboard.html')



def dp_academics_dashboard(request):
    designation = request.session.get('designation', '').strip().lower()
    if designation != 'dp academics':
        return redirect('admin_login')
    return render(request, 'dp_academics/dp_academics_dashboard.html')


# def hod_dashboard_view(request):
#     if request.session.get('designation') != 'HOD':
#         return redirect('admin_login')
#     return render(request, 'hod/hod_dashboard.html', {'name': request.session.get('admin_name')})

# def dp_academics_dashboard_view(request):
#     if request.session.get('designation') != 'DP Academics':
#         return redirect('admin_login')
#     return render(request, 'dashboard/dp_academics.html', {'name': request.session.get('admin_name')})


import re

def gender_by_intake_data(request):
    trainees = Trainee.objects.exclude(trainee_number='').exclude(gender__isnull=True)

    # Extract intake codes and group by gender
    intakes = {}
    for s in trainees:
        match = re.search(r'(\d{2}[A-Z])$', s.trainee_number)  # Matches like 23J, 23M, 23S
        if match:
            code = match.group(1)
            if code not in intakes:
                intakes[code] = {"Male": 0, "Female": 0}
            if s.gender == 'Male':
                intakes[code]["Male"] += 1
            elif s.gender == 'Female':
                intakes[code]["Female"] += 1

    # Sort intake codes chronologically
    sorted_codes = sorted(intakes.keys())
    
    labels = sorted_codes
    male_data = [intakes[code]["Male"] for code in sorted_codes]
    female_data = [intakes[code]["Female"] for code in sorted_codes]

    chart_data = {
        "labels": labels,
        "datasets": [
            {
                "label": "Male Trainees",
                "fillColor": "rgba(60,141,188,0.9)",
                "strokeColor": "rgba(60,141,188,0.8)",
                "pointColor": "#3b8bba",
                "pointStrokeColor": "rgba(60,141,188,1)",
                "pointHighlightFill": "#fff",
                "pointHighlightStroke": "rgba(60,141,188,1)",
                "data": male_data
            },
            {
                "label": "Female Trainees",
                "fillColor": "rgba(210,214,222,0.9)",
                "strokeColor": "rgba(210,214,222,0.8)",
                "pointColor": "#c1c7d1",
                "pointStrokeColor": "rgba(210,214,222,1)",
                "pointHighlightFill": "#fff",
                "pointHighlightStroke": "rgba(220,220,220,1)",
                "data": female_data
            }
        ]
    }

    return JsonResponse(chart_data)

def department_trainee_data(request):
    department_counts = Trainee.objects.values('department__name').annotate(count=Count('id'))

    colors = [
        "#f56954", "#00a65a", "#f39c12", "#00c0ef",
        "#3c8dbc", "#d2d6de", "#8e44ad", "#27ae60"
    ]

    data = []
    for index, entry in enumerate(department_counts):
        data.append({
            'label': entry['department__name'] or 'Unassigned',
            'value': entry['count'],
            'color': colors[index % len(colors)],
            'highlight': colors[index % len(colors)]
        })

    return JsonResponse(data, safe=False)

def trainee_progress_stats_api(request):
    total_male = Trainee.objects.filter(gender='Male').count()
    total_female = Trainee.objects.filter(gender='Female').count()
    total_all = Trainee.objects.count()

    # Get latest intake by date
    latest_date = Trainee.objects.order_by('-date_of_admission').values_list('date_of_admission', flat=True).first()

    latest_male = latest_female = latest_total = 0
    if latest_date:
        latest_year = latest_date.year
        latest_month = latest_date.month
        latest_intake = Trainee.objects.filter(date_of_admission__year=latest_year, date_of_admission__month=latest_month)
        latest_male = latest_intake.filter(gender='Male').count()
        latest_female = latest_intake.filter(gender='Female').count()
        latest_total = latest_intake.count()

    return JsonResponse({
        "total_male": total_male,
        "total_female": total_female,
        "total_all": total_all,
        "latest_male": latest_male,
        "latest_female": latest_female,
        "latest_total": latest_total,
    })



def top_courses_api(request):
    # Group trainees by course and intake code
    trainee_data = Trainee.objects.all().select_related('course')

    course_intake_counts = defaultdict(lambda: defaultdict(int))  # {course_name: {intake: count}}

    for trainee in trainee_data:
        course_name = trainee.course.name
        intake_code = trainee.trainee_number.split('/')[-1]  # Extract intake code from trainee number
        course_intake_counts[course_name][intake_code] += 1

    response_data = []

    for course_name, intakes in course_intake_counts.items():
        sorted_intakes = sorted(intakes.items())  # Sort by intake code
        if len(sorted_intakes) >= 2:
            prev_intake, prev_count = sorted_intakes[-2]
            curr_intake, curr_count = sorted_intakes[-1]
            try:
                percent_change = round(((curr_count - prev_count) / prev_count) * 100, 1)
            except ZeroDivisionError:
                percent_change = 100.0  # If previous is 0, we assume full increase
        else:
            curr_intake, curr_count = sorted_intakes[-1]
            percent_change = 0.0  # No comparison available

        response_data.append({
            'name': course_name,
            'current': curr_count,
            'percent_change': percent_change,
        })

    # Optional: Sort by highest current intake
    response_data.sort(key=lambda x: x['current'], reverse=True)

    return JsonResponse(response_data, safe=False)

from django.http import JsonResponse
from .models import Trainee  # adjust the import if your model is named differently

from django.core.serializers import serialize
from django.utils.timesince import timesince



def api_recent_trainees(request):
    trainees = Trainee.objects.order_by('-date_of_admission')[:12]
    data = []

    for trainee in trainees:
        data.append({
            'id': trainee.id,  # 🔁 Add this line
            'name': trainee.first_name,
            'image_url': trainee.passport_image.url if trainee.passport_image else '/static/img/default.jpg',
            'date_label': timesince(trainee.date_of_admission).split(',')[0] + ' ago'
        })

    return JsonResponse(data, safe=False)

def recent_courses_api(request):
    courses = Course.objects.select_related('department').order_by('-id')[:4]
    data = []

    for course in courses:
        data.append({
            'name': course.name,
            'department': course.department.name,
            'price': "Ksh 0",  # Optional placeholder
            'description': f"Department: {course.department.name}",
            'image': '/static/img/default-50x50.gif',
        })

    return JsonResponse(data, safe=False)

def total_trainees_api(request):
    total = Trainee.objects.count()
    return JsonResponse({'total_trainees': total})





def total_trainees_in_session(request):
    # Get the current active session
    current_session = CurrentSession.objects.filter(
        start_date__lte=timezone.now().date(),
        end_date__gte=timezone.now().date(),
        is_active=True
    ).first()

    if not current_session:
        return JsonResponse({"total_trainees": 0, "message": "No active session found."})

    # Count all trainees registered within this session period
    total_trainees = TraineeSession.objects.filter(
        date_registered__gte=current_session.start_date,
        date_registered__lte=current_session.end_date
    ).count()

    return JsonResponse({"total_trainees": total_trainees})


def gender_intake_stats_api(request):
    data = {}

    # 1. Total males and females
    total_males = Trainee.objects.filter(gender='Male').count()
    total_females = Trainee.objects.filter(gender='Female').count()

    data['total_males'] = total_males
    data['total_females'] = total_females

    # 2. Extract intake codes from trainee_number and group by gender
    trainees = Trainee.objects.exclude(trainee_number='').exclude(gender__isnull=True)
    
    intakes = {}
    for s in trainees:
        match = re.search(r'(\d{2}[A-Z])$', s.trainee_number)  # Matches like 23J, 24M, etc.
        if match:
            code = match.group(1)
            if code not in intakes:
                intakes[code] = {'Male': 0, 'Female': 0}
            if s.gender == 'Male':
                intakes[code]['Male'] += 1
            elif s.gender == 'Female':
                intakes[code]['Female'] += 1

    # Sort intake codes (latest first)
    sorted_intakes = sorted(intakes.keys(), reverse=True)

    # Ensure at least 2 intakes to compare
    if len(sorted_intakes) >= 2:
        latest = sorted_intakes[0]
        previous = sorted_intakes[1]

        male_latest = intakes[latest]['Male']
        female_latest = intakes[latest]['Female']

        male_previous = intakes[previous]['Male']
        female_previous = intakes[previous]['Female']

        # Calculate % change
        def percent_change(current, previous):
            if previous == 0:
                return 100 if current > 0 else 0
            return round(((current - previous) / previous) * 100)

        data.update({
            'latest_intake': latest,
            'previous_intake': previous,
            'male_latest': male_latest,
            'female_latest': female_latest,
            'male_latest_pct': percent_change(male_latest, male_previous),
            'female_latest_pct': percent_change(female_latest, female_previous),
        })
    else:
        data['error'] = "Not enough valid intakes to compare."

    return JsonResponse(data)

def all_departments(request):
    departments = Department.objects.all()
    departments_data = []

    for dept in departments:
        courses = Course.objects.filter(department=dept)
        total_courses = courses.count()

        trainees = Trainee.objects.filter(course__in=courses).order_by('-date_of_admission')
        total_trainees = trainees.count()

        intakes_by_month = (
            trainees
            .dates('date_of_admission', 'month', order='DESC')[:2]
        )

        latest_intake = 0
        previous_intake = 0
        percentage_change = "N/A"

        if intakes_by_month:
            latest_month = intakes_by_month[0]
            latest_intake = trainees.filter(
                date_of_admission__month=latest_month.month,
                date_of_admission__year=latest_month.year
            ).count()

        if len(intakes_by_month) > 1:
            previous_month = intakes_by_month[1]
            previous_intake = trainees.filter(
                date_of_admission__month=previous_month.month,
                date_of_admission__year=previous_month.year
            ).count()

            if previous_intake > 0:
                change = ((latest_intake - previous_intake) / previous_intake) * 100
                percentage_change = f"{change:.1f}%"
            else:
                percentage_change = "∞"

        departments_data.append({
            'department_name': dept.name,
            'total_courses': total_courses,
            'total_trainees': total_trainees,
            'latest_intake': latest_intake,
            'percentage_change': percentage_change,
            'trainers': "N/A",  # Update later when Trainer model exists
            'overview': getattr(dept, 'description', "N/A")
        })

    return render(request, 'registrar_academics/all_departments.html', {'departments_data': departments_data})

def all_departments_dpac(request):
    departments = Department.objects.all()
    departments_data = []

    for dept in departments:
        courses = Course.objects.filter(department=dept)
        total_courses = courses.count()

        trainees = Trainee.objects.filter(course__in=courses).order_by('-date_of_admission')
        total_trainees = trainees.count()

        intakes_by_month = (
            trainees
            .dates('date_of_admission', 'month', order='DESC')[:2]
        )

        latest_intake = 0
        previous_intake = 0
        percentage_change = "N/A"

        if intakes_by_month:
            latest_month = intakes_by_month[0]
            latest_intake = trainees.filter(
                date_of_admission__month=latest_month.month,
                date_of_admission__year=latest_month.year
            ).count()

        if len(intakes_by_month) > 1:
            previous_month = intakes_by_month[1]
            previous_intake = trainees.filter(
                date_of_admission__month=previous_month.month,
                date_of_admission__year=previous_month.year
            ).count()

            if previous_intake > 0:
                change = ((latest_intake - previous_intake) / previous_intake) * 100
                percentage_change = f"{change:.1f}%"
            else:
                percentage_change = "∞"

        departments_data.append({
            'department_name': dept.name,
            'total_courses': total_courses,
            'total_trainees': total_trainees,
            'latest_intake': latest_intake,
            'percentage_change': percentage_change,
            'trainers': "N/A",  # Update later when Trainer model exists
            'overview': getattr(dept, 'description', "N/A")
        })

    return render(request, 'dp_academics/all_departments.html', {'departments_data': departments_data})



def all_courses(request):
    courses = Course.objects.select_related('department').all()
    course_data = []

    for course in courses:
        # All trainees in this course
        trainees = Trainee.objects.filter(course=course).order_by('-date_of_admission')
        total_trainees = trainees.count()

        # Group intakes by month
        intakes_by_month = (
            trainees
            .dates('date_of_admission', 'month', order='DESC')[:2]
        )

        latest_intake = 0
        previous_intake = 0
        percentage_change = "N/A"

        if intakes_by_month:
            latest_month = intakes_by_month[0]
            latest_intake = trainees.filter(
                date_of_admission__month=latest_month.month,
                date_of_admission__year=latest_month.year
            ).count()

        if len(intakes_by_month) > 1:
            previous_month = intakes_by_month[1]
            previous_intake = trainees.filter(
                date_of_admission__month=previous_month.month,
                date_of_admission__year=previous_month.year
            ).count()

            if previous_intake > 0:
                change = ((latest_intake - previous_intake) / previous_intake) * 100
                percentage_change = f"{change:.1f}%"
            else:
                percentage_change = "∞"

        course_data.append({
            'name': course.name,
            'department': course.department.name if course.department else "N/A",
            'level': course.level if hasattr(course, 'level') else "N/A",
            'total_trainees': total_trainees,
            'latest_intake': latest_intake,
            'percentage_change': percentage_change,
        })

    return render(request, 'registrar_academics/all_courses.html', {'courses': course_data})

def all_courses_dpac(request):
    courses = Course.objects.select_related('department').all()
    course_data = []

    for course in courses:
        # All trainees in this course
        trainees = Trainee.objects.filter(course=course).order_by('-date_of_admission')
        total_trainees = trainees.count()

        # Group intakes by month
        intakes_by_month = (
            trainees
            .dates('date_of_admission', 'month', order='DESC')[:2]
        )

        latest_intake = 0
        previous_intake = 0
        percentage_change = "N/A"

        if intakes_by_month:
            latest_month = intakes_by_month[0]
            latest_intake = trainees.filter(
                date_of_admission__month=latest_month.month,
                date_of_admission__year=latest_month.year
            ).count()

        if len(intakes_by_month) > 1:
            previous_month = intakes_by_month[1]
            previous_intake = trainees.filter(
                date_of_admission__month=previous_month.month,
                date_of_admission__year=previous_month.year
            ).count()

            if previous_intake > 0:
                change = ((latest_intake - previous_intake) / previous_intake) * 100
                percentage_change = f"{change:.1f}%"
            else:
                percentage_change = "∞"

        course_data.append({
            'name': course.name,
            'department': course.department.name if course.department else "N/A",
            'level': course.level if hasattr(course, 'level') else "N/A",
            'total_trainees': total_trainees,
            'latest_intake': latest_intake,
            'percentage_change': percentage_change,
        })

    return render(request, 'dp_academics/all_courses.html', {'courses': course_data})

def add_department(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        code = request.POST.get('code')
        date_registered = request.POST.get('date_registered')

        # fallback to today's date if empty
        if not date_registered:
            date_registered = timezone.now().date()

        # Save the department
        Department.objects.create(
            name=name,
            code=code,
            date_registered=date_registered
        )
        return redirect('all_departments_dpac')  # Replace with your list view name

    return render(request, 'dp_academics/add_department.html')

from django.shortcuts import render, redirect
from .models import Course, Department
from decimal import Decimal

def add_course(request):
    if request.method == 'POST':
        name = request.POST.get('course_name')
        code = request.POST.get('course_code')
        level = request.POST.get('level')
        date_registered = request.POST.get('date_registered')
        department_id = request.POST.get('department_id')

        # New: fees inputs
        term1_fees = request.POST.get('term1_fees')
        term2_fees = request.POST.get('term2_fees')
        term3_fees = request.POST.get('term3_fees')

        if name and code and level and date_registered and department_id:
            try:
                department = Department.objects.get(id=department_id)

                # Prepend level to course name (e.g., "L4 Computing and Informatics")
                formatted_name = f"{level.split()[-1]} {name}"  
                formatted_name = f"L{formatted_name}"

                Course.objects.create(
                    name=formatted_name,
                    code=code,
                    level=level,
                    date_registered=date_registered,
                    department=department,
                    term1_fees=Decimal(term1_fees or 0),
                    term2_fees=Decimal(term2_fees or 0),
                    term3_fees=Decimal(term3_fees or 0)
                )
                return redirect('all_courses_dpac')  # Redirect to the courses list

            except Department.DoesNotExist:
                pass

    departments = Department.objects.all()
    return render(request, 'dp_academics/add_course.html', {'departments': departments})

# <<Dp_Academics Views>>
from .models import TrainerData, Department, Course

def dp_academics_dashboard(request):
    designation = request.session.get('designation', '').strip().lower()
    if designation != 'dp academics':
        return redirect('admin_login')
    return render(request, 'dp_academics/dp_academics_dashboard.html')

from .models import TrainerData, Department, TrainerOtherDocument

def trainer_registration(request):
    departments = Department.objects.all()

    if request.method == "POST":
        try:
            # Single file uploads
            passport_image = request.FILES.get("passport_image")
            tertiary_certificate = request.FILES.get("tertiary_certificate")
            o_level_certificate = request.FILES.get("o_level_certificate")
            secondary_certificate = request.FILES.get("secondary_certificate")

            # Multiple files upload for 'Others'
            other_documents = request.FILES.getlist("other_documents")

            # Create TrainerData instance
            trainer = TrainerData(
                passport_image=passport_image,
                first_name=request.POST.get("first_name"),
                middle_name=request.POST.get("middle_name"),
                last_name=request.POST.get("last_name"),
                gender=request.POST.get("gender"),
                dob=request.POST.get("dob"),

                employer=request.POST.get("employer"),
                staff_number=request.POST.get("staff_number"),
                id_number=request.POST.get("id_number"),
                phone=request.POST.get("phone"),
                email=request.POST.get("email"),

                first_appointment=request.POST.get("first_appointment"),
                current_appointment=request.POST.get("current_appointment"),
                department_id=request.POST.get("department"),

                current_jg=request.POST.get("current_jg"),
                courses=request.POST.get("courses"),
                special_responsibilities=request.POST.get("special_responsibilities"),

                kin_name=request.POST.get("kin_name"),
                kin_phone=request.POST.get("kin_phone"),
                kin_address=request.POST.get("kin_address"),
                kin_email=request.POST.get("kin_email"),

                # Academic docs
                tertiary_certificate=tertiary_certificate,
                o_level_certificate=o_level_certificate,
                secondary_certificate=secondary_certificate,
            )

            trainer.save()

            # Save multiple "Other" documents
            for doc in other_documents:
                if doc:
                    TrainerOtherDocument.objects.create(trainer=trainer, document=doc)

            # Success message
            messages.success(request, "Trainer registered successfully ✅")

            return redirect("trainer_registration")

        except Exception as e:
            messages.error(request, f"Error: {str(e)} ❌")
            return redirect("trainer_registration")

    return render(request, "dp_admin/staff_reg.html", {"departments": departments})


from .models import HOD, Department, Trainer

def register_hod(request):
    departments = Department.objects.all()

    if request.method == "POST":
        first_name = request.POST.get("first_name")
        middle_name = request.POST.get("middle_name")
        last_name = request.POST.get("last_name")
        phone = request.POST.get("phone")
        id_number = request.POST.get("id_number")
        email = request.POST.get("email")
        staff_number = request.POST.get("staff_number")
        department_id = request.POST.get("department")

        # Validate department
        try:
            department = Department.objects.get(id=department_id)
        except Department.DoesNotExist:
            messages.error(request, "Selected department does not exist.")
            return redirect('register_hod')

        # Create HOD record
        hod = HOD.objects.create(
            first_name=first_name,
            middle_name=middle_name,
            last_name=last_name,
            phone=phone,
            id_number=id_number,
            email=email,
            staff_number=staff_number,
            department=department
        )

        # 🔥 Automatically assign trainers from this department
        department_trainers = TrainerData.objects.filter(department=department)

        # Only assign if you add M2M field to HOD
        # Example:
        # hod.trainers.set(department_trainers)

        messages.success(
            request,
            f"HOD {hod.first_name} {hod.last_name} registered successfully. "
            f"{department_trainers.count()} trainers linked to this department."
        )
        return redirect('register_hod')

    return render(request, "dp_admin/hod_registration.html", {
        "departments": departments
    })

from django.shortcuts import redirect
from django.contrib import messages
from home.models import TrainerData, HOD

import re
from django.shortcuts import render, redirect
from django.contrib import messages
from home.models import TrainerData, HOD


def extract_abbreviation(dept_name):
    """
    Extract abbreviation inside parentheses.
    E.g. "Computing And Informatics(CI)" → "CI"
    If not found, return the full name.
    """
    match = re.search(r'\((.*?)\)', dept_name)
    if match:
        return match.group(1)
    return dept_name


def staff_login(request):
    if request.method == "POST":
        identifier = request.POST.get("staff_id_or_email")
        password = request.POST.get("password")

        # Try Trainer Login
        trainer = (TrainerData.objects.filter(staff_number=identifier).first()
                   or TrainerData.objects.filter(email=identifier).first())

        if trainer and trainer.staff_number == password:
            dept_abbrev = extract_abbreviation(trainer.department.name)

            request.session['staff_type'] = 'trainer'
            request.session['staff_id'] = trainer.id
            request.session['admin_name'] = f"{trainer.first_name} {trainer.last_name}"
            request.session['designation'] = "Trainer"
            request.session['dept_abbrev'] = dept_abbrev
            request.session['department'] = trainer.department.name
            request.session['profile_image_url'] = trainer.passport_image.url if trainer.passport_image else "/static/default.png"
               
            # return render(request, 'trainer/staff_dashboard.html')
            return redirect('staff_dashboard')

        # Try HOD Login
        hod = (HOD.objects.filter(staff_number=identifier).first()
               or HOD.objects.filter(email=identifier).first())

        if hod and hod.staff_number == password:
            dept_abbrev = extract_abbreviation(hod.department.name)

            request.session['staff_type'] = 'hod'
            request.session['staff_id'] = hod.id
            request.session['admin_name'] = f"{hod.first_name} {hod.last_name}"
            request.session['designation'] = "Head Of Department"
            request.session['dept_abbrev'] = dept_abbrev
            request.session['department'] = hod.department.name

            # request.session['profile_image_url'] = hod.profile_image.url if hod.profile_image else "/static/default.png"

            return render(request, 'hod/hod_dashboard.html')

        messages.error(request, "Invalid credentials.")

    return render(request, 'trainee/login.html')


 # Recommended for getting URL names

def staff_logout(request):
    """
    Clears the staff-specific session keys and redirects the user 
    to the staff login page.
    """
    # 1. Clear staff-specific session data
    if 'staff_type' in request.session:
        del request.session['staff_type']
    
    if 'staff_id' in request.session:
        del request.session['staff_id']
        
    # Optional: If you use Django's built-in messages, you might add one here:
    # messages.success(request, "You have been logged out successfully.")
    
    # 2. Redirect to the staff login page
    # Assuming 'staff_login' is the name of the URL pattern for your login view.
    return redirect(reverse('home')) 
    
    # Alternatively, if you don't use named URLs:
    # return redirect('/staff/login/') # Replace with the actual URL path



def manage_main_page(request):
    """
    View to update MainPage settings dynamically.
    """
    # We assume there is only one MainPage instance
    mainpage, created = MainPage.objects.get_or_create(id=1)

    if request.method == 'POST':
        # META / HEAD
        mainpage.site_title = request.POST.get('site_title', mainpage.site_title)
        favicon = request.FILES.get('favicon')
        if favicon:
            mainpage.favicon = favicon

        # TOPBAR
        mainpage.topbar_location = request.POST.get('topbar_location', mainpage.topbar_location)
        mainpage.topbar_phone = request.POST.get('topbar_phone', mainpage.topbar_phone)
        mainpage.topbar_email = request.POST.get('topbar_email', mainpage.topbar_email)

        mainpage.topbar_twitter = request.POST.get('topbar_twitter', mainpage.topbar_twitter)
        mainpage.topbar_facebook = request.POST.get('topbar_facebook', mainpage.topbar_facebook)
        mainpage.topbar_linkedin = request.POST.get('topbar_linkedin', mainpage.topbar_linkedin)
        mainpage.topbar_instagram = request.POST.get('topbar_instagram', mainpage.topbar_instagram)
        mainpage.topbar_youtube = request.POST.get('topbar_youtube', mainpage.topbar_youtube)

        # NAVBAR
        nav_logo = request.FILES.get('nav_logo')
        if nav_logo:
            mainpage.nav_logo = nav_logo
        mainpage.institution_name = request.POST.get('institution_name', mainpage.institution_name)

        # FOOTER CONTACT
        mainpage.footer_location = request.POST.get('footer_location', mainpage.footer_location)
        mainpage.footer_phone = request.POST.get('footer_phone', mainpage.footer_phone)
        mainpage.footer_email = request.POST.get('footer_email', mainpage.footer_email)

        mainpage.footer_twitter = request.POST.get('footer_twitter', mainpage.footer_twitter)
        mainpage.footer_facebook = request.POST.get('footer_facebook', mainpage.footer_facebook)
        mainpage.footer_linkedin = request.POST.get('footer_linkedin', mainpage.footer_linkedin)
        mainpage.footer_instagram = request.POST.get('footer_instagram', mainpage.footer_instagram)
        mainpage.footer_youtube = request.POST.get('footer_youtube', mainpage.footer_youtube)

        # FOOTER ABOUT
        mainpage.footer_about_title = request.POST.get('footer_about_title', mainpage.footer_about_title)
        mainpage.footer_about_desc = request.POST.get('footer_about_desc', mainpage.footer_about_desc)
        footer_about_logo = request.FILES.get('footer_about_logo')
        if footer_about_logo:
            mainpage.footer_about_logo = footer_about_logo

        mainpage.save()
        messages.success(request, "Main page settings updated successfully!")
        return redirect('manage_main_page')

    context = {
        'mainpage': mainpage
    }
    return render(request, 'adminpages/manage_main_page.html', context)


# ================================================================
# HOD UNIT MANAGEMENT VIEWS
# ================================================================
from .models import Unit

def hod_dashboard(request):
    """
    HOD landing page — shows their department and all units in it.
    """
    designation = request.session.get('designation', '').strip().lower()
    if designation != 'hod':
        return redirect('admin_login')

    staff_id = request.session.get('staff_id')
    try:
        hod = HOD.objects.get(id=staff_id)
    except HOD.DoesNotExist:
        return redirect('admin_login')

    # get all courses in this HOD's department
    courses = Course.objects.filter(department=hod.department)

    # get all units across those courses
    units = Unit.objects.filter(
        course__in=courses
    ).select_related('course', 'trainer')

    # get all trainers in this department
    trainers = TrainerData.objects.filter(department=hod.department)

    context = {
        'hod': hod,
        'courses': courses,
        'units': units,
        'trainers': trainers,
        'total_units': units.count(),
        'unassigned_units': units.filter(trainer__isnull=True).count(),
    }
    return render(request, 'hod/hod_dashboard.html', context)


def hod_add_unit(request):
    """
    HOD creates a new unit and optionally assigns a trainer.
    """
    designation = request.session.get('designation', '').strip().lower()
    if designation != 'head of department':
        return redirect('admin_login')

    staff_id = request.session.get('staff_id')
    try:
        hod = HOD.objects.get(id=staff_id)
    except HOD.DoesNotExist:
        return redirect('admin_login')

    # only courses in HOD's department
    courses = Course.objects.filter(department=hod.department)

    # only trainers in HOD's department
    trainers = TrainerData.objects.filter(department=hod.department)

    if request.method == 'POST':
        course_id = request.POST.get('course')
        name = request.POST.get('name', '').strip()
        code = request.POST.get('code', '').strip()
        hours = request.POST.get('hours', 40)
        term = request.POST.get('term', '1')
        trainer_id = request.POST.get('trainer') or None
        fa1_weight = request.POST.get('fa1_weight', 10)
        fa2_weight = request.POST.get('fa2_weight', 10)
        fa3_weight = request.POST.get('fa3_weight', 10)
        final_weight = request.POST.get('final_weight', 70)

        # basic validation
        errors = []
        if not name:
            errors.append("Unit name is required.")
        if not code:
            errors.append("Unit code is required.")
        if not course_id:
            errors.append("Please select a course.")

        # check weights add to 100
        try:
            total = int(fa1_weight) + int(fa2_weight) + \
                    int(fa3_weight) + int(final_weight)
            if total != 100:
                errors.append(
                    f"Assessment weights must add up to 100. "
                    f"Current total: {total}%"
                )
        except (ValueError, TypeError):
            errors.append("Assessment weights must be numbers.")

        # check code is unique
        if Unit.objects.filter(code=code).exists():
            errors.append(f"Unit code '{code}' already exists.")

        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            try:
                course = Course.objects.get(
                    id=course_id,
                    department=hod.department
                )
                trainer = None
                if trainer_id:
                    trainer = TrainerData.objects.get(
                        id=trainer_id,
                        department=hod.department
                    )

                Unit.objects.create(
                    course=course,
                    name=name,
                    code=code,
                    hours=hours,
                    term=term,
                    trainer=trainer,
                    fa1_weight=fa1_weight,
                    fa2_weight=fa2_weight,
                    fa3_weight=fa3_weight,
                    final_weight=final_weight,
                )
                messages.success(
                    request,
                    f"Unit '{name}' created successfully."
                )
                return redirect('hod_dashboard')

            except Course.DoesNotExist:
                messages.error(request, "Invalid course selected.")
            except TrainerData.DoesNotExist:
                messages.error(request, "Invalid trainer selected.")

    context = {
        'hod': hod,
        'courses': courses,
        'trainers': trainers,
    }
    return render(request, 'hod/hod_add_unit.html', context)


def hod_edit_unit(request, unit_id):
    """
    HOD edits an existing unit — can reassign trainer,
    change weights, hours, term.
    """
    designation = request.session.get('designation', '').strip().lower()
    if designation != 'head of department':
        return redirect('admin_login')

    staff_id = request.session.get('staff_id')
    try:
        hod = HOD.objects.get(id=staff_id)
    except HOD.DoesNotExist:
        return redirect('admin_login')

    # ensure this unit belongs to HOD's department
    unit = get_object_or_404(
        Unit,
        id=unit_id,
        course__department=hod.department
    )

    courses = Course.objects.filter(department=hod.department)
    trainers = TrainerData.objects.filter(department=hod.department)

    if request.method == 'POST':
        unit.name = request.POST.get('name', unit.name).strip()
        unit.code = request.POST.get('code', unit.code).strip()
        unit.hours = request.POST.get('hours', unit.hours)
        unit.term = request.POST.get('term', unit.term)

        trainer_id = request.POST.get('trainer') or None
        if trainer_id:
            try:
                unit.trainer = TrainerData.objects.get(
                    id=trainer_id,
                    department=hod.department
                )
            except TrainerData.DoesNotExist:
                messages.error(request, "Invalid trainer selected.")
                return redirect('hod_edit_unit', unit_id=unit.id)
        else:
            unit.trainer = None

        # validate weights
        try:
            fa1 = int(request.POST.get('fa1_weight', unit.fa1_weight))
            fa2 = int(request.POST.get('fa2_weight', unit.fa2_weight))
            fa3 = int(request.POST.get('fa3_weight', unit.fa3_weight))
            final = int(request.POST.get('final_weight', unit.final_weight))

            if fa1 + fa2 + fa3 + final != 100:
                messages.error(
                    request,
                    f"Weights must add up to 100. "
                    f"Current total: {fa1 + fa2 + fa3 + final}%"
                )
                return render(request, 'hod/hod_edit_unit.html', {
                    'unit': unit,
                    'courses': courses,
                    'trainers': trainers,
                    'hod': hod,
                })

            unit.fa1_weight = fa1
            unit.fa2_weight = fa2
            unit.fa3_weight = fa3
            unit.final_weight = final

        except (ValueError, TypeError):
            messages.error(request, "Assessment weights must be numbers.")
            return redirect('hod_edit_unit', unit_id=unit.id)

        unit.save()
        messages.success(request, f"Unit '{unit.name}' updated successfully.")
        return redirect('hod_dashboard')

    context = {
        'hod': hod,
        'unit': unit,
        'courses': courses,
        'trainers': trainers,
        'selected_course_id': unit.course.id,
    }
    return render(request, 'hod/hod_edit_unit.html', context)


def hod_delete_unit(request, unit_id):
    """
    HOD deletes a unit — POST only.
    """
    designation = request.session.get('designation', '').strip().lower()
    if designation != 'head of department':
        return redirect('admin_login')

    staff_id = request.session.get('staff_id')
    try:
        hod = HOD.objects.get(id=staff_id)
    except HOD.DoesNotExist:
        return redirect('admin_login')

    unit = get_object_or_404(
        Unit,
        id=unit_id,
        course__department=hod.department
    )

    if request.method == 'POST':
        unit_name = unit.name
        unit.delete()
        messages.success(
            request,
            f"Unit '{unit_name}' deleted successfully."
        )

    return redirect('hod_dashboard')

