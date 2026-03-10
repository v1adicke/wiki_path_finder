use std::time::{Duration, Instant};

use axum::extract::State;
use axum::Json;
use serde_json::{json, Value};

use crate::metrics::bump_metric;
use crate::models::{
    AppState, RuntimeMetrics, SearchRequest, SearchResponse, SearchStats, SearchTelemetry,
};
use crate::search::search_bidirectional;
use crate::text::normalize_title;

pub async fn health() -> Json<Value> {
    Json(json!({ "status": "ok" }))
}

pub async fn metrics(State(state): State<AppState>) -> Json<RuntimeMetrics> {
    Json(state.metrics.lock().await.clone())
}

pub async fn search(
    State(state): State<AppState>,
    Json(payload): Json<SearchRequest>,
) -> Json<SearchResponse> {
    let started = Instant::now();
    bump_metric(&state.metrics, |m| m.total_search_requests += 1).await;

    let start_article = normalize_title(&payload.start_article);
    let end_article = normalize_title(&payload.end_article);

    let mut telemetry = SearchTelemetry::default();

    if start_article.is_empty() || end_article.is_empty() {
        bump_metric(&state.metrics, |m| m.error_count += 1).await;
        return Json(SearchResponse {
            path: None,
            elapsed_time: started.elapsed().as_secs_f64(),
            error: Some("start_article and end_article must not be empty".to_string()),
            steps_count: 0,
            telemetry,
        });
    }

    if start_article == end_article {
        bump_metric(&state.metrics, |m| m.success_count += 1).await;
        return Json(SearchResponse {
            path: Some(vec![start_article]),
            elapsed_time: started.elapsed().as_secs_f64(),
            error: None,
            steps_count: 1,
            telemetry,
        });
    }

    let before = state.metrics.lock().await.clone();
    let time_limit = payload.time_limit.unwrap_or(30).max(1);
    let fast_budget = Duration::from_secs_f64((time_limit as f64 * 0.6).min(10.0));

    let t_fast = Instant::now();
    let mut phase_stats = SearchStats::default();
    let fast_path = search_bidirectional(
        &state.wiki,
        &state.metrics,
        &start_article,
        &end_article,
        fast_budget,
        Some(120),
        &mut phase_stats,
    )
    .await;
    telemetry.phase1_ms = t_fast.elapsed().as_millis() as u64;

    if let Some(path) = fast_path {
        telemetry.expanded_nodes = phase_stats.expanded_nodes;
        let after = state.metrics.lock().await.clone();
        telemetry.wikipedia_requests = after
            .wikipedia_requests
            .saturating_sub(before.wikipedia_requests);
        telemetry.cache_hits = after.cache_hits.saturating_sub(before.cache_hits);
        telemetry.cache_misses = after.cache_misses.saturating_sub(before.cache_misses);
        let steps_count = path.len();
        bump_metric(&state.metrics, |m| m.success_count += 1).await;
        return Json(SearchResponse {
            path: Some(path),
            elapsed_time: started.elapsed().as_secs_f64(),
            error: None,
            steps_count,
            telemetry,
        });
    }

    let spent = started.elapsed();
    if spent >= Duration::from_secs(time_limit) {
        bump_metric(&state.metrics, |m| m.not_found_count += 1).await;
        return Json(SearchResponse {
            path: None,
            elapsed_time: spent.as_secs_f64(),
            error: None,
            steps_count: 0,
            telemetry,
        });
    }

    let remaining = Duration::from_secs(time_limit).saturating_sub(spent);
    let t_exact = Instant::now();
    let exact_path = search_bidirectional(
        &state.wiki,
        &state.metrics,
        &start_article,
        &end_article,
        remaining,
        None,
        &mut phase_stats,
    )
    .await;
    telemetry.phase2_ms = t_exact.elapsed().as_millis() as u64;
    telemetry.expanded_nodes = phase_stats.expanded_nodes;

    let after = state.metrics.lock().await.clone();
    telemetry.wikipedia_requests = after
        .wikipedia_requests
        .saturating_sub(before.wikipedia_requests);
    telemetry.cache_hits = after.cache_hits.saturating_sub(before.cache_hits);
    telemetry.cache_misses = after.cache_misses.saturating_sub(before.cache_misses);

    if let Some(path) = exact_path {
        let steps_count = path.len();
        bump_metric(&state.metrics, |m| m.success_count += 1).await;
        return Json(SearchResponse {
            path: Some(path),
            elapsed_time: started.elapsed().as_secs_f64(),
            error: None,
            steps_count,
            telemetry,
        });
    }

    bump_metric(&state.metrics, |m| m.not_found_count += 1).await;
    Json(SearchResponse {
        path: None,
        elapsed_time: started.elapsed().as_secs_f64(),
        error: None,
        steps_count: 0,
        telemetry,
    })
}
