use std::cmp::Ordering;
use std::sync::Arc;
use std::time::{Duration, Instant};

use futures::stream::{self, StreamExt};
use rustc_hash::{FxHashMap, FxHashSet};
use tokio::sync::Mutex;

use crate::models::{RuntimeMetrics, SearchStats};
use crate::text::tokenize_title;
use crate::wiki::WikiClient;

type FastMap<K, V> = FxHashMap<K, V>;
type FastSet<T> = FxHashSet<T>;

pub async fn search_bidirectional(
    wiki: &WikiClient,
    metrics: &Arc<Mutex<RuntimeMetrics>>,
    start: &str,
    end: &str,
    time_budget: Duration,
    max_neighbors_per_node: Option<usize>,
    stats: &mut SearchStats,
) -> Option<Vec<String>> {
    let t0 = Instant::now();

    let mut fwd_front: FastSet<String> = FastSet::default();
    fwd_front.insert(start.to_string());
    let mut bwd_front: FastSet<String> = FastSet::default();
    bwd_front.insert(end.to_string());

    let mut prev_fwd: FastMap<String, Option<String>> = FastMap::default();
    let mut prev_bwd: FastMap<String, Option<String>> = FastMap::default();
    prev_fwd.insert(start.to_string(), None);
    prev_bwd.insert(end.to_string(), None);

    let mut dist_fwd: FastMap<String, usize> = FastMap::default();
    let mut dist_bwd: FastMap<String, usize> = FastMap::default();
    dist_fwd.insert(start.to_string(), 0);
    dist_bwd.insert(end.to_string(), 0);

    let mut best_len = usize::MAX;
    let mut meet: Option<String> = None;

    let end_tokens = tokenize_title(end);
    let start_tokens = tokenize_title(start);
    let mut token_cache: FastMap<String, FastSet<String>> = FastMap::default();

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

            let mut next_front: FastSet<String> = FastSet::default();
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

            let mut next_front: FastSet<String> = FastSet::default();
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

fn adaptive_neighbor_cap(base: Option<usize>, depth: usize) -> Option<usize> {
    base.map(|max| {
        let scaled = (max as f64 / (1.0 + depth as f64 * 0.35)).round() as usize;
        scaled.clamp(25, max)
    })
}

fn rank_neighbors(
    neighbors: Vec<String>,
    target_tokens: &FastSet<String>,
    target_title: &str,
    max_neighbors: Option<usize>,
    token_cache: &mut FastMap<String, FastSet<String>>,
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
    let mut scored: Vec<(String, (i32, i32, i32))> = neighbors
        .into_iter()
        .map(|title| {
            let score = neighbor_score(&title, target_tokens, &target_lc, token_cache);
            (title, score)
        })
        .collect();

    if scored.len() > limit {
        scored.select_nth_unstable_by(limit, |a, b| compare_scores_desc(a.1, b.1));
        scored.truncate(limit);
    }

    scored.sort_unstable_by(|a, b| compare_scores_desc(a.1, b.1));
    scored.into_iter().map(|(title, _)| title).collect()
}

fn neighbor_score(
    title: &str,
    target_tokens: &FastSet<String>,
    target_lc: &str,
    token_cache: &mut FastMap<String, FastSet<String>>,
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

fn find_intersection(left: &FastSet<String>, right: &FastSet<String>) -> Option<String> {
    if left.len() <= right.len() {
        left.iter().find(|node| right.contains(*node)).cloned()
    } else {
        right.iter().find(|node| left.contains(*node)).cloned()
    }
}

fn min_distance(front: &FastSet<String>, dist: &FastMap<String, usize>) -> usize {
    front
        .iter()
        .filter_map(|node| dist.get(node))
        .copied()
        .min()
        .unwrap_or(usize::MAX / 2)
}

fn reconstruct_path(
    prev_fwd: &FastMap<String, Option<String>>,
    prev_bwd: &FastMap<String, Option<String>>,
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
