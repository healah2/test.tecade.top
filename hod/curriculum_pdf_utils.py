"""
Curriculum PDF extraction utilities.

Extracts per-unit curriculum data from a multi-page curriculum PDF using text anchors:
- ISCED UNIT CODE
- TVET CDACC UNIT CODE
- Duration of unit
- This unit addresses the unit of competency
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Union

try:
    import pdfplumber

    HAS_PDFPLUMBER = True
except ImportError:  # pragma: no cover
    HAS_PDFPLUMBER = False

try:
    from PyPDF2 import PdfReader

    HAS_PYPDF2 = True
except ImportError:  # pragma: no cover
    HAS_PYPDF2 = False


_RE_UNIT_CODE = re.compile(
    r"^\s*(?:ISCED\s+UNIT\s+CODE|UNIT\s+CODE)\s*:?\s*(?P<code>.*)\s*$",
    re.IGNORECASE,
)
_RE_CDACC = re.compile(r"^\s*TVET\s+CDACC\s+UNIT\s+CODE\s*:?\s*(?P<code>.+?)\s*$", re.IGNORECASE)
_RE_DURATION = re.compile(
    r"^\s*Duration\s+of\s+unit\s*:?\s*(?P<hours>\d+)\s*(?:hours?|hrs?)\s*$",
    re.IGNORECASE,
)
_RE_PLAIN_UNIT_CODE = re.compile(r"^\s*\d{4}\s+\d{3}\s+[0-9A-Za-z]{2,}\s*$")
_RE_LABELED_CODE_LINE = re.compile(r"^\s*(?P<label>.+?)\s*:\s*(?P<code>.+?)\s*$")
_RE_RELATIONSHIP = re.compile(r"^\s*Relationship\s+to\s+Occupational\s+Standards\b", re.IGNORECASE)
_RE_COMP = re.compile(
    r"^\s*This\s+unit\s+addresses\s+the\s+unit\s+of\s+competency\s*:?\s*(?P<name>.*)\s*$",
    re.IGNORECASE,
)
_RE_STOP_DELIVERY = re.compile(
    r"^\s*Suggested\s+(?:Delivery\s+Methods|Methods\s+of\s+(?:Instruction|Delivery))\b",
    re.IGNORECASE,
)


@dataclass
class CurriculumUnitExtraction:
    isced_unit_code: str = ""
    tvet_cdacc_unit_code: str = ""
    total_time: Optional[int] = None
    unit_of_competency: str = ""
    outcomes: List[dict] = None

    def __post_init__(self):
        if self.outcomes is None:
            self.outcomes = []


TableGrid = List[List[str]]
TableEntry = Union[TableGrid, Dict[str, object]]


def _extract_page_texts(pdf_file) -> tuple[List[str], List[List[TableEntry]], List[Optional[float]]]:
    """
    Extract page texts and tables from a Django UploadedFile / file-like object.
    Prefers pdfplumber; falls back to PyPDF2.
    Returns (page_texts, tables, stop_marker_tops) where:
      - tables is list of tables per page
      - stop_marker_tops is aligned with pages and stores the y/top coordinate of the
        "Suggested ..." stop-marker header when detected (pdfplumber only).
    """
    if HAS_PDFPLUMBER:
        pdf_file.seek(0)
        page_texts: List[str] = []
        tables: List[List[TableEntry]] = []
        stop_marker_tops: List[Optional[float]] = []
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                page_texts.append(text)
                try:
                    # Prefer find_tables() so we can keep basic positional info (bbox).
                    # This lets downstream logic avoid extracting tables that appear
                    # *after* a stop marker on the same page.
                    page_tables: List[TableEntry] = []
                    try:
                        found = page.find_tables()  # type: ignore[attr-defined]
                    except Exception:
                        found = []

                    if found:
                        for t in found:
                            grid = t.extract() or []
                            cleaned_table: TableGrid = []
                            for row in grid:
                                cleaned_row = [str(cell or "").strip() for cell in (row or [])]
                                cleaned_table.append(cleaned_row)
                            page_tables.append({"bbox": getattr(t, "bbox", None), "rows": cleaned_table})
                    else:
                        # Fallback to extract_tables() (no positional metadata).
                        extracted = page.extract_tables() or []
                        for table in extracted:
                            cleaned_table: TableGrid = []
                            for row in table or []:
                                cleaned_row = [str(cell or "").strip() for cell in (row or [])]
                                cleaned_table.append(cleaned_row)
                            page_tables.append(cleaned_table)

                    tables.append(page_tables)
                except Exception:
                    tables.append([])

                # Best-effort: locate the stop-marker header vertical position so we can
                # ignore tables *below* it on the same page.
                marker_top: Optional[float] = None
                try:
                    words = page.extract_words() or []
                    for idx, w in enumerate(words):
                        if str(w.get("text", "")).strip().lower() != "suggested":
                            continue
                        nxt = words[idx + 1] if idx + 1 < len(words) else None
                        nxt2 = words[idx + 2] if idx + 2 < len(words) else None
                        nxt3 = words[idx + 3] if idx + 3 < len(words) else None
                        if (
                            nxt
                            and nxt2
                            and str(nxt.get("text", "")).strip().lower() == "delivery"
                            and str(nxt2.get("text", "")).strip().lower() == "methods"
                        ):
                            marker_top = float(w.get("top")) if w.get("top") is not None else None
                            break
                        if (
                            nxt
                            and nxt2
                            and nxt3
                            and str(nxt.get("text", "")).strip().lower() == "methods"
                            and str(nxt2.get("text", "")).strip().lower() == "of"
                            and str(nxt3.get("text", "")).strip().lower() in {"instruction", "delivery"}
                        ):
                            marker_top = float(w.get("top")) if w.get("top") is not None else None
                            break
                except Exception:
                    marker_top = None
                stop_marker_tops.append(marker_top)
        return page_texts, tables, stop_marker_tops

    if HAS_PYPDF2:
        pdf_file.seek(0)
        reader = PdfReader(pdf_file)
        page_texts = []
        tables = []
        for page in reader.pages:
            page_texts.append(page.extract_text() or "")
            tables.append([])  # PyPDF2 doesn't extract tables
        return page_texts, tables, [None for _ in page_texts]

    raise ImportError("No PDF library available. Install pdfplumber or PyPDF2.")


def _iter_lines(page_texts: Iterable[str]) -> Iterable[tuple[str, int]]:
    for page_index, page_text in enumerate(page_texts):
        for raw in (page_text or "").splitlines():
            line = raw.strip()
            if line:
                yield line, page_index


def _detect_unit_header_block(
    lines: List[tuple[str, int]],
    start_index: int,
    *,
    lookahead: int = 18,
) -> Optional[dict]:
    """
    Detect the "unit header block" the PDF uses to introduce a new unit.

    We consider a new unit to start when we can find, in close proximity:
      - (optional) ISCED UNIT CODE / UNIT CODE (sometimes wrapped to next line)
      - TVET CDACC UNIT CODE
      - Duration of unit
      - Relationship to Occupational Standards
      - This unit addresses the unit of competency

    This is more reliable than relying on a single line because some PDFs omit
    the ISCED/UNIT CODE label or place headings in inconsistent positions.
    """
    if start_index < 0 or start_index >= len(lines):
        return None

    first_line, first_page = lines[start_index]
    starts_with_unit_code = _RE_UNIT_CODE.match(first_line) is not None
    starts_with_cdacc = _RE_CDACC.match(first_line) is not None
    if not (starts_with_unit_code or starts_with_cdacc):
        return None

    # Avoid double-detecting the same unit block:
    # If we start on the CDACC line but a UNIT CODE / ISCED UNIT CODE line appears
    # just above it (often on the same page, but sometimes on the previous page due
    # to page breaks), the unit was already detected when scanning that earlier line.
    if starts_with_cdacc and not starts_with_unit_code:
        back_limit = max(0, start_index - 40)
        for j in range(start_index - 1, back_limit - 1, -1):
            prev_line, prev_page = lines[j]
            # Only look back at most one page.
            if prev_page < first_page - 1:
                break
            if _RE_UNIT_CODE.match(prev_line):
                return None

    end_index = min(len(lines), start_index + lookahead)
    window = lines[start_index:end_index]

    unit_code: str = ""
    cdacc_code: str = ""
    duration_hours: Optional[int] = None
    has_relationship = False
    competency_name: str = ""

    # Extract unit code (supports wrap to next line)
    m_unit = _RE_UNIT_CODE.match(first_line)
    if m_unit:
        unit_code = (m_unit.group("code") or "").strip()
        if not unit_code:
            for j in range(start_index + 1, end_index):
                nxt, _ = lines[j]
                nxt = nxt.strip()
                if not nxt:
                    continue
                if _RE_CDACC.match(nxt) or _RE_DURATION.match(nxt) or _RE_RELATIONSHIP.match(nxt) or _RE_COMP.match(nxt):
                    break
                # Avoid accidentally taking another header-like line
                if _RE_UNIT_CODE.match(nxt):
                    break
                unit_code = nxt
                break
    else:
        # Some PDFs omit the ISCED/UNIT CODE label, but still include the code line
        # immediately above the TVET CDACC line (often at the end of the previous page).
        # The code line can be either plain (e.g. "0413 441 03A") or labeled
        # (e.g. "UNIT CODE: 0413 441 03A").
        if starts_with_cdacc:
            back_limit = max(0, start_index - 40)
            for j in range(start_index - 1, back_limit - 1, -1):
                prev_line, prev_page = lines[j]
                if prev_page < first_page - 1:
                    break
                prev_line = (prev_line or "").strip()
                if not prev_line:
                    continue
                if _RE_CDACC.match(prev_line) or _RE_DURATION.match(prev_line) or _RE_RELATIONSHIP.match(prev_line) or _RE_COMP.match(prev_line):
                    continue

                # Preferred: a labeled UNIT CODE / ISCED UNIT CODE variant.
                m_prev_unit = _RE_UNIT_CODE.match(prev_line)
                if m_prev_unit:
                    candidate = (m_prev_unit.group("code") or "").strip()
                    if candidate:
                        unit_code = candidate
                        break

                # Next: generic "X CODE: <value>" where the value looks like a unit code.
                m_labeled = _RE_LABELED_CODE_LINE.match(prev_line)
                if m_labeled:
                    candidate = (m_labeled.group("code") or "").strip()
                    if candidate and _RE_PLAIN_UNIT_CODE.match(candidate):
                        unit_code = candidate
                        break

                # Last: a plain unit-code line.
                if _RE_PLAIN_UNIT_CODE.match(prev_line):
                    unit_code = prev_line
                    break

    for raw, _p in window:
        m_cdacc = _RE_CDACC.match(raw)
        if m_cdacc and not cdacc_code:
            cdacc_code = m_cdacc.group("code").strip()
            continue

        m_dur = _RE_DURATION.match(raw)
        if m_dur and duration_hours is None:
            try:
                duration_hours = int(m_dur.group("hours"))
            except ValueError:
                duration_hours = None
            continue

        if _RE_RELATIONSHIP.match(raw):
            has_relationship = True
            continue

        m_comp = _RE_COMP.match(raw)
        if m_comp and not competency_name:
            competency_name = (m_comp.group("name") or "").strip().rstrip(",")
            continue

    # Require the stable block anchors. Unit code is optional; many pages omit it.
    if not cdacc_code or duration_hours is None or not has_relationship or not competency_name:
        return None

    return {
        "page_index": first_page,
        "unit_code": unit_code,
        "cdacc_code": cdacc_code,
        "duration_hours": duration_hours,
        "competency_name": competency_name,
    }


def extract_curriculum_units(pdf_file) -> List[CurriculumUnitExtraction]:
    """
    Parse a curriculum PDF and return extracted unit records.

    Unit boundaries are determined by encountering an `ISCED UNIT CODE` line.
    """
    page_texts, tables, stop_marker_tops = _extract_page_texts(pdf_file)
    lines = list(_iter_lines(page_texts))

    units: List[CurriculumUnitExtraction] = []
    current: Optional[CurriculumUnitExtraction] = None
    current_page_index = 0  # Track the page where the unit starts
    paused_until_next_unit = False

    def flush():
        nonlocal current
        if current is None:
            return
        # Extract outcomes for the current unit
        if current.isced_unit_code or current.tvet_cdacc_unit_code:
            current.outcomes = _extract_unit_outcomes(tables, current_page_index, page_texts, stop_marker_tops)
            units.append(current)
        current = None

    i = 0
    while i < len(lines):
        line, page_index = lines[i]

        header = _detect_unit_header_block(lines, i)
        if header is not None:
            # If we've hit the stop section for this unit, ignore repeated headers for the
            # same unit and only resume once we detect a *different* unit block.
            if current is not None and paused_until_next_unit:
                if header["cdacc_code"].strip().lower() == (current.tvet_cdacc_unit_code or "").strip().lower():
                    i += 1
                    continue
                paused_until_next_unit = False

            flush()
            current = CurriculumUnitExtraction(
                isced_unit_code=header["unit_code"],
                tvet_cdacc_unit_code=header["cdacc_code"],
                total_time=header["duration_hours"],
                unit_of_competency=header["competency_name"],
            )
            current_page_index = header["page_index"]
            i += 1
            continue

        if current is None:
            i += 1
            continue

        # Once the unit reaches "Suggested Delivery Methods", stop extracting anything else
        # for the current unit until we encounter the next unit header (new ISCED code).
        if _RE_STOP_DELIVERY.match(line):
            paused_until_next_unit = True
            i += 1
            continue

        if paused_until_next_unit:
            i += 1
            continue

        m_cdacc = _RE_CDACC.match(line)
        if m_cdacc:
            cdacc_code = m_cdacc.group("code").strip()
            # Some unit pages omit the "ISCED UNIT CODE"/"UNIT CODE" header.
            # In that case, treat the first seen TVET CDACC code as the unit boundary.
            if current is None:
                current = CurriculumUnitExtraction(isced_unit_code="", tvet_cdacc_unit_code=cdacc_code)
                current_page_index = page_index
                i += 1
                continue

            # If we already captured a CDACC code and encounter a different one,
            # start a new unit (handles PDFs missing unit-code headers).
            if current.tvet_cdacc_unit_code and cdacc_code.strip().lower() != current.tvet_cdacc_unit_code.strip().lower():
                flush()
                current = CurriculumUnitExtraction(isced_unit_code="", tvet_cdacc_unit_code=cdacc_code)
                current_page_index = page_index
                i += 1
                continue

            if not current.tvet_cdacc_unit_code:
                current.tvet_cdacc_unit_code = cdacc_code
            i += 1
            continue

        m_dur = _RE_DURATION.match(line)
        if m_dur and current.total_time is None:
            try:
                current.total_time = int(m_dur.group("hours"))
            except ValueError:
                current.total_time = None
            i += 1
            continue

        m_comp = _RE_COMP.match(line)
        if m_comp and not current.unit_of_competency:
            name = (m_comp.group("name") or "").strip().rstrip(",")

            # Some PDFs wrap the competency name to the next line.
            if not name:
                j = i + 1
                collected: List[str] = []
                while j < len(lines):
                    nxt, _ = lines[j]
                    nxt = nxt.strip()
                    if not nxt:
                        break
                    if _RE_UNIT_CODE.match(nxt) or _RE_CDACC.match(nxt) or _RE_DURATION.match(nxt) or _RE_COMP.match(nxt):
                        break
                    # Stop on common section headers.
                    if re.match(
                        r"^(relationship to occupational standards|elements of competence|learning outcomes)\\b",
                        nxt,
                        re.IGNORECASE,
                    ):
                        break
                    collected.append(nxt)
                    j += 1
                    if len(" ".join(collected)) > 300:
                        break
                name = " ".join(collected).strip().rstrip(",")

            current.unit_of_competency = name
            i += 1
            continue

        i += 1

    flush()
    return units


def _table_rows(entry: TableEntry) -> TableGrid:
    if isinstance(entry, dict):
        return entry.get("rows") or []
    return entry


def _extract_unit_outcomes(
    tables: List[List[TableEntry]],
    start_page: int,
    page_texts: List[str],
    stop_marker_tops: List[Optional[float]],
    end_page_exclusive: Optional[int] = None,
) -> List[dict]:
    """
    Extract learning outcomes from tables starting from the given page.
    Adapted from trainer/pdf_utils.py _extract_outcomes.
    Only extracts from tables between 'Learning outcomes, Content and Suggested Assessment Methods'
    and 'Suggested Delivery Methods'.
    """
    outcomes = []

    # Find the start page for outcomes extraction
    start_marker = re.compile(r"learning outcomes.*content.*assessment methods", re.IGNORECASE)
    stop_marker = re.compile(
        r"suggested\s+(?:delivery\s+methods|methods\s+of\s+(?:instruction|delivery))",
        re.IGNORECASE,
    )

    if end_page_exclusive is None:
        end_page_exclusive = len(page_texts)
    end_page_exclusive = max(0, min(int(end_page_exclusive), len(page_texts)))
    start_page = max(0, min(int(start_page), end_page_exclusive))

    outcomes_start_page = None
    outcomes_stop_page = None

    for p_idx in range(start_page, end_page_exclusive):
        page_text = page_texts[p_idx]
        if outcomes_start_page is None and start_marker.search(page_text):
            outcomes_start_page = p_idx
        if outcomes_stop_page is None and stop_marker.search(page_text):
            outcomes_stop_page = p_idx
            break

    if outcomes_start_page is None:
        return outcomes  # No outcomes section found

    def norm_header(val):
        val = str(val or "").strip().lower()
        val = re.sub(r"[^a-z0-9]+", "", val)
        return val

    def detect_columns(table):
        lo_idx = content_idx = assess_idx = None
        header_row_idx = None
        for idx, row in enumerate(table[:6]):
            if not row:
                continue
            for col, cell in enumerate(row):
                text = str(cell or "").strip().lower()
                if "learning outcome" in text or text == "outcome":
                    lo_idx = col
                    header_row_idx = idx if header_row_idx is None else header_row_idx
                if "content" in text or "learning expectation" in text:
                    content_idx = col
                    header_row_idx = idx if header_row_idx is None else header_row_idx
                if "assessment" in text and "method" in text:
                    assess_idx = col
                    header_row_idx = idx if header_row_idx is None else header_row_idx
                if "suggested assessment" in text:
                    assess_idx = col
                    header_row_idx = idx if header_row_idx is None else header_row_idx
            if lo_idx is not None and content_idx is not None and assess_idx is not None:
                return header_row_idx, (lo_idx, content_idx, assess_idx)
        return None, None

    def is_header_row(row: List[str]) -> bool:
        if not row:
            return False
        joined = " ".join([str(c or "").strip().lower() for c in row if str(c or "").strip()])
        if not joined:
            return False
        has_lo = ("learning outcome" in joined) or re.search(r"\boutcome\b", joined) is not None
        has_content = ("content" in joined) or ("learning expectation" in joined)
        has_assess = ("assessment" in joined) and ("method" in joined or "suggested" in joined)
        return bool(has_lo and has_content and has_assess)

    last_indices = None

    last_outcome = None
    last_content = ""
    last_assess = ""

    def flush_last():
        if last_outcome is not None:
            outcomes.append(
                {
                    "learning_outcome": last_outcome,
                    "learning_expectations": last_content.strip(),
                    "learning_assessments": last_assess.strip(),
                }
            )

    started = False
    last_table_page: Optional[int] = None

    # Process tables from outcomes_start_page up to (and including) the page where
    # the stop marker is found. The marker typically appears *after* the last
    # outcomes table on the same page, so we must not exclude that page.
    end_page = (outcomes_stop_page + 1) if outcomes_stop_page is not None else end_page_exclusive
    end_page = min(end_page, len(tables))

    for page_idx in range(outcomes_start_page, end_page):
        page_tables = tables[page_idx]
        for table_entry in page_tables:
            table = _table_rows(table_entry)
            if not table:
                continue

            # If we have reached pages after the stop-marker page, stop extracting.
            # The stop condition itself is strictly the presence of the
            # "Suggested Delivery Methods" header (detected in page_texts),
            # and tables *below* it on that same page are filtered by bbox logic.
            if started and outcomes_stop_page is not None and page_idx > outcomes_stop_page:
                flush_last()
                return outcomes

            # Stop if we encounter untabled text between pages after starting.
            if started and last_table_page is not None and page_idx > last_table_page + 1:
                for p in range(last_table_page + 1, page_idx):
                    if (page_texts[p] or "").strip():
                        flush_last()
                        return outcomes

            # If we're on the stop-marker page, avoid tables that are likely below the
            # marker (e.g., a new section with unrelated tables). When we have bbox
            # metadata (pdfplumber find_tables) and a detected marker y-position, compare
            # the table's top against the marker's top.
            if outcomes_stop_page is not None and page_idx == outcomes_stop_page and isinstance(table_entry, dict):
                bbox = table_entry.get("bbox")
                marker_top = stop_marker_tops[page_idx] if page_idx < len(stop_marker_tops) else None
                if bbox and marker_top is not None:
                    try:
                        # pdfplumber bbox is (x0, top, x1, bottom)
                        _, table_top, _, _ = bbox  # type: ignore[misc]
                        if float(table_top) > float(marker_top):
                            continue
                    except Exception:
                        pass

            header_idx, indices = detect_columns(table)
            if indices:
                last_indices = indices
            else:
                # Heuristic: if table looks like 3 columns, assume LO, Content, Assessment
                max_cols = max((len(r) for r in table if r), default=0)
                if max_cols == 3:
                    indices = (0, 1, 2)
                elif last_indices:
                    indices = last_indices

            if not indices:
                continue

            start_row = (header_idx + 1) if header_idx is not None else 0
            # If we couldn't explicitly detect a header row but the first row looks like
            # headers, skip it (data starts on the next row).
            if header_idx is None and start_row == 0 and table and is_header_row([str(c or "") for c in (table[0] or [])]):
                start_row = 1
            lo_idx, content_idx, assess_idx = indices

            for row in table[start_row:]:
                if not row:
                    continue

                def cell_at(i):
                    return str(row[i] or "").strip() if i is not None and i < len(row) else ""

                def find_numbered_cell():
                    for idx, c in enumerate(row):
                        text = str(c or "").strip()
                        if re.match(r"^\\d+\\.\\s*", text):
                            return idx, text
                    return None, ""

                lo = cell_at(lo_idx)
                content = cell_at(content_idx)
                assess = cell_at(assess_idx)

                # Detect LO by numbering pattern, but prefer the designated LO column
                if not lo:
                    lo_idx_found, lo_text = find_numbered_cell()
                    if lo_text and lo_idx_found != content_idx and lo_idx_found != assess_idx:
                        lo = lo_text
                        # Prefer cells to the right of LO for content/assessment
                        right_cells = [
                            str(c or "").strip()
                            for i, c in enumerate(row)
                            if i > lo_idx_found and str(c or "").strip()
                        ]
                        if right_cells:
                            if not content:
                                content = right_cells[0]
                            if not assess and len(right_cells) > 1:
                                assess = right_cells[-1]

                # If indices don't yield content/assess, fall back to non-empty cells
                if not content or not assess:
                    non_empty = [(i, str(c or "").strip()) for i, c in enumerate(row) if str(c or "").strip()]
                    # Remove LO cell from non-empty list if present
                    if lo:
                        non_empty = [(i, v) for i, v in non_empty if v != lo]
                    if non_empty:
                        if not content:
                            content = non_empty[0][1]
                        if not assess and len(non_empty) >= 2:
                            assess = non_empty[-1][1]

                # Skip header-like rows (only header keywords, no numbered LO)
                if not re.search(r"^\\d+\\.\\s*", lo):
                    non_empty_vals = [str(c or "").strip() for c in row if str(c or "").strip()]
                    header_tokens = {
                        "learning outcome",
                        "content",
                        "suggested assessment method",
                        "assessment method",
                    }
                    filtered = [v for v in non_empty_vals if v.lower() not in header_tokens]
                    if non_empty_vals and not filtered:
                        continue

                # Continuation rows: LO empty but content/assessment present
                if not lo:
                    # Prefer column-sensitive continuation: keep column 2 -> content and
                    # column 3 -> assessment, instead of merging everything and guessing.
                    cont_content = content.strip() if content else ""
                    cont_assess = assess.strip() if assess else ""

                    non_empty_vals = [str(c or "").strip() for c in row if str(c or "").strip()]
                    header_tokens = {
                        "learning outcome",
                        "content",
                        "suggested assessment method",
                        "assessment method",
                    }
                    non_empty_vals = [v for v in non_empty_vals if v.lower() not in header_tokens]
                    if non_empty_vals and last_outcome is not None:
                        if cont_content:
                            last_content = f"{last_content}\\n{cont_content}" if last_content else cont_content
                        if cont_assess:
                            last_assess = f"{last_assess}\\n{cont_assess}" if last_assess else cont_assess

                        # Fallback: if we couldn't map columns but there is text, keep the
                        # previous heuristic to avoid dropping data.
                        if not cont_content and not cont_assess:
                            continuation_text = "\\n".join(non_empty_vals)
                            if re.search(r"\\b(observation|written|oral)\\b", continuation_text.lower()):
                                last_assess = f"{last_assess}\\n{continuation_text}" if last_assess else continuation_text
                            else:
                                last_content = f"{last_content}\\n{continuation_text}" if last_content else continuation_text
                        continue
                    # If no previous outcome, skip orphan continuation rows
                    if non_empty_vals and last_outcome is None:
                        continue

                # Skip header-like rows
                row_text = " ".join([str(c or "").strip() for c in row]).lower()
                header_keywords = ["learning outcome", "content", "suggested assessment", "assessment method"]
                if row_text and all(h in row_text for h in ["learning outcome", "content"]) and any(
                    h in row_text for h in ["assessment", "suggested assessment"]
                ):
                    continue
                if row_text in header_keywords:
                    continue
                if lo.strip().lower() in ["learning outcome", "outcome"] and not content and not assess:
                    continue
                if content.strip().lower() == "content" and not lo and not assess:
                    continue
                if assess.strip().lower() in ["assessment", "assessment method", "suggested assessment method"] and not lo and not content:
                    continue

                if lo or content or assess:
                    flush_last()
                    last_outcome = lo
                    last_content = content
                    last_assess = assess

            # Do not flush here; allow continuation across tables.
            started = True
            last_table_page = page_idx

    flush_last()

    if outcomes:
        return outcomes

    # Fallback: parse from raw text lines (same approach as trainer/pdf_utils.py).
    raw_text = "\n".join([page_texts[p] for p in range(outcomes_start_page, end_page) if page_texts[p]])
    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
    header_index = None
    for i, line in enumerate(lines):
        low = line.lower()
        if "learning outcome" in low and ("content" in low or "learning expectation" in low) and "assessment" in low:
            header_index = i
            break

    if header_index is None:
        return []

    for line in lines[header_index + 1 :]:
        parts = re.split(r"\\s{2,}|\\t+", line)
        if len(parts) >= 3:
            outcomes.append(
                {
                    "learning_outcome": parts[0].strip(),
                    "learning_expectations": parts[1].strip(),
                    "learning_assessments": parts[2].strip(),
                }
            )

    # Normalize bullets
    for outcome in outcomes:
        outcome["learning_outcome"] = _normalize_bullets(outcome.get("learning_outcome", ""))
        outcome["learning_expectations"] = _normalize_bullets(outcome.get("learning_expectations", ""))
        outcome["learning_assessments"] = _normalize_bullets(outcome.get("learning_assessments", ""))

    return outcomes


def _normalize_bullets(text):
    if not text:
        return text

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    normalized = []
    main_bullets = ["\\uf071", "ï±", "Ã¯ÂÂ±"]  # main bullet symbols
    sub_bullets = ["\\uf0fc", "\\uf0b7", "\\uf0f0", "ïƒ¼", "ï‚·", "Ã¯Æ’Â¼", "Ã¯â€šÂ·"]  # sub bullet symbols
    bullet_regex = re.compile(
        r"^[\\u2022\\u2023\\u25E6\\u25AA\\u25AB\\u25A0\\u25CF\\u25CB\\u25A1\\u2610\\u2611\\u2713\\u2714\\u2717\\u2718\\uf0b7\\uf071\\uf0fc\\uf0f0ïƒ¼ï‚·ï±Ã¯ÂÂ±Ã¯Æ’Â¼Ã¯â€šÂ·]"
    )

    has_sub_bullets = False
    for line in lines:
        if line and (line[0] in sub_bullets or bullet_regex.match(line)):
            has_sub_bullets = True
            break

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        first_char = stripped[0]
        if first_char in main_bullets:
            content = stripped[1:].strip()
            if content:
                if has_sub_bullets:
                    normalized.append(content)
                else:
                    normalized.append(f"- {content}")
            continue

        if first_char in sub_bullets:
            content = stripped[1:].strip()
            if content:
                normalized.append(f"- {content}")
            continue

        if bullet_regex.match(stripped):
            content = bullet_regex.sub("", stripped).strip()
            if content:
                if has_sub_bullets:
                    normalized.append(content)
                else:
                    normalized.append(f"- {content}")
            continue

        # Preserve existing dashed bullets
        if stripped.startswith("- "):
            normalized.append(stripped)
            continue

        normalized.append(stripped)

    return "\\n".join(normalized)
