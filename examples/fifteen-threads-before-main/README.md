# Fifteen threads before main: example

The thread count from the post [Fifteen threads before main](https://gabrielkoerich.com/posts/fifteen-threads-before-main/). The program prints how many threads exist on the first line of a `#[tokio::main]` function.

| File | What it does |
|---|---|
| `src/main.rs` | Counts its own threads from `/proc/self/status` on Linux, or with `ps -M` on macOS, at the top of `#[tokio::main]` |

## Run

`just run` builds and runs it in Docker (`rust:1`), so you need only Docker and `just`. `just clean` removes `target/`.

Tokio starts one worker per core, so the number is the main thread plus the cores the machine has. In Docker that is the cores Docker gives its VM, not the host's. On the M4 Max in the post, run natively, it was 15.
