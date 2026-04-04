"""
Place a small OTO order on the paper account, inspect the open orders list, then cancel it.
Run with: uv run python scripts/place_then_cancel_order.py
"""

import json
import os

from alpaca.trading.enums import QueryOrderStatus
from alpaca.trading.requests import GetOrdersRequest

from truenorth.alpaca import AlpacaClient

client = AlpacaClient(
    os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"], paper=True
)

# Buy well below market so it won't fill during the test
order_id = client.place_order(
    ticker="AAPL",
    qty=1,
    entry_price=1.00,
    target_price=200.00,
)
print(f"placed order: {order_id}")

print("\n=== open orders ===")
orders = client._trading.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN))
for order in orders:
    print(json.dumps(order.model_dump(), indent=2, default=str))  # type:ignore[attr-defined]

print("\n=== cancelling ===")
client.cancel_order(order_id)
print("done")
