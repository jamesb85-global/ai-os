"""
Venue profiles — fees, funding, drawdown rules, capital.

Defaults: GROSS (zero friction) + EXCHANGE (generic perp).
A DailyRisk profile is an optional example of a desk rule, not a named shop.
"""
from dataclasses import dataclass, replace
from typing import Optional, Dict, List


SLIPPAGE_BPS: Dict[str, Dict[str, float]] = {
    "BTC": {"market": 0.5, "stop": 1.0},
    "ETH": {"market": 1.0, "stop": 1.5},
    "SOL": {"market": 1.5, "stop": 3.0},
    "ETF": {"market": 0.5, "stop": 1.0},
}


def get_slippage_pct(symbol: str, order_type: str) -> float:
    """Return per-side slippage as a decimal fraction (e.g. 0.0001 = 1 bps)."""
    asset = symbol[:3].upper()
    entry = SLIPPAGE_BPS.get(asset, {"market": 1.0, "stop": 1.5})
    bps = entry.get("stop" if order_type in ("stop", "sl") else "market", 1.0)
    return bps / 10_000.0


@dataclass
class FundingConfig:
    interval_hours: float
    rate_pct: float
    static: bool = True
    align_utc: int = 0


@dataclass
class VenueProfile:
    """Ruleset for one venue: fees, funding, drawdown model, targets."""
    name: str

    maker_fee_pct: float
    taker_fee_pct: float

    funding: Optional[FundingConfig] = None

    dd_model: str = "none_self_funded"
    #   "trailing_tick"    — daily floor on unrealized equity, trails to intraday peak
    #   "daily_snapshot"   — daily floor set once from closed balance
    #   "none_self_funded" — no terminal DD; margin liquidation only

    daily_dd_pct: float = 0.0
    max_loss_pct: float = 0.0
    max_loss_trails: bool = False

    day_reset_utc: str = "00:00"

    profit_target_pct: float = 0.0
    min_trading_days: int = 0
    consistency_pct: float = 0.0
    initial_capital: float = 10_000.0

    max_leverage: float = 20.0
    max_leverage_by_symbol: Optional[Dict[str, float]] = None


def with_capital(venue: VenueProfile, capital: float) -> VenueProfile:
    return replace(venue, initial_capital=capital)


GROSS = VenueProfile(
    name="GROSS",
    maker_fee_pct=0.0,
    taker_fee_pct=0.0,
    funding=None,
    dd_model="none_self_funded",
    day_reset_utc="00:00",
    initial_capital=10_000.0,
    max_leverage=999.0,
)

EXCHANGE = VenueProfile(
    name="Exchange",
    maker_fee_pct=0.020,
    taker_fee_pct=0.055,
    funding=FundingConfig(interval_hours=8, rate_pct=0.01, static=True, align_utc=0),
    dd_model="none_self_funded",
    day_reset_utc="00:00",
    initial_capital=10_000.0,
    max_leverage=20.0,
)

# Optional example of a daily-risk desk rule. Not a named firm.
DAILY_RISK = VenueProfile(
    name="DailyRisk",
    maker_fee_pct=0.020,
    taker_fee_pct=0.055,
    funding=FundingConfig(interval_hours=8, rate_pct=0.01, static=True, align_utc=0),
    dd_model="daily_snapshot",
    day_reset_utc="00:00",
    daily_dd_pct=3.0,
    max_loss_pct=6.0,
    profit_target_pct=10.0,
    min_trading_days=5,
    initial_capital=50_000.0,
    max_leverage=20.0,
)

DEFAULT_VENUES: List[VenueProfile] = [GROSS, EXCHANGE]
EXAMPLE_VENUES: List[VenueProfile] = [DAILY_RISK]
ALL_VENUES: List[VenueProfile] = DEFAULT_VENUES + EXAMPLE_VENUES


def venue_by_name(name: str) -> Optional[VenueProfile]:
    key = name.lower().replace("_", " ").strip()
    for v in ALL_VENUES:
        if v.name.lower() == key:
            return v
    return None
