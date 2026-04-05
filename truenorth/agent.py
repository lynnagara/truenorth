import json

from pydantic import BaseModel, ConfigDict, Field

from truenorth.context import AnalysisContext
from truenorth.llm import LLM


class Analysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal: float = Field(ge=-1.0, le=1.0)
    entry_price: float | None  # USD, limit buy price; None if signal is not a buy
    target_price: float | None  # USD, limit sell (take profit); None if signal is not a buy
    reasoning: str


class Agent:
    def __init__(self, llm: LLM, buy_threshold: float):
        self._llm = llm
        self._buy_threshold = buy_threshold

    def analyze(self, ctx: AnalysisContext) -> Analysis:
        history_str = "\n".join(f"  {d}: ${p:.2f}" for d, p in ctx.price_history)

        fundamentals_str = "\n".join(
            [
                f"  industry: {ctx.fundamentals.industry}"
                if ctx.fundamentals.industry
                else "  industry: N/A",
                f"  market cap: ${ctx.fundamentals.market_cap:,.0f}"
                if ctx.fundamentals.market_cap
                else "  market cap: N/A",
                f"  EPS: ${ctx.fundamentals.eps:.2f}" if ctx.fundamentals.eps else "  EPS: N/A",
                f"  P/E ratio: {ctx.fundamentals.pe_ratio:.1f}"
                if ctx.fundamentals.pe_ratio
                else "  P/E ratio: N/A",
            ]
        )

        vix_level = "elevated" if ctx.macro.vix > 25 else "normal" if ctx.macro.vix > 15 else "low"
        macro_str = f"  VIX: {ctx.macro.vix:.1f} ({vix_level} volatility)\n  S&P 500 5-day change: {ctx.macro.spy_change_5d:+.1%}"

        prompt = f"""You are an equity analyst. Analyze the stock {ctx.ticker} currently trading at ${ctx.last_price:.2f}.

Macro environment:
{macro_str}

Price history (daily close, last 90 days):
{history_str}

Fundamentals:
{fundamentals_str}

Return a JSON object with exactly these fields:
- signal: a float between -1.0 and 1.0 where -1.0 is strong sell, 0.0 is neutral, 1.0 is strong buy
- entry_price: if signal >= {self._buy_threshold}, the price (in USD) at which you would place a limit buy order; otherwise null
- target_price: if signal >= {self._buy_threshold}, your take-profit target price (in USD); otherwise null
- reasoning: a concise explanation of your assessment, referencing price trend, fundamentals, and macro environment

Respond with JSON only, no other text.

Example:
{{"signal": 0.7, "entry_price": 170.00, "target_price": 195.00, "reasoning": "Strong fundamentals with recent earnings beat, would enter on a dip to support..."}}"""

        response = self._llm.generate(prompt, json_schema=Analysis.model_json_schema())
        data = json.loads(response)
        return Analysis(**data)
