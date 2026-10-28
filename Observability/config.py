
import os
from pathlib import Path
from dotenv import load_dotenv

# .env is located in the LLM-Gateway project root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

REQUIRED_VARS = [
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "GROQ_API_KEY",
]

missing = [key for key in REQUIRED_VARS if not os.getenv(key)]

if missing:
    raise EnvironmentError(
        f"Missing environment variables: {', '.join(missing)}"
    )

LANGFUSE_HOST = os.getenv(
    "LANGFUSE_HOST", "http://localhost:3000"
)