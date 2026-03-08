use std::cmp::Ordering;
use std::collections::{HashMap, HashSet};
use std::time::{Duration, Instant};

use axum::extract::State;
use axum::routing::{get, post};
use axum::{Json, Router};
use futures::stream::{self, StreamExt};
use once_cell::sync::Lazy;
use regex::Regex;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

static TOKEN_RE: Lazy<Regex> = Lazy::new(|| Regex::new(r"[\w\-]+").expect("token regex build failed"));

#[derive(Clone)]
struct AppState {
    client: Client,
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
}

#[tokio::main]
async fn main() {
    let client = Client::builder()
        .user_agent("wiki-path-finder-rust/0.1")
        .timeout(Duration::from_secs(12))
        .build()
        .expect("failed to build reqwest client");

    let state = AppState { client };

    let app = Router::new()
        .route("/health", get(health))
        .route("/search", post(search))
        .with_state(state);

    let listener = tokio::net::TcpListener::bind("0.0.0.0:8081")
        .await
        .expect("failed to bind 0.0.0.0:8081");

    axum::serve(listener, app)
        .await
        .expect("server crashed");
}

async fn health() -> Json<Value> {
    Json(json!({ "status": "ok" }))
}

async fn search(State(state): State<AppState>, Json(payload): Json<SearchRequest>) -> Json<SearchResponse> {
    let started = Instant::now();

    let start_article = normalize_title(&payload.start_article);
    let end_article = normalize_title(&payload.end_article);

    if start_article.is_empty() || end_article.is_empty() {
        return Json(SearchResponse {
            path: None,
            elapsed_time: started.elapsed().as_secs_f64(),
            error: Some("start_article and end_article must not be empty".to_string()),
            steps_count: 0,
        });
    }

    if start_article == end_article {
        return Json(SearchResponse {
            path: Some(vec![start_article]),
            elapsed_time: started.elapsed().as_secs_f64(),
            error: None,
            steps_count: 1,
        });
    }

    let time_limit = payload.time_limit.unwrap_or(30).max(1);
    let fast_budget = Duration::from_secs_f64((time_limit as f64 * 0.6).min(10.0));

    let fast_path = search_bidirectional(
        &state.client,
        &start_article,
        &end_article,
        fast_budget,
        Some(120),
    )
    .await;

    if let Some(path) = fast_path {
        let steps_count = path.len();
        return Json(SearchResponse {
            path: Some(path),
            elapsed_time: started.elapsed().as_secs_f64(),
            error: None,
            steps_count,
        });
    }

    let spent = started.elapsed();
    if spent >= Duration::from_secs(time_limit) {
        return Json(SearchResponse {
            path: None,
            elapsed_time: spent.as_secs_f64(),
            error: None,
            steps_count: 0,
        });
    }

    let remaining = Duration::from_secs(time_limit).saturating_sub(spent);
    let exact_path = search_bidirectional(
        &state.client,
        &start_article,
        &end_article,
        remaining,
        None,
    )
    .await;

    if let Some(path) = exact_path {
        let steps_count = path.len();
        return Json(SearchResponse {
            path: Some(path),
            elapsed_time: started.elapsed().as_secs_f64(),
            error: None,
            steps_count,
        });
    }

    Json(SearchResponse {
        path: None,
        elapsed_time: started.elapsed().as_secs_f64(),
        error: None,
        steps_count: 0,
    })
}

async fn search_bidirectional(
    client: &Client,
    start: &str,
    end: &str,
    time_budget: Duration,
    max_neighbors_per_node: Option<usize>,
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
                    let links = fetch_links(client, &node).await.unwrap_or_default();
                    (node, links)
                })
                .buffer_unordered(24)
                .collect()
                .await;

            let mut next_front: HashSet<String> = HashSet::new();
            for (node, neighbors) in responses {
                let ranked_neighbors = rank_neighbors(
                    neighbors,
                    &end_tokens,
                    end,
                    max_neighbors_per_node,
                );
                let d = *dist_fwd.get(&node).unwrap_or(&0);
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
                    let backlinks = fetch_backlinks(client, &node).await.unwrap_or_default();
                    (node, backlinks)
                })
                .buffer_unordered(24)
                .collect()
                .await;

            let mut next_front: HashSet<String> = HashSet::new();
            for (node, neighbors) in responses {
                let ranked_neighbors = rank_neighbors(
                    neighbors,
                    &start_tokens,
                    start,
                    max_neighbors_per_node,
                );
                let d = *dist_bwd.get(&node).unwrap_or(&0);
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

    if let Some(node) = meet {
        return Some(reconstruct_path(&prev_fwd, &prev_bwd, &node));
    }

    None
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

fn rank_neighbors(
    neighbors: Vec<String>,
    target_tokens: &HashSet<String>,
    target_title: &str,
    max_neighbors: Option<usize>,
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
        let a_score = neighbor_score(a, target_tokens, &target_lc);
        let b_score = neighbor_score(b, target_tokens, &target_lc);
        compare_scores_desc(a_score, b_score)
    });

    ranked.truncate(limit);
    ranked
}

fn neighbor_score(title: &str, target_tokens: &HashSet<String>, target_lc: &str) -> (i32, i32, i32) {
    let title_lc = title.to_lowercase();
    let title_tokens = tokenize_title(&title_lc);
    let overlap = title_tokens.intersection(target_tokens).count() as i32;
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

async fn fetch_links(client: &Client, title: &str) -> Result<Vec<String>, reqwest::Error> {
    let mut plcontinue: Option<String> = None;
    let mut out: Vec<String> = Vec::new();

    loop {
        let mut params: Vec<(&str, String)> = vec![
            ("action", "query".to_string()),
            ("format", "json".to_string()),
            ("formatversion", "2".to_string()),
            ("titles", title.to_string()),
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
                        if let Some(title) = link.get("title").and_then(|t| t.as_str()) {
                            out.push(title.to_string());
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

async fn fetch_backlinks(client: &Client, title: &str) -> Result<Vec<String>, reqwest::Error> {
    let mut blcontinue: Option<String> = None;
    let mut out: Vec<String> = Vec::new();

    loop {
        let mut params: Vec<(&str, String)> = vec![
            ("action", "query".to_string()),
            ("format", "json".to_string()),
            ("formatversion", "2".to_string()),
            ("list", "backlinks".to_string()),
            ("bltitle", title.to_string()),
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
                if let Some(title) = backlink.get("title").and_then(|t| t.as_str()) {
                    out.push(title.to_string());
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
