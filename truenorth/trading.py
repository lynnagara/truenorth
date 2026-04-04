from enum import StrEnum
import psycopg

from alpaca.trading.enums import OrderSide

from truenorth.agent import Agent, Analysis
from truenorth.alpaca import AlpacaClient
from truenorth.config import Config, RiskConfig, TradingMode
from truenorth.context import AnalysisContext
from truenorth.llm import create_llm
from truenorth.market import MacroContext, fetch_macro_context
from truenorth.massive import MassiveClient


class TickerStatus(StrEnum):
    HELD_WITH_EXIT = "HELD_WITH_EXIT"
    HELD_NO_EXIT = "HELD_NO_EXIT"
    PENDING_BUY = "PENDING_BUY"
    NO_POSITION = "NO_POSITION"


def trade(config: Config) -> None:
    llm = create_llm(config.llm, anthropic_api_key=config.anthropic_api_key)
    agent = Agent(llm=llm, min_buy_confidence=config.risk.min_buy_confidence)
    alpaca = AlpacaClient(
        api_key=config.alpaca_api_key,
        secret_key=config.alpaca_secret_key,
        paper=config.execution.trading == TradingMode.PAPER,
    )
    massive = MassiveClient(config.massive_api_key)

    macro = fetch_macro_context()
    print(f"VIX: {macro.vix:.1f}  SPY 5d: {macro.spy_change_5d:+.1%}")

    results = analyze_all(alpaca, agent, massive, macro, config)

    for ticker, (status, analysis) in results.items():
        print(f"  {ticker} [{status}]: {analysis.signal}  {analysis.reasoning}")

    for ticker, (status, analysis) in results.items():
        if (
            status != TickerStatus.NO_POSITION
            or analysis.signal >= config.risk.min_buy_confidence
        ):
            act(ticker, status, analysis, alpaca, config.risk)


def analyze_all(
    alpaca: AlpacaClient,
    agent: Agent,
    massive: MassiveClient,
    macro: MacroContext,
    config: Config,
) -> dict[str, tuple[TickerStatus, Analysis]]:
    open_orders = alpaca.get_open_orders()
    held_tickers = [str(p.symbol) for p in alpaca.get_open_positions()]
    pending_buy_tickers = [
        str(o.symbol) for o in open_orders if o.side == OrderSide.BUY
    ]
    pending_sell_tickers = {
        str(o.symbol) for o in open_orders if o.side == OrderSide.SELL
    }

    with psycopg.connect(config.database_url) as conn:
        rows = conn.execute("SELECT ticker FROM watchlist ORDER BY ticker").fetchall()
    watchlist_tickers = [row[0] for row in rows]

    all_tickers = list(
        dict.fromkeys(held_tickers + pending_buy_tickers + watchlist_tickers)
    )

    results: dict[str, tuple[TickerStatus, Analysis]] = {}
    for ticker in all_tickers:
        last_price = alpaca.get_latest_price(ticker)
        history = alpaca.get_price_history(ticker)
        fundamentals = massive.get_fundamentals(ticker, last_price)

        ctx = AnalysisContext(
            ticker=ticker,
            last_price=last_price,
            price_history=history,
            fundamentals=fundamentals,
            macro=macro,
        )

        analysis = agent.analyze(ctx)

        if ticker in held_tickers:
            status = (
                TickerStatus.HELD_WITH_EXIT
                if ticker in pending_sell_tickers
                else TickerStatus.HELD_NO_EXIT
            )
        elif ticker in pending_buy_tickers:
            status = TickerStatus.PENDING_BUY
        else:
            status = TickerStatus.NO_POSITION

        results[ticker] = (status, analysis)

    return results


def act(
    ticker: str,
    status: TickerStatus,
    analysis: Analysis,
    alpaca: AlpacaClient,
    risk: RiskConfig,
) -> None:
    pass  # TODO: implement order placement and position management
