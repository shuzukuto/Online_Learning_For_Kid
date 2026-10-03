from __future__ import annotations
import sqlite3
import json
import os
import re
import random
import uuid
import hashlib
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "questions.db")

# --- Performance: Stats Cache (TTL 5s) ---
_stats_cache = {"data": None, "timestamp": 0}
STATS_CACHE_TTL = 5

def invalidate_stats_cache():
    """Call after any INSERT/DELETE/UPDATE on questions to expire cached stats."""
    _stats_cache["data"] = None
    _stats_cache["timestamp"] = 0

def compute_content_hash(text: str) -> str:
    """Compute MD5 hash of normalized content for fast dedup lookups."""
    normalized = (text or "").strip().lower()
    return hashlib.md5(normalized.encode('utf-8')).hexdigest()


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.execute("PRAGMA busy_timeout = 30000;")
    cursor.close()
    return conn

def resequence_question_numbers(cursor=None):
    """Ensures all questions in the bank have strict sequential numbers 1 to N without gaps."""
    own_conn = False
    if cursor is None:
        conn = get_connection()
        cursor = conn.cursor()
        own_conn = True
        
    cursor.execute("""
        WITH numbered AS (
            SELECT id, ROW_NUMBER() OVER (ORDER BY created_at ASC, id ASC) as rn
            FROM questions
        )
        UPDATE questions
        SET q_number = (SELECT rn FROM numbered WHERE numbered.id = questions.id);
    """)
    
    if own_conn:
        conn.commit()
        conn.close()

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Questions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id TEXT PRIMARY KEY,
        q_number INTEGER,
        source_platform TEXT NOT NULL,
        source_detail TEXT,
        source_url TEXT,
        exam_name TEXT,
        year INTEGER,
        grade INTEGER DEFAULT 5,
        subject TEXT DEFAULT 'math',
        topic TEXT,
        question_type TEXT NOT NULL,
        content_html TEXT NOT NULL,
        content_text TEXT NOT NULL,
        images TEXT,
        options TEXT,
        correct_answer TEXT,
        explanation TEXT,
        difficulty TEXT DEFAULT 'medium',
        content_hash TEXT,
        created_at TEXT,
        updated_at TEXT
    );
    """)
    
    # Migrations for existing DB if missing columns
    cursor.execute("PRAGMA table_info(questions)")
    existing_cols = [r[1] for r in cursor.fetchall()]
    if "q_number" not in existing_cols:
        cursor.execute("ALTER TABLE questions ADD COLUMN q_number INTEGER;")
    if "source_detail" not in existing_cols:
        cursor.execute("ALTER TABLE questions ADD COLUMN source_detail TEXT;")
    if "content_hash" not in existing_cols:
        cursor.execute("ALTER TABLE questions ADD COLUMN content_hash TEXT;")
        
    # Indexes for fast querying & filtering
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_q_number ON questions (q_number);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_q_platform ON questions (source_platform);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_q_grade ON questions (grade);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_q_subject ON questions (subject);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_q_type ON questions (question_type);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_q_diff ON questions (difficulty);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_q_created ON questions (created_at DESC);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_q_content_hash ON questions (content_hash);")
    
    # 2. Exams Table (Biên soạn đề thi)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS exams (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        grade INTEGER DEFAULT 5,
        duration_minutes INTEGER DEFAULT 45,
        header_info TEXT,
        notes TEXT,
        question_ids TEXT,
        created_at TEXT
    );
    """)

    # 3. Collector Logs Table (Nhật ký thu thập)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS collector_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        platform TEXT NOT NULL,
        status TEXT NOT NULL,
        message TEXT,
        items_count INTEGER DEFAULT 0,
        created_at TEXT
    );
    """)

    # 4. System Config Table (Lazy Resequence Flag + Settings)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS system_config (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """)

    # 5. FTS5 Full-Text Search Virtual Table (Performance: search)
    try:
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS questions_fts 
            USING fts5(
                content_text, 
                exam_name, 
                topic, 
                explanation,
                content='questions', 
                content_rowid='rowid'
            );
        """)
        
        # Auto-sync triggers: keep FTS5 in sync with questions table
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS questions_fts_ai AFTER INSERT ON questions BEGIN
                INSERT INTO questions_fts(rowid, content_text, exam_name, topic, explanation) 
                VALUES (new.rowid, new.content_text, new.exam_name, new.topic, new.explanation);
            END;
        """)
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS questions_fts_ad AFTER DELETE ON questions BEGIN
                INSERT INTO questions_fts(questions_fts, rowid, content_text, exam_name, topic, explanation) 
                VALUES ('delete', old.rowid, old.content_text, old.exam_name, old.topic, old.explanation);
            END;
        """)
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS questions_fts_au AFTER UPDATE ON questions BEGIN
                INSERT INTO questions_fts(questions_fts, rowid, content_text, exam_name, topic, explanation) 
                VALUES ('delete', old.rowid, old.content_text, old.exam_name, old.topic, old.explanation);
                INSERT INTO questions_fts(rowid, content_text, exam_name, topic, explanation) 
                VALUES (new.rowid, new.content_text, new.exam_name, new.topic, new.explanation);
            END;
        """)
        
        # Populate FTS for existing data (only if FTS table is empty)
        cursor.execute("SELECT COUNT(*) FROM questions_fts")
        fts_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM questions")
        q_count = cursor.fetchone()[0]
        if fts_count == 0 and q_count > 0:
            cursor.execute("""
                INSERT INTO questions_fts(rowid, content_text, exam_name, topic, explanation)
                SELECT rowid, content_text, exam_name, topic, explanation FROM questions;
            """)
    except Exception as e:
        print(f"[init_db] FTS5 setup note: {e}")

    # 6. Populate content_hash for existing questions that lack it
    cursor.execute("SELECT COUNT(*) FROM questions WHERE content_hash IS NULL AND content_text IS NOT NULL")
    null_hash_count = cursor.fetchone()[0]
    if null_hash_count > 0:
        cursor.execute("SELECT id, content_text FROM questions WHERE content_hash IS NULL")
        for row in cursor.fetchall():
            h = compute_content_hash(row[1] or "")
            cursor.execute("UPDATE questions SET content_hash = ? WHERE id = ?", (h, row[0]))
    
    # 7. Practice History Table (Phân hệ Luyện tập thi trực tuyến)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS practice_history (
        id TEXT PRIMARY KEY NOT NULL,
        exam_id TEXT,
        exam_title TEXT NOT NULL,
        subject TEXT NOT NULL DEFAULT 'math',
        grade INTEGER NOT NULL DEFAULT 5,
        total_questions INTEGER NOT NULL,
        correct_count INTEGER NOT NULL DEFAULT 0,
        wrong_count INTEGER NOT NULL DEFAULT 0,
        skipped_count INTEGER NOT NULL DEFAULT 0,
        score REAL NOT NULL DEFAULT 0.0,
        max_score REAL NOT NULL DEFAULT 10.0,
        duration_seconds INTEGER NOT NULL DEFAULT 0,
        time_spent_seconds INTEGER NOT NULL DEFAULT 0,
        ranking TEXT,
        answers_detail TEXT,
        created_at TEXT NOT NULL
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_practice_created_at ON practice_history (created_at DESC);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_practice_subject ON practice_history (subject);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_practice_grade ON practice_history (grade);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_practice_exam_id ON practice_history (exam_id);")

    # 8. OCR Corrections Table (Active Lexicon Learning)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ocr_corrections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        wrong_text TEXT UNIQUE NOT NULL,
        correct_text TEXT NOT NULL,
        frequency INTEGER DEFAULT 1,
        source TEXT DEFAULT 'manual_feedback',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ocr_wrong_text ON ocr_corrections (wrong_text);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ocr_freq ON ocr_corrections (frequency DESC);")

    conn.commit()
    conn.close()

