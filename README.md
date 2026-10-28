# LLM Gateway

A Python client for sending chat-completion requests to models supported by [LiteLLM](https://docs.litellm.ai/), with opt-in tiered model routing and optional Langfuse tracing. It can be used as a library or run as an HTTP service.

## Features

- Send chat messages through LiteLLM using a provider/model identifier.
- Opt-in tiered routing: cheap models for simple prompts, stronger models for heavy ones.
- Pick the tier yourself, or let the prompt be classified automatically.
- Opt-in fallback: when a model fails or is rate-limited, the next one is tried, with or without tiering.
- Per-deployment cooldowns and cross-tier failover handled by `litellm.Router`.
- All routing, fallback, classification, and request defaults live in [config.yml](config.yml).
- Optionally attach user, session, request, application, and environment metadata for Langfuse observability.

## Requirements

- Python 3.13 or newer
- [uv](https://docs.astral.sh/uv/) for dependency and environment management (the repository includes `uv.lock`)
- Credentials for the model providers you plan to use
- Langfuse credentials if tracing is enabled

## Setup

Clone the repository and install its dependencies:

```bash
uv sync
```

Create a `.env` file in the project root and add the API key required by each provider you want to route to:

```dotenv
GEMINI_API_KEY=your-gemini-api-key
GROQ_API_KEY=your-groq-api-key
```

Models whose provider key is missing are dropped from routing automatically, so you only need keys for the providers you actually use.

To enable Langfuse tracing, also configure:

```dotenv
LANGFUSE_PUBLIC_KEY=your-langfuse-public-key
LANGFUSE_SECRET_KEY=your-langfuse-secret-key
# Read by the LiteLLM Langfuse integration; defaults to http://localhost:3000
LANGFUSE_HOST=http://localhost:3000
```

The Langfuse success and failure callbacks are registered when `llm_gateway` is imported, provided both keys are present, so failed requests are traced too. Traces carry the request id, user id, session id, application, environment, and the tier and fallback used.

Keep `.env` and all API credentials private; do not commit secrets to source control. [config.yml](config.yml) holds only environment variable *names*, never values.

## Configuration

[config.yml](config.yml) is the single place to tune the gateway, loaded by [settings.py](settings.py):

| Section | Purpose |
| --- | --- |
| `providers` | Provider prefix of a model id mapped to the environment variable holding its key |
| `tiers` | Models backing the `simple` and `complex` tiers, most preferred first |
| `router` | `routing_strategy`, `num_retries`, `cooldown_time`, `enable_pre_call_checks` |
| `classification` | Tier names, prompt length threshold, code-block marker, complexity keywords |
| `fallback` | Models tried when a pinned model fails and `max_attempts`, the per-request attempt cap; empty `models` means every available tier model, simple first |
| `defaults` | `temperature`, `max_tokens` and `timeout` used when a call omits them |
| `observability` | `application` and `environment` labels attached to Langfuse traces |
| `cost` | Whether to log per-request cost, and the `baseline_model` savings are measured against |

Within a tier, the first model carries the highest weight and serves most traffic; the remaining entries absorb retries, rate limits, and outages. When every model in a tier fails, LiteLLM falls back to the other tier.

## Usage

### Flags

Every flag on `chat()` is independent and defaults to `False`, so nothing happens unless you ask for it.

| Argument | Default | Effect |
| --- | --- | --- |
| `messages` | required | Standard chat list of `{"role", "content"}` dictionaries |
| `model` | `None` | Use this exact model; overrides tiering and the client-level model |
| `tier` | `False` | Turn tiered routing on |
| `tier_level` | `None` | With `tier=True`, force `"simple"` or `"complex"` instead of classifying |
| `fallback` | `False` | On failure or rate limit, try the next model |
| `tracing` | `False` | Send the request to Langfuse |
| `user_id` / `session_id` | `None` | Required when `tracing=True` |
| `temperature` | from `config.yml` | Sampling temperature |
| `max_tokens` | from `config.yml` | Response length cap |
| `timeout` | from `config.yml` | Seconds one provider attempt may run |

`chat()` returns the LiteLLM completion object, so `response.model` shows which model actually served the request. `achat()` takes the same arguments and awaits the result; use it inside an event loop.

### Which model is used

| Call | Model |
| --- | --- |
| `chat(model="x")` | `x`, even if `tier=True` is also passed |
| `chat(tier=True)` | Tier pick: `tier_level` if given, otherwise classified from the prompt |
| `chat()` with `LLMClient(model="x")` | `x` |
| `chat()` with no model anywhere | `ValueError` |

### Examples

```python
from llm_gateway import LLMClient

client = LLMClient()

# Your model, no safety net.
client.chat(
    messages=[{"role": "user", "content": "What is an LLM gateway?"}],
    model="groq/openai/gpt-oss-20b",
)

# Your model, with backup models if it fails.
client.chat(
    messages=[{"role": "user", "content": "What is an LLM gateway?"}],
    model="groq/openai/gpt-oss-20b",
    fallback=True,
)

# Tier chosen by you.
client.chat(
    messages=[{"role": "user", "content": "Summarize this paragraph."}],
    tier=True,
    tier_level="simple",
)

# Tier classified from the prompt, with retries and cross-tier failover.
client.chat(
    messages=[{"role": "user", "content": "Design a multi-region strategy and compare the trade-offs."}],
    tier=True,
    fallback=True,
)

# Traced request.
client.chat(
    messages=[{"role": "user", "content": "Summarize this request."}],
    tier=True,
    tracing=True,
    user_id="user-123",
    session_id="session-456",
)
```

A client-level default model can be set once with `LLMClient(model="...")`.

### How a tier is chosen

With `tier=True` and no `tier_level`, a prompt goes to the `complex` tier when it reaches the configured character threshold, contains a fenced code block, or matches one of the configured keywords; otherwise it goes to the `simple` tier.

### What `fallback=True` does

| Call | Behavior on failure or rate limit |
| --- | --- |
| `model=...`, `fallback=True` | Tries the `fallback.models` chain in order, skipping the pinned model |
| `tier=True`, `fallback=True` | Retries other models in the tier, parks failing ones for `cooldown_time`, then falls back to the other tier |
| `fallback=False` | Single attempt; the provider error is raised |

Attempts are capped by `fallback.max_attempts` in [config.yml](config.yml), counting the first attempt (`0` means no limit). For tiered calls the ceiling comes from `router.num_retries` plus the cross-tier fallback. Every attempt is a real network call, so a high cap means a slow failure.

### Cost tracking

LiteLLM reports the cost of every request to Langfuse. On top of that, a success callback logs the cost against a baseline model, so routing savings are measurable:

```text
model=gemini-3.1-flash-lite tier=simple  cost=0.00001425 baseline=0.00011400 saved=0.00009975
model=openai/gpt-oss-120b   tier=complex cost=0.00062625 baseline=0.01244600 saved=0.01181975
```

The baseline is `cost.baseline_model` in [config.yml](config.yml): what the same tokens would have cost on the strongest model. Savings are an estimate, not a measurement, because the cheaper model may have produced a different number of output tokens. Set `cost.log: false` to turn the logging off.

The `tier` label is only present when `tracing=True`, since it travels in the request metadata.

### Errors

| Condition | Raised |
| --- | --- |
| `tracing=True` without `user_id` or `session_id` | `ValueError` |
| `tracing=True` without Langfuse credentials | `RuntimeError` |
| `tier_level` set without `tier=True` | `ValueError` |
| `tier=False` and no model configured | `ValueError` |
| `tier_level` outside the configured tiers | `UnknownTierError` |
| No configured model has provider credentials | `NoRoutableModelError` |

## Project structure

```text
llm_gateway/       LLMClient: request building, tracing, model/tier/fallback dispatch
model_routing/     Tier definitions, prompt classification, fallback chain, LiteLLM Router setup
Observability/     Langfuse callbacks, trace metadata, cost logging
Fallbacks/         Empty; failover is handled by the LiteLLM Router
tests/             Runnable example scripts
service.py         FastAPI HTTP service
config.yml         Routing, fallback, classification, and request configuration
settings.py        Loads config.yml
main.py            Demo of the chat modes
```

## Running as a service

```bash
uv run uvicorn service:app --host 0.0.0.0 --port 8080
```

| Endpoint | Purpose |
| --- | --- |
| `POST /v1/chat/completions` | Chat request; body mirrors the `chat()` flags |
| `GET /health` | Process is alive |
| `GET /ready` | Router is built; lists the models backing each tier |

```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $GATEWAY_API_KEY" \
  -d '{"messages":[{"role":"user","content":"Say hi"}],"tier":true}'
```

Set `GATEWAY_API_KEY` in the environment to require a bearer token. **If it is unset the API accepts unauthenticated requests**, which is only acceptable for local development — an open gateway lets anyone spend your provider budget.

The service builds one `ModelRouter` at startup and shares it across requests, because deployment cooldown state lives inside the router. Requests use the async client path, so a slow provider does not block the worker.

Responses map provider failures to HTTP status codes: `400` for invalid arguments, `422` for a malformed body, `502` for an upstream model failure, and `503` when no model has credentials. Provider error text is logged server-side only.

## Running the examples

Run from the project root so the local packages resolve:

```bash
uv run python main.py                       # demo of the chat modes
uv run python -m tests.test_model_routing   # prints tier deployments and classification, no model calls
uv run python -m tests.test_multi_llm       # single traced request
```

These files are runnable examples rather than a pytest suite.

## Current scope

The HTTP service has no automated test suite, no container image, and no shared state across replicas. Running more than one replica needs Redis so deployment cooldowns are shared.
