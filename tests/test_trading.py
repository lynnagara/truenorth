from truenorth.agent import Analysis
from truenorth.config import RiskConfig
from truenorth.trading import HeldWithExit, NoPosition, prioritize

RISK = RiskConfig(
    max_position_pct=0.10,
    min_position_pct=0.03,
    max_daily_buys=2,
    buy_threshold=0.65,
    sell_threshold=-0.3,
    entry_update_threshold=0.02,
    target_update_threshold=0.05,
    max_entry_discount=0.05,
)


def _analysis(signal: float, entry: float | None = None, target: float | None = None) -> Analysis:
    return Analysis(signal=signal, entry_price=entry, target_price=target, reasoning="test")


def test_prioritize_exits_before_buys_and_higher_signal_first():
    results = {
        "LOW": (NoPosition(), _analysis(0.7, entry=150.0, target=170.0), None),
        "HIGH": (NoPosition(), _analysis(0.9, entry=800.0, target=900.0), None),
        "EXIT": (HeldWithExit(order_id="x", target_price=300.0), _analysis(-0.5), None),
    }
    ordered = prioritize(results, RISK, buys_today=0)
    tickers = [t for t, _, _ in ordered]
    assert tickers == ["EXIT", "HIGH", "LOW"]
