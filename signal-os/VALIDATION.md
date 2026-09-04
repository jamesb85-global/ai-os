# The harness

A backtest is a simulation with a conflict of interest. The author wants it to work. The harness exists to make that expensive.

Old setups hid a different bug in every notebook: zero-PnL exits, higher-timeframe lookahead, fees that never hit equity. Signal OS centralizes the physics. Strategies talk. One engine settles. Gates grade.

## Architecture

**Signal contract.** `engine/strategy_base.py` — per bar, using only information that existed at close. If tomorrow's close changes yesterday's signal, that's a leak. The lookahead gate exists for that.

**Canonical engine.** `engine/executor.py` — fills, slippage, commission, leverage caps, funding, equity curve, drawdown models. Partial exits and session flatten are engine problems, not strategy problems.

**Venue as config.** `engine/venues.py` — maker/taker, funding interval, capital, daily-risk rules. Default run is GROSS plus a generic Exchange. A DailyRisk profile is an example of a desk constraint, not a named firm. Same signals, different physics.

**Gate battery.** `validate.py` — integrity always. Venue-specific gates (minimum trading days, drawdown survival) only when that profile asks.

## What the gates are for

**Lookahead.** Recompute on a prefix, then on that prefix plus future bars. Any change is FAIL. A planted `shift(-n)` bug must fail; a correctly lagged higher-timeframe feature must pass.

**Accounting.** Every exit has a PnL. Trade PnL plus funding has to match the equity delta. If the story and the ledger disagree, the backtest is theater.

**Costs.** Commission should land in a band implied by maker/taker. Slippage is a conservative model, not a promise of fill quality. Funding in this snapshot is a flat placeholder — longs pay, shorts receive — not historical rates. Don't deploy on that fiction.

**Statistics.** Under 30 trades is FAIL; under 50 is a warning. Walk-forward splits the trade list in time: in-sample up and out-of-sample down is FAIL. Profit factor above 3 warns; above 5 fails. Those tripwires exist because "too good" is usually a bug.

**Drawdown.** If the venue's model blows the account, FAIL. GROSS and Exchange are margin-liquidation only.

**Expectancy.** Net PnL ≤ 0 or PF ≤ 1 after that venue's costs is FAIL. A coin-flip that landed heads can pass. That's "not a net loser," not "has an edge."

## Verdict

`VALIDATED` · `FAILED` · warnings.

Validated means: not a known lie, slightly positive after costs. Multi-asset replication is a later check. Reports land in `data/validation/` (gitignored).

`python validate.py --self-test` is the acceptance test for the harness itself. If that fails, don't trust anything else in the folder.
