use std::cmp::Ordering;
use std::collections::{HashMap, HashSet};
use std::sync::Arc;
use std::time::{Duration, Instant};

use axum::extract::State;
use axum::routing::{get, post};
use axum::{Json, Router};
use futures::stream::{self, StreamExt};
use lru::LruCache;
use once_cell::sync::Lazy;
use regex::Regex;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use tokio::sync::{Mutex, Semaphore};

static TOKEN_RE: Lazy<Regex> = Lazy::new(|| Regex::new(r"[\w\-]+").expect("token regex build failed"));

#[derive(Clone)]
struct AppState {
    wiki: WikiClient,
    metrics: Arc<Mutex<RuntimeMetrics>>,
}

#[derive(Clone)]
struct WikiClient {
    client: Client,
    links_cache: Arc<Mutex<LruCache<String, Arc<Vec<String>>>>>,
    backlinks_cache: Arc<Mutex<LruCache<String, Arc<Vec<String>>>>>,
    request_gate: Arc<Semaphore>,
    cache_size: usize,
    retries: usize,
}

#[derive(Debug, Deserialize)]
struct SearchRequest {
    start_article: String,
    end_article: String,
    time_limit: Option<u64>,
}

#[derive(Debug, Serialize)]
struct SearchResponse {
    path: Option<Vec<String>>,
    elapsed_time: f64,
    error: Option<String>,
    steps_count: usize,
    telemetry: SearchTelemetry,
}

#[derive(Debug, Serialize, Default)]
struct SearchTelemetry {
    phase1_ms: u64,
    phase2_ms: u64,
    expanded_nodes: usize,
    wikipedia_requests: u64,
    cache_hits: u64,
    cache_misses: u64,
}

#[derive(Debug, Serialize, Default, Clone)]
struct RuntimeMetrics {
    total_search_requests: u64,
    success_count: u64,
    not_found_count: u64,
    error_count: u64,
    wikipedia_requests: u64,
    cache_hits: u64,
    cache_misses: u64,
    retry_count: u64,
}

#[derive(Default)]
struct SearchStats {
    expanded_nodes: usize,
}

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

    axum::serve(listener, app)
        .await
        .expect("server crashed");
}

impl WikiClient {
    fn new(client: Client, cache_size: usize, max_concurrency: usize, retries: usize) -> Self {
        Self {
            client,
            links_cache: Arc::new(Mutex::new(LruCache::unbounded())),
            backlinks_cache: Arc::new(Mutex::new(LruCache::unbounded())),
            request_gate: Arc::new(Semaphore::new(max_concurrency)),
            cache_size,
            retries,
        }
    }

    async fn fetch_links(
        &self,
        title: &str,
        metrics: &Arc<Mutex<RuntimeMetrics>>,
    ) -> Vec<String> {
        self.fetch_with_cache(
            title,
            &self.links_cache,
            metrics,
            |client, page| async move { fetch_links_uncached(client, page).await },
        )
        .await
    }

    async fn fetch_backlinks(
        &self,
        title: &str,
        metrics: &Arc<Mutex<RuntimeMetrics>>,
    ) -> Vec<String> {
        self.fetch_with_cache(
            title,
            &self.backlinks_cache,
            metrics,
            |client, page| async move { fetch_backlinks_uncached(client, page).await },
        )
        .await
    }

    async fn fetch_with_cache<F, Fut>(
        &self,
        key: &str,
        cache: &Arc<Mutex<LruCache<String, Arc<Vec<String>>>>>,
        metrics: &Arc<Mutex<RuntimeMetrics>>,
        do_fetch: F,
    ) -> Vec<String>
    where
        F: Fn(Client, String) -> Fut + Send + Sync,
        Fut: std::future::Future<Output = Result<Vec<String>, reqwest::Error>> + Send,
    {
        let title = normalize_title(key);
        if title.is_empty() {
            return Vec::new();
        }

        {
            let mut guard = cache.lock().await;
            if let Some(value) = guard.get(&title) {
                bump_metric(metrics, |m| m.cache_hits += 1).await;
                return (**value).clone();
            }
        }

        bump_metric(metrics, |m| m.cache_misses += 1).await;

        let _permit = self
            .request_gate
            .clone()
            .acquire_owned()
            .await
            .expect("semaphore closed unexpectedly");

        let mut backoff = Duration::from_millis(200);
        let mut last_ok: Vec<String> = Vec::new();

        for attempt in 0..self.retries {
            bump_metric(metrics, |m| m.wikipedia_requests += 1).await;
            let result = do_fetch(self.client.clone(), title.clone()).await;
            match result {
                Ok(items) => {
                    last_ok = dedupe(items);
                    break;
                }
                Err(_) => {
                    if attempt + 1 == self.retries {
                        break;
                    }
                    bump_metric(metrics, |m| m.retry_count += 1).await;
                    tokio::time::sleep(backoff).await;
                    backoff = (backoff * 2).min(Duration::from_secs(2));
                }
            }
        }

        {
            let mut guard = cache.lock().await;
            guard.put(title, Arc::new(last_ok.clone()));
            while guard.len() > self.cache_size {
                guard.pop_lru();
            }
        }

        last_ok
    }
}

