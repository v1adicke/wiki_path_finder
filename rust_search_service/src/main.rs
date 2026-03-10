use std::sync::Arc;
use std::time::Duration;

use axum::routing::{get, post};
use axum::Router;
use reqwest::Client;
use tokio::sync::Mutex;

mod handlers;
mod metrics;
mod models;
mod search;
mod text;
mod wiki;
mod wikipedia_api;

use crate::handlers::{health, metrics, search};
use crate::models::{AppState, RuntimeMetrics};
use crate::wiki::WikiClient;

#[tokio::main]
async fn main() {
    let cache_size = std::env::var("RUST_CACHE_SIZE")
        .ok()
        .and_then(|v| v.parse::<usize>().ok())
        .unwrap_or(4000)
        .max(128);
    let max_concurrency = std::env::var("RUST_WIKI_MAX_CONCURRENCY")
        .ok()
        .and_then(|v| v.parse::<usize>().ok())
        .unwrap_or(32)
        .max(1);
    let retries = std::env::var("RUST_WIKI_RETRIES")
        .ok()
        .and_then(|v| v.parse::<usize>().ok())
        .unwrap_or(3)
        .max(1);

    let client = Client::builder()
        .user_agent("wiki-path-finder-rust/0.2")
        .timeout(Duration::from_secs(12))
        .build()
        .expect("failed to build reqwest client");

    let wiki = WikiClient::new(client, cache_size, max_concurrency, retries);
    let state = AppState {
        wiki,
        metrics: Arc::new(Mutex::new(RuntimeMetrics::default())),
    };

    let app = Router::new()
        .route("/health", get(health))
        .route("/metrics", get(metrics))
        .route("/search", post(search))
        .with_state(state);

    let listener = tokio::net::TcpListener::bind("0.0.0.0:8081")
        .await
        .expect("failed to bind 0.0.0.0:8081");

    axum::serve(listener, app).await.expect("server crashed");
}
