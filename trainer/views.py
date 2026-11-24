import os
import tempfile
from django.shortcuts import render, redirect
from django.utils.html import escape
import re
import trainer
from .models import LearningGuide, Attendance
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from bs4 import BeautifulSoup
import os, tempfile
from django.shortcuts import render, redirect
from django.utils.html import escape
from bs4 import BeautifulSoup
from django.shortcuts import render
from django.utils.timezone import now
import json
import google.generativeai as genai
from django.shortcuts import render, get_object_or_404
from hod.models import TrainerAssighnment, CourseUnitsData
from datetime import datetime


def iter_block_items(parent):
    """Yield paragraphs and tables in order from a docx element."""
    if hasattr(parent, "element") and hasattr(parent.element, "body"):
        parent_elm = parent.element.body  # Document
    else:
        parent_elm = parent._tc  # Table cell
    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)


def runs_to_html(paragraph):
    """Convert runs (bold/italic/underline) into inline HTML."""
    parts = []
    for run in paragraph.runs:
        text = escape(run.text)
        if not text:
            continue
        if run.bold:
            text = f"<strong>{text}</strong>"
        if run.italic:
            text = f"<em>{text}</em>"
        if run.underline:
            text = f"<u>{text}</u>"
        parts.append(text)
    return "".join(parts)


def get_span_attrs(cell):
    """Extract colspan / rowspan info from a table cell XML."""
    colspan = 1
    rowspan = 1

    # check for gridSpan (colspan)
    gridspan = cell._element.xpath(".//w:gridSpan")
    if gridspan:
        colspan = int(
            gridspan[0].get(
                "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val"
            )
        )

    # check for vMerge (rowspan)
    vmerge = cell._element.xpath(".//w:vMerge")
    if vmerge and vmerge[0].get(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val"
    ) != "restart":
        rowspan = 0  # continuation of previous cell
    elif vmerge:
        rowspan = 1  # start of a vertical merge

    return colspan, rowspan


def table_to_html(table):
    """Convert a docx Table into HTML <table> with merged cells preserved."""
    html = '<table class="custom-table" style="width:100%; border-collapse:collapse;">'
    for row in table.rows:
        html += "<tr>"
        for cell in row.cells:
            colspan, rowspan = get_span_attrs(cell)
            if rowspan == 0:  # skip continuation of vertical merge
                continue

            cell_html = ""
            for block in iter_block_items(cell):
                if isinstance(block, Paragraph):
                    text = runs_to_html(block)
                    if text.strip():
                        cell_html += f"<p>{text}</p>"
                elif isinstance(block, Table):
                    cell_html += table_to_html(block)

            span_attr = ""
            if colspan > 1:
                span_attr += f' colspan="{colspan}"'
            if rowspan > 1:
                span_attr += f' rowspan="{rowspan}"'

            html += f"<td{span_attr}>{cell_html}</td>"
        html += "</tr>"
    html += "</table>"
    return html


def docx_to_html(path, header_paragraphs=4):
    """Convert DOCX → HTML (paragraphs + tables), optionally wrap top paragraphs in a header div."""
    doc = Document(path)
    html = ""
    paragraph_count = 0
    header_html = ""
    
    for block in iter_block_items(doc):
        if isinstance(block, Paragraph):
            text = runs_to_html(block)
            if text.strip():
                paragraph_count += 1
                if paragraph_count <= header_paragraphs:
                    # accumulate header paragraphs
                    header_html += f"<p>{text}</p>\n"
                else:
                    html += f"<p>{text}</p>\n"
        elif isinstance(block, Table):
            html += table_to_html(block) + "\n"

    # Wrap header paragraphs in a div
    if header_html:
        header_html = f'<div class="doc-header">\n{header_html}</div>\n'

    # Combine header + rest
    return header_html + html



def clean_html_with_bs4(html_content):
    """Optional cleanup: remove duplicate table cell contents using BeautifulSoup."""
    soup = BeautifulSoup(html_content, "html.parser")

    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            seen = set()
            for cell in row.find_all(["td", "th"]):
                text = cell.get_text(strip=True)
                if text in seen:
                    cell.decompose()  # remove duplicate cell
                else:
                    seen.add(text)

    return str(soup)


def parse_expectations(raw_text):
    """
    Parse learning expectations, handling numbered hierarchy.
    
    Rules:
    - If a numbered item (e.g., 1.2) has deeper-numbered children (1.2.1, 1.2.2, ...),
      bold it as a heading and keep it along with children.
    - Non-heading items and all children are kept as learning expectations.
    - Preserve line wrapping (non-numbered lines following a numbered line).
    """
    lines = [l.rstrip() for l in raw_text.splitlines() if l.strip()]
    if not lines:
        return []

    numbered_re = re.compile(r"^(?P<num>\d+(?:\.\d+)*)[\.\)\s]+(?P<text>.*)$")
    
    # Parse all lines
    parsed = []
    for line in lines:
        m = numbered_re.match(line)
        if m:
            num = m.group("num")
            text = m.group("text")
            parsed.append({
                "original": line,
                "num": num,
                "depth": num.count("."),
                "text": text,
                "is_numbered": True,
            })
        else:
            parsed.append({
                "original": line,
                "num": None,
                "depth": None,
                "text": line,
                "is_numbered": False,
            })

    # Merge non-numbered continuation lines into the previous numbered item
    merged = []
    for item in parsed:
        if item["num"] is None:
            if merged:
                prev = merged[-1]
                prev["original"] = f"{prev['original']} {item['text']}".strip()
                prev["text"] = f"{prev['text']} {item['text']}".strip()
            continue
        merged.append(item)
    parsed = merged
    
    # Mark items that have immediate children
    has_children = set()
    for idx, item in enumerate(parsed):
        if item["num"] is None:
            continue
        parent_prefix = item["num"] + "."
        for later_item in parsed[idx + 1:]:
            if later_item["num"] and later_item["num"].startswith(parent_prefix):
                # Check if it's an immediate child (one level deeper)
                parent_depth = item["depth"]
                child_depth = later_item["depth"]
                if child_depth == parent_depth + 1:
                    has_children.add(item["num"])
                    break
    
    # Build expectations: include all items, bolding parents with children
    expectations = []
    
    for item in parsed:
        if item["num"] is None:
            # Non-numbered line: append to previous expectation if exists
            if expectations:
                expectations[-1] = f"{expectations[-1]} {item['text']}".strip()
            continue
        
        # If this number has children, bold it as a heading
        if item["num"] in has_children:
            expectations.append(f"<strong>{item['original']}</strong>")
        else:
            expectations.append(item["original"])
    
    return expectations


