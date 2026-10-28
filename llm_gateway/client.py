
from dotenv import load_dotenv
from litellm import acompletion, completion

from model_routing import ModelRouter, fallback_models
from Observability.cost import register_cost_logging
from Observability.observability import (
    TRACING_AVAILABLE,
    build_model_metadata,
    create_request_context,
    register_callbacks,
)
from settings import REQUEST_DEFAULTS

load_dotenv()

# Callbacks must exist before the first request, or failures go untraced.
register_callbacks()
register_cost_logging()


class LLMClient:
    def __init__(
        self,
        model: str | None = None,
        router: ModelRouter | None = None,
    ):
        self.model = model
        self._router = router

    @property
    def router(self) -> ModelRouter:
        # Built on first tiered request so untiered calls need no tier config.
        if self._router is None:
            self._router = ModelRouter()

        return self._router

    def _prepare(
        self,
        messages: list[dict],
        temperature: float | None,
        max_tokens: int | None,
        timeout: float | None,
        tracing: bool,
        user_id: str | None,
        session_id: str | None,
        model: str | None,
        tier: bool,
        tier_level: str | None,
        fallback: bool,
    ) -> tuple[dict, str | None]:
        """Validate a call and return request kwargs plus the model to pin, if any."""

        if tier_level and not tier:
            raise ValueError(
                "tier=True is required when tier_level is set"
            )

        kwargs = {
            "messages": messages,
            "temperature": (
                REQUEST_DEFAULTS["temperature"] if temperature is None else temperature
            ),
            "max_tokens": (
                REQUEST_DEFAULTS["max_tokens"] if max_tokens is None else max_tokens
            ),
            "timeout": (
                REQUEST_DEFAULTS["timeout"] if timeout is None else timeout
            ),
        }

        if tracing:
            if not user_id or not session_id:
                raise ValueError(
                    "user_id and session_id are required when tracing=True"
                )

            if not TRACING_AVAILABLE:
                raise RuntimeError(
                    "LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are required "
                    "when tracing=True"
                )

            context = create_request_context(
                user_id=user_id,
                session_id=session_id,
                tier=(
                    self.router.resolve_tier(messages, tier_level)
                    if tier and not model
                    else None
                ),
                fallback=fallback,
            )

            kwargs["metadata"] = build_model_metadata(context)

        # A model named on the call wins over tiering.
        if model:
            return kwargs, model

        if tier:
            return kwargs, None

        if not self.model:
            raise ValueError(
                "model is required when tier=False"
            )

        return kwargs, self.model

    def chat(
        self,
        messages: list[dict],
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout: float | None = None,
        tracing: bool = False,
        user_id: str | None = None,
        session_id: str | None = None,
        model: str | None = None,
        tier: bool = False,
        tier_level: str | None = None,
        fallback: bool = False,
    ):
        kwargs, selected = self._prepare(
            messages, temperature, max_tokens, timeout, tracing,
            user_id, session_id, model, tier, tier_level, fallback,
        )

        if selected:
            return completion(model=selected, **self._with_fallbacks(selected, fallback, kwargs))

        return self.router.completion(
            tier=tier_level,
            fallback=fallback,
            **kwargs,
        )

    async def achat(
        self,
        messages: list[dict],
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout: float | None = None,
        tracing: bool = False,
        user_id: str | None = None,
        session_id: str | None = None,
        model: str | None = None,
        tier: bool = False,
        tier_level: str | None = None,
        fallback: bool = False,
    ):
        kwargs, selected = self._prepare(
            messages, temperature, max_tokens, timeout, tracing,
            user_id, session_id, model, tier, tier_level, fallback,
        )

        if selected:
            return await acompletion(
                model=selected,
                **self._with_fallbacks(selected, fallback, kwargs),
            )

        return await self.router.acompletion(
            tier=tier_level,
            fallback=fallback,
            **kwargs,
        )

    def _with_fallbacks(self, model: str, fallback: bool, kwargs: dict) -> dict:
        if fallback:
            chain = fallback_models(exclude=model)

            if chain:
                kwargs["fallbacks"] = chain

        return kwargs
