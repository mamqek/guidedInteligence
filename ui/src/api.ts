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
  index_estimate?: IndexEstimate;
  qdrant_reachable?: boolean;
  qdrant_status_detail?: string;
  github_repository?: string;
};

export type WorkspaceEntry = {
  workspace_root: string;
  name: string;
  last_opened_at?: string;
  exists: boolean;
  current?: boolean;
};

export type McpSource = {
  enabled?: boolean;
  name: string;
  source_category: string;
  source_key?: string;
  command: string;
  args?: string[];
  env?: Record<string, string>;
  cwd?: string;
  query_tool_name: string;
  query_argument_name?: string;
  limit_argument_name?: string;
  result_limit?: number;
  timeout_seconds?: number;
  min_score?: number;
  static_tool_arguments?: Record<string, string>;
  score_fields?: string[];
  id_fields?: string[];
  title_fields?: string[];
  content_fields?: string[];
};

export type RemoteMcpSource = {
  enabled?: boolean;
  name: string;
  provider: string;
  title?: string;
  source_category: string;
  source_key?: string;
  endpoint_url: string;
  auth_type?: string;
  bearer_token?: string;
  oauth_access_token?: string;
  api_key?: string;
  api_key_header?: string;
  oauth_authorize_url?: string;
  headers?: Record<string, string>;
  scope?: string;
  features?: Record<string, boolean>;
  query_tool_name: string;
  fetch_tool_name?: string;
  query_argument_name?: string;
  limit_argument_name?: string;
  result_limit?: number;
  enrich_results?: boolean;
  enrich_limit?: number;
  timeout_seconds?: number;
  min_score?: number;
  static_tool_arguments?: Record<string, string>;
  score_fields?: string[];
  id_fields?: string[];
  title_fields?: string[];
  content_fields?: string[];
};

export type ProviderAuthState = {
  auth_type?: string;
  connected?: boolean;
  oauth_access_token_configured?: boolean;
  bearer_token_configured?: boolean;
  api_key_configured?: boolean;
  api_key_header?: string;
  updated_at?: string;
};

export type ProviderAuthConnectPayload = {
  provider: string;
  endpoint_url: string;
  scope?: string;
};

export type ProviderAuthPayload = {
  provider: string;
  auth_type: string;
  bearer_token?: string;
  api_key?: string;
  api_key_header?: string;
};

