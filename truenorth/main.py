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
    trade_parser.add_argument(
        "--cache", action="store_true", help="Cache Massive API responses locally"
    )

    evaluate_parser = subparsers.add_parser("evaluate", help="Evaluate signal accuracy vs SPY")
    _add_config_arg(evaluate_parser)

    serve_parser = subparsers.add_parser("serve", help="Start API server")
    _add_config_arg(serve_parser)

    watchlist_parser = subparsers.add_parser("watchlist", help="Manage the watchlist")
    _add_config_arg(watchlist_parser)
    watchlist_sub = watchlist_parser.add_subparsers(dest="watchlist_command")

    watchlist_add = watchlist_sub.add_parser("add", help="Add a ticker")
    watchlist_add.add_argument("ticker", type=str.upper)

    watchlist_remove = watchlist_sub.add_parser("remove", help="Remove a ticker")
    watchlist_remove.add_argument("ticker", type=str.upper)

    watchlist_sub.add_parser("list", help="List all tickers")

    args = parser.parse_args()

    if args.command == "trade":
        from truenorth.trading import trade

        if args.cache:
            import truenorth.trading as _trading
            from truenorth.massive_cached import CachedMassiveClient

            _trading.MassiveClient = CachedMassiveClient  # type: ignore[attr-defined]

        config = load_config(config_path=args.config)
        trade(config)
    elif args.command == "evaluate":
        from truenorth.evaluate import evaluate

        config = load_config(config_path=args.config)
        evaluate(config)
    elif args.command == "serve":
        config = load_config(config_path=args.config)
        from truenorth.server import serve

        serve(config)
    elif args.command == "watchlist":
        from truenorth.watchlist import watchlist

        config = load_config(config_path=args.config)
        watchlist(args, config)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
