import yfinance as yf
from pydantic import BaseModel


class MacroContext(BaseModel):
    vix: float  # CBOE VIX spot level (via Yahoo Finance, ~15min delay)
    spy_change_5d: float  # SPY 5-day price change as a fraction (e.g. -0.032 = -3.2%)


def fetch_macro_context() -> MacroContext:
    vix_ticker = yf.Ticker("^VIX")
    vix = float(vix_ticker.fast_info["last_price"])

    spy_ticker = yf.Ticker("SPY")
    hist = spy_ticker.history(period="6d")
    spy_change_5d = float(
        (hist["Close"].iloc[-1] - hist["Close"].iloc[0]) / hist["Close"].iloc[0]
    )

    return MacroContext(vix=vix, spy_change_5d=spy_change_5d)
