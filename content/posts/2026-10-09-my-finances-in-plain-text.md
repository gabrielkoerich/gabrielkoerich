+++
title = "My finances in plain text"
date = 2026-10-09
[taxonomies]
tags = ["beancount", "finance", "ai", "python"]
+++

Since 2022 every real I spend goes into a text file. Bank accounts, credit cards, investments and my consulting company across many Brazilian banks, plus DeFi positions. About 13,400 transactions so far, and most of them I never typed.

The file is a [Beancount](https://beancount.github.io) ledger. The part that took years is everything around it: getting the statements, turning them into transactions, putting each one in the right account, and doing that every day without me.

Today about 95% of it runs on its own. My part is small: a few statements only exist behind a bank login, so I download those and email them to myself, and now and then I fix a category the system got wrong. Downloading, importing, categorizing, checking balances, removing duplicates and archiving all happen without me.

## Why plain text

I tried the usual options first.

**Finance apps** are nice for a few months. Then they change the pricing, drop a bank, or shut down, and the history goes with them. You also cannot ask them a question they did not plan for.

**A spreadsheet** holds everything and checks nothing. A typo in a formula moves money between categories and nobody notices for a year.

**Open Finance aggregators** exist in Brazil, but they are built for companies, they do not cover all my accounts, and they put a third party between me and my bank data.

Beancount is double entry accounting in a text file. Every transaction has to balance, and I can assert that an account holds an exact amount on a given day. If the numbers do not match the bank, `bean-check` fails. It lives in git, so every change has a diff. And because it is text, I can query it with SQL, read it with [Fava](https://beancount.github.io/fava/), and hand it to an agent.

The catch is that Beancount gives you the format and nothing else. Brazilian banks do not give individuals an API. They give you a PDF by email.

## Getting the statements

Every account has an entry in a config file that says where its statements come from:

```yaml
bank_a_credit_card:
  download_method: email      # Proton Bridge over IMAP
bank_b_credit_card:
  download_method: mail_app   # AppleScript against Mail.app
defi:
  download_method: api        # on-chain events
```

Most banks send the monthly bill to my email, so the downloader searches the mailbox, grabs the attachment, and drops it in a folder per bank. Some accounts arrive through Proton Bridge, others through Mail.app because they go to a different address. DeFi has no statement at all, so that importer reads the contract events straight from the chain.

A few statements never reach my inbox. They only exist behind a bank login with 2FA. For those I download the file and email it to myself with a fixed subject. From there the pipeline treats it like any other bill. This is the main manual step left, a few minutes a month, and I stopped fighting it.

## The importers

An importer reads one kind of file and returns Beancount entries. I wrote fourteen of them on top of [beangulp](https://github.com/beancount/beangulp): PDF credit card bills, bank statements as PDF, spreadsheet and CSV, brokerage notes, my company's invoices and DeFi events.

Each importer has a test with a real statement next to it and the expected output in a `.beancount` file. When a bank changes its PDF layout, the test fails before the ledger gets wrong numbers.

None of these rules were new to me. I have worked with credit cards and finance for years, and I used to reconcile these statements by hand. The work was turning what I already knew into code:

**Credit card dates are not transaction dates.** A bill closes on some day of the month, and the balance on the bill only makes sense after that day. So the importer reads the close date from the PDF, moves older purchases to the day after it, and writes the balance assertion two days after close. Beancount checks balances at the start of the day, so that order matters.

**Installments repeat across bills.** "Amazon (5/10)" shows up ten months in a row. The importer tags them `#recurring` so I can see how much of next month is already spent.

**One bank sends image PDFs.** There is no text to extract, so that importer renders each page at 300 DPI and runs Tesseract in Portuguese. Tesseract reads the "C" for credit as "€" often enough that the code replaces it.

**The importer owns the balance assertion.** Every statement ends with the balance the bank says I have. The importer writes that as a `balance` directive, so the moment I import, Beancount tells me if something is missing. I never let it add `pad` directives on its own. A pad hides a difference, and the difference is the thing I want to see.

## Categorization

A transaction from a bill says "PG *LOJA CENTRO 03/06" and nothing else. Someone has to decide that it is household shopping.

The first pass is rules. A categorizer wraps every importer and matches the payee against a list of regular expressions, one list per account:

```python
"Expenses:Shopping:Household": [
    "^(Mercado Livre|Leroy|Amazon|Havan|...)",
],
"Income:Cashback": [
    "^(Cashback|Benefício do cartão)",
],
```

Today that is 65 accounts and around a thousand merchant patterns, collected one annoying transaction at a time. Specific rules go first, so a broad pattern does not catch a merchant that belongs somewhere else. A category that starts with `!` flags the transaction for review instead of trusting the match.

What the rules miss goes to [smart_importer](https://github.com/beancount/smart_importer), which trains on my own history and guesses the payee and the account. It is right most of the time on merchants it has seen before and useless on new ones, which is why the rules come first.

When both get it wrong, I fix the category by hand. That is the other thing I still do. It happens a few times a month, mostly with a new merchant, and the fix often becomes a new pattern so the same merchant does not come back.

## Duplicates

This took longer than everything else.

The same money shows up in more than one place. A PIX between two of my banks appears in both statements. A bill gets downloaded twice. beangulp has a flag that compares new entries with the ledger and comments out duplicates, but by default it matches on amount and date with a 5% tolerance. Two purchases of the same price on the same day look like one.

So every card importer overrides the comparison and also requires the description to match. Transfers between my own accounts needed their own rule, restricted to the same pair of accounts, because a loan payment of R$ 3,500.00 should not match a PIX of R$ 3,500.00 just because the numbers are equal.

## Running it every day

All of this used to be a monthly evening with coffee. Now [orch](https://github.com/gabrielkoerich/orch), the tool I built to run coding agents on a schedule, does it every morning at 8.

The job is a markdown prompt. It tells an agent to read the config, download new statements for every automated account, run the close pipeline, run `bean-check`, archive the files, and send me a short Telegram message with what came in and what is behind. The agent follows a skill file that holds everything I learned about the importers, so it does not have to rediscover the date rules or the dedup bugs each time.

The agent is not doing the accounting. The importers and Beancount do that, and they are deterministic. The agent is there for the parts that break: Proton Bridge is not running, a bank changed the file name, a statement came in a format the importer has not seen. It reports those instead of guessing.

On a normal day I read the Telegram message and do nothing else.

## Prices and everything else

Once the ledger is complete, it can answer more than "how much did I spend". Price sources pull SELIC, CDI and IPCA from the Central Bank, stock prices from brapi, US macro data from FRED, and a construction cost index from Sinduscon. The ledger has more than 54,000 price lines.

I also track sleep, HRV and steps as commodities in the same file. It sounds strange, but Beancount already knows how to store a number per day and plot it, so I did not need another tool.

## What it costs

**Time.** Each importer is a weekend at first and a few hours every time the bank changes the PDF. Fourteen of them is a lot of weekends.

**Mail access on macOS.** An agent launched by a background service does not inherit the terminal's permissions, so the Mail.app accounts fail with an AppleScript authorization error until I grant access to the right process. The iCloud mailbox search also times out at 120 seconds on a big inbox. Some mornings the report just says those accounts were skipped.

**The last 5%.** A few statements still need a manual download, and the categorizer still misses new merchants. I do not think the rest is worth automating.

**It is only mine.** The importers are written for my banks and my categories, and right now nobody else could run them without reading the code.

## Why I keep doing it

I can ask the ledger anything. How much a loan really costs after fees and insurance. What I spend when I count the outflows no app counts as spending, like loan principal. Whether a month was unusual or just felt like it. The answers come from a file I own, checked against the bank, and nothing about it depends on a company staying in business.

## What comes next

**Get it off my Mac.** Everything runs on my laptop today. If the lid is closed at 8, the job does not run. I want the daily job on a small server at home. The Mac stays in the picture for two things that only exist there: Mail.app and the key that holds my secrets.

**Teach passbox to fetch mail.** I wrote [passbox](@/posts/2026-09-29-a-password-manager-for-agents.md) so agents can use a secret without seeing it, and it already works across machines: a Linux box asks my Mac over Tailscale, and a fingerprint releases the secret. The price API keys already come from passbox, and the rest of the pipeline's secrets, like the passwords that open the bank PDFs, are moving there now. The server will also need my statements, so passbox needs a Mail tool. The job asks the Mac to search a mailbox, and the Mac sends back the PDF attachments and nothing else from the inbox. The search has to be asynchronous, because the iCloud search already takes more than 120 seconds. The job starts it, gets a handle, and checks back later. This tool cannot ask for a fingerprint, because nobody is awake to give one when the job runs. So it is limited by what it returns instead.

Two other passbox changes come with the move. Today the broker cannot tell which machine is asking, so it cannot have rules like "the server can read the price API keys and nothing else". Fixing that means running Tailscale inside the broker so it sees the real caller. And the server should get one approval in the morning that covers the secrets the day's jobs need, instead of a prompt for each read.

**Dockerize the whole pipeline, as two services.** Fava already runs in a container. The downloaders, importers and price sources still run in my local Python environment. I want to split them into two images. The first one does the work: it downloads statements, imports them, fetches prices, commits the ledger and pushes. It is the only one that talks to passbox. The second one only shows the ledger: it runs Fava at home and does `git pull` on a loop. Since git is the only link between the two, they can run on different machines, and moving either one is starting a container somewhere else.

**Open source some importers.** The bank importers have nothing personal in them, because the categories live in a separate file. Few people use Beancount in Brazil, and each of them probably wrote their own parser for the same banks. The work before publishing is the test fixtures, which are my real statements today and need to become fake ones.

If you keep your finances in plain text, especially with Brazilian banks, I would like to know how you handle the statements. And if you would use these importers, tell me, because that decides which ones I publish first.
