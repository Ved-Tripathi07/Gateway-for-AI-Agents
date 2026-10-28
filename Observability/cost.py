
import logging

import litellm

from settings import CLASSIFICATION, COST, TIERS

logger = logging.getLogger("llm_gateway.cost")

BASELINE_MODEL: str = (
    COST["baseline_model"] or TIERS[CLASSIFICATION["complex_tier"]][0]
)


def price_of(model: str, usage) -> float | None:
    """Price a token count against a model's rates.

    Costed from litellm.model_cost directly because a response reports the
    provider's own model id, which LiteLLM cannot always map back to pricing.
    """

    rates = litellm.model_cost.get(model)

    if not rates or usage is None:
        return None

    input_rate = rates.get("input_cost_per_token")
    output_rate = rates.get("output_cost_per_token")

    if input_rate is None or output_rate is None:
        return None

    prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
    completion_tokens = getattr(usage, "completion_tokens", 0) or 0

    return prompt_tokens * input_rate + completion_tokens * output_rate


def log_cost(kwargs, completion_response, start_time, end_time) -> None:
    """LiteLLM success callback recording actual cost against the baseline."""

    try:
        model = kwargs.get("model")
        usage = getattr(completion_response, "usage", None)
        metadata = kwargs.get("litellm_params", {}).get("metadata") or {}
        # Langfuse metadata nests the request fields one level down.
        details = metadata.get("metadata") or {}

        actual = kwargs.get("response_cost")

        if actual is None:
            actual = price_of(model, usage)

        baseline = price_of(BASELINE_MODEL, usage)

        if actual is None or baseline is None:
            logger.debug("no pricing for model=%s", model)
            return

        logger.info(
            "model=%s tier=%s cost=%.8f baseline=%.8f saved=%.8f",
            model,
            details.get("tier"),
            actual,
            baseline,
            baseline - actual,
        )

    except Exception:
        logger.debug("cost logging failed", exc_info=True)


def register_cost_logging() -> bool:
    """Attach the cost callback once, at startup."""

    if not COST["log"]:
        return False

    if log_cost not in litellm.success_callback:
        litellm.success_callback.append(log_cost)

    return True
