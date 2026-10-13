+++
title = "Solana without the fork"
date = 2026-10-13
description = "I built a pinocchio program with stock nightly Rust, upstream LLVM and sbpf-linker. It passed every test and came out half the size of the platform-tools build."
[taxonomies]
tags = ["solana", "rust", "llvm", "pinocchio"]
+++

Last week (Oct 9) a tweet from [Claire Fan](https://x.com/clairefxyz/status/2108550955570487632) showed up on my timeline: "For the first time in Solana history, we can generate Solana programs directly from upstream rustc and LLVM!" Starting with [sbpf-linker](https://github.com/blueshift-gg/sbpf-linker) 0.2.3, a `no_std` program builds with `cargo +nightly build`. Claire also wrote: "Anything that doesn't work should be considered a bug, and I'll fix it!"

I had to try it.

## Every program goes through a fork

Every Solana program you have deployed was compiled by a fork. Solana runs programs in a virtual machine that executes sBPF, its own flavor of eBPF, and the compiler that produces it is [platform-tools](https://github.com/anza-xyz/platform-tools): Anza's fork of [rustc](https://github.com/anza-xyz/rust) and of [LLVM](https://github.com/anza-xyz/llvm-project). `cargo build-sbf` downloads it and builds with it.

Keeping a fork of a compiler current is a lot of work, and it shows in the version numbers. Platform-tools v1.57, the release I tested with, ships rustc 1.95.0-dev from August 17. The nightly I used is rustc 1.101.0. Every Rust feature from those six versions reaches Solana programs late.

sbpf-linker takes another route. Rust already has a `bpfel-unknown-none` target, and upstream LLVM compiles to it. The linker takes the eBPF object that rustc produces and turns it into an sBPF v3 program. Everything Solana specific lives in a `.cargo/config.toml`: no stack unwinding, a 4 KiB stack frame, a few instruction forms LLVM must not emit, and `--cfg=target_os="solana"` so existing crates take their Solana code paths.

The timing works because of sBPF v3. It moves syscalls to link time: a program calls a syscall by the murmur3 hash of its name, so the linker does not need to know anything about how the validator loads programs. I checked the [feature account](https://explorer.solana.com/address/5cC3foj77CWun58pC51ebHFUWavHWKarWyR5UUik7dnC) on mainnet, and v3 deployment has been active since slot 428,976,000, on June 26. A program built this way can be deployed today. With Agave 4.4, expected in November, v3 [becomes the only format](https://solana.com/upgrades/sbpfv3-programs) mainnet accepts for new deploys and upgrades.

## Reading it first

I read code before I run it, and a linker runs on every build. This one is a pleasant read. sbpf-linker is a handful of Rust files, it makes no network calls, starts no other process, and writes only the `.so` it was asked for. The crates.io packages match their git tags file for file, every dependency comes from crates.io, and the release workflow pins its actions by commit and publishes with crates.io trusted publishing. The syscall hashes in the template and the builtins crate all match murmur3 of their names.

Everything below runs in Docker, with sbpf-linker built from its crates.io source, apart from the local validator at the end.

## A counter

The [template](https://github.com/blueshift-gg/solana-upstream-bpf-template) prints "Hello, world!", builds into a 240 byte `.so`, and its test passes after one change I get to below. I wanted something closer to a real program: accounts, an owner check, data I write to, and errors.

So I wrote a counter with [pinocchio](https://github.com/anza-xyz/pinocchio) 0.11.2. One instruction adds the u64 in the instruction data to the u64 stored in an account the program owns.

```rust
use pinocchio::{error::ProgramError, AccountView, Address, ProgramResult};

pinocchio::program_entrypoint!(process_instruction);
pinocchio::no_allocator!();
pinocchio::nostd_panic_handler!();

pub fn process_instruction(program_id: &Address, accounts: &mut [AccountView], data: &[u8]) -> ProgramResult {
    let [counter] = accounts else {
        return Err(ProgramError::NotEnoughAccountKeys);
    };

    if !counter.owned_by(program_id) {
        return Err(ProgramError::IncorrectProgramId);
    }

    // ... writable check

    let by: [u8; 8] = data.try_into().map_err(|_| ProgramError::InvalidInstructionData)?;
    let mut bytes = counter.try_borrow_mut()?;
    let stored: &mut [u8; 8] = (&mut bytes[..]).try_into().map_err(|_| ProgramError::InvalidAccountData)?;
    let next = u64::from_le_bytes(*stored)
        .checked_add(u64::from_le_bytes(by))
        .ok_or(ProgramError::ArithmeticOverflow)?;
    *stored = next.to_le_bytes();
    Ok(())
}
```

This is a plain pinocchio program. Nothing in it knows which compiler built it. I added pinocchio, ran `cargo +nightly build-bpf`, and it built on the first try.

That is less luck than it looks. pinocchio already pulls in its syscalls for `target_arch = "bpf"`, the upstream target, next to `target_os = "solana"`, and `solana-define-syscall` computes the murmur3 hashes at compile time when `static-syscalls` is set.

## Five tests, two compilers

Five [Mollusk](https://github.com/anza-xyz/mollusk) tests cover the add and each way it should fail: an overflow, an account owned by another program, a read only account, and instruction data that is not 8 bytes. I built the same crate through platform-tools v1.57 for sBPF v3 too, and ran the same five tests against both `.so` files.

| | Upstream and sbpf-linker | platform-tools v1.57 |
|---|---|---|
| Tests | 5 of 5 | 5 of 5 |
| `.so` size | 3,824 bytes | 7,680 bytes |
| Add 5 to 37 | 56 CU | 54 CU |

Half the size, and two compute units apart. I ran the set three times and got the same numbers each time. Mollusk counts compute units, it does not time anything.

On Solana, deploying a program means paying rent for every byte of it, so half the size is half the rent.

## On a real validator

Mollusk runs the program, it does not deploy it. So I deployed the upstream `.so` to `solana-test-validator` from Agave 4.3.0, the version mainnet runs, started with `--clone-feature-set` so it has exactly the features active on mainnet. The deploy went through, and three real transactions did what they should:

| Transaction | Result |
|---|---|
| Create the counter and add 37 | counter is 37 |
| Add 5 | counter is 42, in 56 CU, the same as in Mollusk |
| Add `u64::MAX` | rejected, "Program arithmetic overflowed" |

I first tried to run the validator in Docker, like everything else here. Agave only ships Linux binaries for x86_64, so on my Mac it ran under emulation, and it would not start: Agave 4 needs io_uring, and the emulated container does not have it ("Function not implemented"). Lifting Docker's seccomp filter did not help. Agave could be built for arm64 inside Docker, but it is a large Rust build, so `just validator` downloads Agave's own binary for your machine and runs it from there.

## One thing I changed

It is `cargo test`. The template sets `build-std` under `[unstable]`, which applies to the host build too, and the host build then fails with E0152, duplicate lang items. The builtins repo already has the fix in its own tests: put `-Z build-std` in the alias, so only the BPF build uses it.

```toml
[alias]
build-bpf = "build --release --target bpfel-unknown-none -Z build-std=core,alloc"
```

It is a few lines, and a PR I plan to send.

## Where I would like to help

The libcalls are the young part. LLVM turns some operations into calls to helper functions, and `solana-compiler-builtins` provides them for this target. Multiply works and is cheap. u128 division does not link yet: the linker asks for `__udivti3`, and after exporting it, for `__bpf_trap`. An f64 divide works but costs 736 CU against 192 on platform-tools. My counter never divides, so it never hit either problem, but any program that computes a price will.

## What it costs today

**A pinned nightly.** The target is Tier 3 in Rust, so `core` is built from source along with your program. The linker repo pins a nightly and a bot updates it, so you need to pin yours too.

**`no_std` only.** pinocchio fits. I did not try Anchor or `solana-program` on this path.

**Young.** Version 0.2.3. I would test a program here for a while before it holds anyone's money.

## Try it

The counter, a Dockerfile with both toolchains and a `Justfile` are in [examples/solana-without-the-fork](https://github.com/gabrielkoerich/gabrielkoerich/tree/main/examples/solana-without-the-fork). `just test` builds both `.so` files and runs the five tests against each, and `just validator` deploys the upstream one to a local validator and sends it real transactions.

Thanks to [Claire](https://x.com/clairefxyz) and the [Blueshift](https://github.com/blueshift-gg) team for doing the compiler and assembly work so the rest of us can build on stock Rust.
