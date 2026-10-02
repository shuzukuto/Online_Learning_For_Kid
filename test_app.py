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


    print("\n16. Kiểm tra Tính Đồng nhất Phiên bản Toàn hệ thống (Extension v1.3.15, App v1.0.24, Cache Buster ?v=1.0.28)...")
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
        assert "1.3.15" in content, f"Tệp {ef} thiếu phiên bản v1.3.15!"
        for obsolete in ["1.3.0", "1.3.11", "1.3.12", "1.3.14"]:
            assert obsolete not in content, f"Tệp {ef} còn sót phiên bản cũ {obsolete}!"
    print("   => Tiện ích Extension đồng bộ 100% v1.3.15 trên tất cả 6 tệp, sạch hoàn toàn chuỗi cũ!")

    with open("frontend/index.html", "r", encoding="utf-8") as f:
        index_html = f.read()
    with open("frontend/js/app.js", "r", encoding="utf-8") as f:
        app_js = f.read()
    assert "1.0.24" in index_html, "frontend/index.html thiếu phiên bản Web App v1.0.24!"
    assert "1.0.24" in app_js, "frontend/js/app.js thiếu phiên bản Web App v1.0.24!"
    assert "?v=1.0.28" in index_html, "frontend/index.html thiếu Cache Buster ?v=1.0.28!"
    print("   => Web App đồng bộ v1.0.24 và Cache Buster ?v=1.0.28 chính xác!")

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

    print("\n" + "="*60)
    print(">>> TẤT CẢ 19 BƯỚC KIỂM THỬ ĐÃ VƯỢT QUA XUẤT SẮC 100%! <<<")
    print("="*60)

if __name__ == "__main__":
    test_full_pipeline()
