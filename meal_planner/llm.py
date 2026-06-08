"""Provider-aware chat-model factory for BYOK (bring-your-own-key).

The app is a public, zero-cost demo: each request carries the visitor's own
provider + API key (never an env key, never persisted). Nodes build their LLM
per request via `make_llm(...)` instead of importing a module-level singleton, so
no key is read from the environment and no key is shared between requests.

Model IDs are env-overridable so a provider renaming a model is a config change,
not a code change.
"""
from __future__ import annotations

import contextvars
import os

SUPPORTED_PROVIDERS = ("anthropic", "openai")

# Per-request BYOK creds live in a ContextVar — NOT in the LangGraph config.
# LangGraph's SqliteSaver persists config.configurable to disk, so a key passed
# there would leak into checkpoints.db. A ContextVar is request-scoped and never
# serialized. It must be set in the same thread that runs the graph (see
# planning_service), because new threads start with a fresh context.
_creds_var: contextvars.ContextVar[tuple[str, str]] = contextvars.ContextVar(
    "llm_creds", default=("", "")
)


def set_request_creds(provider: str, api_key: str):
    """Set the BYOK creds for the current thread/context. Returns a reset token."""
    return _creds_var.set((provider, api_key))


def get_request_creds() -> tuple[str, str]:
    """(provider, api_key) for the current request, or ("", "") if unset."""
    return _creds_var.get()


def reset_request_creds(token) -> None:
    _creds_var.reset(token)

# role -> model id, per provider. "planner" = heavy reasoning, "light" = cheap/fast.
_MODELS: dict[str, dict[str, str]] = {
    "anthropic": {
        "planner": os.getenv("ANTHROPIC_PLANNER_MODEL", "claude-sonnet-4-6"),
        "light": os.getenv("ANTHROPIC_LIGHT_MODEL", "claude-haiku-4-5-20251001"),
    },
    "openai": {
        "planner": os.getenv("OPENAI_PLANNER_MODEL", "gpt-5.5"),
        "light": os.getenv("OPENAI_LIGHT_MODEL", "gpt-5.4-mini"),
    },
}


class LLMConfigError(ValueError):
    """Raised for a missing key or an unknown/unsupported provider."""


def normalize_provider(provider: str | None) -> str:
    p = (provider or "").strip().lower()
    if not p:
        raise LLMConfigError(
            "No AI provider selected. Connect your Claude or OpenAI API key to continue."
        )
    if p in {"claude", "anthropic"}:
        return "anthropic"
    if p in {"openai", "chatgpt", "gpt"}:
        return "openai"
    raise LLMConfigError(
        f"Unknown provider {provider!r}. Supported: {', '.join(SUPPORTED_PROVIDERS)}."
    )


def make_llm(provider: str, api_key: str, role: str = "planner"):
    """Build a chat model for `provider` using the caller's `api_key`.

    `role` is "planner" (heavy) or "light" (cheap/fast). Never falls back to an
    environment key — a missing key is an error so the BYOK contract is explicit.
    """
    provider = normalize_provider(provider)
    if not api_key or not api_key.strip():
        raise LLMConfigError("No API key provided for the selected AI provider.")
    if role not in ("planner", "light"):
        role = "planner"
    model = _MODELS[provider][role]

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=model, api_key=api_key, timeout=120, max_retries=2)

    # provider == "openai"
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=model, api_key=api_key, timeout=120, max_retries=2)
