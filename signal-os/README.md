# Signal OS

Most backtests are stories. They look like research. They're often a leak.

A strategy "sees" a future bar. Fees are forgotten. Position size is fantasy. In-sample looks like a money printer; out-of-sample dies. The notebook says edge. The account says otherwise.

Signal OS is a **backtesting harness** for investment strategies — short-term mechanical, longer-horizon, DCA, session structure. You plug a strategy in. One engine simulates the world. A gate battery tries to catch the lie.

That's the product: not a magic ticker. An evaluation system. If you can test a strategy honestly, size risk, model cost, and swap the shape when the horizon changes — that's quantitative work you can defend.

## How it works

**Strategies emit signals only.** Entry, exit, stop, target. Data available at bar close. No PnL math in the strategy. No fee logic. No drawdown code. If the candidate is doing the engine's job, the architecture is already wrong.

**One execution engine** takes those signals and does fills, slippage, commission, sizing, funding, equity, optional desk-level drawdown. Same strategy, N venue profiles — GROSS (zero friction) versus a generic exchange — so you can see what "edge" survives contact with cost.

**`validate.py` is the judge.** Lookahead (repaint) test. Accounting identity. Cost bands. Sample size. Walk-forward. Profit-factor tripwire. Expectancy after fees. `VALIDATED` means the run isn't a known class of fake and came out slightly green. It does not mean you found an edge.

A planted-bug self-test has to fail a strategy that peeks at the future and pass a clean control. If the harness can't catch that, it doesn't ship.

## What it's shaped for

The harness is the product. Adapters are how you point it at a market.

It's built to take the shape of the strategy: decentralized venues, longer-horizon work, tokenized ETFs and tokenized stocks as asset-class profiles. Not every adapter is live in this snapshot. Named shops stay out. You can load your own bars. This folder grades; it doesn't fetch a live book.

There's a blank template and a session-structure example — prior New York range as a box — so you can see a candidate that isn't only an EMA cross.

## Run it

```bash
pip install -r requirements.txt

python validate.py --self-test
python validate.py --strategy strategies._template.strategy
```

Synthetic bars in this snapshot. How the gates think: [the harness](VALIDATION.md).

That's Signal OS: an investment-strategy evaluation machine with a real control plane. Cool because it refuses to believe you — until the math checks out.
