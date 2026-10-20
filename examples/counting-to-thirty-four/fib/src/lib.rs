#![no_std]

use pinocchio::{
    cpi::{invoke, Seed, Signer},
    error::ProgramError,
    instruction::{InstructionAccount, InstructionView},
    no_allocator, nostd_panic_handler, program_entrypoint, AccountView, Address, ProgramResult,
};
use pinocchio_system::instructions::CreateAccount;

program_entrypoint!(process_instruction);
no_allocator!();
nostd_panic_handler!();

const SEED: &[u8] = b"fib";
const DATA_LEN: u64 = 25; // a(8) + b(8) + n(8) + bump(1)

pub fn process_instruction(
    program_id: &Address,
    accounts: &mut [AccountView],
    instruction_data: &[u8],
) -> ProgramResult {
    // the runtime only resolves a CPI target that is in the caller's own accounts
    let [pda, payer, system, program, ..] = accounts else {
        return Err(ProgramError::NotEnoughAccountKeys);
    };

    if pda.is_data_empty() {
        let n = u64::from_le_bytes(
            instruction_data
                .get(0..8)
                .ok_or(ProgramError::InvalidInstructionData)?
                .try_into()
                .unwrap(),
        );
        if !payer.is_signer() {
            return Err(ProgramError::MissingRequiredSignature);
        }
        if system.address() != &pinocchio_system::ID {
            return Err(ProgramError::IncorrectProgramId);
        }
        let (expected, bump) =
            Address::find_program_address(&[SEED, payer.address().as_ref()], program_id);
        if pda.address() != &expected {
            return Err(ProgramError::InvalidSeeds);
        }

        let bump_ref = [bump];
        let seeds = [
            Seed::from(SEED),
            Seed::from(payer.address().as_ref()),
            Seed::from(&bump_ref),
        ];
        // Rent::get() reads the sysvar when no rent account is passed
        CreateAccount::with_minimum_balance(payer, pda, DATA_LEN, program_id, None)?
            .invoke_signed(&[Signer::from(&seeds)])?;

        {
            let mut data = pda.try_borrow_mut()?;
            data[0..8].copy_from_slice(&0u64.to_le_bytes());
            data[8..16].copy_from_slice(&1u64.to_le_bytes());
            data[16..24].copy_from_slice(&n.to_le_bytes());
            data[24] = bump;
        }

        if n > 0 {
            self_cpi(program_id, pda, payer, system, program)?;
        }
    } else {
        let remaining = {
            let mut data = pda.try_borrow_mut()?;
            let a = u64::from_le_bytes(data[0..8].try_into().unwrap());
            let b = u64::from_le_bytes(data[8..16].try_into().unwrap());
            let n = u64::from_le_bytes(data[16..24].try_into().unwrap());
            if n == 0 {
                return Ok(());
            }
            let new_b = a.checked_add(b).ok_or(ProgramError::ArithmeticOverflow)?;
            data[0..8].copy_from_slice(&b.to_le_bytes());
            data[8..16].copy_from_slice(&new_b.to_le_bytes());
            data[16..24].copy_from_slice(&(n - 1).to_le_bytes());
            n - 1
        };

        if remaining > 0 {
            self_cpi(program_id, pda, payer, system, program)?;
        }
    }

    Ok(())
}

fn self_cpi(
    program_id: &Address,
    pda: &AccountView,
    payer: &AccountView,
    system: &AccountView,
    program: &AccountView,
) -> ProgramResult {
    let metas = [
        InstructionAccount::writable(pda.address()),
        InstructionAccount::writable_signer(payer.address()),
        InstructionAccount::readonly(system.address()),
        InstructionAccount::readonly(program.address()),
    ];
    let ix = InstructionView {
        program_id,
        accounts: &metas,
        data: &[], // empty data = step mode
    };
    invoke(&ix, &[pda, payer, system, program])
}
