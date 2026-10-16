#![no_std]

use anchor_lang::prelude::*;

declare_id!("3yDL675dKEnNZfvDz6dznB3n3qpXpiZJK4pSYkSAd1Xr");

#[program]
pub mod fib_anchor_v2 {
    use super::*;

    /// Init when the PDA is new (n = steps), step when it exists (n is ignored)
    pub fn fib(ctx: &mut Context<Fib>, n: u64) -> Result<()> {
        let bump = ctx.bumps.pda;
        let state = &mut ctx.accounts.pda;

        // a freshly created account is all zeros, a live one always has b >= 1
        if state.b.get() == 0 {
            state.a = 0u64.into();
            state.b = 1u64.into();
            state.n = n.into();
            state.bump = bump;
        } else {
            if state.n.get() == 0 {
                return Ok(());
            }
            let new_b = state.a.get().checked_add(state.b.get()).unwrap();
            state.a = state.b;
            state.b = new_b.into();
            state.n = (state.n.get() - 1).into();
        }

        if state.n.get() > 0 {
            // zero-copy: the account bytes are already written, nothing to flush
            let accounts = __cpi_accounts_fib::Fib {
                pda: ctx.accounts.pda.cpi_handle_mut(),
                payer: ctx.accounts.payer.cpi_handle_mut(),
                system_program: ctx.accounts.system_program.cpi_handle(),
                fib_program: ctx.accounts.fib_program.cpi_handle(),
            };
            CpiContext::new(&crate::ID, accounts).invoke(&crate::instruction::Fib { n: 0 }.data())?;
        }
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Fib {
    #[account(
        init_if_needed,
        payer = payer,
        seeds = [b"fib", payer.address().as_ref()],
        bump = pda.bump,
    )]
    pub pda: Account<FibState>,
    #[account(mut)]
    pub payer: Signer,
    pub system_program: Program<System>,
    /// the runtime only resolves a CPI target that is in the caller's own accounts
    pub fib_program: Program<FibProgram>,
}

#[account]
pub struct FibState {
    pub a: PodU64,
    pub b: PodU64,
    pub n: PodU64,
    pub bump: u8,
}

/// v2's #[program] emits no program marker type, so `Program<T>` needs one
pub struct FibProgram;

impl Id for FibProgram {
    fn id() -> Address {
        crate::ID
    }
}
