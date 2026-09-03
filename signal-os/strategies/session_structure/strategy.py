"""
Example candidate: prior New York session range as a box.

Not a live adapter. Shows the harness can grade a session-structure idea
the same way it grades a mechanical or DCA candidate. Box math only —
no dashboard, no journal, no named model.
"""
from typing import List

import pandas as pd

from engine.strategy_base import StrategyBase, BarSignal


NY_OPEN = 9 * 60 + 30
NY_CLOSE = 16 * 60


class Strategy(StrategyBase):
    name = "SessionStructure"
    version = "0.1.0"
    timeframe = "15min"
    session_close_hour = 16

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        ny = df.index.tz_convert("America/New_York") if df.index.tz is not None else df.index
        mins = ny.hour * 60 + ny.minute
        df["in_ny"] = (mins >= NY_OPEN) & (mins < NY_CLOSE)
        day = ny.normalize()
        prior_high = df["high"].groupby(day).max().shift(1)
        prior_low = df["low"].groupby(day).min().shift(1)
        df["prior_day_high"] = day.map(prior_high)
        df["prior_day_low"] = day.map(prior_low)
        return df

    def generate_signals(self, df: pd.DataFrame) -> List[BarSignal]:
        signals = []
        for i in range(len(df)):
            action = "none"
            entry = stop = target = None
            high = df["prior_day_high"].iloc[i]
            low = df["prior_day_low"].iloc[i]
            close = float(df["close"].iloc[i])
            in_ny = bool(df["in_ny"].iloc[i])
            if in_ny and pd.notna(high) and pd.notna(low) and high > low:
                if close > float(high):
                    action = "entry_long"
                    entry = close
                    stop = float(low)
                    target = entry + (entry - stop)
            signals.append(BarSignal(
                timestamp=df.index[i],
                action=action,
                entry_price=entry,
                stop_loss=stop,
                take_profit=target,
            ))
        return signals
