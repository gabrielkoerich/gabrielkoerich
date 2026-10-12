+++
title = "To queue or not to queue"
date = 2026-10-12
description = "Beanstalkd ran 500 million jobs a month for my company. When to use a queue, when not to, and leases, retries and idempotency in Rust and TypeScript."
[taxonomies]
tags = ["rust", "typescript", "queues", "concurrency", "distributed-systems", "event-driven", "solana"]
+++

Ten years ago my company ran on [Beanstalkd](https://beanstalkd.github.io/). Jobs went into tubes, each with a priority, an optional delay and a time to run. A worker reserved a job, and if it did not finish within that time the server released the job for someone else. A job that kept failing got buried, set aside where the server would never touch it again, until I kicked it back. At our peak that setup moved more than 500 million background jobs a month.

I rarely see Beanstalkd mentioned now. The project is mature, which is a kind way to say its last commits were in March 2025, and the conversation moved to managed queues, Redis job libraries and Kafka. The ideas stayed. A time to run is a visibility timeout. A buried job is a dead letter. Kicking is a redrive. Every queue I have used since has the same few parts, with different names.

This post is the follow up to [Waiting and working in Rust](@/posts/2026-10-08-waiting-and-working-in-rust.md). That one was about running work concurrently inside one process. This one is about the step after: when work should leave the process and go through a queue, when it should not, and what you have to get right either way. The examples are in Rust and TypeScript, and they all run: [examples/to-queue-or-not-to-queue](https://github.com/gabrielkoerich/gabrielkoerich/tree/main/examples/to-queue-or-not-to-queue).

## What a queue buys you

A queue sits between the code that decides work should happen and the code that does it. The producer does not wait, so a request can return in milliseconds while the slow part, an email, a webhook, a settlement, happens later. A burst of a thousand events turns into a steady stream the workers can keep up with, instead of a thousand things running at once. When a worker fails, the message is still there, and a durable queue keeps it across crashes and deploys. And one event can feed several consumers that know nothing about each other.

Each of these has a price, and the price is the same everywhere: the work is no longer synchronous, so the caller cannot see its result, and the delivery guarantee you get is almost always at least once. [SQS](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-queue-types.html) says it plainly for standard queues: every message is delivered at least once, "but in some cases, a message may be delivered more than once". Most brokers work the same way by default. So the question to design for is how many times a job ran.

## When not to queue

Most work does not need a queue.

If the caller needs the result, a queue only adds a second round trip and a place for the answer to get lost. If the work finishes in the request, run it in the request. If all you want is to stop a thousand tasks from running at once, you want a limit on concurrency, which is a semaphore:

```rust
let limit = Arc::new(Semaphore::new(2));
let handles: Vec<_> = (0..30u64)
    .map(|i| {
        let limit = Arc::clone(&limit);
        tokio::spawn(async move {
            let _permit = limit.acquire_owned().await.unwrap();
            settle(&Transfer { id: format!("tx{i}:0"), amount: i }).await;
        })
    })
    .collect();
```

Source: [`rust/src/bin/queue.rs`](https://github.com/gabrielkoerich/gabrielkoerich/blob/main/examples/to-queue-or-not-to-queue/rust/src/bin/queue.rs)

Thirty settlements, two at a time, 330 ms on my machine, and nothing to deploy.

Two of my own projects make the same choice for different reasons. The broker in [passbox](@/posts/2026-09-29-a-password-manager-for-agents.md) serves one connection at a time with no runtime and no queue, because a biometric prompt blocks anyway. [orch](@/posts/2026-07-05-orchestrating-agents-for-humans.md) does have work waiting, but its queue is a table: tasks live in SQLite and GitHub issues, and a tick loop picks up whatever is ready every ten seconds. When the work already lives in a database, a loop that reads it can be the whole queue.

Postgres can serve a queue from an ordinary table with `SELECT ... FOR UPDATE SKIP LOCKED`, which the [docs](https://www.postgresql.org/docs/current/sql-select.html) describe as a way "to avoid lock contention with multiple consumers accessing a queue-like table". If the database is already there, the queue can live in the same transaction as the data it is about.

Queues in a database had a bad reputation for a long time, and it was earned. Workers polling one table all waited on the same row locks, so a busy queue turned into lock contention. `SKIP LOCKED` fixed that part, but it still has costs. Every claim and every completion is a write, and in Postgres the old row versions stay until vacuum removes them, so a busy queue table needs vacuum to keep up. Workers poll unless something wakes them. The queue shares the database with everything else, so a backlog slows the application. And there is no fan out or replay. For jobs tied to data in the same database, at a volume it handles comfortably, it is a good queue. When the queue starts to compete with the app, or several services need the same events, it is time for a broker.

## An event bus is not a queue

In TypeScript the first thing to reach for is an event emitter, which is not a queue. Node's [`EventEmitter`](https://nodejs.org/api/events.html) "calls all listeners synchronously in the order in which they were registered". There is no buffer and no retry, and nothing survives a crash. An async listener makes it worse, because `emit` does not wait for it:

```ts
const bus = new EventEmitter({ captureRejections: true })

bus.on('transfer', (id: string) => console.log(`saved ${id}`))
bus.on('transfer', async (id: string) => {
  await new Promise(r => setTimeout(r, 10))
  throw new Error(`notify failed for ${id}`)
})
bus.on('error', (e: Error) => console.log(`error event: ${e.message}`))

console.log('before emit')
const hadListeners = bus.emit('transfer', 'tx1:0')
console.log(`after emit, returned ${hadListeners}, nothing was awaited`)
```

Source: [`typescript/emitter.ts`](https://github.com/gabrielkoerich/gabrielkoerich/blob/main/examples/to-queue-or-not-to-queue/typescript/emitter.ts)

```text
before emit
saved tx1:0
after emit, returned true, nothing was awaited
error event: notify failed for tx1:0
```

The sync listener ran inside `emit`. The async one failed later, and the error only reached anyone because of `captureRejections`. Without it, the Node docs warn, an async handler "can lead to an unhandled rejection". An event bus decouples code inside one process, and anything on it is gone when the process dies.

## A queue inside the process

Between "no queue" and "a broker" there is a queue in memory, and this is where Rust and TypeScript differ.

Tokio gives you the queue and its backpressure. A bounded [`mpsc`](https://docs.rs/tokio/latest/tokio/sync/mpsc/index.html) channel "provides backpressure": `send` waits until there is room. The unbounded version is documented as having "the ability of causing the process to run out of memory". Two workers sharing one receiver, with a set of ids they have already handled:

```rust
let (tx, rx) = mpsc::channel::<Transfer>(4);
let rx = Arc::new(Mutex::new(rx));
let seen = Arc::new(Mutex::new(HashSet::new()));

for _ in 0..2 {
    let rx = Arc::clone(&rx);
    let seen = Arc::clone(&seen);
    tokio::spawn(async move {
        loop {
            let Some(t) = rx.lock().await.recv().await else { break };
            if !seen.lock().await.insert(t.id.clone()) {
                continue; // delivered twice, already settled
            }
            settle(&t).await;
        }
    });
}
```

Node has no bounded channel in the standard library, so the TypeScript version writes one: a `put` that waits while the queue is full and a `take` that waits while it is empty. It is about forty lines in [`typescript/queue.ts`](https://github.com/gabrielkoerich/gabrielkoerich/blob/main/examples/to-queue-or-not-to-queue/typescript/queue.ts). Both versions push 40 messages, ten of them duplicates, through a queue of four with two workers:

```text
rust:        settled 30 of 40 messages (30 unique) in 324ms, slowest send waited 22ms
typescript:  settled 30 of 40 messages (30 unique) in 315ms, slowest put waited 21ms
```

The numbers match because the work is waiting, and both runtimes wait well. The differences are elsewhere. Tokio can run those two workers on two threads, and the compiler makes the shared set prove it is safe to share, with `Arc` and a `Mutex`. Node runs both workers on one thread, so the set needs no lock, and nothing in the language stops you from forgetting the bound. Tokio's channel is bounded unless you pick the unbounded one on purpose. In TypeScript a bound exists only if you write it.

The duplicate check is the important line in both. A worker that does the work twice for a duplicate message has a bug, because the queue only ever promised at least once. The set in memory is the demo. In production the idempotency key goes into the database with the result, in the same write.

## Events in, a queue out: an indexer

The design I like most for this came from an indexer I built in TypeScript for a Solana program. It used both kinds of events, each for what it is good at.

The producer side received transactions by webhook. An RPC provider posted every transaction that touched the program to an authenticated endpoint, the indexer parsed and validated each one, and the parser emitted typed events on an in-process event bus: one per program event, one per parsed instruction and one per parsed transaction. Listeners were small classes with an optional `when` guard and a `handle`. One saved the parsed instructions to the database, a couple sent notifications, and one republished every program event to a Pub/Sub topic, with the event type as a message attribute.

Webhooks were the choice on purpose. A websocket subscription such as [`logsSubscribe`](https://solana.com/docs/rpc/websocket/logssubscribe) works too, but it only delivers while the socket is connected, and a dropped connection is a silent gap. A webhook from a provider that retries until it gets a success response is more reliable, because the retry is the provider's job: the endpoint answers `202` when it has the batch and `500` when it does not.

That last listener is the boundary. Everything before it is fast, local and in one process. Everything after it is durable and can fan out to any number of services that never import the indexer.

The consumer side was a worker on a Pub/Sub subscription. It dispatched each message to a handler by its type attribute, and each handler could set retries, a delay, a unique lock so the same job never ran twice at once, and whether to ack on start or on finish. It acked on success, and on failure waited and nacked so Pub/Sub would deliver it again. When it was at its limit of 30 running jobs, it nacked new messages instead of taking them.

The shape holds up. Reading it again next to the docs, these are the parts I would change.

- A backfill for when the provider gives up. Webhook retries do not last forever. A stored cursor, the last signature processed, and a backfill with [`getSignaturesForAddress`](https://solana.com/docs/rpc/http/getsignaturesforaddress), which pages through history with `before` and `until`, up to 1,000 signatures per call, would close any gap the provider leaves.

- A retried batch re-emits events. The parser emitted program events while it parsed. If one transaction in a batch failed after earlier ones had already emitted, the endpoint answered `500`, the provider sent the whole batch again, and those events fired twice, including the publish to Pub/Sub. Each event needs a key that does not change between attempts, such as the transaction signature plus the instruction index, and every consumer has to treat a second copy as already done.

- The `202` went out before the listeners finished. The endpoint emitted the events and answered right away, and as the event bus section showed, `emit` does not wait for async listeners. A listener that failed after that, the Pub/Sub publish included, never caused a `500`, so the provider never retried it. Awaiting the listeners that matter before answering, or writing to an outbox first, puts that failure back where the retry can see it.

- Let the subscription do the retries. Nacking to wait brings the message straight back. A [retry policy](https://docs.cloud.google.com/pubsub/docs/reference/rest/v1/projects.subscriptions) on the subscription backs off instead, and the client's flow control caps the messages in flight without nacking. The attempt counter the worker read was also [always 0](https://docs.cloud.google.com/pubsub/docs/reference/rest/v1/projects.subscriptions/pull) without a dead letter topic, so retry limits based on it never fired.

- Publish from the database, not next to it. Saving to the database and publishing to Pub/Sub were two separate steps, so a crash between them loses one. The [transactional outbox](https://microservices.io/patterns/data/transactional-outbox.html) writes the message into the database in the same transaction as the data, and a separate process publishes it. It can publish twice, which is fine, because the consumers are idempotent anyway.

## Events all the way down

The biggest version of this I built was the automation engine at Bulldesk, running on the same servers and queues as those 500 million jobs a month. A customer drew a campaign as a flow of steps, for example: wait two days, send an email, if they opened it add a tag, otherwise send a text. Every step was a job, and almost everything between steps was an event.

It started with domain events. A lead was created, visited a page, had an order change status, moved stage in a CRM. Each of those fired an event, and a queued listener picked it up on its own `listeners` queue, 15 seconds later. The listener found the active campaigns whose trigger matched that event and dispatched the first step of each one as a job. I wrote up a small piece of the same idea in 2018, in [Refactoring to Events](@/posts/2018-05-24-refactoring-to-events.md): a Stripe webhook controller that maps each webhook type to its own Laravel event, with listeners doing the work.

Every step job began with one more event, `ActionStart`, dispatched so that the first listener to answer `false` stopped the job. Eight listeners voted in order: is this step already running, was it deleted, is sending disabled, is it inside the campaign's schedule, is the lead still in the campaign, was this step already applied to this lead, is it a decision, do the segments still match. Each one was a few lines and checked one thing. A job that got a `false` was recorded as skipped.

When a step finished, its outcome was an event too: applied, not applied or skipped. Their listeners released the lock, wrote the log, scheduled the yes or no branch of a decision, and queued the next step, which is how a campaign moved forward without anything holding the whole flow in memory.

Order mattered inside one lead's campaign, and almost nowhere else, so that is the only place the engine kept it. A lead's steps ran one at a time even though each one was queued: a step dispatched the next only after it finished, delayed by the next step's own wait plus ten seconds, on its own `automation` queue. Across leads, everything ran in parallel. A bulk send to a segment walked its leads and dispatched one job per lead to one of five sending queues, picked at random, with a random delay of up to 90 seconds, so a send to a large list spread across workers and across time instead of landing all at once. It also stored its position as it went and stopped when paused, so a paused or crashed send picked up where it left off. The queued listeners on one event were separate jobs and ran side by side, while the guards on `ActionStart` ran inline and in order, because each one had to answer before the next could decide.

The chain was the second design. The first one queued every action of a campaign the moment a lead entered it, each delayed to the time it should run: three weekly emails were three jobs sitting in the queue for weeks. That made a lot of small problems. When the one in the middle failed, the rest were already queued behind it with nothing tying them to it. Editing the third email was fine, because a queued job held a reference to the email, its class and id, and loaded the content when it ran. Changing the step was not. If the customer swapped that email for another one, the queued job pointed at a deleted email and did nothing. If they replaced it with a different action, the job for the old action was still waiting in the queue. And if they added actions to the campaign, leads already in it never got them, because their whole campaign had been queued the day they entered. So I changed it to queue only the first action, and have each action, when it finished, check for a next one and queue that, until the campaign ended. With the chain, a step was queued at most one wait ahead, and the guards on `ActionStart` checked the campaign again when it ran.

That was the point of splitting a campaign into small actions, each its own step. Every action did one thing, so it finished fast, and when something was wrong it failed fast, at one step, without touching the steps already done. A step that failed went to a failed jobs table in MySQL and its error to an error tracker, and from there I could retry one job or all of them. A retried step that succeeded queued the next one, so an exception in one action no longer broke the campaign for that lead, it carried on from where it stopped. Every piece was small and could change on its own. The trade is that the flow of a campaign lives in the event map rather than in any one file, so following one lead through it means reading the logs.

Those logs had a cost of their own. Every step wrote to the log every time it ran, for every lead in every campaign, all into the same MySQL database the app ran on. The same table was also the duplicate check. Before a step ran, the guard for "already applied" looked in it for that action, lead and campaign, and skipped the step if it found a row, unless the campaign was set to repeat or the lead was added by hand. So every step read the table before it wrote to it. Writes never stopped, and in the end the database could not keep up with them. When we exited, I was looking for a different kind of database for the automation logs, one built to take a lot of writes at once.

## Locks: one message, one worker

With one worker, taking a message is enough. With several, each message needs a lock, usually called a lease, so only one worker has it at a time. Without it, two workers read the same message and both run it.

The brokers give you the lease. Beanstalkd's time to run, SQS's [visibility timeout](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html) and Pub/Sub's [ack deadline](https://docs.cloud.google.com/pubsub/docs/subscription-properties) all hide a message from other workers while one has it.

A table that workers poll has none of this unless you build it. In Postgres it is one query: `SKIP LOCKED` passes over the rows another worker is claiming right now, and a `locked_until` column is the lease after that:

```sql
UPDATE jobs
SET locked_until = now() + interval '30 seconds',
    attempts     = attempts + 1
WHERE id = (
  SELECT id FROM jobs
  WHERE run_at <= now()
    AND (locked_until IS NULL OR locked_until < now())
  ORDER BY id
  LIMIT 1
  FOR UPDATE SKIP LOCKED
)
RETURNING id, payload, attempts;
```

Source: [`postgres/claim.sql`](https://github.com/gabrielkoerich/gabrielkoerich/blob/main/examples/to-queue-or-not-to-queue/postgres/claim.sql)

I ran it with workers claiming at the same time against three jobs, using [`postgres/demo.sh`](https://github.com/gabrielkoerich/gabrielkoerich/blob/main/examples/to-queue-or-not-to-queue/postgres/demo.sh):

```text
worker A holds job 1 in an open transaction
worker B: claimed 2 attempt 1      (skipped the row A was claiming)
worker C: claimed 3 attempt 1
worker D: nothing                  (job 1 is locked, 2 and 3 hold a lease)
job 1's lease expires
worker E: claimed 1 attempt 2      (the work outlived its lease)
```

The last line is the catch. A lease is a timer, and if the worker only acknowledges at the end, any job that runs longer than the lease goes to a second worker while the first is still on it. Now it runs twice, at the same time. There are two ways out. Acknowledge at the start, and a crash loses the job, which is at most once. Or acknowledge at the end and extend the lease while you work. SQS and the Pub/Sub clients both let a worker extend its lease while it works. The indexer's worker made this a choice per handler, with an option to ack on start.

A lease covers one message. Two different messages about the same thing, two deposits for the same account, need a lock on the thing itself. The indexer had that too, a unique lock per job key, but it lived in the memory of one worker process. With two instances, each had its own set of locks, and both could run the same job. A lock that several workers share has to live somewhere they all see: a row lock in the database the work writes to, or a Redis key set with [`SET key token NX EX seconds`](https://redis.io/docs/latest/commands/set/), released by a script that deletes it only if it still holds your token.

Bulldesk's engine used the simple version, and it shows the catch from the other side. It ran on several servers with several queues, and its cache was Redis, so a lock in the cache was shared by every worker on every machine. The first guard on every step took one with the cache's `add`, keyed on the step, the lead and the sending, for 60 seconds. Laravel's `add` was a single Lua script, check that the key does not exist and set it with an expiry, and Redis runs a script atomically, so two workers could never both get it.

The timing left a gap, even if it rarely mattered. Actions were fast, and when something was wrong they failed fast, but the step jobs were allowed to run for 120 seconds, twice the lock. A step still running after a minute would have lost its lock, and a second worker could have started the same step for the same lead. The release had the matching gap: it was a plain delete, so a step that finished after its lock expired could delete the lock another worker had just taken, which is exactly the case the Redis docs' token check exists for. Fast work hides both. The rule for work that can be slow is that the lease outlasts the longest the work is allowed to take, and only the holder can release it.

## Retries and backoff

Every queue retries. The part you design is when to stop and how long to wait.

Errors come in two kinds. A timeout, a 429 or a dropped connection may succeed next time. A bad payload or an unknown account will fail forever, and retrying it only burns time and hides it. Retry the first kind, send the second straight to a dead letter queue, and give up on the first kind after a limit.

The wait between tries should grow, and it should be random. Exponential backoff alone makes every worker that failed together retry together. Full jitter waits a random time between zero and the exponential ceiling, which spreads them out:

```rust
// Full jitter: a random wait between zero and the exponential ceiling
fn backoff(attempt: u32) -> Duration {
    let ceiling = BASE.saturating_mul(1 << attempt.min(16)).min(CAP);
    let random = RandomState::new().build_hasher().finish();
    Duration::from_millis(random % (ceiling.as_millis() as u64 + 1))
}
```

```ts
// Full jitter: a random wait between zero and the exponential ceiling
const backoff = (attempt: number) => Math.random() * Math.min(CAP_MS, BASE_MS * 2 ** attempt)
```

Source: [`rust/src/bin/retry.rs`](https://github.com/gabrielkoerich/gabrielkoerich/blob/main/examples/to-queue-or-not-to-queue/rust/src/bin/retry.rs), [`typescript/retry.ts`](https://github.com/gabrielkoerich/gabrielkoerich/blob/main/examples/to-queue-or-not-to-queue/typescript/retry.ts)

Both versions run the same four messages, with a base of 100 ms, a cap of 2 seconds and five attempts:

```text
ok: settled on attempt 1
flaky: settled on attempt 3
dead letters: bad (unknown account), down (gave up after 5: 503)
```

In Rust the two kinds of error are an enum, and the `match` will not compile if a new kind is added and not handled. In TypeScript they are two classes and an `instanceof` check, and an error from somewhere else falls through to "permanent" unless you remember to classify it.

## Exactly once is always scoped

Every broker that offers exactly once means something narrower than the words.

- **SQS FIFO** deduplicates by deduplication id, but only [within a 5 minute window](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/using-messagededuplicationid-property.html).
- **Pub/Sub** exactly-once delivery [only applies](https://docs.cloud.google.com/pubsub/docs/exactly-once-delivery) "when subscribers connect to the service in the same region", and push subscriptions do not support it.
- **Kafka** has an idempotent producer and transactions that write to several partitions atomically. Its [design docs](https://kafka.apache.org/42/design/design/) are clear that exactly once "for other destination systems generally requires cooperation with such systems".

That other system is your consumer. The database write, the webhook or the token transfer at the end of the pipeline is outside every one of those guarantees. Make that step idempotent, and at least once is enough.

## Choosing one

| | Delivery | Ordering | Replay | Fits |
|---|---|---|---|---|
| [SQS](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-queue-types.html) | at least once, FIFO dedup for 5 min | best effort, or per message group with FIFO | no, retention up to 14 days | jobs on AWS, little to operate |
| [Pub/Sub](https://docs.cloud.google.com/pubsub/docs/ordering) | at least once, exactly once in region | per ordering key | retention up to 31 days | fan out on GCP |
| [Kafka](https://kafka.apache.org/42/getting-started/introduction/) | at least once, transactions inside Kafka | per partition | yes, consumers rewind their offset | event logs many systems read |
| [Redis Streams](https://redis.io/docs/latest/develop/data-types/streams/) | at least once with consumer groups | per stream | while the stream is kept | already running Redis |
| [Postgres `SKIP LOCKED`](https://www.postgresql.org/docs/current/sql-select.html) | what your transaction gives you | whatever you order by | it is a table | work tied to data in the same database |
| [Beanstalkd](https://github.com/beanstalkd/beanstalkd/blob/master/doc/protocol.txt) | at least once, time to run | priority, then arrival | no | fast, simple job queues on your own servers, with no replication |

Kafka is the odd one. A queue deletes a message once it is acked, and in Kafka events ["are not deleted after consumption"](https://kafka.apache.org/42/getting-started/introduction/), so a new consumer can read the whole history. That makes it an event log more than a queue, and it is the right tool when the events themselves are the record. It is moving toward queues too: Kafka 4.2 made [share groups](https://kafka.apache.org/42/getting-started/upgrade/) production ready, where consumers share a partition and acknowledge each message on its own, instead of one consumer per partition committing an offset.

## What it costs

**Duplicates are the default.** Every option above delivers at least once in its normal mode. A consumer that is not idempotent breaks on its first retry.

**Ordering costs throughput.** Ordering keys, message groups and partitions all limit parallelism to one consumer per key. Ask for ordering only where the domain needs it, usually per account or per user, never globally.

**A queue hides failure.** A request that fails shows an error. A job that fails sits in a dead letter queue that nobody reads. A dead letter queue needs an alert and an owner.

**Another system to run.** A broker is a service with its own outages, limits and bill. The table you already have, or a semaphore, costs nothing.

## The rule I use

Run it in the request if the caller needs the answer. Use a semaphore if the problem is too much at once. Use an in-process queue when one process does the work and losing it on a crash is acceptable. Use a broker when the work must survive the process, or when more than one service needs to hear about it. Whichever you pick, give every message a key, make every consumer idempotent, retry only what can succeed, and put an alert on the dead letters.
