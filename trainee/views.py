from django.shortcuts import render, redirect
from django.shortcuts import get_object_or_404
from django.shortcuts import render, redirect
from home.models import AdminIndex, CarouselSlide, AdminAbout, AdminInstitutionalManagement, AdminAcDpt, AdminNonAcDpt, Trainee
# Create your views here.
from django.shortcuts import render
from home.models import AdminIndex, CarouselSlide, AdminBom
from django.db.models import Count, Q
from django.http import JsonResponse
from django.db.models import Count
from home.models import Trainee, Course, Unit
from .forms import EvidenceArtifactForm
from collections import defaultdict
from django.shortcuts import render, redirect
from django.contrib import messages
from home.models import AdminCredentials
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_protect
from home.models import Trainee, Department, Course, Notice
from django.http import JsonResponse
from datetime import datetime
from django.contrib import messages
import re, random
from django.contrib.auth import logout

# imports to handle the login loggic
from django.contrib.auth import login, authenticate
from django.contrib import messages
from home.models import Trainee
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.core.serializers.json import DjangoJSONEncoder
# from django.contrib.auth import login, authenticate
from django.contrib import messages
from home.models import Trainee
from .auth_backends import TraineeAuthBackend
import json
from django.shortcuts import render
from django.core.serializers.json import DjangoJSONEncoder
from home.models import Conversation, Notice, Trainee
from trainee.auth_backends import TraineeAuthBackend
from django.shortcuts import render
from django.core.serializers.json import DjangoJSONEncoder
from home.models import Conversation, Notice, Trainee
from trainee.auth_backends import TraineeAuthBackend
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

from finance.models import FeeStatement
from home.models import TraineeSession, CurrentSession
from django.utils import timezone
from django.contrib import messages
from collections import defaultdict
from django.core.exceptions import ValidationError
from trainer.models import Attendance as TrainerAttendance
from hod.models import TraineeClass

def trainee_login(request):
    if request.method == 'POST':
        user_type = request.POST.get('user_type')  # 'trainee' or 'staff'
        # Trainee authentication
        if user_type == 'trainee':
            trainee_number = request.POST.get('trainee_number')
            password = request.POST.get('password')
            
            # Authenticate using our custom backend
            backend = TraineeAuthBackend()
            trainee = backend.authenticate(request, trainee_number=trainee_number, password=password)
            
            if trainee:
                # Log the trainee in
                login(request, trainee, backend='trainee.auth_backends.TraineeAuthBackend')
                return redirect('trainee:trainee_dashboard')
            else:
                messages.error(request, 'Invalid trainee number or password')
        
        # Staff authentication
        elif user_type == 'staff':
            email_or_id = request.POST.get('email') or request.POST.get('staff_id')
            password = request.POST.get('password')
            return redirect('staff_dashboard')
    
    return render(request, 'trainee/login.html')

from django.shortcuts import render, get_object_or_404
# from .models import Trainee

def portfolio_dashiboard(request):
    trainee = request.user 
    if request.user.is_authenticated:
        trainee = get_object_or_404(Trainee, trainee = request.user)
    return render(request, 'trainee/portfolio.html', {'trainee': trainee})


# @login_required (login_url='/trainee/trainee_login/')
# def trainee_profile(request):
#     return render(request, 'trainee/trainee_profile.html', {'trainee': request.user})

@login_required(login_url='/trainee/trainee_login/')
def trainee_change_password(request):
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        # Verify current password
        if not (request.user.check_password(current_password) or 
                current_password == request.user.trainee_number):
            messages.error(request, 'Current password is incorrect')
            return redirect('trainee_change_password')
        
        # Verify new passwords match
        if new_password != confirm_password:
            messages.error(request, 'New passwords do not match')
            return redirect('trainee_change_password')
        
        # Set new password
        request.user.set_password(new_password)
        request.user.save()
        
        # Update session to prevent logout
        update_session_auth_hash(request, request.user)
        
        messages.success(request, 'Your password has been updated successfully!')
        return redirect('trainee_login')
    
    return render(request, 'trainee/change_password.html')

def trainee_logout(request):
    logout(request)
    return redirect('trainee:trainee_login')

@login_required(login_url='trainee:trainee_login')
def trainee_dashboard(request):
    # Ensure user is authenticated
    if not request.user.is_authenticated:
        return redirect("trainee:trainee_login")
    
    trainee = request.user  
    current_session = CurrentSession.objects.filter(is_active=True).first()
    
    # Check if trainee is registered for current session
    is_registered = False
    current_trainee_session = None
    
    if current_session:
        current_trainee_session = TraineeSession.objects.filter(
            trainee=trainee,
            session_period=current_session.session_period
        ).first()
        is_registered = current_trainee_session is not None

    user_data = json.dumps({
        "id": trainee.id,
        "username": getattr(trainee, "full_name", f"{trainee.first_name} {trainee.last_name}")
    }, cls=DjangoJSONEncoder)

    # Shared conversation
    conversation = Conversation.objects.first()
    if not conversation:
        conversation = Conversation.objects.create()

    notices = Notice.objects.order_by('-created_at')

    return render(request, 'trainee/trainee_dashboard.html', {
        'trainee': trainee,
        'user_data': user_data,
        'conversation': conversation,
        'notices': notices,
        'is_registered': is_registered,
        'current_trainee_session': current_trainee_session,
        'current_session': current_session,
    })


@login_required(login_url='trainee:trainee_login')
def trainee_register_session(request):
    """Allow trainees to self-register for current session"""
    trainee = request.user
    warning = None
    errors = []
    success = None

    try:
        current_session = CurrentSession.objects.get(is_active=True)
    except CurrentSession.DoesNotExist:
        errors.append("No active session available. Please contact administration.")
        current_session = None

    if current_session:
        # Check if already registered
        if TraineeSession.objects.filter(
            trainee=trainee,
            session_period=current_session.session_period
        ).exists():
            warning = f"You are already registered for {current_session.session_period}."
        else:
            # Calculate next year/term
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

            # Create the session
            session = TraineeSession(
                trainee=trainee,
                current_session=current_session,
                session_period=current_session.session_period,
                year_of_study=year_of_study,
                term=term,
            )
            
            try:
                session.save()

                # Create FeeStatement DEBIT entry
                debit_payment_id = f"INV-DEBIT-{session.id}"
                FeeStatement.objects.create(
                    trainee=trainee,
                    transaction_type="DEBIT",
                    amount=session.fee_balance,
                    balance_after=session.fee_balance,
                    invoice_number=debit_payment_id,
                    reference=debit_payment_id,
                    session_period=session.session_period,
                    year_of_study=session.year_of_study,
                    term=session.term
                )

                success = f"Successfully registered for {current_session.session_period} (Year {year_of_study} Term {term}). You can now access all portal services!"
                
            except ValidationError as ve:
                for field, messages_list in ve.message_dict.items():
                    errors.extend(messages_list)

    context = {
        'trainee': trainee,
        'warning': warning,
        'errors': errors,
        'success': success,
        'current_session': current_session,
        'is_registered': TraineeSession.objects.filter(
            trainee=trainee,
            session_period=current_session.session_period if current_session else None
        ).exists() if current_session else False
    }
    return render(request, 'trainee/register_session.html', context)

