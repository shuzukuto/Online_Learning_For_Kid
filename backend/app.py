import os
import io
import asyncio
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse

from backend.database import (
    init_db, get_questions, get_question_by_id, insert_or_update_question,
    bulk_insert_questions, delete_question, get_stats, get_stats_count,
    create_exam, get_exams, get_exam_by_id, delete_exam,
    log_collector_event, get_collector_logs, clear_collector_logs,
    get_duplicate_questions_summary, clean_duplicate_questions,
    run_database_diagnostics, fix_database_issues, auto_generate_exam_questions,
    maybe_resequence_deferred
)
from backend.models import (
    QuestionCreate, QuestionUpdate, BulkQuestionCreate,
    ExamCreate, ScrapeRequest, AutoExamGenerateRequest, CleanDuplicatesRequest
)
from backend.normalizer import normalize_question_payload
from backend.docx_exporter import generate_exam_docx
from backend.pdf_extractor import extract_questions_from_pdf
from backend.scrapers.vioedu import login_vioedu, fetch_vioedu_arena_questions, parse_vioedu_question_data
from backend.scrapers.tnmath import login_tnmath, parse_tnmath_question_data

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
MEDIA_DIR = os.path.join(BASE_DIR, "data", "media")
os.makedirs(MEDIA_DIR, exist_ok=True)

# Initialize database
init_db()

app = FastAPI(
    title="EduQuest Pro API",
    description="Hệ thống Thu thập & Quản lý Ngân hàng Câu hỏi Thi trực tuyến",
    version="1.0.0"
)

@app.on_event("startup")
async def on_startup():
    init_db()
    maybe_resequence_deferred()  # Run any pending lazy resequence from previous session
    stats = get_stats()
    if stats.get("total_questions", 0) == 0:
        await init_sample_questions()

# Enable CORS for browser extension and external tools
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- Question Bank Endpoints -----------------

@app.get("/api/stats")
async def get_dashboard_stats():
    return get_stats()

@app.get("/api/stats/count")
async def get_question_count():
    """Lightweight endpoint for heartbeat polling — single COUNT query, no cache needed."""
    return {"total_questions": get_stats_count()}

