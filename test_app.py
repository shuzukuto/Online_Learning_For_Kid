import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from backend.database import init_db, get_stats, get_questions, insert_or_update_question
from backend.normalizer import clean_html_and_math
from backend.classifier import classify_subject
from backend.docx_exporter import generate_exam_docx
from backend.app import app
from fastapi.testclient import TestClient

def test_full_pipeline():
    print("1. Kiểm tra khởi tạo Cơ sở dữ liệu SQLite...")
    init_db()
    stats = get_stats()
    print(f"   => Khởi tạo DB thành công! Tổng số câu hỏi hiện có: {stats['total_questions']}")

    print("\n2. Kiểm tra chuẩn hóa công thức Toán học (LaTeX & MathJax)...")
    raw_html = '<span class="math-tex">\\( \\frac{3}{4} + \\sqrt{16} \\)</span> và $x^2$'
    clean_html, clean_txt = clean_html_and_math(raw_html)
    print(f"   => Raw: {raw_html}")
    print(f"   => Clean HTML: {clean_html}")
    print(f"   => Clean Text: {clean_txt}")
    assert "$\\frac{3}{4} + \\sqrt{16}$" in clean_html

    print("\n3. Kiểm tra Bộ phân loại Bộ môn Thông minh (AI Subject Classifier)...")
    sub_math = classify_subject(content_text="Tính giá trị biểu thức phân số 1/2 + 3/4", content_html="$\\frac{1}{2}$")
    print(f"   => Test Toán: {sub_math} (kỳ vọng 'math')")
    assert sub_math == "math"

    sub_vn = classify_subject(content_text="Trong các câu sau, câu nào có sử dụng biện pháp nghệ thuật nhân hóa và từ đồng nghĩa?")
    print(f"   => Test Tiếng Việt: {sub_vn} (kỳ vọng 'vietnamese')")
    assert sub_vn == "vietnamese"

    sub_en = classify_subject(content_text="Choose the correct answer: Where did you go yesterday afternoon?")
    print(f"   => Test Tiếng Anh: {sub_en} (kỳ vọng 'english')")
    assert sub_en == "english"

    sub_sci = classify_subject(content_text="Quá trình quang hợp của thực vật diễn ra dưới ánh sáng mặt trời tạo ra chất gì?")
    print(f"   => Test Khoa học: {sub_sci} (kỳ vọng 'science')")
    assert sub_sci == "science"

    print("\n4. Kiểm tra Nạp dữ liệu mẫu ban đầu qua FastAPI Client...")
    client = TestClient(app)
    resp = client.post("/api/init-samples")
    assert resp.status_code == 200
    res_data = resp.json()
    print(f"   => Nạp mẫu thành công: {res_data['message']}")

    print("\n5. Kiểm tra Săn câu hỏi Internet tự động (Internet Question Hunter API)...")
    resp_hunter = client.post("/api/hunter/run", json={"subject": "vietnamese", "grade": 4})
    assert resp_hunter.status_code == 200
    hunter_data = resp_hunter.json()
    print(f"   => Săn câu hỏi Tiếng Việt: {hunter_data['total_harvested']} câu thành công!")
    assert hunter_data["total_harvested"] >= 1

    resp_hunter_en = client.post("/api/hunter/run", json={"subject": "english", "grade": 5})
    assert resp_hunter_en.status_code == 200
    hunter_en_data = resp_hunter_en.json()
    print(f"   => Săn câu hỏi Tiếng Anh: {hunter_en_data['total_harvested']} câu thành công!")
    assert hunter_en_data["total_harvested"] >= 1

    print("\n6. Kiểm tra Lọc theo Bộ môn trong Ngân hàng câu hỏi...")
    resp_vn_q = client.get("/api/questions?subject=vietnamese")
    assert resp_vn_q.status_code == 200
    vn_data = resp_vn_q.json()
    print(f"   => Số câu hỏi Tiếng Việt tìm thấy: {vn_data['total']}")
    assert vn_data["total"] >= 1
    for item in vn_data["items"]:
        assert item["subject"] == "vietnamese"

    resp_en_q = client.get("/api/questions?subject=english")
    assert resp_en_q.status_code == 200
    en_data = resp_en_q.json()
    print(f"   => Số câu hỏi Tiếng Anh tìm thấy: {en_data['total']}")
    assert en_data["total"] >= 1
    for item in en_data["items"]:
        assert item["subject"] == "english"

    print("\n7. Kiểm tra Lọc & Tìm kiếm nền tảng Olympic TIMO...")
    resp_q = client.get("/api/questions?platform=timo")
    assert resp_q.status_code == 200
    q_data = resp_q.json()
    print(f"   => Số câu hỏi TIMO tìm thấy: {q_data['total']}")
    assert q_data['total'] >= 1

    print("\n8. Kiểm tra Xuất Đề thi sang Microsoft Word (.docx)...")
    questions = q_data["items"]
    exam_payload = {
        "title": "KỲ THI THỬ TOÁN HỌC OLYMPIC QUỐC TẾ",
        "header_info": "PHÒNG GIÁO DỤC VÀ ĐÀO TẠO - CLC",
        "grade": 5,
        "duration_minutes": 45,
        "question_ids": [q["id"] for q in questions]
    }
    resp_docx = client.post("/api/export/docx", json=exam_payload)
    assert resp_docx.status_code == 200
    docx_bytes = resp_docx.content
    print(f"   => Tạo file Word thành công! Kích thước file: {len(docx_bytes)} bytes")
    assert len(docx_bytes) > 2000

    print("\n9. Kiểm tra Dashboard Stats API (Thống kê theo môn học)...")
    resp_stats = client.get("/api/stats")
    assert resp_stats.status_code == 200
    new_stats = resp_stats.json()
    print(f"   => Thống kê tổng câu hỏi: {new_stats['total_questions']}")
    print(f"   => Theo nền tảng: {new_stats['by_platform']}")
    print(f"   => Theo bộ môn: {new_stats['by_subject']}")
    assert "vietnamese" in new_stats["by_subject"]
    assert "english" in new_stats["by_subject"]
    assert "math" in new_stats["by_subject"]

    print("\n10. Kiểm tra Săn câu hỏi với danh sách custom_urls...")
    resp_hunter_multi = client.post("/api/hunter/run", json={
        "subject": "math",
        "grade": 5,
        "custom_urls": ["https://khoade.edu.vn/toan-5"]
    })
    assert resp_hunter_multi.status_code == 200
    data_hunter_multi = resp_hunter_multi.json()
    print(f"   => Kết quả Săn đa link: Thu thập thành công {data_hunter_multi['total_harvested']} câu!")
    assert data_hunter_multi["success"] is True

    print("\n11. Kiểm tra Đồng bộ Tự động Nhật ký Extension (Log Auto-Save Sync)...")
    resp_sync = client.post("/api/collect/logs/sync", json={
        "platform": "extension",
        "status": "success",
        "message": "Bắt được 5 câu hỏi VioEdu từ phòng thi",
        "count": 5
    })
    assert resp_sync.status_code == 200
    assert resp_sync.json()["success"] is True

    resp_logs = client.get("/api/collect/logs")
    assert resp_logs.status_code == 200
    logs = resp_logs.json()
    assert len(logs) > 0
    assert any("Bắt được 5 câu hỏi VioEdu" in l["message"] for l in logs)
    print("   => Tự động lưu nhật ký hoạt động vào SQLite DB thành công 100%!")

    print("\n12. Kiểm tra Đánh số câu hỏi từ 1 đến N (Persistent Question ID)...")
    resp_all_q = client.get("/api/questions?sort_by=q_number_asc&page_size=100")
    assert resp_all_q.status_code == 200
    all_q_data = resp_all_q.json()
    items = all_q_data["items"]
    assert len(items) > 0
    print(f"   => Tổng số câu hỏi trả về: {len(items)}")
    for i, item in enumerate(items):
        expected_num = i + 1
        assert item.get("q_number") == expected_num, f"Expected q_number {expected_num}, got {item.get('q_number')}"
    print(f"   => Đã xác thực thành công đánh số thứ tự từ 1 đến {len(items)} không bị đứt đoạn!")

    # Test search by number
    test_target_num = min(5, len(items))
    resp_search_num = client.get(f"/api/questions?search=#{test_target_num}")
    assert resp_search_num.status_code == 200
    search_res = resp_search_num.json()
    assert any(q.get("q_number") == test_target_num for q in search_res["items"])
    print(f"   => Tìm kiếm trực tiếp theo số câu '#{test_target_num}' thành công!")

    print("\n" + "="*60)
    print(">>> TẤT CẢ 12 BƯỚC KIỂM THỬ ĐÃ VƯỢT QUA XUẤT SẮC 100%! <<<")
    print("="*60)

if __name__ == "__main__":
    test_full_pipeline()
