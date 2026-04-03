from datetime import date, datetime, timedelta, timezone

from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestTradeRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit


class AlpacaClient:
    def __init__(self, api_key: str, secret_key: str):
        self._data = StockHistoricalDataClient(api_key, secret_key)

    def get_latest_price(self, ticker: str) -> float:
        request = StockLatestTradeRequest(symbol_or_symbols=ticker, feed=DataFeed.IEX)
        trade = self._data.get_stock_latest_trade(request)
        return float(trade[ticker].price)

    def get_price_history(
        self, ticker: str, days: int = 90
    ) -> list[tuple[date, float]]:
        end = datetime.now(tz=timezone.utc)
        start = end - timedelta(days=days)
        request = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=TimeFrame(1, TimeFrameUnit.Day),  # type: ignore[arg-type] -- pyright sees TimeFrameUnit.Day as str due to str+Enum inheritance, but it is a valid TimeFrameUnit at runtime
            start=start,
            end=end,
            adjustment=Adjustment.SPLIT,
            # IEX feed is free tier; SIP (consolidated) requires a paid subscription.
            # On a live funded account, switch to DataFeed.SIP for more accurate data.
            # TODO: make feed configurable based on execution.trading mode
            feed=DataFeed.IEX,
        )
        bars = self._data.get_stock_bars(request)
        return [(bar.timestamp.date(), float(bar.close)) for bar in bars[ticker]]
