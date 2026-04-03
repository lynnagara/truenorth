import json

from pydantic import BaseModel, Field

from truenorth.context import DecisionContext
from truenorth.llm import LLM


class Decision(BaseModel):
    signal: float = Field(ge=-1.0, le=1.0)
    reasoning: str


class Agent:
    def __init__(self, llm: LLM):
        self._llm = llm

    def analyze(self, ctx: DecisionContext) -> Decision:
        history_str = "\n".join(f"  {d}: ${p:.2f}" for d, p in ctx.price_history)

        fundamentals_str = "\n".join([
            f"  market cap: ${ctx.fundamentals.market_cap:,.0f}" if ctx.fundamentals.market_cap else "  market cap: N/A",
            f"  EPS: ${ctx.fundamentals.eps:.2f}" if ctx.fundamentals.eps else "  EPS: N/A",
            f"  P/E ratio: {ctx.fundamentals.pe_ratio:.1f}" if ctx.fundamentals.pe_ratio else "  P/E ratio: N/A",
        ])

        prompt = f"""You are an equity analyst. Analyze the stock {ctx.ticker} currently trading at ${ctx.last_price:.2f}.

Price history (daily close, last 90 days):
{history_str}

Fundamentals:
{fundamentals_str}

Return a JSON object with exactly these fields:
- signal: a float between -1.0 and 1.0 where -1.0 is strong sell, 0.0 is neutral, 1.0 is strong buy
- reasoning: a concise explanation of your assessment, referencing price trend and fundamentals

Respond with JSON only, no other text.

Example:
{{"signal": 0.6, "reasoning": "Strong fundamentals with recent earnings beat..."}}"""

        response = self._llm.send_message(prompt)
        data = json.loads(response)
        return Decision(**data)
