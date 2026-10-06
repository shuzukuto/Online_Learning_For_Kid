from __future__ import annotations
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, AliasChoices, model_validator, ConfigDict
from datetime import datetime

class OptionItem(BaseModel):
    id: str  # "A", "B", "C", "D" or identifier
    content: str
    is_correct: bool = False

class QuestionCreate(BaseModel):
    id: Optional[str] = None
    q_number: Optional[int] = None
    source_platform: str = "manual"  # vioedu, tnmath, timo, hkimo, asmo, manual
    source_detail: Optional[str] = None
    source_url: Optional[str] = None
    exam_name: Optional[str] = None
    year: Optional[int] = None
    grade: Optional[int] = 5
    subject: Optional[str] = "math"
    topic: Optional[str] = None
    question_type: str = "single_choice"  # single_choice, multiple_choice, fill_blank, matching, essay
    content_html: str
    content_text: Optional[str] = None
    raw_ocr_content: Optional[str] = None
    images: List[str] = Field(default_factory=list)
    options: List[OptionItem] = Field(default_factory=list)
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    difficulty: Optional[str] = "medium"  # easy, medium, hard, olympiad
    created_at: Optional[str] = None

class QuestionUpdate(BaseModel):
    q_number: Optional[int] = None
    source_platform: Optional[str] = None
    source_detail: Optional[str] = None
    source_url: Optional[str] = None
    exam_name: Optional[str] = None
    year: Optional[int] = None
    grade: Optional[int] = None
    subject: Optional[str] = None
    topic: Optional[str] = None
    question_type: Optional[str] = None
    content_html: Optional[str] = None
    content_text: Optional[str] = None
    raw_ocr_content: Optional[str] = None
    images: Optional[List[str]] = None
    options: Optional[List[OptionItem]] = None
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    difficulty: Optional[str] = None

class QuestionResponse(QuestionCreate):
    id: str
    q_number: Optional[int] = None
    source_detail: Optional[str] = None
    created_at: str
    updated_at: str

class BulkQuestionCreate(BaseModel):
    questions: List[QuestionCreate]

class ExamCreate(BaseModel):
    title: str
    grade: Optional[int] = 5
    duration_minutes: int = 45
    header_info: Optional[str] = "BỘ GIÁO DỤC VÀ ĐÀO TẠO - ĐỀ THI KHẢO SÁT CHẤT LƯỢNG"
    notes: Optional[str] = "Học sinh không được sử dụng máy tính bỏ túi."
    question_ids: List[str] = Field(default_factory=list)

class ExamResponse(BaseModel):
    id: str
    title: str
    grade: Optional[int] = 5
    duration_minutes: int = 45
    header_info: Optional[str] = None
    notes: Optional[str] = None
    question_ids: List[str] = Field(default_factory=list)
    created_at: str
    questions: Optional[List[QuestionResponse]] = None

class ScrapeRequest(BaseModel):
    platform: str  # vioedu, tnmath
    action: str  # login, fetch_rounds, fetch_questions
    username: Optional[str] = None
    password: Optional[str] = None
    token: Optional[str] = None
    round_id: Optional[str] = None
    grade: Optional[int] = 5

class AutoExamGenerateRequest(BaseModel):
    subject: str = "math"
    grade: int = 5
    total_questions: int = 20
    easy_count: int = 8
    medium_count: int = 8
    hard_count: int = 4
    topic: Optional[str] = None
    title: Optional[str] = None

class CleanDuplicatesRequest(BaseModel):
    action: str = "keep_oldest"  # "keep_oldest", "keep_newest", "delete_ids"
    delete_ids: Optional[List[str]] = None


# ----------------- Interactive Practice Arena Models -----------------

class PracticeAnswerSubmission(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    question_id: str
    selected_answer: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("selected_answer", "selected_option", "user_answer")
    )  # "A", "B", "C", "D" or text
    time_spent_seconds: Optional[int] = 0

    @model_validator(mode="before")
    @classmethod
    def unify_answer_key(cls, data: Any) -> Any:
        if isinstance(data, dict):
            ans = data.get("selected_answer")
            if ans is None:
                ans = data.get("selected_option")
            if ans is None:
                ans = data.get("user_answer")
            if ans is not None:
                data["selected_answer"] = str(ans).strip()
        return data

