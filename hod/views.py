from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from home.models import Course, Trainee, TrainerData, HOD
from .models import CourseCurriculum, CourseUnitsData, CurriculumLearningOutcome, TrainerAssighnment, Classes, TraineeClass
from .curriculum_pdf_utils import extract_curriculum_units


def hod_dashboard(request):
    return render(request, "hod/hod_dashboard.html")


@require_http_methods(["GET", "POST"])
def upload_course_curriculum(request):
    """
    View to upload a course curriculum PDF and extract unit data.
    """
    if request.method == "POST":
        course_id = request.POST.get('course')
        pdf_file = request.FILES.get('pdf_file')
        
        # Validation
        if not course_id or not pdf_file:
            messages.error(request, "Please select a course and upload a PDF file.")
            courses = Course.objects.all()
            return render(request, 'hod/upload_curriculum.html', {'courses': courses})
        
        if not pdf_file.name.lower().endswith('.pdf'):
            messages.error(request, "Please upload a valid PDF file.")
            courses = Course.objects.all()
            return render(request, 'hod/upload_curriculum.html', {'courses': courses})
        
        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            messages.error(request, "Selected course does not exist.")
            courses = Course.objects.all()
            return render(request, 'hod/upload_curriculum.html', {'courses': courses})
        
        try:
            with transaction.atomic():
                # Save the curriculum document
                curriculum = CourseCurriculum.objects.create(
                    course=course,
                    pdf_file=pdf_file,
                    file_name=pdf_file.name
                )
                
                # Extract units from the PDF
                extracted_units = extract_curriculum_units(pdf_file)
                
                # Create CourseUnitsData records
                for index, unit_data in enumerate(extracted_units, start=1):
                    curriculum_data = CourseUnitsData.objects.create(
                        curriculum=curriculum,
                        unit_index=index,
                        isced_unit_code=unit_data.isced_unit_code,
                        tvet_cdacc_unit_code=unit_data.tvet_cdacc_unit_code,
                        total_time=unit_data.total_time,
                        unit_of_competency=unit_data.unit_of_competency
                    )
                    
                    # Save learning outcomes
                    for outcome in unit_data.outcomes:
                        CurriculumLearningOutcome.objects.create(
                            curriculum_data=curriculum_data,
                            learning_outcome=outcome.get('learning_outcome', ''),
                            learning_expectations=outcome.get('learning_expectations', ''),
                            learning_assessments=outcome.get('learning_assessments', '')
                        )
                
                messages.success(
                    request,
                    f"Curriculum uploaded successfully! Extracted {len(extracted_units)} units from the PDF."
                )
                return redirect('upload_course_curriculum')
                
        except Exception as e:
            messages.error(request, f"Error processing PDF: {str(e)}")
            courses = Course.objects.all()
            return render(request, 'hod/upload_curriculum.html', {'courses': courses})
    
    # GET request
    courses = Course.objects.all()
    return render(request, 'hod/upload_curriculum.html', {'courses': courses})


def _get_logged_in_hod(request):
    if request.session.get('staff_type') != 'hod':
        return None
    hod_id = request.session.get('staff_id')
    if not hod_id:
        return None
    return HOD.objects.select_related('department').filter(id=hod_id).first()


def _parse_course_ids(course_ids_str):
    if not course_ids_str:
        return []
    parts = [p.strip() for p in course_ids_str.split(',') if p.strip()]
    ids = []
    for p in parts:
        try:
            ids.append(int(p))
        except ValueError:
            continue
    return ids


def _get_trainer_courses(trainer, hod):
    course_ids = _parse_course_ids(trainer.courses)
    if course_ids:
        return Course.objects.filter(id__in=course_ids, department=hod.department)
    # Fallback: treat stored values as course names
    if trainer.courses:
        names = [p.strip() for p in trainer.courses.split(',') if p.strip()]
        if names:
            return Course.objects.filter(name__in=names, department=hod.department)
    return Course.objects.none()


def hod_all_courses(request):
    hod = _get_logged_in_hod(request)
    if not hod:
        return redirect('staff_login')

    courses = Course.objects.select_related('department').filter(department=hod.department)
    course_data = []

    for course in courses:
        trainees = Trainee.objects.filter(course=course).order_by('-date_of_admission')
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
                percentage_change = "âˆž"

        course_data.append({
            'id': course.id,
            'name': course.name,
            'department': course.department.name if course.department else "N/A",
            'level': course.level if hasattr(course, 'level') else "N/A",
            'total_trainees': total_trainees,
            'latest_intake': latest_intake,
            'percentage_change': percentage_change,
        })

    return render(request, 'hod/all_courses.html', {'courses': course_data})


def hod_all_trainers(request):
    hod = _get_logged_in_hod(request)
    if not hod:
        return redirect('staff_login')

    trainers = TrainerData.objects.select_related('department').filter(department=hod.department)
    return render(request, 'hod/all_trainers.html', {'trainers': trainers})


