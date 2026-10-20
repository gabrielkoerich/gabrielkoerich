+++
title = "Half a websocket"
description = "I planned a shared Hyperliquid websocket and found I had built half of it in June. What moved off REST, what still polls, and where the 429s come from."
date = 2026-10-19
[taxonomies]
tags = ["distributed-systems", "quant", "python", "hyperliquid", "websockets", "solana", "perps"]
+++

At the end of [Running a quant book on Hyperliquid](@/posts/2026-10-05-running-a-quant-book-on-hyperliquid.md) I listed "one connection" as future work: most of the 429 storms came from many processes each polling REST for the same account state, and one shared websocket, read by everyone, would remove most of that traffic. I sat down to plan it and found I had already built half of it, in June. The daemon has kept a websocket per account and an in-memory snapshot since then. The sleeves, where most of the 429s come from, have never read it.

Past me did half the work in June and told nobody, not even to me.

## Ten processes, one budget

Each sleeve is a Python process running a Nautilus Trader node, pinned to one subaccount. One daemon starts them as detached processes, serves a dashboard and runs the risk monitor. The earlier post has the full layout.

Almost everything in that system wants the same few facts about an account: equity, positions, margin, open orders, recent fills. The dashboard wants them for every sleeve card, the risk monitor every 10 seconds, and each sleeve to size orders and check its stops. The info client's docstring still describes where I started:

```python
"""Thin HL Info API client with per-call TTL caching.

The dashboard polls these endpoints from every sleeve card every few seconds.
HL responds in ~150-300ms; without caching we'd burn 1-2 seconds per page load
on duplicate work. A 5-second TTL is short enough that the UI feels live and
long enough that a fast refresh-all is cheap.
"""
```

The budget is per IP. Hyperliquid's [rate limits page](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/rate-limits-and-user-limits) gives all REST requests an aggregated weight of 1200 per minute per IP. `clearinghouseState`, `spotClearinghouseState` and `allMids` weigh 2, most other info requests weigh 20, and every process on my Mac draws from the same 1200.

The cache is per process. The 5 second TTL lives in a module level dict. The daemon has one, each sleeve has one, and so does each executor that runs as its own process. Ten processes asking about the same subaccount within five seconds make ten requests.

When the budget runs out, every process gets a 429 at once, retries at once, and runs out again. On 30 June that happened when the daemon rewrote the universe file and every sleeve restarted in the same second.

## What I tried around it

The websocket shipped on 5 June. These fixes came after, because it never reached the sleeves.

On 15 June the risk monitor started reading spot balances on every 10 second tick, and the fleet went over budget. The fix added a `ttl` argument to the spot helpers, 30 seconds for the monitor, and 15 seconds on its open orders call. The commit says that roughly halved the per coin REST traffic.

On 30 June `_post` went from 3 retries to 5, with exponential backoff and up to half a second of random jitter, about 18 seconds of total wait. Without the jitter, sleeves that restart in the same second retry in lock step and hit the limit again together.

In late July each process got one `requests.Session` instead of a new TCP and TLS handshake per call. Calls got cheaper, and each one still counted against the same 1200.

## A snapshot in the daemon

The daemon subscribes once per account and keeps the latest message in memory. Readers in the daemon check memory first and go to REST only when memory is stale or empty.

`HlWsClient` opens a socket for one address and subscribes to `webData2` for the account (clearinghouse state, spot state, open orders, asset contexts), `allMids` for prices and `userFills` for fills. A registry in the daemon starts and stops one client with each running sleeve, plus one for the master account so the risk monitor reads it from the push feed too.

Every message goes into `HlSnapshotStore`, and an account message replaces the whole state under a lock, because a `webData2` message is a full picture of the account:

```python
with self._lock:
    self._states[addr] = AccountState(
        address=addr,
        ts=time.monotonic(),
        clearinghouse=ch,
        spot=sp,
        mids=mids,
        funding_by_coin=funding,
        open_orders=orders,
    )
```

`AccountState` has `perp_summary()` and `open_positions()` methods that return the same dicts as the REST helpers, so callers did not change. Each helper checks the snapshot first:

```python
def _ws_state(address: str) -> Any | None:
    store = _snapshot_store
    if store is None:
        return None
    st = store.get_account_state(address)
    if st is None or not st.fresh(_WS_FRESH_WINDOW_S):
        return None
    return st

def perp_summary(address: str) -> dict[str, float | int]:
    ws = _ws_state(address)
    if ws is not None:
        summary = cast(dict[str, float | int], ws.perp_summary())
    else:
        summary = _summarize_clearinghouse(clearinghouse_state(address))
    # ...
```

