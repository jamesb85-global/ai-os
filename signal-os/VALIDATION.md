# Validation harness

Strategies emit signals only. One engine does fills, fees, and drawdown. Gates grade the result.

## Architecture

- **Strategies emit signals only** (`engine/strategy_base.py`) — per bar: entry/exit + stop/target, using only data available at decision time. No PnL, fees, or drawdown logic.
- **One engine** (`engine/executor.py`) does fills, slippage, commission, sizing, equity, and optional venue drawdown.
- **Venue profiles** (`engine/venues.py`) are config: fees, funding, capital, drawdown model. Default run is **GROSS** (zero friction) + **Exchange** (generic perp). A generic daily-risk profile is an optional example of a desk rule, not a named shop.
- **Gates** (`validate.py`) grade the result. Trust gates always run. Trading-day minimum and drawdown survival only fire when that venue asks for them.

## Gate battery

### A. Lookahead

Repaint test: recompute signals on a prefix vs the same prefix plus future bars. Any change = FAIL. Planted-bug self-test must FAIL the leak and PASS the clean control.

### B. Accounting

Every exit has a real PnL. `sum(trade PnL) + funding ≈ equity change`.

### C. Costs

Commission lands in a band implied by the venue's maker/taker rates. Slippage is modeled per asset class.

### D. Statistics

- Sample size: FAIL under 30 trades; WARN under 50.
- Trading days: FAIL only if `venue.min_trading_days > 0` and days are below that.
- Walk-forward: 50/50 time split; FAIL if IS is up and OOS is down.
- PF tripwire: WARN if PF > 3, FAIL if PF > 5.

### E. Drawdown

FAIL if the venue's drawdown model blows the account. GROSS / Exchange use `none_self_funded` (margin liquidation only).

### F. Expectancy

FAIL if net PnL ≤ 0 or PF ≤ 1 after that venue's costs. A coin-flip-heads result can pass this — it means "not a net loser," not "has an edge."

## Verdict

`VALIDATED` · `FAILED` · `INSUFFICIENT` / warnings.

`VALIDATED` means the backtest is not a known class of fake and came out slightly positive. Multi-asset replication is a later check, not this battery.

Reports go to `data/validation/` (gitignored).

## Acceptance for the harness

`python validate.py --self-test` — planted lookahead FAIL, clean HTF PASS.
