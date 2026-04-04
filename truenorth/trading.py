from enum import StrEnum
from typing import NamedTuple
import psycopg

from alpaca.trading.enums import OrderSide

from truenorth.agent import Agent, Decision
from truenorth.alpaca import AlpacaClient
from truenorth.config import Config, TradingMode
from truenorth.context import DecisionContext
from truenorth.llm import create_llm
from truenorth.market import MacroContext, fetch_macro_context
from truenorth.massive import MassiveClient


class TickerStatus(StrEnum):
    HELD_WITH_EXIT = "HELD_WITH_EXIT"
    HELD_NO_EXIT = "HELD_NO_EXIT"
    PENDING_BUY = "PENDING_BUY"
    NO_POSITION = "NO_POSITION"


class Analysis(NamedTuple):
    decision: Decision
    status: TickerStatus


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

    analyses = analyze_all(alpaca, agent, massive, macro, config)

    for ticker, analysis in analyses.items():
        print(
            f"  {ticker} [{analysis.status}]: {analysis.decision.signal}  {analysis.decision.reasoning}"
        )

    for ticker, analysis in analyses.items():
        if (
            analysis.status != TickerStatus.NO_POSITION
            or analysis.decision.signal >= config.risk.min_buy_confidence
        ):
            act(ticker, analysis, alpaca, config)


def analyze_all(
    alpaca: AlpacaClient,
    agent: Agent,
    massive: MassiveClient,
    macro: MacroContext,
    config: Config,
) -> dict[str, Analysis]:
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

    analyses: dict[str, Analysis] = {}
    for ticker in all_tickers:
        last_price = alpaca.get_latest_price(ticker)
        history = alpaca.get_price_history(ticker)
        fundamentals = massive.get_fundamentals(ticker, last_price)

        ctx = DecisionContext(
            ticker=ticker,
            last_price=last_price,
            price_history=history,
            fundamentals=fundamentals,
            macro=macro,
        )

        decision = agent.analyze(ctx)

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

        analyses[ticker] = Analysis(decision=decision, status=status)

    return analyses


def act(ticker: str, analysis: Analysis, alpaca: AlpacaClient, config: Config) -> None:
    pass  # TODO: implement order placement and position management
