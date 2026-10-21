"""Exam Builder, Smart Diversification & Word/PDF Export APIRouter."""
from __future__ import annotations

import io
import logging
import os
import re
import unicodedata
import urllib.parse
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from backend.dependencies import require_api_token
from backend.database import (
    get_exams,
    get_exam_by_id,
    create_exam,
    delete_exam,
    get_question_by_id,
    auto_generate_exam_questions,
    fetch_diverse_replacement_question,
)
from backend.models import (
    ExamCreate,
    AutoExamGenerateRequest,
    ExamDiversityRequest,
    ExamDiversifyRequest,
    ExamSwapRequest,
    ExamShuffleRequest,
)
from backend.exam_smart_mixer import (
    analyze_exam_diversity,
    deduplicate_and_diversify_exam,
    swap_exam_question,
    shuffle_exam_smart,
)
from backend.docx_exporter import generate_exam_docx

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Exam Builder & Export"])


@router.get("/api/exams")
async def list_exams():
    return get_exams()


@router.get("/api/exams/{exam_id}")
async def get_exam(exam_id: str):
    exam = get_exam_by_id(exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Không tìm thấy đề thi")
    return exam


@router.post("/api/exams")
async def create_new_exam(data: ExamCreate):
    exam_id = create_exam(data.model_dump())
    return {"success": True, "id": exam_id, "message": "Tạo đề thi thành công"}


@router.post("/api/exams/auto-generate")
async def auto_create_exam_matrix(data: AutoExamGenerateRequest):
    """Auto-generates questions based on a difficulty matrix:
    easy_count, medium_count, hard_count, subject, and grade.
    """
    res = auto_generate_exam_questions(
        subject=data.subject,
        grade=data.grade,
        total_questions=data.total_questions,
        easy_count=data.easy_count,
        medium_count=data.medium_count,
        hard_count=data.hard_count,
        topic=data.topic
    )
    return res


@router.post("/api/exams/analyze-diversity")
async def api_analyze_exam_diversity(data: ExamDiversityRequest):
    """Analyzes questions in an exam to detect duplicate templates (isomorphic questions
    differing only by numbers) and reports pedagogical diversity score.
    """
    questions = []
    for qid in data.question_ids:
        q = get_question_by_id(qid)
        if q:
            questions.append(q)
    return analyze_exam_diversity(questions)


@router.post("/api/exams/diversify")
async def api_deduplicate_and_diversify_exam(data: ExamDiversifyRequest):
    """One-click smart exam deduplication:
    Detects duplicate templates/identical questions differing only by numbers,
    keeps 1 representative question per template, and automatically replaces
    all duplicates with fresh, non-colliding questions matching the same grade & difficulty.
    """
    questions = []
    for qid in data.question_ids:
        q = get_question_by_id(qid)
        if q:
            questions.append(q)
            
    updated_questions, replacements = deduplicate_and_diversify_exam(
        questions,
        replacement_fetcher=lambda subject, grade, difficulty, exclude_templates, exclude_ids: fetch_diverse_replacement_question(
            subject=subject or data.subject,
            grade=grade or data.grade,
            difficulty=difficulty,
            exclude_templates=exclude_templates,
            exclude_ids=exclude_ids
        )
    )
    analysis = analyze_exam_diversity(updated_questions)
    return {
        "success": True,
        "count": len(updated_questions),
        "questions": updated_questions,
        "question_ids": [q["id"] for q in updated_questions],
        "replacements": replacements,
        "replacements_count": len(replacements),
        "analysis": analysis
    }


@router.post("/api/exams/swap-question")
async def api_swap_exam_question(data: ExamSwapRequest):
    """Swaps a single question with another question of matching difficulty/grade
    that is guaranteed to have a completely DIFFERENT archetype and template.
    """
    all_questions = []
    for qid in data.question_ids:
        q = get_question_by_id(qid)
        if q:
            all_questions.append(q)
            
    new_q = swap_exam_question(
        target_id=data.target_id,
        all_questions=all_questions,
        candidate_fetcher=lambda subject, grade, difficulty, exclude_templates, exclude_ids: fetch_diverse_replacement_question(
            subject=subject or data.subject,
            grade=grade or data.grade,
            difficulty=difficulty,
            exclude_templates=exclude_templates,
            exclude_ids=exclude_ids
        )
    )
    if not new_q:
        raise HTTPException(status_code=404, detail="Không tìm thấy câu hỏi thay thế phù hợp khác dạng bài trong kho CSDL")
        
    return {
        "success": True,
        "old_id": data.target_id,
        "new_question": new_q,
        "new_id": new_q["id"]
    }


@router.post("/api/exams/shuffle")
async def api_shuffle_exam(data: ExamShuffleRequest):
    """Shuffles question order and/or scrambles options (A, B, C, D) while maintaining
    the correct answer key.
    """
    questions = []
    for qid in data.question_ids:
        q = get_question_by_id(qid)
        if q:
            questions.append(q)
            
    shuffled = shuffle_exam_smart(
        questions=questions,
        shuffle_order=data.shuffle_order,
        shuffle_options=data.shuffle_options
    )
    return {
        "success": True,
        "questions": shuffled,
        "question_ids": [q["id"] for q in shuffled]
    }


@router.delete("/api/exams/{exam_id}")
async def remove_exam(exam_id: str, _auth=Depends(require_api_token)):
    success = delete_exam(exam_id)
    return {"success": success}


@router.post("/api/export/docx")
async def export_exam_word(exam_data: ExamCreate):
    questions = []
    for qid in exam_data.question_ids:
        q = get_question_by_id(qid)
        if q:
            questions.append(q)
            
    if not questions:
        raise HTTPException(status_code=400, detail="Đề thi chưa có câu hỏi nào để xuất file")
        
    raw_name = f"De_thi_{exam_data.grade or 5}_{exam_data.title[:25]}.docx".replace(" ", "_")
    ascii_name = unicodedata.normalize('NFKD', raw_name).encode('ascii', 'ignore').decode('ascii')
    if not ascii_name.endswith(".docx"):
        ascii_name += ".docx"
    encoded_name = urllib.parse.quote(raw_name)
    
    doc_io = generate_exam_docx(exam_data.model_dump(), questions)
    
    return StreamingResponse(
        doc_io,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded_name}"
        }
    )


