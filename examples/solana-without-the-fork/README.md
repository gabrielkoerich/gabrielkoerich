# solana-without-the-fork

A pinocchio 0.11.2 program built with upstream nightly rustc, upstream LLVM and [sbpf-linker](https://github.com/blueshift-gg/sbpf-linker) 0.2.3, for the post "Solana without the fork".

The program adds the u64 in the instruction data to the u64 stored in a counter account. It checks the account owner and that the account is writable, and rejects an overflow. Five Mollusk 0.16 tests cover the add and each rejection, and run against two builds of the same crate:

| Build | Toolchain | Size | Add |
|---|---|---|---|
| `target/bpfel-unknown-none/release/libcounter.so` | nightly-2026-10-08, sbpf-linker 0.2.3 | 3,824 bytes | 56 CU |
| `target-pt/sbpfv3-solana-solana/release/counter.so` | platform-tools v1.57, sBPF v3 | 7,680 bytes | 54 CU |

Everything runs in Docker except `just validator`. The image builds sbpf-linker from its crates.io source with `cargo install` and links platform-tools as the `+solana` toolchain.

> **`just validator` runs on your machine, not in Docker.** It downloads Agave 4.3.0's official binary for your OS into `.solana/` in this folder, checks it against a pinned SHA-256, and runs `solana-test-validator` and the Solana CLI from there, natively. Nothing is installed system-wide and nothing goes on your `PATH` outside the recipe, but the binaries do run on your host. The client also needs [Bun](https://bun.sh) on your machine. `just clean` deletes `.solana/`.

```sh
just test        # builds both and runs the five tests against each
just size
just validator   # deploys the upstream build to a local validator and sends real transactions
just clean       # removes the builds and the .solana cache
```

`just validator` runs `solana-test-validator` from Agave 4.3.0, the version mainnet runs, with `--clone-feature-set` so it has mainnet's features. It downloads Agave's own binary for your machine into `.solana/`, checks it against a pinned SHA-256, and keeps the ledger and keypairs there too. It does not run in Docker: Agave only ships Linux binaries for x86_64, and on Apple Silicon the emulated container has no io_uring, which Agave 4 needs. The client in `validator/client.ts` runs with Bun.

| Transaction | Result |
|---|---|
| Create the counter and add 37 | counter is 37 |
| Add 5 | counter is 42, in 56 CU |
| Add `u64::MAX` | rejected, "Program arithmetic overflowed" |

Two changes from the [template](https://github.com/blueshift-gg/solana-upstream-bpf-template): `-Z build-std=core,alloc` lives in the `build-bpf` alias so `cargo test` on the host works, and the panic handler is pinocchio's `nostd_panic_handler!`, which logs the location and aborts.