class PracticeSubmitRequest(BaseModel):
    exam_id: Optional[str] = None
    exam_title: str = "Bài luyện tập trực tuyến"
    subject: str = "math"
    grade: int = 5
    duration_seconds: int = 1800  # Allowed time (seconds)
    time_spent_seconds: int = 0   # Actual time spent
    answers: List[PracticeAnswerSubmission]

class PracticeHistoryResponse(BaseModel):
    id: str
    exam_id: Optional[str] = None
    exam_title: str
    subject: str
    grade: int
    total_questions: int
    correct_count: int
    wrong_count: int
    skipped_count: int
    score: float
    max_score: float
    score_100: Optional[float] = None
    duration_seconds: int
    time_spent_seconds: int
    ranking: str
    created_at: str
    answers_detail: Optional[List[Dict[str, Any]]] = None

class SubjectMastery(BaseModel):
    subject: str
    subject_label: str
    attempts: int
    total_questions: int
    correct_count: int
    accuracy_rate: float
    average_score: float

class BadgeItem(BaseModel):
    id: str
    title: str
    description: str
    icon: str
    category: str
    unlocked: bool
    unlocked_at: Optional[str] = None
    progress: Optional[str] = None

class PracticeAnalyticsResponse(BaseModel):
    total_attempts: int
    total_questions_answered: int
    total_correct: int
    overall_accuracy: float
    average_score: float
    highest_score: float
    trending_scores: List[Dict[str, Any]]
    subject_mastery: List[SubjectMastery]
    recent_history: List[PracticeHistoryResponse]
    badges: List[BadgeItem]

class BulkDeleteRequest(BaseModel):
    question_ids: List[str] = Field(..., description="Danh sách các UUID/ID câu hỏi cần xóa")

BulkDeleteQuestionsRequest = BulkDeleteRequest

class BulkUpdateGradeRequest(BaseModel):
    question_ids: List[str] = Field(..., description="Danh sách các UUID/ID câu hỏi cần đổi khối lớp")
    grade: Any = Field(..., description="Khối lớp mới (chỉ từ 1 đến 12 hoặc 'Lớp 1'-'Lớp 12')")

    @model_validator(mode="after")
    def validate_grade_num(self):
        import re
        val = self.grade
        if isinstance(val, bool):
            raise ValueError("Khối lớp không được là giá trị boolean")
        if isinstance(val, (int, float)):
            if isinstance(val, float) and not val.is_integer():
                raise ValueError("Khối lớp phải là số nguyên")
            num = int(val)
            if 1 <= num <= 12:
                self.grade = num
                return self
            raise ValueError(f"Khối lớp phải từ 1 đến 12, nhận được: {val}")
        s = str(val).strip()
        # Strictly match optional 'Lớp' or 'Khối' followed by digits 1-12 only
        m = re.match(r'^(?:(?:Lớp|Khối)\s*)?([1-9]|1[0-2])$', s, re.IGNORECASE)
        if m:
            self.grade = int(m.group(1))
            return self
        raise ValueError(f"Khối lớp không hợp lệ: {val}")

class OcrLearnRequest(BaseModel):
    raw_text: str = Field(..., description="Văn bản thô OCR nhận diện ban đầu")
    corrected_text: str = Field(..., description="Văn bản chuẩn sau khi người dùng đính chính")
    source: Optional[str] = "manual_feedback"

class OcrCorrectionCreate(BaseModel):
    wrong_text: str = Field(..., description="Từ/cụm từ sai do OCR nhận dạng")
    correct_text: str = Field(..., description="Từ/cụm từ thay thế đúng")
    source: Optional[str] = "manual_rule"

class AiVisionSettingsRequest(BaseModel):
    ai_vision_provider: Optional[str] = "auto"
    openrouter_api_key: Optional[str] = None
    openrouter_model: Optional[str] = None
    opencode_api_key: Optional[str] = None
    opencode_model: Optional[str] = None
    custom_vision_url: Optional[str] = None
    custom_vision_key: Optional[str] = None
    custom_vision_model: Optional[str] = None

class AiVisionTestConnectionRequest(BaseModel):
    provider: str = Field("custom", description="Nền tảng kiểm tra: 'openrouter', 'opencode', 'custom'")
    base_url: Optional[str] = Field(None, description="Base URL endpoint cho custom gateway (vd: http://127.0.0.1:20129/v1)")
    api_key: Optional[str] = Field(None, description="API Key hoặc Bearer Token")
    model: Optional[str] = Field(None, description="Tên model kiểm tra")