def _is_parent_expectation(expectation):
    """Return True for expectations formatted as parent headings."""
    if not isinstance(expectation, str):
        return False
    exp = expectation.strip()
    return exp.startswith("<strong>") and exp.endswith("</strong>")


def _group_expectations_by_parent(flat_expectations):
    """Group flat expectations so each parent heading begins a new session boundary."""
    groups = []
    current = []
    for item in flat_expectations:
        if _is_parent_expectation(item["expectation"]) and current:
            groups.append(current)
            current = [item]
        else:
            current.append(item)

    if current:
        groups.append(current)

    return groups


def _allocate_groups_to_sessions(groups, sessions_to_create):
    """Allocate grouped expectations across the requested number of sessions."""
    import random

    def _expand_groups(groups, min_children=1, max_children=2):
        """Expand groups so that parent groups may be split into multiple chunks.

        Each resulting chunk is a list of flat expectation dicts. If a group
        starts with a parent heading, that parent will be prepended to every
        chunk produced for its children so each chunk/session begins with the
        parent heading.
        """
        chunks = []
        for group in groups:
            if not group:
                continue
            first = group[0]
            # If the first item is a parent heading, split its children
            if _is_parent_expectation(first["expectation"]):
                children = group[1:]
                if not children:
                    chunks.append([first])
                    continue
                idx = 0
                while idx < len(children):
                    take = random.randint(min_children, max_children)
                    take = min(take, len(children) - idx)
                    chunk_children = children[idx: idx + take]
                    # Each chunk/session should begin with the parent heading
                    chunk = [first] + chunk_children
                    chunks.append(chunk)
                    idx += take
            else:
                # Non-parent groups stay as single chunks
                chunks.append(list(group))
        return chunks

    # Expand parent groups into session-sized chunks with randomized child counts
    expanded_chunks = _expand_groups(groups)
    total_expectations = sum(len(chunk) for chunk in expanded_chunks)
    if sessions_to_create <= 0 or total_expectations == 0:
        # return expanded chunks as-is
        return expanded_chunks

    base_count = total_expectations // sessions_to_create
    remainder = total_expectations % sessions_to_create
    targets = [base_count + (1 if i < remainder else 0) for i in range(sessions_to_create)]

    sessions = []
    current = []
    current_count = 0
    session_index = 0

    for chunk in expanded_chunks:
        chunk_size = len(chunk)

        if current and current_count + chunk_size > targets[session_index] and session_index < sessions_to_create - 1:
            sessions.append(current)
            current = []
            current_count = 0
            session_index += 1

        current.extend(chunk)
        current_count += chunk_size

        if session_index < sessions_to_create - 1 and current_count >= targets[session_index]:
            sessions.append(current)
            current = []
            current_count = 0
            session_index += 1

    if current:
        sessions.append(current)

    return sessions


