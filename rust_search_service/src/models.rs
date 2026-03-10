use std::sync::Arc;

use serde::{Deserialize, Serialize};
use tokio::sync::Mutex;

use crate::wiki::WikiClient;

#[derive(Clone)]
pub struct AppState {
    pub wiki: WikiClient,
    pub metrics: Arc<Mutex<RuntimeMetrics>>,
}

#[derive(Debug, Deserialize)]
pub struct SearchRequest {
    pub start_article: String,
    pub end_article: String,
    pub time_limit: Option<u64>,
}

#[derive(Debug, Serialize)]
pub struct SearchResponse {
    pub path: Option<Vec<String>>,
    pub elapsed_time: f64,
    pub error: Option<String>,
    pub steps_count: usize,
    pub telemetry: SearchTelemetry,
}

#[derive(Debug, Serialize, Default)]
pub struct SearchTelemetry {
    pub phase1_ms: u64,
    pub phase2_ms: u64,
    pub expanded_nodes: usize,
    pub wikipedia_requests: u64,
    pub cache_hits: u64,
    pub cache_misses: u64,
}

#[derive(Debug, Serialize, Default, Clone)]
pub struct RuntimeMetrics {
    pub total_search_requests: u64,
    pub success_count: u64,
    pub not_found_count: u64,
    pub error_count: u64,
    pub wikipedia_requests: u64,
    pub cache_hits: u64,
    pub cache_misses: u64,
    pub retry_count: u64,
}

#[derive(Default)]
pub struct SearchStats {
    pub expanded_nodes: usize,
}