async fn health() -> Json<Value> {
    Json(json!({ "status": "ok" }))
}

async fn metrics(State(state): State<AppState>) -> Json<RuntimeMetrics> {
    Json(state.metrics.lock().await.clone())
}

async fn search(State(state): State<AppState>, Json(payload): Json<SearchRequest>) -> Json<SearchResponse> {
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
        telemetry.wikipedia_requests = after.wikipedia_requests.saturating_sub(before.wikipedia_requests);
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
    telemetry.wikipedia_requests = after.wikipedia_requests.saturating_sub(before.wikipedia_requests);
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

async fn search_bidirectional(
    wiki: &WikiClient,
    metrics: &Arc<Mutex<RuntimeMetrics>>,
    start: &str,
    end: &str,
    time_budget: Duration,
    max_neighbors_per_node: Option<usize>,
    stats: &mut SearchStats,
) -> Option<Vec<String>> {
    let t0 = Instant::now();

    let mut fwd_front: HashSet<String> = HashSet::from([start.to_string()]);
    let mut bwd_front: HashSet<String> = HashSet::from([end.to_string()]);

    let mut prev_fwd: HashMap<String, Option<String>> = HashMap::new();
    let mut prev_bwd: HashMap<String, Option<String>> = HashMap::new();
    prev_fwd.insert(start.to_string(), None);
    prev_bwd.insert(end.to_string(), None);

    let mut dist_fwd: HashMap<String, usize> = HashMap::new();
    let mut dist_bwd: HashMap<String, usize> = HashMap::new();
    dist_fwd.insert(start.to_string(), 0);
    dist_bwd.insert(end.to_string(), 0);

    let mut best_len = usize::MAX;
    let mut meet: Option<String> = None;

    let end_tokens = tokenize_title(end);
    let start_tokens = tokenize_title(start);
    let mut token_cache: HashMap<String, HashSet<String>> = HashMap::new();

    while !fwd_front.is_empty() && !bwd_front.is_empty() && t0.elapsed() < time_budget {
        if let Some(border_node) = find_intersection(&fwd_front, &bwd_front) {
            return Some(reconstruct_path(&prev_fwd, &prev_bwd, &border_node));
        }

        let min_f = min_distance(&fwd_front, &dist_fwd);
        let min_b = min_distance(&bwd_front, &dist_bwd);
        if min_f.saturating_add(min_b) >= best_len {
            break;
        }

        let expand_fwd = fwd_front.len() <= bwd_front.len();
        if expand_fwd {
            let current_front: Vec<String> = fwd_front.iter().cloned().collect();
            let responses: Vec<(String, Vec<String>)> = stream::iter(current_front.into_iter())
                .map(|node| async move {
                    let links = wiki.fetch_links(&node, metrics).await;
                    (node, links)
                })
                .buffer_unordered(24)
                .collect()
                .await;

            let mut next_front: HashSet<String> = HashSet::new();
            for (node, neighbors) in responses {
                stats.expanded_nodes += 1;
                let d = *dist_fwd.get(&node).unwrap_or(&0);
                let ranked_neighbors = rank_neighbors(
                    neighbors,
                    &end_tokens,
                    end,
                    adaptive_neighbor_cap(max_neighbors_per_node, d),
                    &mut token_cache,
                );
                for nbr in ranked_neighbors {
                    if !dist_fwd.contains_key(&nbr) {
                        dist_fwd.insert(nbr.clone(), d + 1);
                        prev_fwd.insert(nbr.clone(), Some(node.clone()));

                        if let Some(back_d) = dist_bwd.get(&nbr) {
                            let total = d + 1 + *back_d;
                            if total < best_len {
                                best_len = total;
                                meet = Some(nbr.clone());
                            }
                        }
                        next_front.insert(nbr);
                    }
                }
            }
            fwd_front = next_front;
        } else {
            let current_front: Vec<String> = bwd_front.iter().cloned().collect();
            let responses: Vec<(String, Vec<String>)> = stream::iter(current_front.into_iter())
                .map(|node| async move {
                    let backlinks = wiki.fetch_backlinks(&node, metrics).await;
                    (node, backlinks)
                })
                .buffer_unordered(24)
                .collect()
                .await;

            let mut next_front: HashSet<String> = HashSet::new();
            for (node, neighbors) in responses {
                stats.expanded_nodes += 1;
                let d = *dist_bwd.get(&node).unwrap_or(&0);
                let ranked_neighbors = rank_neighbors(
                    neighbors,
                    &start_tokens,
                    start,
                    adaptive_neighbor_cap(max_neighbors_per_node, d),
                    &mut token_cache,
                );
                for nbr in ranked_neighbors {
                    if !dist_bwd.contains_key(&nbr) {
                        dist_bwd.insert(nbr.clone(), d + 1);
                        prev_bwd.insert(nbr.clone(), Some(node.clone()));

                        if let Some(front_d) = dist_fwd.get(&nbr) {
                            let total = d + 1 + *front_d;
                            if total < best_len {
                                best_len = total;
                                meet = Some(nbr.clone());
                            }
                        }
                        next_front.insert(nbr);
                    }
                }
            }
            bwd_front = next_front;
        }
    }

    meet.map(|node| reconstruct_path(&prev_fwd, &prev_bwd, &node))
}

fn normalize_title(value: &str) -> String {
    value
        .trim()
        .replace('_', " ")
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
}

fn tokenize_title(title: &str) -> HashSet<String> {
    TOKEN_RE
        .find_iter(&title.to_lowercase())
        .map(|m| m.as_str().to_string())
        .filter(|token| token.len() > 2)
        .collect()
}

fn adaptive_neighbor_cap(base: Option<usize>, depth: usize) -> Option<usize> {
    base.map(|max| {
        let scaled = (max as f64 / (1.0 + depth as f64 * 0.35)).round() as usize;
        scaled.clamp(25, max)
    })
}

fn rank_neighbors(
    neighbors: Vec<String>,
    target_tokens: &HashSet<String>,
    target_title: &str,
    max_neighbors: Option<usize>,
    token_cache: &mut HashMap<String, HashSet<String>>,
) -> Vec<String> {
    if neighbors.is_empty() {
        return neighbors;
    }

    let Some(limit) = max_neighbors else {
        return neighbors;
    };

    if neighbors.len() <= limit {
        return neighbors;
    }

    let target_lc = target_title.to_lowercase();
    let mut ranked = neighbors;

    ranked.sort_by(|a, b| {
        let a_score = neighbor_score(a, target_tokens, &target_lc, token_cache);
        let b_score = neighbor_score(b, target_tokens, &target_lc, token_cache);
        compare_scores_desc(a_score, b_score)
    });

    ranked.truncate(limit);
    ranked
}

fn neighbor_score(
    title: &str,
    target_tokens: &HashSet<String>,
    target_lc: &str,
    token_cache: &mut HashMap<String, HashSet<String>>,
) -> (i32, i32, i32) {
    let title_lc = title.to_lowercase();
    let cached_tokens = token_cache
        .entry(title_lc.clone())
        .or_insert_with(|| tokenize_title(&title_lc));
    let overlap = cached_tokens.intersection(target_tokens).count() as i32;
    let contains_target = if !target_lc.is_empty() && title_lc.contains(target_lc) {
        1
    } else {
        0
    };

    (contains_target, overlap, -(title_lc.len() as i32))
}

fn compare_scores_desc(a: (i32, i32, i32), b: (i32, i32, i32)) -> Ordering {
    b.cmp(&a)
}

fn find_intersection(left: &HashSet<String>, right: &HashSet<String>) -> Option<String> {
    if left.len() <= right.len() {
        left.iter().find(|node| right.contains(*node)).cloned()
    } else {
        right.iter().find(|node| left.contains(*node)).cloned()
    }
}

fn min_distance(front: &HashSet<String>, dist: &HashMap<String, usize>) -> usize {
    front
        .iter()
        .filter_map(|node| dist.get(node))
        .copied()
        .min()
        .unwrap_or(usize::MAX / 2)
}

fn reconstruct_path(
    prev_fwd: &HashMap<String, Option<String>>,
    prev_bwd: &HashMap<String, Option<String>>,
    meet_node: &str,
) -> Vec<String> {
    let mut path_front: Vec<String> = Vec::new();
    let mut node: Option<String> = Some(meet_node.to_string());

    while let Some(current) = node {
        path_front.push(current.clone());
        node = prev_fwd.get(&current).cloned().flatten();
    }

    path_front.reverse();

    let mut path_back: Vec<String> = Vec::new();
    let mut node = prev_bwd.get(meet_node).cloned().flatten();
    while let Some(current) = node {
        path_back.push(current.clone());
        node = prev_bwd.get(&current).cloned().flatten();
    }

    path_front.extend(path_back);
    path_front
}

async fn fetch_links_uncached(client: Client, title: String) -> Result<Vec<String>, reqwest::Error> {
    let mut plcontinue: Option<String> = None;
    let mut out: Vec<String> = Vec::new();

    loop {
        let mut params: Vec<(&str, String)> = vec![
            ("action", "query".to_string()),
            ("format", "json".to_string()),
            ("formatversion", "2".to_string()),
            ("titles", title.clone()),
            ("prop", "links".to_string()),
            ("plnamespace", "0".to_string()),
            ("pllimit", "max".to_string()),
        ];
        if let Some(token) = &plcontinue {
            params.push(("plcontinue", token.clone()));
        }

        let data = client
            .get("https://ru.wikipedia.org/w/api.php")
            .query(&params)
            .send()
            .await?
            .json::<Value>()
            .await?;

        if let Some(pages) = data
            .get("query")
            .and_then(|q| q.get("pages"))
            .and_then(|p| p.as_array())
        {
            for page in pages {
                if let Some(links) = page.get("links").and_then(|l| l.as_array()) {
                    for link in links {
                        if let Some(link_title) = link.get("title").and_then(|t| t.as_str()) {
                            out.push(link_title.to_string());
                        }
                    }
                }
            }
        }

        plcontinue = data
            .get("continue")
            .and_then(|c| c.get("plcontinue"))
            .and_then(|v| v.as_str())
            .map(ToOwned::to_owned);

        if plcontinue.is_none() {
            break;
        }
    }

    Ok(out)
}

async fn fetch_backlinks_uncached(client: Client, title: String) -> Result<Vec<String>, reqwest::Error> {
    let mut blcontinue: Option<String> = None;
    let mut out: Vec<String> = Vec::new();

    loop {
        let mut params: Vec<(&str, String)> = vec![
            ("action", "query".to_string()),
            ("format", "json".to_string()),
            ("formatversion", "2".to_string()),
            ("list", "backlinks".to_string()),
            ("bltitle", title.clone()),
            ("blnamespace", "0".to_string()),
            ("bllimit", "max".to_string()),
        ];
        if let Some(token) = &blcontinue {
            params.push(("blcontinue", token.clone()));
        }

        let data = client
            .get("https://ru.wikipedia.org/w/api.php")
            .query(&params)
            .send()
            .await?
            .json::<Value>()
            .await?;

        if let Some(backlinks) = data
            .get("query")
            .and_then(|q| q.get("backlinks"))
            .and_then(|b| b.as_array())
        {
            for backlink in backlinks {
                if let Some(backlink_title) = backlink.get("title").and_then(|t| t.as_str()) {
                    out.push(backlink_title.to_string());
                }
            }
        }

        blcontinue = data
            .get("continue")
            .and_then(|c| c.get("blcontinue"))
            .and_then(|v| v.as_str())
            .map(ToOwned::to_owned);

        if blcontinue.is_none() {
            break;
        }
    }

    Ok(out)
}

fn dedupe(items: Vec<String>) -> Vec<String> {
    let mut seen: HashSet<String> = HashSet::new();
    let mut out: Vec<String> = Vec::new();
    for item in items {
        if seen.insert(item.clone()) {
            out.push(item);
        }
    }
    out
}

async fn bump_metric(metrics: &Arc<Mutex<RuntimeMetrics>>, update: impl FnOnce(&mut RuntimeMetrics)) {
    let mut guard = metrics.lock().await;
    update(&mut guard);
}
