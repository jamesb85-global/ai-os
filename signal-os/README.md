# Signal OS

A **backtesting harness** for investment strategies — short-term mechanical, longer-horizon, DCA, session structure. You plug a strategy in. The engine handles fills, fees, and sizing. `validate.py` grades whether the run is trustworthy.

`VALIDATED` means the run isn't a known class of fake and came out slightly green. It isn't an edge.

## How it works

**Strategies emit signals only.** Entry, exit, stop, target. Data available at bar close. No PnL, fees, or drawdown in the strategy.

**One execution engine** takes those signals and does fills, slippage, commission, sizing, funding, equity, optional desk-level drawdown. Same strategy, multiple venue profiles — GROSS (zero friction) versus a generic exchange — so you can see what survives cost.

**`validate.py` is the judge.** Lookahead, accounting, cost bands, sample size, walk-forward, profit-factor tripwire, expectancy after fees. A planted-bug self-test has to fail a strategy that peeks at the future and pass a clean control.

## What it's shaped for

The harness is the product. Adapters point it at a market. It's built to take the shape of the strategy: decentralized venues, longer-horizon work, tokenized ETFs and tokenized stocks as asset-class profiles. Not every adapter is live in this snapshot. Named shops stay out. You can load your own bars. This folder grades; it doesn't fetch a live book.

There's a blank template and a session-structure example — prior New York range as a box.

## Run it

```bash
pip install -r requirements.txt

python validate.py --self-test
python validate.py --strategy strategies._template.strategy
```

Synthetic bars in this snapshot. How the gates think: [the harness](VALIDATION.md).
