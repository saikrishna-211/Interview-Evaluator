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
    InterviewReportResponse,
    InterviewCompleteResponse,
    InterviewAbandonResponse,
)

from app.report_generator import generate_final_report
from app.ai import evaluate_answer
from app.difficulty import get_next_difficulty
from app.question_generator import generate_question
from fastapi.middleware.cors import CORSMiddleware
from app.input_validator import validate_interview_input




# =========================================================
# CONFIGURATION
# =========================================================

MAX_QUESTIONS = 5


# =========================================================
# APPLICATION LIFESPAN
# =========================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    Base.metadata.create_all(bind=engine)

    yield


# =========================================================
# FASTAPI APPLICATION
# =========================================================

app = FastAPI(
    title="AI Interview Evaluator",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health")
def health_check():

    return {
        "status": "healthy"
    }


# =========================================================
# DATABASE HEALTH CHECK
# =========================================================

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


# =========================================================
# HELPER: GET INTERVIEW
# =========================================================

def get_interview_or_404(
    session_id: str,
    db: Session
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

    return interview


# =========================================================
# HELPER: GET QUESTION
# =========================================================

def get_question_or_404(
    question_id: int,
    db: Session
):

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

    return question


# =========================================================
# HELPER: CHECK INTERVIEW IS ACTIVE
# =========================================================

def ensure_interview_is_active(interview):

    if interview.status != "active":

        raise HTTPException(
            status_code=409,
            detail=(
                f"Interview is already "
                f"{interview.status}"
            )
        )


# =========================================================
# HELPER: GET INTERVIEW HISTORY
# =========================================================

def get_interview_history(
    interview,
    db: Session
):

    previous_questions = (
        db.query(models.InterviewQuestion)
        .filter(
            models.InterviewQuestion.session_id
            == interview.id
        )
        .order_by(
            models.InterviewQuestion.question_number
        )
        .all()
    )

    interview_history = []

    for question in previous_questions:

        answer = (
            db.query(models.CandidateAnswer)
            .filter(
                models.CandidateAnswer.question_id
                == question.id
            )
            .first()
        )

        if answer is None:
            continue

        evaluation = (
            db.query(models.AnswerEvaluation)
            .filter(
                models.AnswerEvaluation.answer_id
                == answer.id
            )
            .first()
        )

        if evaluation is None:
            continue

        interview_history.append({

            "question_number":
                question.question_number,

            "question":
                question.question,

            "difficulty":
                question.difficulty,

            "answer":
                answer.answer,

            "score":
                evaluation.score,

            "feedback":
                evaluation.feedback,

            "strengths":
                evaluation.strengths,

            "weaknesses":
                evaluation.weaknesses
        })

    return interview_history


# =========================================================
# HELPER: GENERATE NEXT QUESTION
# =========================================================

def generate_next_question(
    interview,
    db: Session
):

    previous_questions = (
        db.query(models.InterviewQuestion)
        .filter(
            models.InterviewQuestion.session_id
            == interview.id
        )
        .order_by(
            models.InterviewQuestion.question_number
        )
        .all()
    )

    # -----------------------------------------------------
    # BACKEND QUESTION LIMIT
    # -----------------------------------------------------

    if len(previous_questions) >= MAX_QUESTIONS:

        raise HTTPException(
            status_code=400,
            detail=(
                f"Maximum limit of "
                f"{MAX_QUESTIONS} questions reached"
            )
        )

    interview_history = get_interview_history(
        interview,
        db
    )

    try:

        generated_question = generate_question(
            role=interview.role,
            topic=interview.topic,
            difficulty=interview.current_difficulty,
            interview_history=interview_history
        )

    except ValueError as error:

        raise HTTPException(
            status_code=422,
            detail=str(error)
        )

    except Exception:

        raise HTTPException(
            status_code=503,
            detail=(
                "Unable to generate an interview question right now. "
                "Please try again."
            )
        )

    question_number = (
        len(previous_questions) + 1
    )

    new_question = models.InterviewQuestion(
        session_id=interview.id,
        question=generated_question,
        difficulty=interview.current_difficulty,
        question_number=question_number
    )

    db.add(new_question)

    db.commit()

    db.refresh(new_question)

    return new_question


# =========================================================
# HELPER: GET LATEST QUESTION
# =========================================================

def get_latest_question(
    interview,
    db: Session
):

    return (
        db.query(models.InterviewQuestion)
        .filter(
            models.InterviewQuestion.session_id
            == interview.id
        )
        .order_by(
            models.InterviewQuestion.question_number.desc()
        )
        .first()
    )


# =========================================================
# HELPER: GET CURRENT QUESTION FOR RESUME
# =========================================================

def get_current_question(
    interview,
    db: Session
):

    latest_question = get_latest_question(
        interview,
        db
    )

    # No question exists yet.
    if latest_question is None:
        return None

    # Check whether the latest question has an answer.
    latest_answer = (
        db.query(models.CandidateAnswer)
        .filter(
            models.CandidateAnswer.question_id
            == latest_question.id
        )
        .first()
    )

    # No answer yet -> this is the current question.
    if latest_answer is None:
        return latest_question

    # Check whether the latest answer was evaluated.
    latest_evaluation = (
        db.query(models.AnswerEvaluation)
        .filter(
            models.AnswerEvaluation.answer_id
            == latest_answer.id
        )
        .first()
    )

    # Answer exists but evaluation does not.
    # Resume on this question.
    if latest_evaluation is None:
        return latest_question

    # Latest question is fully completed.
    # If fewer than 5 questions exist, the next question
    # should be generated when requested.
    return None


# =========================================================
# HELPER: GET EVALUATED QUESTIONS
# =========================================================

def get_evaluated_answers(
    interview,
    db: Session
):

    questions = (
        db.query(models.InterviewQuestion)
        .filter(
            models.InterviewQuestion.session_id
            == interview.id
        )
        .order_by(
            models.InterviewQuestion.question_number
        )
        .all()
    )

    evaluated_answers = []

    for question in questions:

        answer = (
            db.query(models.CandidateAnswer)
            .filter(
                models.CandidateAnswer.question_id
                == question.id
            )
            .first()
        )

        if answer is None:
            continue

        evaluation = (
            db.query(models.AnswerEvaluation)
            .filter(
                models.AnswerEvaluation.answer_id
                == answer.id
            )
            .first()
        )

        if evaluation is None:
            continue

        # Important:
        # Only actual answers participate in the final
        # performance report.
        #
        # Skipped questions have answer == "".
        if answer.answer.strip() == "":
            continue

        evaluated_answers.append({

            "question_number":
                question.question_number,

            "question":
                question.question,

            "difficulty":
                question.difficulty,

            "answer":
                answer.answer,

            "score":
                evaluation.score,

            "feedback":
                evaluation.feedback,

            "strengths":
                evaluation.strengths,

            "weaknesses":
                evaluation.weaknesses
        })

    return questions, evaluated_answers


# =========================================================
# HELPER: FINALIZE INTERVIEW
# =========================================================

def finalize_interview(
    interview,
    db: Session
):

    questions, evaluated_answers = (
        get_evaluated_answers(
            interview,
            db
        )
    )

    # -----------------------------------------------------
    # Must have exactly 5 questions
    # -----------------------------------------------------

    if len(questions) != MAX_QUESTIONS:

        raise HTTPException(
            status_code=400,
            detail=(
                f"Interview can only be completed "
                f"after exactly {MAX_QUESTIONS} "
                f"questions exist"
            )
        )

    # -----------------------------------------------------
    # Count actual answered questions
    #
    # A real answer with score 0 still counts as answered.
    # An empty answer / skipped question does not.
    # -----------------------------------------------------

    answered_questions = len(
        evaluated_answers
    )

    # -----------------------------------------------------
    # Prevent duplicate report
    # -----------------------------------------------------

    existing_report = (
        db.query(models.InterviewReport)
        .filter(
            models.InterviewReport.session_id
            == interview.id
        )
        .first()
    )

    if existing_report is not None:

        interview.status = "completed"

        db.commit()

        return existing_report

    # -----------------------------------------------------
    # CASE 1:
    # No actual answers were provided.
    #
    # Do NOT call the AI report generator.
    # -----------------------------------------------------

    if answered_questions == 0:

        average_score = 0.0

        overall_feedback = (
            "The candidate did not answer "
            "any interview questions."
        )

        strengths = (
            "No strengths could be evaluated "
            "because no answers were provided."
        )

        weaknesses = (
            "No interview performance "
            "could be assessed."
        )

        recommendations = (
            "Complete the interview questions "
            "to receive a meaningful performance evaluation."
        )

    # -----------------------------------------------------
    # CASE 2:
    # At least one real answer exists.
    # -----------------------------------------------------

    else:

        average_score = round(
            sum(
                item["score"]
                for item in evaluated_answers
            ) / answered_questions,
            2
        )

        final_report = generate_final_report(
            role=interview.role,
            topic=interview.topic,
            average_score=average_score,
            evaluated_answers=evaluated_answers
        )

        overall_feedback = (
            final_report.overall_feedback
        )

        strengths = (
            final_report.strengths
        )

        weaknesses = (
            final_report.weaknesses
        )

        recommendations = (
            final_report.recommendations
        )

    # -----------------------------------------------------
    # Save report
    # -----------------------------------------------------

    report = models.InterviewReport(

        session_id=interview.id,

        average_score=average_score,

        total_questions=len(questions),

        answered_questions=answered_questions,

        overall_feedback=overall_feedback,

        strengths=strengths,

        weaknesses=weaknesses,

        recommendations=recommendations
    )

    db.add(report)

    interview.status = "completed"

    db.commit()

    db.refresh(report)

    return report


# =========================================================
# HELPER: QUESTION RESPONSE
# =========================================================

def question_to_response(
    question,
    session_id: str
):

    return {

        "id":
            question.id,

        "session_id":
            session_id,

        "question":
            question.question,

        "difficulty":
            question.difficulty,

        "question_number":
            question.question_number
    }


# =========================================================
# CREATE INTERVIEW
# =========================================================
# =========================================================
# VALIDATE INTERVIEW INPUT
# =========================================================

@app.post("/interviews/validate-input")
def validate_input(
    interview: InterviewCreate
):
    try:

        is_valid, message = validate_interview_input(
            role=interview.role,
            topic=interview.topic
        )

        if not is_valid:

            raise HTTPException(
                status_code=422,
                detail=message
            )

        return {
            "valid": True,
            "message": message
        }

    except HTTPException:
        raise

    except RuntimeError as error:

        raise HTTPException(
            status_code=503,
            detail=str(error)
        )

    except Exception:

        raise HTTPException(
            status_code=503,
            detail=(
                "Unable to validate the role and topic right now. "
                "Please try again."
            )
        )

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

        current_difficulty=(
            interview.difficulty.value
        ),

        status="active"
    )

    db.add(new_interview)

    db.commit()

    db.refresh(new_interview)

    return {

        "session_id":
            new_interview.session_id,

        "role":
            new_interview.role,

        "topic":
            new_interview.topic,

        "difficulty":
            new_interview.current_difficulty,

        "status":
            new_interview.status,

        "first_question":
            None,

        "current_question":
            None
    }


# =========================================================
# START / RESUME INTERVIEW
# =========================================================

@app.post(
    "/interviews/{session_id}/start",
    response_model=QuestionResponse
)
def start_interview(
    session_id: str,
    db: Session = Depends(get_db)
):

    interview = get_interview_or_404(
        session_id,
        db
    )

    ensure_interview_is_active(interview)

    latest_question = get_latest_question(
        interview,
        db
    )

    # -----------------------------------------------------
    # No questions yet -> generate Q1
    # -----------------------------------------------------

    if latest_question is None:

        first_question = generate_next_question(
            interview,
            db
        )

        return question_to_response(
            first_question,
            interview.session_id
        )

    # -----------------------------------------------------
    # Check latest answer
    # -----------------------------------------------------

    latest_answer = (
        db.query(models.CandidateAnswer)
        .filter(
            models.CandidateAnswer.question_id
            == latest_question.id
        )
        .first()
    )

    # -----------------------------------------------------
    # Latest question is still unanswered.
    # Resume here.
    # -----------------------------------------------------

    if latest_answer is None:

        return question_to_response(
            latest_question,
            interview.session_id
        )

    # -----------------------------------------------------
    # Check latest evaluation
    # -----------------------------------------------------

    latest_evaluation = (
        db.query(models.AnswerEvaluation)
        .filter(
            models.AnswerEvaluation.answer_id
            == latest_answer.id
        )
        .first()
    )

    # -----------------------------------------------------
    # Answer exists but evaluation missing.
    # Resume here.
    # -----------------------------------------------------

    if latest_evaluation is None:

        return question_to_response(
            latest_question,
            interview.session_id
        )

    # -----------------------------------------------------
    # Latest question is fully completed.
    #
    # If fewer than 5 questions exist, generate the next.
    # -----------------------------------------------------

    question_count = (
        db.query(models.InterviewQuestion)
        .filter(
            models.InterviewQuestion.session_id
            == interview.id
        )
        .count()
    )

    if question_count >= MAX_QUESTIONS:

        # This should normally never happen because Q5
        # automatically completes the interview.
        raise HTTPException(
            status_code=409,
            detail="Interview is already completed"
        )

    next_question = generate_next_question(
        interview,
        db
    )

    return question_to_response(
        next_question,
        interview.session_id
    )


# =========================================================
# GET INTERVIEW
# =========================================================

@app.get(
    "/interviews/{session_id}",
    response_model=InterviewResponse
)
def get_interview(
    session_id: str,
    db: Session = Depends(get_db)
):

    interview = get_interview_or_404(
        session_id,
        db
    )

    # -----------------------------------------------------
    # First question
    # -----------------------------------------------------

    first_question = (
        db.query(models.InterviewQuestion)
        .filter(
            models.InterviewQuestion.session_id
            == interview.id,
            models.InterviewQuestion.question_number
            == 1
        )
        .first()
    )

    # -----------------------------------------------------
    # Current question for resume
    # -----------------------------------------------------

    current_question = None

    if interview.status == "active":

        current_question = get_current_question(
            interview,
            db
        )

        # If all existing questions are complete but the
        # interview is still active, expose the next question
        # only when it already exists. We don't generate here.
        if current_question is None:

            latest_question = get_latest_question(
                interview,
                db
            )

            if latest_question is not None:

                latest_answer = (
                    db.query(
                        models.CandidateAnswer
                    )
                    .filter(
                        models.CandidateAnswer.question_id
                        == latest_question.id
                    )
                    .first()
                )

                latest_evaluation = None

                if latest_answer:

                    latest_evaluation = (
                        db.query(
                            models.AnswerEvaluation
                        )
                        .filter(
                            models.AnswerEvaluation.answer_id
                            == latest_answer.id
                        )
                        .first()
                    )

                # If latest question is complete, leave current
                # question as None. The /start endpoint will
                # generate the next one.
                if (
                    latest_answer is not None
                    and latest_evaluation is not None
                ):
                    current_question = None

    return {

        "session_id":
            interview.session_id,

        "role":
            interview.role,

        "topic":
            interview.topic,

        "difficulty":
            interview.current_difficulty,

        "status":
            interview.status,

        "first_question": (

            question_to_response(
                first_question,
                interview.session_id
            )

            if first_question

            else None
        ),

        "current_question": (

            question_to_response(
                current_question,
                interview.session_id
            )

            if current_question

            else None
        )
    }


# =========================================================
# CREATE MANUAL QUESTION
# =========================================================

@app.post(
    "/interviews/{session_id}/questions",
    response_model=QuestionResponse
)
def create_question(
    session_id: str,
    question_data: QuestionCreate,
    db: Session = Depends(get_db)
):

    interview = get_interview_or_404(
        session_id,
        db
    )

    ensure_interview_is_active(interview)

    last_question = (
        db.query(models.InterviewQuestion)
        .filter(
            models.InterviewQuestion.session_id
            == interview.id
        )
        .order_by(
            models.InterviewQuestion.question_number.desc()
        )
        .first()
    )

    if last_question is None:

        question_number = 1

    else:

        question_number = (
            last_question.question_number + 1
        )

    if question_number > MAX_QUESTIONS:

        raise HTTPException(
            status_code=400,
            detail=(
                f"Maximum limit of "
                f"{MAX_QUESTIONS} questions reached"
            )
        )

    new_question = models.InterviewQuestion(

        session_id=interview.id,

        question=question_data.question,

        difficulty=question_data.difficulty.value,

        question_number=question_number
    )

    db.add(new_question)

    db.commit()

    db.refresh(new_question)

    return question_to_response(
        new_question,
        interview.session_id
    )


# =========================================================
# GET ALL QUESTIONS
# =========================================================

@app.get(
    "/interviews/{session_id}/questions",
    response_model=list[QuestionResponse]
)
def get_questions(
    session_id: str,
    db: Session = Depends(get_db)
):

    interview = get_interview_or_404(
        session_id,
        db
    )

    questions = (
        db.query(models.InterviewQuestion)
        .filter(
            models.InterviewQuestion.session_id
            == interview.id
        )
        .order_by(
            models.InterviewQuestion.question_number
        )
        .all()
    )

    return [

        question_to_response(
            question,
            interview.session_id
        )

        for question in questions
    ]


# =========================================================
# CREATE CANDIDATE ANSWER
# =========================================================

@app.post(
    "/questions/{question_id}/answers",
    response_model=AnswerResponse
)
def create_answer(
    question_id: int,
    answer_data: AnswerCreate,
    db: Session = Depends(get_db)
):

    question = get_question_or_404(
        question_id,
        db
    )

    interview = (
        db.query(models.InterviewSession)
        .filter(
            models.InterviewSession.id
            == question.session_id
        )
        .first()
    )

    if interview is None:

        raise HTTPException(
            status_code=404,
            detail="Interview session not found"
        )

    ensure_interview_is_active(interview)

    existing_answer = (
        db.query(models.CandidateAnswer)
        .filter(
            models.CandidateAnswer.question_id
            == question.id
        )
        .first()
    )

    if existing_answer is not None:

        raise HTTPException(
            status_code=409,
            detail="Question has already been answered"
        )

    new_answer = models.CandidateAnswer(

        question_id=question.id,

        answer=answer_data.answer
    )

    db.add(new_answer)

    db.commit()

    db.refresh(new_answer)

    return {

        "id":
            new_answer.id,

        "question_id":
            new_answer.question_id,

        "answer":
            new_answer.answer
    }


# =========================================================
# SKIP QUESTION
# =========================================================

@app.post(
    "/questions/{question_id}/skip",
    response_model=EvaluationResponse
)
def skip_question(
    question_id: int,
    db: Session = Depends(get_db)
):

    question = get_question_or_404(
        question_id,
        db
    )

    interview = (
        db.query(models.InterviewSession)
        .filter(
            models.InterviewSession.id
            == question.session_id
        )
        .first()
    )

    if interview is None:

        raise HTTPException(
            status_code=404,
            detail="Interview session not found"
        )

    ensure_interview_is_active(interview)

    existing_answer = (
        db.query(models.CandidateAnswer)
        .filter(
            models.CandidateAnswer.question_id
            == question.id
        )
        .first()
    )

    if existing_answer is not None:

        raise HTTPException(
            status_code=409,
            detail="Question has already been answered"
        )

    skipped_answer = models.CandidateAnswer(

        question_id=question.id,

        answer=""
    )

    db.add(skipped_answer)

    db.flush()

    skipped_evaluation = models.AnswerEvaluation(

        answer_id=skipped_answer.id,

        score=0.0,

        feedback=(
            "The candidate skipped this question "
            "and did not provide an answer."
        ),

        strengths=(
            "No strengths could be evaluated "
            "because no answer was provided."
        ),

        weaknesses=(
            "The candidate should review this topic "
            "and practice similar interview questions."
        )
    )

    db.add(skipped_evaluation)

    # -----------------------------------------------------
    # Difficulty still adapts to score 0
    # -----------------------------------------------------

    interview.current_difficulty = (
        get_next_difficulty(
            current_difficulty=(
                interview.current_difficulty
            ),
            score=0.0
        )
    )

    db.commit()

    db.refresh(skipped_evaluation)

    # -----------------------------------------------------
    # Q5 skipped → automatically complete
    # -----------------------------------------------------

    if question.question_number == MAX_QUESTIONS:

        finalize_interview(
            interview,
            db
        )

    return skipped_evaluation


# =========================================================
# EVALUATE ANSWER
# =========================================================

@app.post(
    "/answers/{answer_id}/evaluate",
    response_model=EvaluationResponse
)
def evaluate_candidate_answer(
    answer_id: int,
    db: Session = Depends(get_db)
):

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

    existing_evaluation = (
        db.query(models.AnswerEvaluation)
        .filter(
            models.AnswerEvaluation.answer_id
            == answer_id
        )
        .first()
    )

    if existing_evaluation is not None:

        raise HTTPException(
            status_code=409,
            detail="Answer has already been evaluated"
        )

    question = get_question_or_404(
        answer.question_id,
        db
    )

    interview = (
        db.query(models.InterviewSession)
        .filter(
            models.InterviewSession.id
            == question.session_id
        )
        .first()
    )

    if interview is None:

        raise HTTPException(
            status_code=404,
            detail="Interview session not found"
        )

    ensure_interview_is_active(interview)

    # -----------------------------------------------------
    # EMPTY ANSWER = SCORE 0
    # -----------------------------------------------------

    if answer.answer.strip() == "":

        score = 0.0

        feedback = (
            "No answer was provided for this question."
        )

        strengths = (
            "No strengths could be evaluated."
        )

        weaknesses = (
            "The candidate should review this topic "
            "and practice answering similar questions."
        )

    else:

        evaluation = evaluate_answer(
            question=question.question,
            answer=answer.answer
        )

        score = evaluation.score
        feedback = evaluation.feedback
        strengths = evaluation.strengths
        weaknesses = evaluation.weaknesses

    # -----------------------------------------------------
    # ADAPTIVE DIFFICULTY UPDATE
    # -----------------------------------------------------

    interview.current_difficulty = (
        get_next_difficulty(
            current_difficulty=(
                interview.current_difficulty
            ),
            score=score
        )
    )

    new_evaluation = models.AnswerEvaluation(

        answer_id=answer.id,

        score=score,

        feedback=feedback,

        strengths=strengths,

        weaknesses=weaknesses
    )

    db.add(new_evaluation)

    db.commit()

    db.refresh(new_evaluation)

    # -----------------------------------------------------
    # Q5 EVALUATED → AUTOMATIC COMPLETION
    # -----------------------------------------------------

    if question.question_number == MAX_QUESTIONS:

        finalize_interview(
            interview,
            db
        )

    return new_evaluation


# =========================================================
# GENERATE NEXT QUESTION
# =========================================================

@app.post(
    "/interviews/{session_id}/generate-question",
    response_model=QuestionResponse
)
def generate_interview_question(
    session_id: str,
    db: Session = Depends(get_db)
):

    interview = get_interview_or_404(
        session_id,
        db
    )

    ensure_interview_is_active(interview)

    latest_question = get_latest_question(
        interview,
        db
    )

    # -----------------------------------------------------
    # No questions yet
    # -----------------------------------------------------

    if latest_question is None:

        new_question = generate_next_question(
            interview,
            db
        )

        return question_to_response(
            new_question,
            interview.session_id
        )

    # -----------------------------------------------------
    # Latest question must have an answer
    # -----------------------------------------------------

    latest_answer = (
        db.query(models.CandidateAnswer)
        .filter(
            models.CandidateAnswer.question_id
            == latest_question.id
        )
        .first()
    )

    if latest_answer is None:

        raise HTTPException(
            status_code=400,
            detail=(
                "Previous question must be answered "
                "and evaluated before generating "
                "the next question"
            )
        )

    # -----------------------------------------------------
    # Latest answer must have evaluation
    # -----------------------------------------------------

    latest_evaluation = (
        db.query(models.AnswerEvaluation)
        .filter(
            models.AnswerEvaluation.answer_id
            == latest_answer.id
        )
        .first()
    )

    if latest_evaluation is None:

        raise HTTPException(
            status_code=400,
            detail=(
                "Previous question must be answered "
                "and evaluated before generating "
                "the next question"
            )
        )

    # -----------------------------------------------------
    # Backend 5-question protection
    # -----------------------------------------------------

    question_count = (
        db.query(models.InterviewQuestion)
        .filter(
            models.InterviewQuestion.session_id
            == interview.id
        )
        .count()
    )

    if question_count >= MAX_QUESTIONS:

        raise HTTPException(
            status_code=400,
            detail=(
                f"Maximum limit of "
                f"{MAX_QUESTIONS} questions reached"
            )
        )

    new_question = generate_next_question(
        interview,
        db
    )

    return question_to_response(
        new_question,
        interview.session_id
    )


# =========================================================
# COMPLETE INTERVIEW
# =========================================================
#
# Normally the frontend does NOT call this.
#
# Q5 evaluation automatically completes the interview.
#
# This endpoint remains available for controlled/manual
# completion when all 5 questions are already evaluated.
# =========================================================

@app.post(
    "/interviews/{session_id}/complete",
    response_model=InterviewCompleteResponse
)
def complete_interview(
    session_id: str,
    db: Session = Depends(get_db)
):

    interview = get_interview_or_404(
        session_id,
        db
    )

    ensure_interview_is_active(interview)

    finalize_interview(
        interview,
        db
    )

    return {

        "session_id":
            interview.session_id,

        "status":
            interview.status,

        "message":
            "Interview completed and final report generated successfully"
    }


# =========================================================
# ABANDON INTERVIEW
# =========================================================

@app.post(
    "/interviews/{session_id}/abandon",
    response_model=InterviewAbandonResponse
)
def abandon_interview(
    session_id: str,
    db: Session = Depends(get_db)
):

    interview = get_interview_or_404(
        session_id,
        db
    )

    ensure_interview_is_active(interview)

    interview.status = "abandoned"

    db.commit()

    return {

        "session_id":
            interview.session_id,

        "status":
            interview.status,

        "message":
            "Interview abandoned successfully"
    }


# =========================================================
# GET FINAL REPORT
# =========================================================

@app.get(
    "/interviews/{session_id}/report",
    response_model=InterviewReportResponse
)
def get_interview_report(
    session_id: str,
    db: Session = Depends(get_db)
):

    interview = get_interview_or_404(
        session_id,
        db
    )

    # -----------------------------------------------------
    # Only completed interviews have reports
    # -----------------------------------------------------

    if interview.status != "completed":

        raise HTTPException(
            status_code=404,
            detail=(
                "Interview report is available "
                "only after interview completion"
            )
        )

    report = (
        db.query(models.InterviewReport)
        .filter(
            models.InterviewReport.session_id
            == interview.id
        )
        .first()
    )

    if report is None:

        raise HTTPException(
            status_code=404,
            detail="Interview report not generated yet"
        )

    questions = (
        db.query(models.InterviewQuestion)
        .filter(
            models.InterviewQuestion.session_id
            == interview.id
        )
        .order_by(
            models.InterviewQuestion.question_number
        )
        .all()
    )

    question_reports = []

    for question in questions:

        answer = (
            db.query(models.CandidateAnswer)
            .filter(
                models.CandidateAnswer.question_id
                == question.id
            )
            .first()
        )

        evaluation = None

        if answer is not None:

            evaluation = (
                db.query(models.AnswerEvaluation)
                .filter(
                    models.AnswerEvaluation.answer_id
                    == answer.id
                )
                .first()
            )

        # -------------------------------------------------
        # Empty answer is shown as None in final report
        # -------------------------------------------------

        actual_answer = None

        if answer is not None:

            if answer.answer.strip() != "":

                actual_answer = answer.answer

        question_reports.append({

            "question_number":
                question.question_number,

            "question":
                question.question,

            "difficulty":
                question.difficulty,

            "answer":
                actual_answer,

            "score": (
                evaluation.score
                if evaluation is not None
                else None
            ),

            "feedback": (
                evaluation.feedback
                if evaluation is not None
                else None
            ),

            "strengths": (
                evaluation.strengths
                if evaluation is not None
                else None
            ),

            "weaknesses": (
                evaluation.weaknesses
                if evaluation is not None
                else None
            )
        })

    # -----------------------------------------------------
    # Strongest / weakest only among questions that
    # actually received an answer.
    # -----------------------------------------------------

    answered_questions = [

        question

        for question in question_reports

        if (
            question["answer"] is not None
            and question["score"] is not None
        )
    ]

    strongest_question = None
    weakest_question = None

    if answered_questions:

        strongest_question = max(
            answered_questions,
            key=lambda question: question["score"]
        )

        weakest_question = min(
            answered_questions,
            key=lambda question: question["score"]
        )

    return {

        "session_id":
            interview.session_id,

        "role":
            interview.role,

        "topic":
            interview.topic,

        "status":
            interview.status,

        "total_questions":
            report.total_questions,

        "answered_questions":
            report.answered_questions,

        "average_score":
            report.average_score,

        "overall_feedback":
            report.overall_feedback,

        "strengths":
            report.strengths,

        "weaknesses":
            report.weaknesses,

        "recommendations":
            report.recommendations,

        "strongest_question":
            strongest_question,

        "weakest_question":
            weakest_question,

        "questions":
            question_reports
    }