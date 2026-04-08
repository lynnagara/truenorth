from datetime import datetime, timedelta, timezone

import psycopg
from scipy.stats import pearsonr

from truenorth.alpaca import AlpacaClient
from truenorth.config import Config, TradingMode

INTERVALS = [1, 2, 7, 14]  # days; 1d and 2d are temporary for faster dev feedback


def evaluate(config: Config) -> None:
    alpaca = AlpacaClient(
        api_key=config.alpaca_api_key,
        secret_key=config.alpaca_secret_key,
        paper=config.execution.trading == TradingMode.PAPER,
    )

    now = datetime.now(tz=timezone.utc)

    spy_cache: dict = {}

    def spy_price(d):
        if d not in spy_cache:
            spy_cache[d] = alpaca.get_price_on_date("SPY", d)
        return spy_cache[d]

    for prompt_name in config.experiments.all_prompts:
        print(f"\nprompt: {prompt_name}")
        print(
            f"{'interval':>10}  {'n':>5}  {'signal/alpha correlation':>24}  {'mean alpha (vs SPY)':>20}"
        )
        print("-" * 70)

        for interval_days in INTERVALS:
            cutoff = now - timedelta(days=interval_days)

            with psycopg.connect(config.database_url) as conn:
                rows = conn.execute(
                    """
                    SELECT DISTINCT ON (ticker, created_at::date) ticker, signal, last_price, created_at
                    FROM analysis
                    WHERE signal != 0 AND created_at <= %s AND prompt_name = %s
                    ORDER BY ticker, created_at::date, created_at DESC
                    """,
                    (cutoff, prompt_name),
                ).fetchall()

            if not rows:
                print(f"{interval_days:>9}d  {'—':>5}  {'—':>24}  {'—':>20}")
                continue

            signals = []
            alphas = []
            for ticker, signal, last_price, created_at in rows:
                signal_date = created_at.date()
                outcome_date = (created_at + timedelta(days=interval_days)).date()

                spy_entry = spy_price(signal_date)
                spy_exit = spy_price(outcome_date)
                ticker_exit = alpaca.get_price_on_date(ticker, outcome_date)

                if spy_entry is None or spy_exit is None or ticker_exit is None:
                    continue

                ticker_return = (ticker_exit - last_price) / last_price
                spy_return = (spy_exit - spy_entry) / spy_entry
                alpha = ticker_return - spy_return
                signals.append(signal)
                alphas.append(alpha)

            n = len(signals)
            if n == 0:
                print(f"{interval_days:>9}d  {'—':>5}  {'—':>24}  {'—':>20}")
                continue

            corr, _ = pearsonr(signals, alphas) if n >= 2 else (None, None)
            mean_alpha = sum(alphas) / n
            corr_str = f"{corr:+.3f}" if corr is not None else "—"
            print(f"{interval_days:>9}d  {n:>5}  {corr_str:>24}  {mean_alpha:>+20.2%}")
