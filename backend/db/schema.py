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
from backend.db.base import compute_content_hash, get_connection


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
        has_handwriting INTEGER DEFAULT 0,
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
    if "has_handwriting" not in existing_cols:
        cursor.execute("ALTER TABLE questions ADD COLUMN has_handwriting INTEGER DEFAULT 0;")
        
    # Indexes for fast querying & filtering
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_q_number ON questions (q_number);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_q_platform ON questions (source_platform);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_q_grade ON questions (grade);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_q_subject ON questions (subject);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_q_type ON questions (question_type);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_q_diff ON questions (difficulty);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_q_created ON questions (created_at DESC);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_q_content_hash ON questions (content_hash);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_q_has_handwriting ON questions (has_handwriting);")
    
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

    # 9. Review Queue Table (Spaced Repetition — P1.3b)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS review_queue (
        question_id TEXT PRIMARY KEY,
        subject TEXT DEFAULT 'math',
        grade INTEGER DEFAULT 5,
        repetitions INTEGER DEFAULT 0,
        interval_days INTEGER DEFAULT 1,
        due_at TEXT,
        last_result TEXT,
        updated_at TEXT
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_review_due_at ON review_queue (due_at);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_review_subject_grade ON review_queue (subject, grade);")

    # 10. Account Auth Tables (login/register/approval/sessions).
    # Logic lives in backend/auth.py; tables are created here so every
    # init_db() (app start, backup-restore) carries them.
    from backend.auth import init_auth_tables
    init_auth_tables(conn)

    conn.commit()
    conn.close()
