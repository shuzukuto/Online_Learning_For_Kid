from __future__ import annotations
import hashlib
import json
import os
import random
import re
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from backend.db.base import (
    DB_PATH, STATS_CACHE_TTL, VN_TZ, _stats_cache, compute_content_hash,
    get_connection, invalidate_stats_cache, resequence_question_numbers,
)


def compute_source_detail(q: Dict[str, Any]) -> str:
    """Computes a human-readable, descriptive source name for a question, never duplicating raw hunter platform name."""
    explicit = (q.get("source_detail") or "").strip()
    plat = (q.get("source_platform") or "").strip().lower()

    # AI Agent Import
    if plat == "ai_agent_import" or explicit.lower() in ("ai_agent_import", "ai agent import"):
        return "AI Agent Import"

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
    d["has_handwriting"] = bool(d.get("has_handwriting", 0))

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
    created_date: Optional[str] = None,
    only_duplicates: bool = False,
    sort_by: str = "q_number_asc",
    page: int = 1,
    page_size: int = 20,
    has_handwriting: Optional[bool] = None
) -> Tuple[List[Dict[str, Any]], int]:
    # Hard cap: chan page_size khong lo de chua chay DoS du goi noi bo
    MAX_DB_PAGE_SIZE = 200
    try:
        page = max(1, int(page))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = max(1, min(int(page_size), MAX_DB_PAGE_SIZE))
    except (TypeError, ValueError):
        page_size = 20
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
        
    if grade is not None and str(grade).strip() != "" and int(grade) >= 0:
        conditions.append("grade = ?")
        params.append(int(grade))

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
        if sd in ("ai_agent_import", "ai agent import"):
            conditions.append("LOWER(source_platform) = 'ai_agent_import'")
        elif sd == "codemath":
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

    if created_date and str(created_date).strip() != "":
        conditions.append("DATE(created_at) = DATE(?)")
        params.append(str(created_date).strip())

    if has_handwriting is not None:
        conditions.append("has_handwriting = ?")
        params.append(1 if has_handwriting else 0)

    if only_duplicates:
        conditions.append("""
            content_hash IN (
                SELECT content_hash FROM questions 
                WHERE content_hash IS NOT NULL
                GROUP BY content_hash HAVING COUNT(*) > 1
            )
        """)

    fts_used = False
    fts_query = None
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
                fts_used = True
            except Exception:
                # Fallback to LIKE if FTS5 is not available
                conditions.append("(content_text LIKE ? OR exam_name LIKE ? OR topic LIKE ? OR explanation LIKE ?)")
                term = f"%{search_term}%"
                params.extend([term, term, term, term])

    def _like_params(base_params, fts_query_value):
        """Thay param FTS bang 4 param LIKE khi execute FTS crash."""
        out = [p for p in base_params if p != fts_query_value]
        term = f"%{search_term}%"
        out.extend([term, term, term, term])
        return out

    def _to_like_where(base_where):
        import re as _re
        return _re.sub(
            r"rowid\s+IN\s*\(\s*SELECT\s+rowid\s+FROM\s+questions_fts\s+WHERE\s+questions_fts\s+MATCH\s+\?\s*\)",
            "(content_text LIKE ? OR exam_name LIKE ? OR topic LIKE ? OR explanation LIKE ?)",
            base_where, flags=re.IGNORECASE | re.DOTALL,
        )

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    # Count total — FTS co the crash luc THUC THI (vd chuoi toan dau nhay
    # vuot qua escape) → fallback LIKE thay vi 500 (3 ban AI 2026-10-12).
    count_sql = f"SELECT COUNT(*) FROM questions {where_clause}"
    try:
        cursor.execute(count_sql, params)
    except sqlite3.OperationalError:
        if not fts_used:
            raise
        where_clause = _to_like_where(where_clause)
        params = _like_params(params, fts_query)
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
    
    now = datetime.now(VN_TZ).isoformat()
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
                has_handwriting = ?,
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
            1 if q.get("has_handwriting") else 0,
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
            has_handwriting, content_hash, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        1 if q.get("has_handwriting") else 0,
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
                now = datetime.now(VN_TZ).isoformat()
                q_id = q.get("id") or str(uuid.uuid4())[:12]
                resolved_detail = compute_source_detail(q)
                cursor.execute("SELECT COALESCE(MAX(q_number), 0) + 1 FROM questions")
                next_q_num = cursor.fetchone()[0]
                
                cursor.execute("""
                    INSERT OR IGNORE INTO questions (
                        id, q_number, source_platform, source_detail, source_url, exam_name, year, grade,
                        subject, topic, question_type, content_html, content_text,
                        images, options, correct_answer, explanation, difficulty,
                        has_handwriting, content_hash, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    1 if q.get("has_handwriting") else 0,
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
    Guarantees:
    - Zero isomorphic duplicate questions (different templates, numbers, methods).
    - Diverse archetypes across mathematical and linguistic concepts.
    """
    from backend.exam_smart_mixer import (
        select_diverse_exam_questions,
        analyze_exam_diversity,
        extract_template_signature,
        classify_problem_archetype
    )
    from backend.normalizer import is_valid_question_payload

    conn = get_connection()
    cursor = conn.cursor()
    
    def fetch_candidates(diff_values: List[str], target_grade: int, target_topic: Optional[str]) -> List[Dict[str, Any]]:
        placeholders = ",".join(["?"] * len(diff_values))
        params = [subject] + diff_values
        topic_clause = ""
        if target_topic and target_topic.strip():
            topic_clause = " AND (topic LIKE ? OR content_text LIKE ?) "
            params.extend([f"%{target_topic.strip()}%", f"%{target_topic.strip()}%"])
            
        # Priority: target grade first, then other grades in same subject
        query = f"""
            SELECT * FROM questions
            WHERE subject = ? AND difficulty IN ({placeholders})
            {topic_clause}
            ORDER BY CASE WHEN grade = {target_grade} THEN 0 ELSE 1 END, RANDOM()
        """
        cursor.execute(query, params)
        raw_rows = [row_to_dict(r) for r in cursor.fetchall()]
        
        # Keep only educational questions (filter web noise)
        valid_candidates = []
        for r in raw_rows:
            is_valid, _ = is_valid_question_payload(r)
            if is_valid:
                valid_candidates.append(r)
        return valid_candidates

    # Fetch candidate pools
    easy_cands = fetch_candidates(["easy"], grade, topic)
    med_cands = fetch_candidates(["medium"], grade, topic)
    hard_cands = fetch_candidates(["hard", "olympiad"], grade, topic)
    conn.close()

    all_selected: List[Dict[str, Any]] = []

    # 1. Easy Questions
    selected_easy = select_diverse_exam_questions(
        candidates=easy_cands,
        count=easy_count,
        already_selected=all_selected
    )
    all_selected.extend(selected_easy)

    # 2. Medium Questions
    selected_med = select_diverse_exam_questions(
        candidates=med_cands,
        count=medium_count,
        already_selected=all_selected
    )
    all_selected.extend(selected_med)

    # 3. Hard Questions
    selected_hard = select_diverse_exam_questions(
        candidates=hard_cands,
        count=hard_count,
        already_selected=all_selected
    )
    all_selected.extend(selected_hard)

    # Diversity analysis
    diversity_report = analyze_exam_diversity(all_selected)

    return {
        "success": True,
        "count": len(all_selected),
        "subject": subject,
        "grade": grade,
        "total_requested": total_questions,
        "total_found": len(all_selected),
        "easy_count": len(selected_easy),
        "medium_count": len(selected_med),
        "hard_count": len(selected_hard),
        "questions": all_selected,
        "question_ids": [q["id"] for q in all_selected],
        "diversity_score": diversity_report["diversity_score"],
        "diversity_status": diversity_report["status"],
        "diversity_message": diversity_report["message"],
        "archetypes": diversity_report["archetypes"]
    }



def fetch_diverse_replacement_question(
    subject: str = "math",
    grade: int = 5,
    difficulty: str = "medium",
    exclude_templates: Optional[Set[str]] = None,
    exclude_ids: Optional[Set[str]] = None
) -> Optional[Dict[str, Any]]:
    """
    Finds a single replacement question matching difficulty/subject whose
    template is not in exclude_templates and id is not in exclude_ids.
    """
    from backend.exam_smart_mixer import extract_template_signature
    from backend.normalizer import is_valid_question_payload
    
    conn = get_connection()
    cursor = conn.cursor()
    
    diff_values = ["hard", "olympiad"] if difficulty in ["hard", "olympiad"] else [difficulty]
    placeholders = ",".join(["?"] * len(diff_values))
    
    query = f"""
        SELECT * FROM questions
        WHERE subject = ? AND difficulty IN ({placeholders})
        ORDER BY CASE WHEN grade = ? THEN 0 ELSE 1 END, RANDOM()
        LIMIT 60
    """
    cursor.execute(query, [subject] + diff_values + [grade])
    rows = [row_to_dict(r) for r in cursor.fetchall()]
    conn.close()
    
    ex_tpls = exclude_templates or set()
    ex_ids = exclude_ids or set()
    
    for r in rows:
        if r["id"] in ex_ids:
            continue
        is_valid, _ = is_valid_question_payload(r)
        if not is_valid:
            continue
        sig = extract_template_signature(r.get("content_text") or "")
        if sig not in ex_tpls:
            return r
            
    return None



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
    now = datetime.now(VN_TZ).isoformat()

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