@app.get("/api/questions")
async def list_questions(
    platform: Optional[str] = Query(None),
    grade: Optional[int] = Query(None),
    subject: Optional[str] = Query(None),
    topic: Optional[str] = Query(None),
    question_type: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    source_detail: Optional[str] = Query(None),
    only_duplicates: bool = Query(False),
    sort_by: str = Query("q_number_asc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=10000)
):
    items, total = get_questions(
        platform=platform,
        grade=grade,
        subject=subject,
        topic=topic,
        question_type=question_type,
        difficulty=difficulty,
        search=search,
        source_detail=source_detail,
        only_duplicates=only_duplicates,
        sort_by=sort_by,
        page=page,
        page_size=page_size
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total > 0 else 1
    }

@app.get("/api/questions/duplicates")
async def get_duplicates_summary():
    """Returns summary of all duplicate question groups in database."""
    return get_duplicate_questions_summary()

@app.post("/api/questions/duplicates/clean")
async def clean_duplicates(data: CleanDuplicatesRequest):
    """Cleans duplicate questions keeping the primary record or specific IDs."""
    res = clean_duplicate_questions(action=data.action, delete_ids=data.delete_ids)
    log_collector_event(
        platform="database",
        status="success",
        message=f"Đã dọn dẹp {res['deleted_count']} câu hỏi trùng lặp khỏi CSDL.",
        count=res['deleted_count']
    )
    return res

@app.get("/api/database/diagnostics")
async def get_db_diagnostics():
    """Runs a complete diagnostic health check on SQLite database."""
    return run_database_diagnostics()

@app.post("/api/database/diagnostics/fix")
async def fix_db_anomalies():
    """Auto-repairs database issues: cleans duplicates, fixes null subjects, vacuums DB."""
    res = fix_database_issues()
    log_collector_event(
        platform="database",
        status="success",
        message=f"Đã sửa lỗi CSDL: dọn dẹp {res['duplicates_cleaned']} câu trùng, chuẩn hóa {res['subjects_reclassified']} bộ môn.",
        count=res['duplicates_cleaned']
    )
    return res

@app.get("/api/questions/{question_id}")
async def get_question(question_id: str):
    q = get_question_by_id(question_id)
    if not q:
        raise HTTPException(status_code=404, detail="Không tìm thấy câu hỏi")
    return q

@app.post("/api/questions")
async def create_single_question(data: QuestionCreate):
    raw_dict = data.model_dump()
    normalized = await normalize_question_payload(raw_dict)
    from backend.normalizer import is_valid_question_payload
    valid, reason = is_valid_question_payload(normalized)
    if not valid:
        raise HTTPException(status_code=400, detail=f"Câu hỏi không hợp lệ: {reason}")
    q_id = insert_or_update_question(normalized)
    return {"success": True, "id": q_id, "message": "Lưu câu hỏi thành công"}

@app.post("/api/questions/bulk")
async def bulk_create_questions(data: BulkQuestionCreate):
    from backend.normalizer import is_valid_question_payload
    normalized_list = []
    skipped_count = 0
    for q in data.questions:
        norm = await normalize_question_payload(q.model_dump())
        valid, reason = is_valid_question_payload(norm)
        if not valid:
            skipped_count += 1
            continue
        normalized_list.append(norm)
    count = bulk_insert_questions(normalized_list)
    if count > 0:
        log_collector_event(
            platform=data.questions[0].source_platform if data.questions else "bulk",
            status="success",
            message=f"Đã nạp {count} câu hỏi qua Extension/API (bỏ qua {skipped_count} câu không hợp lệ)",
            count=count
        )
    return {"success": True, "inserted_count": count, "skipped_count": skipped_count}

@app.put("/api/questions/{question_id}")
async def update_question(question_id: str, data: QuestionUpdate):
    existing = get_question_by_id(question_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Câu hỏi không tồn tại")
    
    update_data = data.model_dump(exclude_unset=True)
    existing.update(update_data)
    normalized = await normalize_question_payload(existing)
    insert_or_update_question(normalized)
    return {"success": True, "id": question_id, "message": "Cập nhật thành công"}

@app.delete("/api/questions/{question_id}")
async def remove_question(question_id: str):
    success = delete_question(question_id)
    if not success:
        raise HTTPException(status_code=404, detail="Không tìm thấy câu hỏi để xóa")
    return {"success": True, "message": "Đã xóa câu hỏi"}

# ----------------- Exam Builder & Word Export -----------------

@app.get("/api/exams")
async def list_exams():
    return get_exams()

@app.get("/api/exams/{exam_id}")
async def get_exam(exam_id: str):
    exam = get_exam_by_id(exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Không tìm thấy đề thi")
    return exam

@app.post("/api/exams")
async def create_new_exam(data: ExamCreate):
    exam_id = create_exam(data.model_dump())
    return {"success": True, "id": exam_id, "message": "Tạo đề thi thành công"}

@app.post("/api/exams/auto-generate")
async def auto_create_exam_matrix(data: AutoExamGenerateRequest):
    """
    Auto-generates questions based on a difficulty matrix:
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

@app.delete("/api/exams/{exam_id}")
async def remove_exam(exam_id: str):
    success = delete_exam(exam_id)
    return {"success": success}

@app.post("/api/export/docx")
async def export_exam_word(exam_data: ExamCreate):
    # Fetch questions for this exam
    questions = []
    for qid in exam_data.question_ids:
        q = get_question_by_id(qid)
        if q:
            questions.append(q)
            
    if not questions:
        raise HTTPException(status_code=400, detail="Đề thi chưa có câu hỏi nào để xuất file")
        
    import urllib.parse
    import unicodedata
    
    # Generate ASCII safe filename + UTF-8 RFC 5987 filename
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

# ----------------- PDF Importer (TIMO, HKIMO, ASMO) -----------------

@app.post("/api/import/pdf")
async def import_pdf_exam(
    file: UploadFile = File(...),
    save_to_bank: bool = Form(False)
):
    content = await file.read()
    extracted_questions = extract_questions_from_pdf(content, filename=file.filename)
    
    saved_count = 0
    if save_to_bank and extracted_questions:
        normalized_list = []
        for q in extracted_questions:
            norm = await normalize_question_payload(q)
            normalized_list.append(norm)
        saved_count = bulk_insert_questions(normalized_list)
        log_collector_event(
            platform=extracted_questions[0]["source_platform"],
            status="success",
            message=f"Bóc tách file PDF: {file.filename}, lưu {saved_count} câu hỏi",
            count=saved_count
        )
        
    return {
        "success": True,
        "filename": file.filename,
        "total_extracted": len(extracted_questions),
        "saved_to_bank": save_to_bank,
        "saved_count": saved_count,
        "preview_questions": extracted_questions
    }

# ----------------- Automated Scraper Runner -----------------

@app.post("/api/collect/run")
async def run_collector_task(req: ScrapeRequest):
    platform = req.platform.lower()
    
    if platform == "vioedu":
        if req.action == "login":
            res = await login_vioedu(req.username, req.password)
            return res
        elif req.action == "fetch_arena":
            questions = await fetch_vioedu_arena_questions(req.token, req.round_id or "1", grade=req.grade or 5)
            normalized_list = [await normalize_question_payload(q) for q in questions]
            inserted = bulk_insert_questions(normalized_list)
            log_collector_event("vioedu", "success", f"Thu thập Đấu trường #{req.round_id}", inserted)
            return {"success": True, "count": inserted, "questions": normalized_list}
            
    elif platform == "tnmath":
        if req.action == "login":
            res = await login_tnmath(req.username, req.password)
            return res
            
    return {"success": False, "error": "Chức năng hoặc nền tảng chưa được hỗ trợ trực tiếp. Vui lòng sử dụng Tiện ích Extension hoặc nạp PDF."}

@app.get("/api/collect/logs")
async def get_logs(limit: int = 50):
    return get_collector_logs(limit)

@app.post("/api/collect/logs/sync")
async def sync_collector_log(payload: dict):
    platform = payload.get("platform", "extension")
    status = payload.get("status", "info")
    message = payload.get("message", "")
    count = int(payload.get("count", 0))
    if message:
        log_collector_event(platform=platform, status=status, message=message, count=count)
    return {"success": True}

@app.delete("/api/collect/logs")
async def delete_logs():
    clear_collector_logs()
    return {"success": True, "message": "Đã xóa toàn bộ nhật ký"}

# ----------------- Sample Data Seeder -----------------

@app.post("/api/init-samples")
async def init_sample_questions():
    """Seeds authentic sample math questions from VioEdu, Trạng Nguyên, TIMO, HKIMO, and ASMO."""
    samples = [
        # 1. VioEdu Grade 5 - Fractions
        {
            "id": "sample_vioedu_001",
            "source_platform": "vioedu",
            "source_url": "https://vio.edu.vn",
            "exam_name": "Đấu trường VioEdu - Vòng Sơ khảo Cấp Quận 2025",
            "grade": 5,
            "subject": "math",
            "topic": "Phân số và Hỗn số",
            "question_type": "single_choice",
            "content_html": "<p>Tính giá trị của biểu thức sau: $A = \\frac{1}{2} + \\frac{1}{6} + \\frac{1}{12} + \\frac{1}{20} + \\frac{1}{30}$</p>",
            "content_text": "Tính giá trị của biểu thức sau: A = 1/2 + 1/6 + 1/12 + 1/20 + 1/30",
            "images": [],
            "options": [
                {"id": "A", "content": "$\\frac{5}{6}$", "is_correct": True},
                {"id": "B", "content": "$\\frac{4}{5}$", "is_correct": False},
                {"id": "C", "content": "$\\frac{1}{6}$", "is_correct": False},
                {"id": "D", "content": "$\\frac{7}{10}$", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Ta có: $\\frac{1}{2} = 1 - \\frac{1}{2}$, $\\frac{1}{6} = \\frac{1}{2} - \\frac{1}{3}$, $\\frac{1}{12} = \\frac{1}{3} - \\frac{1}{4}$, $\\frac{1}{20} = \\frac{1}{4} - \\frac{1}{5}$, $\\frac{1}{30} = \\frac{1}{5} - \\frac{1}{6}$.\nCộng vế với vế ta được: $A = 1 - \\frac{1}{6} = \\frac{5}{6}$.",
            "difficulty": "medium"
        },
        # 2. VioEdu Grade 5 - Geometry Speed/Distance
        {
            "id": "sample_vioedu_002",
            "source_platform": "vioedu",
            "source_url": "https://vio.edu.vn",
            "exam_name": "Đấu trường VioEdu - Vòng Chung kết Tỉnh",
            "grade": 5,
            "subject": "math",
            "topic": "Chuyển động đều",
            "question_type": "fill_blank",
            "content_html": "<p>Hai thành phố $A$ và $B$ cách nhau $165\\text{ km}$. Lúc 7 giờ sáng, một ô tô đi từ $A$ đến $B$ với vận tốc $50\\text{ km/h}$, đồng thời một xe máy đi từ $B$ về $A$ với vận tốc $32.5\\text{ km/h}$. Hỏi hai xe gặp nhau lúc mấy giờ?</p>",
            "content_text": "Hai thành phố A và B cách nhau 165 km. Lúc 7 giờ sáng, một ô tô đi từ A đến B với vận tốc 50 km/h, đồng thời một xe máy đi từ B về A với vận tốc 32.5 km/h. Hỏi hai xe gặp nhau lúc mấy giờ?",
            "images": [],
            "options": [],
            "correct_answer": "9",
            "explanation": "Tổng vận tốc hai xe là: $50 + 32.5 = 82.5\\text{ km/h}$.\nThời gian hai xe gặp nhau là: $165 : 82.5 = 2\\text{ giờ}$.\nHai xe gặp nhau lúc: $7 + 2 = 9\\text{ giờ}$.",
            "difficulty": "medium"
        },
        # 3. Trạng Nguyên Toán Học - Matching (Phép thuật Mèo con)
        {
            "id": "sample_tnmath_001",
            "source_platform": "tnmath",
            "source_url": "https://tnmath.edu.vn",
            "exam_name": "Trạng Nguyên Toàn Tài - Vòng Thi Hương",
            "grade": 4,
            "subject": "math",
            "topic": "Phép nhân và chia số tự nhiên",
            "question_type": "matching",
            "content_html": "<p>Em hãy nối các phép tính có giá trị bằng nhau:</p>",
            "content_text": "Em hãy nối các phép tính có giá trị bằng nhau",
            "images": [],
            "options": [
                {"id": "pair_1", "content": "$25 \\times 4$ ↔ $100$", "is_correct": True},
                {"id": "pair_2", "content": "$125 \\times 8$ ↔ $1000$", "is_correct": True},
                {"id": "pair_3", "content": "$360 : 6$ ↔ $60$", "is_correct": True},
                {"id": "pair_4", "content": "$45 \\times 2$ ↔ $90$", "is_correct": True}
            ],
            "correct_answer": "Nối đúng 4 cặp tương ứng",
            "explanation": "25 x 4 = 100; 125 x 8 = 1000; 360 : 6 = 60; 45 x 2 = 90.",
            "difficulty": "easy"
        },
        # 4. Trạng Nguyên Toán Học - Chuột vàng tài ba
        {
            "id": "sample_tnmath_002",
            "source_platform": "tnmath",
            "source_url": "https://tnmath.edu.vn",
            "exam_name": "Trạng Nguyên Toán Học - Vòng Hội",
            "grade": 5,
            "subject": "math",
            "topic": "Hình học - Diện tích hình thang",
            "question_type": "single_choice",
            "content_html": "<p>Một thửa ruộng hình thang có đáy lớn $120\\text{ m}$, đáy bé bằng $\\frac{2}{3}$ đáy lớn, chiều cao bằng trung bình cộng hai đáy. Diện tích thửa ruộng đó là bao nhiêu mét vuông?</p>",
            "content_text": "Một thửa ruộng hình thang có đáy lớn 120 m, đáy bé bằng 2/3 đáy lớn, chiều cao bằng trung bình cộng hai đáy. Diện tích thửa ruộng đó là bao nhiêu mét vuông?",
            "images": [],
            "options": [
                {"id": "A", "content": "$10000\\text{ m}^2$", "is_correct": True},
                {"id": "B", "content": "$8000\\text{ m}^2$", "is_correct": False},
                {"id": "C", "content": "$12000\\text{ m}^2$", "is_correct": False},
                {"id": "D", "content": "$9600\\text{ m}^2$", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Đáy bé hình thang là: $120 \\times \\frac{2}{3} = 80\\text{ m}$.\nChiều cao hình thang là: $(120 + 80) : 2 = 100\\text{ m}$.\nDiện tích thửa ruộng là: $\\frac{(120 + 80) \\times 100}{2} = 10000\\text{ m}^2$.",
            "difficulty": "medium"
        },
        # 5. TIMO (Thailand International Mathematical Olympiad) - Combinatorics
        {
            "id": "sample_timo_001",
            "source_platform": "timo",
            "source_url": "https://lmsfermat.edu.vn",
            "exam_name": "TIMO National Final 2024 - Secondary 1",
            "grade": 7,
            "subject": "math",
            "topic": "Tổ hợp & Logic (Combinatorics)",
            "question_type": "single_choice",
            "content_html": "<p>How many 3-digit numbers are there such that the sum of their digits is an odd number?<br/><i>(Có bao nhiêu số có 3 chữ số sao cho tổng các chữ số của nó là một số lẻ?)</i></p>",
            "content_text": "How many 3-digit numbers are there such that the sum of their digits is an odd number? (Có bao nhiêu số có 3 chữ số sao cho tổng các chữ số của nó là một số lẻ?)",
            "images": [],
            "options": [
                {"id": "A", "content": "450", "is_correct": True},
                {"id": "B", "content": "440", "is_correct": False},
                {"id": "C", "content": "500", "is_correct": False},
                {"id": "D", "content": "400", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Số có 3 chữ số từ 100 đến 999 có tổng cộng 900 số. Trong đó, chữ số hàng đơn vị thay đổi xen kẽ giữa chẵn và lẻ khiến tổng các chữ số luân phiên chẵn và lẻ với xác suất 1/2. Do đó có đúng: $900 : 2 = 450$ số thỏa mãn.",
            "difficulty": "olympiad"
        },
        # 6. HKIMO (Hong Kong International Mathematical Olympiad) - Number Theory
        {
            "id": "sample_hkimo_001",
            "source_platform": "hkimo",
            "source_url": "https://lmsfermat.edu.vn",
            "exam_name": "HKIMO Heat Round 2024 - Primary 5",
            "grade": 5,
            "subject": "math",
            "topic": "Số học (Number Theory)",
            "question_type": "single_choice",
            "content_html": "<p>Find the last two digits of $7^{2024}$.<br/><i>(Tìm hai chữ số tận cùng của $7^{2024}$.)</i></p>",
            "content_text": "Find the last two digits of 7^2024. (Tìm hai chữ số tận cùng của 7^2024.)",
            "images": [],
            "options": [
                {"id": "A", "content": "01", "is_correct": True},
                {"id": "B", "content": "49", "is_correct": False},
                {"id": "C", "content": "43", "is_correct": False},
                {"id": "D", "content": "07", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Xét chu kỳ hai chữ số tận cùng của lũy thừa của 7 theo modulo 100:\n$7^1 \\equiv 07$\n$7^2 \\equiv 49$\n$7^3 \\equiv 43$\n$7^4 = 2401 \\equiv 01\\pmod{100}$.\nVì $2024$ chia hết cho $4$ ($2024 = 4 \\times 506$), nên hai chữ số tận cùng của $7^{2024}$ là $01$.",
            "difficulty": "olympiad"
        },
        # 7. ASMO (Asian Science and Mathematics Olympiad) - Geometry
        {
            "id": "sample_asmo_001",
            "source_platform": "asmo",
            "source_url": "https://asmo.vn",
            "exam_name": "ASMO National Round 2024 - Grade 6",
            "grade": 6,
            "subject": "math",
            "topic": "Hình học (Geometry)",
            "question_type": "single_choice",
            "content_html": "<p>A square of side length $10\\text{ cm}$ contains four identical circles inscribed as shown. What is the area of the shaded region in terms of $\\pi$?<br/><i>(Một hình vuông cạnh $10\\text{ cm}$ chứa 4 hình tròn bằng nhau tiếp xúc nhau. Tính diện tích phần tô đậm?)</i></p>",
            "content_text": "A square of side length 10 cm contains four identical circles inscribed as shown. What is the area of the shaded region in terms of pi?",
            "images": [],
            "options": [
                {"id": "A", "content": "$100 - 25\\pi$", "is_correct": True},
                {"id": "B", "content": "$100 - 20\\pi$", "is_correct": False},
                {"id": "C", "content": "$80 - 16\\pi$", "is_correct": False},
                {"id": "D", "content": "$50 - 12.5\\pi$", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Bán kính mỗi hình tròn nhỏ là $r = 10 : 4 = 2.5\\text{ cm}$.\nDiện tích 4 hình tròn là $4 \\times \\pi \\times 2.5^2 = 25\\pi\\text{ cm}^2$.\nDiện tích hình vuông là $10 \\times 10 = 100\\text{ cm}^2$.\nDiện tích phần tô đậm là $100 - 25\\pi\\text{ cm}^2$.",
            "difficulty": "olympiad"
        },
        # 8. Tiếng Việt - Trạng Nguyên Tiếng Việt Lớp 4
        {
            "id": "sample_tv_001",
            "source_platform": "tnmath",
            "source_url": "https://trangnguyen.edu.vn",
            "exam_name": "Trạng Nguyên Tiếng Việt - Vòng Hương 2024",
            "grade": 4,
            "subject": "vietnamese",
            "topic": "Từ ngữ & Ngữ pháp Tiếng Việt",
            "question_type": "single_choice",
            "content_html": "<p>Trong các câu sau, câu nào có hình ảnh so sánh?</p>",
            "content_text": "Trong các câu sau, câu nào có hình ảnh so sánh?",
            "images": [],
            "options": [
                {"id": "A", "content": "Mặt trời như một quả cầu lửa khổng lồ từ từ nhô lên.", "is_correct": True},
                {"id": "B", "content": "Mùa xuân về, cây cối đâm chồi nảy lộc.", "is_correct": False},
                {"id": "C", "content": "Tiếng suối róc rách chảy suốt đêm ngày.", "is_correct": False},
                {"id": "D", "content": "Gió heo may nhè nhẹ thổi qua cánh đồng.", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Câu A sử dụng từ so sánh 'như' để ví 'Mặt trời' giống như 'một quả cầu lửa khổng lồ'.",
            "difficulty": "easy"
        },
        # 9. Tiếng Anh - Olympic English IOE Lớp 5
        {
            "id": "sample_eng_001",
            "source_platform": "manual",
            "source_url": "https://ioe.vn",
            "exam_name": "Olympic English Contest (IOE) - Grade 5",
            "grade": 5,
            "subject": "english",
            "topic": "Grammar - Past Tense",
            "question_type": "single_choice",
            "content_html": "<p>Choose the correct answer: <i>'Where ______ you go for your summer vacation last year?'</i></p>",
            "content_text": "Choose the correct answer: 'Where ______ you go for your summer vacation last year?'",
            "images": [],
            "options": [
                {"id": "A", "content": "did", "is_correct": True},
                {"id": "B", "content": "do", "is_correct": False},
                {"id": "C", "content": "are", "is_correct": False},
                {"id": "D", "content": "were", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Câu hỏi ở thì quá khứ đơn với trạng từ 'last year', sử dụng trợ động từ 'did'.",
            "difficulty": "medium"
        }
    ]
    
    for s in samples:
        norm = await normalize_question_payload(s)
        insert_or_update_question(norm)
        
    return {"success": True, "seeded_count": len(samples), "message": f"Đã nạp {len(samples)} câu hỏi mẫu Toán, Tiếng Việt, Tiếng Anh chuẩn quốc tế & học đường!"}

# ----------------- Internet Question Hunter Endpoint -----------------

from backend.scrapers.internet_hunter import run_internet_question_hunter

@app.post("/api/hunter/run")
async def trigger_internet_hunter(payload: dict):
    subject = payload.get("subject", "all")
    grade = int(payload.get("grade", 5))
    custom_url = payload.get("custom_url")
    custom_urls = payload.get("custom_urls", [])
    result = await run_internet_question_hunter(
        subject=subject,
        grade=grade,
        custom_url=custom_url,
        custom_urls=custom_urls
    )
    return result

# ----------------- Favicon Suppression (Clear Browser Cache) -----------------

import base64
TRANSPARENT_FAVICON = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=")

@app.api_route("/favicon.ico", methods=["GET", "HEAD"], include_in_schema=False)
async def suppress_favicon():
    """Returns a 1x1 transparent PNG to clear any cached tab icons and ensure no logo is shown."""
    return Response(
        content=TRANSPARENT_FAVICON,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=31536000, immutable"}
    )

# ----------------- Static Files Serving -----------------

# Mount media directory
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")

# Mount frontend
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

