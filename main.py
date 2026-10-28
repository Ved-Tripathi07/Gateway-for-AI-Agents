from llm_gateway import LLMClient


def main():
    client = LLMClient()

    # Tiering off: the model is chosen by the caller.
    response = client.chat(
        messages=[{"role": "user", "content": "Hi"}],
        model="groq/openai/gpt-oss-20b",
    )
    print(f"\nexplicit model -> {response.model}")
    print(response.choices[0].message.content)

    # Tiering on, tier chosen by the caller.
    response = client.chat(
        messages=[{"role": "user", "content": "Hi"}],
        tier=True,
        tier_level="simple",
    )
    print(f"\ntier_level='simple' -> {response.model}")
    print(response.choices[0].message.content)

    # Tiering on, tier classified from the prompt.
    question = (
        "Design a multi-region deployment strategy for an LLM gateway "
        "and compare the trade-offs."
    )
    response = client.chat(
        messages=[{"role": "user", "content": question}],
        tier=True,
    )
    print(f"\nclassified tier -> {response.model}")
    print(response.choices[0].message.content)


if __name__ == "__main__":
    main()
