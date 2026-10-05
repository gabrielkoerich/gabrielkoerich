+++
title = "Running a quant book on Hyperliquid"
date = 2026-10-05
[taxonomies]
tags = ["quant", "trading", "hyperliquid", "python"]
+++

For the last few months I have been running a small systematic trading book on Hyperliquid. It is a handful of strategies, each one on its own subaccount, managed by one daemon on my Mac. It trades crypto perps and, through HIP-3, stock and commodity perps like the S&P 500, gold and oil.

This post covers how it is built, what the backtests said, what live trading said instead, and the bugs that cost me the most. Most of what I learned is not about finance.

## Why Hyperliquid

Three reasons.

**It has an API that does not fight you.** Orders, positions, fills and funding are one HTTP call away, and an agent wallet can sign orders without holding the master key.

**Subaccounts are free.** Each strategy gets its own account, its own margin and its own P&L. When something goes wrong, the damage stays in one box, and I can read a strategy's equity straight from the exchange instead of reconstructing it.

**HIP-3 puts stocks and commodities on the same rails.** The `xyz` dex lists `xyz:SP500`, `xyz:GOLD`, `xyz:CL` and single stocks next to BTC, on the same API and the same collateral.

That last one is also where most of my bugs came from, so I will come back to it.

## The design

A strategy is a **sleeve**. A sleeve is a Python process running a Nautilus Trader node, pinned to one subaccount. Its capital is whatever equity that subaccount holds.

The sleeves that matter today:

| Sleeve | What it does |
|---|---|
| tsmom | Time-series momentum. Long or short each coin by the sign of its 30-day return, on 8h bars, vol targeted |
| xsmomentum | Cross-sectional momentum. Long the top 5, short the bottom 5 of a dynamic panel, rebalanced weekly |
| xsmom-xyz | The same engine on HIP-3 stocks |
| carry | Long spot, short perp, only when funding runs hot for a week |
| qmj | Quality minus junk. Long majors, short speculative coins, beta neutral |
| smc | Market structure breaks on 1h, gated by the 4h trend |
| dca | Weekly BTC buys, plus a leveraged lump when the bull regime confirms |
| hedger | Trades one BTC position to pull the whole book's beta toward a target set by the market regime |

One daemon sits above them. It starts sleeves as detached processes, so restarting the daemon does not restart the sleeves: they keep trading, and the new daemon adopts them back through pid files. It writes a snapshot of every sleeve every 30 seconds to SQLite, and it pushes a live view to a small SolidJS dashboard over server-sent events.

Everything that acts on live money runs inside that daemon: the killswitches, the sleeve monitor, the daily resolvers that pick which coins each momentum sleeve trades. I run a lot of scheduled agent jobs for this project, and I deliberately kept trading out of them. A job runs in a fresh worktree that can be a few commits behind. A sleeve should never trade on code that is not the code I deployed.

The signing key comes from [passbox](@/posts/2026-09-29-a-password-manager-for-agents.md), behind a fingerprint and a grant scoped to the two entries the daemon needs. The credentials module also refuses to trade if the address it resolves is my master account.

## Backtesting

Every backtest goes through one runner. It uses Nautilus with Hyperliquid's retail fees (4.5bp taker, 1.5bp maker) plus 1bp slippage, on a gap-free lake of 1-minute perp candles for BTC, ETH and SOL from 2021. Every run writes a JSON result that a `/backtests` page indexes, so any strategy can be ranked against any other.

I made this a hard rule after the alternative piled up. A one-off polars script that prints a Sharpe ratio feels faster on the night you write it. Two weeks later nobody can compare it to anything, nobody remembers which fees it assumed, and the strategy ships live with numbers that only exist in a terminal scrollback.

Parameter search runs through sweep profiles: a base config pinned to what runs live and a grid of what to vary. Each cell gets a hash, so a re-run overwrites instead of duplicating.

The most important piece came last: an anchored walk-forward. Fit on 12 months, test on the next 6, step forward 6, repeat. Rank by the mean out-of-sample Sharpe and kill anything whose worst out-of-sample drawdown is too deep.

I built it because of one strategy. Crypto carry, from a 2023 paper that reported a Sharpe of 6.45. My 2024 in-sample run showed Sharpe 2.45 and +36.7%. Over the full three years it returned −40% with a −53% drawdown, and the walk-forward mean out-of-sample Sharpe was −2.61. A single good year had carried the whole result.