The store is a module global that only the daemon sets, at startup. A one-off script that imports the same helpers gets `None` and goes straight to REST. That kept the change small, and it is why the sleeves never benefit.

Staleness is a timestamp. Each state records `time.monotonic()` on arrival, and `fresh()` compares it against a 10 second window. `webData2` pushes far more often than that, so an older state means the socket has gone quiet and the helper falls back to REST on its own.

A disconnect drops the snapshot. The client wraps the SDK's `WebsocketManager` in a loop. When the manager's thread dies or the connection raises, the loop invalidates that address and reconnects with backoff from 1 to 30 seconds:

```python
def _run(self) -> None:
    backoff = self.BACKOFF_INITIAL_S
    while not self._stop.is_set():
        try:
            self._connect_once()
            backoff = self.BACKOFF_INITIAL_S
        except Exception:  # noqa: BLE001
            log.exception("hl_ws: connection error, backing off %.1fs", backoff)
        self._store.invalidate(self._address)
        if self._stop.wait(backoff):
            break
        backoff = min(backoff * 2, self.BACKOFF_MAX_S)
```

Without the `invalidate`, a reader could not tell a reconnecting socket from a live one for up to 10 seconds. With it, the next read goes to REST at once, and the snapshot comes back with the first `webData2` on the new connection.

Fills are a buffer. Over REST, `userFills` got called three to five times per sleeve detail render. The [subscriptions docs](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/websocket/subscriptions) say the first message on a streaming user channel has `isSnapshot: true` and later ones `false`, so the store replaces the buffer on a snapshot and appends otherwise, keeping the 2000 newest:

```python
if is_snapshot:
    st.fills = list(fills)
    st.fills_seeded = True
else:
    st.fills.extend(fills)
    if len(st.fills) > 2000:
        st.fills = st.fills[-2000:]
```

Fills can stay quiet for hours, so the buffer borrows the account's freshness: if `webData2` is fresh, the socket is alive and the buffer should be current. Until October the buffer was almost never used, for a reason further down.

Candles got one socket for every coin, after my first version opened a socket per coin and hit the per IP connection cap at about seven symbols. The dashboard top bar shows each client's last message age, since a dead socket would otherwise only show up as slower pages.

## What still polls

The snapshot lives in the daemon's memory, and only the daemon's code reads it.

| Reader | Process | Account state from |
|---|---|---|
| Dashboard and SSE stream | daemon | websocket snapshot, REST fallback |
| Risk monitor | daemon thread | websocket for main dex positions, REST for spot, open orders and fills |
| Sleeve sizing (`capital_provider`) | each sleeve | REST spot balance |
| Stop and bracket checks | each sleeve | REST `frontendOpenOrders` |
| Nautilus execution reconciliation | each sleeve | the adapter's own REST calls |
| Standalone executors (carry, DCA, QMJ, hedger) | their own processes | REST |
| HIP-3 positions | any | REST, one call per dex |
| Spot balances | any | REST |

A sleeve imports the same `hl_info` module, but nothing calls `set_snapshot_store` in that process, so `_ws_state` returns `None` and every helper goes to REST. The daemon could serve the snapshot over HTTP, the way it already serves portfolio beta to the hedger. I have not built that.

Spot stays on REST on purpose. On the day the websocket shipped, the dashboard showed one sleeve with less USDC than the exchange UI. `webData2` reports spot USDC net of the perp margin hold and perp unrealized P&L. REST `spotClearinghouseState` reports it gross, which is what the exchange shows as spot equity. Spot changes slowly, so it went back to REST everywhere, with a test that locks in the net vs gross relation.

HIP-3 stays on REST too. `webData2` covers the main dex only, so `perp_summary` and `open_positions` still make one `clearinghouseState` call per HIP-3 dex, even in the daemon. The earlier post tells what that blind spot cost.

## Where the 429s come from

I counted every line matching `Too Many Requests` or `Rate limited` in the daemon log and the 17 other logs next to it: 1,690 lines. One failure can print more than one line. Most sleeve lines have no timestamp of their own and the daemon log only goes back to 30 September, so I cannot give a clean before and after for June. To tell which call a line belongs to, I read the lines just before it.

| Source | Lines | What it is |
|---|---|---|
| Sleeves, Nautilus reconciliation, info weight 20 | 970 | Execution reconciliation, almost all order status reports |
| Sleeves, Nautilus reconciliation, info weight 2 | 404 | Execution reconciliation: order status, position status and fill reports |
| Daemon | 141 | Candle and bar fetches for the candle lake and the daily momentum panels |
| Sleeves, my REST helpers | 94 | Position reconcile, bracket queries, off-panel closer, DCA sync |
| Sleeves, exchange weight 1 | 48 | Order actions |
| Sleeves, adapter connect retries | 26 | Exec client startup |
| Other | 7 | Bare tracebacks with no context |

