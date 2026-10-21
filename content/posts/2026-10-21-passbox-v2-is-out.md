+++
title = "Passbox v2 is out!"
date = 2026-10-21
description = "passbox v2 opens approval windows for read-only plugin tools, drops every tool that acts for the caller, and removes get --reveal. What changed since 0.13."
[taxonomies]
tags = ["ai", "agents", "security", "rust", "secrets-management", "touch-id", "ssh", "tailscale", "macos"]
+++

[passbox](https://passbox.gabrielkoerich.com) [v2](https://github.com/gabrielkoerich/passbox/releases/tag/v2.0.1) shipped on October 20, with some fixes today, three weeks after I wrote [the first post](@/posts/2026-09-29-a-password-manager-for-agents.md) about it. That post was about version 0.13. Since then there have been many releases, and most of them added something: an [SSH agent](https://passbox.gabrielkoerich.com/use/#ssh-keys), an [Alfred workflow](https://passbox.gabrielkoerich.com/use/#alfred), [plugins](https://passbox.gabrielkoerich.com/plugins/) that read my mail and my todos. v2 is the release where I took things out, and it started with [Things 3](https://culturedcode.com/things/).

## A prompt for every todo

Some of my scheduled jobs read Things 3 on my Mac through the passbox plugin: what I finished, what is coming up, what is in the logbook. Every plugin call raised a [Touch ID](https://support.apple.com/en-us/102528) prompt, and a job reads Things several times per run. The secrets in the same jobs were fine, because one [`passbox grant ... --for 86400`](https://passbox.gabrielkoerich.com/unattended/#a-grant-for-what-cannot-be-injected) a day covers all of them. So I tried the same thing on a plugin tool:

```
$ passbox grant plugin:things3.logbook --for 600
passbox: no secret named plugin:things3.logbook
```

The broker's `handle_plugin` asked for a fingerprint on every request and never looked at a token ([#47](https://github.com/gabrielkoerich/passbox/issues/47)). So a job either waited for my finger or failed.

The obvious fix was to let a grant name a plugin tool, and I didn't do it. A grant is minted by the caller and travels as a bearer token, so whoever holds the token holds the policy, and anyone it leaks to can use it.

## Windows came back, for plugins only

In [the first post](@/posts/2026-09-29-a-password-manager-for-agents.md) I said my first version had a five-minute approval window and that I moved away from it. [v1](https://github.com/gabrielkoerich/passbox/releases/tag/v1.0.0) went further and made every read prompt unless a grant covers it. So bringing windows back in v2 needed a better reason than "the prompts are annoying".

The reason is the design: the policy belongs to the `owner` and not to the `caller`. I set a [window](https://github.com/gabrielkoerich/passbox/blob/main/docs/content/design.md#plugin-windows) myself, in a file on the Mac, and the caller can only ask for one:

```toml
# ~/.passbox/config.toml
[plugins.windows]
"things3.logbook" = "24h"
"things3.upcoming" = "24h"
"imap.search" = "1h"
```

After one approved call, later calls of that tool from the same caller skip the prompt until the window ends, and each one is audited as `by window`. A key names exactly one plugin and one tool. `things3`, `*` and `things3.*` are refused when the file loads, so a window never covers a tool added later. Every window is capped at 24 hours, the same ceiling as a grant.

"The same caller" needed a definition the broker can check. A tailnet client is named by [`tailscale whois`](https://tailscale.com/kb/1080/cli#whois), so a window opened from one host does not cover another. Everything on the Mac is one scope, because a local agent name is whatever the agent says it is.

The hard part is that `config.toml` is plain text, and any process running as me can edit it, an agent included. So the broker hashes the section together with each named tool's command, and a window applies only while that hash is the one I approved. An edit makes the next plugin call prompt once with the new list:

```
allow plugin windows imap.search 1h, things3.logbook 24h,
things3.upcoming 24h for claude,
then run plugin:things3.logbook for claude
```

Approving it ends the windows opened under the old section. Refusing keeps the old approval, and its windows apply again once I put the old section back. The approved hash lives in `windows-<host>.json` with a MAC under the store key, so a record written by anything else opens nothing. Secrets still have no windows at all.

A window also covers only the exact arguments of the call that opened it. My first version did not, and I found and fixed it while writing this post: one approved `imap.search` allowed any search, in any mailbox, for the whole window, and the prompt never showed the query ([#54](https://github.com/gabrielkoerich/passbox/issues/54)). Now the prompt shows the arguments, and an approved search is valid only for the query I saw in it. A new query or message id prompts again, and the audit record keeps the arguments. A job that repeats `things3.logbook` keeps its window, and one that searches for something new asks me first. The broker can only hold a call to its arguments when it runs the command itself, which it does for `imap` and for every call from another machine. A local `things3` call runs in the caller's own process, and anything on my Mac can run `things` directly anyway.

## Asking the Mac from a Linux box

[The first post](@/posts/2026-09-29-a-password-manager-for-agents.md) tested a [remote client](https://passbox.gabrielkoerich.com/another-machine/) from a [Raspberry Pi](https://www.raspberrypi.com/). Now it is how my jobs run. [orch](@/posts/2026-07-05-orchestrating-agents-for-humans.md), my orchestrator for coding agents, runs them on a Linux box, and that box has no store and no key. Its passbox client is the [release binary](https://github.com/gabrielkoerich/passbox/releases), pinned with its SHA-256, and its whole configuration is one line in `~/.passbox/host` with the Mac's tailnet name. Every read goes over [Tailscale](https://tailscale.com/) to the broker on the Mac, and the fingerprint stays on the Mac:

```bash
# on the Linux box
passbox exec --env API_TOKEN=example/token -- ./daily-report
passbox plugin things3 logbook
passbox plugin imap search --query invoice
```

On the Mac each of those raises a prompt. This one is a Things read from the Linux box, with its host name and tailnet address hidden:

<a href="/images/posts/passbox-v2-remote-prompt.png"><img src="/images/posts/passbox-v2-remote-prompt.png" alt="Touch ID prompt on the Mac for plugin:things3.upcoming, asked by passbox on the Linux box" width="280" style="display:block;margin:2rem auto"></a>

The agent part of the prompt is whatever the job sets in `PASSBOX_AGENT`, and this one set nothing.

Secrets and app reads are approved in different ways. A job's secrets come from one `passbox grant` a day, so the box costs me one fingerprint a day for all of them. The app reads are covered by windows. My Mac's `config.toml` lists every read-only tool at `24h`, so each tool prompts the first time a job calls it that day. When I tested it from the Linux box on October 21, the first `things3` call prompted and the calls after it came back in 0.2 seconds with no prompt.

The `imap` plugin shows why the broker runs a plugin that needs a secret itself. My IMAP account is in the store on the Mac, so a job on the Linux box asks for `imap search` and gets back only the mail, while the password stays on the Mac.

## passbox gives, it never acts

Writing the windows forced a question I had skipped: which tools may have one? A 24 hour window on `mail.send` lets anything on my Mac send mail as me for a day with no fingerprint. A prompt on every call is not much better, because I would be approving mail I had not read.

So v2 has a defined rule, written in the [design doc](https://passbox.gabrielkoerich.com/design/): passbox gives what it was asked for, a secret or data, and never acts for the caller. These are all gone:

| Removed | Use instead |
|---|---|
| `things3.add` | your own client under `passbox exec` |
| `mail.send` | your SMTP client, with `passbox exec --env SMTP_PASSWORD=mail/smtp` |
| `mail.attachments`, which wrote files | `imap.attachments`, which returns JSON |
| the `git` plugin | the SSH agent, which prompts for every signature |
| the `gh` plugin | `passbox exec --env GH_TOKEN=github/token -- gh pr create` |

The `git` and `gh` plugins I should have caught earlier. An agent runs git and gh directly, so a plugin for them gated nothing. It was a locked door with no walls, which is 100% effective if you follow the rules.

The `imap` plugin from [1.14](https://github.com/gabrielkoerich/passbox/releases/tag/v1.14.0) is the shape I want for the rest. The broker writes the password to the script's stdin, so it is never an argument, an environment variable or a file. Before the prompt, the broker compares the installed plugin byte for byte with the copy compiled into the binary, and it runs the bundled bytes, so an agent that edits `imap.py` to print the password gets a refusal instead. Then it scrubs the password out of the output anyway. The one thing I want to change is that it only reads one entry, `mail/imap`. I want to name several accounts in `config.toml`, so a job can pick which one to read ([#55](https://github.com/gabrielkoerich/passbox/issues/55)).

## The flag that explained how to get past it

[1.1.0](https://github.com/gabrielkoerich/passbox/releases/tag/v1.1.0) made `passbox get` refuse when stdout is not a terminal, because a pipe is where a value ends up in an agent's context. The clipboard case moved to `passbox copy`, which keeps the value on the clipboard for 20 seconds, clears it, and marks it so clipboard managers never save it to their history. The [Alfred workflow](https://github.com/gabrielkoerich/passbox/tree/main/integrations/alfred) copies through the same command. (And yes, I still use Alfred.)

The refusal had an override, `--reveal`, and the refusal message named it. So anything that hit the refusal, an agent included, learned the way past it in the same message, so the check only stopped the honest mistake. Really? Yes. I wrote that error message.

So v2 removes `--reveal` ([#19](https://github.com/gabrielkoerich/passbox/issues/19)). The Rust library in the [`passbox` crate](https://crates.io/crates/passbox) was built on it, so it went too, and the crate is now the CLI only. A program runs under `passbox exec --env` and reads `std::env::var` with no dependency. The Python and TypeScript helpers kept only the parts built on `exec`.

But nothing is 100% safe. `passbox exec --env V=name -- printenv V` prints the value, because `exec` hands it to a child and the child can print it. What v2 removed is the one command passbox itself offered that prints a secret into a pipe.

## What 1.x added on the way

passbox has replaced [`pass`](https://www.passwordstore.org/) for me completely. In [the first post](@/posts/2026-09-29-a-password-manager-for-agents.md) I kept [1Password](https://1password.com/), on my Mac only, for SSH and the passwords I keep out of the macOS Keychain, and on October 16 I decided passbox should replace that too. Most of the later 1.x releases came from that decision. It is almost there, and I still open 1Password for secure notes and a few other things.

| Release | Date | What it added |
|---|---|---|
| [0.14](https://github.com/gabrielkoerich/passbox/releases/tag/v0.14.0), [0.15](https://github.com/gabrielkoerich/passbox/releases/tag/v0.15.0) | Oct 7 to 9 | plugins, and plugins from a tailnet client |
| [1.0.0](https://github.com/gabrielkoerich/passbox/releases/tag/v1.0.0) | Oct 12 | every read prompts unless a grant covers it |
| [1.1.0](https://github.com/gabrielkoerich/passbox/releases/tag/v1.1.0) | Oct 13 | `passbox copy`, and `get` only to a terminal |
| [1.2.0](https://github.com/gabrielkoerich/passbox/releases/tag/v1.2.0) | Oct 14 | an Alfred workflow that copies a secret with `passbox copy`, attached to every release |
| [1.3.0](https://github.com/gabrielkoerich/passbox/releases/tag/v1.3.0) | Oct 14 | iCloud sync to a hidden `.passbox` folder |
| [1.4.0](https://github.com/gabrielkoerich/passbox/releases/tag/v1.4.0) | Oct 15 | every write pushes when the store repo has a remote |
| [1.6.0](https://github.com/gabrielkoerich/passbox/releases/tag/v1.6.0) | Oct 16 | the sync destination in `~/.passbox/config.toml` |
| [1.7.0](https://github.com/gabrielkoerich/passbox/releases/tag/v1.7.0) | Oct 19 | an SSH agent, signing with keys in the store |
| [1.8.0](https://github.com/gabrielkoerich/passbox/releases/tag/v1.8.0) | Oct 20 | the tailnet host named in the Touch ID prompt |
| [1.9.0](https://github.com/gabrielkoerich/passbox/releases/tag/v1.9.0) | Oct 20 | child tokens, `--token-stdin`, a `delegated` audit record |
| [1.11.0](https://github.com/gabrielkoerich/passbox/releases/tag/v1.11.0) | Oct 20 | a backup [YubiKey](https://www.yubico.com/) with a bare `passbox yubikey-add` |
| [1.14.0](https://github.com/gabrielkoerich/passbox/releases/tag/v1.14.0) | Oct 20 | the `imap` plugin |

Yes, the last four rows and v2 all came out on October 20. It was a long day.

The SSH agent is the biggest of them. The broker serves the [ssh-agent protocol](https://datatracker.ietf.org/doc/html/draft-miller-ssh-agent) on a second socket, signs with Ed25519 or P-256 keys from the store, and the private key never leaves the broker:

```bash
passbox add ssh/github < ~/.ssh/id_ed25519
export SSH_AUTH_SOCK=~/.passbox/ssh-agent.sock
ssh-add -L            # lists it, no prompt
ssh -T git@github.com # Touch ID
```

The prompt reads what is being signed out of the data itself, an SSH login and its user, or an [`SSHSIG`](https://github.com/openssh/openssh-portable/blob/master/PROTOCOL.sshsig) namespace such as git for a signed commit. I tested it on October 21 with a throwaway key. A git commit signed through the agent raised this prompt, and `git verify-commit` accepted the signature:

<a href="/images/posts/passbox-v2-ssh-prompt.png"><img src="/images/posts/passbox-v2-ssh-prompt.png" alt="Touch ID prompt on the Mac to sign a git signature with the SSH key passbox-blog-test for ssh-keygen" width="280" style="display:block;margin:2rem auto"></a>

I had to change the broker's lifecycle. The broker used to exit after 300 seconds idle, which was how it dropped the key from memory. An SSH agent cannot do that, because `SSH_AUTH_SOCK` has to reach a live socket or every `ssh` and `git` call fails. Now it drops the key in place and keeps running, and it relies on the allocator that wipes every freed block, where exiting used to hand the memory back to the kernel.

[Child tokens](https://passbox.gabrielkoerich.com/unattended/#a-supervisor-that-starts-its-own-workers) ([#22](https://github.com/gabrielkoerich/passbox/issues/22)) came from my [trading daemon](@/posts/2026-10-05-running-a-quant-book-on-hyperliquid.md). It runs in a container that starts worker containers, and I want one fingerprint a day for all of it. Before 1.9.0 the supervisor minted one 24 hour grant and gave the same token to every worker on stdin, so every worker held a token for every worker's secrets. Now the supervisor mints a child per worker with no prompt, for that worker's names only. Minting one is audited as `delegated`, and every read through a child carries the id of the grant behind it, so it traces back to the one fingerprint.

## What broke between v1 and v2

The first was that 300 second idle exit. It also ended every grant, because grants live in broker memory. A job holding a valid 24 hour token went back to a prompt per read the next time the broker had been quiet for five minutes. [1.1.1](https://github.com/gabrielkoerich/passbox/commit/faeedb0) kept the broker up while a token lives, and [1.7.0](https://github.com/gabrielkoerich/passbox/releases/tag/v1.7.0) stopped the exit altogether.

A prompt nobody answered blocked everything. The unix socket served one connection at a time, every request ran inside one lock, and the prompt ran inside it too. A grant renewal raised at night sat on the screen until morning, and every worker that started in the meantime held a valid token and still could not read. [1.1.2](https://github.com/gabrielkoerich/passbox/issues/23) gave each connection its own thread, gave token reads their own lock, and kept one prompt on screen at a time.

A Linux client could not ask for many secrets at once. `passbox exec` with 14 `--env` flags from a client raised 14 prompts for one process start, and `passbox grant` failed before it reached the broker. [1.0.3](https://github.com/gabrielkoerich/passbox/issues/13) fixed both.

The prompt named the wrong thing. From a Linux client, `timeout 60 passbox plugin things3 today` raised "passbox is trying to run plugin:things3.today for timeout." `timeout` was the parent process, and nothing told me which machine asked. [1.8.0](https://github.com/gabrielkoerich/passbox/issues/37) turns on the [PROXY protocol](https://www.haproxy.org/download/1.8/doc/proxy-protocol.txt) in [`tailscale serve`](https://tailscale.com/kb/1242/tailscale-serve), so the broker sees the client's tailnet address and asks `tailscale whois` for its name. The prompt now says something like `claude on server (someone@example.com, 100.61.0.7)`, with the host name from Tailscale's control plane.

[Alfred](https://www.alfredapp.com/) closed itself. The workflow listed names inside its [Script Filter](https://www.alfredapp.com/help/workflows/inputs/script-filter/), the listing raised Touch ID, Touch ID took focus, and Alfred hides when it loses focus. The box closed before any name arrived. [1.6.1](https://github.com/gabrielkoerich/passbox/pull/29) lists first with Alfred closed and then reopens it with the names. Now you open Alfred, type `pbx`, which runs `passbox ls`, and touch the sensor. Alfred reopens with your secret names, and you search and press enter to copy one. It stays on the clipboard for 20 seconds and never lands in clipboard history.

And one I found and fixed while writing this post: v2 shipped still reading the old one-line `~/.passbox/remote` sync file, with a warning that said it "stops being read in v2". The warning now says v3 ([#51](https://github.com/gabrielkoerich/passbox/issues/51)).

## Upgrading

```bash
brew upgrade passbox
passbox plugin list     # flags plugins older than the bundled copy
passbox plugin update things3
```

v2 breaks anything that used `get --reveal`, the Rust library, `get` in the Python helper, `config()` in the TypeScript one, or the plugin tools in the table above. If a Linux box asks your Mac over Tailscale, the forward needs `--proxy-protocol 1` since 1.8.0, and the broker refuses connections without it:

```bash
tailscale serve --bg --proxy-protocol 1 --tcp 8787 tcp://127.0.0.1:8787
```

## The tradeoffs

**One window covers every local caller.** A window opened by one job on the Mac covers every other process on the Mac for that tool, because the broker cannot tell local callers apart in a way it can trust.

**A windowed `imap` holds its password longer.** The password still never leaves the broker, but during a window the broker keeps it in memory, as it does for a token, instead of reading it from the store on each call. A rotated IMAP password is seen only after the window ends.

**A job with changing queries prompts every time.** A window covers one set of arguments, so a job that searches for something new each run needs my finger each run.

**A restart still ends everything.** Grants and windows live in broker memory, so a `brew upgrade` costs a fingerprint for every job that held one. Only the approved window hash survives on disk.

**The Linux box is only as awake as the Mac.** Every prompt shows on the Mac, so a closed lid or a sleeping Mac stops any job that needs a new one.

**A local user can lie about the host.** Someone who connects to the loopback port directly can write a PROXY header naming another tailnet host. It does not get past the prompt, but the prompt can then name the wrong machine. So the Mac that runs the broker should have no other users. The network side is Tailscale's job: `tailscale serve` exposes the broker only to devices on my tailnet, never to the internet, and an [ACL](https://tailscale.com/kb/1018/acls) can limit it to the machines that run jobs.

**It is still young.** It is three weeks old and I am the only maintainer.

Keeping grants across a broker restart is the open problem, [#24](https://github.com/gabrielkoerich/passbox/issues/24). Every upgrade today means re-granting every job. The proposal there writes each grant to disk, encrypted with a key derived from its token. The catch is that someone holding both the token and the file can decrypt it without the broker, and that read leaves no audit record. I have not decided if that is even worth it.

Source, updated docs and the [v2 release](https://github.com/gabrielkoerich/passbox/releases/tag/v2.0.1): [passbox.gabrielkoerich.com](https://passbox.gabrielkoerich.com) · [github.com/gabrielkoerich/passbox](https://github.com/gabrielkoerich/passbox)
