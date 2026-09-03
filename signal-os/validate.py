"""
validate.py — Validation gate battery

Strategies emit signals once; the engine settles them across venue profiles
(default: GROSS + generic Exchange). Trust gates always run. Venue-specific
gates (trading-day minimum, DD survival) only fire when that profile asks for them.

Output: data/validation/<strategy>_venues.md
        data/validation/<strategy>_<venue>_<symbol>.json
"""

import sys, os, json
from datetime import datetime
from dataclasses import dataclass
from typing import List, Optional

import pandas as pd

base = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base)

from data_io.synthetic import synthetic_ohlcv
from engine.strategy_base import StrategyBase, BarSignal
from engine.executor import run as execute, BacktestResult
from engine.venues import (
    VenueProfile, ALL_VENUES, DEFAULT_VENUES,
    venue_by_name, with_capital,
)

OUTPUT_DIR = os.path.join(base, "data", "validation")
os.makedirs(OUTPUT_DIR, exist_ok=True)


@dataclass
class GateResult:
    name: str
    passed: bool
    detail: str
    severity: str = "INFO"  # INFO, WARN, FAIL


@dataclass
class VenueRun:
    venue_name: str
    result: BacktestResult
    gates: List[GateResult]
    verdict: str


def _timeframe_minutes(strategy: StrategyBase) -> int:
    return int(str(strategy.timeframe).replace("min", "").replace("m", "") or "15")