def compute_source_detail(q: Dict[str, Any]) -> str:
    """Computes a human-readable, descriptive source name for a question, never duplicating raw hunter platform name."""
    explicit = (q.get("source_detail") or "").strip()
    plat = (q.get("source_platform") or "").strip().lower()

    # If explicitly given and valid (not empty or raw platform name)
    if explicit and explicit.lower() not in ("internet_hunter", "internet hunter", "null", "none"):
        return explicit

    url = (q.get("source_url") or "").lower()
    exam = (q.get("exam_name") or "")
    top = (q.get("topic") or "")
    sub = (q.get("subject") or "").lower()
    comb = f"{url} {exam} {top}".lower()

    # VioEdu (check before IOE to avoid substring collision)
    if plat == "vioedu" or "vioedu" in comb or "vio.edu" in url or "đấu trường toán" in comb:
        if "codemath" in comb:
            for olym in ["TIMO", "HKIMO", "BBB", "IKMC", "FMO", "ITMC", "SASMO", "SEAMO", "ASMO"]:
                if olym.lower() in comb:
                    return f"CodeMath • {olym}"
        return "VioEdu (FPT)"

    # CodeMath & Olympiad competitions
    if "codemath" in comb or "hacodemath" in comb:
        for olym in ["TIMO", "HKIMO", "BBB", "IKMC", "FMO", "ITMC", "SASMO", "SEAMO", "ASMO"]:
            if olym.lower() in comb:
                return f"CodeMath • {olym}"
        return "CodeMath Olympic"

    # IOE English Olympiad
    if bool(re.search(r'\bioe\b', comb)) or "english olympiad" in comb or "olympic english" in comb:
        return "Olympic IOE English"

    # Trạng Nguyên
    if "trạng nguyên toàn tài" in comb:
        return "Trạng Nguyên Toàn Tài"
    if "trạng nguyên tiếng việt" in comb or ("trạng nguyên" in comb and sub == "vietnamese"):
        return "Trạng Nguyên Tiếng Việt"
    if "trạng nguyên toán" in comb or ("trạng nguyên" in comb and sub == "math"):
        return "Trạng Nguyên Toán"
    if "trạng nguyên" in comb or plat == "tnmath":
        return "Trạng Nguyên"

    # Sách Giáo Khoa / Hành Trang Số
    if "cánh diều" in comb:
        return "SGK Cánh Diều"
    if "kết nối tri thức" in comb:
        return "SGK Kết Nối Tri Thức"
    if "chân trời sáng tạo" in comb:
        return "SGK Chân Trời Sáng Tạo"
    if "hanhtrangso" in comb or plat == "hanhtrangso" or "sách giáo khoa" in comb:
        return "Hành Trang Số (SGK)"

    # International English Math Platforms
    if "k5learning" in comb or plat == "k5learning":
        return "K5 Learning (US Math)"
    if "ixl.com" in comb or plat == "ixl":
        return "IXL Learning Math"
    if "khanacademy" in comb or plat == "khanacademy":
        return "Khan Academy Math"
    if "commoncore" in comb:
        return "Common Core Math"
    if "math-drills" in comb:
        return "Math-Drills"

    # Specific Olympics
    if bool(re.search(r'\btimo\b', comb)) or plat == "timo":
        return "Olympic TIMO"
    if bool(re.search(r'\bhkimo\b', comb)) or plat == "hkimo":
        return "Olympic HKIMO"
    if bool(re.search(r'\bsasmo\b', comb)):
        return "Olympic SASMO"
    if bool(re.search(r'\bseamo\b', comb)):
        return "Olympic SEAMO"
    if bool(re.search(r'\basmo\b', comb)) or plat == "asmo":
        return "Olympic ASMO"
    if bool(re.search(r'\bikmc\b', comb)) or "kangaroo" in comb or plat == "kangaroo":
        return "Olympic Kangaroo (IKMC)"
    if bool(re.search(r'\bfmo\b', comb)):
        return "Olympic FMO"

    # Common School Contests & Fields
    if "khám phá khoa học" in comb or "khoa học & tự nhiên" in comb:
        return "Khoa học & Tự nhiên"
    if "tin học trẻ" in comb:
        return "Tin học Trẻ Tiểu học"
    if "khảo sát năng lực" in comb:
        return "Khảo sát Năng lực"
    if "olympic toán" in comb:
        return "Olympic Toán Tiểu học"

    # Web Portals
    if "vietjack" in url:
        return "VietJack"
    if "vndoc" in url:
        return "VnDoc"
    if "loigiaihay" in url:
        return "Lời Giải Hay"
    if "tuyensinh247" in url:
        return "Tuyensinh247"
    if "hoc24" in url:
        return "Hoc247"
    if "olm" in url or plat == "olm":
        return "OLM.vn (ĐH Sư Phạm)"

    if plat == "manual":
        return "Soạn thủ công"

    if "khoade" in url or "khoade" in comb:
        return "Kho Đề Mở (Online)"

    if plat == "internet_hunter":
        return "Kho Đề Mở (Online)"

    return plat.upper() if plat else "Nguồn mở"

def row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    d = dict(row)
    if "images" in d and d["images"]:
        try:
            d["images"] = json.loads(d["images"])
        except Exception:
            d["images"] = []
    else:
        d["images"] = []

    if "options" in d and d["options"]:
        try:
            d["options"] = json.loads(d["options"])
        except Exception:
            d["options"] = []
    else:
        d["options"] = []

    if "question_ids" in d and d["question_ids"]:
        try:
            d["question_ids"] = json.loads(d["question_ids"])
        except Exception:
            d["question_ids"] = []

    # Dynamic fallback for source_detail to guarantee accurate, descriptive label
    d["source_detail"] = compute_source_detail(d)

    return d

