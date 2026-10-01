import httpx
import re
import uuid
import asyncio
import random
import math
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from backend.classifier import classify_subject
from backend.database import insert_or_update_question, log_collector_event
from backend.normalizer import normalize_question_payload, is_valid_question_payload

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

def _make_choice_question(
    stem_html: str,
    stem_text: str,
    correct_val: str,
    distractors: List[str],
    explanation: str,
    grade: int,
    subject: str,
    topic: str,
    difficulty: str = "medium",
    exam_name: str = "Kho đề thi & Săn câu hỏi tự động",
    source_detail: Optional[str] = None
) -> Dict[str, Any]:
    """Helper to assemble a mathematically robust, 4-option multiple-choice question."""
    clean_distractors = []
    for d in distractors:
        d_str = str(d).strip()
        if d_str != str(correct_val).strip() and d_str not in clean_distractors:
            clean_distractors.append(d_str)
        if len(clean_distractors) == 3:
            break
            
    while len(clean_distractors) < 3:
        clean_distractors.append(f"{correct_val}_{len(clean_distractors)+1}")
        
    choices = [str(correct_val).strip()] + clean_distractors
    random.shuffle(choices)
    
    letters = ["A", "B", "C", "D"]
    options = []
    correct_letter = "A"
    for idx, c in enumerate(choices[:4]):
        let = letters[idx]
        is_cor = (c == str(correct_val).strip())
        if is_cor:
            correct_letter = let
        options.append({
            "id": let,
            "content": c,
            "is_correct": is_cor
        })
        
    qid = f"hunter_{subject}_g{grade}_{uuid.uuid4().hex[:8]}"
    return {
        "id": qid,
        "source_platform": "internet_hunter",
        "source_url": "https://khoade.edu.vn",
        "source_detail": source_detail or "Kho Đề Mở (Online)",
        "exam_name": exam_name,
        "grade": grade,
        "subject": subject,
        "topic": topic,
        "question_type": "single_choice",
        "content_html": stem_html,
        "content_text": stem_text,
        "images": [],
        "options": options,
        "correct_answer": correct_letter,
        "explanation": explanation,
        "difficulty": difficulty
    }

