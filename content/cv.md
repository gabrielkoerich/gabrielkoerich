+++
title = ""
description = "Senior Software Engineer with 15+ years experience"
+++

## Summary <a href="{{ asset(path="gabrielkoerich-cv.pdf") }}" class="no-print" style="float: right; font-size: 0.85em; font-weight: normal;">Download as PDF</a>

Senior software engineer with 15+ years building production systems, coding since age 13. Most of my work is backends that do many things at once: queues, background workers, retries and concurrency. 

I have written Rust since 2021 and I'm currently building Solana DeFi at Lulo. Previously founded Bulldesk, a marketing automation SaaS that ran 500M+ background jobs a month, acquired in 2021. BBA in Finance.

I also build AI tooling: I run Claude Code, Codex and OpenCode in parallel every day with [orch](https://github.com/gabrielkoerich/orch), an agent orchestrator I wrote in Rust, and help companies do the same.

<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 8px;"><rect x="2" y="4" width="20" height="16" rx="2"></rect><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"></path></svg> [gabriel@gabrielkoerich.com](mailto:gabriel@gabrielkoerich.com)  
<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 8px;"><path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4"></path><path d="M9 18c-4.51 2-5-2-7-2"></path></svg> [github.com/gabrielkoerich](https://github.com/gabrielkoerich)  
<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 8px;"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"></path><rect x="2" y="9" width="4" height="12"></rect><circle cx="4" cy="4" r="2"></circle></svg> [linkedin.com/in/gabrielkoerich](https://linkedin.com/in/gabrielkoerich) 

## Core Competencies

**Distributed Systems & Concurrency**

- Event-driven and queue-driven backends: background workers, retries, idempotency and at-least-once delivery
- 500M+ background jobs a month on Beanstalkd, Redis and SQS, on dedicated worker servers
- Async Rust with Tokio: worker pools, backpressure and keeping blocking work off the runtime

**Blockchain Engineering**

- Solana programs (Rust, Anchor) and EVM contracts (Solidity, Hardhat, Foundry), with unit, fuzz, property and integration tests
- DeFi integrations: CPI, composability, onchain and off-chain indexing

**AI & Agent Orchestration**

- Claude Code, Codex and OpenCode in daily production work, run in parallel with [orch](https://github.com/gabrielkoerich/orch)
- Agent workflows for planning, implementation, review, refactoring, docs and ops

## Technical Skills

- **Languages:** Rust, TypeScript, Python
- **Data & messaging:** PostgreSQL, MySQL (replication, tuning), SQLite, Redis, Beanstalkd, SQS, Pub/Sub
- **Infrastructure:** Docker, GitHub Actions, Terraform, Ansible, AWS, GCP, Fly.io, Datadog, Sentry
- **Frontend:** Vue.js, React, Vite

## Professional Experience

### Senior Software Engineer, Lulo  
**November 2022 – Present**   

Smart contract development for the DeFi protocol. Implemented the lending aggregator contract. Designed a security pool that protects users against protocol hacks while earning yield, and a higher-yield pool with standard DeFi risk.

- Built an indexer that receives transactions through webhooks and dispatches jobs over GCP Pub/Sub
- Architected the protocol and its CPI integrations with major Solana protocols
- Built the SDKs and CLIs, with Rust unit tests and Anchor integration tests
- EVM protocol integrations with Solidity, Forge and Hardhat

**Stack:** Rust, Solana, Anchor, TypeScript, GitHub Actions, GCP, Pub/Sub

---

### Solana Smart Contract Engineer, Freelance  
**October 2021 – November 2022** 

Moved to Rust as my primary language and shipped three Solana projects:

- NFT marketplace with custom auction mechanisms
- Price prediction game with an onchain oracle
- DeFi contract using Orca Whirlpools for liquidity

Each shipped with tests, TypeScript/Rust SDKs and CLI tooling.

**Stack:** Rust, Solana, Anchor, TypeScript, GitHub Actions

---

### Senior Software Engineer, Covie  
**May 2021 – October 2021** 

Built scrapers and browser automation that collected policy and claims data from insurance company portals at high volume.

**Stack:** Symfony, Node, PostgreSQL

---

### Founder, Bulldesk  
**September 2015 – May 2021** 

Founded and scaled the first Brazilian platform to combine marketing automation and CRM. Acquired in 2021.

- Designed an event-driven backend around queues: the automation engine, campaigns and email all ran on background workers
- 80M+ requests and 500M+ background jobs per month
- Automation engine processing 1M+ leads with 5 to 10 concurrent actions each
- Load-balanced app servers and dedicated worker servers, MySQL replication, Beanstalkd, Redis and SQS queues, real-time updates over WebSockets
- Led a team of 4 developers and ran infrastructure and DevOps, plus product, business and finance

**Stack:** Laravel, Node, MySQL, Beanstalkd, Redis, SQS, Vue.js, Stripe, AWS

## Education

- **BBA Finance**: Universidade do Sul de Santa Catarina
- **English Language Studies**: LSI (London)

**Languages:** Portuguese (native), English (fluent)

## Notable Projects

- **[orch](https://github.com/gabrielkoerich/orch)** (Rust, Tokio): background service that hands issues to coding agents in separate worktrees and opens the pull requests
- **[passbox](https://github.com/gabrielkoerich/passbox)** (Rust, Swift): password manager for AI agents, a fingerprint releases one secret into one process
- **[skills](https://github.com/gabrielkoerich/skills)**: skills for AI agents, including Solana and EVM security audits
- **[writing articles](https://gabrielkoerich.com/posts/)** about Rust, concurrency, queues, Solana and AI agents