def get_questions(
    platform: Optional[str] = None,
    grade: Optional[int] = None,
    subject: Optional[str] = None,
    topic: Optional[str] = None,
    question_type: Optional[str] = None,
    difficulty: Optional[str] = None,
    search: Optional[str] = None,
    source_detail: Optional[str] = None,
    only_duplicates: bool = False,
    sort_by: str = "q_number_asc",
    page: int = 1,
    page_size: int = 20
) -> Tuple[List[Dict[str, Any]], int]:
    conn = get_connection()
    cursor = conn.cursor()
    
    conditions = []
    params = []
    
    if platform and platform != "all":
        if platform == "olympiad":
            conditions.append("(source_platform IN ('timo', 'hkimo', 'asmo') OR difficulty = 'olympiad')")
        else:
            conditions.append("source_platform = ?")
            params.append(platform)
        
    if grade and grade > 0:
        conditions.append("grade = ?")
        params.append(grade)

    if subject and subject != "all":
        conditions.append("subject = ?")
        params.append(subject)
        
    if topic:
        conditions.append("topic LIKE ?")
        params.append(f"%{topic}%")
        
    if question_type and question_type != "all":
        conditions.append("question_type = ?")
        params.append(question_type)
        
    if difficulty and difficulty != "all":
        conditions.append("difficulty = ?")
        params.append(difficulty)
        
    if source_detail and source_detail != "all":
        sd = source_detail.lower().strip()
        if sd == "codemath":
            conditions.append("(source_detail LIKE '%codemath%' OR source_url LIKE '%codemath%' OR topic LIKE '%codemath%' OR exam_name LIKE '%codemath%' OR exam_name LIKE '%timo%' OR exam_name LIKE '%sasmo%' OR exam_name LIKE '%hkimo%' OR exam_name LIKE '%ikmc%')")
        elif sd in ("hanhtrangso", "hành trang số"):
            conditions.append("(source_detail LIKE '%hành trang số%' OR source_detail LIKE '%sgk%' OR source_platform = 'hanhtrangso' OR source_url LIKE '%hanhtrangso%')")
        elif sd == "vioedu":
            conditions.append("(source_detail LIKE '%vioedu%' OR source_platform = 'vioedu' OR source_url LIKE '%vio.edu%')")
        elif sd in ("trangnguyen", "trạng nguyên"):
            conditions.append("(source_detail LIKE '%trạng nguyên%' OR source_platform = 'tnmath' OR source_url LIKE '%trangnguyen%' OR source_url LIKE '%tnmath%')")
        elif sd in ("kho đề mở", "kho de mo", "khoade"):
            conditions.append("(source_detail LIKE '%kho đề%' OR source_url LIKE '%khoade%')")
        elif sd in ("olympiad", "olympic"):
            conditions.append("(source_detail LIKE '%olympic%' OR source_detail LIKE '%ioe%' OR source_platform IN ('timo', 'hkimo', 'asmo') OR difficulty = 'olympiad' OR topic LIKE '%olympic%')")
        elif sd in ("vietjack", "vndoc"):
            conditions.append("(source_detail LIKE '%vietjack%' OR source_detail LIKE '%vndoc%' OR source_url LIKE '%vietjack%' OR source_url LIKE '%loigiaihay%' OR source_url LIKE '%vndoc%')")
        elif sd in ("manual", "soạn thủ công"):
            conditions.append("(source_detail LIKE '%thủ công%' OR source_platform = 'manual')")
        else:
            conditions.append("source_detail LIKE ?")
            params.append(f"%{source_detail}%")

    if only_duplicates:
        conditions.append("""
            content_hash IN (
                SELECT content_hash FROM questions 
                WHERE content_hash IS NOT NULL
                GROUP BY content_hash HAVING COUNT(*) > 1
            )
        """)

    if search:
        search_term = search.strip()
        num_match = re.search(r"^(?:câu\s*|#)?(\d+)$", search_term, re.IGNORECASE)
        if num_match:
            target_q_num = int(num_match.group(1))
            conditions.append("q_number = ?")
            params.append(target_q_num)
        else:
            # Try FTS5 first (indexed full-text search), fallback to LIKE
            try:
                # Escape FTS5 special characters, build AND query
                fts_clean = re.sub(r'[^\w\s]', ' ', search_term)
                fts_tokens = [f'"{t}"' for t in fts_clean.split() if len(t) >= 2]
                if fts_tokens:
                    fts_query = ' AND '.join(fts_tokens)
                else:
                    fts_query = f'"{search_term}"'
                conditions.append("""
                    rowid IN (
                        SELECT rowid FROM questions_fts 
                        WHERE questions_fts MATCH ?
                    )
                """)
                params.append(fts_query)
            except Exception:
                # Fallback to LIKE if FTS5 is not available
                conditions.append("(content_text LIKE ? OR exam_name LIKE ? OR topic LIKE ? OR explanation LIKE ?)")
                term = f"%{search_term}%"
                params.extend([term, term, term, term])
        
    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)
        
    # Count total
    count_sql = f"SELECT COUNT(*) FROM questions {where_clause}"
    cursor.execute(count_sql, params)
    total = cursor.fetchone()[0]
    
    # Query items - default ordered by permanent q_number 1..N
    order_clause = "ORDER BY q_number ASC"
    if sort_by in ("created_at_desc", "created_desc", "newest"):
        order_clause = "ORDER BY created_at DESC, id DESC"
    elif sort_by in ("created_at_asc", "created_asc", "oldest"):
        order_clause = "ORDER BY created_at ASC, id ASC"
    elif sort_by in ("q_number_desc", "num_desc"):
        order_clause = "ORDER BY q_number DESC"
    elif sort_by in ("q_number_asc", "num_asc"):
        order_clause = "ORDER BY q_number ASC"

    offset = (page - 1) * page_size
    query_sql = f"""
        SELECT * FROM questions 
        {where_clause} 
        {order_clause} 
        LIMIT ? OFFSET ?
    """
    cursor.execute(query_sql, params + [page_size, offset])
    rows = cursor.fetchall()
    items = [row_to_dict(r) for r in rows]
    
    conn.close()
    return items, total

def get_question_by_id(question_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM questions WHERE id = ?", (question_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row_to_dict(row)
    return None

def find_duplicate_question_id(cursor, content_text: str, current_id: Optional[str] = None) -> Optional[str]:
    """Finds an existing question ID with the exact same normalized content text using content_hash index."""
    if not content_text or len(content_text.strip()) < 5:
        return None
    h = compute_content_hash(content_text)
    if current_id:
        cursor.execute("SELECT id FROM questions WHERE content_hash = ? AND id != ? LIMIT 1", (h, current_id))
    else:
        cursor.execute("SELECT id FROM questions WHERE content_hash = ? LIMIT 1", (h,))
    row = cursor.fetchone()
    if row:
        return row[0]
    return None

def insert_or_update_question(q: Dict[str, Any], allow_duplicate: bool = False) -> Optional[str]:
    """
    Inserts a new question or updates an existing one.
    Crucial:
    1. Validates that question has meaningful content and rejects HTML/CSS dumps.
    2. Cross-checks with database to ensure questions are NOT duplicated!
    If a question with identical content already exists, returns the existing question ID.
    """
    from backend.normalizer import is_valid_question_payload
    valid, reason = is_valid_question_payload(q)
    if not valid:
        return None

    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    q_id = q.get("id") or str(uuid.uuid4())[:12]
    resolved_source_detail = compute_source_detail(q)
    
    images_str = json.dumps(q.get("images", []), ensure_ascii=False)
    options_str = json.dumps(q.get("options", []), ensure_ascii=False)
    
    # 1. Check if explicit ID exists -> UPDATE
    cursor.execute("SELECT id, q_number FROM questions WHERE id = ?", (q_id,))
    exists_row = cursor.fetchone()
    
    if exists_row:
        existing_q_num = exists_row["q_number"]
        if existing_q_num is None:
            cursor.execute("SELECT COALESCE(MAX(q_number), 0) + 1 FROM questions")
            existing_q_num = cursor.fetchone()[0]

        cursor.execute("""
            UPDATE questions SET
                q_number = ?,
                source_platform = ?,
                source_detail = ?,
                source_url = ?,
                exam_name = ?,
                year = ?,
                grade = ?,
                subject = ?,
                topic = ?,
                question_type = ?,
                content_html = ?,
                content_text = ?,
                images = ?,
                options = ?,
                correct_answer = ?,
                explanation = ?,
                difficulty = ?,
                content_hash = ?,
                updated_at = ?
            WHERE id = ?
        """, (
            existing_q_num,
            q.get("source_platform", "manual"),
            resolved_source_detail,
            q.get("source_url"),
            q.get("exam_name"),
            q.get("year"),
            q.get("grade", 5),
            q.get("subject", "math"),
            q.get("topic"),
            q.get("question_type", "single_choice"),
            q.get("content_html", ""),
            q.get("content_text", ""),
            images_str,
            options_str,
            q.get("correct_answer"),
            q.get("explanation"),
            q.get("difficulty", "medium"),
            compute_content_hash(q.get("content_text", "")),
            now,
            q_id
        ))
        conn.commit()
        conn.close()
        invalidate_stats_cache()
        return q_id
        
    # 2. Check if a question with matching content already exists in DB (Deduplication against DB)
    if not allow_duplicate:
        content_text = q.get("content_text") or ""
        dupe_id = find_duplicate_question_id(cursor, content_text)
        if dupe_id:
            conn.close()
            return dupe_id

    # 3. Insert new unique question with next sequential q_number
    cursor.execute("SELECT COALESCE(MAX(q_number), 0) + 1 FROM questions")
    next_q_num = cursor.fetchone()[0]

    cursor.execute("""
        INSERT INTO questions (
            id, q_number, source_platform, source_detail, source_url, exam_name, year, grade,
            subject, topic, question_type, content_html, content_text,
            images, options, correct_answer, explanation, difficulty,
            content_hash, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        q_id,
        next_q_num,
        q.get("source_platform", "manual"),
        resolved_source_detail,
        q.get("source_url"),
        q.get("exam_name"),
        q.get("year"),
        q.get("grade", 5),
        q.get("subject", "math"),
        q.get("topic"),
        q.get("question_type", "single_choice"),
        q.get("content_html", ""),
        q.get("content_text", ""),
        images_str,
        options_str,
        q.get("correct_answer"),
        q.get("explanation"),
        q.get("difficulty", "medium"),
        compute_content_hash(q.get("content_text", "")),
        now,
        now
    ))
    conn.commit()
    conn.close()
    invalidate_stats_cache()
    return q_id

def bulk_insert_questions(questions: List[Dict[str, Any]], skip_duplicates: bool = True) -> int:
    """Optimized bulk insert using a single transaction for all questions."""
    inserted = 0
    conn = get_connection()
    cursor = conn.cursor()
    from backend.normalizer import is_valid_question_payload
    
    try:
        for q in questions:
            try:
                valid, _ = is_valid_question_payload(q)
                if not valid:
                    continue
                content_text = (q.get("content_text") or "").strip()
                if skip_duplicates and content_text:
                    # Fast hash-based dedup check using index
                    h = compute_content_hash(content_text)
                    cursor.execute("SELECT 1 FROM questions WHERE content_hash = ? LIMIT 1", (h,))
                    if cursor.fetchone():
                        continue
                
                # Direct insert using current cursor (same connection/transaction)
                now = datetime.now().isoformat()
                q_id = q.get("id") or str(uuid.uuid4())[:12]
                resolved_detail = compute_source_detail(q)
                cursor.execute("SELECT COALESCE(MAX(q_number), 0) + 1 FROM questions")
                next_q_num = cursor.fetchone()[0]
                
                cursor.execute("""
                    INSERT OR IGNORE INTO questions (
                        id, q_number, source_platform, source_detail, source_url, exam_name, year, grade,
                        subject, topic, question_type, content_html, content_text,
                        images, options, correct_answer, explanation, difficulty,
                        content_hash, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    q_id, next_q_num,
                    q.get("source_platform", "manual"), resolved_detail,
                    q.get("source_url"), q.get("exam_name"), q.get("year"),
                    q.get("grade", 5), q.get("subject", "math"), q.get("topic"),
                    q.get("question_type", "single_choice"),
                    q.get("content_html", ""), q.get("content_text", ""),
                    json.dumps(q.get("images", []), ensure_ascii=False),
                    json.dumps(q.get("options", []), ensure_ascii=False),
                    q.get("correct_answer"), q.get("explanation"),
                    q.get("difficulty", "medium"),
                    compute_content_hash(content_text),
                    now, now
                ))
                if cursor.rowcount > 0:
                    inserted += 1
            except Exception as e:
                print(f"Error inserting question: {e}")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    
    if inserted > 0:
        invalidate_stats_cache()
    return inserted

def get_duplicate_questions_summary() -> Dict[str, Any]:
    """Scans and groups all duplicate questions in the database."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT content_hash, COUNT(*) as cnt
        FROM questions
        WHERE content_hash IS NOT NULL
        GROUP BY content_hash
        HAVING cnt > 1
        ORDER BY cnt DESC
    """)
    groups_meta = cursor.fetchall()
    
    total_groups = len(groups_meta)
    total_dupes = sum(r["cnt"] - 1 for r in groups_meta)
    
    duplicate_groups = []
    for g in groups_meta:
        h = g["content_hash"]
        cursor.execute("""
            SELECT * FROM questions 
            WHERE content_hash = ?
            ORDER BY created_at ASC, id ASC
        """, (h,))
        items = [row_to_dict(r) for r in cursor.fetchall()]
        duplicate_groups.append({
            "content_text": items[0]["content_text"] if items else h,
            "count": len(items),
            "original_id": items[0]["id"] if items else None,
            "items": items
        })
        
    conn.close()
    return {
        "total_groups": total_groups,
        "total_duplicate_copies": total_dupes,
        "groups": duplicate_groups
    }

