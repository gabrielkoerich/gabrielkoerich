use agave_feature_set::{raise_cpi_nesting_limit_to_8, FeatureSet};
use litesvm::LiteSVM;
use solana_address::{address, Address};
use solana_instruction::{AccountMeta, Instruction};
use solana_keypair::Keypair;
use solana_message::Message;
use solana_signer::Signer;
use solana_transaction::Transaction;

const FIB: Address = address!("3yDL675dKEnNZfvDz6dznB3n3qpXpiZJK4pSYkSAd1Xr");
const SYSTEM: Address = Address::new_from_array([0; 32]);
const RUNS: usize = 3;
const MAX_RELAYS: usize = 9;

#[derive(PartialEq, Debug, Clone)]
struct Run {
    total: u64,
    levels: Vec<u64>, // inclusive CU per invoke depth of the given programs, index 0 = top level
}

fn svm(simd_0268: bool) -> LiteSVM {
    let mut features: FeatureSet = LiteSVM::mainnet_feature_set();
    assert!(!features.is_active(&raise_cpi_nesting_limit_to_8::ID), "litesvm thinks mainnet has SIMD-0268");
    if simd_0268 {
        features.activate(&raise_cpi_nesting_limit_to_8::ID, 0);
    }
    LiteSVM::new().with_feature_set(features)
}

fn so(path: &str) -> Vec<u8> {
    std::fs::read(format!("{}/../{}", env!("CARGO_MANIFEST_DIR"), path)).expect("build the programs first")
}

fn send(svm: &mut LiteSVM, payer: &Keypair, ix: Instruction, programs: &[Address]) -> Result<Run, String> {
    let msg = Message::new(&[ix], Some(&payer.pubkey()));
    let tx = Transaction::new(&[payer], msg, svm.latest_blockhash());
    let res = svm.send_transaction(tx);
    svm.expire_blockhash();
    match res {
        Ok(meta) => Ok(Run { total: meta.compute_units_consumed, levels: levels(&meta.logs, programs) }),
        Err(e) => Err(format!("{:?}\n{}", e.err, e.meta.logs.join("\n"))),
    }
}

