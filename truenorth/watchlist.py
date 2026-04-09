import psycopg

from truenorth.config import Config


def watchlist(args, config: Config) -> None:
    if args.watchlist_command == "add":
        with psycopg.connect(config.database_url) as conn:
            conn.execute(
                "INSERT INTO watchlist (ticker) VALUES (%s) ON CONFLICT DO NOTHING",
                (args.ticker,),
            )
            conn.commit()
        print(f"+ {args.ticker}")

    elif args.watchlist_command == "remove":
        with psycopg.connect(config.database_url) as conn:
            conn.execute("DELETE FROM watchlist WHERE ticker = %s", (args.ticker,))
            conn.commit()
        print(f"- {args.ticker}")

    elif args.watchlist_command == "list":
        with psycopg.connect(config.database_url) as conn:
            rows = conn.execute("SELECT ticker FROM watchlist ORDER BY ticker").fetchall()
        for (ticker,) in rows:
            print(ticker)

    else:
        print("Usage: truenorth watchlist [add|remove|list]")
