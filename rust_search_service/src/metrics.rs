use std::sync::Arc;

use tokio::sync::Mutex;

use crate::models::RuntimeMetrics;

pub async fn bump_metric(
    metrics: &Arc<Mutex<RuntimeMetrics>>,
    update: impl FnOnce(&mut RuntimeMetrics),
) {
    let mut guard = metrics.lock().await;
    update(&mut guard);
}
