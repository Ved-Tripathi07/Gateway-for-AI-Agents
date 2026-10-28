
from langchain_litellm import ChatLiteLLM
from langchain_core.messages import HumanMessage

from Observability.observability import (
    create_request_context,
    build_model_metadata,
)
from settings import TIERS

DEFAULT_MODEL = TIERS["simple"][0]


def run_request(
    prompt: str,
    user_id: str,
    session_id: str,
    model: str = DEFAULT_MODEL,
):
    context = create_request_context(
        user_id=user_id,
        session_id=session_id,
    )

    chat = ChatLiteLLM(
        model=model,
        model_kwargs={
            "metadata": build_model_metadata(context),
        },
    )

    try:
        response = chat.invoke([
            HumanMessage(content=prompt)
        ])

        return {
            "request_id": context["request_id"],
            "model": model,
            "response": response.content,
            "status": "success",
        }

    except Exception:
        # Do not swallow errors; preserve the original exception.
        raise


if __name__ == "__main__":
    result = run_request(
        prompt="What model are you?",
        user_id="user-101",
        session_id="conversation-001",
    )

    print("Request ID:", result["request_id"])
    print("Status:", result["status"])
    print("Model:", result["model"])
    print("Response:", result["response"])
