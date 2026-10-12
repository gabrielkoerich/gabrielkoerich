# solana-without-the-fork

A pinocchio 0.11.2 program built with upstream nightly rustc, upstream LLVM and [sbpf-linker](https://github.com/blueshift-gg/sbpf-linker) 0.2.3, for the post "Solana without the fork".

The program adds the u64 in the instruction data to the u64 stored in a counter account. It checks the account owner and that the account is writable, and rejects an overflow. Five Mollusk 0.16 tests cover the add and each rejection, and run against two builds of the same crate:

| Build | Toolchain | Size | Add |
|---|---|---|---|
| `target/bpfel-unknown-none/release/libcounter.so` | nightly-2026-10-08, sbpf-linker 0.2.3 | 3,824 bytes | 56 CU |
| `target-pt/sbpfv3-solana-solana/release/counter.so` | platform-tools v1.57, sBPF v3 | 7,680 bytes | 54 CU |

Everything runs in Docker. The image builds sbpf-linker from its crates.io source with `cargo install` and links platform-tools as the `+solana` toolchain.

```sh
just test    # builds both and runs the five tests against each
just size
just clean
```

Two changes from the [template](https://github.com/blueshift-gg/solana-upstream-bpf-template): `-Z build-std=core,alloc` lives in the `build-bpf` alias so `cargo test` on the host works, and the panic handler is pinocchio's `nostd_panic_handler!`, which logs the location and aborts.