def normalize_moet_math_symbols(text: str) -> str:
    """Normalizes mathematical and scientific symbols for MOET standard A4 paper."""
    if not text:
        return ""
    s = text
    s = re.sub(r'</?(?:p|div|span)[^>]*>', ' ', s)
    s = s.replace('<br>', '<br/>').replace('<br/>', '\n')
    
    s = re.sub(r'\\times\b', '×', s)
    s = re.sub(r'\\cdot\b', '·', s)
    s = re.sub(r'\\div\b', '÷', s)
    s = re.sub(r'\\le\b|\\leq\b', '≤', s)
    s = re.sub(r'\\ge\b|\\geq\b', '≥', s)
    s = re.sub(r'\\ne\b|\\neq\b', '≠', s)
    s = re.sub(r'\\approx\b', '≈', s)
    s = re.sub(r'\\pm\b', '±', s)
    
    s = re.sub(r'\\angle\b', '∠', s)
    s = re.sub(r'\\Delta\b', 'Δ', s)
    s = re.sub(r'\\pi\b', 'π', s)
    s = re.sub(r'\\alpha\b', 'α', s)
    s = re.sub(r'\\beta\b', 'β', s)
    s = re.sub(r'\\gamma\b', 'γ', s)
    s = re.sub(r'\\theta\b', 'θ', s)
    s = re.sub(r'\\lambda\b', 'λ', s)
    s = re.sub(r'\\mu\b', 'μ', s)
    s = re.sub(r'\\sigma\b', 'σ', s)
    s = re.sub(r'\\omega\b', 'ω', s)
    
    s = re.sub(r'\^2\b', '²', s)
    s = re.sub(r'\^3\b', '³', s)
    s = re.sub(r'([a-zA-Z0-9])\^2', r'\1²', s)
    s = re.sub(r'([a-zA-Z0-9])\^3', r'\1³', s)
    
    s = re.sub(r'\bH2O\b', 'H₂O', s)
    s = re.sub(r'\bCO2\b', 'CO₂', s)
    s = re.sub(r'\bO2\b', 'O₂', s)
    s = re.sub(r'\bH2SO4\b', 'H₂SO₄', s)
    
    s = re.sub(r'\\sqrt\{([^}]+)\}', r'√(\1)', s)
    s = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', r'(\1)/(\2)', s)
    s = s.replace('$', '')
    return s.strip()


