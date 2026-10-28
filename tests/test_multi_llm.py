from llm_gateway import LLMClient

client = LLMClient("gemini/gemini-3.6-flash")

response = client.chat(
    messages=[
        {"role": "user", "content": "What is an LLM gateway?"}
    ],
    tracing=True,
    user_id="vedtripathi07",
    session_id="chat-session-001",
)

print(response.choices[0].message.content)
