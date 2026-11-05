+++
title = "Introducing shipcheck: the checks your agents already ran, now on their PRs"
date = 2026-11-05
slug = "shipcheck"
description = "shipcheck turns the tests your agents already ran into the PR's required checks. How it works, why agents can't cheat, and two weeks of real numbers."
[taxonomies]
tags = ["ci", "agents", "rust", "shipcheck", "security"]
+++

I run coding agents with [orch](https://github.com/gabrielkoerich/orch). An agent finishes a change in a few minutes, and then its PR waits while GitHub Actions runs the same tests the agent just ran. Every push uses Actions minutes, and every month, somewhere between the 10th and the 15th, I run out of free ones and start paying for each minute.

The agent already ran the tests. That run should be the check.

So I built [shipcheck](https://shipcheck.run). It runs your CI on the machine where the agent works, and the shipcheck GitHub App posts the result on the PR as its required checks. It's a single Rust binary for macOS and Linux, open source under MIT.

![An agent runs shipcheck run, commits the tree that passed, and the PR gets its required checks](https://raw.githubusercontent.com/gabrielkoerich/shipcheck/main/assets/shipcheck-agent.gif)

## How my agents work now

My agents run `shipcheck run` instead of the project's tests. shipcheck tests the working copy in a clean clone and answers with an exit code:

- `0`: it passed. The agent commits with `shipcheck commit` and pushes, and the PR gets its checks right away, because that exact tree already passed.
- `1`: it failed. The agent reads `shipcheck logs` and fixes the code.
- `2`: shipcheck couldn't run, for example because Docker is down. The agent commits and pushes with git as usual. shipcheck never blocks the agent's work.

When a pushed commit fails, its check on the PR lists the failed tests first, with their output, like [this cargo test failure](https://github.com/gabrielkoerich/shipcheck/runs/122095745495).

The agents learn this from a short block that `shipcheck init` writes into `AGENTS.md` and `CLAUDE.md`. The same rules are on one page at [shipcheck.run/SKILL.md](https://shipcheck.run/SKILL.md), and [shipcheck.run/llms.txt](https://shipcheck.run/llms.txt) links every doc.

## But what if the agent cheats?

The agent already ran the tests before it pushed, so that run should count as the PR's check. The problem is trust. An agent wants to finish its task, and the easiest way to finish is to say the tests passed. So the agent never reports a result. It can only start a run, and shipcheck runs the tests itself and reports what it saw.

The rules come from `main`, not from the PR. shipcheck reads `shipcheck.toml` and the workflows from `main`, so a PR that edits a workflow to `exit 0` or deletes a job still has to pass every job on `main`. Only the shipcheck App posts the checks, and only for runs shipcheck started. You make those checks required in [branch protection](https://shipcheck.run/docs/branch-protection/), together with the rule that a branch must be up to date with `main`. Then the tree shipcheck tested is exactly the tree that lands on `main`.

## Each tree is tested once

shipcheck keeps each result by git tree, not by commit. A rebase, an amend or a squash that leaves the files as they were gets its checks in seconds, with nothing to run. On [PR 168](https://github.com/gabrielkoerich/shipcheck/pull/168/checks) they posted 3 seconds after the push, from a run that had passed 22 minutes before.

Some changes happen on GitHub, like the Update branch button. For those, `shipcheck init` starts a daemon on your machine. With the shipcheck App installed, GitHub's webhook tells it about each push to a PR within seconds. Without the App, it checks your open PRs every 10 seconds. A new commit whose tree already passed gets its checks at once, and anything else runs the same way a push does.

## What runs where

`shipcheck init` reads your workflows and decides, job by job, how each one runs:

- As a host check: the job's commands, like `cargo test`, run natively on your machine in an OS sandbox.
- As an act job: the workflow job itself runs in Docker with [act](https://github.com/nektos/act).
- On GitHub, when neither runs the job the way GitHub does. `init` tells you why for each one.

The first version of `shipcheck init` turned every job into a host check. It worked on my repositories. Of course it did, I wrote both. On curl it wrote a proselint check that passed because it had dropped the proselint steps.

A false pass is worse than no check, so now a job runs locally only if it runs the same way as on GitHub.

To test that on code I didn't write, I ran `shipcheck init --yes` and `shipcheck run` on four public repositories and kept what `init` wrote as it was:

| Repository | PR jobs | On shipcheck | On GitHub |
|---|---|---|---|
| ripgrep, Rust | 6 | 5 | `test`, whose cross-compiled legs start their own Docker containers |
| fzf, Go | 5 | 2, the Linux build with its tmux integration tests, and typos | CodeQL and dependency review, which report to GitHub, and the macOS build, which writes into Homebrew's folders |
| faker, Ruby | 4 | 4, the whole Ruby matrix included | none |
| zod, TypeScript | 4 | 3, the Node matrix included | the Claude review bot |

Every job shipcheck ran passed. A matrix counts as one job. I kept what `init` picked by default, and two of the jobs on GitHub could run here with a little more setup: ripgrep's `test` on a colima VM, which has its own Docker and which `init` lets you pick for code you trust, and fzf's macOS build once its steps stop writing into Homebrew's folders, which the sandbox blocks.

## Two weeks on my own repositories

Since 2026-10-23, 592 PRs in seven of my repositories got their checks from shipcheck, and 564 of them merged. Most of those repositories are private. shipcheck's own records on my Mac show:

| | |
|---|---|
| Runs | 3,341 |
| Real runs | 2,080 |
| Answered from a tree already tested | 1,214 |
| Pushes answered from a tree already tested | 87% |
| Trees that failed locally and never reached GitHub | 381 |

A push whose tree already passed got its first check on GitHub a median of 4 seconds after it started. One afternoon a run took 24 minutes to pass. The rebased commit with the same tree got its checks 4 seconds after its push.

The 381 failed trees are agents breaking things on my Mac and fixing them before any PR saw them. On GitHub, each of those would have been a red run, and minutes on the bill.

For the minutes, I counted one run for each commit that got checks, with each job rounded up to a whole minute, as GitHub bills. On the private repositories that comes to about 5,600 minutes in two weeks that never ran on GitHub. It's an estimate: GitHub's runners would also spend time on setup that my local times don't count.

## Running code the agent wrote

shipcheck runs whatever the branch contains, so it treats every job as untrusted. An act job gets no Docker socket, no host token or environment, and no network unless the config on `main` turns it on. A host check runs in the OS sandbox, `sandbox-exec` on macOS and bubblewrap on Linux. It writes only to its own clone and caches, and it can't read the rest of your home or your credentials. The sandbox is its own crate, [sandbox-jail](https://crates.io/crates/sandbox-jail).

The shipcheck App can't read your code, and results and logs stay on your machine. The [security page](https://shipcheck.run/docs/security/) lists everything a job can reach.

## What it costs

- shipcheck proves the tests ran and passed, not that they're good. An agent that deletes or weakens a test still passes, so review test changes in the PR.
- act runs your workflows the way GitHub's runner does, in images that copy GitHub's, but a few things differ, such as no `GITHUB_TOKEN` in a job.
- Your workflows still run on GitHub after each merge to `main`, and use minutes there. That run catches what a local one can miss, such as a test that passes on your Mac and fails on Linux.
- No Windows jobs. macOS jobs run only as host checks on a Mac.
- A matrix that mixes Linux with macOS or Windows stays on GitHub as a whole.
- The first run on a machine is slow, since it installs toolchains and builds every dependency. On orch, a Rust crate with about 2,100 tests, a cold run took 238 s against 116 s on GitHub, and a warm run took 105 s against 115 to 124 s.

## Try it

```sh
brew install gabrielkoerich/tap/shipcheck
shipcheck init
```

Run `shipcheck init` on `main`, merge the `shipcheck.toml` it writes, and install the [shipcheck App](https://github.com/apps/shipcheck-run). Each teammate runs `shipcheck install` once per clone. The [quickstart](https://shipcheck.run/docs/quickstart/) has every step.

The docs are at [shipcheck.run](https://shipcheck.run) and the code is at [github.com/gabrielkoerich/shipcheck](https://github.com/gabrielkoerich/shipcheck). If you try it on your repository, tell me what `init` kept on GitHub and why, on X at [@gabrielmkoerich](https://x.com/gabrielmkoerich) or in an issue.
