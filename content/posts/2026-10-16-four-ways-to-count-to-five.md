+++
title = "Four ways to count to five"
description = "A recursive Fibonacci Solana program that only ran in my tests, rebuilt four ways with split crates, Anchor 1, Anchor 2 and Pinocchio, and measured."
date = 2026-10-16
[taxonomies]
tags = ["rust", "solana", "anchor", "pinocchio", "performance"]
+++

In February I wanted to see how small a Solana program could get without a framework. `solana-program` had been split into small crates, so I wrote [solana-fib-cpi](https://github.com/gabrielkoerich/solana-fib-cpi) with six of them: `solana-account-info`, `solana-cpi`, `solana-instruction`, `solana-msg`, `solana-program-entrypoint` and `solana-pubkey`. No Anchor, no `solana-program`.

The program computes Fibonacci numbers in the most wasteful way I could think of. One instruction creates a PDA at `["fib", payer]` with 25 bytes, `a`, `b`, `n` and a bump. Then the program calls itself through CPI, and every call advances `(a, b, n)` to `(b, a + b, n - 1)` until `n` reaches zero. Solana allows direct self-recursion and refuses indirect reentrancy, and the [CPI docs](https://solana.com/docs/core/cpi) put the stack depth at 5, so `n = 4` is as far as one transaction goes. Four steps from `a = 0, b = 1` ends at `b = 5`. Hence the title.

The tests passed. I meant to compare it with the new frameworks. The first thing I found was that it could not run on mainnet.

## It only ran in my tests

My tests registered the program with `processor!`, which runs it as native Rust inside the test. For this post I built every version with `cargo build-sbf` and ran the real `.so` in [LiteSVM](https://github.com/LiteSVM/litesvm) with the mainnet feature set. The February program failed on the first self-CPI:

```text
Program 3yDL675dKEnNZfvDz6dznB3n3qpXpiZJK4pSYkSAd1Xr invoke [1]
Program 11111111111111111111111111111111 invoke [2]
Program 11111111111111111111111111111111 success
Program log: init: a=0 b=1 n=4
Unknown program 3yDL675dKEnNZfvDz6dznB3n3qpXpiZJK4pSYkSAd1Xr
Program 3yDL675dKEnNZfvDz6dznB3n3qpXpiZJK4pSYkSAd1Xr failed: An account required by the instruction is missing
```

On mainnet, a program can only invoke a program that is one of its own instruction accounts, and calling yourself is no exception. My instruction passed the PDA, the payer and the System Program, never the program itself.

Switching my tests from the native processor to the `.so` did not catch it either. All six still passed. Agave 2.x has a feature gate, `lift_cpi_caller_restriction`, that looks the callee up in the whole transaction instead, and `solana-program-test` turns on every feature by default. That one was never activated on mainnet: its feature account does not exist, and newer Agave releases have dropped it. With the feature turned off in the test, three of the six fail with the same `Unknown program`.

The fix is a fourth readonly account, the program, forwarded on every self-CPI. It is in [the repo](https://github.com/gabrielkoerich/solana-fib-cpi) now, with tests that load the `.so` and turn that feature off, and every version below has it. I wrote about the same trap in the post on [my quant book](@/posts/2026-10-05-running-a-quant-book-on-hyperliquid.md), from the other side: a test only proves what it actually runs, and here that includes the runtime's feature set.

## What changed since February

Before measuring anything I checked what my February code was standing on.

- `solana-program` now lives in [anza-xyz/solana-sdk](https://github.com/anza-xyz/solana-sdk) and is a facade: version 5.1.0 is mostly re-exports of the small crates. The ones I used at `2` are now at 3.x and 4.x.
- `Pubkey` is now `Address`. SDK v3 introduced `Address`, and `Pubkey` is a type alias of it.
- Rent got cheaper. I had hardcoded `(128 + len) * 3480 * 2`. [SIMD-0194](https://github.com/solana-foundation/solana-improvement-documents/blob/main/proposals/0194-deprecate-rent-exemption-threshold.md) replaced that pair with a single `lamports_per_byte` of 6,960, and SIMD-0437 has been lowering it in steps since. Mainnet charges 5,080 per byte today, so my program overpaid by about 287,000 lamports per PDA, and the gap grows with each step down. Read `Rent::get()`.
- The stack depth is still 5, so four nested CPIs. SIMD-0268 raises that to 8 nested CPIs and is accepted, but its feature is not active on mainnet yet.

## What dropping `solana-program` buys

The standard entrypoint in `solana-program-entrypoint` deserializes the input buffer into a `Vec` of `AccountInfo`, each one holding its lamports and data behind `Rc<RefCell<...>>`. That is a heap allocation and a set of reference counted cells before your code reads a single byte.

[Pinocchio](https://github.com/anza-xyz/pinocchio) does the opposite. Its README describes it as a library with "no external dependencies" whose entrypoint works "with no copies or allocations". An `AccountView` points into the input buffer the runtime already wrote, and the crate is `no_std`, so a program can declare `no_allocator!()` and have no heap at all. The account views now come from the SDK itself, `solana-account-view` and `solana-instruction-view`, and Pinocchio is a thin layer over them.

The new frameworks build on that layer. Anchor v2 is the one most people will meet: its crates depend on Pinocchio 0.11, `pinocchio-system` and a handful of split crates, and not on `solana-program` at all. Its [README](https://github.com/otter-sec/anchor/tree/v2.0.0-rc.1/lang-v2) calls it "a drop-in speedup for Anchor v1" that is "up to 94% smaller and 3× faster or more per instruction". Those are its own numbers, so I measured mine.

## One program, four ways

Same logic, same accounts, same 25 bytes of state (plus the 8 byte discriminator in both Anchor versions), four builds:

1. February, the split crates at 2.x, with the account fix and nothing else.
2. Anchor 1.2.1, the current stable release, on the split crates and their standard entrypoint.
3. Pinocchio 0.11.2, with `pinocchio-system` for the account creation.
4. Anchor 2.0.0-rc.1, the first release candidate on crates.io.

All four were built with `cargo build-sbf` 3.1.10 and platform-tools v1.52, and run in LiteSVM with the mainnet feature set. Each transaction runs init with `n = 4`, five levels deep, and every version ends at `a = 3, b = 5`. Logging costs a lot and every library logs differently, so the main builds have no logs. Every number held across three runs. The code and the benchmark are in [examples/four-ways-to-count-to-five](https://github.com/gabrielkoerich/gabrielkoerich/tree/main/examples/four-ways-to-count-to-five), and `just bench` reproduces the table.

The Pinocchio version reads close to the February one, with views instead of infos:

```rust
let [pda, payer, system, program, ..] = accounts else {
    return Err(ProgramError::NotEnoughAccountKeys);
};

if pda.is_data_empty() {
    // ... check the signer, the System Program and the PDA address
    CreateAccount::with_minimum_balance(payer, pda, DATA_LEN, program_id, None)?
        .invoke_signed(&[Signer::from(&seeds)])?;
    // ... write a = 0, b = 1, n and the bump straight into the account
}
```

Source: [`pinocchio/src/lib.rs`](https://github.com/gabrielkoerich/gabrielkoerich/blob/main/examples/four-ways-to-count-to-five/pinocchio/src/lib.rs)

Anchor v2 looks like Anchor, minus the lifetimes, with state that is read in place:

```rust
#[derive(Accounts)]
pub struct Fib {
    #[account(
        init_if_needed,
        payer = payer,
        seeds = [b"fib", payer.address().as_ref()],
        bump = pda.bump,
    )]
    pub pda: Account<FibState>,
    #[account(mut)]
    pub payer: Signer,
    pub system_program: Program<System>,
    pub fib_program: Program<FibProgram>,
}

#[account]
pub struct FibState {
    pub a: PodU64,
    pub b: PodU64,
    pub n: PodU64,
    pub bump: u8,
}
```

Source: [`anchor-v2/src/lib.rs`](https://github.com/gabrielkoerich/gabrielkoerich/blob/main/examples/four-ways-to-count-to-five/anchor-v2/src/lib.rs)

The results:

| Version | `.so` bytes | Init, n = 4 (CU) | Deepest level alone (CU) |
|---|---:|---:|---:|
| Anchor 1.2.1 | 147,368 | 33,686 | 4,637 |
| February, split crates 2.x | 41,616 | 14,517 | 878 |
| Anchor 2.0.0-rc.1 | 42,480 | 17,505 | 766 |
| Pinocchio 0.11.2 | 13,792 | 7,595 | 90 |

The deepest level is the last step, which does the Fibonacci arithmetic and returns without another CPI, so it is close to the fixed cost of entering each program.

## Reading the numbers

Anchor v1 is the expensive one. It costs 4.4 times what Pinocchio costs for the whole transaction, and its binary is more than ten times larger. Part of that is my program shape: with `init_if_needed` and a plain `bump`, Anchor v1 runs `find_program_address` and reads rent on every level, even when the account exists, because it cannot trust a stored bump on an account it might be creating. It also needs `exit()` before the self-CPI and `reload()` after, or the outer level writes its stale copy over the inner ones. A v1 program split into separate init and step instructions would pay less. It would also be a different program.

Anchor v2 halves it: 17,505 CU against 33,686, and a binary three and a half times smaller. It reads the bump from the account (`bump = pda.bump`), works on the account bytes in place, and needs no reload after the CPI. Its optional guardrails cost 88 CU, so turning them off is not where the difference is.

The levels make the comparison cleaner. After init, every recursive step adds a constant amount in each version, and the CPI itself is the same runtime work for all four:

| Version | CU per recursive step |
|---|---:|
| Anchor 1.2.1 | 6,687 |
| Anchor 2.0.0-rc.1 | 3,893 |
| February, split crates 2.x | 2,606 |
| Pinocchio 0.11.2 | 1,160 |

Per step, v2 is 1.7 times cheaper than v1 for this program, not the "3× faster" in its README. The README benchmarks other programs, so both can be true. Pinocchio does the whole step for a third of what v2 spends, so most of v2's remaining cost is the framework.

The hand-written split crates sit between them. The February version, without logs, is cheaper than Anchor v2 for the whole transaction and slightly more expensive at the deepest level. It still pays for the standard entrypoint, and it has none of Anchor's checks.

Pinocchio is the floor, 90 CU for a level that reads 24 bytes, adds two numbers and writes them back. Most of what is left in its 7,595 is the CPIs themselves. The same direction shows up in [SIMD-0266](https://github.com/solana-foundation/solana-improvement-documents/blob/main/proposals/0266-efficient-token-program.md), where the Token program rewritten on Pinocchio, p-token, takes `Approve` from 2,904 CU to 124.

Logs are not free either. The February program as I wrote it, with its `msg!` calls, costs 18,316 CU. Removing them saves 3,799, about a fifth of the transaction.

## What Anchor v2 changes

- No `<'info>` lifetimes, and handlers take `&mut Context<T>`.
- `Pubkey` becomes `Address`, following the SDK.
- `Account<T>` is zero-copy by default, for `T: Pod`. The Borsh behaviour of v1 moves to `BorshAccount<T>`.
- PDA bumps are computed at compile time when every seed is a literal.
- The crate is `no_std`, with `alloc` as a default feature.

It is still a release candidate. `2.0.0-rc.1` was published on 2026-08-12 and `2.0.0-rc.2` on 2026-10-12, and the v2 README still says "Alpha. Not audited". Building this example hit three rough edges: the `#[program]` derive needed `wincode` as a direct dependency, there was no generated program type to use in `Program<T>`, and the self-CPI went through a hidden `__cpi_accounts_fib` module because the public `cpi` module disables the entrypoint.

## What it costs

Pinocchio's 90 CU come with no checks I did not write: the `// ...` in the snippet above is where the signer, the System Program and the PDA address get checked by hand, and the February version is the same. Anchor v2 brings the checks back as a release candidate with the rough edges above. Anchor v1 is the stable release and the most expensive one in every column.

Testing the real `.so` costs a second harness: every program built with `cargo build-sbf` and loaded into LiteSVM with the mainnet feature set, next to the `processor!` tests, which passed for a program that never ran on mainnet.

## What I would do now

For a program where compute matters, Pinocchio, with the account views from the SDK. For a program a team has to read and change for years, Anchor v2 once it is released, because it keeps the Anchor shape and drops most of the cost.

The title has an expiry date. SIMD-0268 raises nesting to 8 CPIs once its feature is active on mainnet, and then the same program counts to 34 in one transaction. Which of the four pays most for the extra four levels is the next thing to measure.