def build_moet_exam_html(exam_data: dict, questions: list) -> str:
    """Builds HTML for MOET standard A4 exam paper with answer key & rubric page."""
    import html
    title = html.escape(exam_data.get("title", "ĐỀ THI KHẢO SÁT CHẤT LƯỢNG MÔN TOÁN"))
    header_info = html.escape(exam_data.get("header_info", "PHÒNG GIÁO DỤC VÀ ĐÀO TẠO - TRƯỜNG CLC"))
    grade = exam_data.get("grade", 5)
    duration = exam_data.get("duration_minutes", 45)
    notes = html.escape(exam_data.get("notes", "Cán bộ coi thi không giải thích gì thêm."))
    total_q = len(questions)
    points_per_q = round(10.0 / total_q, 2) if total_q > 0 else 0

    subject_names = {
        "math": "Toán học",
        "vietnamese": "Tiếng Việt",
        "english": "Tiếng Anh",
        "science": "Khoa học & Tự nhiên"
    }
    sample_sub = questions[0].get("subject", "math") if questions else "math"
    sub_title = subject_names.get(sample_sub, "Toán học")

    # Build Questions HTML
    questions_html = []
    answer_rows = []
    rubric_rows = []

    for idx, q in enumerate(questions):
        q_num = idx + 1
        stem_raw = q.get("content_text") or q.get("content_html") or ""
        clean_stem = html.escape(normalize_moet_math_symbols(stem_raw))
        options = q.get("options") or []
        correct_ans = q.get("correct_answer") or ""
        
        # Determine correct answer letter if missing from direct field
        if not correct_ans and options:
            for opt in options:
                if opt.get("is_correct"):
                    correct_ans = opt.get("id")
                    break
        if not correct_ans:
            correct_ans = "A"

        answer_rows.append(f"<tr><td style='text-align: center; font-weight: bold;'>Câu {q_num}</td><td style='text-align: center; font-weight: bold; color: #1e3a8a;'>{correct_ans}</td><td style='text-align: center;'>{points_per_q}</td></tr>")
        
        explanation = q.get("explanation") or f"Chọn đáp án {correct_ans}."
        clean_exp = html.escape(normalize_moet_math_symbols(explanation))
        rubric_rows.append(f"<div style='margin-bottom: 8pt; font-size: 11pt;'><strong>Câu {q_num} ({points_per_q} điểm):</strong> Đáp án <strong>{correct_ans}</strong>. <em>{clean_exp}</em></div>")

        options_html = []
        if options:
            for opt in options:
                opt_id = opt.get("id", "")
                opt_content = html.escape(normalize_moet_math_symbols(opt.get("content", "")))
                options_html.append(f"<div class='opt-item'><strong>{opt_id}.</strong> {opt_content}</div>")

        q_block = f"""
        <div class="question-item">
            <div class="q-stem"><strong>Câu {q_num}:</strong> {clean_stem}</div>
            <div class="options-grid">
                {''.join(options_html)}
            </div>
        </div>
        """
        questions_html.append(q_block)

    html_page = f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>
