from django.shortcuts import render, redirect
from django.utils import timezone
import json


def staff_dashboard(request):
    """
    Trainer dashboard view.
    Pulls real data from DB where available,
    falls back to safe defaults when DB is empty.
    """
    # ── Auth check ──
    if request.session.get('staff_type') != 'trainer':
        return redirect('staff_login')

    trainer_id = request.session.get('staff_id')

    # ── Lazy imports to avoid circular imports ──
    from home.models import TrainerData, Unit, Trainee, Course
    from home.models import AttendanceRegister, ExcuseRequest
    from home.models import Assignment, Submission

    # ── Get trainer object safely ──
    try:
        trainer = TrainerData.objects.get(id=trainer_id)
    except TrainerData.DoesNotExist:
        return redirect('staff_login')

    # ── Units assigned to this trainer (from HOD assignments) ──
    my_units = []
    try:
        from hod.models import TrainerAssighnment
        from types import SimpleNamespace

        assignments = TrainerAssighnment.objects.filter(trainer=trainer).prefetch_related('units', 'course_units')

        for assign in assignments:
            # Legacy manual units (hod.Units)
            for u in assign.units.all():
                my_units.append(SimpleNamespace(
                    name=getattr(u, 'unit_competence', '') or str(u),
                    code=getattr(u, 'code', '') if hasattr(u, 'code') else '',
                    hours=getattr(u, 'hours', 40),
                    term=getattr(u, 'term', '1'),
                    course=getattr(u, 'course', assign.course)
                ))

            # Extracted course units (CourseUnitsData)
            for cu in assign.course_units.all():
                my_units.append(SimpleNamespace(
                    name=cu.unit_of_competency or getattr(cu, 'unit_competence', '') or f"Unit {cu.unit_index}",
                    code=cu.isced_unit_code or (cu.tvet_cdacc_unit_code if hasattr(cu, 'tvet_cdacc_unit_code') else f"U{cu.unit_index}"),
                    hours=cu.total_time or 40,
                    term='1',
                    course=getattr(cu, 'curriculum').course if getattr(cu, 'curriculum', None) else assign.course
                ))

    except Exception:
        # Fallback to legacy Unit model if HOD app or assignments unavailable
        my_units = list(Unit.objects.filter(trainer=trainer).select_related('course'))

    # ── Courses this trainer teaches (derive from assigned units) ──
    course_ids = set()
    for u in my_units:
        c = getattr(u, 'course', None)
        if c and getattr(c, 'id', None):
            course_ids.add(c.id)

    if course_ids:
        trainer_courses = Course.objects.filter(id__in=course_ids)
    else:
        trainer_courses = Course.objects.filter(units__trainer=trainer).distinct()

    # ── Trainees in those courses ──
    trainees_qs = Trainee.objects.filter(
        course__in=trainer_courses
    ).select_related('course').order_by('-date_of_admission')

    total_trainees = trainees_qs.count()
    trainees_list  = trainees_qs[:8]

    # ── Recent attendance registers ──
    recent_registers = AttendanceRegister.objects.filter(
        course__in=trainer_courses
    ).order_by('-date')[:5]

    # ── Pending excuse requests ──
    pending_excuses = ExcuseRequest.objects.filter(
        trainee__course__in=trainer_courses,
        status='Pending'
    ).count()

    # ── Submissions ──
    try:
        recent_submissions = Submission.objects.filter(
            assignment__course__in=trainer_courses
        ).select_related('trainee', 'assignment').order_by('-submitted_at')[:5]

        pending_submissions = Submission.objects.filter(
            assignment__course__in=trainer_courses,
            status='Submitted'
        ).count()
    except Exception:
        recent_submissions  = []
        pending_submissions = 0

    # ── Recent learning guides ──
    try:
        from trainer.models import LearningGuide
        recent_guides = LearningGuide.objects.filter(
            trainer=trainer
        ).order_by('-date_preparation')[:4]
    except Exception:
        recent_guides = []

    # ── Portfolio evidence for units assigned to this trainer ──
    try:
        from home.models import EvidenceArtifact, Assessment
        from django.db.models import Q

        unit_names = [getattr(u, 'name', None) for u in my_units if getattr(u, 'name', None)]
        unit_codes = [getattr(u, 'code', None) for u in my_units if getattr(u, 'code', None)]

        evidence_qs = EvidenceArtifact.objects.none()
        q = Q()
        if trainer_courses.exists() if hasattr(trainer_courses, 'exists') else True:
            # trainer_courses may be a queryset or list; handle both
            try:
                q |= Q(unit__course__in=trainer_courses)
            except Exception:
                pass

        if unit_names:
            q |= Q(unit__name__in=unit_names)
        if unit_codes:
            q |= Q(unit__code__in=unit_codes)

        if q:
            evidence_qs = EvidenceArtifact.objects.filter(q).select_related('trainee', 'unit').order_by('-upload_date')

        recent_evidence = evidence_qs[:5]
        # Evidence without any assessments (pending)
        pending_evidence = evidence_qs.filter(assessment__isnull=True).count()
    except Exception:
        recent_evidence = []
        pending_evidence = 0

    # ── Pie chart: lesson hours per unit ──
    if my_units:
        pie_labels = json.dumps([getattr(u, 'name', str(u)) for u in my_units])
        pie_data   = json.dumps([getattr(u, 'hours', 40) for u in my_units])
    else:
        pie_labels = json.dumps(['Unit 1', 'Unit 2', 'Unit 3'])
        pie_data   = json.dumps([40, 40, 40])

    # ── Attendance bar chart ──
    unit_labels         = []
    attendance_datasets = []

    try:
        colors = [
            '#00c0ef', '#00a65a', '#f39c12',
            '#dd4b39', '#3c8dbc', '#605ca8'
        ]
        unit_labels = [getattr(u, 'name', str(u)) for u in my_units]

        for idx, trainee in enumerate(trainees_list):
            pct_per_unit = []
            for unit in my_units:
                registers = AttendanceRegister.objects.filter(
                    course=getattr(unit, 'course', None)
                )
                total_sessions = registers.count()
                if total_sessions == 0:
                    pct_per_unit.append(0)
                    continue
                present_count = 0
                for reg in registers:
                    present_count += reg.attendances.filter(
                        trainee=trainee,
                        status='Present'
                    ).count()
                pct = round((present_count / total_sessions) * 100)
                pct_per_unit.append(pct)

            attendance_datasets.append({
                'label'          : f"{trainee.first_name} {trainee.last_name}",
                'data'           : pct_per_unit,
                'backgroundColor': colors[idx % len(colors)],
            })
    except Exception:
        unit_labels         = []
        attendance_datasets = []

    # ── Dummy fallback when no real attendance data ──
    if not unit_labels or not attendance_datasets:
        unit_labels = (
            [getattr(u, 'name', str(u)) for u in my_units]
            if my_units
            else ['Unit 1', 'Unit 2', 'Unit 3']
        )
        attendance_datasets = [
            {
                'label'          : 'Sample Trainee A',
                'data'           : [75, 80, 90][:len(unit_labels)],
                'backgroundColor': '#00c0ef',
            },
            {
                'label'          : 'Sample Trainee B',
                'data'           : [60, 85, 70][:len(unit_labels)],
                'backgroundColor': '#00a65a',
            },
            {
                'label'          : 'Sample Trainee C',
                'data'           : [90, 65, 80][:len(unit_labels)],
                'backgroundColor': '#f39c12',
            },
        ]

    unit_labels_json         = json.dumps(unit_labels)
    attendance_datasets_json = json.dumps(attendance_datasets)

    # ── Stat display fallbacks ──
    total_units_display    = len(my_units) if len(my_units) > 0 else '—'
    total_trainees_display = total_trainees      if total_trainees > 0      else '—'
    pending_subs_display   = pending_submissions if pending_submissions > 0 else '—'
    pending_exc_display    = pending_excuses     if pending_excuses > 0     else '—'

    context = {
        # trainer
        'trainer'             : trainer,

        # stat boxes
        'total_trainees'      : total_trainees_display,
        'total_units'         : total_units_display,
        'pending_submissions' : pending_subs_display,
        'pending_excuses'     : pending_exc_display,

        # lists
        'my_units'            : my_units,
        'trainees_list'       : trainees_list,
        'recent_registers'    : recent_registers,
        'recent_submissions'  : recent_submissions,
        'recent_guides'       : recent_guides,
        'recent_evidence'     : recent_evidence,
        'pending_evidence'    : pending_evidence,

        # charts
        'pie_labels'          : pie_labels,
        'pie_data'            : pie_data,
        'unit_labels'         : unit_labels_json,
        'attendance_datasets' : attendance_datasets_json,
    }

    return render(request, 'trainer/staff_dashboard.html', context)