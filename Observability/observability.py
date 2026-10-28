
import os
import uuid

import litellm
from dotenv import load_dotenv

from settings import OBSERVABILITY

load_dotenv()

REQUIRED_KEYS = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")

TRACING_AVAILABLE = all(os.getenv(key) for key in REQUIRED_KEYS)


def register_callbacks() -> bool:
    """Attach the Langfuse success and failure callbacks once, at startup."""

    if not TRACING_AVAILABLE:
        return False

    for callbacks in (litellm.success_callback, litellm.failure_callback):
        if "langfuse" not in callbacks:
            callbacks.append("langfuse")

    return True


def create_request_context(
    user_id: str,
    session_id: str,
    application: str = OBSERVABILITY["application"],
    environment: str = OBSERVABILITY["environment"],
    tier: str | None = None,
    fallback: bool = False,
) -> dict:
    """Create metadata for one model request."""

    tags = [application, environment]

    if tier:
        tags.append(f"tier:{tier}")

    return {
        "request_id": str(uuid.uuid4()),
        "user_id": user_id,
        "session_id": session_id,
        "application": application,
        "environment": environment,
        "tier": tier,
        "fallback": fallback,
        "tags": tags,
    }


def build_model_metadata(context: dict) -> dict:
    """Build metadata understood by the LiteLLM Langfuse callback."""

    return {
        "trace_user_id": context["user_id"],
        "session_id": context["session_id"],
        "tags": context["tags"],
        "metadata": {
            "request_id": context["request_id"],
            "application": context["application"],
            "environment": context["environment"],
            "tier": context["tier"],
            "fallback": context["fallback"],
        },
    }
