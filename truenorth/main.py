import argparse
from pathlib import Path

from truenorth.config import load_config


def main():
    parser = argparse.ArgumentParser(prog="truenorth")
    parser.add_argument("--config", type=Path, required=True, help="Path to yaml config file")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("trade", help="Execute trading cycle")
    subparsers.add_parser("serve", help="Start API server")

    args = parser.parse_args()
    config = load_config(config_path=args.config)

    print(f"llm:        {config.llm.provider} / {config.llm.model}")
    print(f"embeddings: {config.embeddings.provider}")
    print(f"autonomy:   {config.execution.autonomy}")
    print(f"trading:    {config.execution.trading}")

    if args.command == "trade":
        print("trade: not implemented")
    elif args.command == "serve":
        print("serve: not implemented")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
