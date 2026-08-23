from groq import Groq
from dotenv import load_dotenv
from pathlib import Path
import os

from app.schemas import EvaluationCreate


# Load .env explicitly
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


# Get API key
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found in .env")


# Create Groq client
client = Groq(
    api_key=GROQ_API_KEY
)


def evaluate_answer(
    question: str,
    answer: str
) -> EvaluationCreate:

    prompt = f"""
You are an expert technical interviewer.

Evaluate the candidate's answer.

Question:
{question}

Candidate Answer:
{answer}

Evaluate based on:

1. Technical correctness
2. Conceptual understanding
3. Completeness
4. Clarity

Score the answer from 0 to 10.

Be fair and objective.

Return the evaluation in this JSON format:

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

    return EvaluationCreate.model_validate_json(content)