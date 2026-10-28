from langchain_litellm import ChatLiteLLM
from langchain_core.messages import HumanMessage
import os

from Observability.observability import (
    create_request_context,
    build_model_metadata,
)

USER_ID = "vedtripathi07"
SESSION_ID = "chat-session-001"


def main():
    print("Observability Test Chatbot")
    print("Type 'exit' to quit.\n")

    while True:
        question = input("You: ").strip()

        if question.lower() == "exit":
            print("Chat ended.")
            break

        if not question:
            continue

        context = create_request_context(
            user_id=USER_ID,
            session_id=SESSION_ID,
            application="test-chatbot",
            environment="development",
        )

        chat = ChatLiteLLM(
            model=os.getenv("DEFAULT_MODEL"),
            model_kwargs={
                "metadata": build_model_metadata(context),
            },
        )

        try:
            response = chat.invoke([
                HumanMessage(content=question)
            ])

            print(f"\nBot: {response.content}")
            print(f"Request ID: {context['request_id']}\n")

        except Exception as exc:
            print(f"\nRequest failed: {exc}\n")


if __name__ == "__main__":
    main()
