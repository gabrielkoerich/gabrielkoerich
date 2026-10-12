use mollusk_svm::{result::Check, Mollusk};
use solana_account::Account;
use solana_instruction::{AccountMeta, Instruction};
use pinocchio::error::ProgramError;
use solana_pubkey::Pubkey;

const PROGRAM: [u8; 32] = [7; 32];
const COUNTER: [u8; 32] = [9; 32];

fn mollusk() -> Mollusk {
    let elf = std::env::var("ELF").unwrap_or("target/bpfel-unknown-none/release/libcounter".into());
    Mollusk::new(&PROGRAM.into(), &elf)
}

fn counter(value: u64, owner: [u8; 32]) -> (Pubkey, Account) {
    let account = Account { lamports: 1_000_000, data: value.to_le_bytes().to_vec(), owner: owner.into(), ..Default::default() };
    (COUNTER.into(), account)
}

fn add(by: &[u8], writable: bool) -> Instruction {
    let meta = if writable { AccountMeta::new(COUNTER.into(), false) } else { AccountMeta::new_readonly(COUNTER.into(), false) };
    Instruction { program_id: PROGRAM.into(), accounts: vec![meta], data: by.to_vec() }
}

#[test]
fn adds() {
    let r = mollusk().process_and_validate_instruction(
        &add(&5u64.to_le_bytes(), true),
        &[counter(37, PROGRAM)],
        &[Check::success(), Check::account(&COUNTER.into()).data(&42u64.to_le_bytes()).build()],
    );
    println!("add 5 to 37: {} CU", r.compute_units_consumed);
}

#[test]
fn rejects_overflow() {
    mollusk().process_and_validate_instruction(
        &add(&5u64.to_le_bytes(), true),
        &[counter(u64::MAX - 1, PROGRAM)],
        &[Check::err(ProgramError::ArithmeticOverflow)],
    );
}

#[test]
fn rejects_wrong_owner() {
    mollusk().process_and_validate_instruction(
        &add(&5u64.to_le_bytes(), true),
        &[counter(37, [1; 32])],
        &[Check::err(ProgramError::IncorrectProgramId)],
    );
}

#[test]
fn rejects_read_only() {
    mollusk().process_and_validate_instruction(
        &add(&5u64.to_le_bytes(), false),
        &[counter(37, PROGRAM)],
        &[Check::err(ProgramError::InvalidAccountData)],
    );
}

#[test]
fn rejects_short_data() {
    mollusk().process_and_validate_instruction(
        &add(&[5, 0, 0], true),
        &[counter(37, PROGRAM)],
        &[Check::err(ProgramError::InvalidInstructionData)],
    );
}