def hod_add_unit(request):
    hod = _get_logged_in_hod(request)
    if not hod:
        return redirect('staff_login')

    courses = Course.objects.filter(department=hod.department).order_by('name')

    if request.method == 'POST':
        messages.error(request, "Manual unit entry is disabled. Upload a course curriculum PDF to extract units.")
        return redirect('upload_course_curriculum')

    return render(request, 'hod/add_unit.html', {'courses': courses})


def hod_course_units(request, course_id):
    hod = _get_logged_in_hod(request)
    if not hod:
        return redirect('staff_login')

    course = Course.objects.select_related('department').filter(
        id=course_id,
        department=hod.department
    ).first()
    if not course:
        return redirect('hod_all_courses')

    latest_curriculum = CourseCurriculum.objects.filter(course=course).order_by('-date_uploaded').first()
    units = CourseUnitsData.objects.filter(curriculum=latest_curriculum).order_by('unit_index') if latest_curriculum else []
    return render(request, 'hod/course_units.html', {
        'course': course,
        'units': units
    })


def hod_assign_trainer(request):
    hod = _get_logged_in_hod(request)
    if not hod:
        return redirect('staff_login')

    trainers = TrainerData.objects.select_related('department').filter(department=hod.department).order_by('first_name', 'last_name')

    if request.method == 'POST':
        trainer_id = request.POST.get('trainer_id')
        course_id = request.POST.get('course_id')
        class_slot_value = request.POST.get('class_id')
        unit_ids = request.POST.getlist('unit_ids[]')
        confirm_update = request.POST.get('confirm_update') == '1'

        if not trainer_id:
            messages.error(request, "Please select a trainer.")
        elif not course_id:
            messages.error(request, "Course is required.")
        elif not class_slot_value:
            messages.error(request, "Please select a class slot.")
        elif not unit_ids:
            messages.error(request, "Please select at least one unit.")
        else:
            trainer = TrainerData.objects.filter(id=trainer_id, department=hod.department).first()
            course = Course.objects.filter(id=course_id, department=hod.department).first()

            if not trainer:
                messages.error(request, "Selected trainer is invalid.")
            elif not course:
                messages.error(request, "Selected course is invalid.")
            else:
                trainer_courses = _get_trainer_courses(trainer, hod)
                if trainer_courses.exists() and not trainer_courses.filter(id=course.id).exists():
                    messages.error(request, "Selected course is not assigned to this trainer.")
                else:
                    units = CourseUnitsData.objects.filter(id__in=unit_ids, curriculum__course=course)
                    if not units.exists():
                        messages.error(request, "Selected units are invalid.")
                    else:
                        # Look up the class by slot value (strip whitespace to be safe)
                        class_slot_value_clean = class_slot_value.strip()
                        class_slot = Classes.objects.filter(slot=class_slot_value_clean, course=course).first()
                        if not class_slot:
                            messages.error(request, "Selected class is invalid for this course.")
                            return render(request, 'hod/assign_trainer.html', {'trainers': trainers})

                        existing = TrainerAssighnment.objects.filter(
                            trainer=trainer,
                            class_slot=class_slot
                        ).first()

                        if existing and not confirm_update:
                            warning = f"This trainer is already assighned to {class_slot.slot}. Do you want to update it instead?"
                            return render(request, 'hod/assign_trainer.html', {
                                'trainers': trainers,
                                'confirm_update': True,
                                'confirm_message': warning,
                                'pending': {
                                    'trainer_id': trainer_id,
                                    'course_id': course_id,
                                    'class_id': class_slot_value,
                                    'unit_ids': unit_ids,
                                }
                            })

                        if existing and confirm_update:
                            existing.course = course
                            existing.class_slot = class_slot
                            existing.save()
                            existing.course_units.add(*units)
                            messages.success(request, "Assignment updated successfully.")
                            return redirect('hod_assign_trainer')

                        assignment = TrainerAssighnment.objects.create(
                            trainer=trainer,
                            course=course,
                            class_slot=class_slot
                        )
                        assignment.course_units.set(units)
                        messages.success(request, "Units assigned to trainer successfully.")
                        return redirect('hod_assign_trainer')

    return render(request, 'hod/assign_trainer.html', {'trainers': trainers})


