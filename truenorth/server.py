import psycopg
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from truenorth.config import Config

app = FastAPI(title="True North")


class WatchlistItem(BaseModel):
    ticker: str


def create_app(config: Config) -> FastAPI:
    @app.get("/watchlist")
    def get_watchlist() -> list[str]:
        with psycopg.connect(config.database_url) as conn:
            rows = conn.execute("SELECT ticker FROM watchlist ORDER BY ticker").fetchall()
        return [row[0] for row in rows]

    @app.post("/watchlist", status_code=201)
    def add_ticker(item: WatchlistItem) -> WatchlistItem:
        with psycopg.connect(config.database_url) as conn:
            try:
                conn.execute("INSERT INTO watchlist (ticker) VALUES (%s)", (item.ticker.upper(),))
                conn.commit()
            except psycopg.errors.UniqueViolation:
                raise HTTPException(
                    status_code=409, detail=f"{item.ticker} is already on the watchlist"
                )
        return WatchlistItem(ticker=item.ticker.upper())

    @app.delete("/watchlist/{ticker}", status_code=204)
    def remove_ticker(ticker: str) -> None:
        with psycopg.connect(config.database_url) as conn:
            result = conn.execute("DELETE FROM watchlist WHERE ticker = %s", (ticker.upper(),))
            conn.commit()
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail=f"{ticker} not found in watchlist")

    return app


def serve(config: Config) -> None:
    create_app(config)
    uvicorn.run(app, host="0.0.0.0", port=8000)