@login_required(login_url='trainee:trainee_login')
def trainee_fee_statement(request):
    """Trainee view their own fee statement"""
    trainee = request.user
    current_session = CurrentSession.objects.filter(is_active=True).first()
    
    # Check if registered for current session
    if not current_session or not TraineeSession.objects.filter(
        trainee=trainee,
        session_period=current_session.session_period
    ).exists():
        messages.error(request, "You must be registered for the current accademic session to view your fee statement.")
        return redirect('trainee:trainee_dashboard')

    # Get fee statements for the trainee
    statements = FeeStatement.objects.filter(trainee=trainee).order_by("date")

    TERM_MAP = {'1': 'Term 1', '2': 'Term 2', '3': 'Term 3'}
    YEAR_MAP = {'1': 'First Year', '2': 'Second Year', '3': 'Third Year'}

    # Group by session
    grouped_statements = defaultdict(lambda: {"items": [], "termly_balance": 0})

    for stmt in statements:
        term_label = TERM_MAP.get(str(stmt.term), stmt.term)
        year_label = YEAR_MAP.get(str(stmt.year_of_study), stmt.year_of_study)
        session_label = f"{year_label} - {term_label}"

        grouped_statements[session_label]["items"].append(stmt)

    # Get latest balance for each session
    for session_label, data in grouped_statements.items():
        last_stmt = data["items"][-1]
        grouped_statements[session_label]["termly_balance"] = last_stmt.balance_after

    # Get current trainee session
    trainee_session = TraineeSession.objects.filter(trainee=trainee).order_by("-created_at").first()

    context = {
        "trainee": trainee,
        "trainee_session": trainee_session,
        "grouped_statements": grouped_statements.items(),
        "now": timezone.now(),
    }
    return render(request, "trainee/fee_statement.html", context)

# views.py
from django.shortcuts import render, redirect
from .forms import NoticeForm
from home .models import Notice

def upload_notice(request):
    if request.method == 'POST':
        form = NoticeForm(request.POST, request.FILES)
        if form.is_valid():
            saved_notice = form.save()
            return redirect('trainee:notice_detail', pk=saved_notice.pk)
    else:
        form = NoticeForm()
    
    return render(request, 'adminpages/upload_notice.html', {'form': form})

    

def notice_detail(request, pk):
    notice = get_object_or_404(Notice, pk=pk)
    other_notices = Notice.objects.exclude(pk=pk).order_by('-created_at')[:5]
    return render(request, 'notices/notice_detail.html', {
        'notice': notice,
        'other_notices': other_notices
    })    

def attendance(request):
    # For testing, get the first trainee
    trainee = Trainee.objects.first()
    if not trainee:
        # Create a test trainee if none exists
        trainee = Trainee.objects.create(
            trainee_number="TEST001",
            first_name="Test",
            last_name="Trainee",
            email="test@example.com"
        )
    
    context = {
        'trainee': trainee,
        'trainee_id': trainee.id
    }
    return render(request, 'stats/attendance.html', context)


from django.shortcuts import render, get_object_or_404
from home.models import LovedBook, Trainee
import requests


@login_required(login_url='trainee:trainee_login')
def library(request, trainee_id):
    trainee = get_object_or_404(Trainee, id=trainee_id)

    # get search params
    query = request.GET.get('q', '')
    department = request.GET.get('department', '')

    books = []

    if query:
        url = f"https://www.googleapis.com/books/v1/volumes?q={query}+subject:{department}"
        response = requests.get(url).json()

        for item in response.get("items", []):
            info = item.get("volumeInfo", {})
            books.append({
                "google_id": item["id"],
                "title": info.get("title", "No Title"),
                "author": ", ".join(info.get("authors", [])),
                "cover": info.get("imageLinks", {}).get("thumbnail", ""),
                "department": department or "General",
                "preview_link": info.get("previewLink"),  
            })

    context = {
        "trainee": trainee,
        "books": books,
        "search_query": query, 
        "borrowed_books": [],        
    }
    return render(request, 'stats/library.html', context)


@login_required(login_url='trainee:trainee_login')
def love_book(request, google_id):
    trainee = request.user
    # fetch details from Google Books
    url = f"https://www.googleapis.com/books/v1/volumes/{google_id}"
    response = requests.get(url).json()
    info = response.get("volumeInfo", {})

    LovedBook.objects.create(
        user=trainee,
        google_id=google_id,
        title=info.get("title", "No Title"),
        author=", ".join(info.get("authors", [])),
        cover=info.get("imageLinks", {}).get("thumbnail", ""),
        department=", ".join(info.get("categories", [])) if info.get("categories") else None
    )
    
    return redirect("trainee:library_detail", trainee_id=trainee.id)
    # return render ( request, 'stats/library.html', trainee_id=trainee.id)

# def assignment(request, trainee_id):
#     trainee = get_object_or_404(Trainee, id=trainee_id)
#     return render ( request, 'stats/assignments.html', {'trainee': trainee})




@login_required(login_url='/trainee/trainee_login/')
def traine_profile(request, trainee_id):
    trainee = get_object_or_404(Trainee, id=trainee_id)
    return render(request, 'trainee/trainee_profile.html', {'trainee': trainee})

# =================VIEWS FOR TIMETABLE STARTS HERE===========

from django.shortcuts import render, redirect, get_object_or_404
from home.models import Timetable, Session
from .forms import TimetableForm, SessionForm

def manage_timetable(request):
    timetables = Timetable.objects.all()
    
    if request.method == 'POST':
        form = TimetableForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('adminpages/manage_timetable')
    else:
        form = TimetableForm()
    
    return render(request, 'adminpages/timetable_admin.html', {
        'timetables': timetables,
        'form': form
    })

def edit_timetable(request, timetable_id):
    timetable = get_object_or_404(Timetable, id=timetable_id)
    
    # Get all courses for the dropdown
    courses = Course.objects.all()
    
    if request.method == 'POST':
        form = TimetableForm(request.POST, instance=timetable)
        if form.is_valid():
            form.save()
            messages.success(request, 'Timetable updated successfully!')
            return redirect('adminpages/manage_timetable')
    else:
        form = TimetableForm(instance=timetable)
    
    return render(request, 'adminpages/edit_timetable.html', {
        'timetable': timetable,
        'form': form,
        'courses': courses  # Make sure to pass courses to the template
    })

def delete_timetable(request, timetable_id):
    timetable = get_object_or_404(Timetable, id=timetable_id)
    timetable.delete()
    return redirect('adminpages/manage_timetable')

from django.shortcuts import render, get_object_or_404, redirect
from home.models import Timetable, Session
from .forms import SessionForm

def manage_sessions(request, timetable_id):
    timetable = get_object_or_404(Timetable, id=timetable_id)
    sessions = Session.objects.filter(timetable=timetable)

    if request.method == 'POST':
        form = SessionForm(request.POST)
        if form.is_valid():
            session = form.save(commit=False)
            session.timetable = timetable  # link session to timetable
            session.save()
            return redirect('trainee:manage_sessions', timetable_id=timetable.id)
    else:
        form = SessionForm()

    return render(request, 'adminpages/session_admin.html', {
        'timetable': timetable,
        'sessions': sessions,
        'form': form,
    })


def edit_session(request, session_id):
    session = get_object_or_404(Session, id=session_id)
    
    if request.method == 'POST':
        form = SessionForm(request.POST, instance=session)
        if form.is_valid():
            form.save()
            return redirect('manage_sessions', timetable_id=session.timetable.id)
    else:
        form = SessionForm(instance=session)
    
    return render(request, 'adminpages/edit_session.html', {
        'session': session,
        'form': form
    })

def delete_session(request, session_id):
    session = get_object_or_404(Session, id=session_id)
    timetable_id = session.timetable.id
    session.delete()
    return redirect('manage_sessions', timetable_id=timetable_id)    

from django.utils import timezone
from datetime import timedelta
from django.shortcuts import render
from home.models import Trainee, Timetable, Session  # make sure these are imported