def clean_duplicate_questions(action: str = "keep_oldest", delete_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    """Cleans duplicate questions while preserving the primary record."""
    conn = get_connection()
    cursor = conn.cursor()
    deleted_count = 0
    
    if delete_ids and len(delete_ids) > 0:
        for q_id in delete_ids:
            cursor.execute("DELETE FROM questions WHERE id = ?", (q_id,))
            deleted_count += cursor.rowcount
    else:
        cursor.execute("""
            SELECT content_hash, COUNT(*) as cnt
            FROM questions
            WHERE content_hash IS NOT NULL
            GROUP BY content_hash
            HAVING cnt > 1
        """)
        groups = cursor.fetchall()
        for g in groups:
            h = g["content_hash"]
            order = "ASC" if action == "keep_oldest" else "DESC"
            cursor.execute(f"""
                SELECT id FROM questions 
                WHERE content_hash = ?
                ORDER BY created_at {order}, id ASC
            """, (h,))
            ids = [r[0] for r in cursor.fetchall()]
            if len(ids) > 1:
                # Keep the first one, delete all redundant copies
                for to_del in ids[1:]:
                    cursor.execute("DELETE FROM questions WHERE id = ?", (to_del,))
                    deleted_count += cursor.rowcount
    if deleted_count > 0:
        resequence_question_numbers(cursor)
        invalidate_stats_cache()
    conn.commit()
    cursor.execute("SELECT COUNT(*) FROM questions")
    remaining = cursor.fetchone()[0]
    conn.close()
    
    return {
        "success": True,
        "deleted_count": deleted_count,
        "remaining_questions": remaining
    }

def run_database_diagnostics() -> Dict[str, Any]:
    """Runs a complete diagnostic health check on the SQLite database."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Integrity check
    cursor.execute("PRAGMA integrity_check")
    integrity = cursor.fetchone()[0]
    
    # 2. Total questions & unique questions
    cursor.execute("SELECT COUNT(*) FROM questions")
    total_q = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT LOWER(TRIM(content_text))) FROM questions")
    unique_q = cursor.fetchone()[0]
    duplicate_count = total_q - unique_q
    
    # 3. Breakdown by subject
    cursor.execute("SELECT subject, COUNT(*) FROM questions GROUP BY subject")
    by_subject = {r[0] or "unknown": r[1] for r in cursor.fetchall()}
    
    # 4. Breakdown by grade
    cursor.execute("SELECT grade, COUNT(*) FROM questions GROUP BY grade ORDER BY grade")
    by_grade = {f"Lớp {r[0]}": r[1] for r in cursor.fetchall()}
    
    # 5. Breakdown by platform
    cursor.execute("SELECT source_platform, COUNT(*) FROM questions GROUP BY source_platform")
    by_platform = {r[0] or "unknown": r[1] for r in cursor.fetchall()}
    
    # 6. Breakdown by difficulty
    cursor.execute("SELECT difficulty, COUNT(*) FROM questions GROUP BY difficulty")
    by_diff = {r[0] or "medium": r[1] for r in cursor.fetchall()}
    
    # 7. Quality Anomalies & Content Validity Check
    cursor.execute("SELECT COUNT(*) FROM questions WHERE options IS NULL OR options = '[]' OR options = ''")
    no_options_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM questions WHERE correct_answer IS NULL OR correct_answer = ''")
    no_answer_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM questions WHERE explanation IS NULL OR explanation = ''")
    no_explanation_count = cursor.fetchone()[0]

    from backend.normalizer import is_valid_question_payload
    cursor.execute("SELECT id, content_text, content_html, options, question_type FROM questions")
    all_diag_rows = cursor.fetchall()
    corrupt_ids = []
    for r in all_diag_rows:
        try:
            opts = json.loads(r[3]) if r[3] else []
        except Exception:
            opts = []
        q_dict = {
            "id": r[0],
            "content_text": r[1],
            "content_html": r[2],
            "options": opts,
            "question_type": r[4]
        }
        valid, _ = is_valid_question_payload(q_dict)
        if not valid:
            corrupt_ids.append(r[0])
    corrupt_count = len(corrupt_ids)
    
    # 8. Table stats
    cursor.execute("SELECT COUNT(*) FROM exams")
    total_exams = cursor.fetchone()[0]
    try:
        cursor.execute("SELECT COUNT(*) FROM collector_logs")
        total_logs = cursor.fetchone()[0]
    except Exception:
        total_logs = 0

    # 9. File size
    file_size_bytes = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
    
    conn.close()
    
    return {
        "success": True,
        "status": "healthy" if integrity == "ok" and duplicate_count == 0 and corrupt_count == 0 else "needs_attention",
        "integrity": integrity,
        "sqlite_integrity": integrity,
        "total_questions": total_q,
        "unique_questions": unique_q,
        "duplicate_copies": duplicate_count,
        "duplicate_copies_count": duplicate_count,
        "by_subject": by_subject,
        "by_grade": by_grade,
        "by_platform": by_platform,
        "by_difficulty": by_diff,
        "anomalies": {
            "corrupt_questions": corrupt_count,
            "no_options": no_options_count,
            "no_correct_answer": no_answer_count,
            "no_explanation": no_explanation_count
        },
        "table_stats": {
            "questions": total_q,
            "exams": total_exams,
            "system_logs": total_logs
        },
        "db_file_size_kb": round(file_size_bytes / 1024, 1),
        "db_path": DB_PATH
    }

def fix_database_issues() -> Dict[str, Any]:
    """Repairs and optimizes the database by cleaning corrupt questions, removing duplicates, and optimizing storage."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 0. Clean corrupt and invalid non-question entries (HTML dumps, contact info, blog descriptions)
    from backend.normalizer import is_valid_question_payload
    cursor.execute("SELECT id, content_text, content_html, options, question_type FROM questions")
    all_rows = cursor.fetchall()
    corrupt_ids = []
    for r in all_rows:
        try:
            opts = json.loads(r[3]) if r[3] else []
        except Exception:
            opts = []
        q_dict = {
            "id": r[0],
            "content_text": r[1],
            "content_html": r[2],
            "options": opts,
            "question_type": r[4]
        }
        valid, _ = is_valid_question_payload(q_dict)
        if not valid:
            corrupt_ids.append(r[0])
            
    corrupt_deleted = 0
    if corrupt_ids:
        placeholders = ",".join("?" for _ in corrupt_ids)
        cursor.execute(f"DELETE FROM questions WHERE id IN ({placeholders})", corrupt_ids)
        corrupt_deleted = cursor.rowcount
        resequence_question_numbers(cursor)
    conn.commit()
    conn.close()

    # 1. Clean duplicates (keep oldest)
    clean_res = clean_duplicate_questions(action="keep_oldest")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # 2. Fix empty subjects
    from backend.classifier import classify_subject
    cursor.execute("SELECT id, content_text FROM questions WHERE subject IS NULL OR subject = '' OR subject = 'unknown'")
    unknown_rows = cursor.fetchall()
    reclassified = 0
    for row in unknown_rows:
        q_id, c_text = row[0], row[1]
        correct_sub = classify_subject(c_text)
        cursor.execute("UPDATE questions SET subject = ? WHERE id = ?", (correct_sub, q_id))
        reclassified += 1
        
    # 3. Resequence numbers again to guarantee 1..N continuous numbering
    resequence_question_numbers(cursor)

    # 4. Vacuum and analyze SQLite DB
    conn.commit()
    cursor.execute("VACUUM")
    cursor.execute("ANALYZE")
    conn.close()
    
    diag = run_database_diagnostics()
    return {
        "success": True,
        "corrupt_cleaned": corrupt_deleted,
        "duplicates_cleaned": clean_res["deleted_count"],
        "subjects_reclassified": reclassified,
        "current_total": diag["total_questions"],
        "diagnostics": diag
    }

def auto_generate_exam_questions(
    subject: str = "math",
    grade: int = 5,
    total_questions: int = 20,
    easy_count: int = 8,
    medium_count: int = 8,
    hard_count: int = 4,
    topic: Optional[str] = None
) -> Dict[str, Any]:
    """
    Auto-generates questions for an exam based on a difficulty matrix:
    easy, medium, hard, subject, and grade.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    selected_ids = []
    
    def fetch_by_diff(diff_values: List[str], needed: int, exclude: List[str]) -> List[Dict[str, Any]]:
        if needed <= 0:
            return []
        placeholders = ",".join(["?"] * len(diff_values))
        ex_placeholders = ",".join(["?"] * len(exclude)) if exclude else "''"
        
        # Exact subject and grade
        query = f"""
            SELECT * FROM questions
            WHERE subject = ? AND grade = ? AND difficulty IN ({placeholders})
            AND id NOT IN ({ex_placeholders})
            ORDER BY RANDOM()
            LIMIT ?
        """
        params = [subject, grade] + diff_values + exclude + [needed]
        cursor.execute(query, params)
        rows = [row_to_dict(r) for r in cursor.fetchall()]
        
        # Fallback 1: Exact subject, any grade
        if len(rows) < needed:
            remaining = needed - len(rows)
            current_exclude = exclude + [r["id"] for r in rows]
            ex_p = ",".join(["?"] * len(current_exclude))
            fb_query = f"""
                SELECT * FROM questions
                WHERE subject = ? AND difficulty IN ({placeholders})
                AND id NOT IN ({ex_p})
                ORDER BY RANDOM()
                LIMIT ?
            """
            cursor.execute(fb_query, [subject] + diff_values + current_exclude + [remaining])
            rows.extend([row_to_dict(r) for r in cursor.fetchall()])
            
        return rows
        
    easy_questions = fetch_by_diff(["easy"], easy_count, selected_ids)
    selected_ids.extend([q["id"] for q in easy_questions])
    
    medium_questions = fetch_by_diff(["medium"], medium_count, selected_ids)
    selected_ids.extend([q["id"] for q in medium_questions])
    
    hard_questions = fetch_by_diff(["hard", "olympiad"], hard_count, selected_ids)
    selected_ids.extend([q["id"] for q in hard_questions])
    
    all_selected = easy_questions + medium_questions + hard_questions
    if len(all_selected) < total_questions:
        shortfall = total_questions - len(all_selected)
        cur_ids = [q["id"] for q in all_selected]
        ex_p = ",".join(["?"] * len(cur_ids)) if cur_ids else "''"
        cursor.execute(f"""
            SELECT * FROM questions
            WHERE subject = ? AND id NOT IN ({ex_p})
            ORDER BY RANDOM()
            LIMIT ?
        """, [subject] + cur_ids + [shortfall])
        extra = [row_to_dict(r) for r in cursor.fetchall()]
        all_selected.extend(extra)
        
    conn.close()
    
    return {
        "success": True,
        "count": len(all_selected),
        "subject": subject,
        "grade": grade,
        "total_requested": total_questions,
        "total_found": len(all_selected),
        "easy_count": len(easy_questions),
        "medium_count": len(medium_questions),
        "hard_count": len(hard_questions),
        "questions": all_selected,
        "question_ids": [q["id"] for q in all_selected]
    }

def delete_question(question_id: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM questions WHERE id = ?", (question_id,))
    affected = cursor.rowcount
    if affected > 0:
        # Lazy resequence: mark flag instead of running O(N) update immediately
        cursor.execute("""
            INSERT OR REPLACE INTO system_config (key, value) 
            VALUES ('needs_resequence', '1')
        """)
        invalidate_stats_cache()
    conn.commit()
    conn.close()
    return affected > 0

def bulk_delete_questions(question_ids: List[str]) -> int:
    """
    Xóa nhiều câu hỏi an toàn trong 1 transaction SQLite duy nhất.
    Tự động chia batch 500 ID để không vượt giới hạn tham số SQLite.
    Bật cờ lazy resequence và vô hiệu hóa cache thống kê.
    """
    if not question_ids:
        return 0

    clean_ids = list(dict.fromkeys(str(qid).strip() for qid in question_ids if qid and str(qid).strip()))
    if not clean_ids:
        return 0

    conn = get_connection()
    cursor = conn.cursor()
    total_deleted = 0

    try:
        batch_size = 500
        for i in range(0, len(clean_ids), batch_size):
            chunk = clean_ids[i:i + batch_size]
            placeholders = ",".join("?" for _ in chunk)
            cursor.execute(f"DELETE FROM questions WHERE id IN ({placeholders})", chunk)
            total_deleted += cursor.rowcount

        if total_deleted > 0:
            cursor.execute("""
                INSERT OR REPLACE INTO system_config (key, value) 
                VALUES ('needs_resequence', '1')
            """)
            invalidate_stats_cache()

        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

    return total_deleted

def bulk_update_questions_grade(question_ids: List[str], grade: int) -> int:
    """
    Cập nhật khối lớp (Lớp 1 đến 12) hàng loạt trong 1 transaction SQLite.
    Cập nhật đồng thời trường updated_at ISO timestamp.
    """
    if not (1 <= grade <= 12):
        raise ValueError(f"Khối lớp không hợp lệ: {grade}. Chỉ chấp nhận từ 1 đến 12.")

    if not question_ids:
        return 0

    clean_ids = list(dict.fromkeys(str(qid).strip() for qid in question_ids if qid and str(qid).strip()))
    if not clean_ids:
        return 0

    conn = get_connection()
    cursor = conn.cursor()
    total_updated = 0
    now = datetime.now().isoformat()

    try:
        batch_size = 500
        for i in range(0, len(clean_ids), batch_size):
            chunk = clean_ids[i:i + batch_size]
            placeholders = ",".join("?" for _ in chunk)
            cursor.execute(
                f"UPDATE questions SET grade = ?, updated_at = ? WHERE id IN ({placeholders})",
                [grade, now] + chunk
            )
            total_updated += cursor.rowcount

        if total_updated > 0:
            invalidate_stats_cache()

        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

    return total_updated

def get_stats() -> Dict[str, Any]:
    """Returns dashboard stats with in-memory TTL cache (5s)."""
    now = time.time()
    if _stats_cache["data"] and (now - _stats_cache["timestamp"]) < STATS_CACHE_TTL:
        return _stats_cache["data"]
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM questions")
    total_questions = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM exams")
    total_exams = cursor.fetchone()[0]
    
    # By platform
    cursor.execute("SELECT source_platform, COUNT(*) as count FROM questions GROUP BY source_platform")
    by_platform = {row["source_platform"]: row["count"] for row in cursor.fetchall()}

    # By subject
    cursor.execute("SELECT subject, COUNT(*) as count FROM questions GROUP BY subject")
    by_subject = {row["subject"]: row["count"] for row in cursor.fetchall() if row["subject"]}
    
    # By grade
    cursor.execute("SELECT grade, COUNT(*) as count FROM questions GROUP BY grade ORDER BY grade")
    by_grade = {str(row["grade"]): row["count"] for row in cursor.fetchall() if row["grade"] is not None}
    
    # By question type
    cursor.execute("SELECT question_type, COUNT(*) as count FROM questions GROUP BY question_type")
    by_type = {row["question_type"]: row["count"] for row in cursor.fetchall()}
    
    # By difficulty
    cursor.execute("SELECT difficulty, COUNT(*) as count FROM questions GROUP BY difficulty")
    by_difficulty = {row["difficulty"]: row["count"] for row in cursor.fetchall()}
    
    # Recent 5 questions
    cursor.execute("SELECT id, q_number, exam_name, source_platform, grade, subject, topic, question_type, content_text, created_at FROM questions ORDER BY created_at DESC LIMIT 5")
    recent = [dict(r) for r in cursor.fetchall()]
    
    conn.close()
    
    result = {
        "total_questions": total_questions,
        "total_exams": total_exams,
        "by_platform": by_platform,
        "by_subject": by_subject,
        "by_grade": by_grade,
        "by_type": by_type,
        "by_difficulty": by_difficulty,
        "recent_questions": recent
    }
    
    _stats_cache["data"] = result
    _stats_cache["timestamp"] = now
    return result

def get_stats_count() -> int:
    """Lightweight count-only for heartbeat polling (no cache needed, single fast query)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM questions")
    total = cursor.fetchone()[0]
    conn.close()
    return total

def maybe_resequence_deferred():
    """Check lazy resequence flag and run if needed. Call on startup or before bank view load."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT value FROM system_config WHERE key = 'needs_resequence'")
        row = cursor.fetchone()
        if row and row[0] == '1':
            resequence_question_numbers(cursor)
            cursor.execute("UPDATE system_config SET value = '0' WHERE key = 'needs_resequence'")
            conn.commit()
    except Exception:
        pass
    finally:
        conn.close()

# Exam functions
def create_exam(exam: Dict[str, Any]) -> str:
    conn = get_connection()
    cursor = conn.cursor()
    exam_id = exam.get("id") or str(uuid.uuid4())[:8]
    now = datetime.now().isoformat()
    q_ids_str = json.dumps(exam.get("question_ids", []), ensure_ascii=False)
    
    cursor.execute("""
        INSERT INTO exams (id, title, grade, duration_minutes, header_info, notes, question_ids, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        exam_id,
        exam.get("title", "Đề thi mới"),
        exam.get("grade", 5),
        exam.get("duration_minutes", 45),
        exam.get("header_info"),
        exam.get("notes"),
        q_ids_str,
        now
    ))
    conn.commit()
    conn.close()
    return exam_id

