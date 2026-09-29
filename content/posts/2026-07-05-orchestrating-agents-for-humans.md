+++
title = "Orchestrating agents for humans"
date = 2026-07-05
[taxonomies]
tags = ["ai", "rust", "agents"]
+++

In February I was running Claude Code, Codex and OpenCode side by side in a grid of terminal tabs. Each one needed me to paste the issue, point it at the right branch, wait, read the diff, push, open the PR, and then remember which tab was doing what. The agents were fast. I was the slow part, and I was mostly doing clerical work.

I also wanted to test every model on real work. A new one ships every few weeks, each vendor is best at something different, and any of them can change its price, its limits or its terms tomorrow. I did not want to be tied to one of them. That is why orch does not care which agent runs a task: Claude, Codex, OpenCode, Kimi, MiniMax and GLM all go through the same pipeline, and switching models or dropping an agent is a config change.

So I wrote [orch](https://github.com/gabrielkoerich/orch). It is a service that runs on my Mac, reads GitHub issues, picks an agent and a model for each one, runs the agent in its own git worktree, opens the PR, has a different agent review it, and merges it when CI passes. Since March it has closed almost 5,000 tasks across about 12,500 agent runs, split between Claude, OpenCode, Codex, MiniMax, Kimi and GLM.

Agents are tools. Orch is how one person uses many of them at once and still decides what ships. It takes a project from an issue to a merged PR without me, and it runs scheduled jobs with the right context for each one. Most days it feels like magic. This post is about the parts that are not magic: the design, and the bugs it took to get there.

## The problems

**I was the scheduler.** Every agent waited on me to give it work, and every finished agent waited on me to ship it. Three agents in parallel meant three times the context switching.

**Agents share one checkout badly.** Two agents in the same directory overwrite each other's files, fight over the branch, and leave a state that neither of them understands.

**Every vendor fails differently.** One rate limits with a "try again at" timestamp. One runs out of credits. One renames a model and returns "model not found". One goes silent and never exits. A single agent setup breaks on all of these.

**Recurring work needs context.** A nightly job that says "check the ledger" is useless unless the agent knows what the ledger is, what the rules of the repo are, and what went wrong last night.

## Why Rust

The [first version](https://github.com/gabrielkoerich/orchestrator-sh) was almost all bash, with a few small Python helpers for prompt templates, JSON parsing and cron matching. It worked for one project and a few tasks a day. Then it started to show its limits: every task started a Python process eight or more times just to render prompts, the scripts read the YAML config from disk on every call, and two ticks could dispatch the same task twice. In late February I rewrote it in Rust.

**One binary.** Homebrew installs it and launchd runs it. There is no Python, `yq` or script directory that has to be on the right path when the service starts at boot.

**One process for many slow things.** The tick loop, GitHub polling, tmux output capture every two seconds, the Discord websocket and the Telegram bot all run on Tokio in one process. Most of what orch does is wait on something, and async Rust is good at waiting.

**The compiler catches mistakes early.** A task status is an enum, so a new status breaks every `match` that forgot it. CI runs clippy with warnings as errors. Many bugs fail the build before anyone reviews the diff.

The cost is that a change goes through a compile and a release before the service runs it. With a script I could edit a line and see the result on the next tick.

## The design

**GitHub issues are the source of truth.** A task is an issue, and its status is a label: `new`, `routed`, `in_progress`, `needs_review`, `in_review`, `done`, `blocked`. I can see and change the state of everything from my phone. Work that does not deserve an issue, like a scheduled report, is an internal task in SQLite and goes through the same pipeline.

**One worktree per task.** Each task gets a branch and a worktree under `~/.orch/worktrees/<project>/<branch>/`. The agent never touches my checkout. A tool-level sandbox blocks reads and writes to the main project directory.

**tmux is the runtime.** Every agent runs in its own tmux session. I can attach to any of them, `orch stream` shows all of them live, and the same output goes to Telegram and Discord. If the service restarts, running tasks go back to `routed` and resume in their existing worktree.

**The router picks a complexity.** An LLM call classifies each task as simple, medium or complex. A table in the config maps each level to a model per agent, so `complex` means Opus on Claude and the strongest Codex model on Codex. Labels like `agent:codex` or `complexity:simple` override it. Changing models is a config edit. A model list can also hold `opencode:free`, which orch expands at startup to every free model that `opencode models` returns. So far 1,785 runs have used 13 different free models, about one run in seven, at no cost.

**A different agent reviews.** When a PR is open, orch picks a reviewer that is not the agent that wrote the code and not one that already reviewed this task. The reviewer reads the diff and returns approve, request changes, or reject. Changes go back to the same agent, in the same worktree, on the same PR. After two review cycles the task blocks and waits for me.

**Context is built for every run.** Before an agent starts, orch assembles its prompt from the issue and its comments, the repo's `CLAUDE.md`, `AGENTS.md` and `README.md`, the file tree, the parent task if there is one, any review feedback, selected skills, and a memory of the last three attempts: what each agent tried, what it learned, and what failed. A retry starts where the last one stopped.

**Jobs are cron plus that context.** A project defines jobs in `.orch.yml` or as markdown files with a schedule in the frontmatter. A job either runs a shell command or creates a task, and the task gets the full context above. A job does not start again while its last task is still running. This is what runs my finance ledger: statements download, import, get categorized and reconciled on a schedule, and an agent with the repo's rules handles whatever does not fit.

## The issues, and how we solved them

**Agents analyzed instead of shipping.** At one point more than sixteen tasks closed with no PR. The agents read the code, wrote a good summary, and committed nothing. A plugin was injecting a session hook that told them to plan with skills before anything else, and they did, every time. I removed the plugin and changed the runner: an issue that finishes with no code goes back to the router with a different agent. Internal tasks like reports can still finish without a PR.

**A model name in the router.** A provider renamed a model, dispatch failed, and an agent fixed it by adding a table that rewrote the old name to the new one. Then another agent added a second name. Both PRs were reverted. The rule now is that the routing code contains no model names at all. When a model fails with "not found", that one model goes into a long cooldown and the router picks the next one. Lists rot the next time a vendor renames something. The cooldown does not need to know any names.

**A timer next to the cooldowns.** When every agent was cooled, an agent added a per-task "retry after" timestamp so routing would stop logging errors. The timestamp was half the remaining cooldown, and some cooldowns last days. When the agents recovered, nine tasks were still stuck behind their own timers while `orch cooldown list` said there were no cooldowns at all. I removed it. Now the cooldown table is the only answer to "is this agent available", and routing simply tries again on the next tick, ten seconds later. The error log is loud on purpose.

**Blocking a whole repo for one bad merge.** More velocity means more code getting done, and every PR runs CI. One of my private projects shows how much: with orch working on it, CI ran almost all day.

Orch itself is public, so its Actions minutes are free. A private repo pays for them, and without a spending limit the bill gets out of control. The other option is to run your own runner. My GitHub Pro plan includes 3,000 Actions minutes a month, and I had a $10 spending limit on top of that. That one project used both in a week, and CI stopped until the next cycle.

An agent saw the billing error and made orch skip every new task for that repo for 24 hours. No agent wrote code and no reviewer reviewed for a full day, for a failure that only matters at merge time. And this was wrong.

Now the billing error blocks only the task that tried to merge. Everything else keeps going: agents write code, reviewers review, and the PRs wait. When the new cycle starts, I unblock them and they merge.

**Cooldowns that were all different.** Rate limits, empty credits, disabled orgs, exhausted billing cycles and silent hangs each had their own special case. They are now one mechanism: exponential backoff, `min(base * 3^(n-1), max)`, persisted in SQLite so a restart does not forget it, and reset on the next success. A vendor's own "try again at" always wins. Silence detection catches the agents that hang without an error.

**Token budgets on flat plans.** Orch used to track tokens per task and warn when a task went over. Every agent I use is on a subscription, so the numbers meant nothing and the bookkeeping broke often. A migration dropped the columns. Hung agents, slow calls and runaway retries already have timeouts, a watchdog and attempt limits.

**An edited migration.** An agent changed an existing SQL migration instead of adding a new one. SQLx checks a hash of every applied migration, so the service failed on startup for over an hour. Migrations are now immutable, and a test runs them twice on a fresh database.

**A PTY that did not need to exist.** The first runner spawned agents in a pseudo terminal and forwarded output into tmux with `send-keys`. It broke in ways that were hard to see. tmux already gives every session a terminal, so I deleted about 700 lines and ran the agent directly in the session.

**Agents changing the service that runs them.** Agents edited the live config, ran `brew upgrade` on my machine, and filed issues saying the installed version was behind main. Each one was trying to help. Now the config, Homebrew and upgrades belong to me, and the agent explains a needed change in the PR instead.

Most of these fixes are also a paragraph in the repo's `AGENTS.md`, under a section called "DO NOT TOUCH". It lists each settled decision, the PR or issue that broke it, and why it was reverted. Every agent reads that file before it starts, and the reviewer reads it before it approves. It is the most useful file in the repo, and every entry in it is a mistake an agent made at least once.

## What it costs

**It runs on one machine.** Orch is a local service with no public endpoint. Webhooks do not reach it, so it polls GitHub every 45 seconds. When the Mac sleeps, nothing runs.

**Agents still need supervision.** Most fixes in the list above came from an agent solving the wrong problem well. Orch makes agents cheap to run. Their judgement does not improve with it. The review agent catches a lot, and I still read what merges into anything that matters.

**Subscriptions run out.** With six vendors, some agent is always cooled. That is fine when the pool is large, and it means slow days when two vendors hit their limits at once.

**It has a lot of moving parts.** A router, a reviewer, a scheduler, cooldowns and three chat channels. Most of the bugs now are in the space between those parts.

## Why bother

Because that was the moment I saw that the world changed, or at least the part of it that involves my work. I still write code, decide the architecture and design the systems. What changed is everything around that: I write the issues, read the reviews and decide what merges, and the clerical part runs on its own, at night included.

Orch now fixes and builds itself. A daily job reads its own database, writes a review of the last 24 hours, and files issues for what broke. Those issues go through the same pipeline as any other: an agent picks one up, another agent reviews the PR, and it merges. Feature work goes the same way. I write the issue and orch implements it. Every PR merged into orch in the last two weeks came from orch.

It does the same for every other project I run. The finance ledger and the next thing I start get the same loop: issues in, reviewed PRs out, and scheduled jobs that keep each project running.

## Next: worktrees that share their files

Every task gets a full git worktree. Git shares the history between worktrees, but every file is written to disk again, and every build installs its own dependencies. With many agents on one large repo, most of the disk and most of the setup time go to copies of the same files.

The plan is APFS clones. APFS, the filesystem on every Mac, can clone a file with `clonefile`, the call behind `cp -c`. A clone shares disk blocks with its source until one side writes, and then only the changed blocks are copied. A clone of a whole checkout takes almost no space and about a second to create, and each agent can still write anything. Orch would keep one ready checkout per project, with dependencies installed, and clone it for each task. Tools like [git-cow](https://github.com/onnimonni/git-cow) already do this.

This feature will be built the same way as everything else in orch. It starts as an issue. Orch picks it up, a different agent reviews it, and I decide if it merges.

## And what about the future?

I am also thinking about a GUI. Today I follow orch through the CLI, tmux, Telegram and the GitHub issues. One window with every project, task, agent session and cooldown would make it easier to see what is happening and to step in when something needs me.

There is more to come, so keep watching. And if you run coding agents on your own projects, try orch and tell me what breaks.

If you want to learn more and get involved, here are the [docs](https://orch.gabrielkoerich.com/), with daily updates created automatically by orch itself, [like this one](https://orch.gabrielkoerich.com/posts/daily-review-2026-07-05/), and the [source](https://github.com/gabrielkoerich/orch).
