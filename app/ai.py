from groq import Groq
from dotenv import load_dotenv
from pathlib import Path
import os

from app.schemas import EvaluationCreate


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
# EVALUATE ANSWER
# =========================================================

def evaluate_answer(
    question: str,
    answer: str
) -> EvaluationCreate:

    prompt = f"""
You are an expert technical interviewer.

Evaluate the candidate's answer fairly and objectively.

Question:
{question}

Candidate Answer:
{answer}

Evaluate using:

1. Technical correctness
2. Conceptual understanding
3. Completeness
4. Clarity

Important:
- Give a score from 0 to 10.
- Do not give a high score merely because the answer is long.
- Do not penalize concise answers if they are technically correct.
- Identify exactly what the candidate understood.
- Identify exactly what is missing or incorrect.
- Keep the feedback useful for determining the next interview question.

Return ONLY valid JSON:

{{
    "score": number,
    "feedback": "string",
    "strengths": "string",
    "weaknesses": "string"
}}
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
            "Groq returned an empty evaluation"
        )

    return EvaluationCreate.model_validate_json(
        content
    )