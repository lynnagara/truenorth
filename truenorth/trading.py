from truenorth.config import Config
from truenorth.llm import create_llm
from truenorth.agent import Agent
from truenorth.market import fetch_macro_context
import psycopg
from truenorth.massive import MassiveClient

from truenorth.alpaca import AlpacaClient
from truenorth.context import DecisionContext


def trade(config: Config) -> None:
    """
    Iterate through each ticker on the watchlist and output a decision for
    each, based on fundamentals, industry and macro factors. Filters to
    tickers where signal >= min_buy_confidence.
    """
    llm = create_llm(config.llm)
    agent = Agent(llm=llm, min_buy_confidence=config.risk.min_buy_confidence)
    alpaca = AlpacaClient(config.alpaca_api_key, config.alpaca_secret_key)
    massive = MassiveClient(config.massive_api_key)

    macro = fetch_macro_context()
    print(f"VIX: {macro.vix:.1f}  SPY 5d: {macro.spy_change_5d:+.1%}")

    with psycopg.connect(config.database_url) as conn:
        rows = conn.execute("SELECT ticker FROM watchlist ORDER BY ticker").fetchall()
    tickers = [row[0] for row in rows]
    candidates = []
    for ticker in tickers:
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

        print(f"\n{ticker} last price: ${last_price}")
        print(f"fundamentals: {fundamentals}")

        decision = agent.analyze(ctx)
        print(f"signal:    {decision.signal}")
        print(
            f"entry:     ${decision.entry_price:.2f}"
            if decision.entry_price
            else "entry:     N/A"
        )
        print(f"reasoning: {decision.reasoning}")

        if decision.signal >= config.risk.min_buy_confidence:
            candidates.append((ticker, decision))

    print(f"\n--- buy candidates (signal >= {config.risk.min_buy_confidence}) ---")
    if candidates:
        for ticker, decision in candidates:
            entry = (
                f"  limit ${decision.entry_price:.2f}" if decision.entry_price else ""
            )
            print(f"  {ticker}: {decision.signal:.2f}{entry}")
    else:
        print("  none")
