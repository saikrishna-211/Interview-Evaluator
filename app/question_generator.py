from groq import Groq
from dotenv import load_dotenv
from pathlib import Path
import os


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
# REFUSAL DETECTION
# =========================================================

REFUSAL_PHRASES = [

    "i'm sorry, i can't help with that",
    "i’m sorry, i can’t help with that",

    "i cannot help with that",
    "i can't help with that",

    "i am unable to help with that",
    "i’m unable to help with that",

    "i cannot assist with that",
    "i can't assist with that",

    "i am unable to assist with that",
    "i’m unable to assist with that",

    "i cannot generate that",
    "i can't generate that",

    "i am unable to generate that",
    "i’m unable to generate that",

    "sorry, but i can't",
    "sorry, i can't",

    "i cannot comply with that",
    "i can't comply with that",

    "i'm unable to comply with that",
    "i’m unable to comply with that",
]


# =========================================================
# CHECK AI REFUSAL
# =========================================================

def is_refusal_response(
    text: str
) -> bool:

    normalized = (
        text
        .strip()
        .lower()
        .replace("’", "'")
    )

    return any(
        phrase in normalized
        for phrase in REFUSAL_PHRASES
    )


# =========================================================
# GENERATE INTERVIEW QUESTION
# =========================================================

def generate_question(
    role: str,
    topic: str,
    difficulty: str,
    interview_history: list[dict]
) -> str:

    # -----------------------------------------------------
    # Build previous interview history
    # -----------------------------------------------------

    if interview_history:

        history_parts = []

        for item in interview_history:

            history_parts.append(
                f"""
Question {item["question_number"]}:
{item["question"]}

Difficulty:
{item["difficulty"]}

Candidate Answer:
{item["answer"]}

Score:
{item["score"]}/10

Feedback:
{item["feedback"]}

Strengths:
{item["strengths"]}

Weaknesses:
{item["weaknesses"]}
"""
            )

        history_text = "\n".join(
            history_parts
        )

    else:

        history_text = (
            "No previous questions have been asked. "
            "This is the first question."
        )

    # -----------------------------------------------------
    # Prompt
    # -----------------------------------------------------

    prompt = f"""
You are an expert technical interviewer conducting a
real-time adaptive technical interview.

Interview Role:
{role}

Interview Topic:
{topic}

Requested Difficulty:
{difficulty}

Previous Interview History:
{history_text}

Your task is to generate EXACTLY ONE new technical
interview question.

Rules:

1. The question must be directly relevant to the role
   and topic.

2. Do NOT repeat or closely rephrase any previous question.

3. Consider the candidate's previous answers and
   performance when choosing the next question.

4. If the candidate performed poorly:
   - prefer reinforcing fundamentals
   - use a similar or slightly easier concept

5. If the candidate performed reasonably well:
   - keep a similar difficulty or increase it slightly

6. If the candidate performed very well:
   - test deeper understanding
   - increase difficulty when appropriate

7. For the FIRST question:
   - start easy-to-medium
   - test an important fundamental concept
   - do not start with an extremely difficult question

8. The question should be appropriate for the candidate's
   stated role.

9. Ask one clear question only.

10. Do not include:
    - answers
    - explanations
    - hints
    - headings
    - "Question:"
    - introductions

11. Return ONLY the raw interview question.

Generate the next best question now.
"""

    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",

        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],

        temperature=0.7
    )

    question = response.choices[0].message.content

    if not question:
        raise ValueError(
            "Groq returned an empty question"
        )

    question = question.strip()

    # -----------------------------------------------------
    # NEVER store an AI refusal as a question.
    # -----------------------------------------------------

    if is_refusal_response(question):

        raise ValueError(
            "The AI could not generate a suitable interview "
            "question for this role or topic. "
            "Please choose a different role or topic."
        )

    return question