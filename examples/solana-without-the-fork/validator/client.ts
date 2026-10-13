// Creates a counter account owned by the program, then sends real add instructions to it
import { readFileSync } from 'node:fs'
import {
  Connection, Keypair, PublicKey, SystemProgram, Transaction, TransactionInstruction, sendAndConfirmTransaction,
} from '@solana/web3.js'

const programId = new PublicKey(process.argv[2])
const connection = new Connection('http://127.0.0.1:8899', 'confirmed')
const payer = Keypair.fromSecretKey(Uint8Array.from(JSON.parse(readFileSync(process.env.PAYER!, 'utf8'))))
const counter = Keypair.generate()

const u64 = (n: bigint) => {
  const b = Buffer.alloc(8)
  b.writeBigUInt64LE(n)
  return b
}

const add = (by: bigint) => new TransactionInstruction({
  programId,
  keys: [{ pubkey: counter.publicKey, isSigner: false, isWritable: true }],
  data: u64(by),
})

async function send(label: string, ...ixs: TransactionInstruction[]) {
  const signers = ixs.some(ix => ix.programId.equals(SystemProgram.programId)) ? [payer, counter] : [payer]
  try {
    const sig = await sendAndConfirmTransaction(connection, new Transaction().add(...ixs), signers)
    const tx = await connection.getTransaction(sig, { commitment: 'confirmed', maxSupportedTransactionVersion: 0 })
    const value = (await connection.getAccountInfo(counter.publicKey))!.data.readBigUInt64LE(0)
    console.log(`${label}: ok, counter = ${value}, ${tx?.meta?.computeUnitsConsumed} CU for the transaction`)
  } catch (e) {
    const logs = (e as { logs?: string[] }).logs ?? []
    const reason = logs.find(l => l.includes('failed')) ?? String(e)
    console.log(`${label}: rejected, ${reason}`)
  }
}

const rent = await connection.getMinimumBalanceForRentExemption(8)
const create = SystemProgram.createAccount({
  fromPubkey: payer.publicKey, newAccountPubkey: counter.publicKey, lamports: rent, space: 8, programId,
})

await send('create the counter and add 37', create, add(37n))
await send('add 5', add(5n))
await send('add u64::MAX', add(18446744073709551615n))
