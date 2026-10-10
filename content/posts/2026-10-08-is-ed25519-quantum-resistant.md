+++
title = "Is Ed25519 quantum resistant? Checking Solana's seed claim"
description = "Breaking Ed25519 exposes the signing key, not the seed. Solana's seed claim holds, but the exposed key still signs, so Solana still needs a network upgrade."
date = 2026-10-08
aliases = ["/posts/the-seed-behind-the-scalar/"]
[taxonomies]
tags = ["solana", "ethereum", "bitcoin", "cryptography", "quantum", "security"]
[extra]
image = "/images/posts/is-ed25519-quantum-resistant.png"
+++

I was scrolling Twitter today and found this post:

{% tweet(url="https://x.com/jacobvcreech/status/2108042644819427521", author="Jacob Creech (@jacobvcreech)", date="October 8, 2026") %}
Unlike many networks, Solana users don't need to go into "bunker mode" ahead of an accelerated quantum timeline or classical attack provided by AI.
{% end %}

Is Solana really quantum resistant? I did not think that was possible yet, so I started digging.

Creech was answering Justin Drake from the Ethereum Foundation. The day before, Drake had asked the industry to start planning for "bunker mode": move funds to addresses whose public keys are still hidden behind a hash. His worry is that elliptic curve signatures break sooner than planned, by a quantum computer or by an AI that finds a better classical attack.

{% tweet(url="https://x.com/drakefjustin/status/2107837081313505768", author="Justin Drake (@drakefjustin)", date="October 7, 2026") %}
Today I call upon the blockchain industry to calmly begin planning for "bunker mode". My personal recommendation is to set in motion a controlled mass migration of assets to fresh addresses, i.e. addresses whose pubkeys remain hidden behind a hash.
{% end %}

Creech's argument is that Solana does not need a bunker. Ed25519 derives every signing key by hashing a secret seed. Breaking the curve exposes the key, not the seed, so owners could later prove they know the seed and move to a safe scheme.

Both posts are about the same question: what exactly does an attacker get when the curve falls, and what is left for the owner? I read the papers, ran the math, and built Anza's proof of concept to find out. The examples run in Docker: [examples/is-ed25519-quantum-resistant](https://github.com/gabrielkoerich/gabrielkoerich/tree/main/examples/is-ed25519-quantum-resistant).

## What breaks, and how soon

