"""
Every strategy implements this interface. Strategies emit SIGNALS ONLY:
entry/exit decisions + stop/target prices. No PnL math, no fee accounting,
no position tracking, no drawdown logic — that lives in the engine.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List
import pandas as pd


@dataclass
class BarSignal:
    """One bar's strategy decision. Only uses data available at bar close."""
    timestamp: pd.Timestamp
    action: str  # "entry_long", "entry_short", "exit", "none"

    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    position_size: Optional[float] = None
    entry_order_type: str = "market"  # "market"=taker, "limit"=maker fee on entry

    exit_reason: Optional[str] = None  # "tp", "sl", "trailing_stop", "signal_reversal"

    regime: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class StrategyBase(ABC):
    """
    Strategy interface — signals only, no execution logic.

    Subclass and implement:
      - compute_indicators(df) -> df with indicator columns added
      - generate_signals(df) -> list of BarSignal per bar

    The engine handles: fills, slippage, commission, position tracking,
    partial exits, equity curve, drawdown enforcement, and reporting.
    """

    name: str = "UnnamedStrategy"
    version: str = "0.1.0"
    timeframe: str = "15min"

    # Optional session-force-close hour (NY time).
    # None = hold across sessions; set to e.g. 16 for NY 4pm flat.
    session_close_hour: Optional[int] = None

    @abstractmethod
    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add indicator columns. Must only use data available at each bar's close."""
        ...

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> List[BarSignal]:
        """
        One signal per bar. Must only use data available at bar close.

        Rules:
        - "entry_long" / "entry_short": must include entry_price, stop_loss, take_profit
        - "exit": must include exit_reason
        - "none": no action this bar
        - No same-bar entry+exit (engine ignores exits on entry bars)
        """
        ...

    def get_config(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "timeframe": self.timeframe,
        }
