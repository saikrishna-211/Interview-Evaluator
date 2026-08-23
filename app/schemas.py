from enum import Enum

from pydantic import BaseModel


class DifficultyLevel(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


# -------------------------
# Interview Schemas
# -------------------------

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


# -------------------------
# Question Schemas
# -------------------------

class QuestionCreate(BaseModel):
    question: str
    difficulty: DifficultyLevel = DifficultyLevel.medium


class QuestionResponse(BaseModel):
    id: int
    session_id: str
    question: str
    difficulty: DifficultyLevel
    question_number: int


# -------------------------
# Answer Schemas
# -------------------------

class AnswerCreate(BaseModel):
    answer: str


class AnswerResponse(BaseModel):
    id: int
    question_id: int
    answer: str


# -------------------------
# Evaluation Schemas
# -------------------------
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