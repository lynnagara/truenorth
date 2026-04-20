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
    news: list[str] = []  # recent headlines with summaries


class Prompt:
    def build(self, ctx: AnalysisContext) -> str:
        raise NotImplementedError

    def _format_common(self, ctx: AnalysisContext) -> dict:
        history_str = "\n".join(f"  {d}: ${p:.2f}" for d, p in ctx.price_history)
        f = ctx.fundamentals
        fundamentals_str = "\n".join(
            [
                f"  industry: {f.industry}" if f.industry else "  industry: N/A",
                f"  market cap: ${f.market_cap:,.0f}" if f.market_cap else "  market cap: N/A",
                f"  EPS: ${f.eps:.2f}" if f.eps else "  EPS: N/A",
                f"  P/E ratio: {f.pe_ratio:.1f}" if f.pe_ratio else "  P/E ratio: N/A",
                f"  revenue: ${f.revenues:,.0f}" if f.revenues else "  revenue: N/A",
                f"  gross margin: {f.gross_margin:.1%}" if f.gross_margin else "  gross margin: N/A",
                f"  operating cash flow: ${f.operating_cash_flow:,.0f}" if f.operating_cash_flow else "  operating cash flow: N/A",
                f"  long-term debt: ${f.long_term_debt:,.0f}" if f.long_term_debt else "  long-term debt: N/A",
                f"  equity: ${f.equity:,.0f}" if f.equity else "  equity: N/A",
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


class SwingNewsFundamentalsPrompt(Prompt):
    _TEMPLATE = """You are an equity analyst focused on swing trades with a 2-4 week holding period. Analyze the stock {ticker} currently trading at ${last_price:.2f}.

Macro environment:
{macro}

Price history (daily close, last 90 days):
{history}

Fundamentals:
{fundamentals}

Recent news:
{news}

Weigh recent news heavily. Identify any specific near-term catalyst (earnings surprise, analyst action, product launch, macro event) and size your conviction around it. Use price history and fundamentals as context. If there is no meaningful catalyst, lean neutral.

Return a JSON object with exactly these fields:
- signal: a float between -1.0 and 1.0 where -1.0 is strong sell, 0.0 is neutral, 1.0 is strong buy
- entry_price: suggested limit buy price (in USD) if you are bullish; otherwise null
- target_price: suggested take-profit price (in USD) over a 2-4 week horizon if you are bullish; otherwise null
- reasoning: a concise explanation referencing the key catalyst, price trend, fundamentals, and macro environment

Respond with JSON only, no other text.

Example:
{{"signal": 0.7, "entry_price": 170.00, "target_price": 195.00, "reasoning": "Earnings beat last week with raised guidance is a clear catalyst; technicals show breakout from consolidation; macro tailwind from falling rates."}}"""

    def build(self, ctx: AnalysisContext) -> str:
        news_str = "\n".join(f"  {item}" for item in ctx.news) if ctx.news else "  No recent news."
        return self._TEMPLATE.format(**self._format_common(ctx), news=news_str)



class SwingNewsDipPrompt(Prompt):
    _TEMPLATE = """You are an equity analyst focused on swing trades with a 2-4 week holding period. Analyze the stock {ticker} currently trading at ${last_price:.2f}.

Macro environment:
{macro}

Price statistics:
  20-day moving average: ${ma20:.2f} (current price is {ma20_diff:+.1%} vs MA)
  Drawdown from 20-day high: {drawdown:.1%}
  Price history (daily close, last 90 days):
{history}

Fundamentals:
{fundamentals}

Recent news:
{news}

Identify any specific near-term catalyst (earnings surprise, analyst action, product launch, macro event) and size your conviction around it. Use fundamentals to assess business quality — favour positive or growing operating cash flow, reasonable gross margins, and manageable debt.

Be mindful of entry timing: if the stock has already run up significantly on the catalyst (trading well above its 20-day MA), the move may be priced in — lean neutral or wait for a better entry. Prefer stocks where a catalyst exists but the price hasn't fully reacted yet, or where a quality stock has dipped.

If there is no meaningful catalyst and no dip opportunity, lean neutral.

Return a JSON object with exactly these fields:
- signal: a float between -1.0 and 1.0 where -1.0 is strong sell, 0.0 is neutral, 1.0 is strong buy
- entry_price: suggested limit buy price (in USD) if you are bullish; otherwise null
- target_price: suggested take-profit price (in USD) over a 2-4 week horizon if you are bullish; otherwise null
- reasoning: a concise explanation referencing the catalyst, entry timing relative to the move, business quality, and macro environment

Respond with JSON only, no other text.

Example:
{{"signal": 0.7, "entry_price": 170.00, "target_price": 195.00, "reasoning": "Earnings beat with raised guidance is a clear catalyst; stock is only +2% vs 20-day MA suggesting the move isn't fully priced in; strong operating cash flow and gross margins support quality; targeting 2-week recovery."}}"""

    def build(self, ctx: AnalysisContext) -> str:
        prices = [p for _, p in ctx.price_history]
        ma20 = sum(prices[-20:]) / min(20, len(prices)) if prices else ctx.last_price
        high20 = max(prices[-20:]) if prices else ctx.last_price
        ma20_diff = (ctx.last_price - ma20) / ma20
        drawdown = (ctx.last_price - high20) / high20
        news_str = "\n".join(f"  {item}" for item in ctx.news) if ctx.news else "  No recent news."
        return self._TEMPLATE.format(**self._format_common(ctx), ma20=ma20, ma20_diff=ma20_diff, drawdown=drawdown, news=news_str)


basic_fundamentals = FundamentalsPrompt()
swing_news_fundamentals = SwingNewsFundamentalsPrompt()
swing_news_dip = SwingNewsDipPrompt()

PROMPT_REGISTRY: dict[str, Prompt] = {
    "basic_fundamentals": basic_fundamentals,
    "swing_news_fundamentals": swing_news_fundamentals,
    "swing_news_dip": swing_news_dip,
}