def validate(strategy: StrategyBase,
             symbol: str = "BTCUSDT",
             start: str = "2025-07-01",
             end: str = "2025-09-01",
             risk_per_trade: Optional[float] = None,
             venues: List[VenueProfile] = None,
             capital: Optional[float] = None) -> dict:
    """
    Run the full gate battery across venue profiles.

    Strategy signals computed ONCE; settled N ways.
    Default venues are GROSS + Exchange. This snapshot uses synthetic bars.
    Trust gates (lookahead, accounting, costs) always run.
    """
    if venues is None:
        venues = list(DEFAULT_VENUES)
    if capital is not None:
        venues = [with_capital(v, capital) for v in venues]

    config = strategy.get_config()
    results = {
        "strategy": config,
        "symbol": symbol,
        "period": f"{start} to {end}",
        "timestamp": datetime.now().isoformat(),
        "gates": [],
        "verdict": None,
        "venue_results": [],
    }

    print(f"\n{'='*60}")
    print(f"VALIDATING: {config['name']} on {symbol}")
    print(f"  Venues: {', '.join(v.name for v in venues)}")
    print(f"{'='*60}")

    print("Building synthetic series...")
    tf_minutes = _timeframe_minutes(strategy)
    df = synthetic_ohlcv(symbol, start, end, minutes=tf_minutes)
    if df is None or len(df) == 0:
        results["verdict"] = "ERROR — no data"
        return results

    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")

    print(f"  {len(df)} {strategy.timeframe} candles")

    print("Computing indicators...")
    try:
        df_i = strategy.compute_indicators(df)
    except Exception as e:
        results["gates"].append(GateResult("Indicators", False, str(e), "FAIL").__dict__)
        results["verdict"] = "FAILED — indicator computation error"
        return results

    print("Generating signals...")
    try:
        signals = strategy.generate_signals(df_i)
        if len(signals) != len(df_i):
            results["gates"].append(GateResult(
                "Signals", False,
                f"Signal count {len(signals)} != bar count {len(df_i)}",
                "FAIL"
            ).__dict__)
            results["verdict"] = "FAILED — signal/bar mismatch"
            return results
    except Exception as e:
        results["gates"].append(GateResult("Signals", False, str(e), "FAIL").__dict__)
        results["verdict"] = "FAILED — signal generation error"
        return results

    df_i = df_i.copy()
    if df_i.index.tz is not None:
        df_i.index = df_i.index.tz_convert("America/New_York")
    else:
        df_i.index = df_i.index.tz_localize("UTC").tz_convert("America/New_York")

    print("Gate A: Lookahead check...")
    gate_a = _check_lookahead(df, strategy)
    results["gates"].append(gate_a.__dict__)

    if gate_a.severity == "FAIL" and not gate_a.passed:
        results["verdict"] = "FAILED — lookahead"
        return results

    sch = getattr(strategy, "session_close_hour", None)

    for venue in venues:
        print(f"\n  --- {venue.name} ---")

        result = execute(signals, df_i,
                         venue=venue, symbol=symbol,
                         risk_per_trade=risk_per_trade,
                         force_close_session_end=(sch is not None),
                         session_end_hour=(sch if sch is not None else 0))

        trades = result.trades
        metrics = result.stats
        metrics["total_pnl"] = sum(t.pnl for t in trades)
        metrics["total_funding"] = result.total_funding
        metrics["total_commission"] = round(sum(t.commission for t in trades), 2)

        venue_gates = []
        venue_gates.append(_check_accounting(trades, result, venue.initial_capital))
        venue_gates.append(_check_costs_venue(trades, result, venue))
        venue_gates.extend(_check_statistics(trades, metrics, venue))
        venue_gates.append(_check_dd_survival_venue(result, venue))
        venue_gates.append(_check_expectancy(trades, metrics, venue))

        failures = [g for g in venue_gates if g.severity == "FAIL" and not g.passed]
        warnings = [g for g in venue_gates if g.severity == "WARN" and not g.passed]

        if failures:
            venue_verdict = f"FAILED — {len(failures)} gate(s)"
        elif warnings:
            venue_verdict = f"VALIDATED (with {len(warnings)} warning(s))"
        else:
            venue_verdict = "VALIDATED"

        vr = VenueRun(
            venue_name=venue.name,
            result=result,
            gates=venue_gates,
            verdict=venue_verdict,
        )
        results["venue_results"].append(vr)

        if results.get("verdict") is None and venue.name != "GROSS":
            for g in venue_gates:
                results["gates"].append(g.__dict__)
            results["verdict"] = venue_verdict
            results["metrics"] = metrics

        print(f"    Trades: {metrics.get('total_trades', 0)}  "
              f"WR: {metrics.get('win_rate', 0)}%  "
              f"PF: {metrics.get('profit_factor', 0)}  "
              f"PnL: ${metrics.get('total_pnl', 0):,.0f}  "
              f"Funding: ${result.total_funding:,.0f}  "
              f"DD: ${metrics.get('max_drawdown', 0):,.0f}  "
              f"Blown: {metrics.get('account_blown', False)}")

    if results.get("verdict") is None and results["venue_results"]:
        vr = results["venue_results"][0]
        for g in vr.gates:
            results["gates"].append(g.__dict__)
        results["verdict"] = vr.verdict
        results["metrics"] = vr.result.stats

    name_slug = config["name"].lower().replace(" ", "_")
    _write_venues_report(results, name_slug, symbol)
    for vr in results["venue_results"]:
        _write_venue_json(vr, config, name_slug, symbol, results)
    _write_legacy_json(results, name_slug, symbol)

    print(f"\n{'='*60}")
    print(f"VENUE COMPARISON — {config['name']} on {symbol}")
    print(f"{'='*60}")
    print(f"  {'Venue':<18} {'Verdict':<38} {'PnL':>10} {'PF':>6} {'WR':>6} {'FloatDD':>8} {'Blown':>6}")
    print(f"  {'-'*18} {'-'*38} {'-'*10} {'-'*6} {'-'*6} {'-'*8} {'-'*6}")
    for vr in results["venue_results"]:
        m = vr.result.stats
        print(f"  {vr.venue_name:<18} {vr.verdict:<38} "
              f"${m.get('total_pnl', 0):>9,.0f} {m.get('profit_factor', 0):>5.2f} "
              f"{m.get('win_rate', 0):>5.1f}% ${m.get('max_floating_dd', 0):>7,.0f} "
              f"{str(m.get('account_blown', False)):>6}")

    return results


