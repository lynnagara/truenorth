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
