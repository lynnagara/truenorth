from contextlib import contextmanager
from typing import Callable, Generator

from langfuse import Langfuse

from truenorth.config import Config
from truenorth.context import AnalysisContext

langfuse: Langfuse | None = None


def init_tracing(config: Config) -> None:
    """Initialize tracing providers. Any provider without keys is a no-op."""
    global langfuse
    if config.langfuse_public_key and config.langfuse_secret_key:
        langfuse = Langfuse(
            public_key=config.langfuse_public_key,
            secret_key=config.langfuse_secret_key,
        )


@contextmanager
def trace_run() -> Generator[None, None, None]:
    """Top-level span grouping all ticker analyses in one trade run."""
    if langfuse is None:
        yield
        return

    with langfuse.start_as_current_observation(as_type="span", name="trade-run"):
        yield


@contextmanager
def trace_analysis(
    ctx: AnalysisContext, model: str
) -> Generator[Callable[[dict], None], None, None]:
    """Per-ticker LLM generation span, nested inside trace_run. Yields a callable to record output."""
    if langfuse is None:
        yield lambda _: None
        return

    with langfuse.start_as_current_observation(
        as_type="generation",
        name=f"analyze-{ctx.ticker}",
        model=model,
        input={"ticker": ctx.ticker, "last_price": ctx.last_price},
    ) as generation:
        yield lambda output: generation.update(output=output)  # type: ignore[attr-defined]
