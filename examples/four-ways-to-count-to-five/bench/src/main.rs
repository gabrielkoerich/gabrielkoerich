use litesvm::LiteSVM;
use solana_address::{address, Address};
use solana_instruction::{AccountMeta, Instruction};
use solana_keypair::Keypair;
use solana_message::Message;
use solana_signer::Signer;
use solana_transaction::Transaction;

const PROGRAM_ID: Address = address!("3yDL675dKEnNZfvDz6dznB3n3qpXpiZJK4pSYkSAd1Xr");
const SYSTEM: Address = Address::new_from_array([0; 32]);
// sha256("global:fib")[..8], the Anchor instruction discriminator in v1 and v2
const ANCHOR_IX: [u8; 8] = [70, 90, 4, 242, 125, 100, 145, 58];
const RUNS: usize = 3;

struct Version {
    name: &'static str,
    so: &'static str,
    anchor: bool,
}

const VERSIONS: &[Version] = &[
    Version { name: "split-crates-2x (with msg!)", so: "split-crates-2x/target/logs/fib_split.so", anchor: false },
    Version { name: "split-crates-2x", so: "split-crates-2x/target/deploy/fib_split.so", anchor: false },
    Version { name: "anchor-v1", so: "anchor-v1/target/deploy/fib_anchor_v1.so", anchor: true },
    Version { name: "pinocchio", so: "pinocchio/target/deploy/fib_pinocchio.so", anchor: false },
    Version { name: "anchor-v2", so: "anchor-v2/target/deploy/fib_anchor_v2.so", anchor: true },
    Version { name: "anchor-v2 (no guardrails)", so: "anchor-v2/target/no-guardrails/fib_anchor_v2.so", anchor: true },
];

#[derive(PartialEq, Debug, Clone)]
struct Run {
    total: u64,
    levels: Vec<u64>, // inclusive CU per invoke depth, index 0 = top level
    logs: Vec<String>,
}

fn ix(v: &Version, pda: Address, payer: Address, n: Option<u64>) -> Instruction {
    let data = match (v.anchor, n) {
        (true, n) => [&ANCHOR_IX[..], &n.unwrap_or(0).to_le_bytes()].concat(),
        (false, Some(n)) => n.to_le_bytes().to_vec(),
        (false, None) => vec![],
    };
    Instruction {
        program_id: PROGRAM_ID,
        accounts: vec![
            AccountMeta::new(pda, false),
            AccountMeta::new(payer, true),
            AccountMeta::new_readonly(SYSTEM, false),
            // the self-CPI target must be one of the caller's accounts
            AccountMeta::new_readonly(PROGRAM_ID, false),
        ],
        data,
    }
}

fn send(svm: &mut LiteSVM, payer: &Keypair, ix: Instruction) -> Result<Run, String> {
    let msg = Message::new(&[ix], Some(&payer.pubkey()));
    let tx = Transaction::new(&[payer], msg, svm.latest_blockhash());
    let meta = svm.send_transaction(tx).map_err(|e| format!("{:?}\n{}", e.err, e.meta.logs.join("\n")))?;
    svm.expire_blockhash();
    Ok(Run { total: meta.compute_units_consumed, levels: levels(&meta.logs), logs: meta.logs })
}

/// Pair each "consumed X of Y" line with the depth of the invoke it closes
fn levels(logs: &[String]) -> Vec<u64> {
    let (mut stack, mut out) = (Vec::new(), vec![0u64; 0]);
    let program = PROGRAM_ID.to_string();
    for l in logs {
        let Some(rest) = l.strip_prefix("Program ") else { continue };
        if let Some(d) = rest.split(" invoke [").nth(1) {
            stack.push(d.trim_end_matches(']').parse::<usize>().unwrap());
        } else if rest.starts_with(&program) && rest.contains(" consumed ") {
            let cu: u64 = rest.split(" consumed ").nth(1).unwrap().split(' ').next().unwrap().parse().unwrap();
            let depth = *stack.last().unwrap();
            if out.len() < depth {
                out.resize(depth, 0);
            }
            out[depth - 1] = cu;
        } else if rest.ends_with(" success") || rest.contains(" failed: ") {
            stack.pop();
        }
    }
    out
}

fn state(svm: &LiteSVM, pda: &Address, v: &Version) -> (u64, u64, u64, u8, usize, u64) {
    let acct = svm.get_account(pda).expect("pda missing");
    assert_eq!(acct.owner, PROGRAM_ID);
    let d = &acct.data[if v.anchor { 8 } else { 0 }..];
    let u = |i: usize| u64::from_le_bytes(d[i..i + 8].try_into().unwrap());
    (u(0), u(8), u(16), d[24], acct.data.len(), acct.lamports)
}

