export type Health = {
  status: string;
  workspace_root: string;
  config_path: string;
  config_exists: boolean;
  env_exists: boolean;
  qdrant_configured: boolean;
  llm_configured: boolean;
  embedding_configured: boolean;
  runs_dir: string;
};

export type McpSource = {
  enabled?: boolean;
  name: string;
  source_category: string;
  command: string;
  args?: string[];
  cwd?: string;
  query_tool_name: string;
  query_argument_name?: string;
  limit_argument_name?: string;
  result_limit?: number;
  timeout_seconds?: number;
};

export type AppConfig = {
  workspace_root: string;
  runs_dir: string;
  enabled_source_categories: string[];
  connections: {
    mcp_sources: McpSource[];
  };
  ui: {
    default_prompt: string;
  };
};

export type RunSummary = {
  run_id: string;
  run_dir: string;
  prompt: string;
  coverage_status: string;
  sufficient: boolean;
  selected_count: number;
  stop_reason: string;
  response_preview: string;
};

export type EvidenceItem = {
  source_category: string;
  source_id: string;
  snippet: string;
  rank?: number;
  metadata?: Record<string, string>;
};

export type RunDetail = RunSummary & {
  result: Record<string, unknown>;
  evidence: EvidenceItem[];
};

export type TraceEvent = {
  event_type?: string;
  conversation_id?: string;
  created_at?: string;
  payload?: Record<string, unknown>;
};

export type RunTrace = {
  run_id: string;
  retrieval_trace: TraceEvent[];
  orchestration_trace: TraceEvent[];
};

const jsonHeaders = { "Content-Type": "application/json" };

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, init);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(String(payload.error || `Request failed: ${response.status}`));
  }
  return payload as T;
}

export const api = {
  health: () => requestJson<Health>("/health"),
  config: () => requestJson<AppConfig>("/config"),
  saveConfig: (config: AppConfig) =>
    requestJson<AppConfig>("/config", {
      method: "PUT",
      headers: jsonHeaders,
      body: JSON.stringify(config),
    }),
  runs: () => requestJson<{ runs: RunSummary[] }>("/runs"),
  run: (runId: string) => requestJson<RunDetail>(`/runs/${encodeURIComponent(runId)}`),
  trace: (runId: string) => requestJson<RunTrace>(`/runs/${encodeURIComponent(runId)}/trace`),
  retrieve: (payload: { prompt: string; allowed_sources: string[]; run_id?: string }) =>
    requestJson<RunSummary>("/retrieve", {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify(payload),
    }),
  testConnection: (source: McpSource & { test_query?: string }) =>
    requestJson<Record<string, unknown>>("/connections/test", {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify(source),
    }),
};