Here is what the backtests got wrong more than once:

**One year carries everything.** The SMC edge was almost all 2025. Without it, the BTC 4h mean Sharpe was negative. The three-sleeve combined Sharpe of 3.43 that I was excited about was mostly that year.

**Fees and funding are the strategy.** The first version of the basis carry sleeve lost 60% with a 3% win rate. A round trip cost enough that it needed about six days in the trade to break even, and the exit rule left after about 17 hours. Version two stays in the trade and was positive over 18 months. A funding tilt strategy had a Sharpe of −1.11, all of it fees. Holding BTC perps at 3x for three years loses most of the margin to funding alone.

**Picking by recent performance picks noise.** A TSMOM coin panel that looked like the 2025 winner was the worst over 4.5 years. Choosing panels by trailing strategy Sharpe gave a −90% drawdown. Adding two coins to one panel cut its out-of-sample Sharpe from 2.06 to 0.42.

**The simple combiner wins.** Combining sleeves with inverse volatility beat equal weight, and both beat Markowitz. With a handful of sleeves and a few months of data, the covariance estimate is mostly noise, and an optimiser fits that noise.

## What broke

The backtest tells you whether an idea has an edge. It tells you nothing about whether your system runs the idea. Almost every loss I took that was not market risk came from the second part.

### The prefix

A HIP-3 coin has a different name depending on who you ask. `clearinghouseState` with `dex=xyz` returns `xyz:MSFT`. My position helper returns `MSFT` with a separate `dex` field. Nautilus has its own instrument id. I counted five names for the same perp across the layers.

The stock momentum sleeve had a component that closes positions no longer in the panel. It built `xyz:` + the coin name, received a name that already had the prefix, and asked for `xyz:xyz:MSFT`. That matched nothing in the panel, so every HIP-3 position looked stale, and it closed all nine of them five seconds after every start. For about a month.

Three things hid it:

- The close path stripped one prefix, so the close orders themselves went through fine
- The sleeves had no logging config, so the INFO lines that would have shown it went nowhere
- The unit test passed, because its fixture returned a bare `SP500`

The test checked that the code agreed with the fixture, and the fixture was wrong. The fix was one module that owns HIP-3 naming, and a rule: before you trust a test at an integration boundary, check its fixture against one real response.

Two dexes also means two of every state query. Any call without `dex="xyz"` silently misses HIP-3 positions, orders and stops. The websocket feed I used was main-dex only. My own risk monitor reported zero positions for a sleeve that held fifteen. The SDK needs `perp_dexs=["", "xyz"]` or it raises `KeyError` on any xyz coin, and my risk executor shipped without it.

### The empty panel

The momentum sleeves trade a panel of coins that a resolver picks once a day. One morning Hyperliquid returned a storm of 429s. The resolver caught each error, skipped the coin and moved on. Every coin failed, so it wrote an empty panel, and then marked the day as done.

tsmom read the empty panel as "nothing qualifies" and closed all 13 positions. The "already ran today" guard blocked every retry until UTC midnight.

The fix is in the producer: an all-empty result is suspect. Refuse to write it, keep the last good panel, and alert. A failed run must never satisfy the guard that says the work is done.

### State saved before the side effect

The cross-sectional momentum sleeves stopped rebalancing for 12 days. There were four causes. The worst: an order rejection arrived about 3ms after the sleeve had already saved "rebalanced today", so the next attempt was scheduled seven days out. The hedger had the same shape: it recorded a hedge step when the submit came back with a 429, then waited four hours for the next step.

Both fixes were the same. Advance the state only after the side effect is confirmed.

### Silence

One sleeve froze for eight days without an error. The exchange adapter fetched order status reports in a batch, and one entry with a zero quantity made the whole batch return an empty list. Nothing crashed. The process was alive, and the log file kept being touched.

I added a heartbeat line every five minutes and a watchdog that restarts a sleeve whose heartbeat goes quiet for six hours. On its first day it caught a real ten-hour freeze. I eventually moved the patches for six upstream adapter bugs into one subclass of the Nautilus execution client, so they live in one file with tests instead of as monkey-patches spread across the code.

### Stale data that looks fresh

