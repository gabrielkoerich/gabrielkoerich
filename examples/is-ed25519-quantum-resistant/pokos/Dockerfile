FROM rust:1-bookworm
ARG COMMIT=54963bf050487c49d7dcfa492ae5fb8882845ecd
RUN git clone https://github.com/anza-xyz/cryptography /src \
    && git -C /src checkout "$COMMIT"
WORKDIR /src
RUN cargo build --release -p ed25519-pokos --example gen_verify_pokos
CMD ["./target/release/examples/gen_verify_pokos"]
