+++
title = "Waiting and working in Rust"
date = 2026-10-08
[taxonomies]
tags = ["rust", "async", "concurrency", "tokio", "rayon", "performance", "low-latency", "solana"]
+++

Rust gives you at least five ways to do more than one thing: OS threads, an async runtime, a blocking pool inside that runtime, a data parallel pool, and a thread that owns a core and never sleeps. People ask "should I use async?" as if it were one question. It is three.

**Is the program waiting?** Sockets, timers, RPC calls, a database. The CPU is idle and the work is in somebody else's hands. This is concurrency: many things in progress, few of them running.

**Is the program working?** Hashing, parsing, simulating, signing. The CPU is the bottleneck and the answer is more cores. This is parallelism: many things running at the same instant.

**Does the program have to react within a bound?** A market data tick, a packet, an interrupt. Here the number that matters is how late the worst reaction is.

Each tool in Rust answers one of these well and the others badly. I measured the differences on my machine, an M4 Max with 14 cores, so the numbers below are real but they are one machine. Run them on yours.

## How async works in Rust

A Rust `async fn` compiles to a state machine. Each `.await` is a point where the function can stop and save its local variables into that state machine. The future does nothing on its own. An executor calls `poll` on it. The future either finishes, or registers a waker and returns `Pending`. When the socket has data or the timer fires, the waker puts the task back in the executor's queue, and the executor polls it again.

Three properties follow.

**It is cooperative.** The executor cannot interrupt a task. A task gives up the thread only at an `.await` that is not ready. Code between two awaits runs to completion, however long it takes.

