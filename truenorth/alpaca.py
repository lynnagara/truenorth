from datetime import date, datetime, timedelta, timezone

from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.historical import NewsClient, StockHistoricalDataClient
from alpaca.data.requests import NewsRequest, StockBarsRequest, StockLatestTradeRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import (
    OrderClass,
    OrderSide,
    OrderType,
    QueryOrderStatus,
    TimeInForce,
)
from alpaca.trading.models import Order, Position
from alpaca.trading.requests import (
    ClosePositionRequest,
    GetOrdersRequest,
    LimitOrderRequest,
    TakeProfitRequest,
)


class AlpacaClient:
    def __init__(self, api_key: str, secret_key: str, paper: bool = True):
        self._data = StockHistoricalDataClient(api_key, secret_key)
        self._news = NewsClient(api_key, secret_key)
        self._trading = TradingClient(api_key, secret_key, paper=paper)
        # IEX is free; SIP is comprehensive but requires a paid subscription.
        self._feed = DataFeed.IEX

    def get_latest_price(self, ticker: str) -> float:
        request = StockLatestTradeRequest(symbol_or_symbols=ticker, feed=self._feed)
        trade = self._data.get_stock_latest_trade(request)
        return float(trade[ticker].price)

    def get_price_on_date(self, ticker: str, target: date) -> float | None:
        """Return the closing price on the last trading day on or before target. Returns None if no bar found."""
        request = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=TimeFrame(1, TimeFrameUnit.Day),  # type: ignore[arg-type]
            start=datetime(target.year, target.month, target.day, tzinfo=timezone.utc)
            - timedelta(days=5),
            end=datetime(target.year, target.month, target.day, tzinfo=timezone.utc),
            adjustment=Adjustment.SPLIT,
        )
        bars = self._data.get_stock_bars(request)
        ticker_bars = bars.data.get(ticker, [])  # type: ignore[union-attr]
        if not ticker_bars:
            return None
        return float(ticker_bars[-1].close)

    def get_price_history(self, ticker: str, days: int = 90) -> list[tuple[date, float]]:
        end = datetime.now(tz=timezone.utc)
        start = end - timedelta(days=days)
        request = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=TimeFrame(1, TimeFrameUnit.Day),  # type: ignore[arg-type] -- pyright sees TimeFrameUnit.Day as str due to str+Enum inheritance, but it is a valid TimeFrameUnit at runtime
            start=start,
            end=end,
            adjustment=Adjustment.SPLIT,
            feed=self._feed,
        )
        bars = self._data.get_stock_bars(request)
        return [(bar.timestamp.date(), float(bar.close)) for bar in bars[ticker]]

    def get_news(self, ticker: str, days: int = 10, limit: int = 10) -> list[str]:
        """Return recent news headlines and summaries for a ticker."""
        start = datetime.now(tz=timezone.utc) - timedelta(days=days)
        request = NewsRequest(symbols=ticker, start=start, limit=limit, exclude_contentless=True)
        news = self._news.get_news(request)
        items: list = news.data.get("news", [])  # type: ignore[union-attr]
        result = []
        for item in items:
            item_dict = item if isinstance(item, dict) else item.__dict__
            created_at = item_dict.get("created_at")
            headline = item_dict.get("headline", "")
            summary = item_dict.get("summary", "")
            date_str = created_at.strftime("%Y-%m-%d") if created_at else "unknown"
            line = f"[{date_str}] {headline}"
            if summary:
                line += f" — {summary}"
            result.append(line)
        return result

    def get_account_info(self) -> tuple[float, float]:
        """Returns (equity, buying_power)."""
        account = self._trading.get_account()
        return float(account.equity), float(account.buying_power)  # type: ignore[arg-type]

    def place_order(
        self,
        ticker: str,
        qty: float,
        entry_price: float,
        target_price: float,
    ) -> str:
        """Place a GTC limit buy that triggers a take-profit limit sell when filled. Returns the order ID."""
        order = self._trading.submit_order(
            LimitOrderRequest(
                symbol=ticker,
                qty=qty,
                side=OrderSide.BUY,
                type=OrderType.LIMIT,
                time_in_force=TimeInForce.GTC,
                order_class=OrderClass.OTO,
                limit_price=entry_price,
                take_profit=TakeProfitRequest(limit_price=target_price),
            )
        )
        return str(order.id)  # type: ignore[union-attr]

    def get_open_orders(self) -> list[Order]:
        return self._trading.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN))  # type: ignore[return-value]

    def get_todays_buy_count(self) -> int:
        """Count buy orders submitted today (open or filled)."""
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        orders: list[Order] = self._trading.get_orders(  # type: ignore[assignment]
            GetOrdersRequest(status=QueryOrderStatus.ALL, side=OrderSide.BUY, after=today_start)
        )
        return len(orders)

    def get_open_position(self, ticker: str) -> Position:
        """Raises an exception if no position exists for the ticker."""
        return self._trading.get_open_position(ticker)  # type: ignore[return-value]

    def get_open_positions(self) -> list[Position]:
        return self._trading.get_all_positions()  # type: ignore[return-value]

    def place_take_profit(self, ticker: str, target_price: float) -> str:
        """Place a standalone GTC limit sell for the full position. Returns the order ID."""
        position = self.get_open_position(ticker)
        order = self._trading.submit_order(
            LimitOrderRequest(
                symbol=ticker,
                qty=position.qty,
                side=OrderSide.SELL,
                type=OrderType.LIMIT,
                time_in_force=TimeInForce.GTC,
                limit_price=target_price,
            )
        )
        return str(order.id)  # type: ignore[union-attr]

    def cancel_order(self, order_id: str) -> None:
        self._trading.cancel_order_by_id(order_id)

    def close_position(self, ticker: str) -> None:
        """Market sell entire position immediately."""
        self._trading.close_position(ticker, ClosePositionRequest(percentage="100"))
