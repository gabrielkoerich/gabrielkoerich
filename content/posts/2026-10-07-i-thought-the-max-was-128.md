+++
title = "I thought the max was 128"
date = 2026-10-07
[taxonomies]
tags = ["solana", "rust", "anchor", "defi"]
+++

I am building a vault on Solana that holds several assets at once. A curator sets target weights, depositors get shares, and a withdrawal pays out in kind: a slice of every asset the vault holds.

The vault account stores its allocations in a fixed array of 20, because a zero copy account needs its data length fixed when it is created. The first version of the create instruction checked new vaults against that array length, so a curator could create a vault with 20 allocations. At that point I had not checked whether such a vault could be withdrawn from. It could not. So I measured the limits on a Solana transaction, found the one that binds, and capped the vault at 10. A test built a vault at 10 and withdrew from all of it in one transaction. It passed.

Then I checked the number I had built everything on against the Solana docs. The account limit I used was 128. On mainnet it is 64. A vault at the cap of 10 would take deposits and could never pay them back.

This post is about how accounts and transactions work on Solana, why the account limit and not bytes or compute decides how big this vault can be, how I got that limit wrong, and what the new v1 transaction format changes.

## How Solana accounts work

Everything on Solana is an account. An account has an address, a balance in lamports, an owner program, and a byte array of data. Programs hold no state of their own. A program's state lives in accounts it owns, and only the owner can change their data.

