from __future__ import annotations
import os
import io
import re
from typing import List, Dict, Any
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

MEDIA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "media")

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """Set cell padding in twips."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def clean_for_docx(text: str) -> str:
    """Removes HTML tags and cleans LaTeX markers for Word readable text."""
    if not text:
        return ""
    # Strip HTML tags
    clean = re.sub(r'<[^>]+>', '', text)
    # Simplify common LaTeX symbols to readable text if needed
    clean = clean.replace(r'\times', '×').replace(r'\div', '÷').replace(r'\le', '≤').replace(r'\ge', '≥')
    clean = clean.replace(r'\frac', '').replace(r'\sqrt', '√')
    clean = clean.replace('\\', '').replace('$', '')
    clean = re.sub(r'[{}]', '', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean

def generate_exam_docx(exam_data: Dict[str, Any], questions: List[Dict[str, Any]]) -> io.BytesIO:
    """
    Generates a professionally styled Microsoft Word (.docx) exam paper.
    """
    doc = Document()
    
    # Page setup: Standard A4, 2cm margins
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(0.85)
        section.right_margin = Inches(0.75)
        
    # Default Normal Style: Times New Roman, 12pt
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Times New Roman'
    normal_style.font.size = Pt(12)
    normal_style.font.color.rgb = RGBColor(15, 23, 42)
    normal_style.paragraph_format.line_spacing = 1.2
    normal_style.paragraph_format.space_after = Pt(4)
    
    # 1. Header Table (2 Columns: Left info & Right exam title)
    header_table = doc.add_table(rows=1, cols=2)
    header_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    header_table.autofit = False
    
    # Remove borders for header table
    for row in header_table.rows:
        for cell in row.cells:
            tcPr = cell._tc.get_or_add_tcPr()
            tcBorders = parse_xml(r'''
                <w:tcBorders xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
                    <w:top w:val="none"/>
                    <w:left w:val="none"/>
                    <w:bottom w:val="none"/>
                    <w:right w:val="none"/>
                </w:tcBorders>
            ''')
            tcPr.append(tcBorders)
            
    header_table.columns[0].width = Inches(3.2)
    header_table.columns[1].width = Inches(3.6)
    
    cell_left = header_table.cell(0, 0)
    p_left = cell_left.paragraphs[0]
    p_left.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_school = p_left.add_run(exam_data.get("header_info") or "PHÒNG GIÁO DỤC VÀ ĐÀO TẠO\nTRƯỜNG TIỂU HỌC & THCS CLC")
    r_school.font.size = Pt(10)
    r_school.font.bold = True
    
    p_left2 = cell_left.add_paragraph()
    p_left2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    exam_code = exam_data.get("exam_code") or "101"
    r_code = p_left2.add_run(f"MÃ ĐỀ THI: {exam_code}")
    r_code.font.bold = True
    r_code.font.size = Pt(11)
    
    cell_right = header_table.cell(0, 1)
    p_right = cell_right.paragraphs[0]
    p_right.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_title = p_right.add_run(f"{exam_data.get('title', 'ĐỀ THI KHẢO SÁT CHẤT LƯỢNG TOÁN')}\n")
    r_title.font.bold = True
    r_title.font.size = Pt(12)
    
    grade = exam_data.get("grade", 5)
    duration = exam_data.get("duration_minutes", 45)
    r_sub = p_right.add_run(f"Khối lớp: {grade} — Thời gian làm bài: {duration} phút\n(Không kể thời gian phát đề)")
    r_sub.font.italic = True
    r_sub.font.size = Pt(10.5)
    
    # Student info box
    doc.add_paragraph()
    p_student = doc.add_paragraph()
    p_student.paragraph_format.space_after = Pt(8)
    r_s = p_student.add_run("Họ và tên thí sinh: ............................................................................ Số báo danh: ..................... Lớp: .............")
    r_s.font.size = Pt(11)
    r_s.font.italic = True
    
    # Separator
    p_sep = doc.add_paragraph()
    p_sep.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_sep = p_sep.add_run("──────────────── • ❖ • ────────────────")
    r_sep.font.color.rgb = RGBColor(100, 116, 139)
    p_sep.paragraph_format.space_after = Pt(12)
    
    # 2. Questions Section
    for idx, q in enumerate(questions, 1):
        p_q = doc.add_paragraph()
        p_q.paragraph_format.space_before = Pt(6)
        p_q.paragraph_format.space_after = Pt(3)
        
        # Question label
        r_lbl = p_q.add_run(f"Câu {idx}: ")
        r_lbl.font.bold = True
        r_lbl.font.color.rgb = RGBColor(37, 99, 235)  # Cobalt blue
        
        # Content
        content = clean_for_docx(q.get("content_html") or q.get("content_text") or "")
        p_q.add_run(content)
        
        # If question has local images, insert them
        images = q.get("images", [])
        for img_rel in images:
            if isinstance(img_rel, str) and img_rel.startswith("/media/"):
                img_path = os.path.join(MEDIA_DIR, os.path.basename(img_rel))
                if os.path.exists(img_path):
                    try:
                        p_img = doc.add_paragraph()
                        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        p_img.paragraph_format.space_after = Pt(4)
                        p_img.add_run().add_picture(img_path, width=Inches(3.2))
                    except Exception as e:
                        print(f"Error inserting picture {img_path}: {e}")
                        
        # Options (A, B, C, D)
        options = q.get("options", [])
        if options and len(options) > 0:
            # Check length of options to determine 4-col or 2-col or vertical
            max_len = max([len(clean_for_docx(opt.get("content", ""))) for opt in options]) if options else 0
            
            if len(options) == 4 and max_len < 20:
                # 4 options in 1 line
                p_opts = doc.add_paragraph()
                p_opts.paragraph_format.left_indent = Inches(0.3)
                p_opts.paragraph_format.space_after = Pt(4)
                line_text = ""
                for opt in options:
                    oid = opt.get("id", "")
                    otxt = clean_for_docx(opt.get("content", ""))
                    line_text += f"{oid}. {otxt}               "
                p_opts.add_run(line_text.strip())
            elif len(options) == 4 and max_len < 45:
                # 2 lines x 2 columns
                p_opts1 = doc.add_paragraph()
                p_opts1.paragraph_format.left_indent = Inches(0.3)
                p_opts1.paragraph_format.space_after = Pt(2)
                p_opts1.add_run(f"A. {clean_for_docx(options[0].get('content', ''))}                                      B. {clean_for_docx(options[1].get('content', ''))}")
                
                p_opts2 = doc.add_paragraph()
                p_opts2.paragraph_format.left_indent = Inches(0.3)
                p_opts2.paragraph_format.space_after = Pt(4)
                p_opts2.add_run(f"C. {clean_for_docx(options[2].get('content', ''))}                                      D. {clean_for_docx(options[3].get('content', ''))}")
            else:
                # 1 option per line
                for opt in options:
                    p_opt = doc.add_paragraph()
                    p_opt.paragraph_format.left_indent = Inches(0.3)
                    p_opt.paragraph_format.space_after = Pt(2)
                    r_oid = p_opt.add_run(f"{opt.get('id', '')}. ")
                    r_oid.font.bold = True
                    p_opt.add_run(clean_for_docx(opt.get("content", "")))
                    
    # End of test marker
    p_end = doc.add_paragraph()
    p_end.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_end.paragraph_format.space_before = Pt(14)
    r_end = p_end.add_run("─── HẾT ───\n(Cán bộ coi thi không giải thích gì thêm)")
    r_end.font.bold = True
    r_end.font.size = Pt(11)
    
    # 3. Answer Key & Detailed Solution (On New Page)
    doc.add_page_break()
    p_ans_header = doc.add_paragraph()
    p_ans_header.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_ah = p_ans_header.add_run("BẢNG ĐÁP ÁN & HƯỚNG DẪN GIẢI CHI TIẾT")
    r_ah.font.bold = True
    r_ah.font.size = Pt(14)
    r_ah.font.color.rgb = RGBColor(16, 185, 129)  # Emerald
    
    # Answer summary grid
    # E.g. Table with columns for questions
    num_q = len(questions)
    cols = min(10, num_q) if num_q > 0 else 1
    rows_needed = (num_q + cols - 1) // cols
    
    if num_q > 0:
        ans_table = doc.add_table(rows=rows_needed * 2, cols=cols)
        ans_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        
        for r_idx in range(rows_needed):
            for c_idx in range(cols):
                q_num = r_idx * cols + c_idx + 1
                if q_num <= num_q:
                    q_item = questions[q_num - 1]
                    ans = q_item.get("correct_answer") or "-"
                    
                    cell_top = ans_table.cell(r_idx * 2, c_idx)
                    cell_top.text = f"Câu {q_num}"
                    cell_top.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                    cell_top.paragraphs[0].runs[0].font.bold = True
                    cell_top.paragraphs[0].runs[0].font.size = Pt(10)
                    
                    cell_bot = ans_table.cell(r_idx * 2 + 1, c_idx)
                    cell_bot.text = str(ans)
                    cell_bot.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                    cell_bot.paragraphs[0].runs[0].font.bold = True
                    cell_bot.paragraphs[0].runs[0].font.size = Pt(11)
                    cell_bot.paragraphs[0].runs[0].font.color.rgb = RGBColor(220, 38, 38)
                    
                    set_cell_margins(cell_top, top=60, bottom=60, left=80, right=80)
                    set_cell_margins(cell_bot, top=60, bottom=60, left=80, right=80)
                    
        # Apply borders to table
        for r in ans_table.rows:
            for c in r.cells:
                tcPr = c._tc.get_or_add_tcPr()
                tcBorders = parse_xml(r'''
                    <w:tcBorders xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
                        <w:top w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>
                        <w:left w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>
                        <w:bottom w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>
                        <w:right w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>
                    </w:tcBorders>
                ''')
                tcPr.append(tcBorders)
                
    doc.add_paragraph()
    
    # Detailed explanations
    p_exp_h = doc.add_paragraph()
    r_eh = p_exp_h.add_run("Lời giải chi tiết:")
    r_eh.font.bold = True
    r_eh.font.size = Pt(12)
    
    for idx, q in enumerate(questions, 1):
        exp = q.get("explanation")
        ans = q.get("correct_answer") or "-"
        if exp or ans:
            p_e = doc.add_paragraph()
            p_e.paragraph_format.space_before = Pt(4)
            p_e.paragraph_format.space_after = Pt(2)
            r_c = p_e.add_run(f"Câu {idx} (Chọn {ans}): ")
            r_c.font.bold = True
            if exp:
                p_e.add_run(clean_for_docx(exp))
            else:
                p_e.add_run("Đáp án chính xác theo đề thi.")
                
    output = io.BytesIO()
    doc.save(output)
    output.seek(0)
    return output
