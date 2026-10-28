import os

import litellm
from dotenv import load_dotenv
from litellm import Router

from settings import CLASSIFICATION, FALLBACK, PROVIDER_API_KEYS, ROUTER, TIERS

load_dotenv()

SIMPLE_TIER: str = CLASSIFICATION["simple_tier"]
COMPLEX_TIER: str = CLASSIFICATION["complex_tier"]
COMPLEX_CHAR_THRESHOLD: int = CLASSIFICATION["char_threshold"]
CODE_BLOCK_MARKER: str = CLASSIFICATION["code_block_marker"]
COMPLEX_KEYWORDS: tuple[str, ...] = tuple(CLASSIFICATION["keywords"])


class UnknownTierError(ValueError):
    """Raised when a tier name is not configured."""


class NoRoutableModelError(RuntimeError):
    """Raised when no candidate model has credentials configured."""


def provider_of(model: str) -> str | None:
    """Return the provider prefix of a LiteLLM model identifier."""

    return model.split("/", 1)[0] if "/" in model else None


def is_available(model: str) -> bool:
    """Report whether the API key required by a model's provider is set."""

    provider = provider_of(model)
    env_key = PROVIDER_API_KEYS.get(provider) if provider else None

    # Providers outside the mapping are left to LiteLLM to validate.
    return env_key is None or bool(os.getenv(env_key))


def message_text(messages: list[dict]) -> str:
    """Return the text of the last user message."""

    for message in reversed(messages):
        if message.get("role") != "user":
            continue

        content = message.get("content")

        if isinstance(content, str):
            return content

        if isinstance(content, list):
            return " ".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict)
            )

    return ""


def classify(messages: list[dict]) -> str:
    """Pick the tier a request belongs to from the prompt itself."""

    text = message_text(messages)
    lowered = text.lower()

    if len(text) >= COMPLEX_CHAR_THRESHOLD:
        return COMPLEX_TIER

    if CODE_BLOCK_MARKER in text:
        return COMPLEX_TIER

    if any(keyword in lowered for keyword in COMPLEX_KEYWORDS):
        return COMPLEX_TIER

    return SIMPLE_TIER


def fallback_models(exclude: str | None = None) -> list[str]:
    """Return the models to try, in order, when a pinned model fails."""

    configured = FALLBACK["models"] or [
        model for models in TIERS.values() for model in models
    ]

    chain = []

    for model in configured:
        if model != exclude and model not in chain and is_available(model):
            chain.append(model)

    max_attempts = FALLBACK["max_attempts"]

    if max_attempts:
        # The pinned model is the first attempt, so the chain gets the rest.
        chain = chain[: max(max_attempts - 1, 0)]

    return chain


def build_model_list(tiers: dict[str, list[str]]) -> list[dict]:
    """Build LiteLLM deployments, weighted so preferred models are picked first."""

    deployments = []

    for tier, models in tiers.items():
        available = [model for model in models if is_available(model)]

        for index, model in enumerate(available):
            deployments.append(
                {
                    "model_name": tier,
                    "litellm_params": {
                        "model": model,
                        "weight": len(available) - index,
                    },
                }
            )

    return deployments


class ModelRouter:
    """Route requests to a model tier and fail over on errors or rate limits."""

    def __init__(
        self,
        tiers: dict[str, list[str]] | None = None,
        num_retries: int | None = None,
        cooldown_time: int | None = None,
    ):
        source = tiers or TIERS
        self.model_list = build_model_list(source)

        if not self.model_list:
            raise NoRoutableModelError(
                "No configured model has provider credentials available. "
                f"Set one of: {', '.join(sorted(set(PROVIDER_API_KEYS.values())))}."
            )

        self.tiers = {
            deployment["model_name"] for deployment in self.model_list
        }

        self.router = Router(
            model_list=self.model_list,
            fallbacks=self._fallbacks(),
            context_window_fallbacks=self._context_window_fallbacks(),
            routing_strategy=ROUTER["routing_strategy"],
            num_retries=(
                ROUTER["num_retries"] if num_retries is None else num_retries
            ),
            cooldown_time=(
                ROUTER["cooldown_time"] if cooldown_time is None else cooldown_time
            ),
            enable_pre_call_checks=ROUTER["enable_pre_call_checks"],
        )

    def _fallbacks(self) -> list[dict[str, list[str]]]:
        """Send a tier's traffic to the other tier once its own models fail."""

        return [
            {tier: sorted(self.tiers - {tier})}
            for tier in sorted(self.tiers)
            if self.tiers - {tier}
        ]

    def _context_window_fallbacks(self) -> list[dict[str, list[str]]]:
        if {SIMPLE_TIER, COMPLEX_TIER} <= self.tiers:
            return [{SIMPLE_TIER: [COMPLEX_TIER]}]

        return []

    def deployments(self, tier: str) -> list[str]:
        """Return the models backing a tier, most preferred first."""

        return [
            deployment["litellm_params"]["model"]
            for deployment in self.model_list
            if deployment["model_name"] == tier
        ]

    def resolve_tier(self, messages: list[dict], tier: str | None = None) -> str:
        """Resolve the tier to call, falling back when a tier has no models."""

        selected = tier or classify(messages)

        if selected in self.tiers:
            return selected

        if tier is not None:
            raise UnknownTierError(
                f"Unknown tier '{tier}'. "
                f"Available tiers: {', '.join(sorted(self.tiers))}"
            )

        return sorted(self.tiers)[0]

    def completion(
        self,
        messages: list[dict],
        model: str | None = None,
        tier: str | None = None,
        fallback: bool = False,
        **kwargs,
    ):
        """Send a request through the router, or directly to an explicit model."""

        if model:
            return litellm.completion(model=model, messages=messages, **kwargs)

        return self.router.completion(
            model=self.resolve_tier(messages, tier),
            messages=messages,
            **self._routing_kwargs(fallback, kwargs),
        )

    async def acompletion(
        self,
        messages: list[dict],
        model: str | None = None,
        tier: str | None = None,
        fallback: bool = False,
        **kwargs,
    ):
        """Async counterpart of completion, for use inside a running event loop."""

        if model:
            return await litellm.acompletion(
                model=model, messages=messages, **kwargs
            )

        return await self.router.acompletion(
            model=self.resolve_tier(messages, tier),
            messages=messages,
            **self._routing_kwargs(fallback, kwargs),
        )

    def _routing_kwargs(self, fallback: bool, kwargs: dict) -> dict:
        if not fallback:
            # Keep the request on the deployment the tier picked first.
            kwargs["num_retries"] = 0
            kwargs["fallbacks"] = []

        return kwargs