**Size is fixed when you create the account.** You pay a rent deposit for the bytes. An account can grow later with `realloc`, [by at most 10 KiB per instruction](https://docs.rs/solana-account-info/latest/solana_account_info/constant.MAX_PERMITTED_DATA_INCREASE.html), and the payer tops up the deposit. In practice you decide the layout before the first user deposits, because every later change is a migration of live accounts that hold money.

**Program derived addresses have no private key.** A PDA is derived from seeds and the program id, and only that program can sign for it. This is how a program owns token accounts and holds funds.

**A transaction declares every account it touches, up front.** Each account is listed with a flag for writable and for signer, and the runtime locks them before execution. Transactions that write to different accounts can run in parallel. Transactions that write to the same account run one after the other. This is how Solana runs in parallel without programs knowing anything about threads.

That last rule is where the limits come from.

## Three limits on one transaction

**Bytes.** A legacy or v0 transaction is [at most 1,232 bytes](https://solana.com/docs/core/transactions), the IPv6 minimum MTU of 1,280 minus 48 bytes of headers. Every account address is 32 bytes.

**Compute.** [Each instruction gets 200,000 compute units by default](https://solana.com/docs/core/fees). A transaction can request up to 1,400,000.

**Accounts.** A transaction can reference at most 64 unique account addresses. That count includes every program the transaction calls, and an account used by several instructions counts once.

An Address Lookup Table helps with bytes. [A table stores up to 256 addresses](https://solana.com/docs/advanced/lookup-tables) on chain, and a v0 transaction refers to each one by a one byte index instead of 32 bytes. It does not help with the account limit. In the words of the docs, the runtime loads at most 64 accounts per transaction regardless of how many addresses the tables it references hold.

## Why a withdrawal needs so many accounts

Two rules make a withdrawal large.

**It pays out of every allocation.** Per allocation, the instruction needs the vault's position in that reserve, the reserve, its price oracle, the reserve's token authority, the treasury token account, the mint, and the depositor's destination token account. That is 7 accounts per allocation.

**It needs a valuation from the same slot.** The share price is the vault's total value divided by its shares. Earlier, some instructions accepted a cached value up to 30 seconds old, and two checked nothing at all. Since refreshing is permissionless, a 30 second window let a caller choose which 30 seconds of prices to act on. Now a refresh instruction writes a slot number only after it values every leg, and every instruction that uses the value requires that slot to be the current one. So the refresh goes in the same transaction as the withdrawal, with its own accounts.

Together that is 11 fixed accounts plus 7 per allocation. Those are slots in the instructions, not unique addresses. Legs can share accounts, for example two reserves of the same mint share that mint. But a cap has to hold for the worst case, a vault where no two legs share anything, so the budget counts every slot as its own address.

## Measuring bytes and compute

I measured the refresh plus withdrawal pair in a local test environment.

**Bytes ran out at 2 allocations** in a legacy transaction. With a lookup table, 20 allocations compiled to 972 bytes, and 10 compiled to 581.

**Compute measured 105k units at one allocation and 144k at two.** That is about 39k per leg on a floor of 66k. Past about three allocations the pair goes over the 200k default and has to request more. Twenty allocations would land near 850k, under the 1.4M ceiling.

So bytes looked tight and a lookup table removed them, and compute had room to spare. The account limit was the one that decided the size of the vault.

## Where 128 came from

I designed the cap against 128 accounts. That number was everywhere I looked. The Solana SDK has a constant for it:

```rust
pub const MAX_TX_ACCOUNT_LOCKS: usize = 128;
```

Source: [`solana-transaction` v2.2.3, `sanitized.rs`](https://github.com/anza-xyz/solana-sdk/blob/transaction%40v2.2.3/transaction/src/sanitized.rs#L21)

At 128, the ceiling is 16 allocations. I put the cap at 10, to leave room in case a later change added an account per leg, and wrote a compile time check against the constant:

```rust
const _: () = assert!(
    FIXED_ACCOUNTS + ACCOUNTS_PER_LEG * MAX_ACTIVE_LEGS <= MAX_TX_ACCOUNT_LOCKS,
    "a vault at the cap must stay withdrawable in one transaction"
);
```

The end to end test at 10 allocations withdrew from every leg in one transaction, and it passed. That test does not settle the limit. Its legs share accounts, all ten use the same oracle, so its unique count is below the worst case, and I did not measure it.

The name gave me a second reason to think there was room. `MAX_TX_ACCOUNT_LOCKS` sounds like a count of locks, and I read locks as the writable accounts: the vault, its positions, the token accounts. The oracles, mints and programs are read-only, so I assumed they did not count. They do. The runtime takes a read lock on every read-only account, which lets other transactions read it in parallel, and the limit is checked against the length of the whole account list, writable or not:

```rust
pub fn validate_account_locks(
    account_keys: AccountKeys,
    tx_account_lock_limit: usize,
) -> TransactionResult<()> {
    if account_keys.len() > tx_account_lock_limit {
        Err(TransactionError::TooManyAccountLocks)
    } else if has_duplicates(account_keys) {
        Err(TransactionError::AccountLoadedTwice)
    } else {
        Ok(())
    }
}
```

Source: [Agave, `accounts-db/src/account_locks.rs`](https://github.com/anza-xyz/agave/blob/8063bd2f7ea538f9d532ca958c882f8caa7fa28d/accounts-db/src/account_locks.rs#L143-L154)

`account_keys.len()` adds up the static keys and every address loaded from a lookup table, writable and read-only. Marking an account read-only lets more transactions run beside yours. It does not make room under the limit.

The validator does not use the constant directly. In Agave the limit depends on a feature gate:

```rust
pub fn get_transaction_account_lock_limit(&self) -> usize {
    if let Some(transaction_account_lock_limit) = self.transaction_account_lock_limit {
        transaction_account_lock_limit
    } else if self.feature_set.snapshot().increase_tx_account_lock_limit {
        MAX_TX_ACCOUNT_LOCKS
    } else {
        64
    }
}
```

Source: [Agave, `runtime/src/bank.rs`](https://github.com/anza-xyz/agave/blob/8063bd2f7ea538f9d532ca958c882f8caa7fa28d/runtime/src/bank.rs#L3849-L3857)

The gate is [`increase_tx_account_lock_limit`](https://github.com/solana-labs/solana/issues/27241), "increase tx account lock limit to 128". It was activated on devnet and testnet. On mainnet it was never activated:

```
$ solana feature status 9LZdXeKGeBV6hRLdxS1rHbHoEUsKqesCC2ZAPTPKJAbK -um
9LZdXeKGeBV6hRLdxS1rHbHoEUsKqesCC2ZAPTPKJAbK | inactive | NA | increase tx account lock limit to 128 #27241
```

[The Solana docs say it directly](https://solana.com/docs/core/transactions): max accounts per transaction is 64, and 128 only when that gate is activated, which it currently is not.

At 64, the worst case ceiling is 11 + 7n ≤ 64, so 7 allocations. A cap of 10 needs up to 81. The compile time check passed because it compared against the wrong constant. It is only as good as the number on the right side, and that number was correct for devnet and wrong for mainnet.

## The lookup table did not change it

It is easy to read a lookup table as a way around the account limit. It only changes how accounts are written down. A v0 transaction with a lookup table fits ten legs in 581 bytes, and the runtime still refuses to load more than 64 unique accounts.

## What v1 transactions change

On September 15, 2026, at the start of mainnet epoch 1035, the v1 transaction format went live ([SIMD-0385](https://github.com/solana-foundation/solana-improvement-documents/blob/main/proposals/0385-transaction-v1.md)). The feature account for `enable_tx_v1` shows activation at slot 447,120,000. [Solana's own comparison](https://solana.com/upgrades/larger-transaction-sizes):

| | legacy | v0 | v1 |
|---|---|---|---|
| size | 1,232 bytes | 1,232 bytes | 4,096 bytes |
| accounts | about 32, bound by size | 64, through lookup tables | 64, inline |
| lookup tables | not supported | supported | not supported |

For this vault, v1 removes the byte problem. Sixty four addresses at 32 bytes each are 2,048 bytes, which fits in 4,096 with room for instructions and signatures. A withdrawal no longer needs a lookup table, and neither does the client code that builds, extends and fetches one before every transaction.

It does not move the account limit. A v1 transaction can name 64 accounts, the same as v0, so the ceiling is still 7 allocations.

The change that would move it is [SIMD-0596](https://github.com/solana-foundation/solana-improvement-documents/blob/main/proposals/0596-increase-txv1-account-lock-limit-to-96.md), which raises the account limit for v1 transactions to 96 and keeps legacy and v0 at 64. At 96 the ceiling is 12 allocations, and a cap of 10 fits with room for one more account per leg. Its status today is Draft, and it has no feature gate yet. Until it ships, the cap is 7.

## Zero copy layouts, because the layout is forever

`MAX_LEGS = 20` is an array length. It sets the vault account's data length, and changing it means migrating every vault, so it stays at 20. How many allocations a vault may use is a separate constant, `MAX_ACTIVE_LEGS`. The bug at the start of this post was using the first as if it were the second.

Anchor gives you two ways to read an account. `Account<T>` deserializes the bytes with Borsh into a Rust struct, a copy, on every instruction. For large accounts that costs compute and memory, and a program has [a 4,096 byte stack frame and a 32 KiB heap](https://solana.com/docs/core/programs) by default. The vault account is 3,488 bytes and holds two arrays of 20 allocations, the current weights and the pending ones.

`#[account(zero_copy)]` with `AccountLoader<T>` [skips the copy](https://www.anchor-lang.com/docs/features/zero-copy). The struct is laid out as `#[repr(C)]` and must be `Pod`, and loading it is a cast of the account's bytes to a reference. Nothing is deserialized. The price is that the in-memory layout is the on-chain layout, byte for byte:

```rust
#[zero_copy]
pub struct Allocation {
    pub reserve: Pubkey,         // 32
    pub value: u64,              // 8
    pub weight_bps: u16,         // 2
    pub _pad: [u8; 22],          // explicit, 64 bytes in total
}
```

`Pod` forbids implicit padding, so every gap is a named `_pad` field. Fields go from largest alignment to smallest so the gaps stay small. Each struct ends with a reserved tail, `_reserved: [u64; N]`, so new fields can be carved out of it later without changing the account size.

Each struct then gets two size assertions, and both are needed:

```rust
// a sum of the fields, which proves there is no implicit padding
const_assert_eq!(size_of::<Schedule>(), 8 * 8 + 3 * 32 + /* ... */ 32 * 8);

// a literal, which proves the account size did not change
const_assert_eq!(size_of::<Schedule>(), 424);
```

The literal looks redundant, and it caught a real bug. A change took 32 bytes of the reserved tail to add 24 bytes of new fields. The field sum was updated on both sides and still matched, and the account had silently become 8 bytes smaller. On a live account that would misread every field after the change. Only the literal noticed.

The reserved tail is made of `u64`, so it can only give up whole 8 byte slots. A 15 byte field costs 16 bytes of reserve, and the arithmetic has to say so.

One more trick saves bytes entirely. Some reserves have an optional strategy with its own settings. Instead of adding optional fields to every reserve, the strategy lives in a separate PDA derived from the reserve's address. Whether the strategy is enabled is answered by whether that account exists, which costs zero bytes on the reserve.

## What it costs

**Seven allocations.** A curator who wants a 10 asset vault cannot have one until a paginated withdrawal works or the account limit goes up.

**A test that never builds the worst case.** The test at 10 allocations shares one oracle across every leg, so its transaction has fewer unique accounts than a vault whose legs share nothing. A limit test has to build the largest transaction a user can create, on a runtime with the target cluster's feature set.

**Lookup tables for v0.** Until clients move to v1, every operation that reads the vault's value needs a lookup table, and the table has to hold more than the vault's own addresses. A table built only from them left a deposit 84 bytes over the limit, because protocol accounts, mints and the depositor's token accounts are in the same instructions.

**Callers must raise the compute limit.** The default 200k is not enough past three allocations, so a hand built transaction will fail.

**Unused layout.** Thirteen allocation slots, twice, sit in every vault account and do nothing until the limit or the withdrawal design changes.

## What I check now

Constants in an SDK describe what the code supports. Feature gates decide what a cluster enforces. Before a limit becomes a number users depend on, I check three things: the docs for the current value, `solana feature status -um` for any gate that changes it, and the SIMD for anything that will. Then I run the worst case transaction against a runtime with mainnet's feature set.

## What I am studying next: paginated withdrawals

Seven assets is too few for a vault whose whole point is holding several of them. Waiting for SIMD-0596 to raise v1 transactions to 96 accounts would get to 12, and it is still a draft. So I am studying a withdrawal that is no longer one transaction.

I passed on this when I thought the limit was 128 and a cap of 10 was safe. It adds permanent state, and a cap can be raised later while that state can never be removed. Other multi-asset vault designs land in the same range for the same reason: one standard caps at 8 assets, and one basket protocol ran 15 per basket in one transaction before moving to multi-step auctions to go higher. At 7 the trade looks different.

The idea is to burn the shares and freeze what the depositor is owed in each asset in the first transaction, at that moment's valuation, so nobody can burn, wait for one asset to move, and claim the rest at a better price. The vault sets those amounts aside as reserved, and later transactions pay them out a few legs at a time, each small enough to fit under 64 accounts.

It is not solved yet, because the first transaction still has to value every leg in the same slot. The refresh takes three accounts per leg (the vault's position, the reserve and its oracle) plus a handful of fixed ones, so on its own it can value about 19 legs in one transaction when no two legs share an account. The burn adds its own accounts on top. Paginating the payout moves the ceiling from 7 into the teens. Reaching 20 would mean splitting the valuation too, and that collides with the rule that the valuation must come from the current slot.

The cost is known: every reserve total splits into reserved and available, and valuation, share supply checks, rebalance, swap based rebalance and moving liquidity between reserves all have to respect that split.

The layout is ready for whatever comes out of it. The vault account keeps 20 allocation slots, so raising the active cap is one constant and no migration.
