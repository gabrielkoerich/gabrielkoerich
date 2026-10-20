use std::process::Command;

fn threads() -> usize {
    // Linux (and Docker) has /proc, macOS needs `ps -M`, which prints a header and one line per thread
    if let Ok(status) = std::fs::read_to_string("/proc/self/status") {
        let line = status.lines().find(|l| l.starts_with("Threads:")).unwrap();
        return line[8..].trim().parse().unwrap();
    }

    let out = Command::new("ps").args(["-M", &std::process::id().to_string()]).output().unwrap();
    String::from_utf8_lossy(&out.stdout).lines().count() - 1
}

#[tokio::main]
async fn main() {
    println!("threads at the top of #[tokio::main]: {}", threads());
}
