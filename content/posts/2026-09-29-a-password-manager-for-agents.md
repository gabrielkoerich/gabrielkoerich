+++
title = "A password manager for agents"
date = 2026-09-29
aliases = ["/posts/passbox/"]
[taxonomies]
tags = ["ai", "agents", "security", "rust", "secrets-management", "mcp", "touch-id", "secure-enclave", "tailscale", "macos"]
+++

I have twenty-three scheduled jobs that run coding agents against my finance project. They read API keys, an exchange signing key, a mail password. They got those from `pass`, which works like this: one GPG passphrase opens everything, the agent caches it, and from then on the agent can read every secret I own.

That was fine when the one reading secrets was me. It stopped being fine when it became an agent whose transcript gets sent to a model provider.

## The problem

Three things happen when an agent needs a secret.

**It reads the whole store, not one entry.** Nothing scopes a GPG passphrase to one file. Once the agent has it, `pass show anything` works. So "this job needs one API key" really means "this job can read everything I own".

**The value lands in the context.** `pass show api/key` prints to stdout, the agent captures stdout, and now the secret is in a transcript that gets logged, retried, and sent to a model. A `.env` file is the same problem with fewer steps. You cannot un-send it.

**Nobody can say what was read.** There is no record of which agent opened which secret at which time. When something leaks, the investigation starts at "well, it had access to everything".

I also found hardcoded passwords in my own repo while looking into this, which is the usual way these things go.

## The alternatives, and why I did not use them

**`pass`** is what I was already running and still run. It is a decade old, packaged everywhere, and losing your laptop is survivable by design. But entry names are plaintext filenames, and they show up in git commit subjects too. One passphrase opens everything, and it has no idea who is asking.

**A `.env` file** puts values on disk in the clear, which is why it is gitignored, and why it ends up being pasted into chat when a colleague needs it.

**1Password's CLI** is good and I use it daily for SSH. It is built for a human at a keyboard. A signed-in session can read every item the account can see. [`op run`](https://www.1password.dev/cli/reference/commands/run/) can put secrets into one process, and a [service account](https://www.1password.dev/service-accounts/) can be limited to chosen vaults. What I wanted and did not find was a fingerprint for one secret, asked for by one named agent.

**Vault** solves scoping properly and costs a server, a policy language, and an operator. For a laptop and a handful of scheduled jobs it is the wrong size. And you still end up with a token that, once leaked, opens what it was scoped to.

None of these are bad, and I still use two of them. They were built for people. What changed is that the thing asking for a secret is now a program, and its memory is a transcript that goes somewhere else.

## What I built

[passbox](https://passbox.gabrielkoerich.com) is a password store where a fingerprint releases one secret into one process.

```bash
passbox exec --env GITHUB_TOKEN=github/token -- gh api /user
```

macOS raises a Touch ID prompt naming the agent and the secret. The value goes from the broker into that child process. It is never in the agent's stdout, transcript, or tool result.

Four properties follow from that:

**Entry names live inside the ciphertext.** Files on disk are random ids, so the store leaks how many secrets you have and nothing else. No `github/token` in a filename or a commit subject.

**The key is sealed to the Secure Enclave.** There is no passphrase by default, so there is no file anyone can carry off and grind. The cost is real and I will come back to it.

**Every release is audited**, encrypted, one record per line: which agent, which secret, when, and what the decision was.

**The MCP server has no `get_secret` tool.** It has `list_secrets`, which returns names, and `run_with_secret`, which runs your command and scrubs the value out of the output.

## The part I got wrong first

My first version prompted per read, with a five-minute approval window. It worked, but a trading job at 3am cannot answer a fingerprint prompt.

I tried a longer window, then a per-secret lease held in the broker, then a scoped bearer token. The token is a good mechanism and it shipped, but it still did not solve the problem, because a token expires and renewing one needs a human.

The answer was to stop reading at runtime:

```bash
passbox exec --env SIGNING_KEY=acme/signing-key -- ./daemon
```

One approval at launch, the value in the process environment, every child inherits it, and nothing calls passbox again for the life of the process. My daemon went from a fingerprint per order to zero reads in sixty seconds of live trading. I deleted the lease. Two mechanisms for one job means the docs start disagreeing with the code.

## What it costs

**A machine with no sensor cannot approve.** A Linux box can ask my Mac over Tailscale and the prompt appears here. I tested that from a Raspberry Pi and from a fly.io machine in another region. But the Mac has to be awake, unlocked, and lid open. A closed lid fails. The error says so and suggests opening the lid or using the recovery passphrase.

**Unattended means no human gate.** Injection and tokens both hand a value to something that runs without you. What you keep is that the value never enters the agent's context, every release is recorded, and a grant covers named secrets instead of the whole store.

**The agent name is self-declared.** The broker cannot verify it, because the process on the socket is always `passbox` with the real caller somewhere up the tree. You can trust the secret name in the prompt. Treat the agent name as a label.

**Lose the Mac and the secrets are gone**, unless you turned sync on. `pass` gets this right by default and passbox does not.

**It is young and unreviewed.** Cross-implementation tests raise confidence. Python's `cryptography` opens what CryptoKit sealed, and the reference `age` CLI reads the store. Neither is an audit.

## Why bother

The other option is to hand an agent the keys to everything and hope the transcript never leaks.

So I use passbox for the secrets my agents touch, `pass` for the ones I cannot afford to lose, and 1Password for the ones I need on my phone. passbox only does the one job: it sits between an agent and a credential.

If you run agents on your own machine, I would like to know whether this holds up for you.

If you want to understand it better, here is the [design](https://passbox.gabrielkoerich.com/design/) and here's the [roadmap and future ideas](https://passbox.gabrielkoerich.com/roadmap/).

Source and docs: [passbox.gabrielkoerich.com](https://passbox.gabrielkoerich.com) · [github.com/gabrielkoerich/passbox](https://github.com/gabrielkoerich/passbox)

---

**Corrections, 2026-10-06.**

- From [v0.13.12](https://github.com/gabrielkoerich/passbox/releases/tag/v0.13.12) to v0.13.42, passbox kept a plaintext list of entry names at `~/.passbox/names` so that `ls` needed no key. It never synced, but any process running as the user could read it, which broke the promise above that names live only inside the ciphertext. [v0.13.43](https://github.com/gabrielkoerich/passbox/releases/tag/v0.13.43) removed it ([72e46cd](https://github.com/gabrielkoerich/passbox/commit/72e46cd)), so listing now needs approval and is audited like a read.
- [v0.13.44](https://github.com/gabrielkoerich/passbox/releases/tag/v0.13.44) also hardened the broker: decrypted secrets are wiped from memory after use, it refuses a debugger, and a crash writes no core dump ([ff0b994](https://github.com/gabrielkoerich/passbox/commit/ff0b994)).
- The 1Password paragraph said there is no "this one secret, for this one process". `op run` does inject secrets into a single process, so I corrected it.
