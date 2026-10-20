#![no_std]

use pinocchio::{
    cpi::invoke_with_bounds,
    error::ProgramError,
    instruction::{InstructionAccount, InstructionView},
    no_allocator, nostd_panic_handler, program_entrypoint, AccountView, Address, ProgramResult,
};

program_entrypoint!(process_instruction);
no_allocator!();
nostd_panic_handler!();

const MAX_ACCOUNTS: usize = 12;

/// Calls the program in account 0 with the remaining accounts and the same data
pub fn process_instruction(
    _program_id: &Address,
    accounts: &mut [AccountView],
    data: &[u8],
) -> ProgramResult {
    // the runtime only resolves a CPI target that is in the caller's own accounts
    let [next, rest @ ..] = accounts else {
        return Err(ProgramError::NotEnoughAccountKeys);
    };
    if rest.is_empty() || rest.len() > MAX_ACCOUNTS {
        return Err(ProgramError::InvalidArgument);
    }

    let metas: [InstructionAccount; MAX_ACCOUNTS] = core::array::from_fn(|i| {
        let a = &rest[i.min(rest.len() - 1)];
        InstructionAccount::new(a.address(), a.is_writable(), a.is_signer())
    });
    let ix = InstructionView {
        program_id: next.address(),
        accounts: &metas[..rest.len()],
        data,
    };
    invoke_with_bounds::<MAX_ACCOUNTS, _>(&ix, rest)
}
