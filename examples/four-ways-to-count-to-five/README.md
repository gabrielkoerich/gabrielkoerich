# One program, four ways

The same recursive self-CPI Fibonacci program written four times, measured for deployed binary size and compute units.

The program has one instruction. When the PDA at `["fib", payer]` is empty, it reads `n` from the instruction data, creates the PDA with `a=0 b=1 n bump`, and calls itself. When the PDA exists, it advances `(a, b, n) -> (b, a+b, n-1)` and calls itself again while steps remain. Mainnet invoke depth is 5, so `n <= 4` fits in one transaction. After init with `n=4` the PDA holds `a=3 b=5 n=0`.

| Crate | Libraries | State bytes |
|---|---|---:|
| `split-crates-2x` | `solana-*` 2.x split crates, hardcoded rent (the reference program) | 25 |
| `anchor-v1` | `anchor-lang` 1.2.1, `init_if_needed`, `Account<T>` with Borsh | 33 (8 byte discriminator) |
| `pinocchio` | `pinocchio` 0.11.2, `pinocchio-system` 0.6.1, `no_std`, no allocator | 25 |
| `anchor-v2` | `anchor-lang` 2.0.0-rc.1 from crates.io, `init_if_needed`, zero-copy `Account<T>` with `PodU64` | 33 (8 byte discriminator) |

## Run

```
just bench    # builds all programs, then runs the litesvm harness in Docker
just build    # programs only
just clean    # removes .solana and every target folder
```

`just build` downloads the official Agave 3.1.10 release into `.solana/`, checks it against a pinned SHA-256 and runs its `cargo build-sbf` from there. `just bench` runs the harness in the `rust:1` image. The `Justfile` adds two extra builds: `split-crates-2x` with its `msg!` calls into `target/logs/`, and `anchor-v2` without guardrails into `target/no-guardrails/`.

Toolchain: `cargo build-sbf` 3.1.10, platform-tools v1.52 (rustc 1.89) for every program. Harness: litesvm 0.16.0 (agave 4.2.2) with its default mainnet feature set.

## Results

| Version | .so bytes | init n=4 tx CU | init CU per level, depth 1 to 5 | step n=4 tx CU | step CU per level, depth 1 to 4 |
|---|---:|---:|---|---:|---|
| split-crates-2x, with `msg!` | 43,184 | 18,316 | 18316 / 12107 / 8746 / 5385 / 2024 | 12,107 | 12107 / 8746 / 5385 / 2024 |
| split-crates-2x | 41,616 | 14,517 | 14517 / 8696 / 6090 / 3484 / 878 | 8,696 | 8696 / 6090 / 3484 / 878 |
| anchor-v1 | 147,368 | 33,686 | 33686 / 24698 / 18011 / 11324 / 4637 | 24,698 | 24698 / 18011 / 11324 / 4637 |
| pinocchio | 13,792 | 7,595 | 7595 / 3570 / 2410 / 1250 / 90 | 3,570 | 3570 / 2410 / 1250 / 90 |
| anchor-v2 | 42,480 | 17,505 | 17505 / 12445 / 8552 / 4659 / 766 | 12,445 | 12445 / 8552 / 4659 / 766 |
| anchor-v2, no guardrails | 42,128 | 17,417 | 17417 / 12377 / 8501 / 4625 / 749 | 12,377 | 12377 / 8501 / 4625 / 749 |

- `.so bytes` is the stripped file in `target/deploy`, the one that deploys.
- Per-level numbers are the runtime's `consumed X of Y` lines. Each one includes every level below it, so level 1 equals the transaction total.
- "step n=4" writes `a=0 b=1 n=4` into an existing PDA and sends the step instruction, so it measures four levels without the create.
- Each measurement runs 3 times on a fresh VM and the harness asserts identical numbers. Every version ends at `a=3 b=5 n=0` with the canonical bump, and `n=5` fails with `CallDepth` in all of them.
- All rows except the first are built without program logs. Anchor builds use `no-log-ix-name`.
- The payer is fixed, so the PDA bump is 255 in every run and `find_program_address` takes one iteration.

## Differences between the versions

- The reference program as first published failed on a real runtime: `Unknown program 3yDL…` then `MissingAccount` on the first self-CPI. Agave resolves a CPI target only from the caller's own instruction accounts, and the reference passed three. Its tests registered the program with `processor!`, so they ran it natively rather than as SBF. [solana-fib-cpi#1](https://github.com/gabrielkoerich/solana-fib-cpi/pull/1) fixed it on 2026-10-07. All four versions here take the program itself as a fourth readonly account and forward it on every self-CPI.
- Anchor instructions carry an 8 byte discriminator plus `n`, so step sends 16 bytes where the other two send none. The PDA is 8 bytes larger, and rent is 1,120,560 lamports where the others pay 1,064,880.
- Both Anchor versions detect a fresh account by `b == 0`, because `init_if_needed` does not report whether it created the account.
- anchor-v1 runs `Rent::get` and `find_program_address` on every level, also when the account exists. It must call `exit()` before the self-CPI and `reload()` after, or the outer level writes its stale copy back over the inner levels.
- anchor-v2 verifies the stored bump with `bump = pda.bump` on existing accounts, and its zero-copy account needs no flush or reload around the CPI. Its `#[program]` emits no program marker type, so `FibProgram` implements `Id` by hand for `Program<T>`.
- pinocchio and anchor-v2 read rent from the sysvar. split-crates-2x keeps the reference's hardcoded `(128 + 25) * 3480 * 2`, which gives the same number as LiteSVM's rent sysvar (6,960 lamports per byte). Mainnet charges 5,080 per byte, so on mainnet the hardcoded value overpays.
