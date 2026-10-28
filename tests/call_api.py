import os

import httpx

BASE_URL = os.getenv("GATEWAY_URL", "http://localhost:8080")
API_KEY = os.getenv("GATEWAY_API_KEY")
TIMEOUT = 120


def chat(content: str, **options) -> dict:
    """Send one chat request to the gateway and return the response body."""

    headers = {"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}

    response = httpx.post(
        f"{BASE_URL}/v1/chat/completions",
        json={"messages": [{"role": "user", "content": content}], **options},
        headers=headers,
        timeout=TIMEOUT,
    )
    response.raise_for_status()

    return response.json()


def show(label: str, content: str, **options) -> None:
    try:
        result = chat(content, **options)

    except httpx.HTTPStatusError as exc:
        print(f"{label:16} FAILED {exc.response.status_code} {exc.response.text}\n")
        return

    reply = result["choices"][0]["message"]["content"].strip().replace("\n", " ")
    print(f"{label:16} {result['model']}")
    print(f"{'':16} {reply[:120]}\n")


def main() -> None:
    print(f"gateway: {BASE_URL}\n")
    print("available models:", httpx.get(f"{BASE_URL}/ready", timeout=30).json()["tiers"], "\n")

    show("auto tier", "What is 2 + 2?", tier=True)

    show(
        "forced complex",
        "Compare REST and GraphQL in detail",
        tier=True,
        tier_level="complex",
    )

    show("pinned model", "Say hi in 3 words", model="groq/openai/gpt-oss-20b")

    show(
        "with fallback",
        "Say hi in 3 words",
        model="groq/does-not-exist",
        fallback=True,
    )

    show(
        "traced",
        "Say hi in 3 words",
        tier=True,
        tracing=True,
        user_id="ved-123",
        session_id="demo-session",
    )


if __name__ == "__main__":
    main()
