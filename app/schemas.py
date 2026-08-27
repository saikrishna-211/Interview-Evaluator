from enum import Enum

from pydantic import BaseModel


# =========================================================
# ENUMS
# =========================================================

class DifficultyLevel(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


# =========================================================
# INTERVIEW
# =========================================================

class InterviewCreate(BaseModel):
    role: str
    topic: str

    difficulty: DifficultyLevel = DifficultyLevel.medium


class InterviewResponse(BaseModel):
    session_id: str
    role: str
    topic: str
    difficulty: DifficultyLevel
    status: str

    # Kept for compatibility with the existing API.
    first_question: "QuestionResponse | None" = None

    # The question the user should currently work on.
    current_question: "QuestionResponse | None" = None


# =========================================================
# QUESTIONS
# =========================================================

class QuestionCreate(BaseModel):
    question: str
    difficulty: DifficultyLevel = DifficultyLevel.medium


class QuestionResponse(BaseModel):
    id: int
    session_id: str
    question: str
    difficulty: DifficultyLevel
    question_number: int


# =========================================================
# ANSWERS
# =========================================================

class AnswerCreate(BaseModel):
    # Empty answer is intentionally allowed.
    answer: str


class AnswerResponse(BaseModel):
    id: int
    question_id: int
    answer: str


# =========================================================
# EVALUATION
# =========================================================

class EvaluationCreate(BaseModel):
    score: float
    feedback: str
    strengths: str
    weaknesses: str


class EvaluationResponse(BaseModel):
    id: int
    answer_id: int
    score: float
    feedback: str
    strengths: str
    weaknesses: str


# =========================================================
# QUESTION REPORT
# =========================================================

class QuestionReport(BaseModel):
    question_number: int
    question: str
    difficulty: str

    answer: str | None
    score: float | None
    feedback: str | None
    strengths: str | None
    weaknesses: str | None


# =========================================================
# FINAL REPORT
# =========================================================

class InterviewReportResponse(BaseModel):
    session_id: str
    role: str
    topic: str
    status: str

    total_questions: int
    answered_questions: int

    average_score: float | None

    overall_feedback: str | None
    strengths: str | None
    weaknesses: str | None
    recommendations: str | None

    strongest_question: QuestionReport | None
    weakest_question: QuestionReport | None

    questions: list[QuestionReport]


class FinalReportCreate(BaseModel):
    overall_feedback: str
    strengths: str
    weaknesses: str
    recommendations: str


# =========================================================
# COMPLETE / ABANDON
# =========================================================

class InterviewCompleteResponse(BaseModel):
    session_id: str
    status: str
    message: str


class InterviewAbandonResponse(BaseModel):
    session_id: str
    status: str
    message: str