import time
from dataclasses import dataclass

from massive import RESTClient
from massive.rest.models import TickerDetails
from urllib3.exceptions import MaxRetryError


@dataclass
class Fundamentals:
    market_cap: float | None  # USD
    eps: float | None  # USD, earnings per share (most recent quarter)
    pe_ratio: float | None  # price / EPS
    industry: str | None  # SIC description
    revenues: float | None  # USD, most recent quarter
    gross_profit: float | None  # USD, most recent quarter
    gross_margin: float | None  # gross_profit / revenues
    operating_cash_flow: float | None  # USD, most recent quarter
    long_term_debt: float | None  # USD
    equity: float | None  # USD


class MassiveClient:
    def __init__(self, api_key: str):
        self._client = RESTClient(api_key=api_key)

    def get_fundamentals(self, ticker: str, last_price: float, _retries: int = 3, _delay: float = 12.0) -> Fundamentals:
        try:
            result = self._get_fundamentals(ticker, last_price)
            time.sleep(12)
            return result
        except MaxRetryError:
            if _retries <= 0:
                raise
            time.sleep(_delay)
            return self.get_fundamentals(ticker, last_price, _retries=_retries - 1, _delay=_delay * 2)

    def _get_fundamentals(self, ticker: str, last_price: float) -> Fundamentals:
        details = self._client.get_ticker_details(ticker=ticker)
        # massive sdk seems to return Union[TickerDetails, HTTPResponse] here?
        assert isinstance(details, TickerDetails)
        market_cap = float(details.market_cap) if details.market_cap else None
        industry = details.sic_description or None

        def _val(obj, *attrs):
            try:
                for a in attrs:
                    obj = getattr(obj, a)
                return float(obj) if obj is not None else None
            except (AttributeError, TypeError):
                return None

        eps = None
        revenues = None
        gross_profit = None
        gross_margin = None
        operating_cash_flow = None
        long_term_debt = None
        equity = None

        quarters = []
        financials = self._client.vx.list_stock_financials(ticker=ticker, limit=1)  # type: ignore[attr-defined]
        for financial in financials:
            quarters.append(financial)
            break

        if quarters:
            fin = quarters[0].financials
            eps = _val(fin, "income_statement", "basic_earnings_per_share", "value")
            revenues = _val(fin, "income_statement", "revenues", "value")
            gross_profit = _val(fin, "income_statement", "gross_profit", "value")
            gross_margin = (gross_profit / revenues) if gross_profit and revenues else None
            operating_cash_flow = _val(fin, "cash_flow_statement", "net_cash_flow_from_operating_activities", "value")
            long_term_debt = _val(fin, "balance_sheet", "long_term_debt", "value")
            equity = _val(fin, "balance_sheet", "equity", "value")

        pe_ratio = (last_price / eps) if eps and eps != 0 else None

        return Fundamentals(
            market_cap=market_cap,
            eps=eps,
            pe_ratio=pe_ratio,
            industry=industry,
            revenues=revenues,
            gross_profit=gross_profit,
            gross_margin=gross_margin,
            operating_cash_flow=operating_cash_flow,
            long_term_debt=long_term_debt,
            equity=equity,
        )
