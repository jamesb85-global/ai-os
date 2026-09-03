# Signal OS

A market-signal investment machine. Plug in a strategy — short-term mechanical, longer-horizon, DCA — and one engine grades it.

Product inside: a **backtesting harness**. Strategies emit signals only. The engine does fills, fees, sizing, and drawdown. `validate.py` says whether the backtest is trustworthy.

`VALIDATED` means the run is not a known class of fake and came out slightly positive. It is not an edge.

## What it is shaped for

The harness can be shaped to the strategy. Current lean: decentralized venues, longer-horizon work, tokenized ETFs and tokenized stocks as *asset-class adapters*. Not every adapter is live in this snapshot. Named exchanges and prop shops stay out of this folder.

## How to run

```bash
pip install -r requirements.txt

# Prove the harness still catches a planted lookahead bug
python validate.py --self-test

# Grade the template (or copy it and point --strategy at yours)
python validate.py --strategy strategies._template.strategy
```

Self-test uses synthetic bars. No live market fetch in this snapshot.

## Layout

```
signal-os/
├── engine/                      Signal contract, executor, venue profiles
├── validate.py                  Gate battery
├── data_io/                     Synthetic bars (CSV load optional)
├── strategies/_template/        Scaffold
└── strategies/session_structure/  Optional example: session box as a candidate
```

Copy `_template/strategy.py`. Implement `compute_indicators` and `generate_signals`. No PnL or fee math in the strategy.

## Gates

Lookahead self-test, accounting, costs, sample size, walk-forward, profit-factor tripwire, expectancy. Spec: [VALIDATION.md](VALIDATION.md).