fn setup(v: &Version) -> (LiteSVM, Keypair, Address, u8) {
    let mut svm = LiteSVM::new();
    let so = std::fs::read(format!("{}/../{}", env!("CARGO_MANIFEST_DIR"), v.so)).expect("build the programs first");
    svm.add_program(PROGRAM_ID, &so).unwrap();
    // fixed payer so the PDA bump, and with it the find_program_address cost, is the same everywhere
    let payer = Keypair::new_from_array([7; 32]);
    svm.airdrop(&payer.pubkey(), 10_000_000_000).unwrap();
    let (pda, bump) = Address::find_program_address(&[b"fib", payer.pubkey().as_ref()], &PROGRAM_ID);
    (svm, payer, pda, bump)
}

/// init with n=4: create the PDA, then 4 self-CPI steps, ending at a=3 b=5
fn init_n4(v: &Version) -> Run {
    let (mut svm, payer, pda, bump) = setup(v);
    let run = send(&mut svm, &payer, ix(v, pda, payer.pubkey(), Some(4))).unwrap();
    let (a, b, n, stored_bump, len, lamports) = state(&svm, &pda, v);
    assert_eq!((a, b, n, stored_bump), (3, 5, 0, bump), "{}: wrong fib state", v.name);
    assert_eq!(lamports, 1_064_880 + if v.anchor { 8 * 6960 } else { 0 }, "{}: rent", v.name);
    assert_eq!(len, if v.anchor { 33 } else { 25 });
    run
}

/// step on an existing PDA holding a=0 b=1 n=4: 4 levels, same final state
fn step_n4(v: &Version) -> Run {
    let (mut svm, payer, pda, bump) = setup(v);
    send(&mut svm, &payer, ix(v, pda, payer.pubkey(), Some(0))).unwrap();
    let mut acct = svm.get_account(&pda).unwrap();
    let o = if v.anchor { 8 } else { 0 };
    acct.data[o + 16..o + 24].copy_from_slice(&4u64.to_le_bytes());
    svm.set_account(pda, acct).unwrap();
    let run = send(&mut svm, &payer, ix(v, pda, payer.pubkey(), None)).unwrap();
    let (a, b, n, stored_bump, _, _) = state(&svm, &pda, v);
    assert_eq!((a, b, n, stored_bump), (3, 5, 0, bump), "{}: wrong fib state after step", v.name);
    run
}

/// n=5 needs invoke depth 6, mainnet allows 5
fn n5_error(v: &Version) -> String {
    let (mut svm, payer, pda, _) = setup(v);
    match send(&mut svm, &payer, ix(v, pda, payer.pubkey(), Some(5))) {
        Ok(_) => "accepted".into(),
        Err(e) => e.lines().next().unwrap().to_string(),
    }
}

fn repeat(f: fn(&Version) -> Run, v: &Version) -> Run {
    let first = f(v);
    for _ in 1..RUNS {
        assert_eq!(f(v), first, "{}: CU not deterministic", v.name);
    }
    first
}

fn fmt(levels: &[u64]) -> String {
    levels.iter().map(|c| c.to_string()).collect::<Vec<_>>().join(" / ")
}

fn main() {
    let verbose = std::env::args().any(|a| a == "--logs");
    println!("| version | .so bytes | init n=4 tx CU | init per level (inclusive, depth 1..5) | step n=4 tx CU | step per level (depth 1..4) | n=5 result |");
    println!("|---|---:|---:|---|---:|---|---|");
    for v in VERSIONS {
        let size = std::fs::metadata(format!("{}/../{}", env!("CARGO_MANIFEST_DIR"), v.so)).unwrap().len();
        let init = repeat(init_n4, v);
        let step = repeat(step_n4, v);
        println!(
            "| {} | {} | {} | {} | {} | {} | {} |",
            v.name, size, init.total, fmt(&init.levels), step.total, fmt(&step.levels), n5_error(v)
        );
        if verbose {
            eprintln!("--- {} init logs\n{}", v.name, init.logs.join("\n"));
        }
    }
    let bump = setup(&VERSIONS[0]).3;
    println!("\neach number held across {RUNS} runs; every version ends at a=3 b=5 n=0 with the canonical bump ({bump})");
}