def get_exams() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM exams ORDER BY created_at DESC")
    rows = cursor.fetchall()
    exams = [row_to_dict(r) for r in rows]
    conn.close()
    return exams

def get_exam_by_id(exam_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM exams WHERE id = ?", (exam_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    exam = row_to_dict(row)
    
    # Fetch all questions in this exam
    q_ids = exam.get("question_ids", [])
    questions = []
    for qid in q_ids:
        cursor.execute("SELECT * FROM questions WHERE id = ?", (qid,))
        qr = cursor.fetchone()
        if qr:
            questions.append(row_to_dict(qr))
            
    exam["questions"] = questions
    conn.close()
    return exam

def delete_exam(exam_id: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM exams WHERE id = ?", (exam_id,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

# Logs
def log_collector_event(platform: str, status: str, message: str, count: int = 0):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO collector_logs (platform, status, message, items_count, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (platform, status, message, count, now))
    conn.commit()
    conn.close()

def get_collector_logs(limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM collector_logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def clear_collector_logs() -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM collector_logs")
    conn.commit()
    conn.close()
    return True


# ----------------- Practice History & Analytics -----------------

def save_practice_history(record: Dict[str, Any]) -> str:
    conn = get_connection()
    cursor = conn.cursor()
    p_id = record.get("id") or str(uuid.uuid4())[:12]
    now = record.get("created_at") or datetime.now().isoformat()
    
    answers_detail_str = None
    if "answers_detail" in record and record["answers_detail"] is not None:
        if isinstance(record["answers_detail"], str):
            answers_detail_str = record["answers_detail"]
        else:
            answers_detail_str = json.dumps(record["answers_detail"], ensure_ascii=False)
            
    cursor.execute("""
        INSERT INTO practice_history (
            id, exam_id, exam_title, subject, grade, total_questions,
            correct_count, wrong_count, skipped_count, score, max_score,
            duration_seconds, time_spent_seconds, ranking, answers_detail, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        p_id,
        record.get("exam_id"),
        record.get("exam_title", "Bài luyện tập"),
        record.get("subject", "math"),
        record.get("grade", 5),
        record.get("total_questions", 0),
        record.get("correct_count", 0),
        record.get("wrong_count", 0),
        record.get("skipped_count", 0),
        round(float(record.get("score", 0.0)), 2),
        round(float(record.get("max_score", 10.0)), 2),
        record.get("duration_seconds", 0),
        record.get("time_spent_seconds", 0),
        record.get("ranking", "Trung bình"),
        answers_detail_str,
        now
    ))
    conn.commit()
    conn.close()
    return p_id

def get_practice_history(limit: int = 50, subject: Optional[str] = None, grade: Optional[int] = None) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    conditions = []
    params = []
    if subject and subject != "all":
        conditions.append("subject = ?")
        params.append(subject)
    if grade and grade > 0:
        conditions.append("grade = ?")
        params.append(grade)
        
    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    cursor.execute(f"""
        SELECT * FROM practice_history
        {where_clause}
        ORDER BY created_at DESC
        LIMIT ?
    """, params + [limit])
    rows = cursor.fetchall()
    results = []
    for r in rows:
        d = dict(r)
        if d.get("answers_detail"):
            try:
                d["answers_detail"] = json.loads(d["answers_detail"])
            except Exception:
                pass
        if d.get("max_score") and d["max_score"] > 0:
            d["score_100"] = round((d["score"] / d["max_score"]) * 100.0, 1)
        else:
            d["score_100"] = round(d["score"] * 10.0, 1)
        results.append(d)
    conn.close()
    return results

def get_practice_history_by_id(record_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM practice_history WHERE id = ?", (record_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    if d.get("answers_detail"):
        try:
            d["answers_detail"] = json.loads(d["answers_detail"])
        except Exception:
            pass
    if d.get("max_score") and d["max_score"] > 0:
        d["score_100"] = round((d["score"] / d["max_score"]) * 100.0, 1)
    else:
        d["score_100"] = round(d["score"] * 10.0, 1)
    return d

def _evaluate_badges(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Evaluates 8 distinct gamification achievement badges."""
    total_attempts = len(history)
    max_score = max([float(h.get("score") or 0) for h in history], default=0.0)
    avg_score = round(sum([float(h.get("score") or 0) for h in history]) / total_attempts, 2) if total_attempts > 0 else 0.0
    excellent_count = sum(1 for h in history if (h.get("ranking") == "Xuất sắc" or float(h.get("score") or 0) >= 9.0))
    math_attempts = sum(1 for h in history if h.get("subject") == "math")
    subjects_practiced = set(h.get("subject") for h in history if h.get("subject"))
    fast_attempts = sum(1 for h in history if (h.get("time_spent_seconds", 0) > 0 and h.get("duration_seconds", 0) > 0 and h.get("time_spent_seconds", 0) <= h.get("duration_seconds", 0) / 2 and float(h.get("score") or 0) >= 8.0))
    perfect_attempts = sum(1 for h in history if float(h.get("score") or 0) >= float(h.get("max_score") or 10.0))
    
    badge_defs = [
        {
            "id": "badge_first_step",
            "title": "Bước Đầu Chinh Phục",
            "description": "Hoàn thành bài thi luyện tập đầu tiên",
            "icon": "🌱",
            "category": "milestone",
            "unlocked": total_attempts >= 1,
            "progress": f"{min(total_attempts, 1)}/1 bài"
        },
        {
            "id": "badge_perfect_score",
            "title": "Điểm Mười Hoàn Hảo",
            "description": "Đạt điểm tuyệt đối (10/10) trong một bài luyện tập",
            "icon": "💯",
            "category": "accuracy",
            "unlocked": perfect_attempts >= 1 or max_score >= 10.0,
            "progress": f"{perfect_attempts}/1 lần điểm 10"
        },
        {
            "id": "badge_speed_racer",
            "title": "Tốc Độ Siêu Phàm",
            "description": "Nộp bài dưới 50% thời gian cho phép và đạt điểm Giỏi trở lên",
            "icon": "⚡",
            "category": "speed",
            "unlocked": fast_attempts >= 1,
            "progress": f"{fast_attempts}/1 lần"
        },
        {
            "id": "badge_math_master",
            "title": "Chiến Binh Toán Học",
            "description": "Luyện tập hoàn thành ít nhất 3 đề Toán",
            "icon": "📐",
            "category": "subject",
            "unlocked": math_attempts >= 3,
            "progress": f"{min(math_attempts, 3)}/3 bài Toán"
        },
        {
            "id": "badge_scholar",
            "title": "Học Giả Xuất Sắc",
            "description": "Đạt xếp loại Xuất sắc (>= 9.0) ít nhất 3 lần",
            "icon": "👑",
            "category": "mastery",
            "unlocked": excellent_count >= 3,
            "progress": f"{min(excellent_count, 3)}/3 lần Xuất sắc"
        },
        {
            "id": "badge_persistent",
            "title": "Chiến Binh Bền Bỉ",
            "description": "Kiên trì hoàn thành 5 bài thi luyện tập",
            "icon": "🛡️",
            "category": "persistence",
            "unlocked": total_attempts >= 5,
            "progress": f"{min(total_attempts, 5)}/5 bài"
        },
        {
            "id": "badge_multilingual",
            "title": "Toàn Năng Đa Môn",
            "description": "Luyện tập tối thiểu 2 môn học khác nhau",
            "icon": "🌟",
            "category": "breadth",
            "unlocked": len(subjects_practiced) >= 2,
            "progress": f"{min(len(subjects_practiced), 2)}/2 môn"
        },
        {
            "id": "badge_top_tier",
            "title": "Đỉnh Cao Tri Thức",
            "description": "Duy trì điểm trung bình tổng thể từ 8.5 điểm trở lên",
            "icon": "🏆",
            "category": "excellence",
            "unlocked": total_attempts >= 3 and avg_score >= 8.5,
            "progress": f"ĐTB {avg_score}/8.5 ({total_attempts}/3 bài)"
        }
    ]
    return badge_defs

def get_practice_analytics(subject: Optional[str] = None, grade: Optional[int] = None) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    
    conditions = []
    params = []
    if subject and subject != "all":
        conditions.append("subject = ?")
        params.append(subject)
    if grade and grade > 0:
        conditions.append("grade = ?")
        params.append(grade)
        
    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    
    cursor.execute(f"SELECT COUNT(*) FROM practice_history {where_clause}", params)
    total_attempts = cursor.fetchone()[0]
    
    if total_attempts == 0:
        conn.close()
        return {
            "total_attempts": 0,
            "total_questions_answered": 0,
            "total_correct": 0,
            "overall_accuracy": 0.0,
            "average_score": 0.0,
            "highest_score": 0.0,
            "trending_scores": [],
            "subject_mastery": [],
            "recent_history": [],
            "badges": _evaluate_badges([])
        }
        
    cursor.execute(f"""
        SELECT 
            SUM(total_questions) as total_q,
            SUM(correct_count) as total_c,
            AVG(score) as avg_s,
            MAX(score) as max_s
        FROM practice_history {where_clause}
    """, params)
    agg = cursor.fetchone()
    total_questions = agg[0] or 0
    total_correct = agg[1] or 0
    avg_score = round(float(agg[2] or 0.0), 2)
    max_score = round(float(agg[3] or 0.0), 2)
    overall_accuracy = round((total_correct / total_questions * 100.0), 1) if total_questions > 0 else 0.0
    
    # Chronological trending scores (up to 30)
    cursor.execute(f"""
        SELECT id, exam_title, subject, score, max_score, created_at, ranking
        FROM practice_history {where_clause}
        ORDER BY created_at ASC
        LIMIT 30
    """, params)
    trend_rows = cursor.fetchall()
    trending_scores = []
    for r in trend_rows:
        sc = float(r["score"])
        m_sc = float(r["max_score"]) if r["max_score"] else 10.0
        pct = round((sc / m_sc * 100.0), 1) if m_sc > 0 else sc * 10.0
        trending_scores.append({
            "id": r["id"],
            "exam_title": r["exam_title"],
            "subject": r["subject"],
            "score": sc,
            "max_score": m_sc,
            "percentage": pct,
            "ranking": r["ranking"],
            "created_at": r["created_at"]
        })
        
    # Subject mastery breakdown
    cursor.execute("""
        SELECT 
            subject,
            COUNT(*) as attempts,
            SUM(total_questions) as sub_total_q,
            SUM(correct_count) as sub_correct,
            AVG(score) as sub_avg_score
        FROM practice_history
        GROUP BY subject
    """)
    sub_rows = cursor.fetchall()
    subject_labels = {
        "math": "Toán học",
        "vietnamese": "Tiếng Việt",
        "english": "Tiếng Anh",
        "science": "Khoa học",
        "informatics": "Tin học"
    }
    subject_mastery = []
    for sr in sub_rows:
        s_name = sr["subject"] or "math"
        s_tot = sr["sub_total_q"] or 0
        s_cor = sr["sub_correct"] or 0
        s_acc = round((s_cor / s_tot * 100.0), 1) if s_tot > 0 else 0.0
        subject_mastery.append({
            "subject": s_name,
            "subject_label": subject_labels.get(s_name, s_name.capitalize()),
            "attempts": sr["attempts"],
            "total_questions": s_tot,
            "correct_count": s_cor,
            "accuracy_rate": s_acc,
            "average_score": round(float(sr["sub_avg_score"] or 0.0), 2)
        })
        
    cursor.execute("SELECT * FROM practice_history ORDER BY created_at DESC")
    all_history = [dict(r) for r in cursor.fetchall()]
    badges = _evaluate_badges(all_history)
    
    conn.close()
    recent_history = get_practice_history(limit=10, subject=subject, grade=grade)
    
    return {
        "total_attempts": total_attempts,
        "total_questions_answered": total_questions,
        "total_correct": total_correct,
        "overall_accuracy": overall_accuracy,
        "average_score": avg_score,
        "highest_score": max_score,
        "trending_scores": trending_scores,
        "subject_mastery": subject_mastery,
        "recent_history": recent_history,
        "badges": badges
    }

# ============================================================================
# Active Lexicon Learning (Human-in-the-Loop OCR Memory)
# ============================================================================
_ocr_corrections_cache = {"data": None, "timestamp": 0}
OCR_CORRECTIONS_TTL = 15  # seconds

def invalidate_ocr_corrections_cache():
    """Expires in-memory cache of user-trained OCR corrections."""
    _ocr_corrections_cache["data"] = None
    _ocr_corrections_cache["timestamp"] = 0

def record_ocr_learning_diff(raw_text: str, corrected_text: str, source: str = "manual_feedback") -> List[Dict[str, Any]]:
    """
    Compares original raw OCR text with human-corrected text using SequenceMatcher.
    Extracts phrase/word-level corrections and stores/updates them in ocr_corrections.
    Returns list of newly learned or incremented items.
    """
    if not raw_text or not corrected_text:
        return []

    import difflib
    import unicodedata

    raw_norm = unicodedata.normalize('NFC', raw_text.strip())
    corr_norm = unicodedata.normalize('NFC', corrected_text.strip())
    if raw_norm == corr_norm:
        return []

    raw_tokens = raw_norm.split()
    corr_tokens = corr_norm.split()

    matcher = difflib.SequenceMatcher(None, raw_tokens, corr_tokens)
    learned = []

    now_iso = datetime.now().isoformat()
    conn = get_connection()
    cursor = conn.cursor()

    try:
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'replace':
                raw_slice = raw_tokens[i1:i2]
                corr_slice = corr_tokens[j1:j2]

                # Limit phrase length to max 12 words to avoid full-paragraph mismatches
                if len(raw_slice) > 12 or len(corr_slice) > 12:
                    continue

                w = " ".join(raw_slice).strip('.,:;!?()[]{}"\' \t\n')
                c = " ".join(corr_slice).strip('.,:;!?()[]{}"\' \t\n')

                if not w or not c:
                    continue
                if w.lower() == c.lower():
                    continue
                if len(w) < 2 or len(c) < 2:
                    continue
                if w.isdigit() and c.isdigit():
                    continue

                # Upsert into ocr_corrections
                cursor.execute("""
                    INSERT INTO ocr_corrections (wrong_text, correct_text, frequency, source, created_at, updated_at)
                    VALUES (?, ?, 1, ?, ?, ?)
                    ON CONFLICT(wrong_text) DO UPDATE SET
                        correct_text = excluded.correct_text,
                        frequency = frequency + 1,
                        updated_at = excluded.updated_at
                """, (w, c, source, now_iso, now_iso))

                learned.append({"wrong": w, "correct": c})

        conn.commit()
        if learned:
            invalidate_ocr_corrections_cache()
    except Exception as e:
        print(f"[record_ocr_learning_diff] Error: {e}")
    finally:
        conn.close()

    return learned

def get_ocr_corrections_map() -> Dict[str, str]:
    """Returns mapping wrong_text -> correct_text ordered by descending length so longer phrases replace first."""
    global _ocr_corrections_cache
    now = time.time()
    if _ocr_corrections_cache["data"] is not None and (now - _ocr_corrections_cache["timestamp"] < OCR_CORRECTIONS_TTL):
        return _ocr_corrections_cache["data"]

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT wrong_text, correct_text FROM ocr_corrections ORDER BY LENGTH(wrong_text) DESC")
        rows = cursor.fetchall()
        mapping = {r[0]: r[1] for r in rows}
        _ocr_corrections_cache["data"] = mapping
        _ocr_corrections_cache["timestamp"] = now
        return mapping
    except Exception as e:
        return {}
    finally:
        conn.close()

def get_ocr_corrections(page: int = 1, page_size: int = 50, search: str = "") -> Tuple[List[Dict[str, Any]], int]:
    """Retrieves paginated list of learned OCR corrections for dashboard view."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        where_clause = ""
        params = []
        if search:
            where_clause = "WHERE wrong_text LIKE ? OR correct_text LIKE ?"
            s_param = f"%{search}%"
            params.extend([s_param, s_param])

        cursor.execute(f"SELECT COUNT(*) FROM ocr_corrections {where_clause}", params)
        total = cursor.fetchone()[0]

        offset = (page - 1) * page_size
        params.extend([page_size, offset])
        cursor.execute(f"""
            SELECT id, wrong_text, correct_text, frequency, source, created_at, updated_at
            FROM ocr_corrections
            {where_clause}
            ORDER BY frequency DESC, updated_at DESC
            LIMIT ? OFFSET ?
        """, params)
        items = [dict(r) for r in cursor.fetchall()]
        return items, total
    finally:
        conn.close()

def add_manual_ocr_correction(wrong_text: str, correct_text: str, source: str = "manual_rule") -> Dict[str, Any]:
    """Manually adds or updates a specific correction rule in the lexicon."""
    w = wrong_text.strip()
    c = correct_text.strip()
    if not w or not c:
        raise ValueError("Từ sai và từ sửa đổi không được để trống")
    now_iso = datetime.now().isoformat()
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO ocr_corrections (wrong_text, correct_text, frequency, source, created_at, updated_at)
            VALUES (?, ?, 1, ?, ?, ?)
            ON CONFLICT(wrong_text) DO UPDATE SET
                correct_text = excluded.correct_text,
                frequency = frequency + 1,
                updated_at = excluded.updated_at
        """, (w, c, source, now_iso, now_iso))
        conn.commit()
        cursor.execute("SELECT id, wrong_text, correct_text, frequency, source, created_at, updated_at FROM ocr_corrections WHERE wrong_text = ?", (w,))
        row = cursor.fetchone()
        invalidate_ocr_corrections_cache()
        return dict(row) if row else {"wrong_text": w, "correct_text": c, "source": source}
    finally:
        conn.close()

def delete_ocr_correction(correction_id: int) -> bool:
    """Deletes a learned correction rule by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM ocr_corrections WHERE id = ?", (correction_id,))
        affected = cursor.rowcount > 0
        conn.commit()
        if affected:
            invalidate_ocr_corrections_cache()
        return affected
    finally:
        conn.close()

def clear_all_ocr_corrections() -> int:
    """Clears all learned corrections."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM ocr_corrections")
        affected = cursor.rowcount
        conn.commit()
        invalidate_ocr_corrections_cache()
        return affected
    finally:
        conn.close()


