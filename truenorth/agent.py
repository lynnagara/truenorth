import json

from pydantic import BaseModel, Field

from truenorth.llm import LLM


class Decision(BaseModel):
    signal: float = Field(ge=-1.0, le=1.0)
    reasoning: str


class Agent:
    def __init__(self, llm: LLM):
        self._llm = llm

    def analyze(self, ticker: str, price: float) -> Decision:
        prompt = f"""You are an equity analyst. Analyze the stock {ticker} currently trading at ${price:.2f}.

Return a JSON object with exactly these fields:
- signal: a float between -1.0 and 1.0 where -1.0 is strong sell, 0.0 is neutral, 1.0 is strong buy
- reasoning: a concise explanation of your assessment

Respond with JSON only, no other text.

Example:
{{"signal": 0.6, "reasoning": "Strong fundamentals with recent earnings beat..."}}"""

        response = self._llm.send_message(prompt)
        data = json.loads(response)
        return Decision(**data)