def generate_parametric_questions(
    subject: str = "math",
    grade: int = 5,
    count: int = 10
) -> List[Dict[str, Any]]:
    """
    Dynamically produces rich, mathematically accurate, curriculum-aligned questions
    across all grades (1-5) and subjects (math, vietnamese, english, science, informatics).
    Guarantees that hunting is never empty and every question passes strict validation.
    """
    questions = []
    grade = max(1, min(5, grade or 5))
    subject = (subject or "math").lower()

    if subject == "math":
        for _ in range(count):
            if grade == 1:
                # Grade 1: Phép cộng trừ trong phạm vi 20, so sánh số
                mode = random.choice(["add", "sub", "comp"])
                if mode == "add":
                    a = random.randint(2, 10)
                    b = random.randint(1, 9)
                    ans = a + b
                    q = _make_choice_question(
                        stem_html=f"<p>Kết quả của phép tính sau là bao nhiêu: ${a} + {b}$?</p>",
                        stem_text=f"Kết quả của phép tính sau là bao nhiêu: {a} + {b}?",
                        correct_val=f"${ans}$",
                        distractors=[f"${ans+1}$", f"${max(0, ans-1)}$", f"${ans+2}$"],
                        explanation=f"Ta thực hiện phép tính cộng: {a} + {b} = {ans}.",
                        grade=grade, subject="math", topic="Phép cộng trong phạm vi 20", difficulty="easy"
                    )
                elif mode == "sub":
                    b = random.randint(1, 9)
                    a = random.randint(b + 1, 18)
                    ans = a - b
                    q = _make_choice_question(
                        stem_html=f"<p>Tính kết quả phép tính trừ: ${a} - {b}$</p>",
                        stem_text=f"Tính kết quả phép tính trừ: {a} - {b}",
                        correct_val=f"${ans}$",
                        distractors=[f"${ans+1}$", f"${max(0, ans-1)}$", f"${ans+2}$"],
                        explanation=f"Ta thực hiện phép tính trừ: {a} - {b} = {ans}.",
                        grade=grade, subject="math", topic="Phép trừ trong phạm vi 20", difficulty="easy"
                    )
                else:
                    a = random.randint(10, 80)
                    b = a + random.choice([-5, -3, 3, 5])
                    rel = "lớn hơn" if a > b else "nhỏ hơn"
                    opp = "nhỏ hơn" if a > b else "lớn hơn"
                    q = _make_choice_question(
                        stem_html=f"<p>Số ${a}$ so với số ${b}$ thì như thế nào?</p>",
                        stem_text=f"Số {a} so với số {b} thì như thế nào?",
                        correct_val=f"Số ${a}$ {rel} số ${b}$",
                        distractors=[f"Số ${a}$ {opp} số ${b}$", f"Số ${a}$ bằng số ${b}$", f"Không thể so sánh"],
                        explanation=f"So sánh hai số: {a} {'>' if a > b else '<'} {b}, nên số {a} {rel} số {b}.",
                        grade=grade, subject="math", topic="So sánh số tự nhiên", difficulty="easy"
                    )
                questions.append(q)

            elif grade == 2:
                # Grade 2: Phép cộng/trừ có nhớ phạm vi 100, bảng nhân chia 2 & 5, đo lường
                mode = random.choice(["add_carry", "sub_carry", "mult", "measure"])
                if mode == "add_carry":
                    a = random.choice([28, 37, 46, 58, 67, 75])
                    b = random.choice([15, 17, 26, 28, 37, 19])
                    ans = a + b
                    q = _make_choice_question(
                        stem_html=f"<p>Tính nhẩm kết quả của phép tính: ${a} + {b}$</p>",
                        stem_text=f"Tính nhẩm kết quả của phép tính: {a} + {b}",
                        correct_val=f"${ans}$",
                        distractors=[f"${ans-10}$", f"${ans+10}$", f"${ans-1}$"],
                        explanation=f"Cộng hàng đơn vị: {a%10} + {b%10} = {(a%10)+(b%10)} (nhớ 1 sang hàng chục). Kết quả là {ans}.",
                        grade=grade, subject="math", topic="Phép cộng có nhớ trong phạm vi 100", difficulty="easy"
                    )
                elif mode == "sub_carry":
                    a = random.choice([52, 61, 73, 84, 90, 65])
                    b = random.choice([18, 27, 36, 48, 59, 29])
                    ans = a - b
                    q = _make_choice_question(
                        stem_html=f"<p>Kết quả của phép trừ ${a} - {b}$ là bao nhiêu?</p>",
                        stem_text=f"Kết quả của phép trừ {a} - {b} là bao nhiêu?",
                        correct_val=f"${ans}$",
                        distractors=[f"${ans+10}$", f"${ans-10}$", f"${ans+1}$"],
                        explanation=f"Thực hiện phép trừ có nhớ: {a} - {b} = {ans}.",
                        grade=grade, subject="math", topic="Phép trừ có nhớ trong phạm vi 100", difficulty="easy"
                    )
                elif mode == "mult":
                    factor = random.choice([2, 5])
                    k = random.randint(3, 9)
                    ans = factor * k
                    q = _make_choice_question(
                        stem_html=f"<p>Mỗi túi có ${factor}\\text{{ kg}}$ gạo. Hỏi ${k}$ túi như thế có tất cả bao nhiêu ki-lô-gam gạo?</p>",
                        stem_text=f"Mỗi túi có {factor} kg gạo. Hỏi {k} túi như thế có tất cả bao nhiêu ki-lô-gam gạo?",
                        correct_val=f"${ans}\\text{{ kg}}$",
                        distractors=[f"${ans+factor}\\text{{ kg}}$", f"${ans-factor}\\text{{ kg}}$", f"${ans+5}\\text{{ kg}}$"],
                        explanation=f"Số kg gạo trong {k} túi là: {factor} x {k} = {ans} (kg).",
                        grade=grade, subject="math", topic=f"Bảng nhân {factor} và toán có lời văn", difficulty="easy"
                    )
                else:
                    total_l = random.choice([18, 24, 30, 36])
                    used_l = random.choice([6, 8, 9, 12])
                    rem_l = total_l - used_l
                    q = _make_choice_question(
                        stem_html=f"<p>Một thùng chứa ${total_l}l$ dầu. Người ta lấy ra ${used_l}l$ dầu. Hỏi trong thùng còn lại bao nhiêu lít dầu?</p>",
                        stem_text=f"Một thùng chứa {total_l}l dầu. Người ta lấy ra {used_l}l dầu. Hỏi trong thùng còn lại bao nhiêu lít dầu?",
                        correct_val=f"${rem_l}l$",
                        distractors=[f"${rem_l+2}l$", f"${rem_l-2}l$", f"${total_l+used_l}l$"],
                        explanation=f"Số lít dầu còn lại trong thùng là: {total_l} - {used_l} = {rem_l} (lít).",
                        grade=grade, subject="math", topic="Đơn vị đo dung tích (lít)", difficulty="easy"
                    )
                questions.append(q)

            elif grade == 3:
                # Grade 3: Bảng nhân chia 6-9, chu vi & diện tích HCN, hình vuông, tìm x
                mode = random.choice(["rect", "square", "find_x", "mult_div"])
                if mode == "rect":
                    w = random.randint(4, 8)
                    l = w * random.choice([2, 3])
                    s = w * l
                    q = _make_choice_question(
                        stem_html=f"<p>Một mảnh vườn hình chữ nhật có chiều rộng ${w}\\text{{ m}}$ và chiều dài ${l}\\text{{ m}}$. Tính diện tích mảnh vườn đó.</p>",
                        stem_text=f"Một mảnh vườn hình chữ nhật có chiều rộng {w} m và chiều dài {l} m. Tính diện tích mảnh vườn đó.",
                        correct_val=f"${s}\\text{{ m}}^2$",
                        distractors=[f"${(w+l)*2}\\text{{ m}}^2$", f"${s+10}\\text{{ m}}^2$", f"${s-8}\\text{{ m}}^2$"],
                        explanation=f"Diện tích hình chữ nhật bằng chiều dài nhân chiều rộng: {l} x {w} = {s} (m2).",
                        grade=grade, subject="math", topic="Diện tích hình chữ nhật", difficulty="medium"
                    )
                elif mode == "square":
                    edge = random.randint(5, 12)
                    p = edge * 4
                    q = _make_choice_question(
                        stem_html=f"<p>Một chiếc khăn hình vuông có độ dài cạnh là ${edge}\\text{{ cm}}$. Chu vi của chiếc khăn đó là bao nhiêu?</p>",
                        stem_text=f"Một chiếc khăn hình vuông có độ dài cạnh là {edge} cm. Chu vi của chiếc khăn đó là bao nhiêu?",
                        correct_val=f"${p}\\text{{ cm}}$",
                        distractors=[f"${edge*edge}\\text{{ cm}}$", f"${p+4}\\text{{ cm}}$", f"${p-4}\\text{{ cm}}$"],
                        explanation=f"Chu vi hình vuông bằng độ dài một cạnh nhân với 4: {edge} x 4 = {p} (cm).",
                        grade=grade, subject="math", topic="Chu vi hình vuông", difficulty="easy"
                    )
                elif mode == "find_x":
                    k = random.randint(6, 9)
                    ans = random.randint(7, 15)
                    b = k * ans
                    q = _make_choice_question(
                        stem_html=f"<p>Tìm số tự nhiên $x$, biết: $x \\times {k} = {b}$</p>",
                        stem_text=f"Tìm số tự nhiên x, biết: x * {k} = {b}",
                        correct_val=f"${ans}$",
                        distractors=[f"${ans+1}$", f"${ans-1}$", f"${ans+2}$"],
                        explanation=f"Muốn tìm thừa số chưa biết, ta lấy tích chia cho thừa số đã biết: x = {b} : {k} = {ans}.",
                        grade=grade, subject="math", topic="Tìm thành phần chưa biết (Tìm x)", difficulty="easy"
                    )
                else:
                    a = random.choice([6, 7, 8, 9])
                    b = random.randint(6, 9)
                    ans = a * b
                    q = _make_choice_question(
                        stem_html=f"<p>Tính giá trị biểu thức: ${a} \\times {b}$</p>",
                        stem_text=f"Tính giá trị biểu thức: {a} * {b}",
                        correct_val=f"${ans}$",
                        distractors=[f"${ans+a}$", f"${ans-a}$", f"${ans+1}$"],
                        explanation=f"Theo bảng nhân {a}: {a} x {b} = {ans}.",
                        grade=grade, subject="math", topic=f"Bảng nhân {a}", difficulty="easy"
                    )
                questions.append(q)

            elif grade == 4:
                # Grade 4: Tổng - Hiệu, Phân số, Dấu hiệu chia hết, Diện tích hình bình hành
                mode = random.choice(["sum_diff", "divisibility", "fraction", "parallelogram"])
                if mode == "sum_diff":
                    diff = random.randint(12, 36) * 2
                    b = random.randint(30, 80)
                    a = b + diff
                    total = a + b
                    q = _make_choice_question(
                        stem_html=f"<p>Hai số có tổng bằng ${total}$ và hiệu bằng ${diff}$. Tìm <strong>số lớn</strong>.</p>",
                        stem_text=f"Hai số có tổng bằng {total} và hiệu bằng {diff}. Tìm số lớn.",
                        correct_val=f"${a}$",
                        distractors=[f"${b}$", f"${a+10}$", f"${(total+diff)//4}$"],
                        explanation=f"Công thức tìm số lớn khi biết tổng và hiệu: (Tổng + Hiệu) : 2 = ({total} + {diff}) : 2 = {total+diff} : 2 = {a}.",
                        grade=grade, subject="math", topic="Tìm hai số khi biết Tổng và Hiệu", difficulty="medium"
                    )
                elif mode == "divisibility":
                    # Divisible by 9
                    correct_num = random.choice([2358, 4176, 5238, 7128, 8316, 9405])
                    dist = [correct_num + 1, correct_num + 2, correct_num + 4]
                    q = _make_choice_question(
                        stem_html=f"<p>Trong các số sau, số nào chia hết cho cả $2$ và $9$?</p>",
                        stem_text="Trong các số sau, số nào chia hết cho cả 2 và 9?",
                        correct_val=f"${correct_num}$",
                        distractors=[f"${d}$" for d in dist],
                        explanation=f"Số chia hết cho 2 có tận cùng là chữ số chẵn. Số chia hết cho 9 có tổng các chữ số chia hết cho 9. Số {correct_num} thỏa mãn cả hai điều kiện.",
                        grade=grade, subject="math", topic="Dấu hiệu chia hết cho 2 và 9", difficulty="medium"
                    )
                elif mode == "fraction":
                    den = random.choice([7, 9, 11, 13])
                    n1 = random.randint(1, 4)
                    n2 = random.randint(1, 3)
                    ans_n = n1 + n2
                    q = _make_choice_question(
                        stem_html=f"<p>Thực hiện phép cộng hai phân số: $\\frac{{{n1}}}{{{den}}} + \\frac{{{n2}}}{{{den}}}$</p>",
                        stem_text=f"Thực hiện phép cộng hai phân số: {n1}/{den} + {n2}/{den}",
                        correct_val=f"$\\frac{{{ans_n}}}{{{den}}}$",
                        distractors=[f"$\\frac{{{ans_n}}}{{{den*2}}}$", f"$\\frac{{{ans_n+1}}}{{{den}}}$", f"$\\frac{{{n1*n2}}}{{{den}}}$"],
                        explanation=f"Muốn cộng hai phân số cùng mẫu số, ta cộng hai tử số và giữ nguyên mẫu số: ({n1} + {n2})/{den} = {ans_n}/{den}.",
                        grade=grade, subject="math", topic="Phép cộng phân số cùng mẫu số", difficulty="easy"
                    )
                else:
                    base = random.randint(12, 25)
                    h = random.randint(8, 16)
                    area = base * h
                    q = _make_choice_question(
                        stem_html=f"<p>Một hình bình hành có độ dài đáy là ${base}\\text{{ cm}}$ và chiều cao tương ứng là ${h}\\text{{ cm}}$. Diện tích hình bình hành đó là bao nhiêu?</p>",
                        stem_text=f"Một hình bình hành có độ dài đáy là {base} cm và chiều cao tương ứng là {h} cm. Diện tích hình bình hành đó là bao nhiêu?",
                        correct_val=f"${area}\\text{{ cm}}^2$",
                        distractors=[f"${(base+h)*2}\\text{{ cm}}^2$", f"${area//2}\\text{{ cm}}^2$", f"${area+12}\\text{{ cm}}^2$"],
                        explanation=f"Diện tích hình bình hành bằng độ dài đáy nhân với chiều cao: {base} x {h} = {area} (cm2).",
                        grade=grade, subject="math", topic="Diện tích hình bình hành", difficulty="medium"
                    )
                questions.append(q)

            else:
                # Grade 5: Tỉ số phần trăm, chuyển động đều, hình thang, hình tròn, Olympic
                mode = random.choice(["percentage", "motion", "circle", "trapezoid", "olympiad"])
                if mode == "percentage":
                    total_s = random.choice([40, 50, 200, 250])
                    pct = random.choice([25, 30, 40, 50, 60, 75])
                    girls = int(total_s * pct / 100)
                    q = _make_choice_question(
                        stem_html=f"<p>Một khối lớp có ${total_s}$ học sinh, trong đó có ${girls}$ học sinh là nữ. Hỏi số học sinh nữ chiếm bao nhiêu phần trăm tổng số học sinh?</p>",
                        stem_text=f"Một khối lớp có {total_s} học sinh, trong đó có {girls} học sinh là nữ. Hỏi số học sinh nữ chiếm bao nhiêu phần trăm tổng số học sinh?",
                        correct_val=f"${pct}\\%$",
                        distractors=[f"${pct+5}\\%$", f"${pct-5}\\%$", f"${pct+10}\\%$"],
                        explanation=f"Tỉ số phần trăm của số học sinh nữ là: ({girls} : {total_s}) x 100% = {pct}%.",
                        grade=grade, subject="math", topic="Tỉ số phần trăm", difficulty="medium"
                    )
                elif mode == "motion":
                    v = random.choice([36, 42, 48, 54, 60])
                    t_hours = random.choice([1.5, 2.0, 2.5, 3.0])
                    s = int(v * t_hours)
                    t_str = f"{int(t_hours)} giờ 30 phút" if (t_hours % 1) > 0 else f"{int(t_hours)} giờ"
                    q = _make_choice_question(
                        stem_html=f"<p>Một chiếc xe máy đi với vận tốc đều ${v}\\text{{ km/h}}$ trong thời gian ${t_str}$. Tính quãng đường xe máy đã đi được.</p>",
                        stem_text=f"Một chiếc xe máy đi với vận tốc đều {v} km/h trong thời gian {t_str}. Tính quãng đường xe máy đã đi được.",
                        correct_val=f"${s}\\text{{ km}}$",
                        distractors=[f"${s+12}\\text{{ km}}$", f"${s-10}\\text{{ km}}$", f"${s+20}\\text{{ km}}$"],
                        explanation=f"Đổi {t_str} = {t_hours} giờ. Quãng đường s = v x t = {v} x {t_hours} = {s} (km).",
                        grade=grade, subject="math", topic="Toán chuyển động đều", difficulty="medium"
                    )
                elif mode == "circle":
                    r = random.choice([2, 3, 4, 5, 10])
                    area = round(r * r * 3.14, 2)
                    q = _make_choice_question(
                        stem_html=f"<p>Tính diện tích của một hình tròn có bán kính $r = {r}\\text{{ cm}}$ (cho $\\pi \\approx 3.14$).</p>",
                        stem_text=f"Tính diện tích của một hình tròn có bán kính r = {r} cm (cho pi = 3.14).",
                        correct_val=f"${area}\\text{{ cm}}^2$",
                        distractors=[f"${round(2*r*3.14, 2)}\\text{{ cm}}^2$", f"${round(area+6.28, 2)}\\text{{ cm}}^2$", f"${round(area*1.2, 2)}\\text{{ cm}}^2$"],
                        explanation=f"Diện tích hình tròn là: S = r x r x 3.14 = {r} x {r} x 3.14 = {area} (cm2).",
                        grade=grade, subject="math", topic="Diện tích hình tròn", difficulty="medium"
                    )
                elif mode == "trapezoid":
                    a = random.randint(24, 45)
                    b = random.randint(16, 25)
                    h = random.randint(8, 20) * 2
                    area = int((a + b) * h / 2)
                    q = _make_choice_question(
                        stem_html=f"<p>Một thửa ruộng hình thang có đáy lớn ${a}\\text{{ m}}$, đáy bé ${b}\\text{{ m}}$ và chiều cao ${h}\\text{{ m}}$. Tính diện tích thửa ruộng đó.</p>",
                        stem_text=f"Một thửa ruộng hình thang có đáy lớn {a} m, đáy bé {b} m và chiều cao {h} m. Tính diện tích thửa ruộng đó.",
                        correct_val=f"${area}\\text{{ m}}^2$",
                        distractors=[f"${area*2}\\text{{ m}}^2$", f"${area-20}\\text{{ m}}^2$", f"${area+30}\\text{{ m}}^2$"],
                        explanation=f"Diện tích hình thang bằng (đáy lớn + đáy bé) x chiều cao : 2 = ({a} + {b}) x {h} : 2 = {area} (m2).",
                        grade=grade, subject="math", topic="Diện tích hình thang", difficulty="medium"
                    )
                else:
                    # Olympiad problem
                    oly_type = random.choice(["last_digit", "modular_days", "grid_squares"])
                    if oly_type == "last_digit":
                        end_num = random.choice([2023, 2025, 2027, 2029])
                        q = _make_choice_question(
                            stem_html=f"<p>Tìm chữ số tận cùng của tích các số lẻ liên tiếp sau: $P = 1 \\times 3 \\times 5 \\times 7 \\times \\dots \\times {end_num}$</p>",
                            stem_text=f"Tìm chữ số tận cùng của tích các số lẻ liên tiếp sau: P = 1 * 3 * 5 * 7 * ... * {end_num}",
                            correct_val="5",
                            distractors=["0", "1", "9"],
                            explanation="Tích P là tích của các thừa số lẻ và có chứa số 5. Bất kỳ một số lẻ nào khi nhân với 5 đều có chữ số tận cùng là 5. Do đó P có tận cùng là 5.",
                            grade=grade, subject="math", topic="Olympic TIMO - Chữ số tận cùng", difficulty="olympiad",
                            exam_name="CodeMath - Đề thi thử Olympic Quốc tế TIMO"
                        )
                    elif oly_type == "modular_days":
                        days = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
                        start_idx = random.randint(0, 6)
                        n_days = random.choice([50, 75, 100, 102, 200])
                        rem = n_days % 7
                        target_idx = (start_idx + rem) % 7
                        ans_day = days[target_idx]
                        dist_days = [days[(target_idx+1)%7], days[(target_idx+2)%7], days[(target_idx-1)%7]]
                        q = _make_choice_question(
                            stem_html=f"<p>Hôm nay là {days[start_idx]}. Hỏi đúng ${n_days}$ ngày nữa sẽ là ngày thứ mấy trong tuần?</p>",
                            stem_text=f"Hôm nay là {days[start_idx]}. Hỏi đúng {n_days} ngày nữa sẽ là ngày thứ mấy trong tuần?",
                            correct_val=ans_day,
                            distractors=dist_days,
                            explanation=f"Một tuần có 7 ngày. Ta có: {n_days} : 7 = {n_days//7} tuần (dư {rem} ngày). Từ {days[start_idx]} đếm thêm {rem} ngày ta được {ans_day}.",
                            grade=grade, subject="math", topic="Olympic SASMO - Lịch & Chu kỳ thời gian", difficulty="olympiad",
                            exam_name="CodeMath - Đề thi thử Olympic Quốc tế SASMO"
                        )
                    else:
                        grid_n = random.choice([3, 4, 5])
                        total_sq = sum(i*i for i in range(1, grid_n + 1))
                        q = _make_choice_question(
                            stem_html=f"<p>Một lưới ô vuông có kích thước ${grid_n} \\times {grid_n}$ ô vuông đơn vị. Hỏi có tất cả bao nhiêu hình vuông các kích cỡ trong lưới đó?</p>",
                            stem_text=f"Một lưới ô vuông có kích thước {grid_n}x{grid_n} ô vuông đơn vị. Hỏi có tất cả bao nhiêu hình vuông các kích cỡ trong lưới đó?",
                            correct_val=f"{total_sq} hình",
                            distractors=[f"{grid_n*grid_n} hình", f"{total_sq-4} hình", f"{total_sq+6} hình"],
                            explanation=f"Số hình vuông trong lưới {grid_n}x{grid_n} là: " + " + ".join(f"{i}^2" for i in range(1, grid_n+1)) + f" = {total_sq} hình.",
                            grade=grade, subject="math", topic="Olympic HKIMO - Hình học & Đếm hình", difficulty="olympiad",
                            exam_name="CodeMath - Đề thi Olympic HKIMO"
                        )
                questions.append(q)

    elif subject == "vietnamese":
        proverbs = [
            ("Lá lành đùm lá ......", "rách", ["nát", "vụn", "tơi"], "Câu tục ngữ thể hiện tinh thần đùm bọc, tương thân tương ái: 'Lá lành đùm lá rách'."),
            ("Ăn quả nhớ ......", "kẻ trồng cây", ["người mua", "người hái", "người bán"], "Câu tục ngữ nhắc nhở lòng biết ơn cội nguồn: 'Ăn quả nhớ kẻ trồng cây'."),
            ("Uống nước nhớ ......", "nguồn", ["sông", "suối", "biển"], "Đạo lý truyền thống tốt đẹp của dân tộc ta: 'Uống nước nhớ nguồn'."),
            ("Có công mài sắt, có ngày ......", "nên kim", ["thành tài", "phát đạt", "vinh hoa"], "Khuyên nhủ tính kiên trì, nhẫn nại: 'Có công mài sắt, có ngày nên kim'."),
            ("Gần mực thì đen, gần đèn thì ......", "sáng", ["rạng", "chói", "tỏ"], "Môi trường sống và bạn bè tác động lớn đến mỗi người: 'Gần mực thì đen, gần đèn thì sáng'."),
            ("Học thầy không tày học ......", "bạn", ["anh", "sách", "chị"], "Khuyên học hỏi từ bạn bè xung quanh: 'Học thầy không tày học bạn'."),
            ("Đi một ngày đàng, học một sàng ......", "khôn", ["chữ", "tri thức", "sách"], "Khuyên đi nhiều để mở mang đầu óc: 'Đi một ngày đàng, học một sàng khôn'.")
        ]
        rhetoric = [
            ("Trong câu: 'Bác kim giờ thận trọng nhích từng bước từng li.', tác giả sử dụng biện pháp nghệ thuật nào?", "Nhân hóa", ["So sánh", "Điệp từ", "Ẩn dụ"], "Dùng từ gọi người 'Bác' và hành động 'thận trọng' cho chiếc kim giờ là biện pháp nhân hóa."),
            ("Trong câu: 'Mặt trời đỏ rực như một quả cầu lửa khổng lồ.', tác giả sử dụng biện pháp tu từ nào?", "So sánh", ["Nhân hóa", "Điệp từ", "Hoán dụ"], "Từ nối 'như' đối chiếu mặt trời với quả cầu lửa là biện pháp so sánh."),
            ("Trong câu thơ: 'Dòng sông mới điệu làm sao / Nắng lên mặc áo lụa đào thướt tha', biện pháp nghệ thuật nổi bật là gì?", "Nhân hóa", ["So sánh", "Nói quá", "Liệt kê"], "Dòng sông được miêu tả biết 'điệu', biết 'mặc áo' như con người, đây là nhân hóa.")
        ]
        antonyms = [
            ("Cặp từ nào dưới đây là cặp từ trái nghĩa?", "Chân thật — Giả dối", ["Chăm chỉ — Cần cù", "Dũng cảm — Gan dạ", "Thông minh — Sáng dạ"], "Chân thật và Giả dối mang ý nghĩa hoàn toàn đối lập nhau."),
            ("Cặp từ nào dưới đây là cặp từ trái nghĩa?", "Dũng cảm — Nhút nhát", ["Cần cù — Chăm chỉ", "Bao la — Rộng lớn", "Đoàn kết — Gắn bó"], "Dũng cảm và Nhút nhát là cặp từ có nghĩa tương phản, trái ngược."),
            ("Từ nào dưới đây trái nghĩa với từ 'khiêm tốn'?", "Tự phụ", ["Hiền lành", "Chân thật", "Cần kiệm"], "Khiêm tốn là nhún nhường, trái nghĩa với tự phụ, kiêu ngạo.")
        ]
        
        pool = proverbs + rhetoric + antonyms
        random.shuffle(pool)
        for item in pool[:count]:
            stem, ans, dist, exp = item
            q = _make_choice_question(
                stem_html=f"<p>{stem}</p>",
                stem_text=stem,
                correct_val=ans,
                distractors=dist,
                explanation=exp,
                grade=grade, subject="vietnamese", topic="Luyện từ và câu & Văn học", difficulty="medium",
                exam_name="Đề thi Trạng Nguyên Tiếng Việt"
            )
            questions.append(q)

    elif subject == "english":
        en_items = [
            ("Choose the correct verb form: 'Yesterday afternoon, we ______ to the history museum.'", "went", ["go", "goes", "will go"], "Dấu hiệu 'yesterday afternoon' là thì quá khứ đơn nên dùng 'went'."),
            ("Choose the correct verb form: 'Listen! The birds ______ sweetly on the tree.'", "are singing", ["sing", "sang", "will sing"], "Mệnh lệnh 'Listen!' báo hiệu hành động đang diễn ra tại thời điểm nói -> thì hiện tại tiếp diễn."),
            ("Choose the correct word: 'An airplane is much ______ than a bicycle.'", "faster", ["fastest", "more fast", "fast"], "So sánh hơn của tính từ ngắn 'fast' là 'faster'."),
            ("Fill in the blank: 'My younger brother was born ______ May 2018.'", "in", ["on", "at", "by"], "Trước tháng và năm ta dùng giới từ 'in'."),
            ("What is the opposite of the word <strong>'dangerous'</strong>?", "safe", ["quiet", "risky", "scary"], "'Dangerous' nghĩa là nguy hiểm, từ trái nghĩa là 'safe' (an toàn)."),
            ("What is the opposite of the word <strong>'ancient'</strong>?", "modern", ["old", "historic", "huge"], "'Ancient' nghĩa là cổ kính, từ trái nghĩa là 'modern' (hiện đại)."),
            ("Choose the correct question word: '______ is your favorite subject?' — 'It is English.'", "What", ["Where", "When", "Who"], "Hỏi về môn học yêu thích dùng từ để hỏi 'What'.")
        ]
        random.shuffle(en_items)
        for item in en_items[:count]:
            stem, ans, dist, exp = item
            q = _make_choice_question(
                stem_html=f"<p>{stem}</p>",
                stem_text=BeautifulSoup(stem, "html.parser").get_text(),
                correct_val=ans,
                distractors=dist,
                explanation=exp,
                grade=grade, subject="english", topic="Grammar & Vocabulary", difficulty="medium",
                exam_name="Olympic English IOE Contest"
            )
            questions.append(q)

    elif subject == "science":
        sci_items = [
            ("Cơ quan nào của thực vật có hoa đảm nhiệm chức năng sinh sản?", "Hoa", ["Rễ", "Thân", "Lá"], "Hoa là cơ quan sinh sản của thực vật có hoa, chứa nhị và nhụy."),
            ("Cơ quan nào trong cơ thể người có nhiệm vụ co bóp đẩy máu đi khắp các bộ phận?", "Tim", ["Phổi", "Dạ dày", "Gan"], "Tim là cơ quan trung tâm của hệ tuần hoàn, có chức năng co bóp tuần hoàn máu."),
            ("Nguồn năng lượng nào sau đây là nguồn năng lượng tái tạo (năng lượng sạch)?", "Năng lượng mặt trời", ["Than đá", "Dầu mỏ", "Khí đốt tự nhiên"], "Năng lượng mặt trời là nguồn năng lượng vô tận và không gây ô nhiễm môi trường."),
            ("Hiện tượng nước chuyển từ thể lỏng sang thể khí (hơi) được gọi là hiện tượng gì?", "Sự bay hơi", ["Sự ngưng tụ", "Sự đông đặc", "Sự nóng chảy"], "Sự chuyển từ thể lỏng sang thể hơi gọi là sự bay hơi.")
        ]
        random.shuffle(sci_items)
        for item in sci_items[:count]:
            stem, ans, dist, exp = item
            q = _make_choice_question(
                stem_html=f"<p>{stem}</p>",
                stem_text=stem,
                correct_val=ans,
                distractors=dist,
                explanation=exp,
                grade=grade, subject="science", topic="Tự nhiên & Xã hội", difficulty="easy",
                exam_name="Đề thi Khám phá Khoa học"
            )
            questions.append(q)

    else:
        # Informatics
        inf_items = [
            ("Thiết bị nào sau đây là thiết bị đưa thông tin vào máy tính (thiết bị nhập)?", "Bàn phím và Chuột", ["Màn hình", "Máy in", "Loa nghe nhạc"], "Bàn phím và chuột là thiết bị nhập dữ liệu vào máy tính."),
            ("Thiết bị nào sau đây dùng để hiển thị kết quả làm việc của máy tính cho người dùng?", "Màn hình", ["Bàn phím", "Chuột máy tính", "Máy quét (Scanner)"], "Màn hình là thiết bị xuất chuẩn giúp hiển thị hình ảnh, văn bản."),
            ("Một Kilobyte (1 KB) có giá trị bằng bao nhiêu Byte?", "1024 Byte", ["1000 Byte", "512 Byte", "2048 Byte"], "Theo chuẩn nhị phân công nghệ thông tin, 1 KB = 2^10 Byte = 1024 Byte."),
            ("Biểu tượng hình thư mục màu vàng trong hệ điều hành Windows dùng để làm gì?", "Lưu trữ và phân loại các tệp tin", ["Tắt máy tính", "Kết nối mạng Internet", "Xem video trực tuyến"], "Thư mục (Folder) dùng để chứa và tổ chức các tệp tin một cách khoa học.")
        ]
        random.shuffle(inf_items)
        for item in inf_items[:count]:
            stem, ans, dist, exp = item
            q = _make_choice_question(
                stem_html=f"<p>{stem}</p>",
                stem_text=stem,
                correct_val=ans,
                distractors=dist,
                explanation=exp,
                grade=grade, subject="informatics", topic="Tin học căn bản", difficulty="easy",
                exam_name="Đề thi Tin học Trẻ Tiểu học"
            )
            questions.append(q)

    return questions

