#!/usr/bin/env bash
# Deploys the upstream build to a local validator with mainnet's feature set, then sends real instructions
set -euo pipefail

work=${WORK:-/tmp/counter-validator}
rpc=http://127.0.0.1:8899
mkdir -p "$work"

solana-test-validator --reset --quiet --ledger "$work/ledger" --clone-feature-set --url https://api.mainnet-beta.solana.com &
validator=$!
trap 'kill "$validator" 2>/dev/null || true' EXIT

# Wait for RPC, and stop with the log if the validator dies first
for _ in $(seq 120); do
  if solana cluster-version --url "$rpc" >/dev/null 2>&1; then
    break
  fi

  if ! kill -0 "$validator" 2>/dev/null; then
    tail -20 "$work/ledger/validator.log"
    exit 1
  fi

  sleep 1
done

solana-keygen new --no-bip39-passphrase --silent --force -o "$work/payer.json"
solana-keygen new --no-bip39-passphrase --silent --force -o "$work/program.json"
solana airdrop 10 --url "$rpc" --keypair "$work/payer.json" >/dev/null
solana program deploy --url "$rpc" --keypair "$work/payer.json" --program-id "$work/program.json" ../target/bpfel-unknown-none/release/libcounter.so

# A program becomes callable from the slot after its deploy, so wait for the next slot
deployed=$(solana slot --url "$rpc")
while [ "$(solana slot --url "$rpc")" -le "$deployed" ]; do
  sleep 0.2
done

bun install --silent
PAYER="$work/payer.json" bun client.ts "$(solana address -k "$work/program.json")"