Every major chain signs with an elliptic curve: secp256k1 for Bitcoin and Ethereum, Ed25519 for Solana. Their security rests on the discrete logarithm problem. Given a public point `A = s·B`, finding `s` is hard. [Shor's algorithm](https://arxiv.org/abs/quant-ph/9508027) solves it in polynomial time on a large enough quantum computer.

"Large enough" keeps shrinking:

| Year | Paper | Cost to break a 256-bit curve |
|---|---|---|
| 2017 | [Roetteler, Naehrig, Svore, Lauter](https://arxiv.org/abs/1706.06752) | About 2,330 logical qubits |
| 2023 | [Litinski](https://arxiv.org/abs/2306.08585) | 50 million Toffoli gates, one key every 10 minutes on 6,000 modules |
| 2026 | [Babbush, Gidney, Boneh, Drake and others](https://arxiv.org/abs/2603.28846) | Fewer than 1,200 logical qubits, "in minutes using fewer than half a million physical qubits" |
| 2026 | [Chevignard, Fouque, Schrottenloher](https://eprint.iacr.org/2026/280) | 1,193 logical qubits |

The Babbush paper does not publish its circuit. "In the interest of responsible disclosure", it proves the result with a zero knowledge proof instead. Classical attacks are far behind. The largest public breaks are around 113 bits for a [binary curve on FPGAs](https://eprint.iacr.org/2016/382) in 2016 and 114 bits for a [prime curve on 2,000 CPU cores](https://doi.org/10.1007/978-3-319-78556-1_13) in 2017. A 256-bit curve needs about 2^128 steps with Pollard's rho. Drake's AI worry is that someone finds a shortcut nobody has found in forty years of elliptic curve cryptography. No public result shows one.

Hashes are different. [Grover's algorithm](https://arxiv.org/abs/quant-ph/9605043) speeds up a brute force search only by a square root, and [that bound is tight](https://arxiv.org/abs/quant-ph/9701001). Searching 2^256 possibilities still takes about 2^128 quantum steps. Both tweets build on that gap between curves and hashes.

## Where each chain keeps the key

What the attacker needs is the public key. Here the three chains differ:

| | Bitcoin | Ethereum | Solana |
|---|---|---|---|
| Address | Hash of the key (P2PKH, P2WPKH), or the key itself (P2PK, Taproot) | Last 20 bytes of the Keccak hash of the key | The Ed25519 public key itself |
| Key public after | The first spend, or at creation for P2PK and Taproot | The first transaction | Creation |
| Can a user hide today? | Yes, with a fresh hashed address | Yes, with an address that never sent a transaction | Only by moving funds into a program account |

Hiding protects coins at rest. Every spend still reveals the key until the transaction confirms, and the Babbush paper warns that the first fast quantum computers "would enable on-spend attacks on public mempool transactions of some cryptocurrencies".

Bitcoin's exposure is measurable. Project Eleven's [snapshot from September 14](https://bitcoin-risq-list.projecteleven.com) counts 8,177,337 BTC in addresses whose public keys are already on chain. Most of it comes from address reuse, and 1.7 million sits in old P2PK outputs, Satoshi's coins included.

On Solana there is nothing to count, because [an address is the public key](https://solana.com/docs/core/accounts). Every funded account has been exposed since the moment it existed. The only accounts without an Ed25519 key are program accounts, like the Winternitz vault further down, and those are only as safe as the key that can upgrade the program.

## The seed

Creech's claim is about how [Ed25519](https://eprint.iacr.org/2011/368) makes its key. [RFC 8032](https://www.rfc-editor.org/rfc/rfc8032) starts from a 32-byte seed, hashes it with SHA-512, and clamps the first half into the secret scalar `s`. The public key is `s·B`, and the second half of the hash becomes a prefix used to derive nonces:

```python
import hashlib

digest = bytearray(hashlib.sha512(seed).digest())
digest[0] &= 248
digest[31] &= 127
digest[31] |= 64
s = int.from_bytes(digest[:32], "little")
```

The seed is what Solana keypair files store and what wallets derive from a mnemonic through SLIP-0010. Breaking the curve gives the attacker `s`. Going back to the seed means searching the 2^256 possible seeds for one that hashes to `s`, which Grover cuts only to about 2^128 quantum steps. For a wallet, the weakest link is the mnemonic: a 12-word phrase has 128 bits of entropy, so about 2^64 quantum steps, each one a full PBKDF2 key stretch. Both are far out of reach, so the claim holds: after the break, the owner still knows something the attacker cannot learn.

## What the scalar can still do

Knowing `s` is enough to sign. Ed25519 verification checks `S·B = R + k·A` and never checks how the nonce `r` was chosen. The seed's prefix makes nonces deterministic, but any random `r` gives a valid signature.

I tested it. The script derives a key from a random seed, keeps only `s`, signs with a random nonce, and verifies with Python's `cryptography` library:

```text
address (base58): 2yo4kayYa9i3tgmx2opVWTgq8dfdYUadsSxNATa28whS
s * B equals the address: True
forged signature verifies: True
```

So the seed only protects an account once the network stops accepting Ed25519 signatures. Anza's [post on the migration](https://www.anza.xyz/blog/securing-solana-against-a-powerful-quantum-adversary), published in April after the Babbush paper, says the same: an owner can migrate after the break "provided legacy Ed25519 signing has been disabled". That switch is Solana's version of bunker mode, and no user can do it alone. It is a network upgrade, and until it lands every account on chain can be drained with a valid signature.

## The proof that exists today

The proof of concept Creech linked is [ed25519-pokos](https://github.com/anza-xyz/cryptography/tree/master/experimental/ed25519-pokos) in Anza's cryptography repo, based on the paper [Post-Quantum Readiness in EdDSA Chains](https://eprint.iacr.org/2025/1368) by Baldimtsi, Chalkias, Roy and Sedaghat. A Plonky3 STARK proves that the prover knows a seed behind two public hashes. STARKs use only hash functions, with no curve for Shor to break, so they are considered post-quantum, although Grover shrinks their security margin.

I built it at commit `54963bf` and ran the bundled example three times in Docker on an Apple Silicon Mac, with 14 vCPUs and Rust 1.99:

| Run | Prove | Verify | Proof |
|---|---|---|---|
| 1 | 383 ms | 40 ms | 364,125 bytes |
| 2 | 358 ms | 45 ms | 366,525 bytes |
| 3 | 432 ms | 71 ms | 364,797 bytes |

These numbers describe one machine proving and checking one proof, off chain. On a chain the cost is different. Every validator would verify every migration proof, and the proof has to reach the chain somehow: 365 KB is about 300 times today's 1,232-byte transaction limit and about 90 times the proposed 4,096 bytes. So a proof this size cannot ride in a normal transaction, and these runs do not answer how a migration would carry or verify proofs at network scale. The README also calls the proof envelope stable, but its size changed on every run here.

The README also states the limits of the design.

**It proves a new derivation.** The chain inside the proof is `SHA512("ed25519-pokos/derive-sk/v1" || seed)`, a domain separated step that today's wallets do not use. Keys created with `solana-keygen` or a BIP39 wallet need a circuit that follows their actual derivation.

**It does not prove the link to the public key.** "It does not prove `sk → pk` inside the circuit; that link is enforced externally by the Ed25519 signature over the proof transcript." The README says what that means: "In a post-quantum setting, once an adversary can recover `sk` from `pk`, the signature no longer adds meaningful security." The authors call it "a temporary engineering compromise".

**It is not zero knowledge yet.** The README describes a zero knowledge proof, but at this commit the prover uses Plonky3's plain `TwoAdicFriPcs` commitment, not the hiding one, so the proof can leak information about the trace it was built from.

Proving the link to the public key inside the circuit while keeping `sk` secret "exceeds 1 billion gates", because elliptic curve math is expensive to prove. After Ed25519 is disabled, `s` no longer needs to stay secret: the attacker has it anyway. The proof can then reveal `s`, prove only the SHA-512 steps from the seed, and let the verifier check `s·B` against the address directly, which is cheap. The work that remains is a circuit for each derivation wallets really use, and binding the new post-quantum key into the proof so a copied proof cannot be replayed.

## Ethereum and Bitcoin have the same trick

The seed argument is not special to Solana. Vitalik Buterin described it for Ethereum in 2024, in [How to hard-fork to save most users' funds in a quantum emergency](https://ethresear.ch/t/how-to-hard-fork-to-save-most-users-funds-in-a-quantum-emergency/18901). His plan: revert the blocks where theft started, disable normal transactions, and let users prove with a STARK that they know the hash preimage their key came from, since "most users' private keys are themselves the result of a bunch of hash calculations". Bitcoin's draft [BIP-361](https://github.com/bitcoin/bips/blob/master/bip-0361.mediawiki) builds the same rescue into a plan to sunset legacy signatures, and Olaoluwa Osuntokun [proposed](https://groups.google.com/g/bitcoindev/c/Q06piCEJhkI) a STARK proof of BIP-32 seed knowledge for Taproot keys.

What differs is which keys have no seed to prove:

| Chain | Keys the seed proof cannot rescue |
|---|---|
| Ethereum | Keys imported as raw bytes, with no preimage |
| Bitcoin | Early P2PK coins. BIP-361 says it is "not currently believed possible to construct a rescue protocol for P2PK UTXOs" |
| Solana | Custody that never had a seed |

On Solana every normal key is an RFC 8032 seed by construction, so even a raw keypair file has something to prove. The exception is threshold custody. Schemes like [FROST](https://www.rfc-editor.org/rfc/rfc9591.html) split a random scalar, and Blockdaemon's docs say that for their EdDSA keys ["there is no seed"](https://builder-vault-tsm.docs.blockdaemon.com/docs/key-derivation-eddsa). Those accounts cannot use the proof and have to move before the break.

## What replaces the curve

After the switch, accounts need a new signature scheme, and every candidate is bigger:

| Scheme | Public key | Signature | Based on |
|---|---|---|---|
| Ed25519 | 32 bytes | 64 bytes | Elliptic curve |
| Falcon-512 | 897 bytes | 666 bytes | Lattices |
| ML-DSA-44 ([FIPS 204](https://csrc.nist.gov/pubs/fips/204/final)) | 1,312 bytes | 2,420 bytes | Lattices |
| SLH-DSA-128s ([FIPS 205](https://csrc.nist.gov/pubs/fips/205/final)) | 32 bytes | 7,856 bytes | Hashes only |

A Solana transaction is limited to 1,232 bytes today. Anza's post discusses Falcon, "the smallest of the three NIST schemes" and still "roughly 10 times larger" than Ed25519, and proposes indexing the new accounts by a hash of the public key. SIMD-0296 and SIMD-0385 would raise the transaction size to 4,096 bytes.

Drake goes further and wants to avoid structured math altogether, lattices included, and use only hash-based schemes like [SPHINCS+](https://eprint.iacr.org/2019/1086), which became SLH-DSA. Ethereum's draft roadmap at [strawmap.org](https://strawmap.org) already plans hash-based signatures for consensus, following [Hash-Based Multi-Signatures for Post-Quantum Ethereum](https://eprint.iacr.org/2025/055). The cost is in the table: 7,856 bytes per signature.

Solana already has one hash-based option. Blueshift's [Winternitz vault](https://github.com/blueshift-gg/solana-winternitz-vault) uses one-time signatures, the idea [Merkle](https://link.springer.com/chapter/10.1007/0-387-34805-0_21) credited to Winternitz in 1989. Each signature reveals part of the key, so every spend closes the vault and moves the rest to a new one. It holds only SOL, and you have to opt in.

User accounts are not the only thing signed with Ed25519. Validator identity, gossip messages, the QUIC TLS certificates between nodes and shreds all use it. Alpenglow's votes move to BLS, which a quantum computer also breaks. Proof of History is a sequential SHA-256 chain, and Grover does not speed that up.

## What it costs

**Dormant accounts.** Disabling Ed25519 stops every account that has not migrated, and an owner who is away when it happens needs a seed proof to get back in.

**The timing is a bet.** The upgrade has to land before a capable attacker exists. Waiting for proof of an attack means waiting until the first drained accounts.

**One circuit per wallet type.** RFC 8032 keys, BIP39 with SLIP-0010, and any wallet with its own derivation each need their own proof, and each needs an audit.

**Bigger transactions.** A post-quantum signature is ten to a hundred times the size of an Ed25519 signature, on a chain built around a 1,232-byte transaction.

**Validators too.** Identity keys, gossip, TLS and votes all need new schemes in the same window.

## Is Solana quantum safe?

No, and neither are Bitcoin or Ethereum. Creech's Ed25519 claim checks out: the key is a hash of a seed, breaking the curve exposes the key and not the seed, and seeds never appear on chain. But the exposed key still signs, so users cannot skip the bunker. On Solana the bunker is a network upgrade.

Some of the pieces already exist:

- Falcon implementations from Anza and Firedancer, according to the [Solana Foundation](https://solana.com/news/quantum-readiness).
- An on-chain Falcon verifier that costs under 170k compute units, the reason the [Falcon syscall SIMD](https://github.com/solana-foundation/solana-improvement-documents/pull/461) was paused.
- The Winternitz vault, usable today.
- Anza's seed proof, as a proof of concept.
- SIMD-0296 and SIMD-0385 for bigger transactions.

The pieces that make it safe do not:

- A SIMD that disables Ed25519 and migrates accounts. None has been proposed.
- Seed proofs for the derivations wallets use today, bound to the new post-quantum key.
- Post-quantum signatures for validator identity, gossip, TLS, shreds and Alpenglow's BLS votes.
- A plan for MPC custody, which has no seed to prove.

The other chains are at a similar stage. Ethereum's [roadmap](https://ethereum.org/roadmap/future-proofing/quantum-resistance/) aims for full post-quantum protection by about 2029, and its user side change, [EIP-8141](https://eips.ethereum.org/EIPS/eip-8141), is a draft. Bitcoin's [BIP-360](https://github.com/bitcoin/bips/blob/master/bip-0360.mediawiki) and BIP-361 are drafts, and BIP-361's sunset runs about five years after activation.

Whether Solana is safe depends on the rest landing before a capable quantum computer does. Anza puts that risk as almost negligible within two to three years and possible within five, which gives Solana a few years to specify and ship the migration.

If you work on any of these migrations, I would like to know how you plan to handle dormant accounts. The scripts are at [examples/is-ed25519-quantum-resistant](https://github.com/gabrielkoerich/gabrielkoerich/tree/main/examples/is-ed25519-quantum-resistant).

## Papers

- Shor, [Polynomial-Time Algorithms for Prime Factorization and Discrete Logarithms on a Quantum Computer](https://arxiv.org/abs/quant-ph/9508027), 1994
- Grover, [A fast quantum mechanical algorithm for database search](https://arxiv.org/abs/quant-ph/9605043), 1996
- Bennett, Bernstein, Brassard, Vazirani, [Strengths and Weaknesses of Quantum Computing](https://arxiv.org/abs/quant-ph/9701001), 1997
- Bernstein, Duif, Lange, Schwabe, Yang, [High-speed high-security signatures](https://eprint.iacr.org/2011/368), 2011
- Roetteler, Naehrig, Svore, Lauter, [Quantum resource estimates for computing elliptic curve discrete logarithms](https://arxiv.org/abs/1706.06752), 2017
- Bernstein, Hülsing, Kölbl, Niederhagen, Rijneveld, Schwabe, [The SPHINCS+ Signature Framework](https://eprint.iacr.org/2019/1086), 2019
- Litinski, [How to compute a 256-bit elliptic curve private key with only 50 million Toffoli gates](https://arxiv.org/abs/2306.08585), 2023
- Drake, Khovratovich, Kudinov, Wagner, [Hash-Based Multi-Signatures for Post-Quantum Ethereum](https://eprint.iacr.org/2025/055), 2025
- Baldimtsi, Chalkias, Roy, Sedaghat, [Post-Quantum Readiness in EdDSA Chains](https://eprint.iacr.org/2025/1368), 2025
- Babbush, Zalcman, Gidney, Broughton, Khattar, Neven, Bergamaschi, Drake, Boneh, [Securing Elliptic Curve Cryptocurrencies against Quantum Vulnerabilities](https://arxiv.org/abs/2603.28846), 2026
- Chevignard, Fouque, Schrottenloher, [Reducing the Number of Qubits in Quantum Discrete Logarithms on Elliptic Curves](https://eprint.iacr.org/2026/280), 2026