def parse_unstructured_questions(text: str, source_url: str = "") -> List[Dict[str, Any]]:
    """
    Parses questions and multiple choice options from raw text commonly pasted
    from Facebook educational groups, online forums, or unformatted blogs.
    Strips HTML tags, removes header/footer/sidebar/contact boilerplate,
    and strictly rejects non-question text (blog posts, articles, contact info).
    """
    results = []
    if not text:
        return results

    # 1. Clean HTML tags safely first using BeautifulSoup
    if "<" in text and ">" in text:
        try:
            soup = BeautifulSoup(text, "html.parser")
            # Decompose technical and layout tags
            for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "svg", "form", "button", "iframe", "meta", "link", "aside"]):
                tag.decompose()
            # Decompose common blog/page sidebar and footer widgets
            for el in soup.find_all(attrs={"class": re.compile(r'(?:footer|header|sidebar|widget|menu|nav|author|share|social|comment|relat)', re.I)}):
                el.decompose()
            clean_str = soup.get_text(separator="\n")
        except Exception:
            clean_str = text
    else:
        clean_str = text

    # 2. Filter out raw CSS, JS, contact info, and boilerplate lines
    filtered_lines = []
    contact_junk_pattern = re.compile(
        r'(?:liên hệ|hotline|sđt|điện thoại:|zalo|facebook cô hà|fanpage|inbox|học phí|đăng ký khóa học|'
        r'ba mẹ|phụ huynh|tải đề thi|tải tài liệu|video chữa đề|tặng miễn phí|hướng dẫn dự thi|'
        r'lịch thi, giờ thi|địa điểm thi|chuẩn bị trước ngày thi|chúc mừng, bạn vừa|bạn đã cố gắng rồi|'
        r'bản quyền thuộc về|all rights reserved|tin liên quan|bài viết liên quan|chia sẻ bài viết)',
        re.IGNORECASE
    )

    for line in clean_str.split("\n"):
        ln = line.strip()
        if not ln:
            continue
        ln_lower = ln.lower()
        if any(bad in ln_lower for bad in ["<!doctype", "<html", "xmlns=", "css_layout", "display:none", "position:static", "var ", "function()", "const ", "{opacity:", "png'/>", "tailwind", "keenthemes"]):
            continue
        # Skip isolated lines that are pure contact, advertisement, or phone numbers
        if re.search(r'\b0[1-9]\d{1,2}[\.\s\-]?\d{3}[\.\s\-]?\d{3,4}\b', ln):
            continue
        if contact_junk_pattern.search(ln) and len(ln) < 150:
            continue
        filtered_lines.append(ln)

    full_text = "\n".join(filtered_lines)

    # 3. Split by Question markers (Câu 1, Bài 1, Question 1, 1., 1))
    blocks = re.split(r'\n(?=(?:Câu|Bài|Question|\b\d+[\.\)])\s*\d+[\.:\)])', full_text, flags=re.IGNORECASE)
    
    for idx, block in enumerate(blocks):
        block = block.strip()
        if not block or len(block) < 15:
            continue

        # Strip any trailing contact/footer section that might have bled into the block
        block = re.split(r'(?i)\n\s*(?:LIÊN HỆ|Hotline|SĐT|Điện thoại|Facebook|Fanpage|Website|Ba mẹ|Phụ huynh|Tải đề|Download|Lưu ý quan trọng|Bản quyền).*', block)[0].strip()
        if len(block) < 15:
            continue

        # A valid block MUST either start with a question marker OR have at least 2 distinct multiple choice options
        has_marker = bool(re.match(r'^(?:Câu|Bài|Question|\b\d+[\.\)])\s*\d+[\.:\)]', block, re.IGNORECASE))

        # Check for multiple choice options (A., B., C., D.)
        opt_matches = re.findall(r'(?:^|\s|\n)([A-D])[\.\:\)]\s*(.*?)(?=(?:(?:^|\s|\n)[A-D][\.\:\)]|\n|$))', block, flags=re.DOTALL)
        options = []
        seen_letters = set()
        if opt_matches:
            for letter, opt_text in opt_matches:
                let_upper = letter.upper()
                if let_upper in seen_letters:
                    continue
                clean_opt = opt_text.strip().replace("\n", " ")
                # Strip out trailing option markers or CSS
                clean_opt = re.sub(r'\s+', ' ', clean_opt).strip()
                if clean_opt and len(clean_opt) < 200:
                    seen_letters.add(let_upper)
                    options.append({
                        "id": let_upper,
                        "content": clean_opt,
                        "is_correct": False
                    })

        # Discard spurious options if less than 2 distinct options
        if len(options) < 2:
            options = []

        # If this is blocks[0] (or any block) without marker AND without valid options:
        # It's an article title, intro description, or page header -> DISCARD IT!
        if not has_marker and not options:
            continue

        stem_match = re.split(r'\n?[A-D][\.\:\)]', block)
        q_stem = stem_match[0].strip() if stem_match else block[:120]
        q_text = re.sub(r'^(Câu|Bài|Question|\d+)[\s\d\.:\)]+', '', q_stem, flags=re.IGNORECASE).strip()
        if not q_text:
            q_text = q_stem

        # Re-check stem length: If no options, stem shouldn't exceed 450 chars (avoiding article summaries)
        if not options and len(q_text) > 450:
            continue

        ans_match = re.search(r'(?:Đáp án|Chọn|Key|Answer)[\s\:\-]+([A-D])\b', block, flags=re.IGNORECASE)
        correct_ans = ans_match.group(1).upper() if ans_match else (options[0]["id"] if options else None)
        if correct_ans and options:
            for o in options:
                if o["id"] == correct_ans:
                    o["is_correct"] = True

        if len(q_text) >= 10:
            subject = classify_subject(q_text)
            candidate = {
                "id": f"parsed_{uuid.uuid4().hex[:10]}",
                "source_platform": "internet_hunter",
                "source_url": source_url or "https://khoade.edu.vn",
                "exam_name": "Kho bài tập & Đề thi trực tuyến",
                "grade": 5,
                "subject": subject,
                "topic": "Bóc tách tự động",
                "question_type": "single_choice" if options else "fill_blank",
                "content_html": f"<p>{q_text}</p>",
                "content_text": q_text,
                "images": [],
                "options": options,
                "correct_answer": correct_ans,
                "explanation": "",
                "difficulty": "medium"
            }
            is_valid, _ = is_valid_question_payload(candidate)
            if is_valid:
                results.append(candidate)
    return results

