use std::collections::HashSet;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::{mpsc, Mutex, Semaphore};

#[derive(Debug, Clone)]
struct Transfer {
    id: String, // idempotency key, e.g. "<signature>:<instruction index>"
    amount: u64,
}

async fn settle(t: &Transfer) {
    tokio::time::sleep(Duration::from_millis(20)).await; // the slow side effect
    let _ = t.amount;
}

#[tokio::main]
async fn main() {
    // 1. A bounded channel is a queue with backpressure: send waits when it is full
    let (tx, rx) = mpsc::channel::<Transfer>(4);
    let rx = Arc::new(Mutex::new(rx));
    let seen = Arc::new(Mutex::new(HashSet::new()));

    let mut workers = Vec::new();
    for _ in 0..2 {
        let rx = Arc::clone(&rx);
        let seen = Arc::clone(&seen);
        workers.push(tokio::spawn(async move {
            let mut handled = 0;
            loop {
                let Some(t) = rx.lock().await.recv().await else { break };
                if !seen.lock().await.insert(t.id.clone()) {
                    continue; // delivered twice, already settled
                }
                settle(&t).await;
                handled += 1;
            }
            handled
        }));
    }

    let start = Instant::now();
    let mut slowest_send = Duration::ZERO;
    for i in 0..40u64 {
        let id = format!("tx{}:0", i % 30); // ten duplicates, like a retried delivery
        let t0 = Instant::now();
        tx.send(Transfer { id, amount: i }).await.unwrap();
        slowest_send = slowest_send.max(t0.elapsed());
    }
    drop(tx);
    let mut total = 0;
    for w in workers {
        total += w.await.unwrap();
    }
    println!("queue: settled {total} of 40 messages (30 unique) in {:?}, slowest send waited {:?}", start.elapsed(), slowest_send);

    // 2. No queue: the caller waits, a semaphore caps how many run at once
    let limit = Arc::new(Semaphore::new(2));
    let start = Instant::now();
    let handles: Vec<_> = (0..30u64)
        .map(|i| {
            let limit = Arc::clone(&limit);
            tokio::spawn(async move {
                let _permit = limit.acquire_owned().await.unwrap();
                settle(&Transfer { id: format!("tx{i}:0"), amount: i }).await;
            })
        })
        .collect();
    for h in handles {
        h.await.unwrap();
    }
    println!("no queue: settled 30 with 2 at a time in {:?}", start.elapsed());
}
