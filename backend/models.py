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
    images: List[str] = Field(default_factory=list)
    options: List[OptionItem] = Field(default_factory=list)
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    difficulty: Optional[str] = "medium"  # easy, medium, hard, olympiad

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

