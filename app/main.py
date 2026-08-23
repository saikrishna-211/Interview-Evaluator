from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import engine, Base, get_db
from app import models

from app.schemas import (
    InterviewCreate,
    InterviewResponse,
    QuestionCreate,
    QuestionResponse,
    AnswerCreate,
    AnswerResponse,
    EvaluationResponse,
)
from app.ai import evaluate_answer
from app.difficulty import get_next_difficulty


# -----------------------------------
# Application Lifespan
# -----------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):

    # Create database tables if they don't exist
    Base.metadata.create_all(bind=engine)

    yield


# -----------------------------------
# FastAPI Application
# -----------------------------------

app = FastAPI(
    title="AI Interview Evaluator",
    version="1.0.0",
    lifespan=lifespan
)


# -----------------------------------
# Health Check
# -----------------------------------

@app.get("/health")
def health_check():

    return {
        "status": "healthy"
    }


# -----------------------------------
# Database Health Check
# -----------------------------------

@app.get("/health/database")
def database_health_check():

    try:

        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "status": "healthy",
            "database": "connected"
        }

    except Exception as error:

        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(error)
        }


# -----------------------------------
# Create Interview
# -----------------------------------

@app.post(
    "/interviews",
    response_model=InterviewResponse
)
def create_interview(
    interview: InterviewCreate,
    db: Session = Depends(get_db)
):

    new_interview = models.InterviewSession(

        session_id=str(uuid4()),

        role=interview.role,

        topic=interview.topic,

        current_difficulty=interview.difficulty.value,

        status="active"
    )

    db.add(new_interview)

    db.commit()

    db.refresh(new_interview)

    return {
        "session_id": new_interview.session_id,
        "role": new_interview.role,
        "topic": new_interview.topic,
        "difficulty": new_interview.current_difficulty,
        "status": new_interview.status
    }


# -----------------------------------
# Get Interview
# -----------------------------------

@app.get(
    "/interviews/{session_id}",
    response_model=InterviewResponse
)
def get_interview(
    session_id: str,
    db: Session = Depends(get_db)
):

    interview = (
        db.query(models.InterviewSession)
        .filter(
            models.InterviewSession.session_id == session_id
        )
        .first()
    )

    if interview is None:

        raise HTTPException(
            status_code=404,
            detail="Interview session not found"
        )

    return {
        "session_id": interview.session_id,
        "role": interview.role,
        "topic": interview.topic,
        "difficulty": interview.current_difficulty,
        "status": interview.status
    }


# -----------------------------------
# Create Question
# -----------------------------------

@app.post(
    "/interviews/{session_id}/questions",
    response_model=QuestionResponse
)
def create_question(
    session_id: str,
    question_data: QuestionCreate,
    db: Session = Depends(get_db)
):

    # Find interview
    interview = (
        db.query(models.InterviewSession)
        .filter(
            models.InterviewSession.session_id == session_id
        )
        .first()
    )

    if interview is None:

        raise HTTPException(
            status_code=404,
            detail="Interview session not found"
        )

    # Find latest question
    last_question = (
        db.query(models.InterviewQuestion)
        .filter(
            models.InterviewQuestion.session_id == interview.id
        )
        .order_by(
            models.InterviewQuestion.question_number.desc()
        )
        .first()
    )

    # Determine question number
    if last_question is None:

        question_number = 1

    else:

        question_number = (
            last_question.question_number + 1
        )

    # Create question
    new_question = models.InterviewQuestion(

        session_id=interview.id,

        question=question_data.question,

        difficulty=question_data.difficulty.value,

        question_number=question_number
    )

    db.add(new_question)

    db.commit()

    db.refresh(new_question)

    return {
        "id": new_question.id,
        "session_id": interview.session_id,
        "question": new_question.question,
        "difficulty": new_question.difficulty,
        "question_number": new_question.question_number
    }