def generate_learning_plan(request):
    GEMINI_API_KEY = "AIzaSyCgO3JupI-_EA1R4q5JGPTypvdFHfK9NBQ"
    genai.configure(api_key=GEMINI_API_KEY)

    def fetch_ai_session_details(title, expectations):
        joined_expectations = "; ".join(expectations)
        prompt = f"""
        Generate structured lesson plan details for a session with:
        Title: {title}
        Expectations: {joined_expectations}
        Return a valid JSON object with the keys:
        trainer_activities, trainee_activities, resources, assessments
        """
        def normalize(value):
            if isinstance(value, list):
                if all(isinstance(v, dict) for v in value):
                    return [f"{v.get('activity', '')}: {v.get('description', '')}" for v in value]
                return [str(v) for v in value]
            elif isinstance(value, str):
                return [value]
            return [str(value)]

        try:
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt)
            content = response.text.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[len("json"):].strip()
            parsed = json.loads(content)
            return {
                "trainer_activities": normalize(parsed.get("trainer_activities", "")),
                "trainee_activities": normalize(parsed.get("trainee_activities", "")),
                "resources": normalize(parsed.get("resources", "")),
                "assessments": normalize(parsed.get("assessments", "")),
            }
        except Exception as e:
            print("Gemini API failed:", str(e))
            return {
                "trainer_activities": ["Guide learners through examples, supervise tasks."],
                "trainee_activities": ["Engage in group work, ask questions, practice hands-on tasks."],
                "resources": ["Computers, projector, whiteboard, course notes."],
                "assessments": ["Practical exercise, quiz, oral Q&A."]
            }

    from .models import OSData
    from home.models import TrainerData
    from hod.models import TrainerAssighnment


    staff_id = request.session.get('staff_id')
    trainer = TrainerData.objects.filter(id=staff_id).first() if staff_id else None

    # Build CourseUnitsData options for dropdown filtered to this trainer
    from hod.models import CourseUnitsData
    units_options = []
    if trainer:
        units_qs = CourseUnitsData.objects.filter(
            trainer_assignments__trainer=trainer
        ).select_related('curriculum__course').distinct()
    else:
        units_qs = CourseUnitsData.objects.none()

    for unit in units_qs:
        course_obj = unit.curriculum.course if unit.curriculum else None
        class_slot = ""
        if trainer and unit:
            assignment = TrainerAssighnment.objects.filter(trainer=trainer, course_units=unit).select_related('class_slot').first()
            if assignment and assignment.class_slot:
                class_slot = assignment.class_slot.slot

        units_options.append({
            'id': unit.id,
            'unit_competence': unit.unit_of_competency or "",
            'unit_code': unit.isced_unit_code or unit.tvet_cdacc_unit_code or "",
            'course': course_obj.name if course_obj else "",
            'level': course_obj.level if course_obj else "",
            'class_slot': class_slot,
            'total_time': unit.total_time or "",
        })

    if request.method == "POST":
        # -------------------------------
        # Collect metadata
        # -------------------------------
        unit_competence = request.POST.get("unit_competence", "").strip()
        unit_code = request.POST.get("unit_code", "").strip()
        unit_id = request.POST.get("unit_id")
        trainer_name = request.POST.get("trainer_name", "").strip()
        course = request.POST.get("course", "").strip()
        institution = request.POST.get("institution", "").strip()
        level = request.POST.get("level", "").strip()
        date_preparation = request.POST.get("date_preparation", "").strip()
        date_revision = request.POST.get("date_revision", "").strip()
        term = request.POST.get("term", "").strip()
        trainees = request.POST.get("trainees", "").strip()
        class_name = request.POST.get("class_name", "").strip()

        try:
            total_time = int(request.POST.get("total_time", 0))
        except (TypeError, ValueError):
            total_time = 0

        # If CourseUnitsData unit selected, use its stored values
        if unit_id:
            unit = CourseUnitsData.objects.select_related('curriculum__course').filter(id=unit_id).first()
            if unit:
                unit_competence = unit.unit_of_competency or unit_competence
                unit_code = unit.isced_unit_code or unit.tvet_cdacc_unit_code or unit_code
                course_obj = unit.curriculum.course if unit.curriculum else None
                if course_obj:
                    course = course_obj.name or course
                    level = course_obj.level or level

        # -------------------------------
        # Collect learning outcomes
        # -------------------------------
        outcomes = []
        idx = 0
        while True:
            title_key = f"outcomes[{idx}][title]"
            expect_key = f"outcomes[{idx}][expectations]"
            if title_key not in request.POST:
                break
            title = request.POST.get(title_key, "").strip()
            expectations_raw = request.POST.get(expect_key, "").strip()
            expectations = parse_expectations(expectations_raw)
            if not expectations and expectations_raw:
                expectations = [expectations_raw]
            outcomes.append({
                "title": title or "Untitled Outcome",
                "expectations": expectations,
            })
            idx += 1

        # -------------------------------
        # Flatten expectations
        # -------------------------------
        flat_expectations = []
        for outcome in outcomes:
            for exp in outcome["expectations"]:
                flat_expectations.append({
                    "title": outcome["title"],
                    "expectation": exp
                })

        total_expectations = len(flat_expectations)
        grouped_expectations = _group_expectations_by_parent(flat_expectations)

        # -------------------------------
        # Sessions config
        # -------------------------------
        HOURS_PER_SESSION = 2
        SESSIONS_PER_WEEK = 2
        ASSESSMENT_INTERVAL_WEEKS = 4  # assessment after every 4 weeks

        total_sessions = max(1, total_time // HOURS_PER_SESSION) if total_time > 0 else max(1, total_expectations)
        # Always create sessions based on total hours (2 hrs per session)
        sessions_to_create = total_sessions

        sessions = []

        # Week 1: Reporting and Admission
        sessions.append({
            "week": 1,
            "session_no": "",
            "title": "REPORTING AND ADMISSION",
            "trainer_activities": [],
            "trainee_activities": [],
            "resources": [],
            "assessments": [],
            "special": True
        })

        # If expectations are fewer than sessions, repeat sequentially to fill
        if sessions_to_create > 0 and total_expectations > 0:
            if total_expectations < sessions_to_create:
                extra = sessions_to_create - total_expectations
                idx = 0
                while extra > 0:
                    flat_expectations.insert(idx + 1, flat_expectations[idx])
                    idx += 2
                    if idx >= len(flat_expectations):
                        idx = 0
                    extra -= 1
                total_expectations = len(flat_expectations)
                grouped_expectations = _group_expectations_by_parent(flat_expectations)

        # Preserve original expectation order so the first learning outcome stays first.
        # Previously this was shuffled randomly when there were more expectations than sessions.

        # Generate normal sessions & insert assessment dynamically
        if sessions_to_create > 0:
            session_chunks = _allocate_groups_to_sessions(grouped_expectations, sessions_to_create)
            current_week = 2
            outcome_seen = {}
            outcome_number = 0

            for s_idx, chunk in enumerate(session_chunks):
                expectations_for_session = [c["expectation"] for c in chunk]
                outcome_title = chunk[0]["title"] if chunk else f"Outcome {s_idx+1}"

                if outcome_title not in outcome_seen:
                    outcome_number += 1
                    outcome_seen[outcome_title] = outcome_number

                session_no = s_idx + 1
                if expectations_for_session:
                    ai_data = fetch_ai_session_details(outcome_title, expectations_for_session)
                else:
                    ai_data = {
                        "trainer_activities": [],
                        "trainee_activities": [],
                        "resources": [],
                        "assessments": [],
                    }

                sessions.append({
                    "week": current_week,
                    "session_no": session_no,
                    "title": f"Session {session_no}",
                    "learning_outcome": outcome_title,
                    "outcome_no": outcome_seen[outcome_title],
                    "expectations": expectations_for_session,
                    **ai_data,
                    "special": False
                })

                if session_no % SESSIONS_PER_WEEK == 0:
                    current_week += 1

                if (current_week - 1) % ASSESSMENT_INTERVAL_WEEKS == 0 and (
                    session_no % SESSIONS_PER_WEEK == 0 or s_idx == len(session_chunks) - 1
                ):
                    sessions.append({
                        "week": current_week,
                        "session_no": "",
                        "title": "ASSESSMENT",
                        "trainer_activities": [],
                        "trainee_activities": [],
                        "resources": [],
                        "assessments": [],
                        "special": True
                    })
                    current_week += 1

        # -------------------------------
        # Save generated guide in DB
        # -------------------------------
        guide = LearningGuide.objects.create(
            unit_code=unit_code,
            unit_competence=unit_competence,
            trainer_name=trainer_name,
            course=course,
            institution=institution,
            level=level,
            date_preparation=date_preparation or None,
            date_revision=date_revision or None,
            term=term,
            trainees=trainees,
            class_name=class_name,
            total_time=total_time,
            sessions_json=sessions
        )

        context = {
            "unit_competence": unit_competence,
            "unit_code": unit_code,
            "trainer_name": trainer_name,
            "course": course,
            "institution": institution,
            "level": level,
            "date_preparation": date_preparation,
            "date_revision": date_revision,
            "term": term,
            "trainees": trainees,
            "class_name": class_name,
            "total_time": total_time,
            "total_sessions": total_sessions,
            "sessions_created": len(sessions),
            "sessions": sessions,
            "guide_saved": True  # Flag to auto-display success
        }

        return render(request, "trainer/learning_plan.html", context)

    return render(request, "trainer/generate_learning_plan.html", {
        "trainer_name_prefill": f"{trainer.first_name} {trainer.last_name}" if trainer else "",
        "units_options": units_options,
    })








def learning_guides_list(request):
    guides = LearningGuide.objects.all()
    return render(request, "trainer/learning_guides_list.html", {"guides": guides})

import json
from django.shortcuts import render, get_object_or_404
from .models import LearningGuide

import ast
from django.shortcuts import get_object_or_404, render

def view_learning_guide(request, pk):
    guide = get_object_or_404(LearningGuide, pk=pk)

    # Convert string representation of list to Python list
    if guide.sessions_json:
        try:
            sessions = ast.literal_eval(guide.sessions_json)
        except Exception as e:
            sessions = []
            print("Error parsing sessions_json:", e)
    else:
        sessions = []

    return render(request, "trainer/view_learning_plan.html", {
        "guide": guide,
        "sessions": sessions
    })

import ast
import json
from django.shortcuts import get_object_or_404, render, redirect
from .models import LearningGuide, SavedSessionPlan

def generate_session_plan(request):
    guides = LearningGuide.objects.all()

    # Prepare units dropdown
    units = []
    for guide in guides:
        if guide.unit_competence:
            try:
                sessions = ast.literal_eval(guide.sessions_json or "[]")
            except Exception as e:
                print("Error parsing sessions_json for guide", guide.id, e)
                sessions = []

            units.append({
                'id': guide.id,
                'unit_competence': guide.unit_competence,
                'sessions': sessions
            })

    # Selected guide for AJAX reload
    selected_guide_id = request.GET.get('unit_id')
    selected_sessions = []

    if selected_guide_id:
        guide = get_object_or_404(LearningGuide, id=selected_guide_id)

        try:
            sessions = ast.literal_eval(guide.sessions_json or "[]")
        except Exception as e:
            print("Error parsing sessions_json:", e)
            sessions = []

        for s in sessions:
            if not s.get('special', False):
                selected_sessions.append({
                    'title': s.get('title', ''),
                    'expectations': json.dumps(s.get('expectations', [])),  # <-- JSON encode
                    'trainer_activities': s.get('trainer_activities', []),
                    'trainee_activities': s.get('trainee_activities', []),
                    'resources': s.get('resources', [])
                })

    # ----------------------------------------------------------
    # SAVE SESSION PLAN
    # ----------------------------------------------------------
    if request.method == 'POST':
        guide_id = request.POST.get('unit_id')
        session_title = request.POST.get('session_title')
        presenter_name = request.POST.get('presenter_name')
        date = request.POST.get('date')
        duration = request.POST.get('duration')
        bridge_in = request.POST.get('bridge_in')
        pre_assessment = request.POST.get('pre_assessment')
        post_assessment = request.POST.get('post_assessment')
        summary = request.POST.get('summary')
        time = request.POST.getlist('time[]')

        # MULTIPLE EXPECTATIONS
        expectations = request.POST.getlist('expectation[]')
        expectation_str = "\n".join([e.strip() for e in expectations if e.strip()])

        # Activity Lists
        trainer_activities = request.POST.getlist('trainer_activities[]')
        trainee_activities = request.POST.getlist('trainee_activities[]')
        resources = request.POST.getlist('resources[]')

        # Clean strings
        trainer_str = '\n'.join([t.strip() for t in trainer_activities if t.strip()])
        trainee_str = '\n'.join([t.strip() for t in trainee_activities if t.strip()])
        resources_str = '\n'.join([r.strip() for r in resources if r.strip()])
        time_str = '\n'.join([ti.strip() for ti in time if ti.strip()])

        guide = get_object_or_404(LearningGuide, id=guide_id)

        SavedSessionPlan.objects.create(
            unit=guide,
            session_title=session_title,
            presenter_name=presenter_name,
            date=date,
            duration=duration,
            bridge_in=bridge_in,
            pre_assessment=pre_assessment,
            post_assessment=post_assessment,
            summary=summary,
            expectation=expectation_str,
            time=time_str,
            trainer_activities=trainer_str,
            trainee_activities=trainee_str,
            resources=resources_str
        )

        return redirect("session_plans_list")

    return render(request, 'trainer/generate_session_plan.html', {
        'guides': guides,
        'units': units,
        'selected_sessions': selected_sessions,
        'selected_guide_id': selected_guide_id
    })



def session_plans_list(request):
    plans = SavedSessionPlan.objects.select_related('unit').all().order_by('-date')
    return render(request, 'trainer/session_plans_list.html', {'plans': plans})


def view_session_plan(request, plan_id):
    plan = get_object_or_404(SavedSessionPlan, id=plan_id)

    trainer_activities = plan.trainer_activities.splitlines() if plan.trainer_activities else []
    trainee_activities = plan.trainee_activities.splitlines() if plan.trainee_activities else []
    resources = plan.resources.splitlines() if plan.resources else []
    time = plan.time.splitlines() if plan.time else []

    # Split expectations too (NEW)
    expectations = plan.expectation.splitlines() if plan.expectation else []

    participatory_rows = list(zip(time, trainer_activities, trainee_activities, resources))

    return render(request, 'trainer/view_session_plan.html', {
        'plan': plan,
        'participatory_rows': participatory_rows,
        'expectations': expectations
    })



def sp(request):
    return render(request, 'sp.html') #sp.html


def session_plan(request, session_no):
    # For simplicity, assume one guide; otherwise filter by course/unit/etc.
    guide = get_object_or_404(LearningGuide, pk=1)  

    # Parse sessions JSON
    sessions = guide.sessions  # uses the property you defined

    # Find the specific session by session_no
    session = next((s for s in sessions if s.get('session_no') == session_no), None)

    if not session:
        return render(request, 'session_not_found.html', {'session_no': session_no})

    return render(request, 'session_plan.html', {'session': session}) #session_plan



from django.shortcuts import render
from django.contrib.auth.decorators import login_required
# from assignments.models import Assignment, Submission
# from schedule.models import Session, Timetable
# from trainee.models import Trainee
from home.models import Trainee, Assignment, Submission, Session, Timetable
from django.utils import timezone




@login_required
def trainer_assessment_dashboard(request):
    # Get trainer profile
    # trainer = trainer(request.user)
    trainer_name = trainer
    
    # Get assignments created by this trainer
    assignments = Assignment.objects.filter(trainer=trainer_name)
    
    # Get submissions for trainer's assignments
    submissions = Submission.objects.filter(assignment__trainer=trainer)
    
    # Statistics
    context = {
        # Counts for quick stats boxes
        'assignments_count': assignments.filter(is_active=True).count(),
        'pending_submissions': submissions.filter(is_graded=False).count(),
        'upcoming_sessions': Session.objects.filter(
            trainer=trainer, 
            start_time__gte=timezone.now()
        ).count(),
        'total_trainees': trainer.trainees.count(),
        
        # Recent data
        'recent_assignments': assignments.order_by('-created_at')[:5],
        'recent_submissions': submissions.order_by('-submitted_at')[:5],
        'upcoming_sessions_list': Session.objects.filter(
            trainer=trainer,
            start_time__gte=timezone.now()
        ).order_by('start_time')[:5],
        
        # Additional stats
        'ungraded_count': submissions.filter(is_graded=False).count(),
        'completion_rate': calculate_completion_rate(trainer),
        'grading_progress': calculate_grading_progress(trainer),
        'average_score': calculate_average_score(trainer),
    }
    
    return render(request, 'trainer/assessment.html', context)

def calculate_completion_rate(trainer):
    """Calculate assignment completion rate for trainer's trainees"""
    total_assignments = Assignment.objects.filter(trainer=trainer).count()
    total_expected = total_assignments * trainer.trainees.count()
    if total_expected == 0:
        return 0
    total_submitted = Submission.objects.filter(
        assignment__trainer=trainer
    ).count()
    return round((total_submitted / total_expected) * 100, 1)

def calculate_grading_progress(trainer):
    """Calculate grading progress percentage"""
    total_submissions = Submission.objects.filter(
        assignment__trainer=trainer
    ).count()
    if total_submissions == 0:
        return 0
    graded_submissions = Submission.objects.filter(
        assignment__trainer=trainer,
        is_graded=True
    ).count()
    return round((graded_submissions / total_submissions) * 100, 1)

def calculate_average_score(trainer):
    """Calculate average score for graded submissions"""
    graded_submissions = Submission.objects.filter(
        assignment__trainer=trainer,
        is_graded=True
    )
    if not graded_submissions:
        return 0
    total_score = sum(sub.grade for sub in graded_submissions)
    return round(total_score / graded_submissions.count(), 1)

# ================================================================
# TRAINER PORTFOLIO ASSESSMENT VIEWS
# ================================================================
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from home.models import (
    EvidenceArtifact, Assessment, Competency,
    TrainerData, Trainee, Course, PortfolioShare, PortfolioView
)
from django.contrib.auth import get_user_model


def get_trainer_from_session(request):
    """
    Helper — gets the TrainerData record for whoever is logged in.
    Works for both staff_login session and Django auth.
    """
    # try session-based login first (your existing staff_login)
    staff_id = request.session.get('staff_id')
    staff_type = request.session.get('staff_type')

    if staff_id and staff_type == 'trainer':
        try:
            return TrainerData.objects.get(id=staff_id)
        except TrainerData.DoesNotExist:
            return None

    # fallback — try matching by email to logged-in Django user
    if request.user.is_authenticated:
        try:
            return TrainerData.objects.get(email=request.user.email)
        except TrainerData.DoesNotExist:
            return None

    return None


# def get_trainer_course_ids(trainer):
#     """
#     Helper — returns list of Course IDs this trainer teaches.
#     trainer.courses is stored as comma-separated IDs e.g. "1,2,5"
#     """
#     if not trainer or not trainer.courses:
#         return []
#     return [
#         int(c.strip())
#         for c in trainer.courses.split(',')
#         if c.strip().isdigit()
#     ]

def get_trainer_unit_ids(trainer):
    """
    Returns list of Unit IDs this trainer is assigned to teach.
    """
    from home.models import Unit
    return list(
        Unit.objects.filter(trainer=trainer).values_list('id', flat=True)
    )

def trainer_portfolio_overview(request):
    """
    View 1 — Trainer sees all trainees who have evidence
    tagged to units they teach.
    """
    trainer = get_trainer_from_session(request)

    if not trainer:
        messages.error(request, "You must be logged in as a trainer.")
        return redirect('staff_login')

    unit_ids = get_trainer_unit_ids(trainer)

    if not unit_ids:
        return render(request, 'trainer/portfolio_overview.html', {
            'trainer': trainer,
            'trainee_summaries': [],
            'no_units': True,
        })

    # get all evidence artifacts for units this trainer teaches
    evidence_qs = EvidenceArtifact.objects.filter(
        unit__id__in=unit_ids
    ).select_related('trainee', 'unit')

    # group by trainee
    trainee_map = {}
    for ev in evidence_qs:
        trainee_id = ev.trainee.id
        if trainee_id not in trainee_map:
            trainee_map[trainee_id] = {
                'trainee': ev.trainee,
                'units': {},
            }
        unit_name = ev.unit.name if ev.unit else 'Unknown'
        if unit_name not in trainee_map[trainee_id]['units']:
            trainee_map[trainee_id]['units'][unit_name] = {
                'fa1': 0, 'fa2': 0, 'fa3': 0, 'final': 0,
                'assessed': 0, 'total': 0,
            }

        stage = ev.assessment_stage or ''
        if stage in ['fa1', 'fa2', 'fa3', 'final']:
            trainee_map[trainee_id]['units'][unit_name][stage] += 1
        trainee_map[trainee_id]['units'][unit_name]['total'] += 1

        # count how many have been assessed
        if Assessment.objects.filter(evidence=ev).exists():
            trainee_map[trainee_id]['units'][unit_name]['assessed'] += 1

    trainee_summaries = list(trainee_map.values())

    return render(request, 'trainer/portfolio_overview.html', {
        'trainer': trainer,
        'trainee_summaries': trainee_summaries,
        'no_units': False,
    })


def trainer_review_trainee(request, trainee_user_id):
    """
    View 2 — Trainer opens one trainee's evidence
    for the units they teach. Evidence grouped by assessment stage.
    """
    trainer = get_trainer_from_session(request)

    if not trainer:
        messages.error(request, "You must be logged in as a trainer.")
        return redirect('staff_login')

    unit_ids = get_trainer_unit_ids(trainer)
    User = get_user_model()
    trainee_user = get_object_or_404(User, id=trainee_user_id)

    # get evidence for this trainee scoped to trainer's units
    evidence_qs = EvidenceArtifact.objects.filter(
        trainee=trainee_user,
        unit__id__in=unit_ids
    ).select_related('unit').order_by('unit__name', 'assessment_stage')

    # group by stage
    stages = {
        'fa1': {'label': 'Formative Assessment 1', 'items': []},
        'fa2': {'label': 'Formative Assessment 2', 'items': []},
        'fa3': {'label': 'Formative Assessment 3', 'items': []},
        'final': {'label': 'Final Assessment', 'items': []},
        '': {'label': 'Untagged', 'items': []},
    }

    for ev in evidence_qs:
        stage_key = ev.assessment_stage or ''
        if stage_key not in stages:
            stage_key = ''

        # attach existing assessment if any
        existing = Assessment.objects.filter(
            evidence=ev
        ).order_by('-assessment_date').first()

        stages[stage_key]['items'].append({
            'evidence': ev,
            'existing_assessment': existing,
        })

    # remove empty stages
    grouped = {k: v for k, v in stages.items() if v['items']}

    return render(request, 'trainer/review_trainee.html', {
        'trainer': trainer,
        'trainee_user': trainee_user,
        'grouped': grouped,
        'unit_ids': unit_ids,
    })


def submit_assessment(request):
    """
    View 3 — Receives POST from shared_view.html
    when trainer submits their verdict on a piece of evidence.
    Creates Assessment records and logs the view.
    """
    if request.method != 'POST':
        return redirect('trainer:trainer_portfolio_overview')

    trainer = get_trainer_from_session(request)

    # also accept Django-auth trainers
    if not trainer and request.user.is_authenticated:
        try:
            trainer = TrainerData.objects.get(email=request.user.email)
        except TrainerData.DoesNotExist:
            pass

    if not trainer:
        messages.error(request, "You must be logged in as a trainer.")
        return redirect('staff_login')

    User = get_user_model()

    # get the share token so we can redirect back correctly
    share_token = request.POST.get('share_token')

    # overall fields
    overall_status = request.POST.get('overall_status', 'under_review')
    overall_feedback = request.POST.get('overall_feedback', '')
    score = request.POST.get('score') or None
    max_score = request.POST.get('max_score') or 100

    # find assessor User record — create one for trainer if needed
    assessor, _ = User.objects.get_or_create(
        username=trainer.staff_number,
        defaults={
            'first_name': trainer.first_name,
            'last_name': trainer.last_name,
            'email': trainer.email or '',
        }
    )

    # get all evidence IDs submitted (individual verdicts per evidence)
    evidence_ids = request.POST.getlist('evidence_ids')

    assessments_created = 0

    for ev_id in evidence_ids:
        try:
            evidence = EvidenceArtifact.objects.get(id=ev_id)
        except EvidenceArtifact.DoesNotExist:
            continue

        # per-evidence status and feedback from hidden inputs
        ev_status = request.POST.get(
            f'evidence_status_{ev_id}', overall_status
        )
        ev_feedback = request.POST.get(
            f'evidence_feedback_{ev_id}', overall_feedback
        )

        # update existing assessment or create new one
        assessment, created = Assessment.objects.update_or_create(
            evidence=evidence,
            assessor=assessor,
            defaults={
                'status': ev_status,
                'feedback': ev_feedback,
                'comments': overall_feedback,
                'score': score,
                'max_score': max_score,
                'assessment_date': timezone.now(),
            }
        )
        assessments_created += 1

    # log the portfolio view
    if share_token:
        try:
            share = PortfolioShare.objects.get(token=share_token)
            PortfolioView.objects.create(
                share=share,
                viewed_by=f"{trainer.first_name} {trainer.last_name} (Trainer)",
                unit_seen=share.unit if share.scope == 'unit' else None,
            )
        except PortfolioShare.DoesNotExist:
            pass

    messages.success(
        request,
        f"Assessment submitted successfully. "
        f"{assessments_created} evidence item(s) assessed."
    )

    # redirect back to shared view if token exists
    if share_token:
        from django.urls import reverse
        return redirect(
            reverse('trainee:portfolio_shared', kwargs={'token': share_token})
        )

    return redirect('trainer_portfolio_overview')


def trainer_assessment_history(request):
    """
    View 4 — Trainer sees all assessments they have
    previously submitted, filterable by trainee and unit.
    """
    trainer = get_trainer_from_session(request)

    if not trainer:
        messages.error(request, "You must be logged in as a trainer.")
        return redirect('staff_login')

    User = get_user_model()

    # get assessor User record for this trainer
    try:
        assessor = User.objects.get(username=trainer.staff_number)
    except User.DoesNotExist:
        assessor = None

    assessments = Assessment.objects.none()

    if assessor:
        assessments = Assessment.objects.filter(
            assessor=assessor
        ).select_related(
            'evidence', 'evidence__trainee', 'evidence__unit'
        ).order_by('-assessment_date')

    # filters
    unit_filter = request.GET.get('unit', '')
    status_filter = request.GET.get('status', '')

    if unit_filter:
        assessments = assessments.filter(evidence__unit__id=unit_filter)

    if status_filter:
        assessments = assessments.filter(status=status_filter)

    # get units this trainer teaches for filter dropdown
    unit_ids = get_trainer_unit_ids(trainer)
    units = Course.objects.filter(id__in=unit_ids)

    return render(request, 'trainer/assessment_history.html', {
        'trainer': trainer,
        'assessments': assessments,
        'units': units,
        'unit_filter': unit_filter,
        'status_filter': status_filter,
        'status_choices': Assessment.STATUS_CHOICES,
    })

def _get_logged_in_trainer(request):
    if request.session.get('staff_type') != 'trainer':
        return None
    trainer_id = request.session.get('staff_id')
    if not trainer_id:
        return None
    return TrainerData.objects.select_related('department').filter(id=trainer_id).first()

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


def trainer_all_courses(request):
    trainer = _get_logged_in_trainer(request)
    if not trainer:
        return redirect('staff_login')

    course_ids = _parse_course_ids(trainer.courses)
    courses = Course.objects.select_related('department').filter(id__in=course_ids).order_by('name')

    course_data = []
    for course in courses:
        course_data.append({
            'id': course.id,
            'name': course.name,
            'department': course.department.name if course.department else "N/A",
            'level': course.level if hasattr(course, 'level') else "N/A",
        })

    return render(request, 'trainer/all_courses.html', {'courses': course_data})

def trainer_os_outcomes_api(request, unit_id):
    from hod.models import CourseUnitsData, CurriculumLearningOutcome
    from django.http import JsonResponse

    unit = CourseUnitsData.objects.filter(id=unit_id).first()
    if not unit:
        return JsonResponse({'outcomes': []})

    outcomes = CurriculumLearningOutcome.objects.filter(curriculum_data=unit).order_by('id')
    return JsonResponse({
        'outcomes': [
            {
                'title': o.learning_outcome or '',
                'expectations': o.learning_expectations or ''
            }
            for o in outcomes
        ]
    })


def trainer_my_classes(request):
    """View trainer's assigned classes"""
    from home.models import TrainerData
    from hod.models import TrainerAssighnment
    
    staff_id = request.session.get('staff_id')
    assignments = []
    
    if staff_id:
        try:
            trainer = TrainerData.objects.get(id=staff_id)
            assignments = TrainerAssighnment.objects.filter(
                trainer=trainer
            ).select_related('course', 'class_slot').prefetch_related('course_units')
        except TrainerData.DoesNotExist:
            pass
    
    context = {
        'assignments': assignments
    }
    return render(request, 'trainer/my_classes.html', context)

def trainer_course_units(request, assignment_id):
    """View units for a trainer's assigned class"""
    from home.models import TrainerData
    from hod.models import TrainerAssighnment
    
    staff_id = request.session.get('staff_id')
    assignment = None
    units = []
    
    if staff_id:
        try:
            trainer = TrainerData.objects.get(id=staff_id)
            assignment = TrainerAssighnment.objects.get(
                id=assignment_id,
                trainer=trainer
            )
            # Fetch units for this specific assignment/class.
            units = list(assignment.course_units.all())
        except (TrainerData.DoesNotExist, TrainerAssighnment.DoesNotExist):
            pass
    
    context = {
        'assignment': assignment,
        'units': units
    }
    return render(request, 'trainer/course_units.html', context)

def trainer_view_curriculum(request, assignment_id, unit_id):
    """View extracted curriculum learning outcomes for a unit in an assignment."""
    from home.models import TrainerData
    from hod.models import TrainerAssighnment

    staff_id = request.session.get("staff_id")
    if not staff_id:
        return redirect("trainer_my_classes")

    try:
        trainer = TrainerData.objects.get(id=staff_id)
        assignment = TrainerAssighnment.objects.select_related("course", "class_slot").get(
            id=assignment_id,
            trainer=trainer,
        )
        unit = assignment.course_units.get(id=unit_id)
        outcomes = unit.learning_outcomes.all().order_by("id")
    except Exception:
        return redirect("trainer_course_units", assignment_id=assignment_id)

    return render(
        request,
        "trainer/view_curriculum.html",
        {"assignment": assignment, "unit": unit, "outcomes": outcomes},
    )

def trainer_edit_curriculum(request, assignment_id, unit_id):
    """Edit extracted curriculum unit + outcomes (for correcting extraction errors)."""
    from django.db import transaction
    from django.forms import modelformset_factory
    from home.models import TrainerData
    from hod.models import TrainerAssighnment, CurriculumLearningOutcome
    from .forms import CourseUnitsDataForm, CurriculumLearningOutcomeForm

    staff_id = request.session.get("staff_id")
    if not staff_id:
        return redirect("trainer_my_classes")

    try:
        trainer = TrainerData.objects.get(id=staff_id)
        assignment = TrainerAssighnment.objects.select_related("course", "class_slot").get(
            id=assignment_id,
            trainer=trainer,
        )
        unit = assignment.course_units.get(id=unit_id)
    except Exception:
        return redirect("trainer_course_units", assignment_id=assignment_id)

    OutcomeFormSet = modelformset_factory(
        CurriculumLearningOutcome,
        form=CurriculumLearningOutcomeForm,
        extra=0,
        can_delete=False,
    )

    qs = unit.learning_outcomes.all().order_by("id")

    if request.method == "POST":
        unit_form = CourseUnitsDataForm(request.POST, instance=unit)
        formset = OutcomeFormSet(request.POST, queryset=qs)
        if unit_form.is_valid() and formset.is_valid():
            with transaction.atomic():
                unit_form.save()
                formset.save()
            return redirect("trainer_view_curriculum", assignment_id=assignment_id, unit_id=unit_id)
    else:
        unit_form = CourseUnitsDataForm(instance=unit)
        formset = OutcomeFormSet(queryset=qs)

    return render(
        request,
        "trainer/edit_curriculum.html",
        {"assignment": assignment, "unit": unit, "unit_form": unit_form, "formset": formset},
    )


def upload_occupational_standards(request, unit_id, assignment_id):
    """Handle OS PDF upload for a unit"""
    from home.models import TrainerData
    from hod.models import TrainerAssighnment, Units
    from .models import OccupationalStandards
    from .forms import OccupationalStandardsForm
    from django.contrib import messages
    
    staff_id = request.session.get('staff_id')
    
    if not staff_id:
        messages.error(request, 'You must be logged in to upload OS.')
        return redirect('trainer_my_classes')
    
    try:
        trainer = TrainerData.objects.get(id=staff_id)
        unit = Units.objects.get(id=unit_id)
        assignment = TrainerAssighnment.objects.get(
            id=assignment_id,
            trainer=trainer,
            units=unit
        )
    except (TrainerData.DoesNotExist, Units.DoesNotExist, TrainerAssighnment.DoesNotExist):
        messages.error(request, 'Invalid unit or assignment.')
        return redirect('trainer_my_classes')
    
    if request.method == 'POST':
        form = OccupationalStandardsForm(request.POST, request.FILES)
        if form.is_valid():
            os_doc = form.save(commit=False)
            os_doc.trainer = trainer
            os_doc.unit = unit
            os_doc.assignment = assignment
            os_doc.save()
            messages.success(request, f'Occupational Standards for {unit.unit_competence} uploaded successfully!')
            return redirect('trainer_course_units', assignment_id=assignment_id)
        else:
            for error in form.errors.values():
                messages.error(request, error)
    else:
        form = OccupationalStandardsForm()
    
    context = {
        'form': form,
        'unit': unit,
        'assignment': assignment
    }
    return render(request, 'trainer/upload_os.html', context)


def api_upload_occupational_standards(request):
    """AJAX API endpoint for OS PDF upload with automatic data extraction"""
    from home.models import TrainerData
    from hod.models import TrainerAssighnment, Units
    from .models import OccupationalStandards, OSData, OSLearningOutcome
    from .forms import OccupationalStandardsForm
    from .pdf_utils import extract_pdf_data
    from django.http import JsonResponse
    from django.contrib import messages
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed'}, status=405)
    
    staff_id = request.session.get('staff_id')
    
    if not staff_id:
        return JsonResponse({'success': False, 'message': 'Not authenticated'}, status=401)
    
    unit_id = request.POST.get('unit_id')
    assignment_id = request.POST.get('assignment_id')
    
    try:
        trainer = TrainerData.objects.get(id=staff_id)
        unit = Units.objects.get(id=unit_id)
        assignment = TrainerAssighnment.objects.get(
            id=assignment_id,
            trainer=trainer,
            units=unit
        )
    except (TrainerData.DoesNotExist, Units.DoesNotExist, TrainerAssighnment.DoesNotExist):
        return JsonResponse({'success': False, 'message': 'Invalid unit or assignment'}, status=400)
    
    form = OccupationalStandardsForm(request.POST, request.FILES)
    
    if form.is_valid():
        os_doc = form.save(commit=False)
        os_doc.trainer = trainer
        os_doc.unit = unit
        os_doc.assignment = assignment
        os_doc.save()
        
        # Extract PDF data
        try:
            pdf_file = request.FILES['pdf_file']
            extracted_data = extract_pdf_data(pdf_file)
            os_doc.extracted_text = extracted_data.get('raw_text', '')
            os_doc.save(update_fields=['extracted_text'])
            
            # Save extracted data to OSData model with correct field mapping
            os_data = OSData.objects.create(
                occupational_standard=os_doc,
                unit_code=extracted_data.get('unit_code', ''),
                unit_competence=unit.unit_competence,
                total_time=extracted_data.get('total_time')
            )

            for item in extracted_data.get('outcomes', []):
                OSLearningOutcome.objects.create(
                    os_data=os_data,
                    learning_outcome=item.get('learning_outcome', ''),
                    learning_expectations=item.get('learning_expectations', ''),
                    learning_assessments=item.get('learning_assessments', '')
                )
            
            debug = request.POST.get('debug') == '1'
            # Debug logs removed after successful verification
            response_payload = {
                'success': True, 
                'message': f'OS uploaded and data extracted successfully!',
                'file_name': os_doc.file_name,
                'extracted_data': {
                    'page_count': extracted_data.get('page_count', 0),
                    'word_count': extracted_data.get('word_count', 0),
                    'character_count': extracted_data.get('character_count', 0),
                    'competencies_found': len(extracted_data.get('competencies', '').split('\n')) if extracted_data.get('competencies') else 0,
                }
            }
            if debug:
                response_payload['debug'] = {
                    'unit_code': extracted_data.get('unit_code', ''),
                    'outcomes_count': len(extracted_data.get('outcomes', [])),
                    'tables_preview': extracted_data.get('tables_preview', []),
                }
            return JsonResponse(response_payload)
        except ImportError as e:
            # PDF library not available, still save the document but warn user
            return JsonResponse({
                'success': True, 
                'message': f'OS uploaded successfully! (PDF extraction library not installed)',
                'file_name': os_doc.file_name,
                'warning': 'PDF data extraction is not available. Install pdfplumber: pip install pdfplumber'
            })
        except Exception as e:
            # Extraction failed but document is saved
            return JsonResponse({
                'success': True, 
                'message': f'OS uploaded successfully! (Data extraction failed: {str(e)})',
                'file_name': os_doc.file_name,
                'warning': f'Could not extract PDF data: {str(e)}'
            })
    else:
        errors = {}
        for field, error_list in form.errors.items():
            errors[field] = [str(e) for e in error_list]
        return JsonResponse({'success': False, 'errors': errors}, status=400)

def create_attendance(request):
    staff_id = request.session.get('staff_id')
    trainer = TrainerData.objects.filter(id=staff_id).first() if staff_id else None

    if not trainer:
        return redirect('trainer_my_classes')

    assignments = TrainerAssighnment.objects.filter(trainer=trainer).select_related('class_slot', 'course')
    units = CourseUnitsData.objects.filter(trainer_assignments__trainer=trainer).distinct()
    unit_names = list(units.values_list('unit_of_competency', flat=True))
    sessions = SavedSessionPlan.objects.filter(unit__unit_competence__in=unit_names).distinct()

    errors = []
    form_data = {}

    if request.method == 'POST':
        assignment_id = request.POST.get('assignment')
        unit_id = request.POST.get('unit')
        session_id = request.POST.get('session_plan')
        date_str = request.POST.get('date')
        start_time_str = request.POST.get('start_time')
        end_time_str = request.POST.get('end_time')
        venue = request.POST.get('venue', '').strip()

        form_data = {
            'assignment': assignment_id,
            'unit': unit_id,
            'session_plan': session_id,
            'date': date_str,
            'start_time': start_time_str,
            'end_time': end_time_str,
            'venue': venue,
        }

        assignment = TrainerAssighnment.objects.filter(id=assignment_id, trainer=trainer).first()
        unit = CourseUnitsData.objects.filter(id=unit_id, trainer_assignments__trainer=trainer).first()
        session_plan = SavedSessionPlan.objects.filter(id=session_id).first()

        if not assignment:
            errors.append('Please select a valid class assigned to you.')
        if not unit:
            errors.append('Please select a valid unit assigned to you.')
        if not session_plan:
            errors.append('Please select a valid session plan.')
        if unit and session_plan and session_plan.unit.unit_competence != unit.unit_of_competency:
            errors.append('The selected session does not belong to the selected unit.')

        try:
            attendance_date = datetime.fromisoformat(date_str).date() if date_str else None
        except Exception:
            attendance_date = None
            errors.append('Please enter a valid date.')

        try:
            start_time = datetime.strptime(start_time_str, '%H:%M').time() if start_time_str else None
        except Exception:
            start_time = None
            errors.append('Please enter a valid start time.')

        try:
            end_time = datetime.strptime(end_time_str, '%H:%M').time() if end_time_str else None
        except Exception:
            end_time = None
            errors.append('Please enter a valid end time.')

        if start_time and end_time and start_time >= end_time:
            errors.append('End time must be later than start time.')

        if not errors:
            attendance = Attendance.objects.create(
                trainer=trainer,
                assignment=assignment,
                unit=unit,
                session_plan=session_plan,
                date=attendance_date,
                start_time=start_time,
                end_time=end_time,
                venue=venue,
                status='Pending',
            )
            # Generate unique code and QR code
            attendance.generate_attendance_code()
            attendance.generate_qr_code()
            return redirect('attendance_list')

    return render(request, 'trainer/create_attendance.html', {
        'trainer': trainer,
        'assignments': assignments,
        'units': units,
        'sessions': sessions,
        'errors': errors,
        'form_data': form_data,
    })


def attendance_list(request):
    staff_id = request.session.get('staff_id')
    trainer = TrainerData.objects.filter(id=staff_id).first() if staff_id else None
    attendances = Attendance.objects.filter(trainer=trainer).order_by('-date', '-start_time') if trainer else []
    return render(request, 'trainer/attendance_list.html', {
        'attendances': attendances
    })



def attendance_qrcode(request, attendance_id):
    """Display QR code and link for marking attendance"""
    staff_id = request.session.get('staff_id')
    trainer = TrainerData.objects.filter(id=staff_id).first() if staff_id else None

    if not trainer:
        return redirect('trainer_my_classes')

    attendance = get_object_or_404(Attendance, id=attendance_id, trainer=trainer)
    
    # Ensure code and QR code are generated
    if not attendance.attendance_code:
        attendance.generate_attendance_code()
    if not attendance.qr_code:
        attendance.generate_qr_code()

    return render(request, 'trainer/attendance_qrcode.html', {
        'attendance': attendance,
        'attendance_code': attendance.attendance_code,
        'attendance_link': attendance.get_attendance_link(),
    })
