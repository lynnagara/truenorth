import argparse
from pathlib import Path

from truenorth.agent import Agent
from truenorth.alpaca import AlpacaClient
from truenorth.config import load_config
from truenorth.llm import create_llm


def _add_config_arg(parser):
    parser.add_argument("--config", type=Path, required=True, help="Path to yaml config file")


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
        client = AlpacaClient(config.alpaca_api_key, config.alpaca_secret_key)
        price = client.get_latest_price("AAPL")
        print(f"AAPL latest price: ${price}")
        decision = agent.analyze("AAPL", price)
        print(f"signal:    {decision.signal}")
        print(f"reasoning: {decision.reasoning}")
    elif args.command == "serve":
        config = load_config(config_path=args.config)
        print("serve: not implemented")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
