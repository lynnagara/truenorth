import json

from pydantic import BaseModel, ConfigDict, Field

from truenorth.llm import LLM
from truenorth.prompts import AnalysisContext, Prompt


class Analysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal: float = Field(ge=-1.0, le=1.0)
    entry_price: float | None  # USD, limit buy price; None if signal is not a buy
    target_price: float | None  # USD, limit sell (take profit); None if signal is not a buy
    reasoning: str


class Agent:
    def __init__(self, llm: LLM, prompt: Prompt):
        self._llm = llm
        self._prompt = prompt

    def analyze(self, ctx: AnalysisContext) -> Analysis:
        prompt = self._prompt.build(ctx)
        response = self._llm.generate(prompt, json_schema=Analysis.model_json_schema())
        data = json.loads(response)
        return Analysis(**data)
