"""
Canonical backtest engine.

Consumes BarSignals from any strategy and simulates fills, fees,
position tracking, equity curve, and venue-specific drawdown rules.

One engine, N venue profiles — every strategy settled identically.

DD model dispatch:
  trailing_tick    — daily floor on unrealized, trails to peak
  daily_snapshot   — daily floor from closed balance
  none_self_funded — GROSS / generic exchange (default)
"""
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Optional, Dict

from engine.strategy_base import BarSignal
from engine.venues import (
    VenueProfile, get_slippage_pct,
    EXCHANGE,
)


def trading_day_for_venue(ts_ny, reset_utc: str):
    """Compute trading day based on a venue's UTC reset time.
    ts_ny is a tz-aware NY timestamp; resets are specified as "HH:MM" UTC.
    """
    utc = ts_ny.tz_convert("UTC")
    hour, minute = map(int, reset_utc.split(":"))
    reset = utc.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if utc < reset:
        return (utc - pd.Timedelta(days=1)).date()
    return utc.date()


@dataclass
class ExecutedTrade:
    trade_id: int
    direction: str
    entry_time: pd.Timestamp
    entry_price: float
    exit_time: pd.Timestamp
    exit_price: float
    exit_reason: str
    position_size: float
    pnl: float
    commission: float
    worst_floating_dd: float = 0.0


@dataclass
class BacktestResult:
    trades: List[ExecutedTrade]
    equity_curve: pd.Series
    account_blown: bool
    blow_reason: str
    stats: dict = field(default_factory=dict)
    total_funding: float = 0.0


