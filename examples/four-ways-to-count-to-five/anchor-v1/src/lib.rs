use anchor_lang::prelude::*;
use anchor_lang::solana_program::{instruction::Instruction, program::invoke};
use anchor_lang::{InstructionData, ToAccountMetas};

declare_id!("3yDL675dKEnNZfvDz6dznB3n3qpXpiZJK4pSYkSAd1Xr");

#[program]
pub mod fib_anchor_v1 {
    use super::*;

    /// Init when the PDA is new (n = steps), step when it exists (n is ignored)
    pub fn fib(ctx: Context<Fib>, n: u64) -> Result<()> {
        let state = &mut ctx.accounts.pda;

        // a freshly created account is all zeros, a live one always has b >= 1
        if state.b == 0 {
            state.a = 0;
            state.b = 1;
            state.n = n;
            state.bump = ctx.bumps.pda;
        } else {
            if state.n == 0 {
                return Ok(());
            }
            let new_b = state.a.checked_add(state.b).unwrap();
            state.a = state.b;
            state.b = new_b;
            state.n -= 1;
        }

        if state.n > 0 {
            // persist before the self-CPI, Anchor otherwise writes its stale copy on exit
            ctx.accounts.pda.exit(&crate::ID)?;
            let ix = Instruction {
                program_id: crate::ID,
                accounts: crate::accounts::Fib {
                    pda: ctx.accounts.pda.key(),
                    payer: ctx.accounts.payer.key(),
                    system_program: ctx.accounts.system_program.key(),
                    fib_program: crate::ID,
                }
                .to_account_metas(None),
                data: crate::instruction::Fib { n: 0 }.data(),
            };
            invoke(
                &ix,
                &[
                    ctx.accounts.pda.to_account_info(),
                    ctx.accounts.payer.to_account_info(),
                    ctx.accounts.system_program.to_account_info(),
                    ctx.accounts.fib_program.to_account_info(),
                ],
            )?;
            ctx.accounts.pda.reload()?;
        }
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Fib<'info> {
    #[account(
        init_if_needed,
        payer = payer,
        space = 8 + FibState::INIT_SPACE,
        seeds = [b"fib", payer.key().as_ref()],
        bump,
    )]
    pub pda: Account<'info, FibState>,
    #[account(mut)]
    pub payer: Signer<'info>,
    pub system_program: Program<'info, System>,
    /// the runtime only resolves a CPI target that is in the caller's own accounts
    pub fib_program: Program<'info, crate::program::FibAnchorV1>,
}

#[account]
#[derive(InitSpace)]
pub struct FibState {
    pub a: u64,
    pub b: u64,
    pub n: u64,
    pub bump: u8,
}