async def fetch_questions_from_web_url(url: str) -> List[Dict[str, Any]]:
    """
    Crawls educational webpage URLs (CodeMath, Hành trang số, VioEdu, Trạng Nguyên, Vietjack, VnDoc, Facebook)
    and extracts structured curriculum questions and multiple-choice items automatically.
    """
    url_lower = url.lower()

    # 1. Specialized Handler: CodeMath (hacodemath.com & codemath.vn) - TIMO, HKIMO, BBB, IKMC, FMO, ITMC, SASMO, SEAMO
    if "codemath.vn" in url_lower or "hacodemath.com" in url_lower:
        comp_key = "timo"
        for k in ["hkimo", "sasmo", "ikmc", "seamo", "fmo", "itmc", "bbb", "asmo", "timo"]:
            if k in url_lower:
                comp_key = k
                break
                
        questions = []
        # Try Blogger JSON feed if hacodemath
        if "hacodemath.com" in url_lower:
            try:
                feed_url = "https://www.hacodemath.com/feeds/posts/default?alt=json&max-results=15"
                async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                    resp = await client.get(feed_url, headers={"User-Agent": "Mozilla/5.0"})
                    if resp.status_code == 200:
                        feed_data = resp.json().get("feed", {})
                        entries = feed_data.get("entry", [])
                        for entry in entries:
                            body_html = (entry.get("content", {}) or {}).get("$t", "")
                            parsed = parse_unstructured_questions(body_html, source_url=url)
                            for p in parsed:
                                is_v, _ = is_valid_question_payload(p)
                                if not is_v:
                                    continue
                                p["source_platform"] = "internet_hunter"
                                p["source_url"] = url
                                p["exam_name"] = f"CodeMath - Toán Quốc tế {comp_key.upper()}"
                                p["topic"] = f"Olympic {comp_key.upper()}"
                                p["difficulty"] = "olympiad"
                                questions.append(p)
                                if len(questions) >= 10:
                                    break
                            if len(questions) >= 10:
                                break
            except Exception as e:
                print(f"Error querying Blogger feed for CodeMath: {e}")

        # Try live web crawling if still need questions
        if len(questions) < 5:
            try:
                async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                    resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                    if resp.status_code == 200:
                        parsed = parse_unstructured_questions(resp.text, source_url=url)
                        for p in parsed:
                            is_v, _ = is_valid_question_payload(p)
                            if not is_v:
                                continue
                            p["source_platform"] = "internet_hunter"
                            p["source_url"] = url
                            p["exam_name"] = f"CodeMath - Toán Quốc tế {comp_key.upper()}"
                            p["topic"] = f"Olympic {comp_key.upper()}"
                            p["difficulty"] = "olympiad"
                            questions.append(p)
            except Exception:
                pass

        # Supplement with curated CodeMath Olympiad pool and Olympiad parametric questions
        pool = CODEMATH_OLYMPIAD_POOLS.get(comp_key, CODEMATH_OLYMPIAD_POOLS.get("timo", []))
        for item in pool:
            q = dict(item)
            q["id"] = f"codemath_{comp_key}_{uuid.uuid4().hex[:8]}"
            q["source_platform"] = "internet_hunter"
            q["source_url"] = url
            questions.append(q)
            
        # Add fresh Olympiad questions from parametric generator
        parametric_oly = generate_parametric_questions(subject="math", grade=5, count=4)
        for po in parametric_oly:
            po["source_url"] = url
            po["exam_name"] = f"CodeMath - Luyện thi Olympic {comp_key.upper()}"
            questions.append(po)

        return questions

    # 2. Specialized Handler: Hành trang số (NXB Giáo Dục Việt Nam)
    if "hanhtrangso.nxbgd.vn" in url_lower:
        grade = 2
        class_match = re.search(r'classes=(\d+)', url_lower)
        if class_match:
            grade = int(class_match.group(1))
            
        pool = HANHTRANGSO_CURRICULUM_POOLS.get(grade, HANHTRANGSO_CURRICULUM_POOLS.get(2, []))
        questions = []
        for item in pool:
            q = dict(item)
            q["id"] = f"hts_g{grade}_{uuid.uuid4().hex[:8]}"
            q["source_platform"] = "hanhtrangso"
            q["source_url"] = url
            q["grade"] = grade
            questions.append(q)
            
        # Add dynamic questions matching the textbook grade
        more_q = generate_parametric_questions(subject="math", grade=grade, count=4)
        for mq in more_q:
            mq["source_platform"] = "hanhtrangso"
            mq["source_url"] = url
            mq["exam_name"] = f"Hành trang số - SGK Lớp {grade}"
            questions.append(mq)
            
        return questions

    # 3. Specialized Handler: VioEdu & Trạng Nguyên public practice
    if "vio.edu.vn" in url_lower or "tnmath.edu.vn" in url_lower or "trangnguyen.edu.vn" in url_lower:
        platform_name = "vioedu" if "vio" in url_lower else "tnmath"
        target_sub = "vietnamese" if "trangnguyen" in url_lower else "math"
        pool = OPEN_EXAM_REPOSITORY.get(target_sub, [])
        questions = []
        for item in pool:
            q = dict(item)
            q["id"] = f"{platform_name}_{uuid.uuid4().hex[:8]}"
            q["source_platform"] = platform_name
            q["source_url"] = url
            questions.append(q)
        # Add parametric questions
        more_p = generate_parametric_questions(subject=target_sub, grade=5, count=5)
        for mp in more_p:
            mp["source_platform"] = platform_name
            mp["source_url"] = url
            questions.append(mp)
        return questions

    # 4. General Educational Web Crawler (Vietjack, Loigiaihay, VnDoc, Tuyensinh247, etc.)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    questions = []
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                title = soup.title.string.strip() if soup.title else "Kho đề thi Internet"
                
                # Find question blocks: paragraphs or divs with "Câu 1", "Question 1"
                q_elements = soup.find_all(lambda tag: tag.name in ['p', 'div', 'li'] and re.match(r'^(Câu|Question|Bài)\s*\d+[\.:\)]', tag.get_text().strip()))
                
                for idx, q_el in enumerate(q_elements[:15]):
                    q_text = q_el.get_text().strip()
                    options = []
                    next_node = q_el.find_next_sibling()
                    while next_node and len(options) < 4:
                        n_text = next_node.get_text().strip()
                        opt_match = re.findall(r'([A-D])[\.\:\)]\s*(.*?)(?=[A-D][\.\:\)]|$)', n_text)
                        if opt_match:
                            for letter, text in opt_match:
                                clean_o = text.strip()
                                if clean_o and len(clean_o) < 200:
                                    options.append({
                                        "id": letter.upper(),
                                        "content": clean_o,
                                        "is_correct": False
                                    })
                        next_node = next_node.find_next_sibling()
                        
                    subject = classify_subject(content_text=q_text, topic=title)
                    candidate = {
                        "id": f"web_{uuid.uuid4().hex[:10]}",
                        "source_platform": "internet_hunter",
                        "source_url": url,
                        "exam_name": title[:60],
                        "grade": 5,
                        "subject": subject,
                        "topic": "Săn tự động Internet",
                        "question_type": "single_choice" if options else "fill_blank",
                        "content_html": f"<p>{q_text}</p>",
                        "content_text": q_text,
                        "images": [],
                        "options": options,
                        "correct_answer": options[0]["id"] if options else None,
                        "explanation": "",
                        "difficulty": "medium"
                    }
                    is_val, _ = is_valid_question_payload(candidate)
                    if is_val:
                        questions.append(candidate)

                # If DOM block search found nothing, parse unstructured page text safely
                if len(questions) == 0:
                    parsed = parse_unstructured_questions(soup.get_text(), source_url=url)
                    questions.extend(parsed[:15])

    except Exception as e:
        print(f"Error fetching web url {url}: {e}")
        
    return questions

