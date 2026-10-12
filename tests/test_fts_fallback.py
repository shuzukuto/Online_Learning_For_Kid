"""RED/GREEN: FTS5 syntax error must fallback to LIKE, never HTTP 500.

Bug (3 ban phan bien AI): get_questions() boc try/except quanh viec
XAY CAU truy van FTS (dong 282-301) nhung khong boc lenh THUC THI
cursor.execute() (dong 309/330). Chuoi toan dau nhay (vd '\"\"\"')
vuot qua escape → sqlite3.OperationalError: fts5: syntax error →
API crash 500 thay vi fallback LIKE.

Test dung DB tam rieng (khong ghi DB live), chen 1 cau roi search
chuoi nguy hiem — phai tra ket qua binh thuong, khong nem ngoai le.
"""
from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _make_tmp_db(monkeypatch, tmp_path):
    import backend.db.base as base
    tmp_db = str(tmp_path / "fts_test.db")
    monkeypatch.setattr(base, "DB_PATH", tmp_db)
    import backend.database as shim
    monkeypatch.setattr(shim, "DB_PATH", tmp_db)
    import backend.db.questions as Q
    monkeypatch.setattr(Q, "DB_PATH", tmp_db)
    # get_connection doc tu base.DB_PATH luc goi → patch ca base
    from backend.database import init_db
    init_db()
    return Q


def test_fts_malicious_quotes_fallback_no_crash(monkeypatch, tmp_path):
    Q = _make_tmp_db(monkeypatch, tmp_path)
    from backend.database import insert_or_update_question
    rid = insert_or_update_question({
        "id": "fts_probe_01",
        "content_text": "Tính giá trị biểu thức phân số một phần hai",
        "content_html": "<p>Tính giá trị biểu thức phân số một phần hai</p>",
        "subject": "math", "grade": 5,
    })
    assert rid, "khong chen duoc cau probe"
    # Chuoi toan dau nhay: escape thanh '\"\"\"' → FTS crash neu khong boc
    items, total = Q.get_questions(search='"""', page_size=10)
    assert isinstance(items, list) and isinstance(total, int)


def test_fts_normal_search_still_works(monkeypatch, tmp_path):
    Q = _make_tmp_db(monkeypatch, tmp_path)
    from backend.database import insert_or_update_question
    insert_or_update_question({
        "id": "fts_probe_02",
        "content_text": "Mẹ mua gạo giá năm mươi nghìn đồng",
        "content_html": "<p>Mẹ mua gạo giá năm mươi nghìn đồng</p>",
        "subject": "math", "grade": 2,
    })
    items, total = Q.get_questions(search="gạo giá", page_size=10)
    assert total >= 1, "search thuong mat ket qua sau fix fallback"
