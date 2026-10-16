use solana_account_info::{next_account_info, AccountInfo};
use solana_cpi::{invoke, invoke_signed};
use solana_instruction::{AccountMeta, Instruction};
#[cfg(not(feature = "no-logs"))]
use solana_msg::msg;
#[cfg(feature = "no-logs")]
macro_rules! msg {
    ($($t:tt)*) => {};
}
use solana_program_entrypoint::{entrypoint, ProgramResult};
use solana_pubkey::Pubkey;

entrypoint!(process_instruction);

const SEED: &[u8] = b"fib";
const DATA_LEN: u64 = 25; // a(8) + b(8) + n(8) + bump(1)
const SYSTEM_PROGRAM: Pubkey = Pubkey::new_from_array([0u8; 32]);

/// Rent-exempt minimum: (128 overhead + data_len) * 3480 lamports/byte-year * 2 years
const fn rent_minimum(data_len: u64) -> u64 {
    (128 + data_len) * 3_480 * 2
}

/// Build a CreateAccount instruction for the system program (bincode).
fn create_account_ix(
    from: &Pubkey,
    to: &Pubkey,
    lamports: u64,
    space: u64,
    owner: &Pubkey,
) -> Instruction {
    let mut data = Vec::with_capacity(52);
    data.extend_from_slice(&0u32.to_le_bytes());
    data.extend_from_slice(&lamports.to_le_bytes());
    data.extend_from_slice(&space.to_le_bytes());
    data.extend_from_slice(owner.as_ref());
    Instruction {
        program_id: SYSTEM_PROGRAM,
        accounts: vec![AccountMeta::new(*from, true), AccountMeta::new(*to, true)],
        data,
    }
}

pub fn process_instruction(
    program_id: &Pubkey,
    accounts: &[AccountInfo],
    instruction_data: &[u8],
) -> ProgramResult {
    let iter = &mut accounts.iter();
    let pda = next_account_info(iter)?;
    let payer = next_account_info(iter)?;
    let system = next_account_info(iter)?;
    // the runtime only resolves a CPI target that is in the caller's own accounts
    let program = next_account_info(iter)?;

    if pda.data_is_empty() {
        // create PDA, store state, start recursion
        assert!(instruction_data.len() >= 8, "need u64 n");
        assert!(payer.is_signer, "payer must sign");
        assert_eq!(*system.key, SYSTEM_PROGRAM, "bad system program");

        let n = u64::from_le_bytes(instruction_data[0..8].try_into().unwrap());
        let (expected, bump) =
            Pubkey::find_program_address(&[SEED, payer.key.as_ref()], program_id);
        assert_eq!(*pda.key, expected, "wrong PDA");

        invoke_signed(
            &create_account_ix(
                payer.key,
                pda.key,
                rent_minimum(DATA_LEN),
                DATA_LEN,
                program_id,
            ),
            &[payer.clone(), pda.clone()],
            &[&[SEED, payer.key.as_ref(), &[bump]]],
        )?;

        let mut data = pda.try_borrow_mut_data()?;
        data[0..8].copy_from_slice(&0u64.to_le_bytes()); // a = fib(0)
        data[8..16].copy_from_slice(&1u64.to_le_bytes()); // b = fib(1)
        data[16..24].copy_from_slice(&n.to_le_bytes());
        data[24] = bump;
        drop(data);

        msg!("init: a=0 b=1 n={}", n);

        if n > 0 {
            self_cpi(program_id, pda, payer, system, program)?;
        }
    } else {
        //  advance fibonacci, recurse if steps remain
        let mut data = pda.try_borrow_mut_data()?;
        let a = u64::from_le_bytes(data[0..8].try_into().unwrap());
        let b = u64::from_le_bytes(data[8..16].try_into().unwrap());
        let n = u64::from_le_bytes(data[16..24].try_into().unwrap());

        if n == 0 {
            msg!("done: {}", b);
            return Ok(());
        }

        let new_b = a.checked_add(b).expect("overflow");
        data[0..8].copy_from_slice(&b.to_le_bytes());
        data[8..16].copy_from_slice(&new_b.to_le_bytes());
        data[16..24].copy_from_slice(&(n - 1).to_le_bytes());
        drop(data);

        msg!("step: a={} b={} n={}", b, new_b, n - 1);

        if n - 1 > 0 {
            self_cpi(program_id, pda, payer, system, program)?;
        } else {
            msg!("done: {}", new_b);
        }
    }

    Ok(())
}

/// Recursive self-CPI: invoke this program again to advance one fibonacci step.
/// Solana max invoke stack height is 5, so max 4 recursive steps after init.
fn self_cpi<'a>(
    program_id: &Pubkey,
    pda: &AccountInfo<'a>,
    payer: &AccountInfo<'a>,
    system: &AccountInfo<'a>,
    program: &AccountInfo<'a>,
) -> ProgramResult {
    invoke(
        &Instruction {
            program_id: *program_id,
            accounts: vec![
                AccountMeta::new(*pda.key, false),
                AccountMeta::new(*payer.key, true),
                AccountMeta::new_readonly(SYSTEM_PROGRAM, false),
                AccountMeta::new_readonly(*program_id, false),
            ],
            data: vec![], // empty data = step mode
        },
        &[pda.clone(), payer.clone(), system.clone(), program.clone()],
    )
}