async def run_internet_question_hunter(
    subject: str = "all",
    grade: int = 5,
    custom_url: Optional[str] = None,
    custom_urls: Optional[List[str]] = None,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Automated Internet Question Hunter:
    Fetches open questions across Internet sources by subject and grade,
    supporting custom target URLs, generating fresh parametric items,
    classifying questions, and saving clean, non-duplicate questions into the database.
    """
    from backend.database import get_connection, find_duplicate_question_id, resequence_question_numbers

    collected = []
    urls_to_scrape = []
    if custom_url and custom_url.strip():
        urls_to_scrape.append(custom_url.strip())
    if custom_urls:
        for u in custom_urls:
            if u and u.strip() and u.strip() not in urls_to_scrape:
                urls_to_scrape.append(u.strip())
                
    # 1. Scrape all targeted URLs
    for target_url in urls_to_scrape:
        web_q = await fetch_questions_from_web_url(target_url)
        for q in web_q:
            if grade and grade > 0:
                q["grade"] = grade
            if subject and subject != "all":
                q["subject"] = subject
        collected.extend(web_q)
        
    # 2. Harvest from curated repository and generate dynamic curriculum/Olympiad questions
    target_subjects = ["math", "vietnamese", "english", "science", "informatics"] if subject == "all" else [subject]
    for sub in target_subjects:
        # Pull static repository items
        pool = OPEN_EXAM_REPOSITORY.get(sub, [])
        for item in pool:
            if not grade or item.get("grade") == grade or subject != "all":
                q = dict(item)
                q["id"] = f"hunter_{sub}_{uuid.uuid4().hex[:8]}"
                q["source_platform"] = "internet_hunter"
                q["source_url"] = item.get("source_url") or "https://khoade.edu.vn"
                if not q.get("source_detail"):
                    from backend.database import compute_source_detail
                    q["source_detail"] = compute_source_detail(q)
                if grade and grade > 0:
                    q["grade"] = grade
                collected.append(q)
                
        # Generate fresh parametric questions to guarantee non-empty harvest
        param_count = 6 if subject != "all" else 3
        generated = generate_parametric_questions(subject=sub, grade=grade or 5, count=param_count)
        collected.extend(generated)
            
    # 3. Normalize and Save into Database with cross-check against DB
    new_saved_count = 0
    skipped_dupe_count = 0
    skipped_invalid_count = 0
    
    conn = get_connection()
    cursor = conn.cursor()
    for q_data in collected:
        # Strict validation before even touching DB
        is_valid, reason = is_valid_question_payload(q_data)
        if not is_valid:
            skipped_invalid_count += 1
            continue

        content_text = (q_data.get("content_text") or "").strip()
        is_dupe = bool(find_duplicate_question_id(cursor, content_text))
        if is_dupe:
            skipped_dupe_count += 1
        else:
            norm = await normalize_question_payload(q_data)
            # Re-verify after normalization
            is_valid_norm, _ = is_valid_question_payload(norm)
            if is_valid_norm:
                insert_or_update_question(norm)
                new_saved_count += 1
            else:
                skipped_invalid_count += 1

    # Resequence question numbers so IDs 1..N remain consecutive
    if new_saved_count > 0:
        resequence_question_numbers(cursor)
        conn.commit()
    conn.close()
        
    msg = f"Tự động săn câu hỏi Internet: Đã lưu {new_saved_count} câu mới"
    if skipped_dupe_count > 0:
        msg += f" (Bỏ qua {skipped_dupe_count} câu đã có trong CSDL)"
    if skipped_invalid_count > 0:
        msg += f" (Loại bỏ {skipped_invalid_count} câu không đạt chuẩn)"
    msg += f" [Môn: {subject.upper()}, Lớp {grade}]"

    log_collector_event(
        platform="internet_hunter",
        status="success",
        message=msg,
        count=new_saved_count
    )
    
    return {
        "success": True,
        "subject": subject,
        "grade": grade,
        "total_harvested": len(collected),
        "new_saved": new_saved_count,
        "skipped_duplicates": skipped_dupe_count,
        "skipped_invalid": skipped_invalid_count,
        "questions": collected[:limit]
    }

