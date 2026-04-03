import time
from dataclasses import dataclass

from massive import RESTClient
from massive.rest.models import TickerDetails
from urllib3.exceptions import MaxRetryError


@dataclass
class Fundamentals:
    market_cap: float | None  # USD
    eps: float | None  # USD, earnings per share
    pe_ratio: float | None  # price / EPS
    industry: str | None  # SIC description


class MassiveClient:
    def __init__(self, api_key: str):
        self._client = RESTClient(api_key=api_key)

    def get_fundamentals(
        self, ticker: str, last_price: float, _retries: int = 10
    ) -> Fundamentals:
        try:
            return self._get_fundamentals(ticker, last_price)
        except MaxRetryError:
            if _retries <= 0:
                raise
            time.sleep(10)
            return self.get_fundamentals(ticker, last_price, _retries=_retries - 1)

    def _get_fundamentals(self, ticker: str, last_price: float) -> Fundamentals:
        details = self._client.get_ticker_details(ticker=ticker)
        # massive sdk seems to return Union[TickerDetails, HTTPResponse] here?
        assert isinstance(details, TickerDetails)
        market_cap = float(details.market_cap) if details.market_cap else None
        industry = details.sic_description or None

        eps = None
        financials = self._client.vx.list_stock_financials(ticker=ticker, limit=1)  # type: ignore[attr-defined]
        for financial in financials:
            try:
                eps = float(
                    financial.financials.income_statement.basic_earnings_per_share.value  # type: ignore[attr-defined]
                )
            except AttributeError, TypeError:
                pass
            break

        pe_ratio = (last_price / eps) if eps and eps != 0 else None

        return Fundamentals(
            market_cap=market_cap, eps=eps, pe_ratio=pe_ratio, industry=industry
        )
