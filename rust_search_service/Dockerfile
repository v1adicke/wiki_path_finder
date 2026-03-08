FROM rust:1.87-bookworm AS builder
WORKDIR /app

COPY Cargo.toml ./
COPY src ./src

RUN cargo build --release

FROM debian:bookworm-slim
WORKDIR /app

RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/target/release/rust_search_service /usr/local/bin/rust_search_service

EXPOSE 8081
CMD ["rust_search_service"]