The daemon is quiet on account state. Every rate limit line in the current daemon log comes from fetching candles and bars, and the risk monitor's log has none.

The sleeves are loud, through reconciliation. Almost all of those 1,374 lines follow a failed order status, position status or fill report. That is Nautilus reconciling its view of orders and positions against the exchange: once at startup, and by [default](https://nautilustrader.io/docs/latest/concepts/live/) every two seconds for any order that has been in flight longer than five. Every sleeve runs its own node, so every sleeve does it for the same account.

I subclassed the execution client for the xyz markets, the HIP-3 dex Nautilus did not cover, and its reconciliation was broken for me. Positions only came from the main dex, one malformed order report emptied the whole batch, which once left a sleeve frozen for eight days, and a stop that closed a position did not update the position list. Nautilus may still have these problems. My subclass fixes the first two, and the position fix adds a second query to every position check. Nautilus also only placed free-standing stops, which left orphan stops behind closed positions, so my stops go through the exchange's own SDK as position-attached triggers. That is one more path talking to the API on its own, and none of it reads the snapshot.

So the old line, "one shared websocket client, read by everyone, removes most of that traffic", was half right. Shared reads removed the daemon's share of account state. Most of what is left is Nautilus reconciling inside each sleeve.

## What I found while writing this 

That's one of the reasons I love writing about those things, I'm always learning with something wrong I did when I'm writing and explaining:

### Every account push erased the fills

`put_web_data2` built a new `AccountState` for each message and did not copy the fills buffer across. The next `webData2` after a `userFills` snapshot reset `fills_seeded` to false, and `user_fills` went back to REST. I checked it against the store alone, with no socket: after a fills snapshot the buffer held one fill, and after one `webData2` message it held none. The fills buffer shipped on 16 June and served REST almost all the time until I fixed it in October. The tests fed each channel on its own, so none sent fills and then an account push. The fix copies the buffer into each new state, and its test sends a fills snapshot and then an account push. That test failed before the fix.

### The mids are never read

Every per-account client subscribes to `allMids`, so the daemon receives the same global price stream once per account. `get_mid` in the store has no caller outside the tests. Code that needs a mid calls `hl_info.all_mids()`, a 5 second REST cache, or a REST helper of its own. My June roadmap entry says mid lookups read the snapshot. They do not.

The daemon receives the same price stream once per account and reads it zero times, which is a really dumb thing to forget.

### My connection limit is out of date

A comment in the candle socket says to stay under "HL's 15-connection-per-IP cap". The rate limits page now says 10 connections, 30 new connections per minute and 10 unique users across user-specific subscriptions, per IP. If I read the last one right, the whole book, master included, can stream at most ten accounts from one IP, whoever opens the sockets. I have not counted the live sockets against that.

## What it costs

**Two code paths for every read.** Each helper has a websocket branch and a REST branch, and only one runs at a time. A bug in the branch that is not running stays hidden, which is how the fills bug lasted from June to October. The tests cover both branches with hand-built payloads, which are only as true as my idea of what the exchange sends.

**A second meaning for the same field.** In the spot bug both numbers were right for what they measured. Any field I move from REST to the push feed needs a check against REST first.

**The daemon holds the state.** If the daemon dies, the snapshot dies with it, and the daemon's readers fall back to REST all at once.

**It hides the remaining load.** With the daemon quiet, the dashboard feels fast and the 429s sit in sleeve logs I do not watch. Counting them for this post was the first time I split them by source.

## What comes next

The first step is to serve the snapshot to the sleeves. The hedger already reads from the daemon over HTTP, and the same shape works for equity, positions and orders, with REST as the fallback when the daemon is down. The newer `allDexsClearinghouseState` and `spotState` channels could move HIP-3 positions and spot onto the push feed, after the net vs gross check. The per-account `allMids` subscription can go.

The HIP-3 positions and the order report batch fixes live in my subclass, and every Nautilus upgrade is a chance for them to drift. They belong in Nautilus itself, so I should open a pull request with them instead of carrying them on my side.

None of that touches the largest source of 429s, Nautilus checking order status inside each sleeve. It needs a longer check interval in each node or a way to feed the adapter from shared state, and I have not looked at which one Nautilus allows.  That is the other half of the websocket, and the [rate limits](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/rate-limits-and-user-limits) page says how much room it has to work in.

I also want to make this work in a perp protocol in Solana, but I'm still looking for the better one to go. After getting hit by the Drift hack I didn't touch perps on Solana anymore, gotta go back to test the other platforms.