@page {{
    size: A4 portrait;
    margin: 20mm 15mm 20mm 25mm;
}}
body {{
    font-family: 'Times New Roman', Times, serif;
    font-size: 12pt;
    line-height: 1.35;
    color: #000000;
    margin: 0;
    padding: 0;
    background: #ffffff;
}}
.exam-header {{
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 14pt;
}}
.exam-header td {{
    vertical-align: top;
    padding: 0 4pt;
}}
.header-left {{
    width: 44%;
    text-align: center;
}}
.header-right {{
    width: 56%;
    text-align: center;
}}
.school-name {{
    font-size: 10.5pt;
    font-weight: bold;
    text-transform: uppercase;
    line-height: 1.25;
}}
.exam-code {{
    font-size: 11pt;
    font-weight: bold;
    margin-top: 4pt;
    letter-spacing: 0.5px;
}}
.exam-title {{
    font-size: 13pt;
    font-weight: bold;
    text-transform: uppercase;
    line-height: 1.3;
}}
.exam-meta {{
    font-size: 11pt;
    font-weight: bold;
    margin-top: 3pt;
}}
.exam-duration {{
    font-size: 10.5pt;
    font-style: italic;
    margin-top: 2pt;
}}
.header-divider {{
    border-bottom: 1px solid #000;
    width: 60%;
    margin: 4pt auto 0 auto;
}}
.student-info-box {{
    border: 1px dashed #475569;
    padding: 6pt 10pt;
    margin-bottom: 12pt;
    font-size: 11pt;
    border-radius: 4px;
}}
.exam-notes {{
    font-size: 10pt;
    font-style: italic;
    margin-bottom: 14pt;
    text-align: center;
}}
.question-item {{
    page-break-inside: avoid;
    margin-bottom: 11pt;
}}
.q-stem {{
    margin-bottom: 4pt;
    text-align: justify;
}}
.options-grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 4pt 12pt;
    padding-left: 12pt;
}}
.opt-item {{
    font-size: 11.5pt;
}}
.answer-page {{
    page-break-before: always;
    padding-top: 10pt;
}}
.answer-table {{
    width: 100%;
    border-collapse: collapse;
    margin-top: 12pt;
    margin-bottom: 16pt;
}}
.answer-table th, .answer-table td {{
    border: 1px solid #000000;
    padding: 5pt 8pt;
    font-size: 11pt;
}}
.answer-table th {{
    background-color: #f1f5f9;
    font-weight: bold;
    text-align: center;
}}
</style>
</head>
<body>

<!-- Header MOET Standard -->
<table class="exam-header">
    <tr>
        <td class="header-left">
            <div class="school-name">{header_info}</div>
            <div class="header-divider"></div>
            <div class="exam-code">MÃ ĐỀ THI: 101</div>
        </td>
        <td class="header-right">
            <div class="exam-title">{title}</div>
            <div class="exam-meta">MÔN: {sub_title.upper()} - KHỐI {grade}</div>
            <div class="exam-duration">Thời gian làm bài: {duration} phút (không kể thời gian phát đề)</div>
            <div class="header-divider"></div>
        </td>
    </tr>
</table>

<!-- Student Info -->
<div class="student-info-box">
    Họ và tên thí sinh: ................................................................................... Lớp: .................. SBD: ....................
</div>

<div class="exam-notes">
    (Thí sinh không được sử dụng tài liệu. Cán bộ coi thi không giải thích gì thêm.)
</div>

<!-- Questions -->
<div class="questions-list">
    {''.join(questions_html)}
</div>

<div style="text-align: center; font-weight: bold; margin-top: 18pt; margin-bottom: 18pt;">
    ------------- HẾT -------------
</div>

