use std::collections::hash_map::RandomState;
use std::hash::{BuildHasher, Hasher};
use std::time::Duration;

#[derive(Debug)]
enum SettleError {
    Retryable(String), // timeout, 429, connection reset
    Permanent(String), // bad payload, unknown account
}

const BASE: Duration = Duration::from_millis(100);
const CAP: Duration = Duration::from_secs(2);
const MAX_ATTEMPTS: u32 = 5;

// Full jitter: a random wait between zero and the exponential ceiling
fn backoff(attempt: u32) -> Duration {
    let ceiling = BASE.saturating_mul(1 << attempt.min(16)).min(CAP);
    let random = RandomState::new().build_hasher().finish();
    Duration::from_millis(random % (ceiling.as_millis() as u64 + 1))
}

async fn settle(id: &str, attempt: u32) -> Result<(), SettleError> {
    match id {
        "bad" => Err(SettleError::Permanent("unknown account".into())),
        "flaky" if attempt < 3 => Err(SettleError::Retryable("timeout".into())),
        "down" => Err(SettleError::Retryable("503".into())),
        _ => Ok(()),
    }
}

async fn handle(id: &str, dead_letters: &mut Vec<(String, String)>) {
    for attempt in 1..=MAX_ATTEMPTS {
        match settle(id, attempt).await {
            Ok(()) => {
                println!("{id}: settled on attempt {attempt}");
                return;
            }
            Err(SettleError::Permanent(e)) => {
                dead_letters.push((id.into(), e)); // retrying cannot fix it
                return;
            }
            Err(SettleError::Retryable(e)) if attempt == MAX_ATTEMPTS => {
                dead_letters.push((id.into(), format!("gave up after {attempt}: {e}")));
                return;
            }
            Err(SettleError::Retryable(_)) => tokio::time::sleep(backoff(attempt)).await,
        }
    }
}

#[tokio::main]
async fn main() {
    let mut dead_letters = Vec::new();
    for id in ["ok", "flaky", "bad", "down"] {
        handle(id, &mut dead_letters).await;
    }
    let list: Vec<String> = dead_letters.iter().map(|(id, why)| format!("{id} ({why})")).collect();
    println!("dead letters: {}", list.join(", "));
}
