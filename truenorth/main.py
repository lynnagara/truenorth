import argparse
from pathlib import Path

from truenorth.config import load_config


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
        from truenorth.trading import trade

        config = load_config(config_path=args.config)
        trade(config)
    elif args.command == "serve":
        config = load_config(config_path=args.config)
        from truenorth.server import serve

        serve(config)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
