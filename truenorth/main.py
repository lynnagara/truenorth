import argparse
from pathlib import Path

import psycopg

from truenorth.agent import Agent
from truenorth.alpaca import AlpacaClient
from truenorth.config import load_config
from truenorth.context import DecisionContext
from truenorth.llm import create_llm
from truenorth.market import fetch_macro_context
from truenorth.massive import MassiveClient


def _add_config_arg(parser):
    parser.add_argument(
        "--config", type=Path, required=True, help="Path to yaml config file"
    )


def main():
    parser = argparse.ArgumentParser(prog="truenorth")
    subparsers = parser.add_subparsers(dest="command")

    trade_parser = subparsers.add_parser("trade", help="Execute trading cycle")
    _add_config_arg(trade_parser)

    serve_parser = subparsers.add_parser("serve", help="Start API server")
    _add_config_arg(serve_parser)

    args = parser.parse_args()

    if args.command == "trade":
        config = load_config(config_path=args.config)
        llm = create_llm(config.llm)
        agent = Agent(llm=llm)
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
            print(f"entry:     ${decision.entry_price:.2f}" if decision.entry_price else "entry:     N/A")
            print(f"reasoning: {decision.reasoning}")

            if decision.signal >= config.risk.min_buy_confidence:
                candidates.append((ticker, decision))

        print(f"\n--- buy candidates (signal >= {config.risk.min_buy_confidence}) ---")
        if candidates:
            for ticker, decision in candidates:
                entry = f"  limit ${decision.entry_price:.2f}" if decision.entry_price else ""
                print(f"  {ticker}: {decision.signal:.2f}{entry}")
        else:
            print("  none")
    elif args.command == "serve":
        config = load_config(config_path=args.config)
        from truenorth.server import serve
        serve(config)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
