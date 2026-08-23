from datetime import datetime, timezone

from sqlalchemy import String, ForeignKey, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    session_id: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        index=True
    )

    role: Mapped[str] = mapped_column(
        String(100)
    )

    topic: Mapped[str] = mapped_column(
        String(100)
    )

    current_difficulty: Mapped[str] = mapped_column(
        String(20),
        default="medium"
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="active"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )


class InterviewQuestion(Base):
    __tablename__ = "interview_questions"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    session_id: Mapped[int] = mapped_column(
        ForeignKey("interview_sessions.id")
    )

    question: Mapped[str] = mapped_column(
        Text
    )

    difficulty: Mapped[str] = mapped_column(
        String(20)
    )

    question_number: Mapped[int] = mapped_column()

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )


class CandidateAnswer(Base):
    __tablename__ = "candidate_answers"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    question_id: Mapped[int] = mapped_column(
        ForeignKey("interview_questions.id")
    )

    answer: Mapped[str] = mapped_column(
        Text
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )


class AnswerEvaluation(Base):
    __tablename__ = "answer_evaluations"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    answer_id: Mapped[int] = mapped_column(
        ForeignKey("candidate_answers.id"),
        unique=True
    )

    score: Mapped[float] = mapped_column()

    feedback: Mapped[str] = mapped_column(
        Text
    )

    strengths: Mapped[str] = mapped_column(
        Text
    )

    weaknesses: Mapped[str] = mapped_column(
        Text
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
 