import argparse
from pathlib import Path

from truenorth.agent import Agent
from truenorth.alpaca import AlpacaClient
from truenorth.config import load_config
from truenorth.context import DecisionContext
from truenorth.llm import create_llm
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

        tickers = ["AAPL", "MSFT", "NVDA", "JPM", "UNH", "GOOGL", "META", "AMZN", "BRK.B", "V"]
        for ticker in tickers:
            last_price = alpaca.get_latest_price(ticker)
            history = alpaca.get_price_history(ticker)
            fundamentals = massive.get_fundamentals(ticker, last_price)

            ctx = DecisionContext(
                ticker=ticker,
                last_price=last_price,
                price_history=history,
                fundamentals=fundamentals,
            )

            print(f"\n{ticker} last price: ${last_price}")
            print(f"fundamentals: {fundamentals}")

            decision = agent.analyze(ctx)
            print(f"signal:    {decision.signal}")
            print(f"reasoning: {decision.reasoning}")
    elif args.command == "serve":
        config = load_config(config_path=args.config)
        print("serve: not implemented")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