**It is cheap.** A task is a heap allocation the size of its state machine, not a thread with a stack. A thread in Rust gets a [2 MiB stack by default](https://doc.rust-lang.org/std/thread/index.html#stack-size).

**Dropping a future cancels it.** It stops at its last await and never resumes. This is how timeouts and `select!` work, and also how you lose half a write if you are not careful.

Tokio's [multi thread runtime](https://docs.rs/tokio/latest/tokio/runtime/index.html) runs one worker per core, each with a local queue. An idle worker steals tasks from a busy one. Tokio's `current_thread` runtime runs everything on one thread, with no stealing. Tasks spawned with `tokio::spawn` still have to be `Send` on either runtime.

## Waiting: one runtime, many tasks

This is what async is for. I spawned 100,000 Tokio tasks that each sleep for 100 ms. All of them finished in 131 ms. One hundred thousand OS threads would reserve 200 GB of virtual stack, and the scheduler would spend its time switching between them.

Spawning is also cheaper. A thread spawn and join cost 17 to 20 µs here. A Tokio spawn and await cost about 8 µs. I did not break that number down, but each spawn in this test hands the task to a worker thread and wakes the caller back up.

[orch](@/posts/2026-07-05-orchestrating-agents-for-humans.md), the service that runs my coding agents, is this shape. One process runs the tick loop, GitHub polling, tmux output capture every two seconds, a Discord websocket and a Telegram bot. Almost all of it is waiting, so it all lives on one Tokio runtime.

Cloudflare made the same choice at a much larger scale. [Their Rust proxy, Pingora](https://blog.cloudflare.com/how-we-built-pingora-the-proxy-that-connects-cloudflare-to-the-internet/), uses threads with work stealing instead of NGINX's processes, so that every request can share one connection pool. Connection reuse for one large customer went from 87.1% to 99.92%, and the service used about 70% less CPU and 67% less memory.

## The rule that breaks it: do not block the runtime

Because async is cooperative, a task that does not await holds its worker thread. Alice Ryhl, one of the Tokio maintainers, [gives the rule of thumb](https://ryhl.io/blog/async-what-is-blocking/): no more than 10 to 100 microseconds between awaits.

I measured what happens when you ignore it. On a `current_thread` runtime, one task waits on a 1 ms timer while another task calls `std::thread::sleep` for 100 ms. The 1 ms timer fired after 101 ms. Every other task on that thread waited the same way. On a multi thread runtime the damage is smaller, until enough tasks block that every worker is stuck.

What counts as blocking is a measure of time, not a list of functions:

- `std::fs` calls, which can wait on a disk
- a synchronous HTTP or database client
- a `std::sync::Mutex` held across an `.await`, or held while another thread does slow work
- CPU work longer than about 100 µs

For blocking IO, Tokio has `spawn_blocking`. It runs the closure on a separate pool of threads, [up to 512 by default](https://docs.rs/tokio/latest/tokio/runtime/struct.Builder.html#method.max_blocking_threads), and gives you a future for the result. [`tokio::fs`](https://docs.rs/tokio/latest/tokio/fs/index.html) itself is built on it, because most operating systems have no async file API. orch flushes its webhook dedup file this way, outside the lock, so a slow disk never holds an async worker:

```rust
let result = tokio::task::spawn_blocking(move || flush_dedup_file(&path, &entries)).await;
```

Source: [`src/channels/github.rs`](https://github.com/gabrielkoerich/orch/blob/872859922a506602e810712d929e13135be1c7f7/src/channels/github.rs#L188-L206)

The same codebase has the opposite case, on purpose. orch reads its GitHub token by running `gh auth token`, a blocking subprocess call of about 100 ms. It runs at most once an hour, under a lock, and the result is cached. Earlier attempts to "fix" it with `spawn_blocking` or `tokio::process` broke the auth flow. The function now carries [a comment](https://github.com/gabrielkoerich/orch/blob/872859922a506602e810712d929e13135be1c7f7/src/github/token.rs#L308-L321) that says not to touch it. A blocking call that happens once an hour costs nothing. The rule is about how long and how often, and grep cannot find that for you.

## Working: more cores

For CPU work the tool is [Rayon](https://docs.rs/rayon/latest/rayon/). It keeps [one thread per logical CPU](https://docs.rs/rayon/latest/rayon/struct.ThreadPoolBuilder.html#method.num_threads) and splits a parallel iterator across them with work stealing:

```rust
use rayon::prelude::*;

let total: u64 = jobs.par_iter().map(|&j| work(j)).sum();
```

2,000 small jobs took 47 ms on one thread and 4 ms with `par_iter`. That is close to 12x on 14 cores, and the M4 Max has 10 performance cores and 4 efficiency cores, so 12x is about what the hardware allows.

Tokio can also run CPU work in parallel, and with small jobs it matched Rayon's throughput. The cost shows up elsewhere: CPU work sits on the same workers as your network tasks.

To show it, I ran 56 jobs of 50 ms each, four per core, while a task on the same runtime waited on a 1 ms timer:

| where the 50 ms jobs ran | worst wait for a 1 ms timer |
|---|---|
| Tokio workers | 126 to 223 ms |
| Rayon, results sent back to Tokio | 11 to 114 ms |

On Tokio's workers, the timer task had to wait for a worker to finish a job. Four jobs of 50 ms per worker is about 200 ms, which fits the 126 to 223 ms I measured. With Rayon, the runtime threads stayed free. The timer was still late, and the likely reason is that Rayon's 14 threads and Tokio's 14 workers share 14 cores, so the OS scheduler decides who runs. I did not measure that part. If you need the runtime to stay responsive under full CPU load, give Rayon fewer threads than you have cores.

The pattern to connect them is a oneshot channel:

```rust
use tokio::sync::oneshot;

async fn hash(data: Vec<u8>) -> [u8; 32] {
    let (tx, rx) = oneshot::channel();
    rayon::spawn(move || {
        let _ = tx.send(blake3::hash(&data).into());
    });
    rx.await.expect("hash task panicked")
}
```

`spawn_blocking` works for CPU work too, but its pool grows to 512 threads. [Tokio's own docs](https://docs.rs/tokio/latest/tokio/task/fn.spawn_blocking.html) say to limit CPU work there with a semaphore, or to use Rayon.

So the split is simple. Waiting goes on the async runtime. Working goes on a pool sized to the cores. A program that does both keeps them apart and passes results through a channel.

## When a runtime is too much

The broker in [passbox](@/posts/2026-09-29-a-password-manager-for-agents.md), my password manager for agents, has no async runtime at all. It [accepts one connection at a time](https://github.com/gabrielkoerich/passbox/blob/f4d4a937c1aabc50787e2a48514799dc2ef3e240/src/broker.rs#L585-L594) on a Unix socket and answers it. A second thread [serves the network listener](https://github.com/gabrielkoerich/passbox/blob/f4d4a937c1aabc50787e2a48514799dc2ef3e240/src/broker.rs#L558-L576), and a third is [a watchdog](https://github.com/gabrielkoerich/passbox/blob/f4d4a937c1aabc50787e2a48514799dc2ef3e240/src/broker.rs#L600-L610) that exits the process, dropping the key, when no request has arrived for too long.

The [design doc](https://passbox.gabrielkoerich.com/design/) gives the reason in one line: no async runtime, "because a biometric prompt blocks anyway". The two listener threads share the broker state behind one `Mutex`, so only one request touches it at a time.

[Tokio's own tutorial](https://tokio.rs/tokio/tutorial) lists the cases where it does not help: CPU bound work, reading a lot of files, and a program that sends a single request. Plain threads also have real advantages. A blocking stack trace shows where the thread is waiting. There is no runtime to start and no colored functions, and `std::thread::scope` lets threads borrow from the caller instead of requiring `'static` data. A handful of long lived threads that each own one job is a good design.

If you do want async on one thread without the `Send` bound, spawn tasks with `spawn_local` on a `LocalSet`. Those tasks can hold `Rc` and `RefCell` instead of `Arc` and `Mutex`.

## Reacting: when the worst case matters

Async runtimes are built for throughput across many tasks. They are not built to bound how late one task can be. Every wake up goes through a queue, a parked worker has to be woken by the OS, and work stealing can move your task to a core with a cold cache.

I measured one way wake up latency three ways, sending one message at a time with a short idle pause between them:

| receiver | p50 | p99 | p99.9 |
|---|---|---|---|
| Tokio task, `tokio::sync::mpsc` | 8 µs | 440 to 620 µs | 1.0 to 1.7 ms |
| thread blocked on `std::sync::mpsc` | 2.6 to 3 µs | 130 to 220 µs | 0.56 to 0.73 ms |
| thread spinning on an atomic | 0.13 to 0.25 µs | 3.5 to 5.4 µs | 17 to 240 µs |

The median tells you about throughput. The tail tells you about the one tick you missed. A parked thread or task cost microseconds to wake at the median and hundreds of microseconds in the tail. The likely cause is that the OS has to schedule the thread again, which I did not measure directly. A thread that never sleeps is already running when the message lands.

For a hot path that has to react, the design changes:

- **One thread owns the work.** No runtime, no queue between the event and the handler.
- **It spins instead of parking.** It burns a whole core to never pay the wake up.
- **Nothing on the hot path allocates or takes a lock.** Memory is allocated at start. Data arrives through a lock free single producer, single consumer ring buffer.
- **No syscalls on the hot path.** Logging goes through another ring to another thread.

```rust
use rtrb::RingBuffer;

let (mut producer, mut consumer) = RingBuffer::<Tick>::new(4096);
std::thread::spawn(move || loop {
    match consumer.pop() {
        Ok(tick) => on_tick(tick),
        Err(_) => std::hint::spin_loop(),
    }
});
```

The other half is the operating system. A spinning thread is still preempted when the kernel wants that core. On Linux you pin the thread to a core and keep the kernel off it. [Firedancer](https://docs.firedancer.io/guide/tuning.html), the Solana validator written in C, runs each stage as a "tile" that takes ownership of a core and never sleeps, and its docs say anything else the kernel runs on those cores steals time and adds jitter. They recommend the `nohz_full` and `rcu_nocbs` kernel parameters for that reason.

macOS cannot do this. Apple's affinity API [only expresses hints](https://developer.apple.com/library/archive/releasenotes/Performance/RN-AffinityAPI/), and on Apple Silicon [it is not supported at all](https://developer.apple.com/forums/thread/703361). That is why my spinning thread had a p99.9 anywhere from 17 to 240 µs: a median of 125 ns, and every so often the kernel took the core away. Measure latency work on the hardware and OS it will run on.

The [LMAX Disruptor](https://lmax-exchange.github.io/disruptor/user-guide/index.html), a Java library built for an exchange, names the trade off directly. Its default wait strategy blocks and saves CPU. Its busy spin strategy is the fastest, and they say to use it only when there are fewer handler threads than physical cores. Spinning only works if every spinner has a core of its own.

## Thread per core

Between a work stealing runtime and a hand pinned thread there is a third design: one runtime per core, sharing nothing. [Seastar](https://seastar.io/shared-nothing/), the C++ framework under ScyllaDB, runs one thread per core and passes messages between them instead of sharing memory. In Rust, Glommio and ByteDance's Monoio do the same with io_uring.

The reasons are concrete. With one thread per core, a request is never touched by two threads, so it needs no locks and tasks do not need to be `Send`. Glauber Costa, who wrote Glommio, [points out](https://www.datadoghq.com/blog/engineering/introducing-glommio/) that a context switch costs about 5 µs while an NVMe read can finish in under 4 µs. At that point the scheduler is slower than the disk.

The cost is the reason Tokio steals work. Without stealing, one hot core stays hot while the others are idle. [Monoio's own README](https://github.com/bytedance/monoio) warns that it can be slower than Tokio when load is unbalanced. Thread per core pays off when you can split the load evenly, by connection, by key or by shard.

## Solana takes the same decision away from you

An on-chain Solana program has none of this. It is [single threaded](https://solana.com/docs/programs/limitations), it cannot spawn, and it has no async. Parallelism happens one level up. [Every transaction declares every account](https://solana.com/news/sealevel---parallel-processing-thousands-of-smart-contracts) it will read or write, and the runtime runs transactions with no overlapping writes at the same time. The program is a function. The validator decides what runs in parallel.

The validator had to learn the same lesson inside its own scheduler. [Before Agave 1.18](https://www.anza.xyz/blog/introducing-the-central-scheduler-an-optional-feature-of-agave-v1-18), four threads pulled non-vote transactions independently and often took conflicting locks, because none of them knew what the others were doing. The fix was a single scheduler thread that sees every transaction and routes each one to a worker that will not conflict. Deciding who touches what before the work starts beat letting threads find out through locks.

Off chain, the same split applies to a bot. RPC calls, websocket subscriptions and keeping state in sync are waiting, so they go on Tokio. Building and signing a transaction when an opportunity appears is reacting, so it gets its own thread and a ring buffer between them.

## Small machines

On a microcontroller the async model fits better than anywhere else. [Embassy](https://embassy.dev/book/) runs async Rust with no heap: tasks are statically allocated, and the CPU sleeps until an interrupt wakes the task that was waiting on it. The hardware interrupt is the waker. Embassy's docs say this can use less power than an RTOS, because the executor does not have to guess when a task is ready.

## Choosing

| the program | use |
|---|---|
| waits on many sockets, timers or requests | an async runtime, multi thread by default |
| does a little blocking IO inside async code | `spawn_blocking` |
| blocks once in a long while for ~100 ms | leave it, and write down why |
| does CPU work over many items | Rayon, sized to the cores |
| does both | async for IO, Rayon for CPU, a oneshot or channel between |
| has a few long lived jobs, or one human in the loop | plain threads |
| has to react within microseconds | one pinned thread, spinning, fed by a ring buffer |
| has even load across many connections | thread per core |
| runs on a microcontroller | Embassy |

## What it costs

**Async makes every function choose a side.** An async function can only be awaited from async code, so the choice spreads through a codebase. Crossing back with `block_on` inside a runtime panics.

**`tokio::spawn` needs `Send + 'static`.** Anything a task holds across an await has to be safe to move to another thread, on any runtime, unless it runs on a `LocalSet`. That is why so much async Rust is full of `Arc` and `Mutex`.

**Cancellation is silent.** A future dropped inside `select!` stops at its last await. If that was halfway through a write, the write is half done. Each branch of a `select!` has to be safe to drop.

**Spinning costs a core per thread.** A busy loop shows 100% CPU forever, heats a laptop and empties a battery. Use it only when a few microseconds matter more than a whole core.

**Pinning needs control of the machine.** Kernel parameters, isolated cores and a known CPU. A cloud VM or a Mac gives you less of that.

**Benchmarks lie by machine.** Everything above ran on one laptop, with other programs open. The ratios hold more than the absolute numbers. Measure on the target.
