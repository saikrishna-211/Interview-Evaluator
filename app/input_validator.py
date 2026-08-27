from groq import Groq
from dotenv import load_dotenv
from pathlib import Path
import json
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
# VALIDATE ROLE + TOPIC
# =========================================================

def validate_interview_input(
    role: str,
    topic: str
) -> tuple[bool, str]:

    role = role.strip()
    topic = topic.strip()

    # -----------------------------------------------------
    # Basic validation
    # -----------------------------------------------------

    if not role:
        return False, "Please enter a valid professional role."

    if not topic:
        return False, "Please enter a valid interview topic."

    if len(role) < 2:
        return False, "Please enter a valid professional role."

    if len(topic) < 2:
        return False, "Please enter a valid interview topic."

    # Avoid unreasonable input sizes.
    if len(role) > 150:
        return False, "Please enter a shorter and more specific role."

    if len(topic) > 200:
        return False, "Please enter a shorter and more specific topic."

    # -----------------------------------------------------
    # LLM validation
    # -----------------------------------------------------

    prompt = f"""
You are a validator for a professional AI interview platform.

Role:
{role}

Topic:
{topic}

Decide whether BOTH the role and topic are suitable for
a professional interview.

ACCEPT:
- legitimate professional roles
- legitimate software/technology roles
- legitimate engineering roles
- legitimate data/AI roles
- legitimate cybersecurity roles
- legitimate business/technology roles
- legitimate technical topics
- legitimate computer science topics
- legitimate programming topics
- legitimate professional topics
- legitimate specialized fields

Examples of valid roles:
Python Developer
Backend Developer
Software Engineer
Data Scientist
Machine Learning Engineer
DevOps Engineer
Cybersecurity Analyst
Database Engineer

Examples of valid topics:
Python
FastAPI
SQL
PostgreSQL
Machine Learning
Deep Learning
REST APIs
Data Structures
Algorithms
Docker
AWS
System Design
Operating Systems
Networking

These examples are NOT an exhaustive whitelist.

IMPORTANT:
Do not reject a legitimate professional or technical term
just because one part of the phrase resembles inappropriate
language.

For example:
"penetration testing" is a legitimate cybersecurity topic.

REJECT:
- sexually explicit requests
- vulgar or obscene requests
- hateful requests
- abusive requests
- threatening requests
- requests clearly intended to generate inappropriate content
- meaningless text
- spam
- random keyboard input
- content clearly unrelated to professional interview use

The user is NOT asking you to generate an interview question.
You are ONLY deciding whether the role and topic are appropriate.

Return ONLY valid JSON in this exact structure.

Valid:
{{
    "valid": true,
    "message": "Role and topic are suitable for a professional interview."
}}

Invalid:
{{
    "valid": false,
    "message": "Please enter a valid professional role and interview topic."
}}

Do not include markdown.
Do not include any explanation outside the JSON.
"""

    try:

        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0
        )

        content = response.choices[0].message.content

        if not content:
            raise ValueError(
                "Groq returned an empty validation response"
            )

        content = content.strip()

        # -------------------------------------------------
        # Remove accidental markdown fences
        # -------------------------------------------------

        if content.startswith("```"):

            content = content.replace(
                "```json",
                ""
            )

            content = content.replace(
                "```",
                ""
            )

            content = content.strip()

        result = json.loads(content)

        valid = bool(
            result.get("valid", False)
        )

        message = str(
            result.get(
                "message",
                "Please enter a valid professional role and interview topic."
            )
        )

        return valid, message

    except Exception as error:

        raise RuntimeError(
            "Unable to validate the role and topic right now. "
            "Please try again."
        ) from error