from model_routing import ModelRouter, classify

QUESTIONS = [
    "What is the capital of France?",
    "Design a multi-region deployment strategy for an LLM gateway and compare the trade-offs.",
]

router = ModelRouter()

for tier in sorted(router.tiers):
    print(f"{tier} tier deployments: {router.deployments(tier)}")

print()

for question in QUESTIONS:
    messages = [{"role": "user", "content": question}]
    print(f"{classify(messages)}: {question}")