@require_http_methods(["GET", "POST"])
def hod_assign_trainee_class(request):
    hod = _get_logged_in_hod(request)
    if not hod:
        return redirect('staff_login')

    trainees = Trainee.objects.filter(department=hod.department).order_by('first_name', 'last_name')

    if request.method == 'POST':
        trainee_id = request.POST.get('trainee_id')
        course_id = request.POST.get('course_id')
        class_id = request.POST.get('class_id')
        confirm_update = request.POST.get('confirm_update') == '1'

        if not trainee_id:
            messages.error(request, "Please select a trainee.")
        elif not course_id:
            messages.error(request, "Please select a course.")
        elif not class_id:
            messages.error(request, "Please select a class.")
        else:
            trainee = Trainee.objects.filter(id=trainee_id, department=hod.department).first()
            course = Course.objects.filter(id=course_id, department=hod.department).first()
            class_slot = Classes.objects.filter(id=class_id, course=course).first()

            if not trainee:
                messages.error(request, "Selected trainee is invalid.")
            elif not course:
                messages.error(request, "Selected course is invalid.")
            elif trainee.course_id != course.id:
                messages.error(request, "Selected course does not match the trainee's course.")
            elif not class_slot:
                messages.error(request, "Selected class is invalid for this course.")
            else:
                existing = TraineeClass.objects.filter(trainee=trainee, class_slot=class_slot).first()
                if existing and not confirm_update:
                    warning = f"This trainee is already assigned to {class_slot.slot}. Do you want to update it instead?"
                    return render(request, 'hod/assign_trainee_class.html', {
                        'trainees': trainees,
                        'confirm_update': True,
                        'confirm_message': warning,
                        'pending': {
                            'trainee_id': trainee_id,
                            'course_id': course_id,
                            'class_id': class_id,
                        }
                    })
                if existing and confirm_update:
                    existing.course = course
                    existing.class_slot = class_slot
                    existing.save()
                    messages.success(request, "Trainee class assignment updated successfully.")
                    return redirect('hod_assign_trainee_class')

                TraineeClass.objects.create(
                    trainee=trainee,
                    course=course,
                    class_slot=class_slot
                )
                messages.success(request, "Trainee assigned to class successfully.")
                return redirect('hod_assign_trainee_class')

    return render(request, 'hod/assign_trainee_class.html', {'trainees': trainees})


def hod_add_class(request):
    hod = _get_logged_in_hod(request)
    if not hod:
        return redirect('staff_login')

    courses = Course.objects.filter(department=hod.department).order_by('name')

    if request.method == 'POST':
        course_id = request.POST.get('course_id')
        intake_raw = request.POST.get('intake')

        if not course_id:
            messages.error(request, "Please select a course.")
        elif not intake_raw:
            messages.error(request, "Please select an intake month.")
        else:
            course = Course.objects.filter(id=course_id, department=hod.department).first()
            if not course:
                messages.error(request, "Selected course is invalid for your department.")
            else:
                try:
                    intake_date = timezone.datetime.strptime(intake_raw, "%Y-%m").date()
                    intake_date = intake_date.replace(day=1)
                    Classes.objects.create(
                        course=course,
                        intake=intake_date
                    )
                    messages.success(request, "Class added successfully.")
                    return redirect('hod_add_class')
                except ValueError:
                    messages.error(request, "Invalid intake format.")

    return render(request, 'hod/add_class.html', {'courses': courses})


def hod_classes_list(request):
    hod = _get_logged_in_hod(request)
    if not hod:
        return redirect('staff_login')

    classes = Classes.objects.select_related('course', 'course__department')\
        .filter(course__department=hod.department)\
        .order_by('-intake', 'course__name')

    return render(request, 'hod/classes_list.html', {'classes': classes})


def hod_trainer_course_units_api(request, trainer_id):
    hod = _get_logged_in_hod(request)
    if not hod:
        return JsonResponse({'error': 'unauthorized'}, status=401)

    trainer = TrainerData.objects.filter(id=trainer_id, department=hod.department).first()
    if not trainer:
        return JsonResponse({'error': 'trainer_not_found'}, status=404)

    courses = _get_trainer_courses(trainer, hod).order_by('name')
    return JsonResponse({
        'courses': [
            {'id': c.id, 'name': c.name}
            for c in courses
        ]
    })


def hod_trainee_course_api(request, trainee_id):
    hod = _get_logged_in_hod(request)
    if not hod:
        return JsonResponse({'error': 'unauthorized'}, status=401)

    trainee = Trainee.objects.filter(id=trainee_id, department=hod.department).first()
    if not trainee or not trainee.course:
        return JsonResponse({'courses': []})

    course = Course.objects.filter(id=trainee.course_id, department=hod.department).first()
    if not course:
        return JsonResponse({'courses': []})

    return JsonResponse({
        'courses': [
            {'id': course.id, 'name': course.name}
        ]
    })


def hod_course_units_api(request, course_id):
    hod = _get_logged_in_hod(request)
    if not hod:
        return JsonResponse({'error': 'unauthorized'}, status=401)

    course = Course.objects.filter(id=course_id, department=hod.department).first()
    if not course:
        return JsonResponse({'units': []})

    latest_curriculum = CourseCurriculum.objects.filter(course=course).order_by('-date_uploaded').first()
    units = CourseUnitsData.objects.filter(curriculum=latest_curriculum).order_by('unit_index') if latest_curriculum else []
    return JsonResponse({
        'units': [
            {'id': u.id, 'name': u.unit_competence}
            for u in units
        ]
    })


def hod_course_classes_api(request, course_id):
    hod = _get_logged_in_hod(request)
    if not hod:
        return JsonResponse({'error': 'unauthorized'}, status=401)

    course = Course.objects.filter(id=course_id, department=hod.department).first()
    if not course:
        return JsonResponse({'classes': []})

    classes = Classes.objects.filter(course=course).order_by('-intake')
    return JsonResponse({
        'classes': [
            {'id': c.id, 'slot': c.slot or '', 'intake': c.intake.strftime('%Y-%m-%d')}
            for c in classes
        ]
    })