# -----------------------------------
# Get Questions
# -----------------------------------

@app.get(
    "/interviews/{session_id}/questions",
    response_model=list[QuestionResponse]
)
def get_questions(
    session_id: str,
    db: Session = Depends(get_db)
):

    # Find interview
    interview = (
        db.query(models.InterviewSession)
        .filter(
            models.InterviewSession.session_id == session_id
        )
        .first()
    )

    if interview is None:

        raise HTTPException(
            status_code=404,
            detail="Interview session not found"
        )

    # Get questions
    questions = (
        db.query(models.InterviewQuestion)
        .filter(
            models.InterviewQuestion.session_id == interview.id
        )
        .order_by(
            models.InterviewQuestion.question_number
        )
        .all()
    )

    return [
        {
            "id": question.id,
            "session_id": interview.session_id,
            "question": question.question,
            "difficulty": question.difficulty,
            "question_number": question.question_number
        }
        for question in questions
    ]


# -----------------------------------
# Create Candidate Answer
# -----------------------------------

@app.post(
    "/questions/{question_id}/answers",
    response_model=AnswerResponse
)
def create_answer(
    question_id: int,
    answer_data: AnswerCreate,
    db: Session = Depends(get_db)
):

    # Find question
    question = (
        db.query(models.InterviewQuestion)
        .filter(
            models.InterviewQuestion.id == question_id
        )
        .first()
    )

    if question is None:

        raise HTTPException(
            status_code=404,
            detail="Question not found"
        )

    # Create answer
    new_answer = models.CandidateAnswer(

        question_id=question.id,

        answer=answer_data.answer
    )

    db.add(new_answer)

    db.commit()

    db.refresh(new_answer)

    return {
        "id": new_answer.id,
        "question_id": new_answer.question_id,
        "answer": new_answer.answer
    }
@app.post(
    "/answers/{answer_id}/evaluate",
    response_model=EvaluationResponse
)
def evaluate_candidate_answer(
    answer_id: int,
    db: Session = Depends(get_db)
):

    # Find candidate answer
    answer = (
        db.query(models.CandidateAnswer)
        .filter(
            models.CandidateAnswer.id == answer_id
        )
        .first()
    )

    if answer is None:
        raise HTTPException(
            status_code=404,
            detail="Answer not found"
        )

    # Prevent duplicate evaluation
    existing_evaluation = (
        db.query(models.AnswerEvaluation)
        .filter(
            models.AnswerEvaluation.answer_id == answer_id
        )
        .first()
    )

    if existing_evaluation is not None:
        raise HTTPException(
            status_code=409,
            detail="Answer has already been evaluated"
        )

    # Find the question related to this answer
    question = (
        db.query(models.InterviewQuestion)
        .filter(
            models.InterviewQuestion.id == answer.question_id
        )
        .first()
    )

    if question is None:
        raise HTTPException(
            status_code=404,
            detail="Question not found"
        )

    # Get AI evaluation from Groq
    evaluation = evaluate_answer(
        question=question.question,
        answer=answer.answer
    )    
                # Find the interview session
    session = (
        db.query(models.InterviewSession)
        .filter(
            models.InterviewSession.id == question.session_id
        )
        .first()
    )

    if session is None:
        raise HTTPException(
            status_code=404,
            detail="Interview session not found"
        )

    # Calculate next difficulty
    next_difficulty = get_next_difficulty(
        current_difficulty=session.current_difficulty,
        score=evaluation.score
    )

    # Update the session
    session.current_difficulty = next_difficulty

        # Save AI evaluation
    new_evaluation = models.AnswerEvaluation(
        answer_id=answer.id,
        score=evaluation.score,
        feedback=evaluation.feedback,
        strengths=evaluation.strengths,
        weaknesses=evaluation.weaknesses
    )

    db.add(new_evaluation)

    db.commit()

    db.refresh(new_evaluation)

    return new_evaluation