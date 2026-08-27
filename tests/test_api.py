import pytest
from fastapi.testclient import TestClient

from app.main import app
from app import models
from app.database import SessionLocal


client = TestClient(app)
client.__enter__()


def teardown_module(module):
    client.__exit__(None, None, None)


# =========================================================
# MOCK HELPERS
# =========================================================

def mock_question_generator(
    role,
    topic,
    difficulty,
    interview_history
):
    return "What is React?"


def mock_evaluation(
    score=8.0,
    feedback="Good answer.",
    strengths="Good understanding.",
    weaknesses="Could provide more detail."
):
    return type(
        "Evaluation",
        (),
        {
            "score": score,
            "feedback": feedback,
            "strengths": strengths,
            "weaknesses": weaknesses
        }
    )()


def mock_final_report(
    overall_feedback="Good overall performance.",
    strengths="Strong fundamentals.",
    weaknesses="Needs more depth.",
    recommendations="Practice more."
):
    return type(
        "FinalReport",
        (),
        {
            "overall_feedback": overall_feedback,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "recommendations": recommendations
        }
    )()


# =========================================================
# INTERVIEW HELPERS
# =========================================================

def create_test_interview(monkeypatch):

    monkeypatch.setattr(
        "app.main.generate_question",
        mock_question_generator
    )

    response = client.post(
        "/interviews",
        json={
            "role": "frontend developer",
            "topic": "react",
            "difficulty": "medium"
        }
    )

    assert response.status_code == 200

    return response.json()


def start_test_interview(
    session_id,
    monkeypatch
):

    monkeypatch.setattr(
        "app.main.generate_question",
        mock_question_generator
    )

    response = client.post(
        f"/interviews/{session_id}/start"
    )

    assert response.status_code == 200

    return response.json()


def answer_question(
    question_id,
    answer="Test answer"
):

    response = client.post(
        f"/questions/{question_id}/answers",
        json={
            "answer": answer
        }
    )

    assert response.status_code == 200

    return response.json()


def evaluate_question(
    answer_id,
    monkeypatch,
    score=8.0,
    feedback="Good answer.",
    strengths="Good understanding.",
    weaknesses="Needs more detail."
):

    monkeypatch.setattr(
        "app.main.evaluate_answer",
        lambda question, answer:
            mock_evaluation(
                score=score,
                feedback=feedback,
                strengths=strengths,
                weaknesses=weaknesses
            )
    )

    response = client.post(
        f"/answers/{answer_id}/evaluate"
    )

    assert response.status_code == 200

    return response.json()


def generate_next_question(
    session_id,
    monkeypatch,
    question_text="Next interview question."
):

    monkeypatch.setattr(
        "app.main.generate_question",
        lambda role,
        topic,
        difficulty,
        interview_history:
            question_text
    )

    response = client.post(
        f"/interviews/{session_id}/generate-question"
    )

    assert response.status_code == 200

    return response.json()


# =========================================================
# DATABASE CLEANUP
# =========================================================

def cleanup_interview(session_id):

    db = SessionLocal()

    try:

        interview = (
            db.query(models.InterviewSession)
            .filter(
                models.InterviewSession.session_id
                == session_id
            )
            .first()
        )

        if interview is None:
            return

        # -------------------------------------------------
        # Get questions
        # -------------------------------------------------

        questions = (
            db.query(models.InterviewQuestion)
            .filter(
                models.InterviewQuestion.session_id
                == interview.id
            )
            .all()
        )

        question_ids = [
            question.id
            for question in questions
        ]

        # -------------------------------------------------
        # Get answers
        # -------------------------------------------------

        answer_ids = []

        if question_ids:

            answers = (
                db.query(models.CandidateAnswer)
                .filter(
                    models.CandidateAnswer.question_id.in_(
                        question_ids
                    )
                )
                .all()
            )

            answer_ids = [
                answer.id
                for answer in answers
            ]

        # -------------------------------------------------
        # Delete evaluations
        # -------------------------------------------------

        if answer_ids:

            db.query(
                models.AnswerEvaluation
            ).filter(
                models.AnswerEvaluation.answer_id.in_(
                    answer_ids
                )
            ).delete(
                synchronize_session=False
            )

        # -------------------------------------------------
        # Delete answers
        # -------------------------------------------------

        if answer_ids:

            db.query(
                models.CandidateAnswer
            ).filter(
                models.CandidateAnswer.id.in_(
                    answer_ids
                )
            ).delete(
                synchronize_session=False
            )

        # -------------------------------------------------
        # Delete questions
        # -------------------------------------------------

        if question_ids:

            db.query(
                models.InterviewQuestion
            ).filter(
                models.InterviewQuestion.id.in_(
                    question_ids
                )
            ).delete(
                synchronize_session=False
            )

        # -------------------------------------------------
        # Delete report
        # -------------------------------------------------

        db.query(
            models.InterviewReport
        ).filter(
            models.InterviewReport.session_id
            == interview.id
        ).delete(
            synchronize_session=False
        )

        # -------------------------------------------------
        # Delete interview
        # -------------------------------------------------

        db.delete(interview)

        db.commit()

    finally:

        db.close()


# =========================================================
# FIXTURE
# =========================================================

@pytest.fixture
def interview(monkeypatch):

    data = create_test_interview(
        monkeypatch
    )

    first_question = start_test_interview(
        data["session_id"],
        monkeypatch
    )

    data["first_question"] = first_question

    yield data

    cleanup_interview(
        data["session_id"]
    )


# =========================================================
# HEALTH TESTS
# =========================================================

def test_health():

    response = client.get(
        "/health"
    )

    assert response.status_code == 200

    assert (
        response.json()["status"]
        == "healthy"
    )


