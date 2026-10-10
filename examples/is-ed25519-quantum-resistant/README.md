# Solana quantum seed

Two experiments on what breaking Ed25519 gives an attacker on Solana.

| Recipe | What it does |
|---|---|
| `just forge` | Derives an Ed25519 key from a seed, keeps only the scalar an attacker would recover by breaking the curve, signs with it and verifies with the `cryptography` library |
| `just pokos-build` | Builds `ed25519-pokos` from [anza-xyz/cryptography](https://github.com/anza-xyz/cryptography/tree/master/experimental/ed25519-pokos) at commit `54963bf` |
| `just pokos` | Proves and verifies knowledge of a seed three times and prints the timings and proof size |

Every recipe runs in Docker. The build takes about ten minutes the first time.
