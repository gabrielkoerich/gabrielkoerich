# To queue or not to queue: examples

Runnable examples for the post [To queue or not to queue](https://gabrielkoerich.com/posts/to-queue-or-not-to-queue/). The same ideas in Rust and in TypeScript.

| Example | Rust | TypeScript |
|---|---|---|
| A bounded queue with workers, backpressure and idempotency keys | `rust/src/bin/queue.rs` | `typescript/queue.ts` |
| No queue: bounded concurrency with a semaphore | `rust/src/bin/queue.rs` (second half) | |
| An in-process event bus is synchronous | | `typescript/emitter.ts` |
| Retries with exponential backoff, full jitter and a dead letter list | `rust/src/bin/retry.rs` | `typescript/retry.ts` |
| A Postgres table as a queue: claim with `SKIP LOCKED` and a lease | `postgres/claim.sql` | |

## Run

Rust (Tokio):

```sh
cd rust
cargo run --release --bin queue
cargo run --release --bin retry
```

TypeScript, with [Bun](https://bun.sh), which runs `.ts` files directly:

```sh
cd typescript
bun install    # only for the type check
bun run check
bun run queue
bun run emitter
bun run retry
```

Postgres, in Docker. `demo.sh` starts a container, runs five workers against the query in `claim.sql` with the lease cut to 2 seconds, and stops the container:

```sh
./postgres/demo.sh
```

## Output

Measured on an Apple M4 Max. Timings vary by machine.

```text
rust/queue:  settled 30 of 40 messages (30 unique) in 324ms, slowest send waited 22ms
rust/queue:  no queue: settled 30 with 2 at a time in 330ms
ts/queue:    settled 30 of 40 messages (30 unique) in 315ms, slowest put waited 21ms

emitter:     before emit
             saved tx1:0
             after emit, returned true, nothing was awaited
             error event: notify failed for tx1:0

retry:       ok: settled on attempt 1
             flaky: settled on attempt 3
             dead letters: bad (unknown account), down (gave up after 5: 503)

postgres:    worker A holds job 1 in an open transaction
             worker B: claimed 2 attempt 1      (skipped the row A was claiming)
             worker C: claimed 3 attempt 1
             worker D: nothing                  (job 1 is locked, 2 and 3 hold a lease)
             job 1's lease expires
             worker E: claimed 1 attempt 2      (the work outlived its lease)
```
