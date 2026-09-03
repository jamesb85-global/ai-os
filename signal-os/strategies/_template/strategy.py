"""
Scaffold for a harness candidate.

Subclass StrategyBase. Emit signals only — no PnL, fees, or drawdown.
validate.py imports this module and instantiates Strategy().

    python validate.py --strategy strategies._template.strategy
"""
from typing import List

import pandas as pd

from engine.strategy_base import StrategyBase, BarSignal


class Strategy(StrategyBase):
    name = "Template"
    version = "0.1.0"
    timeframe = "15min"
    session_close_hour = None  # set to e.g. 16 to flatten at 4pm NY

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["ema_fast"] = df["close"].ewm(span=12).mean().shift(1)
        df["ema_slow"] = df["close"].ewm(span=26).mean().shift(1)
        return df

    def generate_signals(self, df: pd.DataFrame) -> List[BarSignal]:
        signals = []
        for i in range(len(df)):
            action = "none"
            entry = stop = target = None
            if i > 0 and pd.notna(df["ema_fast"].iloc[i]) and pd.notna(df["ema_slow"].iloc[i]):
                crossed_up = (
                    df["ema_fast"].iloc[i] > df["ema_slow"].iloc[i]
                    and df["ema_fast"].iloc[i - 1] <= df["ema_slow"].iloc[i - 1]
                )
                if crossed_up:
                    action = "entry_long"
                    entry = float(df["close"].iloc[i])
                    stop = entry * 0.99
                    target = entry * 1.02
            signals.append(BarSignal(
                timestamp=df.index[i],
                action=action,
                entry_price=entry,
                stop_loss=stop,
                take_profit=target,
            ))
        return signals
