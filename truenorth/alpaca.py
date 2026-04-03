from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestTradeRequest


class AlpacaClient:
    def __init__(self, api_key: str, secret_key: str):
        self._data = StockHistoricalDataClient(api_key, secret_key)

    def get_latest_price(self, ticker: str) -> float:
        request = StockLatestTradeRequest(symbol_or_symbols=ticker)
        trade = self._data.get_stock_latest_trade(request)
        return float(trade[ticker].price)