def run(signals: List[BarSignal], df: pd.DataFrame,
        venue: VenueProfile = None,
        symbol: str = "BTCUSDT",
        risk_per_trade: Optional[float] = None,
        force_close_session_end: bool = False,
        session_end_hour: int = 16,
        ) -> BacktestResult:
    """
    Run the canonical backtest on a list of BarSignals under one venue profile.
    """
    if venue is None:
        venue = EXCHANGE
    if risk_per_trade is None:
        risk_per_trade = venue.initial_capital * 0.01

    equity = venue.initial_capital
    max_dd_floor = venue.initial_capital * (1 - venue.max_loss_pct / 100) if venue.max_loss_pct > 0 else 0

    trades: List[ExecutedTrade] = []
    equity_curve = pd.Series(float(equity), index=df.index, dtype="float64")

    dd_model = venue.dd_model
    daily_start_equity: Dict = {}
    intraday_peak: Dict = {}
    current_day = None
    total_funding = 0.0

    in_position = False
    position = None
    trade_id = 0

    account_blown = False
    blow_reason = ""
    global_max_floating_dd = 0.0

    maker_rate = venue.maker_fee_pct / 100
    taker_rate = venue.taker_fee_pct / 100

    if venue.max_leverage_by_symbol:
        lev_cap = venue.max_leverage_by_symbol.get(symbol[:3].upper(), venue.max_leverage)
    else:
        lev_cap = venue.max_leverage

    fund_interval_s = int(venue.funding.interval_hours * 3600) if venue.funding else 0

    if len(signals) != len(df):
        raise ValueError(f"signals length ({len(signals)}) != df length ({len(df)})")

    for i in range(len(df)):
        bar = df.iloc[i]
        bar_time = df.index[i]
        sig = signals[i]

        if account_blown:
            equity_curve.iloc[i] = equity
            continue

        bar_tday = trading_day_for_venue(bar_time, venue.day_reset_utc)

        if current_day is None or bar_tday != current_day:
            if dd_model in ("trailing_tick", "daily_snapshot"):
                daily_start_equity[bar_tday] = equity
            if dd_model == "trailing_tick":
                intraday_peak[bar_tday] = equity
            current_day = bar_tday

        if in_position:
            pos = position
            entry_price = pos["entry_price"]
            pos_size = pos["size"]
            entry_comm = pos["commission"]
            direction = pos["direction"]

            if direction == "long":
                pos["peak_price"] = max(pos["peak_price"], bar["high"])
                worst_price = bar["low"]
                peak_pnl = pos_size * (bar["high"] - entry_price) - entry_comm
                worst_pnl = pos_size * (worst_price - entry_price) - entry_comm
            else:
                pos["peak_price"] = min(pos["peak_price"], bar["low"])
                worst_price = bar["high"]
                peak_pnl = pos_size * (entry_price - bar["low"]) - entry_comm
                worst_pnl = pos_size * (entry_price - worst_price) - entry_comm

            pos["floating_dd"] = min(pos.get("floating_dd", 0.0), worst_pnl)

            if dd_model == "trailing_tick":
                peak_eq = equity + peak_pnl
                if peak_eq > intraday_peak.get(bar_tday, equity):
                    intraday_peak[bar_tday] = peak_eq

            worst_eq = equity + worst_pnl

            float_dd = venue.initial_capital - worst_eq
            if float_dd > global_max_floating_dd:
                global_max_floating_dd = float_dd

            dd_blown = False
            dd_blow_reason = ""

            if dd_model == "trailing_tick":
                sod_floor = daily_start_equity.get(bar_tday, equity) * (1 - venue.daily_dd_pct / 100)
                peak = intraday_peak.get(bar_tday, equity)
                trailing_floor = max(sod_floor, peak * (1 - venue.daily_dd_pct / 100))

                if venue.max_loss_pct > 0 and worst_eq <= max_dd_floor:
                    dd_blown = True
                    dd_blow_reason = f"Max loss: ${worst_eq:.2f} <= ${max_dd_floor:.2f}"
                elif worst_eq <= trailing_floor:
                    dd_blown = True
                    dd_blow_reason = (f"Daily DD: ${worst_eq:.2f} <= ${trailing_floor:.2f} "
                                      f"(peak ${peak:.0f})")

            elif dd_model == "daily_snapshot":
                day_start = daily_start_equity.get(bar_tday, equity)
                daily_floor = day_start * (1 - venue.daily_dd_pct / 100)

                if venue.max_loss_pct > 0 and worst_eq <= max_dd_floor:
                    dd_blown = True
                    dd_blow_reason = f"Max loss: ${worst_eq:.2f} <= ${max_dd_floor:.2f}"
                elif worst_eq <= daily_floor:
                    dd_blown = True
                    dd_blow_reason = (f"Daily DD (snapshot): ${worst_eq:.2f} <= ${daily_floor:.2f} "
                                      f"(start ${day_start:.0f})")

            elif dd_model == "none_self_funded":
                if worst_eq <= 0:
                    dd_blown = True
                    dd_blow_reason = f"Margin liquidation: ${worst_eq:.2f} <= $0"

            if dd_blown:
                account_blown = True
                blow_reason = dd_blow_reason
                exit_price = worst_price
                exit_slip_pct = get_slippage_pct(symbol, "stop")
                if direction == "long":
                    exit_slip = exit_price * (1 - exit_slip_pct)
                else:
                    exit_slip = exit_price * (1 + exit_slip_pct)
                exit_comm = pos_size * exit_slip * taker_rate
                if direction == "long":
                    trade_pnl = pos_size * (exit_slip - entry_price)
                else:
                    trade_pnl = pos_size * (entry_price - exit_slip)
                net_pnl = trade_pnl - entry_comm - exit_comm
                equity += net_pnl
                equity = round(equity, 2)
                trades.append(ExecutedTrade(
                    trade_id=trade_id, direction=direction,
                    entry_time=pos["entry_time"], entry_price=entry_price,
                    exit_time=bar_time, exit_price=round(exit_slip, 2),
                    exit_reason="drawdown_breach", position_size=pos_size,
                    pnl=round(net_pnl, 2), commission=round(entry_comm + exit_comm, 2),
                    worst_floating_dd=round(pos.get("floating_dd", 0.0), 2),
                ))
                in_position = False
                position = None
                equity_curve.iloc[i] = equity
                continue

            if venue.funding and fund_interval_s > 0 and "funding_last_epoch" in pos:
                utc_ts = bar_time.tz_convert("UTC").timestamp()
                current_epoch = int(utc_ts // fund_interval_s)
                last_epoch = pos["funding_last_epoch"]

                if current_epoch > last_epoch:
                    epochs_crossed = current_epoch - last_epoch
                    notional = pos_size * bar["close"]
                    funding_payment = notional * (venue.funding.rate_pct / 100) * epochs_crossed
                    if direction == "long":
                        equity -= funding_payment
                        equity = round(equity, 2)
                        total_funding -= funding_payment
                    else:
                        equity += funding_payment
                        equity = round(equity, 2)
                        total_funding += funding_payment
                    pos["funding_last_epoch"] = current_epoch

            should_exit = False
            exit_price = None
            exit_reason = ""
            exit_fee_type = "taker"

            if sig.action == "exit":
                should_exit = True
                exit_reason = sig.exit_reason or "signal_exit"
                exit_price = sig.entry_price or bar["close"]
                exit_fee_type = "taker"

            # SL before TP (conservative when both hit the same bar).
            if not should_exit:
                sl = pos.get("stop_loss")
                if sl is not None:
                    if direction == "long":
                        if bar["low"] <= sl:
                            should_exit = True
                            exit_reason = "sl"
                            exit_price = sl
                            exit_fee_type = "taker"
                    else:
                        if bar["high"] >= sl:
                            should_exit = True
                            exit_reason = "sl"
                            exit_price = sl
                            exit_fee_type = "taker"

            if not should_exit:
                tp = pos.get("take_profit")
                if tp is not None:
                    if direction == "long":
                        if bar["high"] >= tp:
                            should_exit = True
                            exit_reason = "tp"
                            exit_price = tp
                            exit_fee_type = "maker"
                    else:
                        if bar["low"] <= tp:
                            should_exit = True
                            exit_reason = "tp"
                            exit_price = tp
                            exit_fee_type = "maker"

            if not should_exit and force_close_session_end:
                if bar_time.time() >= pd.Timestamp(f"{session_end_hour}:00").time():
                    should_exit = True
                    exit_reason = "session_close"
                    exit_price = bar["close"]
                    exit_fee_type = "taker"

            if should_exit and exit_price is not None:
                slip_type = "stop" if exit_fee_type == "taker" else "market"
                exit_slip_pct = get_slippage_pct(symbol, slip_type)
                if direction == "long":
                    exit_slip = exit_price * (1 - exit_slip_pct)
                else:
                    exit_slip = exit_price * (1 + exit_slip_pct)

                exit_fee_rate = maker_rate if exit_fee_type == "maker" else taker_rate
                exit_comm = pos_size * exit_slip * exit_fee_rate

                if direction == "long":
                    trade_pnl = pos_size * (exit_slip - entry_price)
                else:
                    trade_pnl = pos_size * (entry_price - exit_slip)
                net_pnl = trade_pnl - entry_comm - exit_comm
                equity += net_pnl
                equity = round(equity, 2)
                trades.append(ExecutedTrade(
                    trade_id=trade_id, direction=direction,
                    entry_time=pos["entry_time"], entry_price=entry_price,
                    exit_time=bar_time, exit_price=round(exit_slip, 2),
                    exit_reason=exit_reason, position_size=pos_size,
                    pnl=round(net_pnl, 2), commission=round(entry_comm + exit_comm, 2),
                    worst_floating_dd=round(pos.get("floating_dd", 0.0), 2),
                ))
                in_position = False
                position = None

        if in_position and not account_blown and sig.action in ("entry_long", "entry_short"):
            pos = position
            exit_price = bar["close"]
            exit_slip_pct = get_slippage_pct(symbol, "stop")
            if pos["direction"] == "long":
                exit_slip = exit_price * (1 - exit_slip_pct)
            else:
                exit_slip = exit_price * (1 + exit_slip_pct)
            exit_comm = pos["size"] * exit_slip * taker_rate
            if pos["direction"] == "long":
                trade_pnl = pos["size"] * (exit_slip - pos["entry_price"])
            else:
                trade_pnl = pos["size"] * (pos["entry_price"] - exit_slip)
            net_pnl = trade_pnl - pos["commission"] - exit_comm
            equity += net_pnl
            equity = round(equity, 2)
            trades.append(ExecutedTrade(
                trade_id=trade_id, direction=pos["direction"],
                entry_time=pos["entry_time"], entry_price=pos["entry_price"],
                exit_time=bar_time, exit_price=round(exit_slip, 2),
                exit_reason="force_close_reentry", position_size=pos["size"],
                pnl=round(net_pnl, 2), commission=round(pos["commission"] + exit_comm, 2),
                worst_floating_dd=round(pos.get("floating_dd", 0.0), 2),
            ))
            in_position = False
            position = None

        if not in_position and not account_blown:
            if sig.action in ("entry_long", "entry_short"):
                direction = "long" if sig.action == "entry_long" else "short"
                entry_price = sig.entry_price or bar["close"]
                sl = sig.stop_loss
                tp = sig.take_profit
                entry_order = getattr(sig, "entry_order_type", "market")

                if entry_price is None or sl is None:
                    equity_curve.iloc[i] = equity
                    continue

                entry_fee_type = "maker" if entry_order == "limit" else "taker"
                entry_fee_rate = maker_rate if entry_fee_type == "maker" else taker_rate

                slip_type = "stop" if entry_fee_type == "taker" else "market"
                entry_slip_pct = get_slippage_pct(symbol, slip_type)
                if direction == "long":
                    entry_slip = entry_price * (1 + entry_slip_pct)
                else:
                    entry_slip = entry_price * (1 - entry_slip_pct)

                stop_dist = abs(entry_slip - sl)
                if stop_dist <= 0:
                    equity_curve.iloc[i] = equity
                    continue

                pos_size = risk_per_trade / stop_dist
                notional = pos_size * entry_slip

                leverage = notional / max(equity, 1.0)
                if leverage > lev_cap:
                    equity_curve.iloc[i] = equity
                    continue

                entry_comm = notional * entry_fee_rate

                trade_id += 1

                funding_last_epoch = None
                if venue.funding and fund_interval_s > 0:
                    utc_ts = bar_time.tz_convert("UTC").timestamp()
                    funding_last_epoch = int(utc_ts // fund_interval_s)

                position = {
                    "direction": direction,
                    "entry_price": entry_slip,
                    "size": pos_size,
                    "commission": entry_comm,
                    "peak_price": entry_slip,
                    "take_profit": tp,
                    "stop_loss": sl,
                    "entry_time": bar_time,
                    "entry_fee_type": entry_fee_type,
                    "funding_last_epoch": funding_last_epoch,
                    "floating_dd": 0.0,
                }
                in_position = True

        equity_curve.iloc[i] = equity

    if in_position and position and not account_blown:
        pos = position
        exit_price = df.iloc[-1]["close"]
        exit_slip_pct = get_slippage_pct(symbol, "stop")
        if pos["direction"] == "long":
            exit_slip = exit_price * (1 - exit_slip_pct)
        else:
            exit_slip = exit_price * (1 + exit_slip_pct)
        exit_comm = pos["size"] * exit_slip * taker_rate
        if pos["direction"] == "long":
            trade_pnl = pos["size"] * (exit_slip - pos["entry_price"])
        else:
            trade_pnl = pos["size"] * (pos["entry_price"] - exit_slip)
        net_pnl = trade_pnl - pos["commission"] - exit_comm
        equity += net_pnl
        equity = round(equity, 2)
        trades.append(ExecutedTrade(
            trade_id=trade_id, direction=pos["direction"],
            entry_time=pos["entry_time"], entry_price=pos["entry_price"],
            exit_time=df.index[-1], exit_price=round(exit_slip, 2),
            exit_reason="end_of_data", position_size=pos["size"],
            pnl=round(net_pnl, 2), commission=round(pos["commission"] + exit_comm, 2),
            worst_floating_dd=round(pos.get("floating_dd", 0.0), 2),
        ))

    stats = _compute_stats(trades, equity_curve, account_blown, blow_reason,
                          venue.initial_capital, venue.day_reset_utc,
                          global_max_floating_dd)

    return BacktestResult(
        trades=trades,
        equity_curve=equity_curve,
        account_blown=account_blown,
        blow_reason=blow_reason,
        stats=stats,
        total_funding=round(total_funding, 2),
    )


def _compute_stats(trades, equity_curve, blown, reason, initial_capital,
                   day_reset_utc="00:00", max_floating_dd=0.0):
    if not trades:
        return {"total_trades": 0, "total_pnl": 0, "win_rate": 0, "profit_factor": 0,
                "max_drawdown": 0, "max_drawdown_pct": 0, "max_floating_dd": 0,
                "max_floating_dd_pct": 0, "days_traded": 0}

    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl <= 0]

    total_pnl = sum(t.pnl for t in trades)
    gross_profit = sum(t.pnl for t in wins) if wins else 0
    gross_loss = abs(sum(t.pnl for t in losses)) if losses else 0

    final_equity = equity_curve.iloc[-1]
    peak = equity_curve.max()
    max_dd = peak - equity_curve.min()

    days = set()
    for t in trades:
        days.add(trading_day_for_venue(t.entry_time, day_reset_utc))
    days_traded = len(days)

    return {
        "total_trades": len(trades),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate": round(len(wins) / len(trades) * 100, 1) if trades else 0,
        "total_pnl": round(total_pnl, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "profit_factor": round(gross_profit / max(gross_loss, 0.01), 2),
        "avg_win": round(gross_profit / max(len(wins), 1), 2),
        "avg_loss": round(gross_loss / max(len(losses), 1), 2),
        "max_drawdown": round(max_dd, 2),
        "max_drawdown_pct": round(max_dd / initial_capital * 100, 2),
        "max_floating_dd": round(max_floating_dd, 2),
        "max_floating_dd_pct": round(max_floating_dd / initial_capital * 100, 2),
        "final_equity": round(final_equity, 2),
        "account_blown": blown,
        "blow_reason": reason,
        "days_traded": days_traded,
    }
