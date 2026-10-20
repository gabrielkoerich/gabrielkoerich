use slots_as_time::{check_cooldown_seconds, check_cooldown_slots, opens_after};
use solana_clock::{DEFAULT_MS_PER_SLOT, DEFAULT_SLOTS_PER_EPOCH};

// 267 is my getRecentPerformanceSamples number on mainnet, 2026-10-07
const STEPS: [(&str, u64); 6] = [
    ("400ms", 400),
    ("350ms", 350),
    ("300ms", 300),
    ("250ms", 250),
    ("measured", 267),
    ("200ms", 200),
];

fn main() {
    println!("solana-clock DEFAULT_MS_PER_SLOT = {DEFAULT_MS_PER_SLOT}");
    println!();
    println!(
        "{:<9} {:>20} {:>15} {:>8}",
        "slot", "150-slot cooldown", "60s cooldown", "epoch"
    );
    for (name, ms) in STEPS {
        let secs = |slots: u64| slots as f64 * ms as f64 / 1_000.0;
        let opens = |check: &dyn Fn(&solana_clock::Clock) -> bool| {
            opens_after(ms, check) as f64 / 1_000.0
        };
        println!(
            "{:<9} {:>19.1}s {:>14.1}s {:>7.1}h",
            name,
            opens(&|c| check_cooldown_slots(c, 0).is_ok()),
            opens(&|c| check_cooldown_seconds(c, 0).is_ok()),
            secs(DEFAULT_SLOTS_PER_EPOCH) / 3_600.0,
        );
    }
}