/// Pair each "consumed X of Y" line of the given programs with the depth of the invoke it closes
fn levels(logs: &[String], programs: &[Address]) -> Vec<u64> {
    let names: Vec<String> = programs.iter().map(|p| p.to_string()).collect();
    let (mut stack, mut out) = (Vec::new(), Vec::new());
    for l in logs {
        let Some(rest) = l.strip_prefix("Program ") else { continue };
        if let Some(d) = rest.split(" invoke [").nth(1) {
            stack.push(d.trim_end_matches(']').parse::<usize>().unwrap());
        } else if rest.contains(" consumed ") && names.iter().any(|n| rest.starts_with(n.as_str())) {
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

/// init the fib PDA with n, which recurses n times through self-CPI, n + 1 levels deep
fn fib(n: u64, simd_0268: bool) -> Result<(Run, u64), String> {
    let mut svm = svm(simd_0268);
    svm.add_program(FIB, &so("fib/target/deploy/fib_pinocchio.so")).unwrap();
    let payer = Keypair::new_from_array([7; 32]);
    svm.airdrop(&payer.pubkey(), 10_000_000_000).unwrap();
    let (pda, _) = Address::find_program_address(&[b"fib", payer.pubkey().as_ref()], &FIB);
    let ix = Instruction {
        program_id: FIB,
        accounts: vec![
            AccountMeta::new(pda, false),
            AccountMeta::new(payer.pubkey(), true),
            AccountMeta::new_readonly(SYSTEM, false),
            AccountMeta::new_readonly(FIB, false),
        ],
        data: n.to_le_bytes().to_vec(),
    };
    let run = send(&mut svm, &payer, ix, &[FIB])?;
    let d = svm.get_account(&pda).unwrap().data;
    let (a, b, left) = (u64::from_le_bytes(d[0..8].try_into().unwrap()), u64::from_le_bytes(d[8..16].try_into().unwrap()), u64::from_le_bytes(d[16..24].try_into().unwrap()));
    assert_eq!((left, fib_pair(n)), (0, (a, b)));
    Ok((run, b))
}

fn fib_pair(n: u64) -> (u64, u64) {
    (0..n).fold((0, 1), |(a, b), _| (b, a + b))
}

fn relay_id(i: usize) -> Address {
    Address::new_from_array([10 + i as u8; 32])
}

/// relay 1 calls relay 2 ... calls relay k, which calls the System Program to move lamports
fn chain(k: usize, simd_0268: bool) -> Result<Run, String> {
    let mut svm = svm(simd_0268);
    let relay = so("relay/target/deploy/relay.so");
    for i in 0..MAX_RELAYS {
        svm.add_program(relay_id(i), &relay).unwrap();
    }
    let payer = Keypair::new_from_array([7; 32]);
    let dest = Address::new_from_array([99; 32]);
    svm.airdrop(&payer.pubkey(), 10_000_000_000).unwrap();
    // every program further down the chain is an account of the ones above it
    let mut accounts: Vec<AccountMeta> = (1..k).map(|i| AccountMeta::new_readonly(relay_id(i), false)).collect();
    accounts.push(AccountMeta::new_readonly(SYSTEM, false));
    accounts.push(AccountMeta::new(payer.pubkey(), true));
    accounts.push(AccountMeta::new(dest, false));
    let data = [&2u32.to_le_bytes()[..], &1_000_000u64.to_le_bytes()].concat(); // SystemInstruction::Transfer
    let ix = Instruction { program_id: relay_id(0), accounts, data };
    let relays: Vec<Address> = (0..k).map(relay_id).collect();
    let run = send(&mut svm, &payer, ix, &relays)?;
    assert_eq!(svm.get_balance(&dest), Some(1_000_000));
    Ok(run)
}

fn repeat<T: PartialEq + std::fmt::Debug>(f: impl Fn() -> T) -> T {
    let first = f();
    for _ in 1..RUNS {
        assert_eq!(f(), first, "not deterministic");
    }
    first
}

fn fmt(levels: &[u64]) -> String {
    levels.iter().map(|c| c.to_string()).collect::<Vec<_>>().join(" / ")
}

fn cell<T>(r: &Result<T, String>, f: impl Fn(&T) -> String) -> String {
    match r {
        Ok(v) => f(v),
        Err(e) => e.lines().next().unwrap().to_string(),
    }
}

fn main() {
    if std::env::args().any(|a| a == "--logs") {
        eprintln!("{}", fib(8, false).unwrap_err());
        return;
    }
    println!("## fib, init with n: n self-CPIs, invoke depth n + 1\n");
    println!("| n | depth | mainnet features | with SIMD-0268 | b | per level with SIMD-0268 (inclusive) |");
    println!("|---:|---:|---|---|---:|---|");
    for n in 0..=9u64 {
        let main = repeat(|| fib(n, false));
        let simd = repeat(|| fib(n, true));
        if let (Ok(a), Ok(b)) = (&main, &simd) {
            assert_eq!(a, b, "feature changed the CU of a run that fits");
        }
        println!(
            "| {n} | {} | {} | {} | {} | {} |",
            n + 1,
            cell(&main, |(r, _)| format!("{} CU", r.total)),
            cell(&simd, |(r, _)| format!("{} CU", r.total)),
            cell(&simd, |(_, b)| b.to_string()),
            cell(&simd, |(r, _)| fmt(&r.levels)),
        );
    }

    println!("\n## relay chain: k relays, the last one calls the System Program, invoke depth k + 1\n");
    println!("| relays | depth | mainnet features | with SIMD-0268 | per relay with SIMD-0268 (inclusive) |");
    println!("|---:|---:|---|---|---|");
    for k in 1..=MAX_RELAYS {
        let main = repeat(|| chain(k, false));
        let simd = repeat(|| chain(k, true));
        println!(
            "| {k} | {} | {} | {} | {} |",
            k + 1,
            cell(&main, |r| format!("{} CU", r.total)),
            cell(&simd, |r| format!("{} CU", r.total)),
            cell(&simd, |r| fmt(&r.levels)),
        );
    }
    println!("\neach number held across {RUNS} runs on a fresh VM");
}
