from __future__ import annotations
import asyncio
import httpx
import math
import random
import re
import uuid
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup
from backend.classifier import classify_subject
from backend.database import insert_or_update_question, log_collector_event
from backend.normalizer import is_valid_question_payload, normalize_question_payload
# Pre-packaged rich open exam pools across multiple subjects for instant automated hunting
OPEN_EXAM_REPOSITORY = {
    "math": [
        {
            "exam_name": "Đề thi VioEdu - Đấu trường Toán học Lớp 5",
            "grade": 5,
            "subject": "math",
            "topic": "Phân số & Hỗn số",
            "question_type": "single_choice",
            "content_html": "<p>Tính giá trị của biểu thức phân số sau: $M = \\frac{3}{4} + \\frac{2}{5} - \\frac{1}{2}$</p>",
            "content_text": "Tính giá trị của biểu thức phân số sau: M = 3/4 + 2/5 - 1/2",
            "options": [
                {"id": "A", "content": "$\\frac{13}{20}$", "is_correct": True},
                {"id": "B", "content": "$\\frac{11}{20}$", "is_correct": False},
                {"id": "C", "content": "$\\frac{7}{10}$", "is_correct": False},
                {"id": "D", "content": "$\\frac{9}{20}$", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Quy đồng mẫu số chung là 20: 3/4 = 15/20; 2/5 = 8/20; 1/2 = 10/20. Vậy M = (15 + 8 - 10)/20 = 13/20.",
            "difficulty": "medium"
        },
        {
            "exam_name": "Đề khảo sát Toán Lớp 5 - Chuyển động đều",
            "grade": 5,
            "subject": "math",
            "topic": "Vận tốc, Quãng đường, Thời gian",
            "question_type": "single_choice",
            "content_html": "<p>Một ô tô đi từ tỉnh A lúc $7$ giờ $15$ phút và đến tỉnh B lúc $9$ giờ $45$ phút với vận tốc $48\\text{ km/h}$. Tính quãng đường từ tỉnh A đến tỉnh B.</p>",
            "content_text": "Một ô tô đi từ tỉnh A lúc 7 giờ 15 phút và đến tỉnh B lúc 9 giờ 45 phút với vận tốc 48 km/h. Tính quãng đường từ tỉnh A đến tỉnh B.",
            "options": [
                {"id": "A", "content": "$120\\text{ km}$", "is_correct": True},
                {"id": "B", "content": "$110\\text{ km}$", "is_correct": False},
                {"id": "C", "content": "$125\\text{ km}$", "is_correct": False},
                {"id": "D", "content": "$140\\text{ km}$", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Thời gian ô tô đi là: 9 giờ 45 phút - 7 giờ 15 phút = 2 giờ 30 phút = 2.5 giờ. Quãng đường AB là: 48 x 2.5 = 120 (km).",
            "difficulty": "medium"
        },
        {
            "exam_name": "Đề thi Học sinh giỏi Toán Lớp 5 - Tỉ số phần trăm",
            "grade": 5,
            "subject": "math",
            "topic": "Tỉ số phần trăm",
            "question_type": "single_choice",
            "content_html": "<p>Một lớp học có $40$ học sinh, trong đó có $24$ bạn nữ. Hỏi số học sinh nữ chiếm bao nhiêu phần trăm số học sinh cả lớp?</p>",
            "content_text": "Một lớp học có 40 học sinh, trong đó có 24 bạn nữ. Hỏi số học sinh nữ chiếm bao nhiêu phần trăm số học sinh cả lớp?",
            "options": [
                {"id": "A", "content": "$60\\%$", "is_correct": True},
                {"id": "B", "content": "$55\\%$", "is_correct": False},
                {"id": "C", "content": "$65\\%$", "is_correct": False},
                {"id": "D", "content": "$40\\%$", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Tỉ số phần trăm của số học sinh nữ so với cả lớp là: (24 : 40) x 100% = 60%.",
            "difficulty": "easy"
        },
        {
            "exam_name": "Đề thi Olympic Toán Lớp 5 - Hình học phẳng",
            "grade": 5,
            "subject": "math",
            "topic": "Diện tích hình thang & hình tam giác",
            "question_type": "single_choice",
            "content_html": "<p>Một thửa ruộng hình thang có đáy lớn $45\\text{ m}$, đáy bé $35\\text{ m}$ và chiều cao $24\\text{ m}$. Tính diện tích thửa ruộng đó.</p>",
            "content_text": "Một thửa ruộng hình thang có đáy lớn 45m, đáy bé 35m và chiều cao 24m. Tính diện tích thửa ruộng đó.",
            "options": [
                {"id": "A", "content": "$960\\text{ m}^2$", "is_correct": True},
                {"id": "B", "content": "$860\\text{ m}^2$", "is_correct": False},
                {"id": "C", "content": "$1020\\text{ m}^2$", "is_correct": False},
                {"id": "D", "content": "$480\\text{ m}^2$", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Diện tích thửa ruộng hình thang là: S = (45 + 35) x 24 : 2 = 80 x 12 = 960 (m2).",
            "difficulty": "medium"
        },
        {
            "exam_name": "Đề thi Trạng Nguyên Toán Lớp 4 - Tìm hai số",
            "grade": 4,
            "subject": "math",
            "topic": "Tìm hai số khi biết Tổng và Hiệu",
            "question_type": "single_choice",
            "content_html": "<p>Hai số có tổng là $186$ và hiệu là $34$. Số lớn là bao nhiêu?</p>",
            "content_text": "Hai số có tổng là 186 và hiệu là 34. Số lớn là bao nhiêu?",
            "options": [
                {"id": "A", "content": "110", "is_correct": True},
                {"id": "B", "content": "106", "is_correct": False},
                {"id": "C", "content": "112", "is_correct": False},
                {"id": "D", "content": "76", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Công thức tìm số lớn: (Tổng + Hiệu) : 2 = (186 + 34) : 2 = 220 : 2 = 110.",
            "difficulty": "easy"
        },
        {
            "exam_name": "Đề thi Toán Lớp 3 - Chu vi và Diện tích",
            "grade": 3,
            "subject": "math",
            "topic": "Hình vuông và Hình chữ nhật",
            "question_type": "single_choice",
            "content_html": "<p>Một hình chữ nhật có chiều dài $24\\text{ cm}$, chiều rộng bằng $\\frac{1}{3}$ chiều dài. Tính diện tích hình chữ nhật đó.</p>",
            "content_text": "Một hình chữ nhật có chiều dài 24 cm, chiều rộng bằng 1/3 chiều dài. Tính diện tích hình chữ nhật đó.",
            "options": [
                {"id": "A", "content": "$192\\text{ cm}^2$", "is_correct": True},
                {"id": "B", "content": "$64\\text{ cm}^2$", "is_correct": False},
                {"id": "C", "content": "$180\\text{ cm}^2$", "is_correct": False},
                {"id": "D", "content": "$96\\text{ cm}^2$", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Chiều rộng hình chữ nhật là: 24 : 3 = 8 (cm). Diện tích hình chữ nhật là: 24 x 8 = 192 (cm2).",
            "difficulty": "easy"
        },
        {
            "exam_name": "Đề thi Toán Lớp 2 - Phép cộng trừ có nhớ",
            "grade": 2,
            "subject": "math",
            "topic": "Số học trong phạm vi 100",
            "question_type": "single_choice",
            "content_html": "<p>Tìm số tự nhiên $x$, biết: $x - 38 = 45$</p>",
            "content_text": "Tìm số tự nhiên x, biết: x - 38 = 45",
            "options": [
                {"id": "A", "content": "83", "is_correct": True},
                {"id": "B", "content": "73", "is_correct": False},
                {"id": "C", "content": "82", "is_correct": False},
                {"id": "D", "content": "7", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Muốn tìm số bị trừ, ta lấy hiệu cộng với số trừ: x = 45 + 38 = 83.",
            "difficulty": "easy"
        }
    ],
    "vietnamese": [
        {
            "exam_name": "Đề thi Trạng Nguyên Tiếng Việt - Vòng Hương",
            "grade": 4,
            "subject": "vietnamese",
            "topic": "Từ đồng nghĩa & Biện pháp tu từ",
            "question_type": "single_choice",
            "content_html": "<p>Trong các câu sau, câu nào có sử dụng biện pháp nghệ thuật <strong>nhân hóa</strong>?</p>",
            "content_text": "Trong các câu sau, câu nào có sử dụng biện pháp nghệ thuật nhân hóa?",
            "options": [
                {"id": "A", "content": "Bác kim giờ thận trọng, nhích từng bước từng li.", "is_correct": True},
                {"id": "B", "content": "Mặt trời đỏ rực như một quả cầu lửa khổng lồ.", "is_correct": False},
                {"id": "C", "content": "Dòng sông mùa lũ cuồn cuộn chảy xiết.", "is_correct": False},
                {"id": "D", "content": "Cánh đồng lúa chín vàng óng ả dưới nắng mai.", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Câu A dùng từ 'Bác' và hành động 'thận trọng' vốn của con người để gán cho chiếc 'kim giờ', đó là biện pháp nhân hóa.",
            "difficulty": "medium"
        },
        {
            "exam_name": "Đề thi Khảo sát Năng lực Tiếng Việt Tiểu học",
            "grade": 5,
            "subject": "vietnamese",
            "topic": "Từ loại & Thành ngữ",
            "question_type": "single_choice",
            "content_html": "<p>Cặp từ nào dưới đây là cặp <strong>từ trái nghĩa</strong>?</p>",
            "content_text": "Cặp từ nào dưới đây là cặp từ trái nghĩa?",
            "options": [
                {"id": "A", "content": "Chân thật — Giả dối", "is_correct": True},
                {"id": "B", "content": "Chăm chỉ — Cần cù", "is_correct": False},
                {"id": "C", "content": "Dũng cảm — Gan dạ", "is_correct": False},
                {"id": "D", "content": "Thông minh — Sáng dạ", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Chân thật và Giả dối mang ý nghĩa hoàn toàn đối lập nhau nên là cặp từ trái nghĩa. Các cặp còn lại là từ đồng nghĩa.",
            "difficulty": "easy"
        },
        {
            "exam_name": "Đề thi Trạng Nguyên Toàn Tài - Vòng Hội",
            "grade": 3,
            "subject": "vietnamese",
            "topic": "Điền từ vào chỗ trống",
            "question_type": "fill_blank",
            "content_html": "<p>Điền từ còn thiếu vào câu tục ngữ sau: <i>'Lá lành đùm lá ......'</i></p>",
            "content_text": "Điền từ còn thiếu vào câu tục ngữ sau: 'Lá lành đùm lá ......'",
            "options": [],
            "correct_answer": "rách",
            "explanation": "Câu tục ngữ khuyên răn con người lòng nhân ái, tương thân tương ái: 'Lá lành đùm lá rách'.",
            "difficulty": "easy"
        }
    ],
    "english": [
        {
            "exam_name": "Olympic English Contest (IOE) - Primary Round",
            "grade": 5,
            "subject": "english",
            "topic": "Grammar & Vocabulary",
            "question_type": "single_choice",
            "content_html": "<p>Choose the best option: <i>'She ______ to the library yesterday afternoon.'</i></p>",
            "content_text": "Choose the best option: 'She ______ to the library yesterday afternoon.'",
            "options": [
                {"id": "A", "content": "went", "is_correct": True},
                {"id": "B", "content": "goes", "is_correct": False},
                {"id": "C", "content": "is going", "is_correct": False},
                {"id": "D", "content": "will go", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Dấu hiệu nhận biết 'yesterday afternoon' là thì quá khứ đơn, nên động từ 'go' chuyển thành 'went'.",
            "difficulty": "medium"
        },
        {
            "exam_name": "Primary English Olympiad - Reading Comprehension",
            "grade": 4,
            "subject": "english",
            "topic": "Vocabulary - Opposites",
            "question_type": "single_choice",
            "content_html": "<p>What is the opposite of <strong>'dangerous'</strong>?</p>",
            "content_text": "What is the opposite of 'dangerous'?",
            "options": [
                {"id": "A", "content": "safe", "is_correct": True},
                {"id": "B", "content": "quiet", "is_correct": False},
                {"id": "C", "content": "noisy", "is_correct": False},
                {"id": "D", "content": "fast", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "'Dangerous' nghĩa là nguy hiểm, từ trái nghĩa là 'safe' (an toàn).",
            "difficulty": "easy"
        }
    ],
    "science": [
        {
            "exam_name": "Đề thi Khám phá Khoa học & Tự nhiên",
            "grade": 5,
            "subject": "science",
            "topic": "Sinh học & Thực vật",
            "question_type": "single_choice",
            "content_html": "<p>Cơ quan sinh sản của thực vật có hoa là gì?</p>",
            "content_text": "Cơ quan sinh sản của thực vật có hoa là gì?",
            "options": [
                {"id": "A", "content": "Hoa", "is_correct": True},
                {"id": "B", "content": "Lá", "is_correct": False},
                {"id": "C", "content": "Thân", "is_correct": False},
                {"id": "D", "content": "Rễ", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Hoa là cơ quan sinh sản của thực vật có hoa, gồm có nhị (sinh dục đực) và nhụy (sinh dục cái).",
            "difficulty": "easy"
        },
        {
            "exam_name": "Khảo sát Khoa học Tự nhiên Lớp 5 - Năng lượng",
            "grade": 5,
            "subject": "science",
            "topic": "Năng lượng & Môi trường",
            "question_type": "single_choice",
            "content_html": "<p>Nguồn năng lượng nào sau đây là nguồn năng lượng tái tạo và thân thiện với môi trường?</p>",
            "content_text": "Nguồn năng lượng nào sau đây là nguồn năng lượng tái tạo và thân thiện với môi trường?",
            "options": [
                {"id": "A", "content": "Năng lượng gió và mặt trời", "is_correct": True},
                {"id": "B", "content": "Than đá", "is_correct": False},
                {"id": "C", "content": "Dầu mỏ", "is_correct": False},
                {"id": "D", "content": "Khí đốt tự nhiên", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Năng lượng gió và mặt trời là nguồn năng lượng tái tạo sạch, vô tận và không phát thải khí nhà kính.",
            "difficulty": "easy"
        },
        {
            "exam_name": "Khám phá Khoa học Tự nhiên Lớp 4 - Vật chất",
            "grade": 4,
            "subject": "science",
            "topic": "Nước và Không khí",
            "question_type": "single_choice",
            "content_html": "<p>Nước có những tính chất nào sau đây?</p>",
            "content_text": "Nước có những tính chất nào sau đây?",
            "options": [
                {"id": "A", "content": "Không màu, không mùi, không vị, không có hình dạng nhất định", "is_correct": True},
                {"id": "B", "content": "Có màu trắng, mùi thơm nhẹ", "is_correct": False},
                {"id": "C", "content": "Có hình dạng cố định như khối vuông", "is_correct": False},
                {"id": "D", "content": "Có vị ngọt thanh khi ở trạng thái tự nhiên", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Nước nguyên chất là chất lỏng trong suốt, không màu, không mùi, không vị và chảy tràn, không có hình dạng nhất định.",
            "difficulty": "easy"
        }
    ],
    "informatics": [
        {
            "exam_name": "Đề thi Tin học Trẻ - Phần cứng máy tính",
            "grade": 5,
            "subject": "informatics",
            "topic": "Phần cứng & Thiết bị số",
            "question_type": "single_choice",
            "content_html": "<p>Bộ phận nào được coi là 'bộ não' điều khiển mọi hoạt động của máy tính?</p>",
            "content_text": "Bộ phận nào được coi là 'bộ não' điều khiển mọi hoạt động của máy tính?",
            "options": [
                {"id": "A", "content": "Bộ vi xử lý (CPU)", "is_correct": True},
                {"id": "B", "content": "Bộ nhớ RAM", "is_correct": False},
                {"id": "C", "content": "Ổ đĩa cứng (Hard drive)", "is_correct": False},
                {"id": "D", "content": "Màn hình hiển thị", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "CPU (Central Processing Unit) là bộ xử lý trung tâm, đảm nhiệm việc xử lý dữ liệu và điều khiển mọi hoạt động của máy tính.",
            "difficulty": "easy"
        },
        {
            "exam_name": "Đề thi Tin học Trẻ - Mạng Internet & An toàn số",
            "grade": 4,
            "subject": "informatics",
            "topic": "An toàn thông tin mạng",
            "question_type": "single_choice",
            "content_html": "<p>Khi sử dụng Internet, hành động nào sau đây là <strong>đúng đắn và an toàn</strong>?</p>",
            "content_text": "Khi sử dụng Internet, hành động nào sau đây là đúng đắn và an toàn?",
            "options": [
                {"id": "A", "content": "Không chia sẻ mật khẩu tài khoản và thông tin cá nhân cho người lạ", "is_correct": True},
                {"id": "B", "content": "Bấm vào các liên kết lạ trúng thưởng xuất hiện trên màn hình", "is_correct": False},
                {"id": "C", "content": "Đặt mật khẩu dễ đoán như 123456 cho tiện ghi nhớ", "is_correct": False},
                {"id": "D", "content": "Cung cấp số điện thoại và địa chỉ nhà cho người quen qua mạng", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Để bảo đảm an toàn trên không gian mạng, tuyệt đối không tiết lộ mật khẩu, thông tin cá nhân hay bấm vào đường link lạ.",
            "difficulty": "easy"
        }
    ]
}



# Specialized curriculum exercise repositories for Hành trang số (NXB Giáo Dục Việt Nam)
HANHTRANGSO_CURRICULUM_POOLS = {
    2: [
        {
            "exam_name": "Hành trang số - SGK Toán 2 (Kết nối tri thức & Cánh diều)",
            "grade": 2,
            "subject": "math",
            "topic": "Phép cộng, phép trừ có nhớ trong phạm vi 100",
            "question_type": "single_choice",
            "content_html": "<p>Tính nhẩm kết quả của phép tính sau: $48 + 27$</p>",
            "content_text": "Tính nhẩm kết quả của phép tính sau: 48 + 27",
            "options": [
                {"id": "A", "content": "$75$", "is_correct": True},
                {"id": "B", "content": "$65$", "is_correct": False},
                {"id": "C", "content": "$74$", "is_correct": False},
                {"id": "D", "content": "$76$", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Ta có: 8 + 7 = 15 (viết 5 nhớ 1), 4 + 2 = 6, thêm 1 bằng 7. Vậy 48 + 27 = 75.",
            "difficulty": "easy"
        },
        {
            "exam_name": "Hành trang số - SGK Toán 2 - Đo lường",
            "grade": 2,
            "subject": "math",
            "topic": "Đơn vị đo lít (l) và ki-lô-gam (kg)",
            "question_type": "single_choice",
            "content_html": "<p>Một can đựng $15l$ dầu, người ta rót ra $7l$ dầu. Hỏi trong can còn lại bao nhiêu lít dầu?</p>",
            "content_text": "Một can đựng 15l dầu, người ta rót ra 7l dầu. Hỏi trong can còn lại bao nhiêu lít dầu?",
            "options": [
                {"id": "A", "content": "$8l$", "is_correct": True},
                {"id": "B", "content": "$9l$", "is_correct": False},
                {"id": "C", "content": "$7l$", "is_correct": False},
                {"id": "D", "content": "$22l$", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Số lít dầu còn lại trong can là: 15 - 7 = 8 (lít).",
            "difficulty": "easy"
        },
        {
            "exam_name": "Hành trang số - Tiếng Việt 2 - Luyện từ và câu",
            "grade": 2,
            "subject": "vietnamese",
            "topic": "Từ chỉ hoạt động và câu kiểu Ai làm gì?",
            "question_type": "single_choice",
            "content_html": "<p>Trong câu <i>'Bầy chim hót líu lo trên cành khế.'</i>, từ ngữ nào là <strong>từ chỉ hoạt động</strong>?</p>",
            "content_text": "Trong câu 'Bầy chim hót líu lo trên cành khế.', từ ngữ nào là từ chỉ hoạt động?",
            "options": [
                {"id": "A", "content": "hót", "is_correct": True},
                {"id": "B", "content": "bầy chim", "is_correct": False},
                {"id": "C", "content": "líu lo", "is_correct": False},
                {"id": "D", "content": "cành khế", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "'Hót' là từ chỉ hoạt động phát ra âm thanh của loài chim.",
            "difficulty": "easy"
        },
        {
            "exam_name": "Hành trang số - Tiếng Việt 2 - Dấu câu",
            "grade": 2,
            "subject": "vietnamese",
            "topic": "Dấu chấm, dấu phẩy, dấu chấm hỏi",
            "question_type": "fill_blank",
            "content_html": "<p>Chọn dấu câu thích hợp điền vào cuối câu sau: <i>'Hôm nay bạn có đi học không ......'</i></p>",
            "content_text": "Chọn dấu câu thích hợp điền vào cuối câu sau: 'Hôm nay bạn có đi học không ......'",
            "options": [],
            "correct_answer": "?",
            "explanation": "Câu trên là câu hỏi dùng để thăm dò thông tin, do đó cuối câu cần đặt dấu chấm hỏi (?).",
            "difficulty": "easy"
        }
    ]
}



# Curated CodeMath International Olympiad Question Repositories (TIMO, HKIMO, BBB, IKMC, FMO, ITMC, SASMO, SEAMO)
CODEMATH_OLYMPIAD_POOLS = {
    "timo": [
        {
            "exam_name": "CodeMath - Đề luyện thi Olympic Toán Quốc tế TIMO",
            "grade": 5,
            "subject": "math",
            "topic": "Olympic TIMO - Số học & Chữ số tận cùng",
            "question_type": "single_choice",
            "content_html": "<p>Tìm chữ số tận cùng của tích sau: $P = 1 \\times 3 \\times 5 \\times 7 \\times \\dots \\times 2025$</p>",
            "content_text": "Tìm chữ số tận cùng của tích sau: P = 1 * 3 * 5 * 7 * ... * 2025",
            "options": [
                {"id": "A", "content": "5", "is_correct": True},
                {"id": "B", "content": "0", "is_correct": False},
                {"id": "C", "content": "1", "is_correct": False},
                {"id": "D", "content": "9", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Tích P gồm toàn các số lẻ và có chứa thừa số 5. Một số lẻ bất kỳ nhân với 5 luôn có chữ số tận cùng là 5. Do đó tích P có tận cùng là 5.",
            "difficulty": "olympiad"
        },
        {
            "exam_name": "CodeMath - Đề thi thử TIMO - Dãy số & Tư duy logic",
            "grade": 4,
            "subject": "math",
            "topic": "Olympic TIMO - Quy luật dãy số",
            "question_type": "single_choice",
            "content_html": "<p>Điền số tiếp theo vào dấu ba chấm trong dãy số sau: $2, 5, 10, 17, 26, \\dots$</p>",
            "content_text": "Điền số tiếp theo vào dấu ba chấm trong dãy số sau: 2, 5, 10, 17, 26, ...",
            "options": [
                {"id": "A", "content": "37", "is_correct": True},
                {"id": "B", "content": "35", "is_correct": False},
                {"id": "C", "content": "36", "is_correct": False},
                {"id": "D", "content": "40", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Khoảng cách giữa các số liên tiếp lần lượt là: 3, 5, 7, 9, ... (dãy số lẻ tăng dần). Số tiếp theo là 26 + 11 = 37.",
            "difficulty": "olympiad"
        }
    ],
    "hkimo": [
        {
            "exam_name": "CodeMath - Đề thi Olympic Toán Quốc tế Hồng Kông (HKIMO)",
            "grade": 5,
            "subject": "math",
            "topic": "Olympic HKIMO - Hình học & Đếm hình",
            "question_type": "single_choice",
            "content_html": "<p>Có bao nhiêu hình vuông trong một hình lưới có kích thước $4 \\times 4$ ô vuông đơn vị?</p>",
            "content_text": "Có bao nhiêu hình vuông trong một hình lưới có kích thước 4x4 ô vuông đơn vị?",
            "options": [
                {"id": "A", "content": "30 hình", "is_correct": True},
                {"id": "B", "content": "16 hình", "is_correct": False},
                {"id": "C", "content": "25 hình", "is_correct": False},
                {"id": "D", "content": "32 hình", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Số hình vuông các kích thước từ 1x1 đến 4x4 là: 4^2 + 3^2 + 2^2 + 1^2 = 16 + 9 + 4 + 1 = 30 hình.",
            "difficulty": "olympiad"
        },
        {
            "exam_name": "CodeMath - HKIMO Tổ hợp & Lý thuyết số",
            "grade": 3,
            "subject": "math",
            "topic": "Olympic HKIMO - Chữ số & Phép chia hết",
            "question_type": "single_choice",
            "content_html": "<p>Có bao nhiêu số có hai chữ số mà tổng hai chữ số của nó chia hết cho $5$?</p>",
            "content_text": "Có bao nhiêu số có hai chữ số mà tổng hai chữ số của nó chia hết cho 5?",
            "options": [
                {"id": "A", "content": "18 số", "is_correct": True},
                {"id": "B", "content": "15 số", "is_correct": False},
                {"id": "C", "content": "20 số", "is_correct": False},
                {"id": "D", "content": "16 số", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Tổng hai chữ số chia hết cho 5 có thể là 5 (các số: 14, 23, 32, 41, 50 -> 5 số), tổng 10 (19, 28, 37, 46, 55, 64, 73, 82, 91 -> 9 số), tổng 15 (69, 78, 87, 96 -> 4 số). Tổng cộng: 5 + 9 + 4 = 18 số.",
            "difficulty": "olympiad"
        }
    ],
    "bbb": [
        {
            "exam_name": "CodeMath - Đấu trường Toán Quốc tế BBB (Big Bang Beagle)",
            "grade": 4,
            "subject": "math",
            "topic": "Olympic BBB - Quy luật hình học & Chu kỳ",
            "question_type": "single_choice",
            "content_html": "<p>Trong một dãy hình lặp lại theo quy luật: $\\Delta, \\square, \\bigcirc, \\Delta, \\square, \\bigcirc, \\dots$, hỏi hình thứ $2024$ là hình gì?</p>",
            "content_text": "Trong một dãy hình lặp lại theo quy luật: Tam giác, Vuông, Tròn, Tam giác, Vuông, Tròn..., hỏi hình thứ 2024 là hình gì?",
            "options": [
                {"id": "A", "content": "Hình vuông ($\\square$)", "is_correct": True},
                {"id": "B", "content": "Hình tam giác ($\\Delta$)", "is_correct": False},
                {"id": "C", "content": "Hình tròn ($\\bigcirc$)", "is_correct": False},
                {"id": "D", "content": "Hình ngôi sao ($\\star$)", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Chu kỳ lặp lại gồm 3 hình. Ta lấy 2024 chia cho 3 được thương 674 và dư 2. Do dư 2 nên hình thứ 2024 tương ứng với hình thứ hai trong chu kỳ, đó là hình vuông.",
            "difficulty": "olympiad"
        }
    ],
    "ikmc": [
        {
            "exam_name": "CodeMath - Toán Quốc tế Kangaroo (IKMC)",
            "grade": 3,
            "subject": "math",
            "topic": "Olympic IKMC - Không gian & Hình học trực quan",
            "question_type": "single_choice",
            "content_html": "<p>Một cái bánh pizza hình tròn được cắt bằng $4$ nhát cắt thẳng đều đi qua tâm bánh. Hỏi chia được nhiều nhất bao nhiêu miếng bánh hình quạt?</p>",
            "content_text": "Một cái bánh pizza hình tròn được cắt bằng 4 nhát cắt thẳng đều đi qua tâm bánh. Hỏi chia được nhiều nhất bao nhiêu miếng bánh hình quạt?",
            "options": [
                {"id": "A", "content": "8 miếng", "is_correct": True},
                {"id": "B", "content": "6 miếng", "is_correct": False},
                {"id": "C", "content": "10 miếng", "is_correct": False},
                {"id": "D", "content": "16 miếng", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Mỗi đường cắt thẳng đi qua tâm chia hình tròn thành 2 phần đối xứng. Cắt 4 nhát qua tâm sẽ tạo ra 4 x 2 = 8 miếng bánh bằng nhau.",
            "difficulty": "olympiad"
        }
    ],
    "sasmo": [
        {
            "exam_name": "CodeMath - Olympic Toán Quốc tế Singapore & Châu Á (SASMO)",
            "grade": 5,
            "subject": "math",
            "topic": "Olympic SASMO - Lịch & Đồng hồ Modular",
            "question_type": "single_choice",
            "content_html": "<p>Hôm nay là Thứ Ba. Hỏi đúng $100$ ngày nữa sẽ là ngày thứ mấy trong tuần?</p>",
            "content_text": "Hôm nay là Thứ Ba. Hỏi đúng 100 ngày nữa sẽ là ngày thứ mấy trong tuần?",
            "options": [
                {"id": "A", "content": "Thứ Năm", "is_correct": True},
                {"id": "B", "content": "Thứ Tư", "is_correct": False},
                {"id": "C", "content": "Thứ Sáu", "is_correct": False},
                {"id": "D", "content": "Chủ Nhật", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Một tuần có 7 ngày. Ta có: 100 : 7 = 14 tuần và dư 2 ngày. Từ Thứ Ba đếm thêm 2 ngày ta được: Thứ Tư, Thứ Năm. Vậy 100 ngày nữa là Thứ Năm.",
            "difficulty": "olympiad"
        }
    ],
    "fmo": [
        {
            "exam_name": "CodeMath - Olympic Toán Quốc tế Fermat (FMO)",
            "grade": 5,
            "subject": "math",
            "topic": "Olympic FMO - Biểu đồ Venn & Tập hợp",
            "question_type": "single_choice",
            "content_html": "<p>Một lớp có $35$ học sinh. Trong đó có $20$ bạn thích bóng đá, $18$ bạn thích bơi lội, và $5$ bạn không thích cả hai môn. Hỏi có bao nhiêu bạn thích cả hai môn thể thao?</p>",
            "content_text": "Một lớp có 35 học sinh. Trong đó có 20 bạn thích bóng đá, 18 bạn thích bơi lội, và 5 bạn không thích cả hai môn. Hỏi có bao nhiêu bạn thích cả hai môn thể thao?",
            "options": [
                {"id": "A", "content": "8 bạn", "is_correct": True},
                {"id": "B", "content": "10 bạn", "is_correct": False},
                {"id": "C", "content": "12 bạn", "is_correct": False},
                {"id": "D", "content": "5 bạn", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Số học sinh thích ít nhất một môn thể thao là: 35 - 5 = 30 bạn. Số bạn thích cả hai môn là: 20 + 18 - 30 = 8 bạn.",
            "difficulty": "olympiad"
        }
    ],
    "itmc": [
        {
            "exam_name": "CodeMath - Đề thi Tìm kiếm Tài năng Toán học (ITMC)",
            "grade": 4,
            "subject": "math",
            "topic": "Olympic ITMC - Tính nhanh dãy số cách đều",
            "question_type": "single_choice",
            "content_html": "<p>Tính tổng nhanh biểu thức sau: $S = 1 + 3 + 5 + 7 + \\dots + 99$</p>",
            "content_text": "Tính tổng nhanh biểu thức sau: S = 1 + 3 + 5 + 7 + ... + 99",
            "options": [
                {"id": "A", "content": "2500", "is_correct": True},
                {"id": "B", "content": "2450", "is_correct": False},
                {"id": "C", "content": "2550", "is_correct": False},
                {"id": "D", "content": "5000", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Số số hạng: (99 - 1) : 2 + 1 = 50 số. Tổng = (1 + 99) x 50 : 2 = 100 x 25 = 2500.",
            "difficulty": "olympiad"
        }
    ],
    "seamo": [
        {
            "exam_name": "CodeMath - Olympic Toán học Đông Nam Á (SEAMO)",
            "grade": 5,
            "subject": "math",
            "topic": "Olympic SEAMO - Phân số quy luật rút gọn",
            "question_type": "single_choice",
            "content_html": "<p>Tính giá trị biểu thức: $S = \\frac{1}{1 \\times 2} + \\frac{1}{2 \\times 3} + \\frac{1}{3 \\times 4} + \\dots + \\frac{1}{99 \\times 100}$</p>",
            "content_text": "Tính giá trị biểu thức: S = 1/(1x2) + 1/(2x3) + 1/(3x4) + ... + 1/(99x100)",
            "options": [
                {"id": "A", "content": "$\\frac{99}{100}$", "is_correct": True},
                {"id": "B", "content": "$\\frac{98}{99}$", "is_correct": False},
                {"id": "C", "content": "$1$", "is_correct": False},
                {"id": "D", "content": "$\\frac{100}{101}$", "is_correct": False}
            ],
            "correct_answer": "A",
            "explanation": "Ta có: S = 1 - 1/2 + 1/2 - 1/3 + 1/3 - ... - 1/100 = 1 - 1/100 = 99/100.",
            "difficulty": "olympiad"
        }
    ]
}



# =====================================================================
# SPECIALIZED GRADE 2 MATH REPOSITORIES (TIẾNG VIỆT, TIẾNG ANH, OLYMPIC)
# =====================================================================

GRADE2_MATH_VN_POOLS = [
    {
        "exam_name": "Đề kiểm tra Toán Lớp 2 - VioEdu & OLM",
        "grade": 2,
        "subject": "math",
        "topic": "Phép cộng có nhớ trong phạm vi 100",
        "question_type": "single_choice",
        "content_html": "<p>Kết quả của phép tính $47 + 38$ là:</p>",
        "content_text": "Kết quả của phép tính 47 + 38 là:",
        "options": [
            {"id": "A", "content": "85", "is_correct": True},
            {"id": "B", "content": "75", "is_correct": False},
            {"id": "C", "content": "84", "is_correct": False},
            {"id": "D", "content": "95", "is_correct": False}
        ],
        "correct_answer": "A",
        "explanation": "Ta có: 7 + 8 = 15 (viết 5 nhớ 1), 4 + 3 = 7 thêm 1 bằng 8. Vậy 47 + 38 = 85.",
        "difficulty": "easy",
        "source_detail": "VioEdu (FPT)"
    },
    {
        "exam_name": "Phiếu bài tập cuối tuần Toán Lớp 2 - VnDoc",
        "grade": 2,
        "subject": "math",
        "topic": "Bài toán nhiều hơn (Toán có lời văn)",
        "question_type": "single_choice",
        "content_html": "<p>Bạn Mai hái được $28$ bông hoa, bạn Lan hái được nhiều hơn bạn Mai $15$ bông hoa. Hỏi bạn Lan hái được bao nhiêu bông hoa?</p>",
        "content_text": "Bạn Mai hái được 28 bông hoa, bạn Lan hái được nhiều hơn bạn Mai 15 bông hoa. Hỏi bạn Lan hái được bao nhiêu bông hoa?",
        "options": [
            {"id": "A", "content": "43 bông hoa", "is_correct": True},
            {"id": "B", "content": "33 bông hoa", "is_correct": False},
            {"id": "C", "content": "42 bông hoa", "is_correct": False},
            {"id": "D", "content": "13 bông hoa", "is_correct": False}
        ],
        "correct_answer": "A",
        "explanation": "Số bông hoa bạn Lan hái được là: 28 + 15 = 43 (bông hoa).",
        "difficulty": "easy",
        "source_detail": "VnDoc"
    },
    {
        "exam_name": "Trạng Nguyên Toán Học Lớp 2 - Vòng Sơ khảo",
        "grade": 2,
        "subject": "math",
        "topic": "Phép trừ có nhớ trong phạm vi 100",
        "question_type": "single_choice",
        "content_html": "<p>Tính giá trị của phép tính: $72 - 35$</p>",
        "content_text": "Tính giá trị của phép tính: 72 - 35",
        "options": [
            {"id": "A", "content": "37", "is_correct": True},
            {"id": "B", "content": "47", "is_correct": False},
            {"id": "C", "content": "35", "is_correct": False},
            {"id": "D", "content": "43", "is_correct": False}
        ],
        "correct_answer": "A",
        "explanation": "Ta lấy 12 - 5 = 7 (nhớ 1 sang 3 là 4), 7 - 4 = 3. Kết quả là 37.",
        "difficulty": "easy",
        "source_detail": "Trạng Nguyên Toán"
    },
    {
        "exam_name": "Đề khảo sát Toán Lớp 2 - OLM.vn",
        "grade": 2,
        "subject": "math",
        "topic": "Bảng nhân 2 & Bảng nhân 5",
        "question_type": "single_choice",
        "content_html": "<p>Mỗi bàn học có $2$ bạn học sinh ngồi. Hỏi $8$ bàn học như thế có tất cả bao nhiêu bạn học sinh?</p>",
        "content_text": "Mỗi bàn học có 2 bạn học sinh ngồi. Hỏi 8 bàn học như thế có tất cả bao nhiêu bạn học sinh?",
        "options": [
            {"id": "A", "content": "16 bạn", "is_correct": True},
            {"id": "B", "content": "10 bạn", "is_correct": False},
            {"id": "C", "content": "18 bạn", "is_correct": False},
            {"id": "D", "content": "14 bạn", "is_correct": False}
        ],
        "correct_answer": "A",
        "explanation": "Số học sinh có trong 8 bàn là: 2 x 8 = 16 (bạn học sinh).",
        "difficulty": "easy",
        "source_detail": "OLM.vn (ĐH Sư Phạm)"
    },
    {
        "exam_name": "SGK Toán 2 - VietJack & Cánh Diều",
        "grade": 2,
        "subject": "math",
        "topic": "Đơn vị đo dung tích (lít)",
        "question_type": "single_choice",
        "content_html": "<p>Có một thùng đựng $20l$ nước mắm. Người ta rót đều vào các can, mỗi can chứa $5l$. Hỏi rót được tất cả bao nhiêu can?</p>",
        "content_text": "Có một thùng đựng 20l nước mắm. Người ta rót đều vào các can, mỗi can chứa 5l. Hỏi rót được tất cả bao nhiêu can?",
        "options": [
            {"id": "A", "content": "4 can", "is_correct": True},
            {"id": "B", "content": "5 can", "is_correct": False},
            {"id": "C", "content": "3 can", "is_correct": False},
            {"id": "D", "content": "15 can", "is_correct": False}
        ],
        "correct_answer": "A",
        "explanation": "Số can rót được là: 20 : 5 = 4 (can).",
        "difficulty": "easy",
        "source_detail": "VietJack"
    },
    {
        "exam_name": "SGK Toán 2 Kết nối tri thức - Hành Trang Số",
        "grade": 2,
        "subject": "math",
        "topic": "Hình học - Độ dài đường gấp khúc",
        "question_type": "single_choice",
        "content_html": "<p>Một đường gấp khúc gồm ba đoạn thẳng có độ dài lần lượt là $14\\text{ cm}$, $26\\text{ cm}$ và $30\\text{ cm}$. Tính độ dài đường gấp khúc đó.</p>",
        "content_text": "Một đường gấp khúc gồm ba đoạn thẳng có độ dài lần lượt là 14 cm, 26 cm và 30 cm. Tính độ dài đường gấp khúc đó.",
        "options": [
            {"id": "A", "content": "$70\\text{ cm}$", "is_correct": True},
            {"id": "B", "content": "$60\\text{ cm}$", "is_correct": False},
            {"id": "C", "content": "$80\\text{ cm}$", "is_correct": False},
            {"id": "D", "content": "$65\\text{ cm}$", "is_correct": False}
        ],
        "correct_answer": "A",
        "explanation": "Độ dài đường gấp khúc là: 14 + 26 + 30 = 70 (cm).",
        "difficulty": "easy",
        "source_detail": "Hành Trang Số (SGK)"
    }
]



GRADE2_MATH_EN_POOLS = [
    {
        "exam_name": "K5 Learning - 2nd Grade Math Worksheets",
        "grade": 2,
        "subject": "math",
        "topic": "2nd Grade Word Problems (Regrouping Addition)",
        "question_type": "single_choice",
        "content_html": "<p>Lucas has $46$ crayons. His mom buys him a new pack of $28$ crayons. How many crayons does Lucas have now?</p>",
        "content_text": "Lucas has 46 crayons. His mom buys him a new pack of 28 crayons. How many crayons does Lucas have now?",
        "options": [
            {"id": "A", "content": "74 crayons", "is_correct": True},
            {"id": "B", "content": "64 crayons", "is_correct": False},
            {"id": "C", "content": "72 crayons", "is_correct": False},
            {"id": "D", "content": "84 crayons", "is_correct": False}
        ],
        "correct_answer": "A",
        "explanation": "Add the two quantities together: 46 + 28 = 74 crayons.",
        "difficulty": "easy",
        "source_detail": "K5 Learning (US Math)"
    },
    {
        "exam_name": "K5 Learning - 2nd Grade Subtraction Worksheets",
        "grade": 2,
        "subject": "math",
        "topic": "Subtraction with Regrouping (Word Problems)",
        "question_type": "single_choice",
        "content_html": "<p>A baker baked $83$ cupcakes. By lunchtime, he sold $37$ cupcakes. How many cupcakes are left?</p>",
        "content_text": "A baker baked 83 cupcakes. By lunchtime, he sold 37 cupcakes. How many cupcakes are left?",
        "options": [
            {"id": "A", "content": "46 cupcakes", "is_correct": True},
            {"id": "B", "content": "56 cupcakes", "is_correct": False},
            {"id": "C", "content": "44 cupcakes", "is_correct": False},
            {"id": "D", "content": "48 cupcakes", "is_correct": False}
        ],
        "correct_answer": "A",
        "explanation": "Subtract the cupcakes sold: 83 - 37 = 46 cupcakes.",
        "difficulty": "easy",
        "source_detail": "K5 Learning (US Math)"
    },
    {
        "exam_name": "IXL Learning - Grade 2 Place Value Skills",
        "grade": 2,
        "subject": "math",
        "topic": "Place Value (Hundreds, Tens, and Ones)",
        "question_type": "single_choice",
        "content_html": "<p>In the number $784$, what is the value of the digit <strong>$8$</strong>?</p>",
        "content_text": "In the number 784, what is the value of the digit 8?",
        "options": [
            {"id": "A", "content": "80", "is_correct": True},
            {"id": "B", "content": "800", "is_correct": False},
            {"id": "C", "content": "8", "is_correct": False},
            {"id": "D", "content": "84", "is_correct": False}
        ],
        "correct_answer": "A",
        "explanation": "The digit 8 is in the tens place, so its value is 8 tens, which equals 80.",
        "difficulty": "easy",
        "source_detail": "IXL Learning Math"
    },
    {
        "exam_name": "IXL Learning - 2nd Grade Math Skills",
        "grade": 2,
        "subject": "math",
        "topic": "Even and Odd Numbers",
        "question_type": "single_choice",
        "content_html": "<p>Which of the following numbers is an <strong>EVEN</strong> number?</p>",
        "content_text": "Which of the following numbers is an EVEN number?",
        "options": [
            {"id": "A", "content": "58", "is_correct": True},
            {"id": "B", "content": "47", "is_correct": False},
            {"id": "C", "content": "63", "is_correct": False},
            {"id": "D", "content": "81", "is_correct": False}
        ],
        "correct_answer": "A",
        "explanation": "Even numbers end in 0, 2, 4, 6, or 8. The number 58 ends in 8, so it is an even number.",
        "difficulty": "easy",
        "source_detail": "IXL Learning Math"
    },
    {
        "exam_name": "Khan Academy - 2nd Grade Common Core Math",
        "grade": 2,
        "subject": "math",
        "topic": "Money & Coins (Cents)",
        "question_type": "single_choice",
        "content_html": "<p>Mia has $3$ dimes and $4$ nickels. How many cents does she have in total?</p>",
        "content_text": "Mia has 3 dimes and 4 nickels. How many cents does she have in total?",
        "options": [
            {"id": "A", "content": "50 cents", "is_correct": True},
            {"id": "B", "content": "40 cents", "is_correct": False},
            {"id": "C", "content": "70 cents", "is_correct": False},
            {"id": "D", "content": "34 cents", "is_correct": False}
        ],
        "correct_answer": "A",
        "explanation": "1 dime = 10 cents, 1 nickel = 5 cents. Total = (3 x 10) + (4 x 5) = 30 + 20 = 50 cents.",
        "difficulty": "easy",
        "source_detail": "Khan Academy Math"
    },
    {
        "exam_name": "K5 Learning - 2nd Grade Geometry Worksheets",
        "grade": 2,
        "subject": "math",
        "topic": "2D Shapes & Vertices",
        "question_type": "single_choice",
        "content_html": "<p>How many sides and vertices does a <strong>hexagon</strong> have?</p>",
        "content_text": "How many sides and vertices does a hexagon have?",
        "options": [
            {"id": "A", "content": "6 sides and 6 vertices", "is_correct": True},
            {"id": "B", "content": "5 sides and 5 vertices", "is_correct": False},
            {"id": "C", "content": "8 sides and 8 vertices", "is_correct": False},
            {"id": "D", "content": "4 sides and 4 vertices", "is_correct": False}
        ],
        "correct_answer": "A",
        "explanation": "A hexagon is a 2D geometric polygon that has exactly 6 sides and 6 vertices.",
        "difficulty": "easy",
        "source_detail": "K5 Learning (US Math)"
    }
]



GRADE2_MATH_OLYMPIAD_POOLS = [
    {
        "exam_name": "Kỳ thi Toán Quốc tế Kangaroo (IKMC) - Lớp 1 & 2",
        "grade": 2,
        "subject": "math",
        "topic": "Toán tư duy Logic & Dãy số (Ecolier)",
        "question_type": "single_choice",
        "content_html": "<p>A rabbit jumps along stones numbered: $2, 5, 8, 11, 14, \\dots$ What number is on the next stone?<br/><i>(Một chú thỏ nhảy qua các hòn đá mang số: $2, 5, 8, 11, 14, \\dots$ Hỏi hòn đá tiếp theo mang số mấy?)</i></p>",
        "content_text": "A rabbit jumps along stones numbered: 2, 5, 8, 11, 14, ... What number is on the next stone? (Một chú thỏ nhảy qua các hòn đá mang số: 2, 5, 8, 11, 14, ... Hỏi hòn đá tiếp theo mang số mấy?)",
        "options": [
            {"id": "A", "content": "17", "is_correct": True},
            {"id": "B", "content": "16", "is_correct": False},
            {"id": "C", "content": "18", "is_correct": False},
            {"id": "D", "content": "15", "is_correct": False}
        ],
        "correct_answer": "A",
        "explanation": "Dãy số tăng dần 3 đơn vị: 14 + 3 = 17.",
        "difficulty": "olympiad",
        "source_detail": "Olympic Kangaroo (IKMC)"
    },
    {
        "exam_name": "Olympic Toán Quốc tế TIMO - Khối 2 (Primary 2)",
        "grade": 2,
        "subject": "math",
        "topic": "Tư duy Logic & Hình học (TIMO P2)",
        "question_type": "single_choice",
        "content_html": "<p>How many small squares are there in a $3 \\times 3$ grid?<br/><i>(Có bao nhiêu hình vuông đơn vị $1 \\times 1$ trong một lưới ô vuông kích thước $3 \\times 3$?)</i></p>",
        "content_text": "How many small squares are there in a 3x3 grid? (Có bao nhiêu hình vuông đơn vị 1x1 trong một lưới ô vuông kích thước 3x3?)",
        "options": [
            {"id": "A", "content": "9", "is_correct": True},
            {"id": "B", "content": "6", "is_correct": False},
            {"id": "C", "content": "12", "is_correct": False},
            {"id": "D", "content": "14", "is_correct": False}
        ],
        "correct_answer": "A",
        "explanation": "Lưới 3 x 3 gồm 3 hàng và 3 cột, có 3 x 3 = 9 hình vuông đơn vị.",
        "difficulty": "olympiad",
        "source_detail": "Olympic TIMO"
    },
    {
        "exam_name": "Toán Tư duy Singapore SASMO - Grade 2",
        "grade": 2,
        "subject": "math",
        "topic": "Toán suy luận tuổi (Bilingual SASMO)",
        "question_type": "single_choice",
        "content_html": "<p>Lily is $7$ years old. Her brother Tom is $3$ years older than Lily. How old will Tom be in $4$ years?<br/><i>(Lily 7 tuổi. Anh trai Tom nhiều hơn Lily 3 tuổi. Hỏi sau 4 năm nữa Tom bao nhiêu tuổi?)</i></p>",
        "content_text": "Lily is 7 years old. Her brother Tom is 3 years older than Lily. How old will Tom be in 4 years? (Lily 7 tuổi. Anh trai Tom nhiều hơn Lily 3 tuổi. Hỏi sau 4 năm nữa Tom bao nhiêu tuổi?)",
        "options": [
            {"id": "A", "content": "14 tuổi", "is_correct": True},
            {"id": "B", "content": "10 tuổi", "is_correct": False},
            {"id": "C", "content": "13 tuổi", "is_correct": False},
            {"id": "D", "content": "15 tuổi", "is_correct": False}
        ],
        "correct_answer": "A",
        "explanation": "Tuổi hiện nay của Tom: 7 + 3 = 10 tuổi. Sau 4 năm nữa Tom có số tuổi là: 10 + 4 = 14 (tuổi).",
        "difficulty": "olympiad",
        "source_detail": "Olympic SASMO"
    }
]



# Lời Giải Hay EXAM-listing IDs — VERIFIED live 2026-10-11 (all HTTP 200).
# These de-thi-...-cNNN.html pages list exam detail pages (-aNNNNNN.html)
# whose div.question blocks carry div.loigiai answer keys.
# (The chapter pages toan-lop-X-c12X.html instead list doc-hieu van links.)
LOIGIAIHAY_MATH_CAT = {1: 1211, 2: 1212, 3: 1215, 4: 1636, 5: 1990,
                       6: 1022, 7: 1097, 8: 1612, 9: 1984, 11: 1623, 12: 1964}
LOIGIAIHAY_VN_CAT = {2: 1213, 3: 2269, 4: 1796, 5: 1994, 9: 1968, 12: 1972}
LOIGIAIHAY_EN_CAT = {2: 1217, 3: 1218, 4: 1627, 5: 2008,
                     6: 1160, 7: 1182, 8: 1658, 9: 2003, 10: 1192}
LOIGIAIHAY_MATH_SLUGS = {
    1: "de-thi-de-kiem-tra-toan-lop-1-ket-noi-tri-thuc-c1211.html",
    2: "de-thi-de-kiem-tra-toan-lop-2-ket-noi-tri-thuc-c1212.html",
    3: "de-thi-de-kiem-tra-toan-lop-3-ket-noi-tri-thuc-c1215.html",
    4: "de-thi-de-kiem-tra-toan-lop-4-ket-noi-tri-thuc-c1636.html",
    5: "de-thi-de-kiem-tra-toan-lop-5-ket-noi-tri-thuc-c1990.html",
    # Grades 6-12 — VERIFIED live 2026-10-12 (all HTTP 200, homepage harvest).
    6: "de-thi-de-kiem-tra-toan-lop-6-ket-noi-tri-thuc-c1022.html",
    7: "de-thi-de-kiem-tra-toan-lop-7-ket-noi-tri-thuc-c1097.html",
    8: "de-thi-de-kiem-tra-toan-lop-8-ket-noi-tri-thuc-c1612.html",
    9: "de-thi-de-kiem-tra-toan-lop-9-ket-noi-tri-thuc-c1984.html",
    10: "v2/tu-luyen-trac-nghiem-toan-10-ket-noi-tri-thuc-c980.html",
    11: "de-thi-de-kiem-tra-toan-lop-11-ket-noi-tri-thuc-c1623.html",
    12: "de-thi-de-kiem-tra-toan-lop-12-ket-noi-tri-thuc-c1964.html",
}
LOIGIAIHAY_VN_SLUGS = {
    2: "de-thi-de-kiem-tra-tieng-viet-lop-2-ket-noi-tri-thuc-c1213.html",
    3: "de-thi-de-kiem-tra-tieng-viet-lop-3-ket-noi-tri-thuc-c2269.html",
    4: "de-thi-de-kiem-tra-tieng-viet-lop-4-ket-noi-tri-thuc-c1796.html",
    5: "de-thi-de-kiem-tra-tieng-viet-lop-5-ket-noi-tri-thuc-c1994.html",
    # Grade 9 Van (de-thi van-9) — VERIFIED 200 2026-10-12.
    9: "de-thi-de-kiem-tra-van-9-ket-noi-tri-thuc-c1968.html",
    # Grade 12 Van de-thi listing (41 exams) — VERIFIED 200 2026-10-12.
    12: "de-thi-de-kiem-tra-van-12-ket-noi-tri-thuc-c1972.html",
}
# Grade 6-12 Van trac-nghiem/tu-luyen hubs — VERIFIED live 2026-10-12
# (all HTTP 200, titles match grade+subject; these list /v2/ quiz links).
LOIGIAIHAY_VN_TRACNGHIEM = {
    6: "v2/tu-luyen-tu-luyen-van-6-kntt-c788.html",
    7: "v2/tu-luyen-tu-luyen-van-7-c761.html",
    8: "v2/tu-luyen-trac-nghiem-van-8-ket-noi-tri-thuc-c1453.html",
    10: "v2/tu-luyen-trac-nghiem-ngu-van-10-ket-noi-tri-thuc-c959.html",
    11: "v2/tu-luyen-trac-nghiem-van-11-ket-noi-tri-thuc-c1481.html",
}
LOIGIAIHAY_EN_SLUGS = {
    2: "de-thi-de-kiem-tra-tieng-anh-lop-2-ket-noi-tri-thuc-c1217.html",
    3: "de-thi-de-kiem-tra-tieng-anh-lop-3-global-success-c1218.html",
    4: "de-thi-de-kiem-tra-tieng-anh-lop-4-global-success-c1627.html",
    5: "de-thi-de-kiem-tra-tieng-anh-lop-5-global-success-c2008.html",
    # Grades 6-10 + trac-nghiem 11 — VERIFIED live 2026-10-12 (all HTTP 200).
    6: "de-thi-de-kiem-tra-tieng-anh-lop-6-global-success-c1160.html",
    7: "de-thi-de-kiem-tra-tieng-anh-lop-7-global-success-c1182.html",
    8: "de-thi-de-kiem-tra-tieng-anh-lop-8-global-success-c1658.html",
    9: "de-thi-de-kiem-tra-tieng-anh-lop-9-global-success-c2003.html",
    10: "de-thi-de-kiem-tra-tieng-anh-lop-10-global-success-c1192.html",
    11: "v2/tu-luyen-trac-nghiem-tieng-anh-11-global-success-c1445.html",
    # Grade 12 trac-nghiem hub (48 /v2/ skill quizzes) — VERIFIED 200 2026-10-12.
    12: "v2/tu-luyen-trac-nghiem-tieng-anh-12-global-success-c1907.html",
}

# vietjack exam-pack URLs — VERIFIED live 2026-10-12 (all HTTP 200).
# NOTE two slug families: lop-{1,2,3} vs toan-lop-4 vs toan-5 (verified each).
VIETJACK_EXAM_PACKS = {
    1: "https://vietjack.com/de-kiem-tra-lop-1/de-kiem-tra-toan-lop-1.jsp",
    2: "https://vietjack.com/de-kiem-tra-lop-2/de-kiem-tra-toan-lop-2.jsp",
    3: "https://vietjack.com/de-kiem-tra-lop-3/de-kiem-tra-toan-lop-3.jsp",
    4: "https://vietjack.com/de-kiem-tra-toan-lop-4/index.jsp",
    5: "https://vietjack.com/de-kiem-tra-toan-5/index.jsp",
}
# vietjack trac-nghiem co dap an (grade 2-5 share the lop-2 bai-tap hub pattern)
VIETJACK_TRACNGHIEM = {
    2: "https://vietjack.com/de-kiem-tra-lop-2/bai-tap-toan-lop-2.jsp",
    3: "https://vietjack.com/giai-toan-lop-3/bai-tap-trac-nghiem-toan-lop-3-co-dap-an.jsp",
    4: "https://vietjack.com/giai-toan-lop-4/bai-tap-trac-nghiem-toan-lop-4-co-dap-an.jsp",
    5: "https://vietjack.com/giai-toan-lop-5/bai-tap-trac-nghiem-toan-lop-5-co-dap-an.jsp",
    # Upper grades — VERIFIED live 2026-10-12 (all HTTP 200).
    6: "https://vietjack.com/toan-6-ket-noi/bai-tap-trac-nghiem-toan-lop-6.jsp",
    7: "https://vietjack.com/toan-7-kn/trac-nghiem-toan-lop-7-ket-noi.jsp",
    8: "https://vietjack.com/toan-8-kn/trac-nghiem-toan-8-ket-noi.jsp",
    9: "https://vietjack.com/toan-9-kn/trac-nghiem-toan-lop-9.jsp",
    10: "https://vietjack.com/toan-10-kn/trac-nghiem-toan-lop-10-ket-noi.jsp",
    11: "https://vietjack.com/toan-11-kn/trac-nghiem-toan-11-ket-noi.jsp",
    12: "https://vietjack.com/toan-12-kn/trac-nghiem-toan-lop-12.jsp",
}
# vietjack upper-grade exam packs (de-kiem-tra hub per grade).
# VERIFIED live 2026-10-12 (all HTTP 200, homepage harvest).
VIETJACK_EXAM_PACKS_UPPER = {
    6: "https://vietjack.com/de-kiem-tra-lop-6/de-kiem-tra-toan-6.jsp",
    7: "https://vietjack.com/de-kiem-tra-lop-7/de-kiem-tra-toan-7.jsp",
    8: "https://vietjack.com/de-kiem-tra-lop-8/de-kiem-tra-toan-8.jsp",
    9: "https://vietjack.com/de-kiem-tra-lop-9/de-kiem-tra-toan-9.jsp",
    10: "https://vietjack.com/de-kiem-tra-lop-10/de-kiem-tra-toan-10.jsp",
    11: "https://vietjack.com/de-kiem-tra-lop-11/de-kiem-tra-toan-11.jsp",
    12: "https://vietjack.com/de-kiem-tra-lop-12/de-kiem-tra-toan-12.jsp",
}

# loigiaihay alternate listings (2nd textbook set, VERIFIED 200 2026-10-12):
# TV2-c2270 (ket-noi) sits beside c1213; TA2-c1327 (global-success) beside c1217.
LOIGIAIHAY_VN_SLUGS_ALT = {
    2: "de-thi-de-kiem-tra-tieng-viet-lop-2-ket-noi-tri-thuc-c2270.html",
}
LOIGIAIHAY_EN_SLUGS_ALT = {
    2: "de-thi-de-kiem-tra-tieng-anh-lop-2-global-success-c1327.html",
}

# education.com worksheet slugs per grade (verified 200)
EDUCATION_GRADE_SLUGS = {
    1: "first-grade", 2: "second-grade", 3: "third-grade",
    4: "fourth-grade", 5: "fifth-grade",
}

# mathplayground game pages per grade (verified 200)
MATHPLAYGROUND_GRADES = {1, 2, 3}

# tienganh123 lesson pages per grade (verified 200, lop-{1..5}-moi.html)
TIENGANH123_GRADES = {1, 2, 3, 4, 5}


def build_loigiaihay_url(subject: str, grade: int) -> Optional[str]:
    """Exam-listing URL for loigiaihay by subject+grade, or None if not on site."""
    slug = {"math": LOIGIAIHAY_MATH_SLUGS, "vietnamese": LOIGIAIHAY_VN_SLUGS,
            "english": LOIGIAIHAY_EN_SLUGS}.get(subject, {}).get(grade)
    if not slug:
        return None
    return f"https://loigiaihay.com/{slug}"


def build_loigiaihay_alt_url(subject: str, grade: int) -> Optional[str]:
    """Alternate-listing URL (2nd textbook set) for grade 2 TV/EN, else None."""
    slug = {"vietnamese": LOIGIAIHAY_VN_SLUGS_ALT,
            "english": LOIGIAIHAY_EN_SLUGS_ALT}.get(subject, {}).get(grade)
    if not slug:
        return None
    return f"https://loigiaihay.com/{slug}"


def extract_grade_from_url(url: str, default_grade: int = 5) -> int:
    """Extracts grade 1-12 from URL query params, path slugs, or text patterns."""
    if not url:
        return default_grade
    url_lower = url.lower()
    
    # 1. Query parameters: classes=X, grade=X, lop=X, class=X
    param_match = re.search(r'(?:classes|grade|lop|class)=(\d+)', url_lower)
    if param_match:
        try:
            g = int(param_match.group(1))
            if 1 <= g <= 12:
                return g
        except ValueError:
            pass

    # 2. Path patterns: toan-lop-X, toan-X, tieng-anh-X, van-X (detail pages), lop-X, grade-X
    path_match = re.search(r'(?:toan-lop-|toan-|tieng-anh-|van(?:-lop)?-|lop-|grade-)(\d+)', url_lower)
    if path_match:
        try:
            g = int(path_match.group(1))
            if 1 <= g <= 12:
                return g
        except ValueError:
            pass

    # 3. English ordinal words and slugs
    word_map = {
        "1st": 1, "first": 1,
        "2nd": 2, "second": 2,
        "3rd": 3, "third": 3,
        "4th": 4, "fourth": 4,
        "5th": 5, "fifth": 5,
        "6th": 6, "sixth": 6,
        "7th": 7, "seventh": 7,
        "8th": 8, "eighth": 8,
        "9th": 9, "ninth": 9,
        "10th": 10, "tenth": 10,
        "11th": 11, "eleventh": 11,
        "12th": 12, "twelfth": 12
    }
    for word, g_val in word_map.items():
        if f"-{word}-grade" in url_lower or f"/{word}-grade" in url_lower or f"cc-{word}-grade" in url_lower or f"grade-{word}" in url_lower:
            return g_val

    return default_grade



def get_all_grades_source_catalog() -> Dict[str, Any]:
    """Catalog of high-quality verified sources covering all Grades 1 to 12."""
    vn_sources = [
        {"name": "Hành Trang Số (SGK GDPT 1-12)", "url": "https://hanhtrangso.nxbgd.vn/sach-dien-tu", "type": "curriculum", "desc": "Kho SGK & SBT GDPT 2018 trọn bộ từ Lớp 1 đến 12 (NXB Giáo Dục)"},
        {"name": "Lời Giải Hay (Toán, Văn, Anh 1-12)", "url": "https://loigiaihay.com/", "type": "practice", "desc": "Kho đề thi học kỳ & trắc nghiệm chi tiết lớp 1 đến 12 (verified 200)"},
        {"name": "VietJack (Bộ đề thi & Trắc nghiệm 1-12)", "url": "https://vietjack.com/", "type": "practice", "desc": "Hệ thống trắc nghiệm và đề thi 12 khối lớp bám sát GDPT 2018"},
        {"name": "OLM.vn (Học trực tuyến K-12)", "url": "https://olm.vn/", "type": "practice", "desc": "Ngân hàng câu hỏi trắc nghiệm tương tác lớp 1 đến 12 (ĐH Sư Phạm)"},
        {"name": "THCS TOANMATH (Toán 6-9)", "url": "https://thcs.toanmath.com/", "type": "practice", "desc": "Chuyên trang đề thi, kiểm tra định kỳ & trắc nghiệm Toán THCS (verified 200)"},
        {"name": "TOANMATH (Toán 10-12 & Đề thi THPT)", "url": "https://toanmath.com/", "type": "practice", "desc": "Đề thi thử tốt nghiệp THPT, đề khảo sát & chuyên đề Toán 10-12 (verified 200)"},
        {"name": "Tech12h (Trắc nghiệm GDPT 1-12)", "url": "https://tech12h.com/", "type": "practice", "desc": "Đề kiểm tra & trắc nghiệm theo bài học SGK Kết nối tri thức 1-12 (verified 200)"},
        {"name": "VioEdu (Đấu trường Toán học 1-9)", "url": "https://vio.edu.vn/skill-list", "type": "interactive", "desc": "Đấu trường toán học & ngân hàng kỹ năng toán FPT 1-9"},
        {"name": "Trạng Nguyên Toán (Tiểu học 1-5)", "url": "https://tnmath.edu.vn/", "type": "interactive", "desc": "Sân chơi thi Toán trực tuyến Tiểu học thuần Việt"},
        {"name": "VnDoc (Tài liệu & Đề thi 1-12)", "url": "https://vndoc.com/", "type": "worksheet", "desc": "Kho tài liệu, đề thi và phiếu bài tập 12 khối lớp"},
    ]
    en_sources = [
        {"name": "K5 Learning (Worksheets K-6)", "url": "https://www.k5learning.com/free-math-worksheets", "type": "worksheets", "desc": "Phiếu bài tập Math & ELA chuẩn US Common Core"},
        {"name": "IXL Learning Math (K-12)", "url": "https://www.ixl.com/math", "type": "adaptive", "desc": "Hàng ngàn kỹ năng Toán chuẩn US thích ứng từ Grade 1 đến 12"},
        {"name": "Khan Academy (Math & Science K-12)", "url": "https://www.khanacademy.org/math", "type": "video_interactive", "desc": "Hệ thống bài giảng và bài tập chuẩn quốc tế từ Lớp 1 đến 12"},
        {"name": "Common Core Math Sheets", "url": "https://www.commoncoresheets.com", "type": "worksheet", "desc": "Trình tạo đề bài tập tự động chuẩn Common Core K-12"},
        {"name": "Education.com (Math & Reading)", "url": "https://www.education.com/worksheets/", "type": "worksheets", "desc": "Phiếu bài tập Toán & Tiếng Anh chuẩn Quốc tế kèm đáp án"},
        {"name": "Tiếng Anh 123 (Chương trình 1-12)", "url": "https://www.tienganh123.com/", "type": "practice", "desc": "Luyện ngữ pháp và bài tập Tiếng Anh 1-12"},
        {"name": "IOE Olympic Tiếng Anh (1-12)", "url": "https://ioe.vn/", "type": "olympiad", "desc": "Olympic Tiếng Anh trực tuyến trên Internet toàn quốc"},
    ]
    olympiad_sources = [
        {"name": "Kangaroo Math IKMC (Khối 1-12)", "url": "https://kangaroo-math.vn", "type": "olympiad", "desc": "Kỳ thi Toán Quốc tế Kangaroo Ecolier, Benjamin, Cadet, Junior, Student"},
        {"name": "Olympic TIMO & ASMO Song ngữ", "url": "https://codemath.vn/khoa-hoc/timo", "type": "olympiad", "desc": "Đề thi Olympic Toán Quốc tế TIMO & ASMO Song ngữ Anh - Việt"},
        {"name": "Math Playground (Game Toán tư duy)", "url": "https://www.mathplayground.com/", "type": "interactive", "desc": "Trò chơi toán học tương tác & giải toán tư duy logic"},
    ]
    return {
        "grade": "all",
        "description": "Tất cả các khối lớp (Cào tuần tự Khối 1 đến 12)",
        "categories": [
            {"id": "vietnamese", "title": "Chương trình GDPT Việt Nam (Khối 1 - 12)", "sources": vn_sources},
            {"id": "english", "title": "Tiếng Anh & US Common Core (Grade 1 - 12)", "sources": en_sources},
            {"id": "olympiad", "title": "Toán Tư duy & Olympic Song ngữ (Khối 1 - 12)", "sources": olympiad_sources},
        ]
    }


def get_grade_source_urls(grade: Any = 2) -> Dict[str, Any]:
    """Generates standardized, grade-aligned source URLs and platform info for Grades 1 to 12 or all."""
    if str(grade).lower() in ("all", "0", "tat_ca"):
        return get_all_grades_source_catalog()
    grade = max(1, min(12, int(grade or 2)))
    
    # Vietnamese sources
    _lgh_math = build_loigiaihay_url("math", grade) or ""
    _lgh_math_quiz = _lgh_math.startswith("https://loigiaihay.com/v2/")
    _lgh_vn = build_loigiaihay_url("vietnamese", grade) or ""
    # Grade 12 VN is a de-thi listing of ESSAY exams (tu luan) — manual open,
    # not auto-harvestable by the MCQ hunter.
    _lgh_vn_essay = grade == 12
    vn_sources = [
        {
            "name": f"Hành Trang Số (SGK Toán {grade})",
            "url": f"https://hanhtrangso.nxbgd.vn/sach-dien-tu?book_active=0&classes={grade}",
            "type": "curriculum",
            "desc": f"SGK & SBT Toán Lớp {grade} Kết nối tri thức & Cánh diều (Bộ GD&ĐT)"
        },
        {
            "name": f"VioEdu Luyện tập Toán {grade}",
            "url": "https://vio.edu.vn/skill-list",
            "type": "interactive",
            "desc": f"Đấu trường toán học & Khóa luyện Toán Lớp {grade} (FPT)"
        },
        {
            "name": f"Trạng Nguyên Toán {grade}",
            "url": "https://tnmath.edu.vn/",
            "type": "interactive",
            "desc": f"Thi Hương, Thi Hội Toán Lớp {grade} Thuần Việt"
        },
        {
            "name": f"OLM.vn Toán Lớp {grade}",
            "url": f"https://olm.vn/lop-{grade}",
            "type": "practice",
            "desc": f"Hệ thống bài tập Toán Lớp {grade} bám sát chương trình GDPT (ĐH Sư Phạm)"
        },
        {
            "name": f"VnDoc Lớp {grade}",
            "url": "https://vndoc.com/",
            "type": "worksheet",
            "desc": f"Phiếu bài tập theo tuần, đề thi giữa kỳ & học kỳ Lớp {grade} (trang chủ sống, link lop-X lẻ trả 400)"
        },
        {
            "name": f"Lời Giải Hay Toán Lớp {grade}",
            "url": _lgh_math,
            "type": "interactive" if _lgh_math_quiz else "practice",
            "desc": (f"Trắc nghiệm Toán Lớp {grade} — trang quiz JS (mở tay, verified 200)"
                     if _lgh_math_quiz else
                     f"Bài tập trắc nghiệm và lời giải chi tiết Toán Lớp {grade} (verified 200)")
        },
        {
            "name": f"Lời Giải Hay Tiếng Việt Lớp {grade}",
            "url": _lgh_vn,
            "type": "interactive" if _lgh_vn_essay else "practice",
            "desc": (f"Đề thi tự luận Văn Lớp {grade} có lời giải (mở tay, verified 200)"
                     if _lgh_vn_essay else
                     f"Soạn bài & luyện từ câu Tiếng Việt Lớp {grade} (verified 200)")
        },
        {
            "name": f"VietJack Đề thi Toán Lớp {grade}",
            "url": VIETJACK_EXAM_PACKS.get(grade) or VIETJACK_EXAM_PACKS_UPPER.get(grade, ""),
            "type": "practice",
            "desc": f"Bộ đề kiểm tra + trắc nghiệm có đáp án Toán Lớp {grade} (.jsp, verified 200)"
        },
        {
            "name": f"VietJack Trắc nghiệm Toán Lớp {grade}",
            "url": VIETJACK_TRACNGHIEM.get(grade, ""),
            "type": "practice",
            "desc": f"Bài tập trắc nghiệm Toán Lớp {grade} có đáp án chi tiết (verified 200)"
        },
        {
            "name": f"Tech12h Trắc nghiệm GDPT Lớp {grade}",
            "url": "https://tech12h.com/",
            "type": "practice",
            "desc": f"Hệ thống bài tập trắc nghiệm và đề kiểm tra bám sát SGK mới Lớp {grade} (verified 200)"
        },
    ]
    # 2nd textbook-set listings (grade 2 TV/EN alternates)
    _alt_vn = build_loigiaihay_alt_url("vietnamese", grade)
    if _alt_vn:
        vn_sources.append({
            "name": f"Lời Giải Hay Tiếng Việt Lớp {grade} (bộ 2)",
            "url": _alt_vn,
            "type": "practice",
            "desc": f"Đề Tiếng Việt Lớp {grade} bộ sách thứ 2 (verified 200)",
        })
    if grade in LOIGIAIHAY_VN_TRACNGHIEM:
        vn_sources.append({
            "name": f"Lời Giải Hay Trắc nghiệm Văn Lớp {grade}",
            "url": f"https://loigiaihay.com/{LOIGIAIHAY_VN_TRACNGHIEM[grade]}",
            "type": "interactive",
            "desc": f"Trắc nghiệm Văn Lớp {grade} có đáp án + lời giải — trang quiz JS (mở tay, verified 200)",
        })
    if 6 <= grade <= 9:
        vn_sources.append({
            "name": f"THCS TOANMATH Toán Lớp {grade}",
            "url": "https://thcs.toanmath.com/",
            "type": "practice",
            "desc": f"Kho tài liệu trắc nghiệm, đề kiểm tra định kỳ & ôn tập Toán Lớp {grade} THCS (verified 200)",
        })
    elif 10 <= grade <= 12:
        vn_sources.append({
            "name": f"TOANMATH Đề thi & Chuyên đề Toán Lớp {grade}",
            "url": "https://toanmath.com/",
            "type": "practice",
            "desc": f"Đề thi thử tốt nghiệp THPT, đề kiểm tra định kỳ & trắc nghiệm Toán Lớp {grade} THPT (verified 200)",
        })
    # Drop entries with no verified URL (e.g. TV grade 1):
    # a guessed category ID points at the WRONG subject's page.
    vn_sources = [s for s in vn_sources if s.get("url")]

    # English US Common Core & Cambridge sources
    k5_slugs = {
        1: "first-grade-1", 2: "second-grade-2", 3: "third-grade-3",
        4: "fourth-grade-4", 5: "fifth-grade-5", 6: "sixth-grade-6"
    }
    if grade in k5_slugs:
        k5_url = f"https://www.k5learning.com/free-math-worksheets/{k5_slugs[grade]}"
        k5_desc = f"Worksheets Toán Grade {grade} chuẩn US Common Core kèm đáp án"
    else:
        k5_url = "https://www.k5learning.com/free-math-worksheets"
        k5_desc = f"Học liệu Toán Quốc tế US Common Core dành cho học sinh Lớp {grade}"

    khan_slugs = {
        1: "cc-1st-grade-math", 2: "cc-2nd-grade-math", 3: "cc-third-grade-math",
        4: "cc-fourth-grade-math", 5: "cc-fifth-grade-math", 6: "cc-sixth-grade-math",
        7: "cc-seventh-grade-math", 8: "cc-eighth-grade-math", 9: "algebra",
        10: "geometry", 11: "algebra2", 12: "precalculus"
    }
    khan_url = f"https://www.khanacademy.org/math/{khan_slugs.get(grade, 'algebra')}"

    en_sources = [
        {
            "name": f"K5 Learning (Math Grade {grade})",
            "url": k5_url,
            "type": "worksheets",
            "desc": k5_desc
        },
        {
            "name": f"IXL Math Grade {grade}",
            "url": f"https://www.ixl.com/math/grade-{grade}",
            "type": "adaptive",
            "desc": f"Hàng trăm kỹ năng Toán Grade {grade} chuẩn US thích ứng"
        },
        {
            "name": f"Khan Academy (Grade {grade})",
            "url": khan_url,
            "type": "video_interactive",
            "desc": f"Khóa học Toán Lớp {grade} chuẩn Common Core / High School miễn phí"
        },
        {
            "name": "Common Core Math",
            "url": "https://www.commoncoresheets.com",
            "type": "worksheet",
            "desc": f"Trình tạo đề bài tập tự động chuẩn Common Core (Khối {grade})"
        }
    ]
    # New verified EN sources (live 200, 2026-10-11). Tiểu học 1-5 có URL theo khối.
    edu_slug = EDUCATION_GRADE_SLUGS.get(grade)
    if edu_slug:
        en_sources.append({
            "name": f"Education.com Math Grade {grade}",
            "url": f"https://www.education.com/worksheets/{edu_slug}/math/",
            "type": "worksheets",
            "desc": f"Phiếu bài tập Toán Grade {grade} in được kèm đáp án (verified 200)"
        })
        en_sources.append({
            "name": f"Education.com ELA Grade {grade}",
            "url": f"https://www.education.com/worksheets/{edu_slug}/ela/",
            "type": "worksheets",
            "desc": f"Phiếu đọc hiểu & ngữ pháp Tiếng Anh Grade {grade} (verified 200)"
        })
    if grade in MATHPLAYGROUND_GRADES:
        ord_map = {1: "1", 2: "2", 3: "3"}
        en_sources.append({
            "name": f"MathPlayground Grade {grade}",
            "url": f"https://www.mathplayground.com/grade_{ord_map[grade]}_games.html",
            "type": "interactive",
            "desc": f"Game Toán tương tác Grade {grade} (verified 200)"
        })
    if grade in TIENGANH123_GRADES:
        en_sources.append({
            "name": f"Tiếng Anh 123 Lớp {grade}",
            "url": f"https://www.tienganh123.com/lop-{grade}-moi.html",
            "type": "practice",
            "desc": f"Bài tập Tiếng Anh Lớp {grade} thuần Việt kèm lời giải (verified 200)"
        })
    en_sources.append({
        "name": "IOE Olympic Tiếng Anh",
        "url": "https://ioe.vn/",
        "type": "olympiad",
        "desc": "Sân chơi Olympic Tiếng Anh IOE (trang chủ sống; trang con đổi slug nên không deep-link)"
    })
    _alt_en = build_loigiaihay_alt_url("english", grade)
    if _alt_en:
        en_sources.append({
            "name": f"Lời Giải Hay Tiếng Anh Lớp {grade} (bộ 2)",
            "url": _alt_en,
            "type": "practice",
            "desc": f"Đề Tiếng Anh Lớp {grade} bộ sách thứ 2 (verified 200)",
        })
    _lgh_en = build_loigiaihay_url("english", grade)
    if _lgh_en:
        _is_quiz = _lgh_en.startswith("https://loigiaihay.com/v2/")
        en_sources.insert(0, {
            "name": f"Lời Giải Hay Tiếng Anh Lớp {grade}",
            "url": _lgh_en,
            "type": "interactive" if _is_quiz else "practice",
            "desc": (f"Trắc nghiệm Tiếng Anh Lớp {grade} — trang quiz JS (mở tay, verified 200)"
                     if _is_quiz else
                     f"Đề thi + lời giải Tiếng Anh Lớp {grade} (verified 200)"),
        })
    # OLM lop pages — VERIFIED live 200 for grades 1-12 (2026-10-11/12).
    en_sources.append({
        "name": f"OLM Học trực tuyến Lớp {grade}",
        "url": f"https://olm.vn/lop-{grade}",
        "type": "practice",
        "desc": f"Bài luyện tương tác Lớp {grade} trên OLM (verified 200)",
    })

    # Olympic & Logic Bilingual sources
    if grade in [1, 2]:
        ikmc_level = "Ecolier (Khối 1-2)"
        timo_level = f"Primary {grade}"
    elif grade in [3, 4]:
        ikmc_level = "Ecolier (Khối 3-4)"
        timo_level = f"Primary {grade}"
    elif grade in [5, 6]:
        ikmc_level = "Benjamin (Khối 5-6)"
        timo_level = "Primary 5" if grade == 5 else "Secondary 1"
    elif grade in [7, 8]:
        ikmc_level = "Cadet (Khối 7-8)"
        timo_level = f"Secondary {grade-5}"
    elif grade in [9, 10]:
        ikmc_level = "Junior (Khối 9-10)"
        timo_level = "Secondary 4 / Senior"
    else:
        ikmc_level = "Student (Khối 11-12)"
        timo_level = "Senior Secondary"

    olympiad_sources = [
        {
            "name": f"Kangaroo Math IKMC ({ikmc_level})",
            "url": "https://kangaroo-math.vn",
            "type": "olympiad",
            "desc": f"Toán tư duy Quốc tế Kangaroo cấp độ {ikmc_level}"
        },
        {
            "name": f"Olympic TIMO ({timo_level})",
            "url": "https://lmsfermat.edu.vn",
            "type": "olympiad",
            "desc": f"Olympic Toán Quốc tế TIMO cấp độ {timo_level} (Song ngữ Anh - Việt)"
        },
        {
            "name": f"Olympic SASMO & CodeMath (Khối {grade})",
            "url": "https://codemath.vn/khoa-hoc/sasmo",
            "type": "olympiad",
            "desc": f"Toán tư duy Singapore SASMO & Kỳ thi Quốc tế Khối {grade}"
        }
    ]

    return {
        "success": True,
        "grade": grade,
        "categories": [
            {
                "id": "vietnamese",
                "name": f"Toán Lớp {grade} Tiếng Việt (GDPT 2018)",
                "icon": "🇻🇳",
                "sources": vn_sources
            },
            {
                "id": "english",
                "name": f"Toán Lớp {grade} Tiếng Anh (Math Grade {grade})",
                "icon": "🇬🇧",
                "sources": en_sources
            },
            {
                "id": "olympiad",
                "name": f"Toán Olympic & Tư duy Lớp {grade} (Song ngữ)",
                "icon": "🏆",
                "sources": olympiad_sources
            }
        ]
    }