def timetable_view(request):
    trainee = request.user

    # Get timetable for trainee's course and level
    timetables = Timetable.objects.filter(
        course=trainee.course,
        level=trainee.course.level.replace("Level ", "")
    ).first()

    if not timetables:
        return render(request, 'stats/timetable.html', {
            'trainee': trainee,  # still pass trainee so base template doesn’t break
            'error': 'No timetable available yet for your course and level. '
                     'Keep checking or contact your course administration.'
        })

    # Get sessions for this timetable within the current week
    now = timezone.now()
    start_of_week = now - timedelta(days=now.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    sessions = Session.objects.filter(
        timetable=timetables,
        start_time__range=[start_of_week, end_of_week]
    ).order_by('start_time')

    # Group sessions by day and mark current sessions
    sessions_by_day = {}
    time_slots = set()

    for session in sessions:
        day = session.start_time.strftime('%A, %B %d')
        time_slot = f"{session.start_time.strftime('%H:%M')} - {session.end_time.strftime('%H:%M')}"
        session.is_current = (session.start_time <= now <= session.end_time)

        sessions_by_day.setdefault(day, []).append({
            'title': session.title,
            'session_type': session.session_type,
            'location': session.location,
            'trainer': session.trainer,
            'requirements': session.requirements,
            'start_time': session.start_time,
            'end_time': session.end_time,
            'time_slot': time_slot,
            'is_current': session.is_current,
        })
        time_slots.add(time_slot)

    # Convert time slots to sorted list
    time_slots = sorted(time_slots)

    return render(request, 'stats/timetable.html', {
        'trainee': trainee,  # always included for base template
        'timetables': timetables,
        'sessions_by_day': sessions_by_day,
        'time_slots': time_slots,
        'now': now
    })




# ____________________________________
# Added views________________________


@csrf_exempt
def tecade_bot(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            message = data.get('message', '')
            image_data = data.get('image', None)
            
            # Prepare the request to Gemini API
            api_key = 'AIzaSyAq017UYKZjvSkIvu_gC7OsjjDAY2RiKYQ'
            url = f'https://generativelanguage.googleapis.com/v1beta/gemini-1.5-flash:generateContent?key={api_key}'
            
            payload = {
                "contents": [{
                    "parts": [{
                        "text": message
                    }]
                }]
            }
            
            if image_data:
                payload["contents"][0]["parts"].append({
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": image_data
                    }
                })
            
            headers = {'Content-Type': 'application/json'}
            response = requests.post(url, json=payload, headers=headers)
            response_data = response.json()
            
            bot_response = response_data['candidates'][0]['content']['parts'][0]['text']
            
            return JsonResponse({'response': bot_response})
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid request method'}, status=400)

# -------------------------ASSIGNMENTS---------------------
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from home.models import Assignment, Submission
from home.models import Trainee
from django.contrib.auth.decorators import login_required

# Helper function for template dictionary
def get_submissions_dict(trainee):
    subs = Submission.objects.filter(trainee=trainee)
    return {sub.assignment.id: sub for sub in subs}

# ---------------- Trainee Views ----------------
@login_required(login_url='trainee:trainee_login')
def assignment_list(request, trainee_id):
    # Get the trainee object
    trainee_obj = get_object_or_404(Trainee, id=trainee_id)
    # Trainee = request.user
    # Verify the logged-in user has access to this trainee's data
    # if request.user != trainee_obj.user:
    #     # Handle unauthorized access
    #     return redirect('trainee:trainee_dashboard')
    
    # Get assignments for the trainee's course
    assignments = Assignment.objects.filter(course=trainee_obj.course)
    submissions_dict = get_submissions_dict(trainee_obj)
    
    context = {
        'trainee': trainee_obj,  # Pass the actual trainee object
        'assignments': assignments, 
        'submissions_dict': submissions_dict,
        'current_user': trainee_id
    }
    return render(request, 'stats/assignments.html', context)





@login_required(login_url='trainee:trainee_login')
def submit_assignment(request, assignment_id):
    # Get the trainee object from the currently logged-in user
    try:
        # trainee = request.user
        trainee_obj = request.user
    except AttributeError:
        messages.error(request, "Trainee profile not found.")
        return redirect('trainee:trainee_dashboard')
    
    # Additional safety check
    if not trainee_obj:
        messages.error(request, "Trainee profile not found.")
        return redirect('trainee:trainee_dashboard')
    
    assignment = get_object_or_404(Assignment, id=assignment_id)
    
    # Check if due date passed
    if timezone.now() > assignment.due_date:
        messages.error(request, "Deadline passed. You cannot submit this assignment.")
        return redirect('trainee:assignment_list', trainee_id=trainee_obj.id)
    
    # Ensure only one submission
    submission, created = Submission.objects.get_or_create(
        assignment=assignment, 
        trainee=trainee_obj
    )

    if request.method == 'POST':
        file_upload = request.FILES.get('file_upload')
        short_text = request.POST.get('short_text')

        if not file_upload and not short_text:
            messages.error(request, "Please submit a file or enter text.")
            return redirect('trainee:assignment_list', trainee_id=trainee_obj.id)

        if file_upload:
            submission.file_upload = file_upload
        if short_text:
            submission.short_text = short_text
        
        submission.status = 'Submitted'
        submission.submitted_at = timezone.now()
        submission.save()
        
        messages.success(request, "Assignment submitted successfully.")
        return redirect('trainee:assignment_list', trainee_id=trainee_obj.id)

    # If it's a GET request, redirect to assignment list
    return redirect('trainee:assignment_list', trainee_id=trainee_obj.id)

# ---------------- Admin Views ----------------
@login_required
def admin_assignments(request):
    assignments = Assignment.objects.all().order_by('-due_date')
    context = {'assignments': assignments}
    return render(request, 'adminpages/admin_assignments.html', context)

@login_required
def create_assignment(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        course_id = request.POST.get('course')
        instructor_name = request.POST.get('instructor_name')
        instructor_email = request.POST.get('instructor_email')
        description = request.POST.get('description')
        instructions = request.POST.get('instructions')
        learning_objectives = request.POST.get('learning_objectives')
        rubric = request.POST.get('rubric')
        due_date = request.POST.get('due_date')
        max_points = request.POST.get('max_points')

        course = get_object_or_404(Course, id=course_id)

        Assignment.objects.create(
            title=title,
            course=course,
            instructor_name=instructor_name,
            instructor_email=instructor_email,
            description=description,
            instructions=instructions,
            learning_objectives=learning_objectives,
            rubric=rubric,
            due_date=due_date,
            max_points=max_points
        )
        messages.success(request, "Assignment created successfully.")
        return redirect('trainee:admin_assignments')

    courses = Course.objects.all()
    return render(request, 'adminpages/create_assignment.html', {'courses': courses})

@login_required
def view_submissions(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    submissions = Submission.objects.filter(assignment=assignment)
    return render(request, 'adminpages/view_submissions.html', {'assignment': assignment, 'submissions': submissions})

@login_required
def grade_submission(request, submission_id):
    submission = get_object_or_404(Submission, id=submission_id)
    if request.method == 'POST':
        submission.grade = request.POST.get('grade')
        submission.admin_feedback = request.POST.get('feedback')
        submission.status = 'Graded'
        submission.save()
        messages.success(request, f"Submission for {submission.trainee} graded successfully.")
        return redirect('trainee:view_submissions', assignment_id=submission.assignment.id)
    return render(request, 'adminpages/grade_submission.html', {'submission': submission})


# ATTENDANCE VIEW

# views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.http import JsonResponse
from django.db.models import Q
from home.models import AttendanceRegister, Attendance, Trainee, Course, Department, ExcuseRequest

# Remove the is_trainer function since we won't be using it for the dummy version


@login_required
def mark_attendance(request):
    trainee = request.user
    if not isinstance(trainee, Trainee):
        return redirect('trainee:trainee_login')

    trainee_class_slots = TraineeClass.objects.filter(trainee=trainee).values_list('class_slot', flat=True)
    available_attendances = TrainerAttendance.objects.filter(
        assignment__class_slot__in=trainee_class_slots,
        status__in=['Pending', 'Active']
    ).select_related('trainer', 'assignment__class_slot', 'unit', 'session_plan').order_by('-date', '-start_time')

    selected_attendance_id = request.POST.get('attendance') if request.method == 'POST' else None
    attendance_code = request.POST.get('attendance_code', '').strip() if request.method == 'POST' else ''
    success_message = None
    error_message = None
    selected_attendance = None

    if request.method == 'POST':
        if not selected_attendance_id or not attendance_code:
            error_message = 'Please select an attendance record and enter its UUID code.'
        else:
            try:
                selected_attendance = available_attendances.get(id=selected_attendance_id)
            except TrainerAttendance.DoesNotExist:
                error_message = 'The selected attendance is not available for you.'
            else:
                if not selected_attendance.attendance_code:
                    selected_attendance.generate_attendance_code()

                if attendance_code != selected_attendance.attendance_code:
                    error_message = 'The attendance UUID does not match the selected session.'
                elif selected_attendance.status == 'Attended':
                    success_message = 'Attendance was already marked for this session.'
                else:
                    selected_attendance.status = 'Attended'
                    selected_attendance.save()
                    success_message = 'Attendance marked successfully.'

    return render(request, 'trainee/mark_attendance.html', {
        'trainee': trainee,
        'available_attendances': available_attendances,
        'selected_attendance_id': selected_attendance_id,
        'attendance_code': attendance_code,
        'success_message': success_message,
        'error_message': error_message,
    })

# views.py
# views.py
def trainer_dashboard(request):
    # Get registers created by this trainer
    # Use the trainee's full name instead of user's full name
    trainer_name = f"{request.user.first_name} {request.user.last_name}"
    registers = AttendanceRegister.objects.filter(trainer_name=trainer_name).order_by('-date')
    
    # Get pending excuse requests for trainees in the trainer's courses
    # Since we're using Trainee objects, we need to adjust this query
    # For now, let's get all pending requests (simplified for dummy version)
    excuse_requests = ExcuseRequest.objects.filter(status='Pending').select_related('trainee')
    
    # Calculate additional stats for the dashboard
    total_trainees = Trainee.objects.count()  # Simplified for dummy version
    total_courses = Course.objects.count()    # Simplified for dummy version
    
    return render(request, "adminpages/trainer_dashboard.html", {
        "registers": registers,
        "excuse_requests": excuse_requests,
        "total_trainees": total_trainees,
        "total_courses": total_courses,
    })


def handle_excuse_request(request, request_id):
    excuse_request = get_object_or_404(ExcuseRequest, id=request_id)
    
    # Verify the trainer teaches this trainee
    trainer_courses = Course.objects.filter(trainer=request.user)
    if not trainer_courses.filter(id=excuse_request.trainee.course.id).exists():
        return redirect('access_denied')
    
    if request.method == "POST":
        action = request.POST.get("action")
        remark = request.POST.get("trainer_remark")
        
        if action == "approve":
            excuse_request.status = "Approved"
            # Update attendance record if exists
            attendance = Attendance.objects.filter(
                register__date=excuse_request.date,
                trainee=excuse_request.trainee
            ).first()
            if attendance:
                attendance.status = "Excused"
                attendance.remark = f"Excused: {excuse_request.reason}"
                attendance.save()
                
        elif action == "reject":
            excuse_request.status = "Rejected"
            
        excuse_request.trainer_remark = remark
        excuse_request.save()
        
        return redirect("trainer_dashboard")
    
    return render(request, "adminpages/excuse_review.html", {
        "excuse_request": excuse_request
    })

# views.py (trainee section)
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from home.models import Attendance, ExcuseRequest, Trainee

@login_required
def trainee_attendance(request):
    trainee = request.user
    if not isinstance(trainee, Trainee):
        return redirect('trainee:trainee_login')

    trainee_class_slots = TraineeClass.objects.filter(trainee=trainee).values_list('class_slot', flat=True)
    attendance_records = TrainerAttendance.objects.filter(
        assignment__class_slot__in=trainee_class_slots
    ).select_related('trainer', 'assignment__class_slot', 'unit', 'session_plan').order_by('-date', '-start_time')[:50]

    attendance_history = []
    for record in attendance_records:
        unit_name = getattr(record.unit, 'unit_of_competency', None) or getattr(record.unit, 'unit_competence', '') or ''
        session_name = getattr(record.session_plan, 'session_title', '') if record.session_plan else ''
        check_in = record.start_time.strftime('%H:%M') if record.start_time else 'N/A'
        check_out = record.end_time.strftime('%H:%M') if record.end_time else 'N/A'
        status = record.get_current_status() if hasattr(record, 'get_current_status') else (getattr(record, 'status', 'Pending') or 'Pending')

        attendance_history.append({
            'date': record.date.strftime('%Y-%m-%d'),
            'unit': unit_name,
            'session': session_name,
            'check_in': check_in,
            'check_out': check_out,
            'status': status,
            'trainer': str(record.trainer),
        })

    return render(request, 'stats/attendance.html', {
        'trainee': trainee,
        'attendance_history': attendance_history,
    })

@login_required
def submit_excuse_request(request):
    try:
        trainee = Trainee.objects.get(user=request.user)
    except Trainee.DoesNotExist:
        return JsonResponse({"success": False, "error": "Trainee not found"})
    
    if request.method == "POST":
        date = request.POST.get("date")
        session = request.POST.get("session")
        reason = request.POST.get("reason")
        
        excuse_request = ExcuseRequest.objects.create(
            trainee=trainee,
            date=date,
            session=session,
            reason=reason
        )
        
        # Handle file upload if present
        if 'supporting_docs' in request.FILES:
            excuse_request.supporting_docs = request.FILES['supporting_docs']
            excuse_request.save()
            
        return JsonResponse({"success": True, "request_id": excuse_request.id})
    
    return JsonResponse({"success": False, "error": "Invalid request method"})    


# views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
import calendar
from home.models import Attendance, ExcuseRequest, Trainee, AttendanceRegister

@login_required
def trainee_attendance_data(request):
    try:
        trainee = Trainee.objects.get(user=request.user)
    except Trainee.DoesNotExist:
        return JsonResponse({"error": "Trainee not found"}, status=404)
    
    # Get last update timestamp from request
    last_update = request.GET.get('last_update')
    
    # Get attendance records
    attendance_records = Attendance.objects.filter(trainee=trainee).select_related('register')
    
    if last_update:
        # Only get records updated since last check
        try:
            last_update_dt = timezone.datetime.fromisoformat(last_update.replace('Z', '+00:00'))
            attendance_records = attendance_records.filter(
                Q(updated_at__gt=last_update_dt) | Q(register__updated_at__gt=last_update_dt)
            )
        except (ValueError, AttributeError):
            pass
    
    attendance_records = attendance_records.order_by('-register__date')

    # Calculate statistics
    total_records = attendance_records.count()
    present_count = attendance_records.filter(status='Present').count()
    absent_count = attendance_records.filter(status='Absent').count()
    late_count = attendance_records.filter(status='Late').count()
    excused_count = attendance_records.filter(status='Excused').count()
    
    overall_attendance = (present_count / total_records * 100) if total_records > 0 else 0
    
    # Calculate monthly attendance (current month)
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_month = month_start + timedelta(days=32)
    month_end = next_month.replace(day=1) - timedelta(days=1)
    
    monthly_records = attendance_records.filter(
        register__date__gte=month_start,
        register__date__lte=month_end
    )
    monthly_total = monthly_records.count()
    monthly_present = monthly_records.filter(status='Present').count()
    monthly_attendance = (monthly_present / monthly_total * 100) if monthly_total > 0 else 0
    
    # Calculate absences left (assuming 10 allowed absences)
    total_allowable_absences = 10
    absences_remaining = max(0, total_allowable_absences - absent_count)
    
    # Prepare attendance history for the table
    attendance_history = []
    for record in attendance_records[:50]:  # Limit to 50 records for performance
        attendance_history.append({
            "date": record.register.date.strftime("%Y-%m-%d"),
            "day": record.register.date.strftime("%A"),
            "session": f"{record.register.time_from.strftime('%H:%M')} - {record.register.time_to.strftime('%H:%M')}",
            "check_in": "N/A",  # You might need to add these fields to your model
            "check_out": "N/A",  # You might need to add these fields to your model
            "status": record.status,
            "trainer": record.register.trainer_name,
        })
    
    # Generate notifications
    notifications = []
    if overall_attendance < 80:
        notifications.append({
            "level": "info",
            "icon": "info",
            "title": "Notice!",
            "message": "Your overall attendance is below 80%."
        })
    
    if monthly_attendance < 80:
        notifications.append({
            "level": "warning",
            "icon": "exclamation-triangle",
            "title": "Warning!",
            "message": "Your attendance for this month is below 80%."
        })
    
    if absences_remaining <= 2:
        notifications.append({
            "level": "danger",
            "icon": "exclamation-circle",
            "title": "Critical!",
            "message": f"You only have {absences_remaining} absences remaining."
        })
    
    # Prepare chart data
    # Monthly trend data (last 6 months)
    trend_labels = []
    trend_values = []
    
    for i in range(5, -1, -1):
        month = now.month - i
        year = now.year
        if month <= 0:
            month += 12
            year -= 1
        
        month_start = timezone.datetime(year, month, 1)
        _, last_day = calendar.monthrange(year, month)
        month_end = timezone.datetime(year, month, last_day)
        
        month_records = attendance_records.filter(
            register__date__gte=month_start,
            register__date__lte=month_end
        )
        month_total = month_records.count()
        month_present = month_records.filter(status='Present').count()
        month_attendance = (month_present / month_total * 100) if month_total > 0 else 0
        
        trend_labels.append(month_start.strftime("%b"))
        trend_values.append(round(month_attendance))
    
    # Attendance distribution for pie chart
    distribution_labels = ["Present", "Absent", "Late", "Excused"]
    distribution_values = [present_count, absent_count, late_count, excused_count]

    has_updates = attendance_records.exists() if last_update else True    
    # Get recent excuse requests
    excuse_requests = ExcuseRequest.objects.filter(trainee=trainee).order_by('-created_at')[:5]
    excuse_list = []
    for req in excuse_requests:
        excuse_list.append({
            "date": req.date.strftime("%Y-%m-%d"),
            "session": req.get_session_display(),
            "reason": req.reason,
            "status": req.status,
            "created_at": req.created_at.strftime("%Y-%m-%d %H:%M"),
        })
    
        return JsonResponse({
        "stats": {
            "overall": round(overall_attendance),
            "monthly": round(monthly_attendance),
            "absences_remaining": absences_remaining,
            "total_allowable_absences": total_allowable_absences,
            "late_count": late_count,
            "present_count": present_count,
            "absent_count": absent_count,
            "excused_count": excused_count,
        },
        "history": attendance_history,
        "notifications": notifications,
        "charts": {
            "trend": {
                "labels": trend_labels,
                "values": trend_values
            },
            "distribution": {
                "labels": distribution_labels,
                "values": distribution_values
            }
        },
        "excuse_requests": excuse_list,
        "last_update": timezone.now().isoformat(),
        "has_updates": has_updates
    })


@login_required
def trainee_attendance_calendar(request):
    try:
        trainee = Trainee.objects.get(user=request.user)
    except Trainee.DoesNotExist:
        return JsonResponse({"error": "Trainee not found"}, status=404)
    
    # Get start and end dates from request parameters
    start_date = request.GET.get('start')
    end_date = request.GET.get('end')
    
    # Get attendance records for this trainee within the date range
    attendance_records = Attendance.objects.filter(trainee=trainee)
    
    if start_date and end_date:
        attendance_records = attendance_records.filter(
            register__date__gte=start_date,
            register__date__lte=end_date
        )
    
    attendance_records = attendance_records.select_related('register').order_by('register__date')
    
    # Prepare events for FullCalendar
    events = []
    for record in attendance_records:
        # Determine color based on status
        color_map = {
            'Present': '#00a65a',  # Green
            'Absent': '#dd4b39',   # Red
            'Late': '#f39c12',     # Yellow
            'Excused': '#00c0ef',  # Blue
        }
        
        color = color_map.get(record.status, '#777')
        
        events.append({
            "title": record.status,
            "start": record.register.date.isoformat(),
            "color": color,
            "description": f"Session: {record.register.time_from.strftime('%H:%M')} - {record.register.time_to.strftime('%H:%M')}<br>Trainer: {record.register.trainer_name}",
            "allDay": True
        })
    
    return JsonResponse({"events": events})

@login_required
def submit_excuse_request(request):
    try:
        trainee = Trainee.objects.get(user=request.user)
    except Trainee.DoesNotExist:
        return JsonResponse({"success": False, "error": "Trainee not found"})
    
    if request.method == "POST":
        date = request.POST.get("date")
        session = request.POST.get("session")
        reason = request.POST.get("reason")
        
        # Validate required fields
        if not all([date, session, reason]):
            return JsonResponse({"success": False, "error": "Missing required fields"})
        
        try:
            excuse_request = ExcuseRequest.objects.create(
                trainee=trainee,
                date=date,
                session=session,
                reason=reason
            )
            
            # Handle file upload if present
            if 'supporting_docs' in request.FILES:
                excuse_request.supporting_docs = request.FILES['supporting_docs']
                excuse_request.save()
                
            return JsonResponse({"success": True, "request_id": excuse_request.id})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})
    
    return JsonResponse({"success": False, "error": "Invalid request method"})    



    from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

@require_GET
def trainee_attendance_data(request):
    return JsonResponse({
        "stats": {
            "overall": 90,
            "monthly": 95,
            "absences_remaining": 2,
            "total_allowable_absences": 5,
            "late_count": 1
        },
        "history": [
            {"date": "2025-08-28", "day": "Monday", "session": "Morning", "check_in": "08:05", "check_out": "12:00", "status": "Present", "trainer": "Mr. Smith"},
            {"date": "2025-08-29", "day": "Tuesday", "session": "Afternoon", "check_in": "14:05", "check_out": "17:00", "status": "Late", "trainer": "Mr. Smith"},
        ],
        "notifications": [],
        "charts": {
            "trend": {"labels": ["Jan", "Feb"], "values": [85, 90]},
            "distribution": {"labels": ["Present", "Absent", "Late", "Excused"], "values": [20, 2, 1, 3]}
        }
    })

@require_GET
def trainee_attendance_calendar(request):
    return JsonResponse({
        "events": [
            {"title": "Present", "start": "2025-08-28", "description": "Morning session"},
            {"title": "Late", "start": "2025-08-29", "description": "Afternoon session"}
        ]
    })

@require_POST
def submit_excuse_request(request):
    return JsonResponse({"status": "ok", "message": "Excuse request submitted"})


# ________________________________________________________
# __________PORT FOLIO OF EVITENCE VIEWS__________________
# ________________________________________________________

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, Http404
from django.urls import reverse
from django.conf import settings
from django.utils import timezone
from django.core.paginator import Paginator
from home.models import *
import json

from home.models import Trainee, Competency, EvidenceArtifact, Reflection, PortfolioShare, Assessment 
from django.contrib.auth import get_user_model

@login_required(login_url='/trainee/trainee_login/')
def portfolio_dashboard(request):
    user = request.user
    User = get_user_model()

    # Detect trainee instance
    if hasattr(user, 'trainee_profile'):
        trainee = user.trainee_profile
        trainee_user = user
    elif isinstance(user, Trainee):
        trainee = user
        trainee_user, _ = User.objects.get_or_create(
            username=trainee.trainee_number,
            defaults={
                'first_name': trainee.first_name,
                'last_name': trainee.last_name,
                'email': trainee.email,
                'password': trainee.trainee_number,
            },
        )
    else:
        trainee = getattr(user, 'trainee_profile', None)
        trainee_user = user

    # ===== Portfolio Data =====
    competencies = Competency.objects.select_related('category').all()

    # Count trainee's evidence
    evidence_items = EvidenceArtifact.objects.filter(trainee=trainee_user)
    evidence_count = evidence_items.count()
    target_evidence = 50

    # Calculate competency progress
    competency_status = {}
    for comp in competencies:
        has_evidence = evidence_items.filter(competencies=comp).exists()
        competency_status[comp.id] = 'competent' if has_evidence else 'in-progress'

    # Count competencies achieved
    achieved_count = sum(1 for s in competency_status.values() if s == 'competent')
    target_competencies = 20

    # Assessments
    recent_assessments = Assessment.objects.filter(
        evidence__trainee=trainee_user
    ).select_related('evidence', 'assessor').order_by('-assessment_date')[:5]

    # Evidence
    recent_evidence = evidence_items.order_by('-upload_date')[:5]

    # Share Link
    share = PortfolioShare.objects.filter(trainee=trainee_user, is_active=True).first()
    share_link = (
        request.build_absolute_uri(
            reverse('trainee:portfolio_shared', kwargs={'token': share.token})
        )
        if share and share.can_access()
        else None
    )

    context = {
        'trainee': trainee,
        'competencies': competencies,
        'competency_status': competency_status,
        'recent_evidence': recent_evidence,
        'recent_assessments': recent_assessments,
        'share_link': share_link,
        'evidence_count': evidence_count,
        'target_evidence': target_evidence,
        'achieved_count': achieved_count,
        'target_competencies': target_competencies,
    }

    return render(request, 'trainee/portfolio_main.html', context)



@login_required(login_url='/trainee/trainee_login/')
def portfolio_evidence(request):
    user = request.user
    User = get_user_model()

    # Detect trainee instance
    if hasattr(user, 'trainee_profile'):
        trainee = user.trainee_profile
        trainee_user = user
    elif isinstance(user, Trainee):
        trainee = user
        trainee_user, _ = User.objects.get_or_create(
            username=trainee.trainee_number,
            defaults={
                'first_name': trainee.first_name,
                'last_name': trainee.last_name,
                'email': trainee.email,
                'password': trainee.trainee_number,
            },
        )
    else:
        trainee = getattr(user, 'trainee_profile', None)
        trainee_user = user
    
    # Get evidence for the trainee
    evidence_list = EvidenceArtifact.objects.filter(trainee=trainee_user).order_by('-upload_date')
    
    # Filtering
    evidence_type = request.GET.get('type', '')
    if evidence_type:
        evidence_list = evidence_list.filter(evidence_type=evidence_type)
    
    competency_id = request.GET.get('competency', '')
    if competency_id:
        evidence_list = evidence_list.filter(competencies__id=competency_id)
    
    search_query = request.GET.get('q', '')
    if search_query:
        evidence_list = evidence_list.filter(
            models.Q(title__icontains=search_query) |
            models.Q(description__icontains=search_query) |
            models.Q(tags__icontains=search_query)
        )
    
    # evidence_type_counts = {}
    # for type_value, type_name in EvidenceArtifact.EVIDENCE_TYPES:
    #     count = EvidenceArtifact.objects.filter(
    #         trainee=request.user, 
    #         evidence_type=type_value
    #     ).count()
    #     evidence_type_counts[type_value] = count

    # Pagination
    paginator = Paginator(evidence_list, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get filter options
    evidence_types = EvidenceArtifact.EVIDENCE_TYPES
    competencies = Competency.objects.all()
    
    context = {
        'page_obj': page_obj,
        'evidence_types': evidence_types,
        'competencies': competencies,
        'current_type': evidence_type,
        'current_competency': competency_id,
        'search_query': search_query,
        'trainee': trainee_user,
        # 'evidence_type_counts': evidence_type_counts,
        'trainee': trainee,
    }
    
    return render(request, 'trainee/evidence.html', context)

from .forms import EvidenceArtifactForm

@login_required(login_url='/trainee/trainee_login/')
def portfolio_upload(request):
    user = request.user
    User = get_user_model()

    if isinstance(user, Trainee):
        trainee = user
        trainee_user, _ = User.objects.get_or_create(
            username=trainee.trainee_number,
            defaults={
                'first_name': trainee.first_name,
                'last_name': trainee.last_name,
                'email': trainee.email,
                'password': trainee.trainee_number,
            },
        )
    else:
        trainee = getattr(user, 'trainee_profile', None)
        trainee_user = user
    from home.models import Unit
    if trainee and hasattr(trainee, 'course') and trainee.course:
        trainee_units = Unit.objects.filter(course=trainee.course)
        # HOD extracted course units (CourseUnitsData)
        try:
            from hod.models import CourseUnitsData
            hod_units = CourseUnitsData.objects.filter(curriculum__course=trainee.course).order_by('unit_index')
        except Exception:
            hod_units = []
    else:
        trainee_units = Unit.objects.none()
        hod_units = []

    selected_hod_unit_id = None
    if request.method == 'POST':
        post_data = request.POST.copy()
        hod_unit_id = post_data.get('hod_unit_id')
        selected_hod_unit_id = hod_unit_id
        # if a HOD unit was selected, try to map to an existing `home.Unit` or create one
        if hod_unit_id:
            try:
                from hod.models import CourseUnitsData
                cu = CourseUnitsData.objects.filter(id=hod_unit_id).first()
                if cu and trainee and hasattr(trainee, 'course') and trainee.course:
                    # try to find a matching Unit by name/code
                    unit_match = Unit.objects.filter(course=trainee.course).filter(
                        Q(name__icontains=(cu.unit_of_competency or getattr(cu, 'unit_competence', ''))) |
                        Q(code__icontains=(cu.unit_of_competency or getattr(cu, 'unit_competence', '')))
                    ).first()
                    if not unit_match:
                        # create a lightweight Unit record so EvidenceArtifact can FK to it
                        code_guess = f"HOD{cu.id}"
                        unit_match = Unit.objects.create(
                            course=trainee.course,
                            name=(cu.unit_of_competency or getattr(cu, 'unit_competence', 'Unit')).strip(),
                            code=code_guess
                        )
                    post_data['unit'] = str(unit_match.id)
            except Exception:
                pass

        form = EvidenceArtifactForm(
            post_data,
            request.FILES,
            trainee=trainee  # passes trainee to scope the unit dropdown
        )
        if form.is_valid():
            evidence = form.save(commit=False)
            evidence.trainee = trainee_user
            evidence.save()
            form.save_m2m()  # saves competencies many-to-many

            messages.success(request, f'Evidence "{evidence.title}" uploaded successfully.')

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Evidence uploaded successfully'})

            return redirect('trainee:portfolio_evidence')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': form.errors}, status=400)

            messages.error(request, 'Please correct the errors below.')
    else:
        form = EvidenceArtifactForm(trainee=trainee)

    recent_uploads = EvidenceArtifact.objects.filter(
        trainee=trainee_user
    ).order_by('-upload_date')[:5]

    context = {
        'form': form,
        'trainee': trainee,
        'recent_uploads': recent_uploads,
        'trainee_Unit': trainee_units,
        'hod_units': hod_units,
        'selected_hod_unit_id': selected_hod_unit_id,
    }

    return render(request, 'trainee/upload.html', context)


from .forms import EvidenceArtifactForm, ReflectionForm

@login_required(login_url='/trainee/trainee_login/')
def portfolio_reflections(request):
    if isinstance(request.user, Trainee):
        trainee_user = get_user_model().objects.get(
            username=request.user.trainee_number
        )
        trainee_obj = request.user
    else:
        trainee_user = request.user
        trainee_obj = getattr(request.user, 'trainee_profile', None)

    if request.method == 'POST':
        form = ReflectionForm(
            request.POST,
            trainee_user=trainee_user
        )
        if form.is_valid():
            reflection = form.save(commit=False)
            reflection.trainee = trainee_user
            reflection.save()
            form.save_m2m()
            messages.success(request, 'Reflection saved successfully.')
            return redirect('trainee:portfolio_reflections')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ReflectionForm(trainee_user=trainee_user)

    reflections = Reflection.objects.filter(trainee=trainee_user).order_by('-date')
    paginator = Paginator(reflections, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'form': form,
        'page_obj': page_obj,
        'trainee': trainee_obj,
        'now': timezone.now(),
        'term_choices': Reflection.TERM_CHOICES,
        'assessment_choices': Reflection.ASSESSMENT_TYPES,
    }

    return render(request, 'trainee/reflections.html', context)

@login_required(login_url='/trainee/trainee_login/')
def edit_reflection(request, reflection_id):
    try:
        # Get the appropriate user object based on authentication backend (same as portfolio_reflections)
        if isinstance(request.user, Trainee):
            trainee_user = get_user_model().objects.get(username=request.user.trainee_number)
        else:
            trainee_user = request.user

        # Get the reflection and ensure it belongs to the current user
        reflection = Reflection.objects.get(id=reflection_id, trainee=trainee_user)
        
        if request.method == 'POST':
            # Update reflection with new data
            reflection.title = request.POST.get('title', '').strip()
            reflection.content = request.POST.get('content', '').strip()
            reflection.unit_name = request.POST.get('unit_name', '').strip()
            reflection.unit_code = request.POST.get('unit_code', '').strip()
            reflection.term = request.POST.get('term', '')
            reflection.assessment_type = request.POST.get('assessment_type', 'general')
            
            # Update related evidence
            evidence_ids = request.POST.getlist('related_evidence')
            reflection.related_evidence.clear()
            for evidence_id in evidence_ids:
                try:
                    evidence = EvidenceArtifact.objects.get(id=evidence_id, trainee=trainee_user)
                    reflection.related_evidence.add(evidence)
                except EvidenceArtifact.DoesNotExist:
                    continue
            
            reflection.save()
            messages.success(request, 'Reflection updated successfully!')
            return redirect('trainee:portfolio_reflections')
        
        # For GET request, show the form with current data
        recent_evidence = EvidenceArtifact.objects.filter(trainee=trainee_user).order_by('-upload_date')[:10]
        
        context = {
            'trainee': trainee_user,
            'reflection': reflection,
            'recent_evidence': recent_evidence,
            'term_choices': Reflection.TERM_CHOICES,
            'assessment_choices': Reflection.ASSESSMENT_TYPES,
        }
        return render(request, 'trainee/edit_reflection.html', context)
        
    except Reflection.DoesNotExist:
        messages.error(request, 'Reflection not found or you do not have permission to edit it.')
        return redirect('trainee:portfolio_reflections')


@login_required(login_url='/trainee/trainee_login/')
def portfolio_share(request):
    user = request.user
    User = get_user_model()

    if isinstance(user, Trainee):
        trainee = user
        trainee_user, _ = User.objects.get_or_create(
            username=trainee.trainee_number,
            defaults={
                'first_name': trainee.first_name,
                'last_name': trainee.last_name,
                'email': trainee.email,
            },
        )
    else:
        trainee = getattr(user, 'trainee_profile', None)
        trainee_user = user

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create':
            expires_days = int(request.POST.get('expires', 30))
            expires_at = timezone.now() + timezone.timedelta(days=expires_days)
            scope = request.POST.get('scope', 'full')
            unit_id = request.POST.get('unit', None)

            # deactivate existing shares of same scope
            PortfolioShare.objects.filter(
                trainee=trainee_user,
                scope=scope
            ).update(is_active=False)

            # resolve unit if unit-scoped
            unit = None
            if scope == 'unit' and unit_id:
                from home.models import Course
                try:
                    unit = Course.objects.get(id=unit_id)
                except Course.DoesNotExist:
                    pass

            PortfolioShare.objects.create(
                trainee=trainee_user,
                expires_at=expires_at,
                scope=scope,
                unit=unit,
            )
            messages.success(
                request,
                f"{'Unit' if scope == 'unit' else 'Full portfolio'} "
                f"share link created successfully."
            )

        elif action == 'deactivate':
            share_id = request.POST.get('share_id')
            PortfolioShare.objects.filter(
                id=share_id,
                trainee=trainee_user
            ).update(is_active=False)
            messages.success(request, "Share link deactivated.")

    # get all active shares for this trainee
    active_shares = PortfolioShare.objects.filter(
        trainee=trainee_user,
        is_active=True
    ).select_related('unit')

    # build share links
    shares_with_links = []
    for share in active_shares:
        if share.can_access():
            link = request.build_absolute_uri(
                reverse('trainee:portfolio_shared', kwargs={'token': share.token})
            )
            # get view history for this share
            recent_views = PortfolioView.objects.filter(
                share=share
            ).order_by('-viewed_at')[:5]

            shares_with_links.append({
                'share': share,
                'link': link,
                'recent_views': recent_views,
            })

    # get units this trainee has evidence for
    from home.models import Unit
    trainee_units = Unit.objects.filter(
        evidence_artifacts__trainee=trainee_user
    ).distinct()

    context = {
        'shares_with_links': shares_with_links,
        'trainee': trainee,
        'trainee_units': trainee_units,
    }

    return render(request, 'trainee/share.html', context)

from home.models import (
    EvidenceArtifact, Reflection, Assessment, PortfolioShare, 
    PortfolioView, Competency, TrainerData
)

def portfolio_shared(request, token):
    # ✅ Step 1 — validate the token
    try:
        share = PortfolioShare.objects.get(token=token)
    except PortfolioShare.DoesNotExist:
        raise Http404("Invalid share link.")

    if not share.can_access():
        raise Http404("This link is no longer active. Please request a new one.")

    trainee = share.trainee

    # ✅ Step 2 — determine who is opening the link
    viewer_name = "Anonymous"
    unit_filter = None  # None means show everything

    if request.user.is_authenticated:
    # check what type of user is opening the link
        from home.models import Trainee as TraineeModel

        if isinstance(request.user, TraineeModel):
            # a trainee is opening someone else's shared link
            # show full portfolio, identify by trainee number
            viewer_name = (
                f"{request.user.first_name} {request.user.last_name}".strip()
                or request.user.trainee_number
            )

        else:
            # Django User — check if they are a trainer
            try:
                trainer = TrainerData.objects.get(
                    email=request.user.email
                )
                unit_ids = list(
                    Unit.objects.filter(
                        trainer=trainer
                    ).values_list('id', flat=True)
                )
                unit_filter = unit_ids if unit_ids else []
                viewer_name = (
                    f"{trainer.first_name} {trainer.last_name} (Trainer)"
                )

            except TrainerData.DoesNotExist:
                # logged in Django user but not a trainer
                # e.g. admin staff — show full portfolio
                viewer_name = (
                    request.user.get_full_name()
                    or request.user.username
                )
    # ✅ Step 3 — if share is explicitly unit-scoped, respect that too
    if share.scope == 'unit' and share.unit:
        if unit_filter is not None:
            # trainer + unit-scoped share — intersection of both
            unit_filter = [
                uid for uid in unit_filter 
                if uid == share.unit.id
            ]
        else:
            unit_filter = [share.unit.id]

    # ✅ Step 4 — filter evidence based on who is viewing
    evidence_list = EvidenceArtifact.objects.filter(
        trainee=trainee
    ).select_related('unit').order_by('-upload_date')

    if unit_filter is not None:
        evidence_list = evidence_list.filter(unit__id__in=unit_filter)

    # ✅ Step 5 — filter reflections the same way
    reflections = Reflection.objects.filter(trainee=trainee).order_by('-date')

    # ✅ Step 6 — assessments scoped to visible evidence
    assessments = Assessment.objects.filter(
        evidence__in=evidence_list
    ).select_related('evidence', 'assessor')

    # ✅ Step 7 — competency status based on visible evidence only
    competencies = Competency.objects.all().select_related('category')
    competency_status = {}

    for competency in competencies:
        evidence_count = evidence_list.filter(competencies=competency).count()

        if evidence_count == 0:
            status = 'not_started'
        else:
            competent_assessments = Assessment.objects.filter(
                evidence__trainee=trainee,
                evidence__competencies=competency,
                evidence__in=evidence_list,
                status='approved'
            ).exists()

            if competent_assessments:
                status = 'competent'
            else:
                under_review = Assessment.objects.filter(
                    evidence__trainee=trainee,
                    evidence__competencies=competency,
                    evidence__in=evidence_list
                ).exclude(status='submitted').exists()

                status = 'under_review' if under_review else 'in_progress'

        competency_status[competency.id] = status

    # ✅ Step 8 — log the view
    PortfolioView.objects.create(
        share=share,
        viewed_by=viewer_name,
        unit_seen=share.unit if share.scope == 'unit' else None,
    )

    # ✅ Step 9 — group evidence by unit for cleaner display
    evidence_by_unit = {}
    for ev in evidence_list:
        unit_name = ev.unit.name if ev.unit else "General"
        if unit_name not in evidence_by_unit:
            evidence_by_unit[unit_name] = []
        evidence_by_unit[unit_name].append(ev)

    context = {
        'trainee': trainee,
        'evidence_list': evidence_list,
        'evidence_by_unit': evidence_by_unit,
        'reflections': reflections,
        'assessments': assessments,
        'competencies': competencies,
        'competency_status': competency_status,
        'is_shared_view': True,
        'is_trainer_view': unit_filter is not None,
        'scope': share.scope,
        'unit': share.unit,
    }

    return render(request, 'trainee/shared_view.html', context)
    


# Add this to your views.py
from django.utils import timezone
from datetime import date
from django.db.models import Count, Avg, Q
from home.models import Assignment, Submission, Trainee, Session, Timetable, ExcuseRequest

def trainer_assessment_dashboard(request):
    # Get counts
    assignments_count = Assignment.objects.count()
    
    # Count pending submissions (submissions not graded)
    pending_submissions = Submission.objects.filter(
        Q(grade__isnull=True),
        status='Submitted'
    ).count()
    
    # Get upcoming sessions (today and future)
    today = timezone.now().date()
    upcoming_sessions = Session.objects.filter(
        start_time__gte=timezone.now()
    ).count()
    
    # Today's sessions
    today_sessions = Session.objects.filter(
        start_time__date=today
    ).select_related('timetable__course')
    
    # Total trainees
    total_trainees = Trainee.objects.count()
    
    # Recent assignments (last 10)
    recent_assignments = Assignment.objects.all().order_by('-created_at')[:10]
    
    # Recent submissions (last 10)
    recent_submissions = Submission.objects.all().select_related('trainee', 'assignment').order_by('-submitted_at')[:10]
    
    # Calculate completion rate (percentage of assignments with submissions)
    total_assignments = Assignment.objects.count()
    assignments_with_submissions = Assignment.objects.filter(
        submission__isnull=False
    ).distinct().count()
    
    completion_rate = (assignments_with_submissions / total_assignments * 100) if total_assignments > 0 else 0
    
    # Calculate grading progress
    total_submissions = Submission.objects.count()
    graded_submissions = Submission.objects.filter(
        Q(grade__isnull=False)
    ).count()
    
    grading_progress = (graded_submissions / total_submissions * 100) if total_submissions > 0 else 0
    
    # Calculate average score
    average_score_result = Submission.objects.filter(
        grade__isnull=False
    ).aggregate(avg_score=Avg('grade'))
    average_score = average_score_result['avg_score'] or 0
    
    # Get pending excuse requests
    excuse_requests = ExcuseRequest.objects.filter(status='Pending').order_by('-created_at')[:5]
    pending_excuses = ExcuseRequest.objects.filter(status='Pending').count()
    excused_count = Attendance.objects.filter(status='Excused').count()
    late_count = Attendance.objects.filter(status='Late').count()
    
    # Get all timetables
    timetables = Timetable.objects.all()
    
    context = {
        'assignments_count': assignments_count,
        'pending_submissions': pending_submissions,
        'upcoming_sessions': upcoming_sessions,
        'today_sessions': today_sessions,
        'total_trainees': total_trainees,
        'recent_assignments': recent_assignments,
        'recent_submissions': recent_submissions,
        'completion_rate': round(completion_rate, 1),
        'grading_progress': round(grading_progress, 1),
        'average_score': round(average_score, 1),
        'pending_excuses': pending_excuses,
        'timetables': timetables,
        'excuse_requests': excuse_requests,
        'excused_count': excused_count,
        'late_count': late_count,
    }
    
    return render(request, 'trainer/assessment.html', context)

def submit_assessment(request):
    """
    Proxy — receives POST from shared_view.html
    and forwards to trainer:submit_assessment.
    Kept in trainee namespace because shared_view.html
    uses {% url 'trainee:submit_assessment' %}.
    """
    from trainer.views import submit_assessment as trainer_submit
    return trainer_submit(request)

@login_required(login_url='trainee:trainee_login')
def trainee_units(request):
    trainee = request.user

    # Trainee only has one course and one class assignment in this context.
    try:
        assignments = trainee.trainer_assignments
    except Exception:
        assignments = []

    trainer_units = []
    unique_unit_ids = set()
    unique_units = []

    for assignment in assignments:
        units = list(assignment.course_units.all())
        trainer_units.append({
            'trainer': assignment.trainer,
            'class_slot': assignment.class_slot,
            'units': units,
        })
        for unit in units:
            if unit.id not in unique_unit_ids:
                unique_unit_ids.add(unit.id)
                unique_units.append(unit)

    return render(request, 'trainee/trainee_units.html', {
        'trainee': trainee,
        'trainer_units': trainer_units,
        'unique_units': unique_units,
    })

def attendance_qr_confirm(request, attendance_code):
    try:
        attendance = TrainerAttendance.objects.select_related('assignment__class_slot', 'unit', 'session_plan', 'trainer').get(attendance_code=attendance_code)
    except TrainerAttendance.DoesNotExist:
        return render(request, 'trainee/attendance_qr_confirm.html', {
            'error_message': 'Invalid attendance QR code.'
        })

    current_status = attendance.get_current_status()
    success_message = None
    error_message = None

    if request.method == 'POST':
        if current_status == 'Pending':
            error_message = 'Attendance has not started for this session yet.'
        elif current_status == 'Unattended':
            error_message = 'This session has already ended without attendance being marked.'
        elif current_status == 'Attended':
            success_message = 'Attendance was already marked for this session.'
        else:
            attendance.status = 'Attended'
            attendance.save()
            success_message = 'Attendance marked successfully.'
            current_status = 'Attended'

    viewer = request.user if request.user.is_authenticated else None

    return render(request, 'trainee/attendance_qr_confirm.html', {
        'trainee': viewer,
        'attendance': attendance,
        'current_status': current_status,
        'success_message': success_message,
        'error_message': error_message,
    })