A resolver read candles from the backtest lake instead of the live API. The lake had stopped updating a month earlier. ETH showed a 30-day return of −30% when the real number was +17%, and the sleeve traded on it.

Now every live path that reads a file checks the timestamp of its last row against the clock and fails loudly when it is too old. Backtest helpers do not get reused in live code without that check.

### Stops

Every position should carry a stop. An audit across 12 subaccounts found 20 positions with a stop and 33 without. One sleeve had piled up 221 orphan stop orders, left behind by positions closed some other way. A trailing stop failed to trail because the code read `trigger` and the field is `triggerPx`, which also skipped the guard that stops a stop from ever being loosened.

The rules now: one stop per position, attached to the position, modified in place by order id, never stacked and never loosened. Most HIP-3 stocks are isolated-only at 10x, so liquidation sits around 9.5% from entry, and a volatility stop that widens to 10% sits past it. That one is still open.

### The config that lied

The cross-sectional momentum sleeve ran at 1.8x gross for a month while three documents said 0.8x. The code had `leg_pct=0.18`, the docs had `0.08`. I found it when I moved sleeve parameters into a YAML file, because the migration has a test that pins the YAML-built config to a snapshot of the old one.

The parameters live in YAML now. The reasoning behind each value lives in a per-sleeve doc, never in a comment next to the value, because a comment does not move when the value does.

## The risk I did not expect: me

I also trade by hand in the Hyperliquid web app, and I had to admit that the riskiest component in the system was me.

So the daemon watches my main account every 10 seconds and computes a tilt score from 0 to 10. It goes up on adding to losers, opening right after a loss, revenge cycles, trading against the regime, and deep drawdown. At 6 it reduces positions; at 8 it closes longs. Most of it still runs in dry-run, and the only live action is tightening stops.

At 10, a small browser extension redirects the Hyperliquid web app to a lock page. It fails closed: if it cannot reach the daemon, an active lock stays on.

## What it costs

**It runs on a laptop.** When the lid closes, the killswitches stop. A Docker setup with a health check and restart policy works end to end, and I have not cut over yet. A dead sleeve once stayed dead for almost three hours because nothing restarted it.

**The guardrails are not all on.** I put the P&L killswitches on hold in late August, and they are still off. Until I turn them back on, a drawdown halts nothing.

**Docs drift.** I keep a long learnings file, and the agents that work on this code read it. Parts of it describe files that no longer exist. The doc I wrote about how backtest results are named describes a filename scheme no file on disk uses. A wrong doc is worse than no doc, because an agent will trust it.

**Small samples.** The live P&L of each sleeve is weeks or months of data. It shows that the system runs, and says very little about whether the edge is real.

## What comes next

**Off the Mac.** Today the whole thing runs on the machine I also work on. The first step is to cut over to the Docker setup, so a crashed daemon comes back without me. The image is also what lets it run anywhere else, which is the real goal.

There are two places it could go. One is a small server at home, which I am already planning for the rest of my agent jobs. The other is a rented box in a datacenter. Home costs nothing per month, but a power cut or an ISP outage at home means positions without a daemon watching them, and for this workload that is a money risk. A datacenter box buys uptime that my house cannot. I have not decided, and the first week on either will run with the Mac as a standby.

**The key on a server.** Neither box has a fingerprint sensor. passbox can already ask my Mac to approve over Tailscale, but then the trading box depends on my Mac being awake, and that is the dependency I am trying to remove. I have not decided how this works yet.

**One connection.** Most of the 429 storms came from many sleeves and the daemon each polling REST for the same state. One shared websocket client, read by everyone, removes most of that traffic.

**Research that is not live yet.** A z-score gate for TSMOM, which skips weak signals, took its 4.5-year Sharpe from 0.32 to about 1.0 in the backtest. It is not in the live config. A walk-forward that refits parameters in each window is also not built. And the killswitches need to come back on, with thresholds that match what each strategy does on a normal bad week.

**Open sourcing it.** I am thinking about it. Most of the hard parts have nothing to do with which strategy you run: an execution client that fixes six Nautilus bugs on Hyperliquid, one module for HIP-3 names, the sweep and walk-forward harness, the tilt monitor and the browser lock. Getting it there means cleaning out a lot of code that only makes sense on my machine.

If you run Nautilus on Hyperliquid, or would use any of those parts, tell me. That will decide what I publish first.
