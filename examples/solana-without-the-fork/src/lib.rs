#![cfg_attr(target_os = "solana", no_std)]

#[cfg(target_arch = "bpf")]
use solana_compiler_builtins as _;

use pinocchio::{error::ProgramError, AccountView, Address, ProgramResult};

pinocchio::program_entrypoint!(process_instruction);
pinocchio::no_allocator!();
pinocchio::nostd_panic_handler!();

// Adds the u64 in the instruction data to the u64 stored in the counter account
pub fn process_instruction(program_id: &Address, accounts: &mut [AccountView], data: &[u8]) -> ProgramResult {
    let [counter] = accounts else {
        return Err(ProgramError::NotEnoughAccountKeys);
    };

    if !counter.owned_by(program_id) {
        return Err(ProgramError::IncorrectProgramId);
    }

    if !counter.is_writable() {
        return Err(ProgramError::InvalidAccountData);
    }

    let by: [u8; 8] = data.try_into().map_err(|_| ProgramError::InvalidInstructionData)?;
    let mut bytes = counter.try_borrow_mut()?;
    let stored: &mut [u8; 8] = (&mut bytes[..]).try_into().map_err(|_| ProgramError::InvalidAccountData)?;
    let next = u64::from_le_bytes(*stored)
        .checked_add(u64::from_le_bytes(by))
        .ok_or(ProgramError::ArithmeticOverflow)?;
    *stored = next.to_le_bytes();
    Ok(())
}
