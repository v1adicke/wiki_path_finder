export interface SearchResult {
  path: string[] | null;
  elapsed_time: number;
  error: string | null;
  steps_count: number;
}

interface ApiErrorPayload {
  detail?: string;
}

export type SearchStatus = "idle" | "heuristic" | "exact" | "done" | "error";

export interface SearchProgress {
  status: SearchStatus;
  result?: SearchResult;
}

export interface DifficultyStats {
  total: number;
  success_rate: number;
  avg_time: number;
}

export interface BenchmarkResult {
  case_id: string;
  start: string;
  end: string;
  difficulty: string;
  elapsed_sec: number;
  success: boolean;
  path_len: number;
  status: string;
  error: string | null;
}

export interface DashboardMetrics {
  generated_at: string;
  total_cases: number;
  success_count: number;
  success_rate: number;
  avg_time: number;
  median_time: number;
  p90_time: number;
  p95_time: number;
  max_time: number;
  avg_path_len_success: number;
  status_counts: Record<string, number>;
  difficulty_stats: Record<string, DifficultyStats>;
  results: BenchmarkResult[];
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
export async function startSearch(
  start: string,
  end: string,
  onProgress?: (progress: SearchProgress) => void
): Promise<SearchResult> {
  onProgress?.({ status: "heuristic" });
  onProgress?.({ status: "exact" });

  const response = await fetch(`${API_BASE_URL}/api/search`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      start_article: start,
      end_article: end,
    }),
  });

  if (!response.ok) {
    let detail = "";
    try {
      const payload = (await response.json()) as ApiErrorPayload;
      detail = payload.detail ? `: ${payload.detail}` : "";
    } catch {
      // Keep a compact fallback if response body is not JSON.
    }
    throw new Error(`Search request failed with status ${response.status}${detail}`);
  }

  const result = (await response.json()) as SearchResult;

  if (result.error) {
    onProgress?.({ status: "error", result });
    return result;
  }

  onProgress?.({ status: "done", result });
  return result;
}

export async function fetchDashboardMetrics(): Promise<DashboardMetrics> {
  const response = await fetch(`${API_BASE_URL}/api/metrics`);
  if (!response.ok) {
    throw new Error(`Metrics request failed with status ${response.status}`);
  }
  return (await response.json()) as DashboardMetrics;
}
