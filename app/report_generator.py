from groq import Groq
from dotenv import load_dotenv
from pathlib import Path
import os

from app.schemas import FinalReportCreate


# =========================================================
# ENVIRONMENT
# =========================================================

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found in .env")


# =========================================================
# GROQ CLIENT
# =========================================================

client = Groq(
    api_key=GROQ_API_KEY
)


# =========================================================
# FINAL REPORT
# =========================================================

def generate_final_report(
    role: str,
    topic: str,
    average_score: float,
    evaluated_answers: list[dict]
) -> FinalReportCreate:

    answers_text = "\n\n".join(
        f"""
Question {answer["question_number"]}:
{answer["question"]}

Score:
{answer["score"]}/10

Feedback:
{answer["feedback"]}

Strengths:
{answer["strengths"]}

Weaknesses:
{answer["weaknesses"]}
"""
        for answer in evaluated_answers
    )

    prompt = f"""
You are an expert technical interviewer.

Generate a final interview performance report.

Interview Role:
{role}

Interview Topic:
{topic}

Average Score:
{average_score}/10

Individual Evaluations:
{answers_text}

Analyze the candidate's overall performance.

Return ONLY valid JSON:

{{
    "overall_feedback": "string",
    "strengths": "string",
    "weaknesses": "string",
    "recommendations": "string"
}}

Requirements:

1. Give constructive and specific feedback.
2. Identify patterns across the interview.
3. Do not simply repeat individual feedback.
4. Recommendations must be actionable.
5. Base your analysis only on the interview results provided.
"""

    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",

        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],

        response_format={
            "type": "json_object"
        }
    )

    content = response.choices[0].message.content

    if not content:
        raise ValueError(
            "Groq returned an empty final report"
        )

    return FinalReportCreate.model_validate_json(
        content
    )