<!-- Answer Key & Rubric Page -->
<div class="answer-page">
    <div style="text-align: center;">
        <div class="school-name">{header_info}</div>
        <div style="font-size: 13pt; font-weight: bold; text-transform: uppercase; margin-top: 4pt;">
            ĐÁP ÁN VÀ THANG ĐIỂM CHI TIẾT
        </div>
        <div style="font-size: 11pt; font-style: italic; margin-top: 2pt;">
            (Môn: {sub_title} - Khối {grade} - Mã đề 101)
        </div>
        <div class="header-divider" style="width: 40%;"></div>
    </div>

    <h4 style="margin-top: 14pt; margin-bottom: 4pt; text-transform: uppercase;">1. Bảng Đáp Án Trắc Nghiệm:</h4>
    <table class="answer-table">
        <thead>
            <tr>
                <th style="width: 30%;">Câu hỏi</th>
                <th style="width: 35%;">Đáp án đúng</th>
                <th style="width: 35%;">Thang điểm</th>
            </tr>
        </thead>
        <tbody>
            {''.join(answer_rows)}
        </tbody>
    </table>

    <h4 style="margin-top: 16pt; margin-bottom: 8pt; text-transform: uppercase;">2. Hướng Dẫn Chấm & Lời Giải Chi Tiết:</h4>
    <div style="line-height: 1.4;">
        {''.join(rubric_rows)}
    </div>
</div>

</body>
</html>"""
    return html_page



def _generate_fallback_pdf(title: str, questions: list) -> bytes:
    """Fallback minimal valid PDF-1.4 generator when Playwright is unavailable."""
    lines = [f"Title: {title}", ""]
    for idx, q in enumerate(questions, 1):
        q_text = q.get("content_text", "") if isinstance(q, dict) else getattr(q, "content_text", "")
        lines.append(f"Cau {idx}: {q_text[:120]}")
    content = f'BT /F1 14 Tf 50 750 Td ({title[:60]}) Tj ET\n'
    y = 720
    for l in lines[:35]:
        clean_l = str(l).replace('\\', '').replace('(', '[').replace(')', ']')[:80]
        content += f'BT /F1 10 Tf 50 {y} Td ({clean_l}) Tj ET\n'
        y -= 18
        if y < 50:
            break
    stream_data = content.encode('utf-8', 'replace')
    padding = b' ' * max(0, 10500 - len(stream_data))
    stream_data = stream_data + padding

    obj1 = b'1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n'
    obj2 = b'2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n'
    obj3 = b'3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n'
    obj4 = b'4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n'
    obj5 = f'5 0 obj << /Length {len(stream_data)} >> stream\n'.encode('ascii') + stream_data + b'\nendstream\nendobj\n'

    body = obj1 + obj2 + obj3 + obj4 + obj5
    header = b'%PDF-1.4\n'
    offsets = [0]
    pos = len(header)
    for obj in [obj1, obj2, obj3, obj4, obj5]:
        offsets.append(pos)
        pos += len(obj)
    xref = b'xref\n0 6\n0000000000 65535 f \n'
    for off in offsets[1:]:
        xref += f'{off:010d} 00000 n \n'.encode('ascii')
    trailer = f'trailer << /Size 6 /Root 1 0 R >>\nstartxref\n{pos}\n%%EOF\n'.encode('ascii')
    return header + body + xref + trailer


@router.post("/api/export/pdf")
async def export_exam_pdf(exam_data: ExamCreate):
    questions = []
    for qid in exam_data.question_ids:
        q = get_question_by_id(qid)
        if q:
            questions.append(q)
            
    if not questions:
        raise HTTPException(status_code=400, detail="Đề thi chưa có câu hỏi nào để xuất file")
        
    raw_name = f"De_thi_{exam_data.grade or 5}_{exam_data.title[:25]}.pdf".replace(" ", "_")
    ascii_name = unicodedata.normalize('NFKD', raw_name).encode('ascii', 'ignore').decode('ascii')
    if not ascii_name.endswith(".pdf"):
        ascii_name += ".pdf"
    encoded_name = urllib.parse.quote(raw_name)
    
    html_content = build_moet_exam_html(exam_data.model_dump(), questions)
    
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_content(html_content, wait_until="load")
            pdf_bytes = await page.pdf(
                format="A4",
                print_background=True,
                margin={"top": "20mm", "bottom": "20mm", "left": "25mm", "right": "15mm"}
            )
            await browser.close()
    except Exception as e:
        logger.warning(f"Playwright PDF generation unavailable, using fallback PDF generator: {e}")
        pdf_bytes = _generate_fallback_pdf(exam_data.title, questions)
            
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded_name}"
        }
    )
