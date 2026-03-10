use std::sync::Arc;
use std::time::Duration;

use lru::LruCache;
use reqwest::Client;
use tokio::sync::{Mutex, Semaphore};

use crate::metrics::bump_metric;
use crate::models::RuntimeMetrics;
use crate::text::normalize_title;
use crate::wikipedia_api::{dedupe, fetch_backlinks_uncached, fetch_links_uncached};

#[derive(Clone)]
pub struct WikiClient {
    client: Client,
    links_cache: Arc<Mutex<LruCache<String, Arc<Vec<String>>>>>,
    backlinks_cache: Arc<Mutex<LruCache<String, Arc<Vec<String>>>>>,
    request_gate: Arc<Semaphore>,
    cache_size: usize,
    retries: usize,
}

impl WikiClient {
    pub fn new(client: Client, cache_size: usize, max_concurrency: usize, retries: usize) -> Self {
        Self {
            client,
            links_cache: Arc::new(Mutex::new(LruCache::unbounded())),
            backlinks_cache: Arc::new(Mutex::new(LruCache::unbounded())),
            request_gate: Arc::new(Semaphore::new(max_concurrency)),
            cache_size,
            retries,
        }
    }

    pub async fn fetch_links(
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

    pub async fn fetch_backlinks(
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
