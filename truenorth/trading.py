import json
import time
from dataclasses import asdict, dataclass

import psycopg
from alpaca.trading.enums import OrderSide

from truenorth.agent import Agent, Analysis
from truenorth.alpaca import AlpacaClient
from truenorth.config import AutonomyMode, Config, RiskConfig, TradingMode
from truenorth.llm import create_llm
from truenorth.market import MacroContext, fetch_macro_context
from truenorth.fundamentals_cache import FundamentalsCache
from truenorth.massive import MassiveClient
from truenorth.prompts import PROMPT_REGISTRY, AnalysisContext
from truenorth.tracing import init_tracing, trace_analysis, trace_run


@dataclass(frozen=True)
class HeldWithExit:
    order_id: str
    target_price: (
        float | None
    )  # None if exit is a market order (not expected — we always place limit take-profits via OTO)


@dataclass(frozen=True)
class PendingBuy:
    order_id: str
    entry_price: float


@dataclass(frozen=True)
class NoPosition: ...


@dataclass(frozen=True)
class HeldNoExit: ...


TickerState = NoPosition | PendingBuy | HeldNoExit | HeldWithExit


def trade(config: Config) -> None:
    llm = create_llm(config.llm, anthropic_api_key=config.anthropic_api_key)
    alpaca = AlpacaClient(
        api_key=config.alpaca_api_key,
        secret_key=config.alpaca_secret_key,
        paper=config.execution.trading == TradingMode.PAPER,
    )
    massive = MassiveClient(config.massive_api_key)
    fundamentals_cache = FundamentalsCache(config.database_url, ttl_hours=config.cache.fundamentals_ttl_hours)

    init_tracing(config)

    macro = fetch_macro_context()
    print(f"VIX: {macro.vix:.1f}  SPY 5d: {macro.spy_change_5d:+.1%}")

    with trace_run():
        primary_results: dict[str, tuple[TickerState, Analysis, AnalysisContext]] = {}

        contexts = fetch_contexts(alpaca, massive, fundamentals_cache, macro, config)

        with psycopg.connect(config.database_url) as conn:
            for prompt_name in config.experiments.all_prompts:
                prompt = PROMPT_REGISTRY[prompt_name]
                agent = Agent(llm=llm, prompt=prompt)
                results = run_analyses(agent, contexts, config)

                for ticker, (state, analysis, _ctx) in results.items():
                    print(
                        f"  [{prompt_name}] {ticker} [{type(state).__name__}]: {analysis.signal}  {analysis.reasoning}"
                    )

                for ticker, (state, analysis, ctx) in results.items():
                    conn.execute(
                        """
                        INSERT INTO analysis (ticker, signal, entry_price, target_price, last_price, reasoning, fundamentals, macro, model, prompt_name)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            ticker,
                            analysis.signal,
                            analysis.entry_price,
                            analysis.target_price,
                            ctx.last_price,
                            analysis.reasoning,
                            json.dumps(asdict(ctx.fundamentals)),
                            json.dumps(ctx.macro.model_dump()),
                            config.llm.model,
                            prompt_name,
                        ),
                    )

                if prompt_name == config.experiments.primary:
                    primary_results = results

            conn.commit()

        for ticker, state, analysis in prioritize(
            primary_results, config.risk, alpaca.get_todays_buy_count()
        ):
            _, ctx = contexts[ticker]
            if config.execution.autonomy == AutonomyMode.AUTONOMOUS:
                handle(ticker, state, analysis, ctx.last_price, alpaca, config.risk)
            else:
                print(
                    f"  [NOTIFY_ONLY] would handle {ticker} ({type(state).__name__}, signal={analysis.signal})"
                )


def fetch_contexts(
    alpaca: AlpacaClient,
    massive: MassiveClient,
    fundamentals_cache: FundamentalsCache,
    macro: MacroContext,
    config: Config,
) -> dict[str, tuple[TickerState, AnalysisContext]]:
    open_orders = alpaca.get_open_orders()
    held_tickers = [str(p.symbol) for p in alpaca.get_open_positions()]
    pending_buy_orders = {str(o.symbol): o for o in open_orders if o.side == OrderSide.BUY}
    pending_sell_orders = {str(o.symbol): o for o in open_orders if o.side == OrderSide.SELL}

    with psycopg.connect(config.database_url) as conn:
        rows = conn.execute("SELECT ticker FROM watchlist ORDER BY ticker").fetchall()
    watchlist_tickers = [row[0] for row in rows]

    all_tickers = list(dict.fromkeys(held_tickers + list(pending_buy_orders) + watchlist_tickers))

    contexts: dict[str, tuple[TickerState, AnalysisContext]] = {}
    for ticker in all_tickers:
        last_price = alpaca.get_latest_price(ticker)
        history = alpaca.get_price_history(ticker)
        fundamentals = fundamentals_cache.get(ticker) or massive.get_fundamentals(ticker, last_price)
        fundamentals_cache.set(ticker, fundamentals)
        news = alpaca.get_news(ticker)

        ctx = AnalysisContext(
            ticker=ticker,
            last_price=last_price,
            price_history=history,
            fundamentals=fundamentals,
            macro=macro,
            news=news,
        )

        if ticker in held_tickers:
            if ticker in pending_sell_orders:
                sell_order = pending_sell_orders[ticker]
                state: TickerState = HeldWithExit(
                    order_id=str(sell_order.id),
                    target_price=float(sell_order.limit_price)
                    if sell_order.limit_price is not None
                    else None,
                )
            else:
                state = HeldNoExit()
        elif ticker in pending_buy_orders:
            buy_order = pending_buy_orders[ticker]
            assert buy_order.limit_price is not None
            state = PendingBuy(order_id=str(buy_order.id), entry_price=float(buy_order.limit_price))
        else:
            state = NoPosition()

        contexts[ticker] = (state, ctx)

    return contexts


def run_analyses(
    agent: Agent,
    contexts: dict[str, tuple[TickerState, AnalysisContext]],
    config: Config,
) -> dict[str, tuple[TickerState, Analysis, AnalysisContext]]:
    results: dict[str, tuple[TickerState, Analysis, AnalysisContext]] = {}
    for ticker, (state, ctx) in contexts.items():
        try:
            with trace_analysis(ctx, config.llm.model) as record:
                analysis = agent.analyze(ctx)
                record(analysis.model_dump())
            results[ticker] = (state, analysis, ctx)
        except Exception as e:
            print(f"  [ERROR] {ticker}: {e}")
    return results


def prioritize(
    results: dict[str, tuple[TickerState, Analysis, AnalysisContext]],
    risk: RiskConfig,
    buys_today: int,
) -> list[tuple[str, TickerState, Analysis]]:
    """
    exits first, then order updates, then new buys descreasing by signal strength.
    """
    items = [(t, s, a) for t, (s, a, _ctx) in results.items()]

    exits: list[tuple[str, TickerState, Analysis]] = [
        (t, s, a)
        for t, s, a in items
        if isinstance(s, (HeldWithExit, HeldNoExit)) and a.signal <= risk.sell_threshold
    ]
    take_profit_updates: list[tuple[str, TickerState, Analysis]] = [
        (t, s, a)
        for t, s, a in items
        if isinstance(s, HeldWithExit)
        and a.target_price is not None
        and s.target_price is not None
        and abs(a.target_price - s.target_price) / s.target_price > risk.target_update_threshold
    ]
    pending_buy_updates: list[tuple[str, TickerState, Analysis]] = [
        (t, s, a)
        for t, s, a in items
        if isinstance(s, PendingBuy)
        and a.entry_price is not None
        and abs(a.entry_price - s.entry_price) / s.entry_price > risk.entry_update_threshold
    ]
    new_buys: list[tuple[str, TickerState, Analysis]] = sorted(  # type: ignore[assignment]
        [
            (t, s, a)
            for t, s, a in items
            if isinstance(s, NoPosition) and a.signal >= risk.buy_threshold
        ],
        key=lambda x: x[2].signal,
        reverse=True,
    )[: max(0, risk.max_daily_buys - buys_today)]

    ordered = exits + take_profit_updates + pending_buy_updates + new_buys
    all_tickers = [t for t, _, _ in ordered]
    assert len(all_tickers) == len(set(all_tickers)), "ticker appears in multiple buckets"

    return ordered


def _place_buy_order(
    ticker: str, analysis: Analysis, last_price: float, alpaca: AlpacaClient, risk: RiskConfig
) -> None:
    assert analysis.entry_price is not None and analysis.target_price is not None
    min_entry = last_price * (1 - risk.max_entry_discount)
    if analysis.entry_price < min_entry:
        print(
            f"skipping buy for {ticker} — suggested entry {analysis.entry_price:.2f} is too far below last price {last_price:.2f}"
        )
        return
    entry_price = round(min(analysis.entry_price, last_price), 2)
    equity, buying_power = alpaca.get_account_info()
    min_qty = int((equity * risk.min_position_pct) / entry_price)
    max_qty = int((equity * risk.max_position_pct) / entry_price)
    affordable_qty = int(buying_power / entry_price)
    qty = min(max_qty, affordable_qty)
    if qty < min_qty:
        print(f"Not enough buying power, skipping buy for {ticker}")
        return
    print(f"placing buy for {ticker}: qty={qty} entry={entry_price:.2f} target={analysis.target_price:.2f}")
    alpaca.place_order(ticker, qty, entry_price, analysis.target_price)


def handle(
    ticker: str,
    state: TickerState,
    analysis: Analysis,
    last_price: float,
    alpaca: AlpacaClient,
    risk: RiskConfig,
) -> None:
    # status is derived at analysis time and may be stale by the time we act
    # re-fetching state is not a guarantee either, so we rely on Alpaca to reject invalid orders

    if isinstance(state, NoPosition):
        if analysis.signal >= risk.buy_threshold:
            _place_buy_order(ticker, analysis, last_price, alpaca, risk)

    elif isinstance(state, PendingBuy):
        if analysis.signal < risk.buy_threshold:
            print(f"cancelling order {state.order_id} ({ticker})")
            alpaca.cancel_order(state.order_id)
        elif analysis.entry_price is not None:
            drift = abs(analysis.entry_price - state.entry_price) / state.entry_price
            if drift > risk.entry_update_threshold:
                print(f"replacing buy order for {ticker}: entry {state.entry_price:.2f} -> {analysis.entry_price:.2f}")
                alpaca.cancel_order(state.order_id)
                _place_buy_order(ticker, analysis, last_price, alpaca, risk)

    elif isinstance(state, HeldNoExit):
        # handles the off-chance the sell leg was cancelled externally (e.g. manually or by Alpaca)
        if analysis.target_price is None:
            print(f"closing position {ticker}")
            alpaca.close_position(ticker)  # market sell — we want out immediately
        else:
            print(f"re-placing take-profit for {ticker} at {analysis.target_price:.2f}")
            alpaca.place_take_profit(ticker, analysis.target_price)

    elif isinstance(state, HeldWithExit):
        if analysis.signal <= risk.sell_threshold:
            print(f"closing position {ticker} (signal={analysis.signal:.2f})")
            alpaca.cancel_order(state.order_id)
            alpaca.close_position(ticker)  # market sell — take-profit cancelled, exit immediately
        elif analysis.target_price is not None and state.target_price is not None:
            drift = abs(analysis.target_price - state.target_price) / state.target_price
            if drift > risk.target_update_threshold:
                print(f"replacing take-profit for {ticker}: target {state.target_price:.2f} -> {analysis.target_price:.2f}")
                alpaca.cancel_order(state.order_id)
                alpaca.place_take_profit(ticker, analysis.target_price)

    else:
        raise ValueError(f"Unhandled TickerState: {type(state).__name__}")