export type AppConfig = {
  workspace_root: string;
  runs_dir: string;
  enabled_source_categories: string[];
  enabled_sources: string[];
  indexing: {
    enable_indexing: boolean;
    exclude_paths: string[];
  };
  retrieval: {
    mode: "workspace" | "codex";
    codex_command: string[];
    codex_model: string;
    codex_timeout_seconds: number;
  };
  connections: {
    remote_mcp_sources?: RemoteMcpSource[];
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
  status?: string;
  phase?: string;
  coverage_status: string;
  sufficient: boolean;
  selected_count: number;
  stop_reason: string;
  response_preview: string;
  index_estimate?: IndexEstimate;
  progress_percent?: number;
  progress_message?: string;
  progress_logs?: string[];
  created_at?: string;
  completed_at?: string;
  elapsed_seconds?: number | null;
  token_usage?: TokenUsage;
};

export type TokenUsage = {
  request_count: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cached_tokens: number;
  reasoning_tokens: number;
};

export type IndexEstimate = {
  file_count: number;
  total_bytes: number;
  estimated_chunks: number;
  estimated_seconds_min?: number;
  estimated_seconds_max?: number;
  cgc_estimated_seconds_min?: number;
  cgc_estimated_seconds_max?: number;
  cgc_full_estimated_seconds_min?: number;
  cgc_full_estimated_seconds_max?: number;
  cgc_skip_external_estimated_seconds_min?: number;
  cgc_skip_external_estimated_seconds_max?: number;
  cgc_timeout_risk?: boolean;
  index_estimate_notes?: string[];
  sample_paths: string[];
  exclude_paths: string[];
  enable_indexing: boolean;
  index_ready?: boolean;
  index_status?: string;
  index_status_detail?: string;
  index_last_built_at?: string;
};

export type IndexPrepareJob = {
  job_id: string;
  status: string;
  phase: string;
  message: string;
  progress_percent: number;
  started_at: string;
  completed_at: string;
  elapsed_seconds: number;
  workspace_root: string;
  index_dir: string;
  document_count: number;
  index_estimate: IndexEstimate;
  logs: string[];
};

export type UnderstandingCheck = {
  id: string;
  role: string;
  question_type: string;
  question: string;
  expected_answer_points: string[];
  hint: string;
  evidence_refs: string[];
  origin: string;
};

export type AnswerEvaluation = {
  question_id: string;
  status: string;
  matched_points: string[];
  missing_points: string[];
  feedback: string;
  next_turn: string;
  repair_focus: string;
};

export type EvidenceItem = {
  source_category: string;
  source_key?: string;
  source_id: string;
  snippet: string;
  rank?: number;
  metadata?: Record<string, string>;
};

export type RunDetail = RunSummary & {
  result: Record<string, unknown>;
  evidence: EvidenceItem[];
  answer_evaluation?: {
    run_id?: string;
    evaluations?: AnswerEvaluation[];
  };
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
  providerAuth: () => requestJson<Record<string, ProviderAuthState>>("/connections/provider-auth"),
  workspaces: () => requestJson<{ workspaces: WorkspaceEntry[] }>("/workspaces"),
  openWorkspace: (workspace_root: string) =>
    requestJson<Health>("/workspaces/open", {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ workspace_root }),
    }),
  browseWorkspace: (start_path: string) =>
    requestJson<{ workspace_root: string; cancelled: boolean }>("/workspaces/browse", {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ start_path }),
    }),
  indexEstimate: () => requestJson<IndexEstimate>("/index/estimate"),
  prepareIndex: () =>
    requestJson<IndexPrepareJob>("/index/prepare", {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({}),
    }),
  indexPrepareJob: (jobId: string) => requestJson<IndexPrepareJob>(`/index/prepare/${encodeURIComponent(jobId)}`),
  saveConfig: (config: AppConfig) =>
    requestJson<AppConfig>("/config", {
      method: "PUT",
      headers: jsonHeaders,
      body: JSON.stringify(config),
    }),
  startProviderAuthConnect: (payload: ProviderAuthConnectPayload) =>
    requestJson<{ ok: boolean; provider: string; authorize_url: string }>("/connections/provider-auth/connect", {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify(payload),
    }),
  saveProviderAuth: (payload: ProviderAuthPayload) =>
    requestJson<Record<string, ProviderAuthState>>("/connections/provider-auth", {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify(payload),
    }),
  runs: () => requestJson<{ runs: RunSummary[] }>("/runs"),
  run: (runId: string) => requestJson<RunDetail>(`/runs/${encodeURIComponent(runId)}`),
  trace: (runId: string) => requestJson<RunTrace>(`/runs/${encodeURIComponent(runId)}/trace`),
  openSourceFile: (path: string) =>
    requestJson<{ opened: boolean; path: string }>("/source/open", {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ path }),
    }),
  openRunSourceFile: (runId: string, path: string) =>
    requestJson<{ opened: boolean; path: string; vscode_url?: string }>(`/runs/${encodeURIComponent(runId)}/source/open`, {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ path }),
    }),
  retrieve: (payload: { prompt: string; allowed_sources: string[]; run_id?: string }) =>
    requestJson<RunSummary>("/retrieve", {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify(payload),
    }),
  evaluateAnswers: (runId: string, answers: Record<string, string>) =>
    requestJson<{ run_id: string; evaluations: AnswerEvaluation[] }>(`/runs/${encodeURIComponent(runId)}/answers`, {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ answers }),
    }),
  testConnection: (source: McpSource & { test_query?: string }) =>
    requestJson<Record<string, unknown>>("/connections/test", {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify(source),
    }),
  testRemoteMcpConnection: (source: RemoteMcpSource & { test_query?: string }) =>
    requestJson<Record<string, unknown>>("/connections/remote-mcp/test", {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify(source),
    }),
  listRemoteMcpTools: (source: RemoteMcpSource) =>
    requestJson<Record<string, unknown>>("/connections/remote-mcp/tools", {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify(source),
    }),
};
