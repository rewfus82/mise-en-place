import os

from dotenv import load_dotenv


def setup_tracing() -> dict:
    """Load .env and validate LangSmith config. Must be called before any LangChain/LangGraph code."""
    load_dotenv()

    api_key = os.getenv("LANGSMITH_API_KEY")
    enabled = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
    project = os.getenv("LANGSMITH_PROJECT", "mise-en-place")

    if enabled and not api_key:
        raise EnvironmentError(
            "LANGCHAIN_TRACING_V2=true but LANGSMITH_API_KEY is not set. "
            "Add it to your .env file."
        )

    if enabled:
        os.environ.setdefault("LANGSMITH_PROJECT", project)

    return {"enabled": enabled, "project": project if enabled else None}
