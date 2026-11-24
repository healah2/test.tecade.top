"""
PDF Extraction Utility for Occupational Standards Documents
Extracts text and structured data from PDF files
"""

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    from PyPDF2 import PdfReader
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False

import re


class PDFExtractor:
    """Extract text and structured data from PDF files"""
    
    def __init__(self, pdf_file):
        """
        Initialize with a file object
        pdf_file: Django UploadedFile or file-like object
        """
        self.pdf_file = pdf_file
        self.raw_text = ""
        self.page_texts = []
        self.page_count = 0
        self.character_count = 0
        self.word_count = 0
        self.competencies = []
        self.skills = []
        self.knowledge = []
        self.assessment_criteria = []
        self.tables = []
        self.table_pages = []
        self.unit_code = ""
        self.outcomes = []
        self.debug_rows = []
        self.debug_indices = []
        self.total_time = None
    
    def extract(self):
        """Extract all data from PDF"""
        if HAS_PDFPLUMBER:
            self._extract_with_pdfplumber()
        elif HAS_PYPDF2:
            self._extract_with_pypdf2()
        else:
            raise ImportError("No PDF library available. Install pdfplumber or PyPDF2")
        
        # Parse structured data from raw text
        self._parse_structured_data()
        
        return self.get_results()
    
    def _extract_with_pdfplumber(self):
        """Extract text using pdfplumber (preferred method)"""
        try:
            self.pdf_file.seek(0)  # Reset file pointer
            with pdfplumber.open(self.pdf_file) as pdf:
                self.page_count = len(pdf.pages)
                
                # Extract text from all pages
                for page_index, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if text:
                        self.raw_text += text + "\n"
                        self.page_texts.append(text)
                    else:
                        self.page_texts.append("")
                    try:
                        page_tables = page.extract_tables()
                        if page_tables:
                            for t in page_tables:
                                self.tables.append(t)
                                self.table_pages.append(page_index)
                    except Exception:
                        pass
        except Exception as e:
            raise Exception(f"Error extracting with pdfplumber: {str(e)}")
    
    def _extract_with_pypdf2(self):
        """Extract text using PyPDF2 (fallback method)"""
        try:
            self.pdf_file.seek(0)  # Reset file pointer
            reader = PdfReader(self.pdf_file)
            self.page_count = len(reader.pages)
            
            # Extract text from all pages
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    self.raw_text += text + "\n"
        except Exception as e:
            raise Exception(f"Error extracting with PyPDF2: {str(e)}")
    
    def _parse_structured_data(self):
        """Parse structured data from raw text"""
        if not self.raw_text:
            return
        
        # Calculate statistics
        self.character_count = len(self.raw_text)
        self.word_count = len(self.raw_text.split())
        
        # Extract competencies (lines containing "competenc" keyword)
        self.competencies = self._extract_section('competenc', limit=10)
        
        # Extract skills (lines containing "skill" keyword)
        self.skills = self._extract_section('skill', limit=10)
        
        # Extract knowledge (lines containing "knowledge" or "understand" keyword)
        self.knowledge = self._extract_section(['knowledge', 'understand', 'know'], limit=10)
        
        # Extract assessment criteria (lines containing "assess" keyword)
        self.assessment_criteria = self._extract_section('assess', limit=10)
        self.unit_code = self._extract_unit_code()
        self.outcomes = self._extract_outcomes()
        self.total_time = self._extract_total_time()

        # Normalize bullet symbols in outcomes
        self.outcomes = [self._normalize_outcome_bullets(o) for o in self.outcomes]

    def _normalize_bullets(self, text):
        if not text:
            return text

        lines = [l.strip() for l in text.splitlines() if l.strip()]
        normalized = []
        main_bullets = ['\uf071', '', 'ï±']  # main bullet symbols
        sub_bullets = ['\uf0fc', '\uf0b7', '\uf0f0', '', '', 'ïƒ¼', 'ï‚·']  # sub bullet symbols
        bullet_regex = re.compile(r'^[\u2022\u2023\u25E6\u25AA\u25AB\u25A0\u25CF\u25CB\u25A1\u2610\u2611\u2713\u2714\u2717\u2718\uf0b7\uf071\uf0fc\uf0f0ï±ïƒ¼ï‚·]')

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
                content = bullet_regex.sub('', stripped).strip()
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

        return "\n".join(normalized)

    def _normalize_outcome_bullets(self, outcome):
        return {
            'learning_outcome': self._normalize_bullets(outcome.get('learning_outcome', '')),
            'learning_expectations': self._normalize_bullets(outcome.get('learning_expectations', '')),
            'learning_assessments': self._normalize_bullets(outcome.get('learning_assessments', '')),
        }

    def _extract_unit_code(self):
        """Extract UNIT CODE value from raw text."""
        if not self.raw_text:
            return ""
        for line in self.raw_text.split('\n'):
            if 'UNIT CODE' in line.upper():
                match = re.search(r'UNIT CODE\s*[:\-]?\s*([A-Za-z0-9\-/]+)', line, re.IGNORECASE)
                if match:
                    return match.group(1).strip()
        return ""

    def _extract_total_time(self):
        """Extract total duration/time in hours from raw text."""
        if not self.raw_text:
            return None
        patterns = [
            r'(?:DURATION|TOTAL\s+TIME|NOMINAL\s+HOURS|DURATION\s+OF\s+UNIT)\s*[:\-]?\s*(\d+)',
            r'(?:DURATION|TOTAL\s+TIME|NOMINAL\s+HOURS|DURATION\s+OF\s+UNIT)\s*[:\-]?\s*(\d+)\s*H',
            r'(\d+)\s*(?:HOURS|HRS)\b'
        ]
        for line in self.raw_text.split('\n'):
            upper = line.upper()
            for pat in patterns:
                m = re.search(pat, upper)
                if m:
                    try:
                        return int(m.group(1))
                    except ValueError:
                        continue
        return None

    def _extract_outcomes(self):
        """Extract learning outcomes table data."""
        outcomes = []

        # Try table-based extraction first
        def norm_header(val):
            val = str(val or '').strip().lower()
            val = re.sub(r'[^a-z0-9]+', '', val)
            return val

        def detect_columns(table):
            lo_idx = content_idx = assess_idx = None
            header_row_idx = None
            for idx, row in enumerate(table[:6]):
                if not row:
                    continue
                for col, cell in enumerate(row):
                    text = str(cell or '').strip().lower()
                    if 'learning outcome' in text or text == 'outcome':
                        lo_idx = col
                        header_row_idx = idx if header_row_idx is None else header_row_idx
                    if 'content' in text or 'learning expectation' in text:
                        content_idx = col
                        header_row_idx = idx if header_row_idx is None else header_row_idx
                    if 'assessment' in text and 'method' in text:
                        assess_idx = col
                        header_row_idx = idx if header_row_idx is None else header_row_idx
                    if 'suggested assessment' in text:
                        assess_idx = col
                        header_row_idx = idx if header_row_idx is None else header_row_idx
            if lo_idx is not None and content_idx is not None and assess_idx is not None:
                return header_row_idx, (lo_idx, content_idx, assess_idx)
            return None, None

        last_indices = None

        last_outcome = None
        last_content = ""
        last_assess = ""

        def flush_last():
            if last_outcome is not None:
                outcomes.append({
                    'learning_outcome': last_outcome,
                    'learning_expectations': last_content.strip(),
                    'learning_assessments': last_assess.strip()
                })

        heading_page_index = None
        heading = "LEARNING OUTCOMES, CONTENT AND SUGGESTED ASSESSMENT METHODS"
        if self.page_texts:
            for p_idx, p_text in enumerate(self.page_texts):
                if heading in (p_text or "").upper():
                    heading_page_index = p_idx
                    break

        started = False
        last_table_page = None
        stop_phrase = "SUGGESTED METHODS OF DELIVERY"
        stop_page_index = None
        if self.page_texts:
            for p_idx, p_text in enumerate(self.page_texts):
                if stop_phrase in (p_text or "").upper():
                    stop_page_index = p_idx
                    break

        def table_has_numbered_outcomes(table, scan_rows=12):
            if not table:
                return False
            for row in table[:scan_rows]:
                if not row:
                    continue
                for cell in row:
                    text = str(cell or '').strip()
                    if re.match(r'^\d+\.\s*', text):
                        return True
            return False

        for t_idx, table in enumerate(self.tables):
            if not table:
                continue

            # If we have reached pages after the marker section, stop extracting.
            # This still allows tables on the marker page itself (including
            # continuation rows) to be processed.
            if started and stop_page_index is not None and self.table_pages:
                current_table_page = self.table_pages[t_idx]
                if current_table_page > stop_page_index:
                    flush_last()
                    return outcomes

                # On the marker page itself, allow continuation rows/tables that
                # still look like learning-outcomes rows. As soon as we hit a
                # non-outcomes table on the marker page, stop.
                if current_table_page == stop_page_index:
                    if outcomes and not table_has_numbered_outcomes(table):
                        flush_last()
                        return outcomes

            # Only process tables on/after the heading page
            if heading_page_index is not None and self.table_pages:
                if self.table_pages[t_idx] < heading_page_index:
                    continue

            # Stop if we encounter untabled text between tables after starting
            if heading_page_index is not None and started and last_table_page is not None and self.table_pages:
                current_page = self.table_pages[t_idx]
                if current_page > last_table_page + 1 and self.page_texts:
                    for p in range(last_table_page + 1, current_page):
                        if (self.page_texts[p] or "").strip():
                            flush_last()
                            return outcomes

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
            lo_idx, content_idx, assess_idx = indices
            if len(self.debug_indices) < 3:
                self.debug_indices.append({
                    'table_index': len(self.debug_indices),
                    'header_idx': header_idx,
                    'indices': indices
                })

            for row in table[start_row:]:
                if not row:
                    continue

                def cell_at(i):
                    return str(row[i] or '').strip() if i is not None and i < len(row) else ''

                def find_numbered_cell():
                    for idx, c in enumerate(row):
                        text = str(c or '').strip()
                        if re.match(r'^\d+\.\s*', text):
                            return idx, text
                    return None, ""

                lo = cell_at(lo_idx)
                content = cell_at(content_idx)
                assess = cell_at(assess_idx)


                # Detect LO by numbering pattern anywhere in the row
                if not lo:
                    lo_idx_found, lo_text = find_numbered_cell()
                    if lo_text:
                        lo = lo_text
                        # Prefer cells to the right of LO for content/assessment
                        right_cells = [str(c or '').strip() for i, c in enumerate(row) if i > lo_idx_found and str(c or '').strip()]
                        if right_cells:
                            if not content:
                                content = right_cells[0]
                            if not assess and len(right_cells) > 1:
                                assess = right_cells[-1]

                # If indices don't yield content/assess, fall back to non-empty cells
                if not content or not assess:
                    non_empty = [(i, str(c or '').strip()) for i, c in enumerate(row) if str(c or '').strip()]
                    # Remove LO cell from non-empty list if present
                    if lo:
                        non_empty = [(i, v) for i, v in non_empty if v != lo]
                    if non_empty:
                        if not content:
                            content = non_empty[0][1]
                        if not assess and len(non_empty) >= 2:
                            assess = non_empty[-1][1]

                # Skip header-like rows (only header keywords, no numbered LO)
                if not re.search(r'^\d+\.\s*', lo):
                    non_empty_vals = [str(c or '').strip() for c in row if str(c or '').strip()]
                    header_tokens = {'learning outcome', 'content', 'suggested assessment method', 'assessment method'}
                    filtered = [v for v in non_empty_vals if v.lower() not in header_tokens]
                    if non_empty_vals and not filtered:
                        continue

                # Continuation rows: LO empty but content/assessment present
                if not lo:
                    non_empty_vals = [str(c or '').strip() for c in row if str(c or '').strip()]
                    header_tokens = {'learning outcome', 'content', 'suggested assessment method', 'assessment method'}
                    non_empty_vals = [v for v in non_empty_vals if v.lower() not in header_tokens]
                    if non_empty_vals and last_outcome is not None:
                        continuation_text = "\n".join(non_empty_vals)
                        if re.search(r'\b(observation|written|oral)\b', continuation_text.lower()):
                            last_assess = f"{last_assess}\n{continuation_text}" if last_assess else continuation_text
                        else:
                            last_content = f"{last_content}\n{continuation_text}" if last_content else continuation_text
                        continue
                    # If no previous outcome, skip orphan continuation rows
                    if non_empty_vals and last_outcome is None:
                        continue

                # Skip header-like rows
                row_text = " ".join([str(c or '').strip() for c in row]).lower()
                header_keywords = ['learning outcome', 'content', 'suggested assessment', 'assessment method']
                if row_text and all(h in row_text for h in ['learning outcome', 'content']) and any(h in row_text for h in ['assessment', 'suggested assessment']):
                    continue
                if row_text in header_keywords:
                    continue
                if lo.strip().lower() in ['learning outcome', 'outcome'] and not content and not assess:
                    continue
                if content.strip().lower() == 'content' and not lo and not assess:
                    continue
                if assess.strip().lower() in ['assessment', 'assessment method', 'suggested assessment method'] and not lo and not content:
                    continue

                if lo or content or assess:
                    flush_last()
                    last_outcome = lo
                    last_content = content
                    last_assess = assess

                if len(self.debug_rows) < 20:
                    self.debug_rows.append({
                        'lo': lo,
                        'content': content,
                        'assess': assess,
                        'row': [str(c or '').strip() for c in row]
                    })

            # do not flush here; allow continuation across tables
            started = True
            if self.table_pages:
                last_table_page = self.table_pages[t_idx]
        flush_last()

        if outcomes:
            return outcomes

        # Fallback: parse from raw text lines
        lines = [l.strip() for l in self.raw_text.split('\n') if l.strip()]
        header_index = None
        for i, line in enumerate(lines):
            low = line.lower()
            if 'learning outcome' in low and ('content' in low or 'learning expectation' in low) and 'assessment' in low:
                header_index = i
                break

        if header_index is None:
            return []

        for line in lines[header_index + 1:]:
            parts = re.split(r'\s{2,}|\t+', line)
            if len(parts) >= 3:
                outcomes.append({
                    'learning_outcome': parts[0].strip(),
                    'learning_expectations': parts[1].strip(),
                    'learning_assessments': parts[2].strip()
                })
        return outcomes
    
    def _extract_section(self, keywords, limit=10):
        """Extract lines containing specific keywords"""
        if isinstance(keywords, str):
            keywords = [keywords]
        
        lines = self.raw_text.split('\n')
        matches = []
        
        for line in lines:
            line_lower = line.lower().strip()
            if line_lower and any(kw.lower() in line_lower for kw in keywords):
                # Clean up the line
                clean_line = line.strip()
                if clean_line and len(clean_line) > 10:  # Skip very short lines
                    matches.append(clean_line)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_matches = []
        for match in matches:
            if match not in seen:
                seen.add(match)
                unique_matches.append(match)
        
        return unique_matches[:limit]
    
    def get_results(self):
        """Return all extracted data as dictionary"""
        tables_preview = []
        for t_idx, table in enumerate(self.tables[:3]):
            preview_rows = []
            for row in (table or [])[:6]:
                preview_rows.append([str(c or '').strip() for c in row])
            tables_preview.append({
                'table_index': t_idx,
                'rows': preview_rows
            })

        return {
            'raw_text': self.raw_text,
            'page_count': self.page_count,
            'character_count': self.character_count,
            'word_count': self.word_count,
            'competencies': '\n'.join(self.competencies),
            'skills': '\n'.join(self.skills),
            'knowledge': '\n'.join(self.knowledge),
            'assessment_criteria': '\n'.join(self.assessment_criteria),
            'unit_code': self.unit_code,
            'outcomes': self.outcomes,
            'tables_preview': tables_preview,
            'debug_rows': self.debug_rows,
            'debug_indices': self.debug_indices,
            'total_time': self.total_time,
        }


def extract_pdf_data(pdf_file):
    """
    Convenience function to extract data from a PDF file
    
    Args:
        pdf_file: Django UploadedFile or file-like object
    
    Returns:
        dict: Extracted data
    """
    extractor = PDFExtractor(pdf_file)
    return extractor.extract()