def test_database_health():

    response = client.get(
        "/health/database"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "healthy"

    assert (
        data["database"]
        == "connected"
    )


# =========================================================
# INPUT VALIDATION TESTS
# =========================================================

def test_validate_valid_interview_input(
    monkeypatch
):

    monkeypatch.setattr(
        "app.main.validate_interview_input",
        lambda role, topic:
            (
                True,
                "Role and topic are suitable for an interview."
            )
    )

    response = client.post(
        "/interviews/validate-input",
        json={
            "role": "Python Developer",
            "topic": "FastAPI",
            "difficulty": "medium"
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["valid"] is True

    assert (
        data["message"]
        == "Role and topic are suitable for an interview."
    )


def test_validate_invalid_interview_input(
    monkeypatch
):

    monkeypatch.setattr(
        "app.main.validate_interview_input",
        lambda role, topic:
            (
                False,
                "Please enter a valid professional role and interview topic."
            )
    )

    response = client.post(
        "/interviews/validate-input",
        json={
            "role": "inappropriate input",
            "topic": "inappropriate topic",
            "difficulty": "medium"
        }
    )

    assert response.status_code == 422

    data = response.json()

    assert (
        data["detail"]
        == "Please enter a valid professional role and interview topic."
    )


def test_validate_input_service_failure(
    monkeypatch
):

    def failing_validator(
        role,
        topic
    ):

        raise RuntimeError(
            "Unable to validate the role and topic right now. "
            "Please try again."
        )

    monkeypatch.setattr(
        "app.main.validate_interview_input",
        failing_validator
    )

    response = client.post(
        "/interviews/validate-input",
        json={
            "role": "Python Developer",
            "topic": "FastAPI",
            "difficulty": "medium"
        }
    )

    assert response.status_code == 503

    assert (
        response.json()["detail"]
        == (
            "Unable to validate the role and topic right now. "
            "Please try again."
        )
    )


# =========================================================
# QUESTION GENERATION SAFETY TESTS
# =========================================================

def test_refused_ai_question_is_not_saved(
    monkeypatch
):

    data = create_test_interview(
        monkeypatch
    )

    session_id = data["session_id"]

    try:

        def refused_question(
            role,
            topic,
            difficulty,
            interview_history
        ):

            raise ValueError(
                "The AI could not generate a suitable interview "
                "question for this role or topic. "
                "Please choose a different role or topic."
            )

        monkeypatch.setattr(
            "app.main.generate_question",
            refused_question
        )

        response = client.post(
            f"/interviews/{session_id}/start"
        )

        assert response.status_code == 422

        data = response.json()

        assert (
            data["detail"]
            == (
                "The AI could not generate a suitable interview "
                "question for this role or topic. "
                "Please choose a different role or topic."
            )
        )

        # -------------------------------------------------
        # Critical regression check:
        # refusal must NOT be stored as Question 1.
        # -------------------------------------------------

        questions_response = client.get(
            f"/interviews/{session_id}/questions"
        )

        assert (
            questions_response.status_code
            == 200
        )

        assert (
            questions_response.json()
            == []
        )

    finally:

        cleanup_interview(
            session_id
        )


def test_valid_ai_question_is_still_saved(
    monkeypatch
):

    data = create_test_interview(
        monkeypatch
    )

    session_id = data["session_id"]

    try:

        monkeypatch.setattr(
            "app.main.generate_question",
            lambda role,
            topic,
            difficulty,
            interview_history:
                "Explain dependency injection in FastAPI."
        )

        response = client.post(
            f"/interviews/{session_id}/start"
        )

        assert response.status_code == 200

        question = response.json()

        assert (
            question["question"]
            == "Explain dependency injection in FastAPI."
        )

        assert (
            question["question_number"]
            == 1
        )

        # -------------------------------------------------
        # Confirm the valid question WAS saved.
        # -------------------------------------------------

        questions_response = client.get(
            f"/interviews/{session_id}/questions"
        )

        assert (
            questions_response.status_code
            == 200
        )

        questions = (
            questions_response.json()
        )

        assert len(questions) == 1

        assert (
            questions[0]["question"]
            == "Explain dependency injection in FastAPI."
        )

    finally:

        cleanup_interview(
            session_id
        )


# =========================================================
# CREATE INTERVIEW TESTS
# =========================================================

def test_create_interview(monkeypatch):

    data = create_test_interview(
        monkeypatch
    )

    try:

        assert "session_id" in data

        assert (
            data["role"]
            == "frontend developer"
        )

        assert (
            data["topic"]
            == "react"
        )

        assert (
            data["difficulty"]
            == "medium"
        )

        assert (
            data["status"]
            == "active"
        )

        assert (
            data["first_question"]
            is None
        )

        assert (
            data["current_question"]
            is None
        )

        db = SessionLocal()

        try:

            interview_db = (
                db.query(
                    models.InterviewSession
                )
                .filter(
                    models.InterviewSession.session_id
                    == data["session_id"]
                )
                .first()
            )

            assert interview_db is not None

            assert (
                interview_db.status
                == "active"
            )

            question_count = (
                db.query(
                    models.InterviewQuestion
                )
                .filter(
                    models.InterviewQuestion.session_id
                    == interview_db.id
                )
                .count()
            )

            assert question_count == 0

        finally:

            db.close()

    finally:

        cleanup_interview(
            data["session_id"]
        )


# =========================================================
# START INTERVIEW TESTS
# =========================================================

def test_start_interview(monkeypatch):

    data = create_test_interview(
        monkeypatch
    )

    try:

        session_id = data["session_id"]

        question = start_test_interview(
            session_id,
            monkeypatch
        )

        assert (
            question["session_id"]
            == session_id
        )

        assert (
            question["question"]
            == "What is React?"
        )

        assert (
            question["question_number"]
            == 1
        )

        assert (
            question["difficulty"]
            == "medium"
        )

    finally:

        cleanup_interview(
            session_id
        )


def test_start_interview_twice(
    monkeypatch
):

    data = create_test_interview(
        monkeypatch
    )

    try:

        session_id = data["session_id"]

        first_response = client.post(
            f"/interviews/{session_id}/start"
        )

        assert (
            first_response.status_code
            == 200
        )

        second_response = client.post(
            f"/interviews/{session_id}/start"
        )

        assert (
            second_response.status_code
            == 200
        )

        first_question = (
            first_response.json()
        )

        second_question = (
            second_response.json()
        )

        assert (
            first_question["id"]
            == second_question["id"]
        )

        assert (
            first_question["question_number"]
            == 1
        )

    finally:

        cleanup_interview(
            session_id
        )


def test_start_invalid_interview():

    response = client.post(
        "/interviews/"
        "00000000-0000-0000-0000-000000000000/"
        "start"
    )

    assert response.status_code == 404


# =========================================================
# GET INTERVIEW TESTS
# =========================================================

def test_get_interview(interview):

    session_id = interview["session_id"]

    response = client.get(
        f"/interviews/{session_id}"
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        data["session_id"]
        == session_id
    )

    assert (
        data["role"]
        == "frontend developer"
    )

    assert (
        data["topic"]
        == "react"
    )

    assert (
        data["difficulty"]
        == "medium"
    )

    assert (
        data["status"]
        == "active"
    )

    assert (
        data["first_question"]
        is not None
    )

    assert (
        data["first_question"]["question"]
        == "What is React?"
    )

    assert (
        data["first_question"]["question_number"]
        == 1
    )

    assert (
        data["current_question"]
        is not None
    )

    assert (
        data["current_question"]["id"]
        == data["first_question"]["id"]
    )


def test_get_interview_before_start(
    monkeypatch
):

    data = create_test_interview(
        monkeypatch
    )

    try:

        response = client.get(
            f"/interviews/{data['session_id']}"
        )

        assert response.status_code == 200

        result = response.json()

        assert (
            result["status"]
            == "active"
        )

        assert (
            result["first_question"]
            is None
        )

        assert (
            result["current_question"]
            is None
        )

    finally:

        cleanup_interview(
            data["session_id"]
        )


def test_get_invalid_interview():

    response = client.get(
        "/interviews/"
        "00000000-0000-0000-0000-000000000000"
    )

    assert response.status_code == 404


# =========================================================
# RESUME TESTS
# =========================================================

def test_resume_unanswered_question(
    interview,
    monkeypatch
):

    session_id = interview["session_id"]

    question_id = (
        interview["first_question"]["id"]
    )

    # Simulate browser closed.
    # No DB change should happen.

    response = client.get(
        f"/interviews/{session_id}"
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        data["current_question"]["id"]
        == question_id
    )

    resume_response = client.post(
        f"/interviews/{session_id}/start"
    )

    assert (
        resume_response.status_code
        == 200
    )

    assert (
        resume_response.json()["id"]
        == question_id
    )


def test_resume_next_question_after_evaluation(
    interview,
    monkeypatch
):

    session_id = interview["session_id"]

    question_id = (
        interview["first_question"]["id"]
    )

    answer = answer_question(
        question_id,
        "React is a JavaScript library."
    )

    evaluate_question(
        answer["id"],
        monkeypatch
    )

    second_question = generate_next_question(
        session_id,
        monkeypatch,
        "Explain React components."
    )

    assert (
        second_question["question_number"]
        == 2
    )

    # Simulate browser closed after Q2 appeared.

    response = client.get(
        f"/interviews/{session_id}"
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        data["current_question"]["question_number"]
        == 2
    )

    assert (
        data["current_question"]["id"]
        == second_question["id"]
    )

    resume_response = client.post(
        f"/interviews/{session_id}/start"
    )

    assert (
        resume_response.status_code
        == 200
    )

    assert (
        resume_response.json()["id"]
        == second_question["id"]
    )


# =========================================================
# QUESTION TESTS
# =========================================================

def test_create_question(interview):

    session_id = interview["session_id"]

    response = client.post(
        f"/interviews/{session_id}/questions",
        json={
            "question": "What are props?",
            "difficulty": "medium"
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        data["session_id"]
        == session_id
    )

    assert (
        data["question"]
        == "What are props?"
    )

    assert (
        data["difficulty"]
        == "medium"
    )

    assert (
        data["question_number"]
        == 2
    )


def test_get_questions(interview):

    session_id = interview["session_id"]

    response_2 = client.post(
        f"/interviews/{session_id}/questions",
        json={
            "question": "What are props?",
            "difficulty": "medium"
        }
    )

    assert (
        response_2.status_code
        == 200
    )

    response_3 = client.post(
        f"/interviews/{session_id}/questions",
        json={
            "question": "What is state?",
            "difficulty": "medium"
        }
    )

    assert (
        response_3.status_code
        == 200
    )

    response = client.get(
        f"/interviews/{session_id}/questions"
    )

    assert response.status_code == 200

    questions = response.json()

    assert len(questions) == 3

    assert (
        questions[0]["question_number"]
        == 1
    )

    assert (
        questions[1]["question_number"]
        == 2
    )

    assert (
        questions[2]["question_number"]
        == 3
    )

    assert (
        questions[0]["question"]
        == "What is React?"
    )


def test_question_limit_manual_creation(
    interview
):

    session_id = interview["session_id"]

    # Q1 already exists.
    # Create Q2-Q5.

    for number in range(2, 6):

        response = client.post(
            f"/interviews/{session_id}/questions",
            json={
                "question":
                    f"Question {number}",
                "difficulty":
                    "medium"
            }
        )

        assert (
            response.status_code
            == 200
        )

    # Q6 must be rejected.

    response = client.post(
        f"/interviews/{session_id}/questions",
        json={
            "question": "Question 6",
            "difficulty": "medium"
        }
    )

    assert response.status_code == 400

    assert (
        response.json()["detail"]
        == "Maximum limit of 5 questions reached"
    )


# =========================================================
# ANSWER TESTS
# =========================================================

def test_create_answer(interview):

    question_id = (
        interview["first_question"]["id"]
    )

    response = client.post(
        f"/questions/{question_id}/answers",
        json={
            "answer":
                "React is a JavaScript library for building user interfaces."
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        data["question_id"]
        == question_id
    )

    assert (
        data["answer"]
        ==
        "React is a JavaScript library for building user interfaces."
    )


def test_empty_answer_is_allowed(
    interview
):

    question_id = (
        interview["first_question"]["id"]
    )

    response = client.post(
        f"/questions/{question_id}/answers",
        json={
            "answer": ""
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        data["question_id"]
        == question_id
    )

    assert (
        data["answer"]
        == ""
    )


def test_duplicate_answer(
    interview
):

    question_id = (
        interview["first_question"]["id"]
    )

    first_response = client.post(
        f"/questions/{question_id}/answers",
        json={
            "answer": "First answer"
        }
    )

    assert (
        first_response.status_code
        == 200
    )

    second_response = client.post(
        f"/questions/{question_id}/answers",
        json={
            "answer": "Second answer"
        }
    )

    assert (
        second_response.status_code
        == 409
    )

    assert (
        second_response.json()["detail"]
        ==
        "Question has already been answered"
    )


def test_invalid_question_answer():

    response = client.post(
        "/questions/999999/answers",
        json={
            "answer": "Test answer"
        }
    )

    assert response.status_code == 404


# =========================================================
# EVALUATION TESTS
# =========================================================

def test_evaluate_answer(
    interview,
    monkeypatch
):

    question_id = (
        interview["first_question"]["id"]
    )

    answer = answer_question(
        question_id,
        "React is a JavaScript library."
    )

    data = evaluate_question(
        answer["id"],
        monkeypatch,
        score=8.0,
        feedback="Good answer.",
        strengths="Correct understanding.",
        weaknesses="Could provide more detail."
    )

    assert (
        data["answer_id"]
        == answer["id"]
    )

    assert data["score"] == 8.0

    assert (
        data["feedback"]
        == "Good answer."
    )

    assert (
        data["strengths"]
        == "Correct understanding."
    )

    assert (
        data["weaknesses"]
        == "Could provide more detail."
    )


def test_evaluate_empty_answer(
    interview,
    monkeypatch
):

    question_id = (
        interview["first_question"]["id"]
    )

    answer = answer_question(
        question_id,
        ""
    )

    data = evaluate_question(
        answer["id"],
        monkeypatch,
        score=0.0,
        feedback="No answer was provided.",
        strengths="No strengths could be evaluated.",
        weaknesses="The question was not answered."
    )

    assert data["score"] == 0.0

    assert (
        data["feedback"]
        == "No answer was provided for this question."
    )


def test_evaluate_answer_updates_difficulty(
    interview,
    monkeypatch
):

    question_id = (
        interview["first_question"]["id"]
    )

    answer = answer_question(
        question_id,
        "Excellent React answer."
    )

    evaluate_question(
        answer["id"],
        monkeypatch,
        score=9.0,
        feedback="Excellent.",
        strengths="Very thorough.",
        weaknesses="None."
    )

    response = client.get(
        f"/interviews/{interview['session_id']}"
    )

    assert response.status_code == 200

    assert (
        response.json()["difficulty"]
        == "hard"
    )


def test_weak_answer_decreases_difficulty(
    monkeypatch
):

    data = create_test_interview(
        monkeypatch
    )

    try:

        session_id = data["session_id"]

        question = start_test_interview(
            session_id,
            monkeypatch
        )

        answer = answer_question(
            question["id"],
            "I don't know."
        )

        evaluate_question(
            answer["id"],
            monkeypatch,
            score=3.0,
            feedback="Needs improvement.",
            strengths="Attempted an answer.",
            weaknesses="Limited understanding."
        )

        response = client.get(
            f"/interviews/{session_id}"
        )

        assert response.status_code == 200

        assert (
            response.json()["difficulty"]
            == "easy"
        )

    finally:

        cleanup_interview(
            session_id
        )


def test_zero_score_real_answer_is_still_answered(
    interview,
    monkeypatch
):

    monkeypatch.setattr(
        "app.main.generate_final_report",
        lambda role,
        topic,
        average_score,
        evaluated_answers:
            mock_final_report()
    )

    question_id = (
        interview["first_question"]["id"]
    )

    answer = answer_question(
        question_id,
        "Wrong but non-empty answer"
    )

    evaluate_question(
        answer["id"],
        monkeypatch,
        score=0.0,
        feedback="Incorrect answer.",
        strengths="Attempted an answer.",
        weaknesses="Concept is not understood."
    )

    # We need all 5 questions to get a report.
    session_id = interview["session_id"]

    for question_number in range(1, 5):

        if question_number > 1:

            current_question = (
                client.post(
                    f"/interviews/{session_id}/generate-question"
                )
            )

            assert (
                current_question.status_code
                == 200
            )

            current_question = (
                current_question.json()
            )

        else:

            current_question = (
                interview["first_question"]
            )

        if question_number == 1:
            continue

        answer = answer_question(
            current_question["id"],
            "Another answer"
        )

        evaluate_question(
            answer["id"],
            monkeypatch,
            score=8.0
        )

    # Generate Q5.
    current_question = client.post(
        f"/interviews/{session_id}/generate-question"
    )

    assert (
        current_question.status_code
        == 200
    )

    current_question = (
        current_question.json()
    )

    assert (
        current_question["question_number"]
        == 5
    )

    answer = answer_question(
        current_question["id"],
        "Final answer"
    )

    evaluate_question(
        answer["id"],
        monkeypatch,
        score=8.0
    )

    # Report should count Q1 even though its score is 0.
    report_response = client.get(
        f"/interviews/{session_id}/report"
    )

    assert (
        report_response.status_code
        == 200
    )

    report = report_response.json()

    assert (
        report["total_questions"]
        == 5
    )

    assert (
        report["answered_questions"]
        == 5
    )


def test_duplicate_evaluation_correct(
    interview,
    monkeypatch
):

    question_id = (
        interview["first_question"]["id"]
    )

    answer = answer_question(
        question_id,
        "React answer"
    )

    monkeypatch.setattr(
        "app.main.evaluate_answer",
        lambda question, answer:
            mock_evaluation()
    )

    first_response = client.post(
        f"/answers/{answer['id']}/evaluate"
    )

    assert (
        first_response.status_code
        == 200
    )

    second_response = client.post(
        f"/answers/{answer['id']}/evaluate"
    )

    assert (
        second_response.status_code
        == 409
    )

    assert (
        second_response.json()["detail"]
        == "Answer has already been evaluated"
    )


def test_invalid_answer_evaluation():

    response = client.post(
        "/answers/999999/evaluate"
    )

    assert response.status_code == 404


# =========================================================
# NEXT QUESTION TESTS
# =========================================================

def test_generate_next_question_before_answer(
    interview
):

    session_id = interview["session_id"]

    response = client.post(
        f"/interviews/{session_id}/generate-question"
    )

    assert response.status_code == 400

    assert (
        response.json()["detail"]
        ==
        (
            "Previous question must be answered "
            "and evaluated before generating "
            "the next question"
        )
    )


def test_generate_next_question_before_evaluation(
    interview
):

    session_id = interview["session_id"]

    question_id = (
        interview["first_question"]["id"]
    )

    answer = answer_question(
        question_id,
        "Test answer"
    )

    assert answer["id"] is not None

    response = client.post(
        f"/interviews/{session_id}/generate-question"
    )

    assert response.status_code == 400

    assert (
        response.json()["detail"]
        ==
        (
            "Previous question must be answered "
            "and evaluated before generating "
            "the next question"
        )
    )


def test_generate_question(
    interview,
    monkeypatch
):

    session_id = interview["session_id"]

    question_id = (
        interview["first_question"]["id"]
    )

    answer = answer_question(
        question_id,
        "Virtual DOM answer"
    )

    monkeypatch.setattr(
        "app.main.evaluate_answer",
        lambda question, answer:
            mock_evaluation(
                score=8.0
            )
    )

    evaluation_response = client.post(
        f"/answers/{answer['id']}/evaluate"
    )

    assert (
        evaluation_response.status_code
        == 200
    )

    monkeypatch.setattr(
        "app.main.generate_question",
        lambda role,
        topic,
        difficulty,
        interview_history:
            "Explain the Virtual DOM in React."
    )

    response = client.post(
        f"/interviews/{session_id}/generate-question"
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        data["question"]
        == "Explain the Virtual DOM in React."
    )

    assert (
        data["question_number"]
        == 2
    )


def test_generate_next_question_receives_history(
    interview,
    monkeypatch
):

    session_id = interview["session_id"]

    question_id = (
        interview["first_question"]["id"]
    )

    answer = answer_question(
        question_id,
        "React is a JavaScript library."
    )

    def mock_evaluator(
        question,
        answer
    ):

        return mock_evaluation(
            score=9.0,
            feedback="Excellent answer.",
            strengths="Strong understanding.",
            weaknesses="Could mention examples."
        )

    monkeypatch.setattr(
        "app.main.evaluate_answer",
        mock_evaluator
    )

    evaluation_response = client.post(
        f"/answers/{answer['id']}/evaluate"
    )

    assert (
        evaluation_response.status_code
        == 200
    )

    captured_history = {}

    def capture_question(
        role,
        topic,
        difficulty,
        interview_history
    ):

        captured_history["role"] = role
        captured_history["topic"] = topic
        captured_history["difficulty"] = difficulty
        captured_history["history"] = interview_history

        return "Explain React reconciliation."

    monkeypatch.setattr(
        "app.main.generate_question",
        capture_question
    )

    response = client.post(
        f"/interviews/{session_id}/generate-question"
    )

    assert response.status_code == 200

    assert len(
        captured_history["history"]
    ) == 1

    history = (
        captured_history["history"][0]
    )

    assert (
        history["question"]
        == "What is React?"
    )

    assert (
        history["answer"]
        == "React is a JavaScript library."
    )

    assert history["score"] == 9.0

    assert (
        history["feedback"]
        == "Excellent answer."
    )

    assert (
        captured_history["difficulty"]
        == "hard"
    )


def test_invalid_generate_question():

    response = client.post(
        "/interviews/"
        "00000000-0000-0000-0000-000000000000/"
        "generate-question"
    )

    assert response.status_code == 404


# =========================================================
# SKIP QUESTION TESTS
# =========================================================

def test_skip_question(
    interview
):

    session_id = interview["session_id"]

    question_id = (
        interview["first_question"]["id"]
    )

    response = client.post(
        f"/questions/{question_id}/skip"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["score"] == 0.0

    next_response = client.post(
        f"/interviews/{session_id}/generate-question"
    )

    assert (
        next_response.status_code
        == 200
    )

    assert (
        next_response.json()["question_number"]
        == 2
    )


def test_skip_question_creates_zero_score(
    interview
):

    question_id = (
        interview["first_question"]["id"]
    )

    response = client.post(
        f"/questions/{question_id}/skip"
    )

    assert response.status_code == 200

    db = SessionLocal()

    try:

        answer = (
            db.query(models.CandidateAnswer)
            .filter(
                models.CandidateAnswer.question_id
                == question_id
            )
            .first()
        )

        assert answer is not None

        assert answer.answer == ""

        evaluation = (
            db.query(models.AnswerEvaluation)
            .filter(
                models.AnswerEvaluation.answer_id
                == answer.id
            )
            .first()
        )

        assert evaluation is not None

        assert evaluation.score == 0.0

    finally:

        db.close()


def test_duplicate_skip(
    interview
):

    question_id = (
        interview["first_question"]["id"]
    )

    first_response = client.post(
        f"/questions/{question_id}/skip"
    )

    assert first_response.status_code == 200

    second_response = client.post(
        f"/questions/{question_id}/skip"
    )

    assert second_response.status_code == 409


# =========================================================
# FIVE QUESTION FLOW HELPER
# =========================================================

def complete_five_questions(
    session_id,
    monkeypatch,
    answer_text="Test answer",
    score=8.0
):

    monkeypatch.setattr(
        "app.main.generate_question",
        lambda role,
        topic,
        difficulty,
        interview_history:
            "Next interview question."
    )

    monkeypatch.setattr(
        "app.main.evaluate_answer",
        lambda question, answer:
            mock_evaluation(
                score=score
            )
    )

    monkeypatch.setattr(
        "app.main.generate_final_report",
        lambda role,
        topic,
        average_score,
        evaluated_answers:
            mock_final_report()
    )

    current_question = client.post(
        f"/interviews/{session_id}/start"
    )

    assert (
        current_question.status_code
        == 200
    )

    current_question = (
        current_question.json()
    )

    for question_number in range(1, 6):

        answer = answer_question(
            current_question["id"],
            answer_text
        )

        evaluation_response = client.post(
            f"/answers/{answer['id']}/evaluate"
        )

        assert (
            evaluation_response.status_code
            == 200
        )

        if question_number < 5:

            next_response = client.post(
                f"/interviews/{session_id}/generate-question"
            )

            assert (
                next_response.status_code
                == 200
            )

            current_question = (
                next_response.json()
            )

    return current_question


# =========================================================
# FIVE QUESTION LIMIT
# =========================================================

def test_question_limit(
    monkeypatch
):

    data = create_test_interview(
        monkeypatch
    )

    session_id = data["session_id"]

    try:

        complete_five_questions(
            session_id,
            monkeypatch
        )

        questions_response = client.get(
            f"/interviews/{session_id}/questions"
        )

        assert (
            questions_response.status_code
            == 200
        )

        questions = (
            questions_response.json()
        )

        assert len(questions) == 5

        assert (
            questions[-1]["question_number"]
            == 5
        )

        interview_response = client.get(
            f"/interviews/{session_id}"
        )

        assert (
            interview_response.json()["status"]
            == "completed"
        )

        # Q6 is impossible.
        response = client.post(
            f"/interviews/{session_id}/generate-question"
        )

        assert response.status_code == 409

        assert (
            response.json()["detail"]
            == "Interview is already completed"
        )

    finally:

        cleanup_interview(
            session_id
        )


# =========================================================
# AUTO COMPLETE AFTER Q5
# =========================================================

def test_interview_auto_completes_after_question_5(
    monkeypatch
):

    data = create_test_interview(
        monkeypatch
    )

    session_id = data["session_id"]

    try:

        final_question = complete_five_questions(
            session_id,
            monkeypatch
        )

        assert (
            final_question["question_number"]
            == 5
        )

        interview_response = client.get(
            f"/interviews/{session_id}"
        )

        assert (
            interview_response.status_code
            == 200
        )

        assert (
            interview_response.json()["status"]
            == "completed"
        )

        report_response = client.get(
            f"/interviews/{session_id}/report"
        )

        assert (
            report_response.status_code
            == 200
        )

        report = (
            report_response.json()
        )

        assert (
            report["status"]
            == "completed"
        )

        assert (
            report["total_questions"]
            == 5
        )

        assert (
            report["answered_questions"]
            == 5
        )

        assert (
            report["average_score"]
            == 8.0
        )

    finally:

        cleanup_interview(
            session_id
        )


# =========================================================
# Q5 EMPTY ANSWER
# =========================================================

def test_empty_answer_on_question_5_completes_interview(
    monkeypatch
):

    data = create_test_interview(
        monkeypatch
    )

    session_id = data["session_id"]

    try:

        monkeypatch.setattr(
            "app.main.generate_question",
            lambda role,
            topic,
            difficulty,
            interview_history:
                "Next interview question."
        )

        monkeypatch.setattr(
            "app.main.evaluate_answer",
            lambda question, answer:
                mock_evaluation(
                    score=0.0
                    if answer.strip() == ""
                    else 8.0
                )
        )

        monkeypatch.setattr(
            "app.main.generate_final_report",
            lambda *args, **kwargs:
                mock_final_report()
        )

        current_question = client.post(
            f"/interviews/{session_id}/start"
        ).json()

        # Q1-Q4 answered.
        for question_number in range(1, 5):

            answer = answer_question(
                current_question["id"],
                "Good answer."
            )

            evaluation_response = client.post(
                f"/answers/{answer['id']}/evaluate"
            )

            assert (
                evaluation_response.status_code
                == 200
            )

            next_response = client.post(
                f"/interviews/{session_id}/generate-question"
            )

            assert (
                next_response.status_code
                == 200
            )

            current_question = (
                next_response.json()
            )

        # Q5 empty.
        assert (
            current_question["question_number"]
            == 5
        )

        answer = answer_question(
            current_question["id"],
            ""
        )

        evaluation_response = client.post(
            f"/answers/{answer['id']}/evaluate"
        )

        assert (
            evaluation_response.status_code
            == 200
        )

        assert (
            evaluation_response.json()["score"]
            == 0.0
        )

        interview_response = client.get(
            f"/interviews/{session_id}"
        )

        assert (
            interview_response.json()["status"]
            == "completed"
        )

        report_response = client.get(
            f"/interviews/{session_id}/report"
        )

        assert (
            report_response.status_code
            == 200
        )

        report = (
            report_response.json()
        )

        assert (
            report["total_questions"]
            == 5
        )

        # Q5 was empty.
        assert (
            report["answered_questions"]
            == 4
        )

        # Four answers scored 8.
        assert (
            report["average_score"]
            == 8.0
        )

        assert (
            report["questions"][4]["answer"]
            is None
        )

        assert (
            report["questions"][4]["score"]
            == 0.0
        )

    finally:

        cleanup_interview(
            session_id
        )


# =========================================================
# FIVE SKIPPED QUESTIONS
# =========================================================

def test_five_skipped_questions_auto_complete(
    monkeypatch
):

    data = create_test_interview(
        monkeypatch
    )

    session_id = data["session_id"]

    try:

        monkeypatch.setattr(
            "app.main.generate_question",
            lambda role,
            topic,
            difficulty,
            interview_history:
                "Next interview question."
        )

        # Should NOT be called when zero real answers exist.
        def fail_if_called(*args, **kwargs):

            pytest.fail(
                "Final AI report generator should not "
                "be called when no actual answers exist."
            )

        monkeypatch.setattr(
            "app.main.generate_final_report",
            fail_if_called
        )

        current_question = client.post(
            f"/interviews/{session_id}/start"
        ).json()

        for question_number in range(1, 6):

            skip_response = client.post(
                f"/questions/{current_question['id']}/skip"
            )

            assert (
                skip_response.status_code
                == 200
            )

            if question_number < 5:

                next_response = client.post(
                    f"/interviews/{session_id}/generate-question"
                )

                assert (
                    next_response.status_code
                    == 200
                )

                current_question = (
                    next_response.json()
                )

        interview_response = client.get(
            f"/interviews/{session_id}"
        )

        assert (
            interview_response.json()["status"]
            == "completed"
        )

        report_response = client.get(
            f"/interviews/{session_id}/report"
        )

        assert (
            report_response.status_code
            == 200
        )

        report = (
            report_response.json()
        )

        assert (
            report["total_questions"]
            == 5
        )

        assert (
            report["answered_questions"]
            == 0
        )

        assert (
            report["average_score"]
            == 0.0
        )

        assert (
            report["overall_feedback"]
            ==
            "The candidate did not answer "
            "any interview questions."
        )

        assert (
            report["strongest_question"]
            is None
        )

        assert (
            report["weakest_question"]
            is None
        )

    finally:

        cleanup_interview(
            session_id
        )


# =========================================================
# REPORT TESTS
# =========================================================

def test_report_not_available_before_completion(
    interview
):

    session_id = interview["session_id"]

    response = client.get(
        f"/interviews/{session_id}/report"
    )

    assert response.status_code == 404


def test_invalid_report():

    response = client.get(
        "/interviews/"
        "00000000-0000-0000-0000-000000000000/"
        "report"
    )

    assert response.status_code == 404


def test_get_report_after_completion(
    monkeypatch
):

    data = create_test_interview(
        monkeypatch
    )

    session_id = data["session_id"]

    try:

        complete_five_questions(
            session_id,
            monkeypatch
        )

        response = client.get(
            f"/interviews/{session_id}/report"
        )

        assert (
            response.status_code
            == 200
        )

        report = (
            response.json()
        )

        assert (
            report["session_id"]
            == session_id
        )

        assert (
            report["role"]
            == "frontend developer"
        )

        assert (
            report["topic"]
            == "react"
        )

        assert (
            report["status"]
            == "completed"
        )

        assert (
            report["total_questions"]
            == 5
        )

        assert (
            report["answered_questions"]
            == 5
        )

        assert (
            report["average_score"]
            == 8.0
        )

        assert (
            report["overall_feedback"]
            == "Good overall performance."
        )

        assert (
            report["strengths"]
            == "Strong fundamentals."
        )

        assert (
            report["weaknesses"]
            == "Needs more depth."
        )

        assert (
            report["recommendations"]
            == "Practice more."
        )

        assert (
            report["strongest_question"]
            is not None
        )

        assert (
            report["weakest_question"]
            is not None
        )

        assert (
            len(report["questions"])
            == 5
        )

    finally:

        cleanup_interview(
            session_id
        )


def test_report_strongest_and_weakest_ignore_skipped(
    monkeypatch
):

    data = create_test_interview(
        monkeypatch
    )

    session_id = data["session_id"]

    try:

        monkeypatch.setattr(
            "app.main.generate_question",
            lambda role,
            topic,
            difficulty,
            interview_history:
                "Next interview question."
        )

        monkeypatch.setattr(
            "app.main.generate_final_report",
            lambda *args, **kwargs:
                mock_final_report()
        )

        scores = [
            8.0,
            4.0,
            None,
            7.0,
            9.0
        ]

        current_question = client.post(
            f"/interviews/{session_id}/start"
        ).json()

        for index in range(5):

            score = scores[index]

            if score is None:

                skip_response = client.post(
                    f"/questions/{current_question['id']}/skip"
                )

                assert (
                    skip_response.status_code
                    == 200
                )

            else:

                answer = answer_question(
                    current_question["id"],
                    "Real answer"
                )

                monkeypatch.setattr(
                    "app.main.evaluate_answer",
                    lambda question, answer,
                    score=score:
                        mock_evaluation(
                            score=score
                        )
                )

                evaluation_response = client.post(
                    f"/answers/{answer['id']}/evaluate"
                )

                assert (
                    evaluation_response.status_code
                    == 200
                )

            if index < 4:

                next_response = client.post(
                    f"/interviews/{session_id}/generate-question"
                )

                assert (
                    next_response.status_code
                    == 200
                )

                current_question = (
                    next_response.json()
                )

        report_response = client.get(
            f"/interviews/{session_id}/report"
        )

        assert (
            report_response.status_code
            == 200
        )

        report = (
            report_response.json()
        )

        assert (
            report["strongest_question"]["score"]
            == 9.0
        )

        assert (
            report["weakest_question"]["score"]
            == 4.0
        )

    finally:

        cleanup_interview(
            session_id
        )


# =========================================================
# MANUAL COMPLETE ENDPOINT
# =========================================================

def test_manual_complete_before_five_questions_fails(
    interview
):

    session_id = interview["session_id"]

    response = client.post(
        f"/interviews/{session_id}/complete"
    )

    assert response.status_code == 400

    assert (
        response.json()["detail"]
        ==
        (
            "Interview can only be completed "
            "after exactly 5 questions exist"
        )
    )


def test_complete_invalid_interview():

    response = client.post(
        "/interviews/"
        "00000000-0000-0000-0000-000000000000/"
        "complete"
    )

    assert response.status_code == 404


# =========================================================
# ABANDON INTERVIEW
# =========================================================

def test_abandon_interview(
    interview
):

    session_id = interview["session_id"]

    response = client.post(
        f"/interviews/{session_id}/abandon"
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        data["session_id"]
        == session_id
    )

    assert (
        data["status"]
        == "abandoned"
    )

    assert (
        data["message"]
        == "Interview abandoned successfully"
    )


def test_abandon_updates_database_status(
    interview
):

    session_id = interview["session_id"]

    response = client.post(
        f"/interviews/{session_id}/abandon"
    )

    assert response.status_code == 200

    db = SessionLocal()

    try:

        interview_db = (
            db.query(models.InterviewSession)
            .filter(
                models.InterviewSession.session_id
                == session_id
            )
            .first()
        )

        assert interview_db is not None

        assert (
            interview_db.status
            == "abandoned"
        )

    finally:

        db.close()


def test_abandon_interview_twice(
    interview
):

    session_id = interview["session_id"]

    first_response = client.post(
        f"/interviews/{session_id}/abandon"
    )

    assert first_response.status_code == 200

    second_response = client.post(
        f"/interviews/{session_id}/abandon"
    )

    assert second_response.status_code == 409

    assert (
        second_response.json()["detail"]
        == "Interview is already abandoned"
    )


def test_abandoned_interview_cannot_start(
    interview
):

    session_id = interview["session_id"]

    response = client.post(
        f"/interviews/{session_id}/abandon"
    )

    assert response.status_code == 200

    response = client.post(
        f"/interviews/{session_id}/start"
    )

    assert response.status_code == 409

    assert (
        response.json()["detail"]
        == "Interview is already abandoned"
    )


def test_abandoned_interview_cannot_answer(
    interview
):

    session_id = interview["session_id"]

    question_id = (
        interview["first_question"]["id"]
    )

    response = client.post(
        f"/interviews/{session_id}/abandon"
    )

    assert response.status_code == 200

    response = client.post(
        f"/questions/{question_id}/answers",
        json={
            "answer": "Late answer"
        }
    )

    assert response.status_code == 409

    assert (
        response.json()["detail"]
        == "Interview is already abandoned"
    )


def test_abandoned_interview_cannot_evaluate(
    interview,
    monkeypatch
):

    session_id = interview["session_id"]

    question_id = (
        interview["first_question"]["id"]
    )

    answer = answer_question(
        question_id,
        "Test answer"
    )

    response = client.post(
        f"/interviews/{session_id}/abandon"
    )

    assert response.status_code == 200

    monkeypatch.setattr(
        "app.main.evaluate_answer",
        lambda question, answer:
            mock_evaluation()
    )

    response = client.post(
        f"/answers/{answer['id']}/evaluate"
    )

    assert response.status_code == 409

    assert (
        response.json()["detail"]
        == "Interview is already abandoned"
    )


def test_abandoned_interview_cannot_generate_question(
    interview
):

    session_id = interview["session_id"]

    response = client.post(
        f"/interviews/{session_id}/abandon"
    )

    assert response.status_code == 200

    response = client.post(
        f"/interviews/{session_id}/generate-question"
    )

    assert response.status_code == 409

    assert (
        response.json()["detail"]
        == "Interview is already abandoned"
    )


def test_abandoned_interview_cannot_complete(
    interview
):

    session_id = interview["session_id"]

    response = client.post(
        f"/interviews/{session_id}/abandon"
    )

    assert response.status_code == 200

    response = client.post(
        f"/interviews/{session_id}/complete"
    )

    assert response.status_code == 409

    assert (
        response.json()["detail"]
        == "Interview is already abandoned"
    )


def test_abandon_completed_interview(
    monkeypatch
):

    data = create_test_interview(
        monkeypatch
    )

    session_id = data["session_id"]

    try:

        complete_five_questions(
            session_id,
            monkeypatch
        )

        response = client.post(
            f"/interviews/{session_id}/abandon"
        )

        assert response.status_code == 409

        assert (
            response.json()["detail"]
            == "Interview is already completed"
        )

    finally:

        cleanup_interview(
            session_id
        )


def test_invalid_abandon_interview():

    response = client.post(
        "/interviews/"
        "00000000-0000-0000-0000-000000000000/"
        "abandon"
    )

    assert response.status_code == 404


# =========================================================
# GET ABANDONED INTERVIEW
# =========================================================

def test_get_abandoned_interview(
    interview
):

    session_id = interview["session_id"]

    response = client.post(
        f"/interviews/{session_id}/abandon"
    )

    assert response.status_code == 200

    response = client.get(
        f"/interviews/{session_id}"
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        data["session_id"]
        == session_id
    )

    assert (
        data["status"]
        == "abandoned"
    )


# =========================================================
# ABANDONED INTERVIEW HAS NO REPORT
# =========================================================

def test_abandoned_interview_has_no_report(
    interview
):

    session_id = interview["session_id"]

    response = client.post(
        f"/interviews/{session_id}/abandon"
    )

    assert response.status_code == 200

    report_response = client.get(
        f"/interviews/{session_id}/report"
    )

    assert (
        report_response.status_code
        == 404
    )


# =========================================================
# COMPLETED INTERVIEW PROTECTION
# =========================================================

def test_answer_after_completion(
    monkeypatch
):

    data = create_test_interview(
        monkeypatch
    )

    session_id = data["session_id"]

    try:

        complete_five_questions(
            session_id,
            monkeypatch
        )

        questions = client.get(
            f"/interviews/{session_id}/questions"
        ).json()

        question_id = questions[0]["id"]

        response = client.post(
            f"/questions/{question_id}/answers",
            json={
                "answer": "Late answer"
            }
        )

        assert response.status_code == 409

        assert (
            response.json()["detail"]
            == "Interview is already completed"
        )

    finally:

        cleanup_interview(
            session_id
        )


def test_generate_question_after_completion(
    monkeypatch
):

    data = create_test_interview(
        monkeypatch
    )

    session_id = data["session_id"]

    try:

        complete_five_questions(
            session_id,
            monkeypatch
        )

        response = client.post(
            f"/interviews/{session_id}/generate-question"
        )

        assert response.status_code == 409

        assert (
            response.json()["detail"]
            == "Interview is already completed"
        )

    finally:

        cleanup_interview(
            session_id
        )


def test_evaluate_after_completion(
    monkeypatch
):

    data = create_test_interview(
        monkeypatch
    )

    session_id = data["session_id"]

    try:

        complete_five_questions(
            session_id,
            monkeypatch
        )

        questions = client.get(
            f"/interviews/{session_id}/questions"
        ).json()

        question_id = questions[-1]["id"]

        # Existing Q5 already has an answer/evaluation.
        # Get that answer from DB.

        db = SessionLocal()

        try:

            question = (
                db.query(
                    models.InterviewQuestion
                )
                .filter(
                    models.InterviewQuestion.id
                    == question_id
                )
                .first()
            )

            answer = (
                db.query(
                    models.CandidateAnswer
                )
                .filter(
                    models.CandidateAnswer.question_id
                    == question.id
                )
                .first()
            )

            answer_id = answer.id

        finally:

            db.close()

        response = client.post(
            f"/answers/{answer_id}/evaluate"
        )

        assert response.status_code == 409

        assert (
            response.json()["detail"]
            == "Answer has already been evaluated"
        )

    finally:

        cleanup_interview(
            session_id
        )


# =========================================================
# MAIN END-TO-END FLOW
# =========================================================

def test_complete_interview_end_to_end(
    monkeypatch
):

    data = create_test_interview(
        monkeypatch
    )

    session_id = data["session_id"]

    try:

        # ---------------------------------------------
        # Mock all AI components
        # ---------------------------------------------

        monkeypatch.setattr(
            "app.main.generate_question",
            lambda role,
            topic,
            difficulty,
            interview_history:
                "What is React?"
        )

        monkeypatch.setattr(
            "app.main.evaluate_answer",
            lambda question, answer:
                mock_evaluation(
                    score=8.0,
                    feedback="Good answer.",
                    strengths="Good fundamentals.",
                    weaknesses="Could provide more depth."
                )
        )

        monkeypatch.setattr(
            "app.main.generate_final_report",
            lambda role,
            topic,
            average_score,
            evaluated_answers:
                mock_final_report(
                    overall_feedback="Strong interview.",
                    strengths="Good React knowledge.",
                    weaknesses="Needs advanced practice.",
                    recommendations="Practice more React patterns."
                )
        )

        # ---------------------------------------------
        # Start
        # ---------------------------------------------

        start_response = client.post(
            f"/interviews/{session_id}/start"
        )

        assert (
            start_response.status_code
            == 200
        )

        current_question = (
            start_response.json()
        )

        # ---------------------------------------------
        # Q1 -> Q5
        # ---------------------------------------------

        for question_number in range(1, 6):

            assert (
                current_question["question_number"]
                == question_number
            )

            answer = answer_question(
                current_question["id"],
                f"Answer {question_number}"
            )

            evaluation_response = client.post(
                f"/answers/{answer['id']}/evaluate"
            )

            assert (
                evaluation_response.status_code
                == 200
            )

            if question_number < 5:

                next_response = client.post(
                    f"/interviews/{session_id}/generate-question"
                )

                assert (
                    next_response.status_code
                    == 200
                )

                current_question = (
                    next_response.json()
                )

        # ---------------------------------------------
        # Completed
        # ---------------------------------------------

        interview_response = client.get(
            f"/interviews/{session_id}"
        )

        assert (
            interview_response.status_code
            == 200
        )

        interview_data = (
            interview_response.json()
        )

        assert (
            interview_data["status"]
            == "completed"
        )

        # ---------------------------------------------
        # Report
        # ---------------------------------------------

        report_response = client.get(
            f"/interviews/{session_id}/report"
        )

        assert (
            report_response.status_code
            == 200
        )

        report = (
            report_response.json()
        )

        assert (
            report["status"]
            == "completed"
        )

        assert (
            report["total_questions"]
            == 5
        )

        assert (
            report["answered_questions"]
            == 5
        )

        assert (
            report["average_score"]
            == 8.0
        )

        assert (
            report["overall_feedback"]
            == "Strong interview."
        )

        assert (
            report["strengths"]
            == "Good React knowledge."
        )

        assert (
            report["weaknesses"]
            == "Needs advanced practice."
        )

        assert (
            report["recommendations"]
            == "Practice more React patterns."
        )

        assert (
            len(report["questions"])
            == 5
        )

    finally:

        cleanup_interview(
            session_id
        )