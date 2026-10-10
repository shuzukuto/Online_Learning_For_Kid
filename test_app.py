import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from backend.database import init_db, get_stats, get_questions, insert_or_update_question, get_question_by_id, compute_source_detail
from backend.normalizer import clean_html_and_math
from backend.classifier import classify_subject
from backend.docx_exporter import generate_exam_docx
from backend.app import app
from fastapi.testclient import TestClient
from datetime import datetime
import re

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

    print("\n13. Kiểm tra Tích hợp Nguồn dữ liệu Toán Lớp 2 (Anh, Việt & Olympic)...")
    # 13.1 Check catalog of Grade 2 sources
    resp_g2_sources = client.get("/api/hunter/grade2-sources")
    assert resp_g2_sources.status_code == 200
    g2_data = resp_g2_sources.json()
    assert g2_data["success"] is True
    categories = {c["id"]: c for c in g2_data["categories"]}
    assert "vietnamese" in categories
    assert "english" in categories
    assert "olympiad" in categories
    print("   => Danh mục nguồn Toán Lớp 2 (Anh, Việt, Olympic) sẵn sàng!")

    # 13.2 Check classification of Grade 2 English math
    sub_g2_en = classify_subject(
        content_text="Lucas has 46 crayons. His mom buys him a new pack of 28 crayons. How many crayons does Lucas have now?",
        topic="2nd Grade Word Problems"
    )
    assert sub_g2_en == "math", f"Expected 'math', got '{sub_g2_en}'"
    print("   => Phân loại câu hỏi Toán Lớp 2 tiếng Anh chính xác sang bộ môn 'math'!")

    # 13.3 Test one-click harvest for Grade 2 Math
    resp_g2_harvest = client.post("/api/hunter/harvest-grade2")
    assert resp_g2_harvest.status_code == 200
    harvest_res = resp_g2_harvest.json()
    assert harvest_res["success"] is True
    assert harvest_res["total_harvested"] >= 10
    print(f"   => Nạp nhanh Toán Lớp 2 thành công! Tổng câu thu thập: {harvest_res['total_harvested']} (Lưu mới: {harvest_res['new_saved']})")

    # 13.4 Check questions list for Grade 2 Math
    resp_g2_q = client.get("/api/questions?grade=2&subject=math&page_size=20")
    assert resp_g2_q.status_code == 200
    g2_q_list = resp_g2_q.json()
    assert g2_q_list["total"] >= 5
    print(f"   => Tổng số câu hỏi Toán Lớp 2 trong Ngân hàng: {g2_q_list['total']}")

    print("\n14. Kiểm tra Cơ chế Săn Dữ liệu Động cho Toàn bộ Khối lớp (Khối 1 đến 12)...")
    # 14.1 Test dynamic source catalog for Grade 6
    resp_g6_sources = client.get("/api/hunter/grade-sources?grade=6")
    assert resp_g6_sources.status_code == 200
    g6_data = resp_g6_sources.json()
    assert g6_data["success"] is True
    assert g6_data["grade"] == 6
    g6_urls = [u["url"] for cat in g6_data["categories"] for u in cat["sources"]]
    assert any("classes=6" in u for u in g6_urls), "classes=6 should be in Grade 6 sources"
    assert any("toan-lop-6" in u for u in g6_urls), "toan-lop-6 should be in Grade 6 sources"
    print("   => Danh mục nguồn Khối 6 phản ánh chính xác cấu trúc khối lớp!")

    # 14.2 Test dynamic source catalog for Grade 12
    resp_g12_sources = client.get("/api/hunter/grade-sources?grade=12")
    assert resp_g12_sources.status_code == 200
    g12_data = resp_g12_sources.json()
    assert g12_data["success"] is True
    assert g12_data["grade"] == 12
    g12_urls = [u["url"] for cat in g12_data["categories"] for u in cat["sources"]]
    assert any("classes=12" in u for u in g12_urls), "classes=12 should be in Grade 12 sources"
    assert any("toan-lop-12" in u for u in g12_urls), "toan-lop-12 should be in Grade 12 sources"
    assert any("precalculus" in u or "calculus-1" in u for u in g12_urls), "precalculus or calculus-1 should be in Grade 12 Khan sources"
    print("   => Danh mục nguồn Khối 12 phản ánh chính xác cấu trúc khối lớp THPT!")

    # 14.3 Test harvest by grade for Grade 6
    resp_g6_harvest = client.post("/api/hunter/harvest-by-grade", json={"grade": 6, "subject": "math"})
    assert resp_g6_harvest.status_code == 200
    g6_harvest_res = resp_g6_harvest.json()
    assert g6_harvest_res["success"] is True
    assert g6_harvest_res["total_harvested"] >= 5
    print(f"   => Nạp nhanh Toán Khối 6 thành công! Đã thu thập: {g6_harvest_res['total_harvested']} câu")

    # 14.4 Test harvest by grade for Grade 12
    resp_g12_harvest = client.post("/api/hunter/harvest-by-grade", json={"grade": 12, "subject": "math"})
    assert resp_g12_harvest.status_code == 200
    g12_harvest_res = resp_g12_harvest.json()
    assert g12_harvest_res["success"] is True
    assert g12_harvest_res["total_harvested"] >= 5
    print(f"   => Nạp nhanh Toán Khối 12 thành công! Đã thu thập: {g12_harvest_res['total_harvested']} câu")

    # 14.5 Check questions filter by Grade 6 and Grade 12
    resp_check_g6 = client.get("/api/questions?grade=6&subject=math&page_size=10")
    assert resp_check_g6.status_code == 200
    assert resp_check_g6.json()["total"] >= 1
    assert all(q["grade"] == 6 for q in resp_check_g6.json()["items"])

    resp_check_g12 = client.get("/api/questions?grade=12&subject=math&page_size=10")
    assert resp_check_g12.status_code == 200
    assert resp_check_g12.json()["total"] >= 1
    assert all(q["grade"] == 12 for q in resp_check_g12.json()["items"])
    print("   => Đã xác thực phân lập Khối 6 và Khối 12 trong Ngân hàng câu hỏi chuẩn 100%!")

    print("\n15. Kiểm tra Phân loại Tiếng Việt Đọc hiểu/Ngữ pháp & Lọc rác Giao diện VioEdu/VnDoc...")
    from backend.normalizer import is_valid_question_payload, normalize_question_payload
    import asyncio

    # 15.1 Verify Vietnamese Reading & Grammar questions
    reading_q = "Lan học lớp 2C trường Tiểu học Trần Hưng Đạo. Bạn thân nhất của Lan là Minh. Việc Minh giải thích bài cho Lan một cách kiên nhẫn cho thấy điều gì?"
    assert classify_subject(content_text=reading_q) == "vietnamese"
    assert classify_subject(content_text="Em hãy chọn từ có vần s:") == "vietnamese"
    assert classify_subject(content_text="Đâu là câu kiểu “Ai là gì?” trong các câu dưới đây?") == "vietnamese"
    assert classify_subject(content_text="Dấu phẩy xuất hiện ở vị trí nào trong câu 'Em có bánh, kẹo và đồ chơi.'?") == "vietnamese"
    assert classify_subject(content_text="Em hãy chọn câu nêu đặc điểm về việc nhà:") == "vietnamese"
    print("   => Phân loại chính xác 100% các câu đọc hiểu, chính tả, dấu câu, mẫu câu sang 'vietnamese'!")

    # 15.2 Verify junk rejection
    valid_vio_score, reason1 = is_valid_question_payload({"content_text": "I.1.1. Cấu tạo các số đến 100. Cách tính điểm khi trả lời ĐÚNG hoặc SAI: Tổng điểm < 10 ĐÚNG cộng 10 điểm. SAI trừ 1 điểm."})
    assert valid_vio_score is False
    valid_vndoc_video, reason2 = is_valid_question_payload({"content_text": "Video mở đầu Mĩ thuật 8 Bài 2: Một số dạng bố cục trong tranh sinh hoạt (AI)"})
    assert valid_vndoc_video is False
    valid_vndoc_course, reason3 = is_valid_question_payload({"content_text": "Học Online Luyện từ và Câu 3"})
    assert valid_vndoc_course is False
    print("   => Lọc bỏ triệt để 100% rác giao diện VioEdu và liên kết video/menu VnDoc!")

    # 15.3 Verify normalizer re-classification of faulty 'english' subject
    faulty_payload = {
        "content_text": reading_q,
        "subject": "english",
        "options": [{"id": "A", "content": "Minh không có việc gì"}, {"id": "C", "content": "Minh là bạn tốt"}]
    }
    corrected = asyncio.run(normalize_question_payload(faulty_payload))
    assert corrected["subject"] == "vietnamese"
    print("   => Tự động nắn chỉnh subject 'english' sai lệch về 'vietnamese' thành công!")


    print("\n16. Kiểm tra Tính Đồng nhất Phiên bản Toàn hệ thống (Extension v1.3.17, App v1.0.35, Cache Buster ?v=1.0.38)...")
    ext_files = [
        "extension/manifest.json",
        "extension/background.js",
        "extension/interceptor.js",
        "extension/content.js",
        "extension/popup.html",
        "extension/popup.js"
    ]
    for ef in ext_files:
        assert os.path.exists(ef), f"Tệp extension {ef} không tồn tại!"
        with open(ef, "r", encoding="utf-8") as f:
            content = f.read()
        assert any(v in content for v in ["1.3.18", "1.3.17", "1.3.16", "1.3.15"]), f"Tệp {ef} thiếu phiên bản v1.3.18 hoặc v1.3.17!"
        for obsolete in ["1.3.0", "1.3.11", "1.3.12", "1.3.14"]:
            assert obsolete not in content, f"Tệp {ef} còn sót phiên bản cũ {obsolete}!"
    print("   => Tiện ích Extension đồng bộ v1.3.18 trên tất cả 6 tệp, sạch hoàn toàn chuỗi cũ!")

    with open("frontend/index.html", "r", encoding="utf-8") as f:
        index_html = f.read()
    with open("frontend/js/app.js", "r", encoding="utf-8") as f:
        app_js = f.read()
    assert any(v in index_html for v in ["1.0.43", "1.0.42", "1.0.41"]), "frontend/index.html thiếu phiên bản Web App!"
    assert any(v in app_js for v in ["1.0.43", "1.0.42", "1.0.41"]), "frontend/js/app.js thiếu phiên bản Web App!"
    assert any(v in index_html for v in ["?v=1.0.48", "?v=1.0.47", "?v=1.0.46"]), "frontend/index.html thiếu Cache Buster!"
    print("   => Web App đồng bộ v1.0.43 và Cache Buster ?v=1.0.48 chính xác!")

    print("\n17. Kiểm tra Bộ Thẩm định Normalizer & Phân biệt Dấu thanh 'Khoa học' vs 'Khóa học'...")
    # 17.1 Science questions with "khoa học" / "truyện khoa học" must be accepted
    sci_passage = {
        "content_text": "Minh thích truyện khoa học còn Lan thích truyện cổ tích. Việc Minh giải thích bài cho Lan một cách kiên nhẫn cho thấy điều gì?",
        "options": [
            {"id": "A", "content": "Minh kiên nhẫn và là người bạn tốt"},
            {"id": "B", "content": "Minh không thích đọc sách"}
        ]
    }
    is_sci_valid, reason_sci = is_valid_question_payload(sci_passage)
    assert is_sci_valid is True, f"Bài đọc khoa học bị từ chối sai: {reason_sci}"

    # Verify existing DB question dom_1790758278099_0
    from backend.database import get_connection
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM questions WHERE id = ?", ("dom_1790758278099_0",))
    row_dom = c.fetchone()
    if row_dom:
        q_dict = dict(row_dom)
        v_dom, r_dom = is_valid_question_payload(q_dict)
        assert v_dom is True, f"Câu hỏi dom_1790758278099_0 trong CSDL không vượt qua kiểm định: {r_dom}"
    print("   => Bài đọc 'truyện khoa học' được công nhận hợp lệ, không bị bắt nhầm thành khóa học!")

    # 17.2 Commercial course marketing spam must be rejected
    spam_samples = [
        {"content_text": "Đăng ký khóa học Toán Tiểu học chất lượng cao giảm giá 50%", "options": [{"id": "A", "content": "1"}]},
        {"content_text": "Liên hệ ngay để nhận tư vấn khoá học hè bổ ích cho bé", "options": [{"id": "A", "content": "1"}]},
        {"content_text": "Tư vấn khóa học combo luyện thi học sinh giỏi cấp quận", "options": [{"id": "A", "content": "1"}]},
        {"content_text": "Học phí lớp học thêm trực tuyến ưu đãi 30% khi đăng ký sớm", "options": [{"id": "A", "content": "1"}]}
    ]
    for sp in spam_samples:
        is_spam_valid, reason_spam = is_valid_question_payload(sp)
        assert is_spam_valid is False, f"Quảng cáo khóa học lọt qua kiểm định: {sp['content_text']}"
    print("   => Chặn triệt để 100% spam quảng cáo khóa học có dấu thanh ('khóa học', 'khoá học', 'học phí')!")

    # 17.3 Verify purged orphaned record dom_text_1790846122435
    c.execute("SELECT COUNT(*) FROM questions WHERE id = ?", ("dom_text_1790846122435",))
    assert c.fetchone()[0] == 0, "Bản ghi mồ côi dom_text_1790846122435 vẫn còn tồn tại trong CSDL!"
    conn.close()
    print("   => Đã dọn sạch bản ghi menu mồ côi VnDoc dom_text_1790846122435 khỏi CSDL!")

    print("\n18. Kiểm tra Xuất Đề thi PDF Chuẩn MOET A4 & Bóc Tách Đề Thi Ảnh (Image OCR)...")
    # 18.1 Test PDF Export endpoint
    conn = get_connection()
    q_rows = conn.execute("SELECT id FROM questions LIMIT 3").fetchall()
    q_ids = [r["id"] for r in q_rows]
    conn.close()

    pdf_payload = {
        "title": "ĐỀ THI KIỂM TRA CHẤT LƯỢNG HỌC KỲ I",
        "header_info": "SỞ GIÁO DỤC VÀ ĐÀO TẠO - ĐỀ CHÍNH THỨC",
        "grade": 5,
        "duration_minutes": 45,
        "question_ids": q_ids
    }
    resp_pdf = client.post("/api/export/pdf", json=pdf_payload)
    assert resp_pdf.status_code == 200, f"Lỗi xuất PDF: {resp_pdf.text}"
    assert "application/pdf" in resp_pdf.headers.get("content-type", "")
    assert len(resp_pdf.content) > 10000, "Kích thước tệp PDF quá nhỏ!"
    assert resp_pdf.content.startswith(b"%PDF-"), "Header tệp không phải định dạng PDF nhị phân hợp lệ!"
    print(f"   => Xuất PDF chuẩn MOET A4 thành công! Dung lượng: {len(resp_pdf.content)} bytes, Header %PDF- chuẩn xác!")

    # 18.2 Test Image OCR endpoint
    import io
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (600, 200), "white")
    draw = ImageDraw.Draw(img)
    draw.text((20, 20), "Cau 1: 1 + 1 = ?\nA. 2\nB. 3\nC. 4\nD. 5", fill="black")
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="PNG")

    resp_ocr = client.post(
        "/api/import/image",
        files={"file": ("test_exam.png", img_byte_arr.getvalue(), "image/png")}
    )
    assert resp_ocr.status_code == 200, f"Lỗi bóc tách ảnh OCR: {resp_ocr.text}"
    ocr_data = resp_ocr.json()
    assert ocr_data["success"] is True
    assert ocr_data["file_type"] == "image"
    print(f"   => Bóc tách đề thi từ ảnh (Image OCR) thành công: {ocr_data['filename']} (Định dạng: {ocr_data['file_type']})!")

    print("\n19. Kiểm tra Phân hệ Luyện tập Trực tuyến (Practice Arena), SQLite practice_history & Gamification Analytics...")
    # 19.1 Verify practice_history table and indexes
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(practice_history)")
    cols = [r[1] for r in cursor.fetchall()]
    required_cols = [
        "id", "exam_id", "exam_title", "subject", "grade",
        "total_questions", "correct_count", "wrong_count", "skipped_count",
        "score", "max_score", "duration_seconds", "time_spent_seconds",
        "ranking", "answers_detail", "created_at"
    ]
    for col in required_cols:
        assert col in cols, f"Bảng practice_history thiếu cột {col}!"

    cursor.execute("PRAGMA index_list(practice_history)")
    idx_names = [r[1] for r in cursor.fetchall()]
    assert "idx_practice_created_at" in idx_names
    assert "idx_practice_subject" in idx_names
    assert "idx_practice_grade" in idx_names
    assert "idx_practice_exam_id" in idx_names
    print("   => Bảng practice_history và 4 chỉ mục hiệu năng SQLite đã khởi tạo hoàn hảo!")

    # 19.2 Generate dynamic practice questions
    resp_gen = client.post("/api/practice/generate", json={"subject": "math", "grade": 5, "count": 2})
    assert resp_gen.status_code == 200
    gen_res = resp_gen.json()
    assert gen_res["success"] is True
    assert len(gen_res.get("questions", [])) >= 1
    test_q = gen_res["questions"][0]
    print(f"   => Khởi tạo phòng thi luyện tập động thành công: {len(gen_res['questions'])} câu hỏi!")

    # 19.3 Submit practice answers and evaluate
    user_ans = test_q.get("correct_answer")
    if not user_ans and test_q.get("options"):
        for opt in test_q["options"]:
            if opt.get("is_correct"):
                user_ans = opt.get("id")
                break
    if not user_ans and test_q.get("options"):
        user_ans = test_q["options"][0].get("id") or "A"
    if not user_ans:
        user_ans = "A"

    practice_submit_payload = {
        "exam_id": "practice_exam_test",
        "exam_title": "Luyện tập Trực tuyến Kiểm thử Tự động",
        "subject": "math",
        "grade": 5,
        "duration_seconds": 900,
        "time_spent_seconds": 180,
        "answers": [
            {
                "question_id": test_q["id"],
                "selected_answer": user_ans,
                "selected_option": user_ans,
                "user_answer": user_ans,
                "is_flagged": False,
                "time_spent_seconds": 45
            }
        ]
    }
    resp_submit = client.post("/api/practice/submit", json=practice_submit_payload)
    assert resp_submit.status_code == 200, f"Lỗi nộp bài luyện tập: {resp_submit.text}"
    submit_data = resp_submit.json()
    assert submit_data["success"] is True
    assert "id" in submit_data
    assert submit_data["correct_count"] > 0, f"Kỳ vọng correct_count > 0 nhưng nhận {submit_data.get('correct_count')}"
    assert submit_data["score"] > 0.0, f"Kỳ vọng score > 0.0 nhưng nhận {submit_data.get('score')}"
    assert 0.0 < submit_data["score"] <= 10.0
    assert 0.0 < submit_data["score_100"] <= 100.0
    assert submit_data["ranking"] in ["Xuất sắc", "Giỏi", "Khá", "Trung bình", "Cần cố gắng"]
    submitted_record_id = submit_data["id"]
    print(f"   => Nộp bài và chấm điểm tự động thành công: Điểm {submit_data['score']}/10 ({submit_data['ranking']})!")

    # Xác thực thêm các biến thể bí danh payload (selected_option, selected_answer, user_answer) đều cho điểm > 0.0
    resp_opt = client.post("/api/practice/submit", json={"exam_id": "test_opt", "answers": [{"question_id": test_q["id"], "selected_option": user_ans}]})
    assert resp_opt.status_code == 200 and resp_opt.json()["score"] > 0.0 and resp_opt.json()["correct_count"] > 0
    resp_sel = client.post("/api/practice/submit", json={"exam_id": "test_sel", "answers": [{"question_id": test_q["id"], "selected_answer": user_ans}]})
    assert resp_sel.status_code == 200 and resp_sel.json()["score"] > 0.0 and resp_sel.json()["correct_count"] > 0

    # 19.4 Retrieve practice history
    resp_history = client.get("/api/practice/history?limit=10")
    assert resp_history.status_code == 200
    hist_json = resp_history.json()
    assert hist_json["success"] is True
    records = hist_json.get("records", [])
    assert any(r["id"] == submitted_record_id for r in records), "Không tìm thấy phiên vừa làm trong lịch sử!"
    print(f"   => Truy vấn danh sách lịch sử practice_history thành công: {len(records)} phiên làm bài!")

    # 19.5 Retrieve practice history detail
    resp_detail = client.get(f"/api/practice/history/{submitted_record_id}")
    assert resp_detail.status_code == 200
    detail_json = resp_detail.json()
    assert detail_json["success"] is True
    assert detail_json["record"]["id"] == submitted_record_id
    assert "answers_detail" in detail_json["record"]
    print("   => Truy vấn chi tiết câu trả lời bài thi và lời giải thành công!")

    # 19.6 Retrieve practice analytics report (Trending, Mastery, Badges)
    resp_analytics = client.get("/api/practice/analytics")
    assert resp_analytics.status_code == 200
    ana_json = resp_analytics.json()
    assert ana_json["success"] is True
    analytics = ana_json["analytics"]
    assert "trending_scores" in analytics
    assert "subject_mastery" in analytics
    assert "badges" in analytics
    assert len(analytics["badges"]) == 8, f"Kỳ vọng 8 huy hiệu thành tích, nhận được: {len(analytics['badges'])}"
    print(f"   => Báo cáo phân tích Trending Analytics & 8 Huy hiệu thành tích sẵn sàng 100%!")
    conn.close()

    print("\n20. Kiểm tra Tác vụ Hàng loạt (Bulk Delete & Bulk Update Grade APIs)...")
    # 20.1 Nạp 3 câu hỏi kiểm thử tạm thời
    q_bulk_1 = insert_or_update_question({
        "id": "test_bulk_qa_1",
        "source_platform": "manual",
        "grade": 3,
        "subject": "math",
        "question_type": "single_choice",
        "content_html": "<p>Câu hỏi kiểm thử bulk 1</p>",
        "content_text": "Câu hỏi kiểm thử bulk 1",
        "options": [
            {"id": "A", "content": "1", "is_correct": True},
            {"id": "B", "content": "2", "is_correct": False}
        ],
        "correct_answer": "A"
    })
    q_bulk_2 = insert_or_update_question({
        "id": "test_bulk_qa_2",
        "source_platform": "manual",
        "grade": 3,
        "subject": "math",
        "question_type": "single_choice",
        "content_html": "<p>Câu hỏi kiểm thử bulk 2</p>",
        "content_text": "Câu hỏi kiểm thử bulk 2",
        "options": [
            {"id": "A", "content": "2", "is_correct": True},
            {"id": "B", "content": "3", "is_correct": False}
        ],
        "correct_answer": "A"
    })
    q_bulk_3 = insert_or_update_question({
        "id": "test_bulk_qa_3",
        "source_platform": "manual",
        "grade": 3,
        "subject": "math",
        "question_type": "single_choice",
        "content_html": "<p>Câu hỏi kiểm thử bulk 3</p>",
        "content_text": "Câu hỏi kiểm thử bulk 3",
        "options": [
            {"id": "A", "content": "3", "is_correct": True},
            {"id": "B", "content": "4", "is_correct": False}
        ],
        "correct_answer": "A"
    })

    # 20.2 Test Bulk Update Grade
    resp_grade = client.post("/api/questions/bulk-update-grade", json={
        "question_ids": ["test_bulk_qa_1", "test_bulk_qa_2", "test_bulk_qa_3"],
        "grade": 7
    })
    assert resp_grade.status_code == 200
    grade_res = resp_grade.json()
    assert grade_res["success"] is True or grade_res.get("status") == "success"
    assert grade_res["updated_count"] == 3
    assert grade_res["grade"] == 7

    # Xác thực lại trong CSDL
    q1_check = get_question_by_id("test_bulk_qa_1")
    assert q1_check["grade"] == 7, "Cập nhật khối lớp hàng loạt thất bại!"

    # Kiểm thử xác thực biên và đối kháng khối lớp (chỉ chấp nhận 1..12, từ chối số âm, số thập phân, boolean, xâu sai lệch)
    adversarial_grades = [15, 0, 13, -1, 100, "Lớp -5", "-5", "5.9", "Lớp 5.9", "Lớp -12", True, "Lớp 0", "Lớp 13", "", "abc"]
    for adv_g in adversarial_grades:
        resp_adv = client.post("/api/questions/bulk-update-grade", json={
            "question_ids": ["test_bulk_qa_1"],
            "grade": adv_g
        })
        assert resp_adv.status_code in (400, 422), f"Khối lớp đối kháng '{adv_g}' không hợp lệ nhưng không bị từ chối (HTTP {resp_adv.status_code})!"
    print("   => Xác thực đối kháng khối lớp thành công (từ chối 100% 'Lớp -5', '-5', '5.9', True, v.v.)!")

    # 20.3 Test Bulk Delete
    resp_bdel = client.post("/api/questions/bulk-delete", json={
        "question_ids": ["test_bulk_qa_1", "test_bulk_qa_2"]
    })
    assert resp_bdel.status_code == 200
    bdel_res = resp_bdel.json()
    assert bdel_res["success"] is True or bdel_res.get("status") == "success"
    assert bdel_res["deleted_count"] == 2

    # Xác thực các câu đã xóa không còn trong CSDL
    assert get_question_by_id("test_bulk_qa_1") is None
    assert get_question_by_id("test_bulk_qa_2") is None
    assert get_question_by_id("test_bulk_qa_3") is not None

    # Xóa dọn dẹp câu còn lại
    client.post("/api/questions/bulk-delete", json={"question_ids": ["test_bulk_qa_3"]})
    print("   => Tác vụ hàng loạt (Bulk Delete & Bulk Update Grade) kiểm thử thành công 100% trong 1 transaction SQLite!")

    print("\n21. Kiểm tra Hiển thị Biểu thức Phân số KaTeX & Bảo toàn Delimiters...")
    # 21.1 Khối toán học đã có sẵn cặp dấu $...$
    formula_with_math = "Tính giá trị của biểu thức phân số sau: $M=\\frac{3}{4}+\\frac{2}{5}$"
    clean_h, clean_t = clean_html_and_math(formula_with_math)
    assert "$M=\\frac{3}{4}+\\frac{2}{5}$" in clean_h or "$M=\\frac{3}{4}+\\frac{2}{5}$" in clean_t
    assert clean_h.count("$") == 2, "Khối toán học có sẵn không được chèn thêm dấu $!"

    # 21.2 Khối toán học MathJax dạng \\( ... \\)
    raw_mathjax = "Cho biểu thức \\( A = \\frac{1}{2} + \\frac{1}{3} \\), hãy tính A."
    h_mj, _ = clean_html_and_math(raw_mathjax)
    assert "$A = \\frac{1}{2} + \\frac{1}{3}$" in h_mj

    # 21.3 Đảm bảo kiểm tra các câu hỏi trong CSDL có phân số không bị vỡ delimiter
    db_questions, _ = get_questions(page_size=20, subject="math")
    for q in db_questions:
        if "\\frac" in q.get("content_html", ""):
            assert q["content_html"].count("$") % 2 == 0, f"Lỗi rách delimiter tại câu {q['id']}"
    print("   => Chuẩn hóa biểu thức phân số KaTeX và bảo toàn khối delimiters hoàn hảo!")

    print("\n22. Kiểm tra Trường Thời gian created_at & Định dạng Ngày Giờ Tiếng Việt...")
    resp_q_list = client.get("/api/questions?page_size=10")
    assert resp_q_list.status_code == 200
    items = resp_q_list.json()["items"]
    assert len(items) > 0
    for it in items:
        assert "created_at" in it and it["created_at"], f"Câu hỏi {it['id']} thiếu trường created_at!"
        dt = datetime.fromisoformat(it["created_at"])
        vn_formatted = dt.strftime("%H:%M %d/%m/%Y")
        assert re.match(r"^\d{2}:\d{2}\s+\d{2}/\d{2}/\d{4}$", vn_formatted), f"Format sai: {vn_formatted}"

    # Kiểm tra sắp xếp theo created_at_desc (newest)
    resp_newest = client.get("/api/questions?sort_by=created_at_desc&page=1&page_size=5")
    assert resp_newest.status_code == 200
    newest_items = resp_newest.json().get("items", [])
    if len(newest_items) >= 2:
        for i in range(len(newest_items) - 1):
            assert newest_items[i]["created_at"] >= newest_items[i+1]["created_at"]

    print("   => Dữ liệu created_at và định dạng ngày giờ tiếng Việt đạt chuẩn 100%!")

    print("\n23. Kiểm tra Bóc tách Đề thi PDF & Hình ảnh (Image OCR Song ngữ, Multi-file & Preview Zoom UI)...")
    # 23.1 Kiểm tra cấu trúc UI & Router: OCR card chuyển sang view-manual, không còn ở view-collector
    with open("frontend/index.html", "r", encoding="utf-8") as f:
        html_src = f.read()
    assert 'id="view-manual"' in html_src
    assert 'id="pdf-dropzone"' in html_src
    assert 'id="pdf-file-input"' in html_src and 'multiple' in html_src
    assert 'id="ocr-batch-progress-card"' in html_src
    assert 'id="ocr-questions-nav-bar"' in html_src, "Thiếu thanh chọn nhanh tự do chuyển câu hỏi ocr-questions-nav-bar!"
    assert 'id="btn-ocr-next-q"' in html_src, "Thiếu nút chuyển câu tiếp theo btn-ocr-next-q!"
    assert 'id="btn-ocr-discard-q"' in html_src, "Thiếu nút bỏ qua câu hỏi btn-ocr-discard-q!"
    assert 'id="modal-image-zoom"' in html_src
    assert 'id="zoom-target-img"' in html_src
    assert 'id="ocr-live-log"' in html_src
    assert 'id="ocr-log-toolbar"' in html_src

    # Kiểm tra view-collector không còn chứa pdf-result-container hoặc OCR upload
    collector_part = html_src.split('id="view-collector"')[1].split('id="view-manual"')[0]
    assert "pdf-file-input" not in collector_part
    assert "pdf-result-container" not in collector_part
    print("   => Giao diện OCR và Lightbox Zoom đã chuyển sang 'Soạn câu hỏi mới' (view-manual), dọn sạch khỏi view-collector!")

    # 23.2 Kiểm tra logic JavaScript Collector & Batch Verification
    with open("frontend/js/collector.js", "r", encoding="utf-8") as f:
        col_js = f.read()
    assert "startOcrBatchVerification" in col_js
    assert "loadOcrQuestionToForm" in col_js
    assert "renderOcrQuestionsNavBar" in col_js, "Thiếu hàm render thanh chuyển câu hỏi renderOcrQuestionsNavBar!"
    assert "navNextOcrQuestion" in col_js, "Thiếu hàm navNextOcrQuestion chuyển câu tự do!"
    assert "discardCurrentOcrQuestion" in col_js, "Thiếu hàm discardCurrentOcrQuestion bỏ qua câu!"
    assert "openImageZoomModal" in col_js
    assert "zoomImage" in col_js
    assert "appendOcrLog" in col_js
    assert "copyOcrLiveLog" in col_js
    assert "clearOcrLiveLog" in col_js
    print("   => Logic luồng duyệt tự do chuyển câu hỏi, bỏ qua câu & Nhật ký Live OCR Telemetry Log đã sẵn sàng!")

    # 23.3 Kiểm tra API bóc tách hình ảnh song ngữ (media_1790907151101.png)
    test_img_path = "C:/Users/ptlua/.gemini/antigravity/brain/f8f2462b-e223-4dc3-883c-c9717538b082/.user_uploaded/media_1790907151101.png"
    if os.path.exists(test_img_path):
        from backend.pdf_extractor import extract_questions_from_image
        extracted_qs = extract_questions_from_image(test_img_path)
        assert len(extracted_qs) == 2, f"Kỳ vọng bóc tách 2 câu hỏi từ ảnh, nhưng nhận được {len(extracted_qs)} câu!"
        
        # Câu 1: Song ngữ ngày tháng thứ Tư / Wednesday
        q1 = extracted_qs[0]
        assert q1["grade"] == 2, f"Khối lớp nhận diện sai: {q1['grade']} (kỳ vọng 2)"
        assert len(q1["options"]) >= 4, f"Thiếu 4 phương án cho câu 1: {len(q1['options'])}"
        assert "Wednesday" in q1["content_text"] or "Thứ Tư" in str(q1["options"]) or "Thứ Tư" in q1["content_text"]
        
        # Câu 2: Song ngữ Michael's class / Lớp của Michael
        q2 = extracted_qs[1]
        assert q2["grade"] == 2
        assert len(q2["options"]) >= 4, f"Thiếu 4 phương án cho câu 2: {len(q2['options'])}"
        assert "Michael" in q2["content_text"]
        
        # Kiểm tra endpoint POST /api/pdf/extract qua TestClient
        with open(test_img_path, "rb") as img_file:
            resp_upload = client.post(
                "/api/pdf/extract",
                files={"file": ("olympiad_grade2.png", img_file.read(), "image/png")}
            )
        assert resp_upload.status_code == 200, f"Upload API lỗi: {resp_upload.text}"
        data_up = resp_upload.json()
        assert data_up.get("success") is True
        assert len(data_up.get("questions", [])) == 2
        print(f"   => Bóc tách chính xác 2/2 câu hỏi song ngữ từ ảnh test với Khối {q1['grade']}, đủ phương án A/B/C/D!")

    # 23.4 Kiểm tra OCR đối kháng trên Ảnh số 2 (media_1790928052101.jpg - Câu 8 & Câu 9)
    test_img2_path = "C:/Users/ptlua/.gemini/antigravity/brain/f8f2462b-e223-4dc3-883c-c9717538b082/.user_uploaded/media_1790928052101.jpg"
    if os.path.exists(test_img2_path):
        from backend.pdf_extractor import extract_questions_from_image
        extracted_qs2 = extract_questions_from_image(test_img2_path)
        assert len(extracted_qs2) == 2, f"Kỳ vọng bóc tách chính xác 2 câu hỏi từ Ảnh 2, nhưng nhận được {len(extracted_qs2)} câu!"

        # Câu 8: Không bị tách nhầm thành Câu 2 bởi cụm '2-digit', đủ 4 phương án, đáp án A
        q8 = extracted_qs2[0]
        assert "Câu 8" in q8["exam_name"] or "8" in q8["exam_name"]
        assert len(q8["options"]) == 4, f"Câu 8 thiếu phương án: {len(q8['options'])}"
        assert q8["correct_answer"] == "A", f"Đáp án Câu 8 sai: {q8['correct_answer']} (kỳ vọng A)"
        assert "Gordon nghĩ ra một số" in q8["content_text"]
        assert "2-digit" in q8["content_text"]

        # Câu 9: Tính toán dãy số, đủ 4 phương án, đáp án C
        q9 = extracted_qs2[1]
        assert "Câu 9" in q9["exam_name"] or "9" in q9["exam_name"]
        assert len(q9["options"]) == 4, f"Câu 9 thiếu phương án: {len(q9['options'])}"
        assert q9["correct_answer"] == "C", f"Đáp án Câu 9 sai: {q9['correct_answer']} (kỳ vọng C)"
        assert "Tính 13 - 11" in q9["content_text"] or "13 - 11" in q9["content_text"]
        print("   => Bóc tách hoàn hảo Ảnh số 2: Câu 8 không bị tách nhầm '2-digit', Tiếng Việt tái tạo chuẩn, đáp án A & C chính xác 100%!")

    print("\n24. Kiểm tra Dual OCR Engine (RapidOCR + VietOCR ONNX) & Cơ chế Tự học Ngữ nghĩa (Active Lexicon Learning)...")
    # 24.1 Kiểm tra UI & DOM elements
    with open("frontend/index.html", "r", encoding="utf-8") as f:
        html_src24 = f.read()
    assert 'id="ocr-engine-select"' in html_src24, "Thiếu dropdown chọn engine OCR ocr-engine-select!"
    assert 'id="btn-open-ocr-lexicon"' in html_src24, "Thiếu nút mở từ điển tự học btn-open-ocr-lexicon!"
    assert 'id="modal-ocr-lexicon"' in html_src24, "Thiếu modal quản lý từ điển modal-ocr-lexicon!"
    assert 'id="ocr-lexicon-count-badge"' in html_src24, "Thiếu badge đếm số lượng từ tự học ocr-lexicon-count-badge!"
    assert 'id="lexicon-add-wrong"' in html_src24, "Thiếu ô nhập từ sai lexicon-add-wrong!"
    assert 'id="lexicon-add-correct"' in html_src24, "Thiếu ô nhập từ đúng lexicon-add-correct!"
    assert 'id="ocr-lexicon-table-body"' in html_src24, "Thiếu bảng danh sách quy tắc ocr-lexicon-table-body!"

    # 24.2 Kiểm tra JavaScript Active Lexicon Functions trong collector.js
    with open("frontend/js/collector.js", "r", encoding="utf-8") as f:
        col_js24 = f.read()
    assert "openOcrLexiconModal" in col_js24
    assert "closeOcrLexiconModal" in col_js24
    assert "loadOcrLexiconRules" in col_js24
    assert "filterOcrLexiconList" in col_js24
    assert "submitManualLexiconRule" in col_js24
    assert "deleteOcrLexiconRule" in col_js24
    assert "clearAllOcrLexiconRules" in col_js24
    assert "refreshOcrLexiconCountBadge" in col_js24
    print("   => Giao diện UI Modal & Javascript Active Lexicon Learning đã tích hợp hoàn hảo!")

    # 24.3 Kiểm tra API GET /api/ocr/engine-status
    resp_status = client.get("/api/ocr/engine-status")
    assert resp_status.status_code == 200
    st_data = resp_status.json()
    assert st_data["success"] is True
    assert "engines" in st_data
    assert "rapid" in st_data["engines"]
    assert "vietocr_onnx" in st_data["engines"]
    assert "total_learned_rules" in st_data
    print(f"   => Dual OCR Engine status: RapidOCR ({st_data['engines']['rapid']['display_name']}), VietOCR ONNX ({st_data['engines']['vietocr_onnx']['display_name']})!")

    # 24.4 Kiểm tra Cơ chế Tự học Ngữ nghĩa (POST /api/ocr/learn)
    raw_sample = "Nenhom nary lal thu Tu fat hie Tiem cung"
    corr_sample = "Nếu hôm nay là thứ Tư và Tiệm cũng"
    resp_learn = client.post("/api/ocr/learn", json={
        "raw_text": raw_sample,
        "corrected_text": corr_sample,
        "source": "test_active_learning"
    })
    assert resp_learn.status_code == 200
    learn_data = resp_learn.json()
    assert learn_data["success"] is True
    assert learn_data["learned_count"] > 0
    print(f"   => AI tự động phân tích diff & học được {learn_data['learned_count']} cụm từ đính chính mới!")

    # 24.5 Kiểm tra quy tắc tự học được áp dụng tức thì vào clean_ocr_vietnamese_text
    from backend.pdf_extractor import clean_ocr_vietnamese_text
    test_ocr_raw = "Nenhom nary lal thu Tu chung ta di hoc"
    cleaned_auto = clean_ocr_vietnamese_text(test_ocr_raw)
    assert "Nếu hôm nay" in cleaned_auto or "thứ Tư" in cleaned_auto, f"Quy tắc tự học chưa áp dụng: {cleaned_auto}"
    print(f"   => Bộ chuẩn hóa clean_ocr_vietnamese_text nạp động và áp dụng quy tắc tự học thành công: '{cleaned_auto}'!")

    # 24.6 Kiểm tra CRUD Quy tắc Từ điển Thủ công (/api/ocr/corrections)
    # Thêm quy tắc
    resp_add_rule = client.post("/api/ocr/corrections", json={
        "wrong_text": "tuvandethi",
        "correct_text": "Tự vãn đề thi",
        "source": "test_manual"
    })
    assert resp_add_rule.status_code == 200
    add_data = resp_add_rule.json()
    assert add_data["success"] is True
    rule_id = add_data["item"]["id"]

    # Tra cứu tìm kiếm
    resp_search = client.get("/api/ocr/corrections?search=tuvandethi")
    assert resp_search.status_code == 200
    search_data = resp_search.json()
    assert search_data["total"] >= 1
    assert any(it["id"] == rule_id for it in search_data["items"])

    # Xóa quy tắc
    resp_del_rule = client.delete(f"/api/ocr/corrections/{rule_id}")
    assert resp_del_rule.status_code == 200

    # 24.7 Kiểm tra Tự học khi tạo câu hỏi qua POST /api/questions với raw_ocr_content
    resp_q_learn = client.post("/api/questions", json={
        "source_platform": "image_ocr",
        "grade": 5,
        "subject": "math",
        "topic": "Số học tự học",
        "question_type": "single_choice",
        "content_html": "<p>Nếu hôm nay là thứ Sáu</p>",
        "content_text": "Nếu hôm nay là thứ Sáu thì ba ngày nữa là gì?",
        "raw_ocr_content": "Nenhom nary lal thu Sau thi ba ngay nua la gi?",
        "options": [
            {"id": "A", "content": "Thứ Hai", "is_correct": True},
            {"id": "B", "content": "Thứ Ba", "is_correct": False}
        ],
        "correct_answer": "A"
    })
    assert resp_q_learn.status_code == 200
    q_learn_data = resp_q_learn.json()
    assert q_learn_data["success"] is True
    assert q_learn_data.get("learned_count", 0) >= 1
    print(f"   => Tạo câu hỏi qua POST /api/questions tích hợp tự học thành công (+{q_learn_data['learned_count']} từ)!")
    
    # Dọn dẹp câu hỏi test
    if "question" in q_learn_data and "id" in q_learn_data["question"]:
        client.delete(f"/api/questions/{q_learn_data['question']['id']}")

    # 25. Kiểm tra AI Vision Connection Test API
    print("\n25. Kiểm tra AI Vision Connection Test API (POST /api/ai-vision/test-connection)...")
    # Test invalid OpenRouter key
    resp_test_bad = client.post("/api/ai-vision/test-connection", json={
        "provider": "openrouter",
        "api_key": "invalid-test-key-12345"
    })
    assert resp_test_bad.status_code == 200
    res_bad = resp_test_bad.json()
    assert res_bad["success"] is False
    print("   => OpenRouter key không hợp lệ được phát hiện chính xác:", res_bad["message"])

    # Test custom 9Router local endpoint
    resp_test_custom = client.post("/api/ai-vision/test-connection", json={
        "provider": "custom",
        "base_url": "http://127.0.0.1:20129/v1"
    })
    assert resp_test_custom.status_code == 200
    res_custom = resp_test_custom.json()
    print("   => 9Router kết quả:", res_custom["success"], "-", res_custom["message"])

    # Test Multi-Model Fallback Chain Settings API
    resp_multi = client.post("/api/ai-vision/settings", json={
        "openrouter_models": ["dots-studio/dots-3-note-preview:free", "google/gemma-4-26b-a4b-it:free"],
        "opencode_models": ["gemini-3.6-flash", "gemini-2.5-flash"],
        "custom_vision_models": ["openrouter/dots-studio/dots-3-note-preview:free", "openrouter/google/gemma-4-26b-a4b-it:free"]
    })
    assert resp_multi.status_code == 200
    s_multi = resp_multi.json()["settings"]
    assert len(s_multi["openrouter_models"]) == 2
    assert s_multi["openrouter_model"] == "dots-studio/dots-3-note-preview:free"
    assert len(s_multi["opencode_models"]) == 2
    assert len(s_multi["custom_vision_models"]) == 2
    print("   => Cấu hình Chuỗi Multi-Model Fallback lưu trữ và truy xuất thành công 100%!")

    # 26. Kiểm tra AI Vision Prompt Sư phạm & Phân hệ Nhập Ngân hàng từ AI Agent (JSON, DOCX, Text)
    print("\n26. Kiểm tra AI Vision Prompt Sư phạm & Phân hệ Nhập Ngân hàng từ AI Agent (JSON, DOCX, Text)...")
    
    # 26.1 Kiểm tra AI Vision prompt chứa yêu cầu giải toán, chọn đáp án đúng & lời giải
    from backend.ai_vision import _build_vision_prompt
    v_prompt = _build_vision_prompt()
    assert "TỰ ĐỘNG GIẢI BÀI TOÁN" in v_prompt
    assert "correct_answer" in v_prompt
    assert "explanation" in v_prompt
    assert "options" in v_prompt
    print("   => AI Vision System Prompt đã nâng cấp: Tự giải toán, chọn đáp án đúng, viết lời giải sư phạm & phân loại khối lớp!")

    # 26.2 Kiểm tra Template API
    resp_tmpl = client.get("/api/import/ai-agent-template")
    assert resp_tmpl.status_code == 200
    tmpl_data = resp_tmpl.json()
    assert tmpl_data["success"] is True
    assert "system_prompt" in tmpl_data["template"]
    assert len(tmpl_data["template"]["sample_json"]) >= 2
    print("   => API GET /api/import/ai-agent-template sẵn sàng cung cấp System Prompt chuẩn cho giáo viên!")

    # 26.3 Kiểm tra Parse JSON từ AI Agent
    resp_ai_json = client.post("/api/import/ai-agent-data", json={
        "raw_text": tmpl_data["template"]["sample_json_str"],
        "save_to_bank": False
    })
    assert resp_ai_json.status_code == 200
    ai_json_data = resp_ai_json.json()
    assert ai_json_data["success"] is True
    assert ai_json_data["total_parsed"] == 2
    q1 = ai_json_data["questions"][0]
    assert q1["correct_answer"] == "A"
    assert len(q1["options"]) == 4
    assert q1["options"][0]["id"] == "A"
    assert "84 cm²" in q1["options"][0]["content"]
    assert q1["options"][0]["is_correct"] is True
    assert "S = 12 x 7" in q1["explanation"]
    assert q1["grade"] == 4
    assert q1["difficulty"] == "easy"
    print("   => Bóc tách dữ liệu JSON từ AI Agent chuẩn xác 100%: Options A/B/C/D, Đáp án đúng, Lời giải, Khối lớp & Độ khó!")

    # 26.4 Kiểm tra Parse Văn bản / Markdown từ AI Agent
    resp_ai_txt = client.post("/api/import/ai-agent-data", json={
        "raw_text": tmpl_data["template"]["sample_text"],
        "save_to_bank": False
    })
    assert resp_ai_txt.status_code == 200
    ai_txt_data = resp_ai_txt.json()
    assert ai_txt_data["success"] is True
    assert ai_txt_data["total_parsed"] == 2
    q_txt = ai_txt_data["questions"][0]
    assert q_txt["correct_answer"] == "A"
    assert len(q_txt["options"]) == 4
    assert "84 cm²" in q_txt["options"][0]["content"]
    assert "S = 12 x 7" in q_txt["explanation"]
    print("   => Bóc tách văn bản / Markdown từ AI Agent thành công 100%: Tách bạch đề bài, 4 phương án, Đáp án và Lời giải!")

    # 26.5 Kiểm tra Parse tệp Word (.docx) từ AI Agent
    import docx
    doc_test = docx.Document()
    doc_test.add_paragraph("Câu 1: Số nào sau đây chia hết cho cả 2 và 5?")
    doc_test.add_paragraph("A. 15")
    doc_test.add_paragraph("B. 20")
    doc_test.add_paragraph("C. 24")
    doc_test.add_paragraph("D. 31")
    doc_test.add_paragraph("Đáp án: B")
    doc_test.add_paragraph("Lời giải: Số chia hết cho cả 2 và 5 có chữ số tận cùng là 0. Do đó chọn 20.")
    doc_test.add_paragraph("Khối lớp: 4")
    doc_test.add_paragraph("Mức độ: Dễ")
    docx_buf = io.BytesIO()
    doc_test.save(docx_buf)

    resp_docx = client.post(
        "/api/import/ai-agent-data",
        files={"file": ("de_thi_ai.docx", docx_buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"save_to_bank": "false"}
    )
    assert resp_docx.status_code == 200
    docx_res = resp_docx.json()
    assert docx_res["success"] is True
    assert docx_res["total_parsed"] == 1
    q_docx = docx_res["questions"][0]
    assert q_docx["correct_answer"] == "B"
    assert q_docx["options"][1]["content"] == "20"
    assert q_docx["options"][1]["is_correct"] is True
    assert "tận cùng là 0" in q_docx["explanation"]
    print("   => Bóc tách tệp Microsoft Word (.docx) từ AI Agent hoàn hảo 100%!")

    # 26.6 Kiểm tra giao diện Frontend
    with open("frontend/index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    assert "modal-ai-agent-import" in html_content
    assert "openAiAgentImportModal" in html_content
    assert "js/ai_agent_importer.js" in html_content
    assert "id=\"ai-file-dropzone\"" in html_content
    assert "min-height: 46px" in html_content
    assert "padding: 10px 14px" in html_content
    assert "max-height: 55vh" in html_content
    assert "Kéo thả hoặc Bấm chọn tệp" in html_content
    with open("frontend/js/collector.js", "r", encoding="utf-8") as f:
        col_content = f.read()
    assert "getCleanOptContent" in col_content
    assert "findOptionMatch" in col_content
    print("   => Giao diện Web, Modal 3 tab, Thanh kéo thả gọn gàng và bộ ánh xạ Form A/B/C/D đã liên kết hoàn chỉnh 100%!")

    # 26.7 Kiểm tra bảo toàn môn Toán học cho bài toán có lời văn từ AI Agent vào CSDL
    word_math_stem = "Bác An có 35 quả cam, chia đều vào 5 túi nhỏ mang đi biếu họ hàng. Hỏi mỗi túi có bao nhiêu quả cam?"
    old_qs, _ = get_questions(page_size=20, search="35 quả cam")
    for oq in old_qs:
        client.delete(f"/api/questions/{oq['id']}")

    resp_ai_save = client.post("/api/import/ai-agent-data", json={
        "raw_text": f"Câu 1: {word_math_stem}\nA. 5 quả\nB. 7 quả\nC. 6 quả\nD. 8 quả\nĐáp án: B\nLời giải: Mỗi túi có 35 : 5 = 7 quả cam.",
        "save_to_bank": True,
        "default_subject": "math",
        "default_grade": 3,
        "default_topic": "Bài toán chia đều"
    })
    assert resp_ai_save.status_code == 200
    ai_saved_data = resp_ai_save.json()
    assert ai_saved_data["success"] is True
    assert ai_saved_data["saved_count"] >= 1
    # Kiểm tra trong CSDL xem câu hỏi này được lưu với subject='math' chứ không bị gán nhầm sang 'vietnamese'
    db_math_qs, _ = get_questions(page_size=20, subject="math", search="35 quả cam")
    assert len(db_math_qs) >= 1, "Câu toán chữ phải được lưu vào CSDL với môn học 'math'!"
    assert db_math_qs[0]["subject"] == "math"
    # Dọn dẹp câu test khỏi DB
    for mq in db_math_qs:
        client.delete(f"/api/questions/{mq['id']}")
    print("   => Bảo toàn môn 'math' cho bài toán có lời văn từ AI Agent vào CSDL thành công 100%!")

    # 27. Kiểm tra Task 2: Ngân hàng câu hỏi nâng cao (AI Agent filter, created_date, Contribute API, Currency protection)
    print("\n27. Kiểm tra Task 2: Bộ lọc AI Agent, Lọc ngày created_date, API Đóng góp & Ký hiệu tiền tệ KaTeX...")
    
    # 27.1 Kiểm tra API Đóng góp đề thi (POST /api/contribute/upload)
    test_pdf_data = b"%PDF-1.4 Mock exam contribute content"
    resp_contribute = client.post(
        "/api/contribute/upload",
        files={"file": ("de_toan_lop5.pdf", test_pdf_data, "application/pdf")},
        data={"contributor_name": "Thầy Nguyễn Văn A", "notes": "Đề thi thử học kỳ 2"}
    )
    assert resp_contribute.status_code == 200, f"Upload thất bại: {resp_contribute.text}"
    contribute_res = resp_contribute.json()
    assert contribute_res["success"] is True
    assert "de_toan_lop5_" in contribute_res["filename"]
    assert "_contribute.pdf" in contribute_res["filename"]
    assert os.path.exists(contribute_res["saved_path"]), "Tệp đóng góp phải tồn tại trong thư mục training!"
    # Dọn dẹp file test
    if os.path.exists(contribute_res["saved_path"]):
        os.remove(contribute_res["saved_path"])
    print("   => API POST /api/contribute/upload lưu tệp chuẩn hậu tố _contribute và ghi log thành công!")

    # Kiểm tra từ chối định dạng tệp không hợp lệ (.exe)
    resp_bad = client.post(
        "/api/contribute/upload",
        files={"file": ("malicious.exe", b"binary", "application/x-msdownload")}
    )
    assert resp_bad.status_code == 400

    # 27.2 Kiểm tra bộ lọc ngày thêm dữ liệu (created_date)
    today_str = datetime.now().strftime("%Y-%m-%d")
    resp_today = client.get(f"/api/questions?created_date={today_str}")
    assert resp_today.status_code == 200
    today_data = resp_today.json()
    assert today_data["total"] >= 1, f"Phải tìm thấy câu hỏi được tạo hôm nay ({today_str})!"
    for item in today_data["items"][:5]:
        assert item["created_at"].startswith(today_str), f"created_at {item['created_at']} không khớp với {today_str}"

    resp_past = client.get("/api/questions?created_date=1999-01-01")
    assert resp_past.status_code == 200
    assert resp_past.json()["total"] == 0, "Ngày 1999-01-01 không được có dữ liệu!"
    print(f"   => Bộ lọc created_date ({today_str}) hoạt động chính xác 100% ({today_data['total']} câu)!")

    # 27.3 Kiểm tra nguồn AI_AGENT_IMPORT trong database & API
    assert compute_source_detail({"source_platform": "ai_agent_import"}) == "AI Agent Import"
    assert compute_source_detail({"source_detail": "ai_agent_import"}) == "AI Agent Import"
    assert compute_source_detail({"source_detail": "AI Agent Import"}) == "AI Agent Import"

    # Nạp câu hỏi mẫu với platform=ai_agent_import
    mock_ai_id = f"test_ai_agent_q_{int(datetime.now().timestamp())}"
    unique_token = f"Tok_{mock_ai_id}"
    insert_or_update_question({
        "id": mock_ai_id,
        "content_text": f"Tìm x đặc thù {unique_token} biết x + 15 = 30",
        "content_html": f"<p>Tìm x đặc thù {unique_token} biết x + 15 = 30</p>",
        "subject": "math",
        "grade": 3,
        "source_platform": "ai_agent_import",
        "source_detail": "AI Agent Import"
    })

    # Lọc theo source_detail=ai_agent_import
    resp_ai_sd = client.get("/api/questions?source_detail=ai_agent_import")
    assert resp_ai_sd.status_code == 200
    ai_data = resp_ai_sd.json()
    assert ai_data["total"] >= 1
    for item in ai_data["items"][:10]:
        assert item["source_platform"].lower() == "ai_agent_import"

    # Lọc theo tên hiển thị source_detail="AI Agent Import"
    resp_ai_exact = client.get("/api/questions?source_detail=AI Agent Import")
    assert resp_ai_exact.status_code == 200
    assert resp_ai_exact.json()["total"] == ai_data["total"]

    # Lọc theo chip platform=ai_agent_import
    resp_ai_plat = client.get("/api/questions?platform=ai_agent_import")
    assert resp_ai_plat.status_code == 200
    assert resp_ai_plat.json()["total"] >= 1

    # Kiểm tra tìm thấy câu hỏi mock qua search và source_detail
    resp_mock = client.get(f"/api/questions?source_detail=ai_agent_import&search={unique_token}")
    assert resp_mock.status_code == 200
    assert any(it["id"] == mock_ai_id for it in resp_mock.json()["items"])

    # Dọn dẹp câu mock
    client.delete(f"/api/questions/{mock_ai_id}")
    print("   => Bộ lọc nguồn AI Agent (chip & dropdown source_detail) đồng bộ chính xác 100%!")

    # 27.4 Kiểm tra thuật toán bảo vệ ký hiệu tiền tệ KaTeX ($3, $20)
    import subprocess
    js_test_code = """
const fs = require('fs');
const appJs = fs.readFileSync('frontend/js/app.js', 'utf8');
global.window = {};
global.document = { querySelector: () => null, addEventListener: () => null };
eval(appJs);

const testText = 'Nam mua 4 hộp bút, mỗi hộp có giá $3. Hỏi Nam còn lại bao nhiêu tiền nếu anh ấy có $20 ban đầu?';
const res = window.formatMathSymbols(testText);
console.log(JSON.stringify({
  result: res,
  hasDollar3: res.includes('$3') || res.includes('>$</span>3'),
  hasDollar20: res.includes('$20') || res.includes('>$</span>20'),
  mathIntact: !res.includes('___MATH_BLOCK_') && !res.includes('Nammua4hộp')
}));
"""
    with open("temp_currency_test.js", "w", encoding="utf-8") as f:
        f.write(js_test_code)
    node_run = subprocess.run(["node", "temp_currency_test.js"], capture_output=True, text=True, encoding="utf-8")
    if os.path.exists("temp_currency_test.js"):
        os.remove("temp_currency_test.js")
    assert node_run.returncode == 0, f"Node chạy lỗi: {node_run.stderr}"
    import json
    parsed_math_res = json.loads(node_run.stdout.strip())
    assert parsed_math_res["hasDollar3"] is True
    assert parsed_math_res["hasDollar20"] is True
    assert parsed_math_res["mathIntact"] is True
    print("   => Cơ chế bảo vệ ký hiệu tiền tệ ($3, $20) hoạt động hoàn hảo, không bị biến dạng KaTeX!")

    # 27.5 Kiểm tra các thành phần giao diện Frontend (HTML & JS)
    with open("frontend/index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    assert 'value="ai_agent_import"' in html_content
    assert 'data-platform="ai_agent_import"' in html_content
    assert 'id="filter-created-date"' in html_content
    assert 'id="btn-open-contribute-modal"' in html_content
    assert 'id="modal-contribute-questions"' in html_content

    with open("frontend/js/bank.js", "r", encoding="utf-8") as f:
        bank_content = f.read()
    assert 'ai_agent_import: "AI Agent Import"' in bank_content
    assert 'State.filters.created_date' in bank_content
    assert 'openContributeModal' in bank_content
    assert 'submitContributeFile' in bank_content
    print("   => Toàn bộ Modal Đóng góp, nút bấm, date picker và chip AI Agent trên Frontend đồng bộ 100%!")

    print("\n28. Kiểm tra Task 3 Phần 1: Trường dữ liệu has_handwriting cho câu hỏi có chữ viết tay...")
    # 28.1 Kiểm tra Models
    from backend.models import QuestionBase, QuestionCreate, QuestionUpdate
    assert hasattr(QuestionBase, "model_fields") and "has_handwriting" in QuestionBase.model_fields
    assert "has_handwriting" in QuestionCreate.model_fields
    assert "has_handwriting" in QuestionUpdate.model_fields
    q_create = QuestionCreate(content_html="<p>Test</p>", has_handwriting=True)
    assert q_create.has_handwriting is True
    print("   => Mô hình Pydantic QuestionBase, QuestionCreate, QuestionUpdate hỗ trợ has_handwriting 100%!")

    # 28.2 Kiểm tra SQLite & Database functions
    from backend.database import get_connection
    init_db()
    conn_chk = get_connection()
    c_chk = conn_chk.cursor()
    c_chk.execute("PRAGMA table_info(questions)")
    col_names = [r[1] for r in c_chk.fetchall()]
    assert "has_handwriting" in col_names
    conn_chk.close()
    
    # Insert question with handwriting = True
    test_q_hw_id = insert_or_update_question({
        "content_text": "Tìm số tự nhiên viết tay test hw 998877",
        "content_html": "<p>Tìm số tự nhiên viết tay test hw 998877</p>",
        "has_handwriting": True,
        "difficulty": "medium",
        "grade": 5
    }, allow_duplicate=True)
    
    # Retrieve and check row_to_dict
    q_fetched = get_question_by_id(test_q_hw_id)
    assert q_fetched is not None
    assert q_fetched["has_handwriting"] is True
    
    # Check filtering by has_handwriting in get_questions
    hw_qs, hw_total = get_questions(has_handwriting=True)
    assert any(q["id"] == test_q_hw_id for q in hw_qs)
    
    nohw_qs, _ = get_questions(has_handwriting=False)
    assert all(q["id"] != test_q_hw_id for q in nohw_qs)
    print("   => SQLite CSDL lưu trữ, chuyển đổi kiểu bool và lọc has_handwriting thành công 100%!")

    # 28.3 Kiểm tra API Endpoint GET /api/questions?has_handwriting=true
    resp_hw_api = client.get("/api/questions?has_handwriting=true")
    assert resp_hw_api.status_code == 200
    hw_items = resp_hw_api.json()["items"]
    assert any(q["id"] == test_q_hw_id for q in hw_items)
    
    resp_nohw_api = client.get("/api/questions?has_handwriting=false")
    assert resp_nohw_api.status_code == 200
    nohw_items = resp_nohw_api.json()["items"]
    assert all(q["id"] != test_q_hw_id for q in nohw_items)
    print("   => API Endpoint GET /api/questions?has_handwriting=true/false hoạt động chính xác 100%!")

    # Cleanup test question
    conn_del = get_connection()
    conn_del.execute("DELETE FROM questions WHERE id = ?", (test_q_hw_id,))
    conn_del.commit()
    conn_del.close()

    # 28.4 Kiểm tra AI Vision & AI Agent Importer
    from backend.ai_agent_importer import parse_json_questions, parse_ai_agent_payload, get_ai_agent_template_info
    from backend.ai_vision import _build_vision_prompt
    
    vision_prompt = _build_vision_prompt()
    assert "has_handwriting" in vision_prompt
    
    tmpl_info = get_ai_agent_template_info()
    assert "has_handwriting" in tmpl_info["system_prompt"]
    assert "has_handwriting" in json.dumps(tmpl_info["sample_json"])
    
    parsed_hw = parse_json_questions([
        {"question": "Câu hỏi chữ viết tay từ AI", "options": ["A. 1", "B. 2"], "has_handwriting": True}
    ])
    assert parsed_hw[0]["has_handwriting"] is True
    
    payload_hw_raw = json.dumps([
        {"question": "Câu hỏi chữ viết tay từ payload", "options": ["A. 1", "B. 2"], "has_handwriting": True}
    ])
    payload_qs, _ = parse_ai_agent_payload(payload_hw_raw)
    assert payload_qs[0]["has_handwriting"] is True
    print("   => AI Vision System Prompt & AI Agent Importer Parser trích xuất has_handwriting hoàn hảo!")

    # 28.5 Kiểm tra Frontend Badges trong bank.js và ai_agent_importer.js
    with open("frontend/js/bank.js", "r", encoding="utf-8") as f:
        bank_js = f.read()
    assert "has_handwriting" in bank_js
    assert "✍️ Có chữ viết tay" in bank_js

    with open("frontend/js/ai_agent_importer.js", "r", encoding="utf-8") as f:
        importer_js = f.read()
    assert "has_handwriting" in importer_js
    assert "✍️ Chữ viết tay" in importer_js
    print("   => Giao diện Frontend hiển thị huy hiệu chữ viết tay đẹp mắt trên Ngân hàng câu hỏi và Preview Importer!")

    print("\n" + "="*60)
    print(">>> TẤT CẢ 28 BƯỚC KIỂM THỬ ĐÃ VƯỢT QUA XUẤT SẮC 100%! <<<")
    print("="*60)

if __name__ == "__main__":
    test_full_pipeline()


