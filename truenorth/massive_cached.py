import json
import time
from dataclasses import asdict
from pathlib import Path

from truenorth.massive import Fundamentals, MassiveClient

_CACHE_DIR = Path(__file__).parent.parent / ".massive_cache"
_CACHE_TTL = 60 * 60 * 24  # 24 hours


class CachedMassiveClient(MassiveClient):
    def get_fundamentals(
        self, ticker: str, last_price: float, _retries: int = 3, _delay: float = 12.0
    ) -> Fundamentals:
        cache_path = _CACHE_DIR / f"fundamentals_{ticker}.json"
        if cache_path.exists() and time.time() - cache_path.stat().st_mtime < _CACHE_TTL:
            return Fundamentals(**json.loads(cache_path.read_text()))

        result = super().get_fundamentals(ticker, last_price, _retries=_retries, _delay=_delay)
        _CACHE_DIR.mkdir(exist_ok=True)
        cache_path.write_text(json.dumps(asdict(result)))
        return result
