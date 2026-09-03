"""
Synthetic OHLCV for the public harness. No live exchange fetch in this snapshot.

Plug a CSV via load_csv() when you have your own bars. Asset-class adapters
(DEX, tokenized ETF / stock) are a shape, not live wires here.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

import numpy as np
import pandas as pd


def synthetic_ohlcv(
    symbol: str = "BTCUSDT",
    start: str = "2025-07-01",
    end: str = "2025-09-01",
    minutes: int = 1,
    seed: int = 42,
) -> pd.DataFrame:
    """Seeded random-walk bars. Enough for gates and the planted-bug self-test."""
    rng = np.random.default_rng(seed + sum(ord(c) for c in symbol[:3]))
    start_ts = pd.Timestamp(start, tz="UTC")
    end_ts = pd.Timestamp(end, tz="UTC")
    index = pd.date_range(start_ts, end_ts, freq=f"{minutes}min", inclusive="left")
    n = len(index)
    if n < 10:
        raise ValueError("Date range too short for a synthetic series")

    base = {"BTC": 65000.0, "ETH": 3200.0, "SOL": 150.0, "ETF": 100.0}.get(
        symbol[:3].upper(), 100.0
    )
    vol = 0.0008 * np.sqrt(minutes)
    rets = rng.normal(0.00002, vol, size=n)
    close = base * np.exp(np.cumsum(rets))
    noise = rng.uniform(0.0002, 0.0015, size=n)
    high = close * (1 + noise)
    low = close * (1 - noise)
    open_ = np.empty(n)
    open_[0] = base
    open_[1:] = close[:-1]
    volume = rng.uniform(50, 500, size=n)

    df = pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum.reduce([open_, high, close]),
            "low": np.minimum.reduce([open_, low, close]),
            "close": close,
            "volume": volume,
        },
        index=index,
    )
    return df


def load_csv(filepath: str) -> pd.DataFrame:
    """
    Load OHLCV from CSV.
    Expects columns: timestamp/datetime, open, high, low, close, volume
    """
    df = pd.read_csv(filepath, parse_dates=[0], index_col=0)
    df.columns = [c.lower().strip() for c in df.columns]

    required = ["open", "high", "low", "close"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    if "volume" not in df.columns:
        df["volume"] = 0.0

    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")

    return df.sort_index()
