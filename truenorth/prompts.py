from datetime import date

from pydantic import BaseModel

from truenorth.market import MacroContext
from truenorth.massive import Fundamentals


class AnalysisContext(BaseModel):
    """
    Holds data available to the agent when analyzing a ticker.
    Price values are all floats in USD, as this matches the types returned by Alpaca and Massive SDKs.
    """

    ticker: str
    last_price: float  # USD
    price_history: list[tuple[date, float]]  # (date, close price in USD)
    fundamentals: Fundamentals
    macro: MacroContext


class Prompt:
    def build(self, ctx: AnalysisContext) -> str:
        raise NotImplementedError

    def _format_common(self, ctx: AnalysisContext) -> dict:
        history_str = "\n".join(f"  {d}: ${p:.2f}" for d, p in ctx.price_history)
        fundamentals_str = "\n".join(
            [
                f"  industry: {ctx.fundamentals.industry}" if ctx.fundamentals.industry else "  industry: N/A",
                f"  market cap: ${ctx.fundamentals.market_cap:,.0f}" if ctx.fundamentals.market_cap else "  market cap: N/A",
                f"  EPS: ${ctx.fundamentals.eps:.2f}" if ctx.fundamentals.eps else "  EPS: N/A",
                f"  P/E ratio: {ctx.fundamentals.pe_ratio:.1f}" if ctx.fundamentals.pe_ratio else "  P/E ratio: N/A",
            ]
        )
        vix_level = "elevated" if ctx.macro.vix > 25 else "normal" if ctx.macro.vix > 15 else "low"
        macro_str = f"  VIX: {ctx.macro.vix:.1f} ({vix_level} volatility)\n  S&P 500 5-day change: {ctx.macro.spy_change_5d:+.1%}"
        return dict(
            ticker=ctx.ticker,
            last_price=ctx.last_price,
            macro=macro_str,
            history=history_str,
            fundamentals=fundamentals_str,
        )


class FundamentalsPrompt(Prompt):
    _TEMPLATE = """You are an equity analyst. Analyze the stock {ticker} currently trading at ${last_price:.2f}.

Macro environment:
{macro}

Price history (daily close, last 90 days):
{history}

Fundamentals:
{fundamentals}

Return a JSON object with exactly these fields:
- signal: a float between -1.0 and 1.0 where -1.0 is strong sell, 0.0 is neutral, 1.0 is strong buy
- entry_price: suggested limit buy price (in USD) if you are bullish; otherwise null
- target_price: suggested take-profit price (in USD) if you are bullish; otherwise null
- reasoning: a concise explanation of your assessment, referencing price trend, fundamentals, and macro environment

Respond with JSON only, no other text.

Example:
{{"signal": 0.7, "entry_price": 170.00, "target_price": 195.00, "reasoning": "Strong fundamentals with recent earnings beat, would enter on a dip to support..."}}"""

    def build(self, ctx: AnalysisContext) -> str:
        return self._TEMPLATE.format(**self._format_common(ctx))


basic_fundamentals = FundamentalsPrompt()

PROMPT_REGISTRY: dict[str, Prompt] = {
    "basic_fundamentals": basic_fundamentals,
}
