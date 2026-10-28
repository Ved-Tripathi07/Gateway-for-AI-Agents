
import logging
import os
import secrets
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from llm_gateway import LLMClient
from model_routing import ModelRouter, NoRoutableModelError, UnknownTierError

logger = logging.getLogger("llm_gateway.service")

API_KEY = os.getenv("GATEWAY_API_KEY")

state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # One router for the process: cooldown state lives inside it.
    state["client"] = LLMClient(router=ModelRouter())

    if not API_KEY:
        logger.warning("GATEWAY_API_KEY is not set; the API is unauthenticated")

    yield

    state.clear()


app = FastAPI(title="LLM Gateway", lifespan=lifespan)


def require_api_key(authorization: str | None = Header(default=None)) -> None:
    if not API_KEY:
        return

    expected = f"Bearer {API_KEY}"

    if not authorization or not secrets.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="invalid api key")


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1)
    model: str | None = None
    tier: bool = False
    tier_level: str | None = None
    fallback: bool = False
    tracing: bool = False
    user_id: str | None = None
    session_id: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, gt=0, le=8192)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict:
    client = state.get("client")

    if client is None:
        raise HTTPException(status_code=503, detail="router not initialised")

    return {
        "status": "ready",
        "tiers": {
            tier: client.router.deployments(tier)
            for tier in sorted(client.router.tiers)
        },
    }


@app.post("/v1/chat/completions")
async def chat_completions(
    request: ChatRequest,
    _: None = Depends(require_api_key),
) -> dict:
    client = state["client"]

    try:
        response = await client.achat(
            messages=[message.model_dump() for message in request.messages],
            model=request.model,
            tier=request.tier,
            tier_level=request.tier_level,
            fallback=request.fallback,
            tracing=request.tracing,
            user_id=request.user_id,
            session_id=request.session_id,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

    except (ValueError, UnknownTierError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    except NoRoutableModelError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    except Exception:
        # Provider errors can echo request content, so only the server logs them.
        logger.exception("upstream model request failed")
        raise HTTPException(
            status_code=502, detail="upstream model request failed"
        ) from None

    return response.model_dump()
