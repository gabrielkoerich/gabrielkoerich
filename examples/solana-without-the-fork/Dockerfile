FROM rust:1-bookworm
ARG TARGETARCH
# Upstream: a pinned nightly and sbpf-linker built from the crates.io source
RUN rustup toolchain install nightly-2026-10-08 --profile minimal --component rust-src \
 && rustup default nightly-2026-10-08 \
 && cargo install sbpf-linker --version 0.2.3 --locked
# Solana's own toolchain, linked as +solana
RUN arch=$([ "$TARGETARCH" = arm64 ] && echo aarch64 || echo x86_64) \
 && curl -sSfL https://github.com/anza-xyz/platform-tools/releases/download/v1.57/platform-tools-linux-$arch.tar.bz2 | tar xj -C /opt --one-top-level=pt \
 && rustup toolchain link solana /opt/pt/rust
WORKDIR /work