def _check_lookahead(df: pd.DataFrame, strategy) -> GateResult:
    """Future-data-invariance (repaint) test. Any change = FAIL."""
    n = len(df)
    if n < 100:
        return GateResult("Lookahead", False, "Too few bars for repaint test", "WARN")

    future_window = min(50, n // 10)
    cut_points = [n // 4 + 1, n // 2 + 1, 3 * n // 4 + 1]
    cut_points = [min(c, n - future_window - 1) for c in cut_points]

    failures = []
    for cut in cut_points:
        if cut + future_window >= n:
            continue

        df_short = df.iloc[:cut].copy()
        try:
            df_i_short = strategy.compute_indicators(df_short)
            signals_short = strategy.generate_signals(df_i_short)
        except Exception as e:
            failures.append(f"Cut {cut}: indicator/signal error: {e}")
            continue

        df_long = df.iloc[:cut + future_window].copy()
        try:
            df_i_long = strategy.compute_indicators(df_long)
            signals_long = strategy.generate_signals(df_i_long)
        except Exception:
            continue

        for i in range(min(len(signals_short), len(signals_long), cut)):
            s_short = signals_short[i]
            s_long = signals_long[i]

            if s_short.action != s_long.action:
                failures.append(
                    f"Cut {cut}, bar {i}: action '{s_short.action}' vs '{s_long.action}' "
                    f"— future data changed past signal"
                )
                break
            if s_short.action in ("entry_long", "entry_short"):
                if s_short.entry_price != s_long.entry_price:
                    failures.append(
                        f"Cut {cut}, bar {i}: entry price changed with future data"
                    )
                    break
                if s_short.stop_loss != s_long.stop_loss:
                    failures.append(
                        f"Cut {cut}, bar {i}: stop_loss changed with future data"
                    )
                    break
                if s_short.take_profit != s_long.take_profit:
                    failures.append(
                        f"Cut {cut}, bar {i}: take_profit changed with future data"
                    )
                    break

        if failures:
            break

    if failures:
        return GateResult("Lookahead", False, failures[0], "FAIL")
    return GateResult("Lookahead", True, f"Repaint test passed at {len(cut_points)} cut points")


def _check_accounting(trades, result: BacktestResult, initial_capital: float) -> GateResult:
    issues = []

    no_exit_price = [t for t in trades if t.exit_price is None or t.exit_price == 0]
    zero_pnl = [t for t in trades if t.pnl == 0]

    if no_exit_price:
        issues.append(f"{len(no_exit_price)} trades with missing exit_price")
    if zero_pnl:
        issues.append(f"{len(zero_pnl)} trades with zero PnL")

    if trades:
        pnl_sum = sum(t.pnl for t in trades)
        total_funding = getattr(result, "total_funding", 0.0)
        equity_delta = result.equity_curve.iloc[-1] - initial_capital
        diff = abs(pnl_sum + total_funding - equity_delta)
        if diff > 1.0:
            issues.append(
                f"PnL sum (${pnl_sum:.2f}) + funding (${total_funding:.2f}) "
                f"!= equity delta (${equity_delta:.2f}), diff ${diff:.2f}"
            )

    if issues:
        return GateResult("Accounting", False, "; ".join(issues), "FAIL")
    return GateResult("Accounting", True, f"{len(trades)} trades, all with valid exit data")


def _check_costs_venue(trades, result: BacktestResult, venue) -> GateResult:
    total_notional = sum(t.position_size * (t.entry_price + t.exit_price) for t in trades)
    actual_comm = sum(t.commission for t in trades)

    if total_notional > 0 and actual_comm > 0:
        rate = actual_comm / total_notional
        min_rate = venue.maker_fee_pct / 100 * 0.5
        max_rate = venue.taker_fee_pct / 100 * 2.0
        if rate < min_rate or rate > max_rate:
            return GateResult(
                "Costs", False,
                f"Commission rate {rate:.4%} outside [{min_rate:.4%}, {max_rate:.4%}]",
                "FAIL",
            )

    return GateResult(
        "Costs", True,
        f"{venue.maker_fee_pct:.3f}%/{venue.taker_fee_pct:.3f}% maker/taker, "
        f"${actual_comm:.2f} total commission",
    )


def _check_statistics(trades, metrics, venue: VenueProfile = None) -> List[GateResult]:
    gates = []
    n = len(trades)

    if n < 30:
        gates.append(GateResult("SampleSize", False, f"Only {n} trades (need ≥30)", "FAIL"))
    elif n < 50:
        gates.append(GateResult("SampleSize", False, f"Low sample: {n} trades (need ≥50 for confidence)", "WARN"))
    else:
        gates.append(GateResult("SampleSize", True, f"{n} trades"))

    days = metrics.get("days_traded", 0)
    min_days = getattr(venue, "min_trading_days", 0) or 0
    if min_days > 0 and days < min_days:
        gates.append(GateResult(
            "TradingDays", False,
            f"Only {days} trading days ({venue.name} requires ≥{min_days})",
            "FAIL",
        ))
    else:
        gates.append(GateResult("TradingDays", True, f"{days} trading days"))

    pf = metrics.get("profit_factor", 0)
    if pf > 5:
        gates.append(GateResult("PF Tripwire", False,
            f"PF {pf:.2f} > 5 — extreme, mandatory manual review", "FAIL"))
    elif pf > 3:
        gates.append(GateResult("PF Tripwire", False,
            f"PF {pf:.2f} > 3 — suspicious, manual review recommended", "WARN"))
    elif pf > 0:
        gates.append(GateResult("ProfitFactor", True, f"PF {pf:.2f}"))

    wr = metrics.get("win_rate", 0)
    if wr > 80:
        gates.append(GateResult("WinRate", False,
            f"WR {wr}% > 80% — suspicious, check for accounting or lookahead bugs", "WARN"))

    if n >= 20:
        sorted_trades = sorted(trades, key=lambda t: t.entry_time)
        mid = len(sorted_trades) // 2
        is_pnl = sum(t.pnl for t in sorted_trades[:mid])
        oos_pnl = sum(t.pnl for t in sorted_trades[mid:])

        if is_pnl > 0 and oos_pnl < 0:
            gates.append(GateResult("WalkForward", False,
                f"OOS PnL ${oos_pnl:,.0f} negative (IS ${is_pnl:,.0f}) — overfit or regime change", "FAIL"))
        elif is_pnl > 0 and oos_pnl > is_pnl * 1.5:
            gates.append(GateResult("WalkForward", False,
                f"OOS PnL ${oos_pnl:,.0f} >> IS ${is_pnl:,.0f} — implausibly better, possible leakage", "WARN"))
        else:
            gates.append(GateResult("WalkForward", True,
                f"IS ${is_pnl:,.0f} / OOS ${oos_pnl:,.0f}"))

    return gates


def _check_dd_survival_venue(result: BacktestResult, venue) -> GateResult:
    if result.account_blown:
        return GateResult("DDSurvival", False,
            f"Account blown ({venue.dd_model}): {result.blow_reason}", "FAIL")
    return GateResult("DDSurvival", True,
        f"Survived {venue.name} {venue.dd_model} "
        f"(daily {venue.daily_dd_pct}% DD / {venue.max_loss_pct}% max)")


def _check_expectancy(trades, metrics, venue) -> GateResult:
    total_pnl = metrics.get("total_pnl", 0)
    pf = metrics.get("profit_factor", 0)
    if total_pnl <= 0:
        return GateResult("Expectancy", False,
            f"Net loss ${total_pnl:+,.0f} (PF {pf:.2f}) — loses money after {venue.name} costs", "FAIL")
    if pf <= 1.0:
        return GateResult("Expectancy", False,
            f"PF {pf:.2f} ≤ 1.0 — no edge after {venue.name} costs", "FAIL")
    return GateResult("Expectancy", True,
        f"Net profit ${total_pnl:+,.0f}, PF {pf:.2f} — positive expectancy after {venue.name} costs")


def _write_venues_report(results: dict, name_slug: str, symbol: str):
    cfg = results["strategy"]
    lines = []

    lines.append(f"# Multi-Venue Validation — {cfg['name']}")
    lines.append("")
    lines.append(f"**Symbol:** {symbol}  ")
    lines.append(f"**Period:** {results['period']}  ")
    lines.append(f"**Timeframe:** {cfg['timeframe']}  ")
    lines.append("")

    lookahead_gate = next((g for g in results["gates"] if g.get("name") == "Lookahead"), None)
    if lookahead_gate:
        status = "PASS" if lookahead_gate["passed"] else "FAIL"
        lines.append(f"**Lookahead:** {status} {lookahead_gate['detail']}")
        lines.append("")

    lines.append("## Venue Comparison")
    lines.append("")
    lines.append("| Venue | Verdict | Net PnL | PF | Win% | Funding | Max DD | Max Float DD | Blown | Trades | Days |")
    lines.append("|-------|---------|---------|-----|------|---------|--------|--------------|-------|--------|------|")

    gross_metrics = None
    for vr in results["venue_results"]:
        m = vr.result.stats
        blown = "yes" if m.get("account_blown", False) else "—"
        funding = f"${vr.result.total_funding:,.0f}"
        float_dd = f"${m.get('max_floating_dd', 0):,.0f}"
        lines.append(
            f"| **{vr.venue_name}** | {vr.verdict[:50]} | "
            f"${m.get('total_pnl', 0):,.0f} | "
            f"{m.get('profit_factor', 0):.2f} | "
            f"{m.get('win_rate', 0):.1f}% | "
            f"{funding} | "
            f"${m.get('max_drawdown', 0):,.0f} | "
            f"{float_dd} | "
            f"{blown} | "
            f"{m.get('total_trades', 0)} | "
            f"{m.get('days_traded', 0)} |"
        )
        if vr.venue_name == "GROSS":
            gross_metrics = m

    lines.append("")

    if gross_metrics and len(results["venue_results"]) >= 2:
        lines.append("## Friction Decomposition")
        lines.append("")
        gross_pnl = gross_metrics.get("total_pnl", 0)
        lines.append(f"**GROSS (raw edge):** ${gross_pnl:+,.0f}")
        lines.append("")

        for vr in results["venue_results"]:
            if vr.venue_name == "GROSS":
                continue
            m = vr.result.stats
            lines.append(f"### {vr.venue_name}")
            lines.append(f"- Net PnL: ${m.get('total_pnl', 0):+,.0f}")
            lines.append(f"- Total fees paid: ${m.get('total_commission', 0):,.0f}")
            lines.append(f"- Funding paid: ${vr.result.total_funding:+,.0f}")
            lines.append(f"- Delta from GROSS: ${m.get('total_pnl', 0) - gross_pnl:+,.0f}")
            lines.append("")

    lines.append(f"*Report generated {results['timestamp']}*")
    lines.append("")
    lines.append("Funding rates in this snapshot are flat placeholders (longs pay, shorts receive).")
    lines.append("They are not directionally accurate. Wire historical funding before any deploy decision.")
    lines.append("Slippage is a conservative cost model, not a promise of fill quality.")

    report_path = os.path.join(OUTPUT_DIR, f"{name_slug}_venues.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  Venue report: {report_path}")


def _write_venue_json(vr: VenueRun, config: dict, name_slug: str, symbol: str, results: dict):
    vname = vr.venue_name.lower().replace(" ", "_")
    json_path = os.path.join(OUTPUT_DIR, f"{name_slug}_{vname}_{symbol.lower()}.json")
    m = vr.result.stats
    m["total_commission"] = round(sum(t.commission for t in vr.result.trades), 2)
    m["total_funding"] = vr.result.total_funding

    payload = {
        "strategy": config,
        "symbol": symbol,
        "venue": vr.venue_name,
        "period": results["period"],
        "timestamp": results["timestamp"],
        "verdict": vr.verdict,
        "gates": [g.__dict__ for g in vr.gates],
        "metrics": m,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)


def _write_legacy_json(results: dict, name_slug: str, symbol: str):
    json_path = os.path.join(OUTPUT_DIR, f"{name_slug}_{symbol.lower()}.json")
    payload = {
        "strategy": results["strategy"],
        "symbol": symbol,
        "period": results["period"],
        "timestamp": results["timestamp"],
        "gates": results["gates"],
        "verdict": results.get("verdict", "UNKNOWN"),
        "metrics": results.get("metrics", {}),
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)


class LookaheadBugStrategy(StrategyBase):
    """Deliberately buggy — uses a future close. Must FAIL repaint test."""
    name = "LookaheadBug"
    timeframe = "15min"

    def compute_indicators(self, df):
        df = df.copy()
        df["future_close"] = df["close"].shift(-5)
        return df

    def generate_signals(self, df):
        signals = []
        for i in range(len(df)):
            action = "none"
            fut = df["future_close"].iloc[i]
            close = df["close"].iloc[i]
            if pd.notna(fut) and float(fut) > float(close):
                action = "entry_long"
            signals.append(BarSignal(
                timestamp=df.index[i],
                action=action,
                entry_price=float(close) if action != "none" else None,
                stop_loss=float(close) * 0.99 if action != "none" else None,
                take_profit=float(close) * 1.02 if action != "none" else None,
            ))
        return signals


class CleanHTFStrategy(StrategyBase):
    """Clean control — correctly-shifted HTF resample. Must PASS repaint test."""
    name = "CleanHTF"
    timeframe = "15min"

    def compute_indicators(self, df):
        df = df.copy()
        htf = df["close"].resample("120min").last().shift(1)
        df["htf_ema"] = htf.reindex(df.index, method="ffill")
        df["ema_slow"] = df["close"].ewm(span=50).mean().shift(1)
        return df

    def generate_signals(self, df):
        signals = []
        for i in range(len(df)):
            action = "none"
            if (i > 0 and not pd.isna(df["htf_ema"].iloc[i])
                and not pd.isna(df["ema_slow"].iloc[i])
                and df["htf_ema"].iloc[i] > df["ema_slow"].iloc[i]):
                action = "entry_long"
            signals.append(BarSignal(
                timestamp=df.index[i],
                action=action,
                entry_price=df["close"].iloc[i] if action != "none" else None,
                stop_loss=df["close"].iloc[i] * 0.99 if action != "none" else None,
                take_profit=df["close"].iloc[i] * 1.02 if action != "none" else None,
            ))
        return signals


def self_test() -> bool:
    print("\n" + "=" * 60)
    print("SELF-TEST: Planted-bug detection")
    print("=" * 60)

    bug_result = validate(LookaheadBugStrategy(), start="2025-07-01", end="2025-09-01")
    bug_lookahead = next((g for g in bug_result["gates"] if g.get("name") == "Lookahead"), None)
    bug_caught = bug_lookahead is not None and not bug_lookahead["passed"]

    clean_result = validate(CleanHTFStrategy(), start="2025-07-01", end="2025-09-01")
    clean_lookahead = next((g for g in clean_result["gates"] if g.get("name") == "Lookahead"), None)
    clean_ok = clean_lookahead is not None and clean_lookahead["passed"]

    print(f"\n  Bug strategy lookahead: {'FAILED (correct)' if bug_caught else 'PASSED (BAD!)'}")
    print(f"  Clean strategy lookahead: {'PASSED (correct)' if clean_ok else 'FAILED (BAD!)'}")

    ok = bug_caught and clean_ok
    print(f"\n  SELF-TEST: {'PASS' if ok else 'FAIL'}")
    return ok


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true", help="Run planted-bug self-test")
    parser.add_argument("--strategy", type=str, help="Strategy module path to validate")
    parser.add_argument("--symbol", type=str, default="BTCUSDT")
    parser.add_argument("--start", type=str, default="2025-07-01")
    parser.add_argument("--end", type=str, default="2025-09-01")
    parser.add_argument("--venue", type=str, default=None,
                       help="Venue name (default: GROSS + Exchange). Optional example: DailyRisk")
    parser.add_argument("--risk", type=float, default=None,
                       help="USD risk per trade (default: 1%% of venue capital)")
    parser.add_argument("--capital", type=float, default=None,
                       help="Override initial capital on every venue in the run")
    args = parser.parse_args()

    if args.self_test:
        self_test()
    elif args.strategy:
        import importlib
        mod = importlib.import_module(args.strategy)
        strat = mod.Strategy()

        venues = None
        if args.venue:
            picked = venue_by_name(args.venue)
            if picked is None:
                names = [v.name for v in ALL_VENUES]
                print(f"Unknown venue '{args.venue}'. Options: {names}")
            else:
                venues = [picked]
        if venues is not None or args.venue is None:
            validate(strat, symbol=args.symbol, start=args.start, end=args.end,
                     risk_per_trade=args.risk, venues=venues, capital=args.capital)
    else:
        print("Usage: python validate.py --self-test  OR  --strategy <module.path> [--venue <name>] [--risk N] [--capital N]")
