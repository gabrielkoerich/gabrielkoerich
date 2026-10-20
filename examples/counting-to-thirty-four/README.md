# Counting to thirty-four

How deep a CPI chain can go on Solana, with and without the SIMD-0268 feature (`raise_cpi_nesting_limit_to_8`, `6TkHkRmP7JZy1fdM6fg5uXn76wChQBWGokHBJzrLB3mj`).

| Crate | What it is |
|---|---|
| `fib` | The Pinocchio Fibonacci program from [four-ways-to-count-to-five](../four-ways-to-count-to-five), copied unchanged. Init with `n` recurses `n` times through self-CPI, so it runs `n + 1` levels deep |
| `relay` | A Pinocchio program that calls the program in its first account with the remaining accounts and the same instruction data. The bench deploys the same `.so` at nine addresses, and the last relay calls the System Program to move lamports |
| `bench` | litesvm 0.16.0 (agave 4.2.2). Each case runs on LiteSVM's mainnet feature set, then again with `raise_cpi_nesting_limit_to_8` activated |

## Run

```
just bench    # builds both programs, then runs the litesvm harness
just logs     # failing logs of fib n=8 on the mainnet feature set
just clean    # removes .solana and every target folder
```

`just build` downloads Agave 3.1.10 into `.solana/`, checks its SHA-256 and runs its `cargo build-sbf`, which still needs Rust on the host and caches platform-tools under `~/.cache/solana`. The bench runs in the `rust:1` Docker image.

## Results

Fibonacci, init with `n`:

| n | depth | mainnet features | with SIMD-0268 | b | CU per level with SIMD-0268, inclusive |
|---:|---:|---|---|---:|---|
| 4 | 5 | 7595 CU | 7595 CU | 5 | 7595 / 3570 / 2410 / 1250 / 90 |
| 5 | 6 | CallDepth | 8755 CU | 8 | 8755 / 4730 / 3570 / 2410 / 1250 / 90 |
| 8 | 9 | CallDepth | 12235 CU | 34 | 12235 / 8210 / 7050 / 5890 / 4730 / 3570 / 2410 / 1250 / 90 |
| 9 | 10 | CallDepth | CallDepth | | |

Relay chain, `k` relays, the last one calls the System Program:

| relays | depth | mainnet features | with SIMD-0268 |
|---:|---:|---|---|
| 4 | 5 | 6265 CU | 6265 CU |
| 5 | 6 | CallDepth | 7922 CU |
| 8 | 9 | CallDepth | 13194 CU |
| 9 | 10 | CallDepth | CallDepth |

`just bench` prints every row from n = 0 and k = 1. Each number held across 3 runs on a fresh VM, and runs that fit in both feature sets cost the same CU in both.
