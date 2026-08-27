import { useEffect, useMemo, useRef, useState } from "react";
import type { MouseEvent, ReactNode } from "react";
import dagre from "@dagrejs/dagre";
import { Background, Controls, MarkerType, MiniMap, ReactFlow, type Edge, type Node } from "@xyflow/react";
import { api, AnswerEvaluation, AppConfig, CodexModelOption, EvidenceAssessmentStatus, EvidenceConnection, EvidenceConnectionsGraph, EvidenceItem, EvidenceOrganization, Health, IndexEstimate, IndexPrepareJob, NextCheck, ProviderAuthState, RemoteMcpSource, RunDetail, RunSummary, RunTrace, SourceAttribution, UnderstandingCheck, WorkspaceEntry } from "./api";
import { sourceLabels, sourceOrder } from "./constants";

type LoadState<T> = {
  data?: T;
  error?: string;
  loading: boolean;
};

type Page = "chat" | "workspace" | "connections" | "settings";

type SourceHelp = {
  title: string;
  description: string;
  details?: string[];
  fields?: Array<{ name: string; description: string }>;
};

const defaultState = <T,>(): LoadState<T> => ({ loading: true });

export function App() {
  const [health, setHealth] = useState<LoadState<Health>>(defaultState);
  const [config, setConfig] = useState<LoadState<AppConfig>>(defaultState);
  const [providerAuth, setProviderAuth] = useState<LoadState<Record<string, ProviderAuthState>>>({ loading: false });
  const [workspaces, setWorkspaces] = useState<LoadState<WorkspaceEntry[]>>({ loading: false });
  const [runs, setRuns] = useState<LoadState<RunSummary[]>>(defaultState);
  const [selectedRunId, setSelectedRunId] = useState<string>("");
  const [runDetail, setRunDetail] = useState<LoadState<RunDetail>>({ loading: false });
  const [trace, setTrace] = useState<LoadState<RunTrace>>({ loading: false });
  const [prompt, setPrompt] = useState("");
  const [allowedSources, setAllowedSources] = useState<string[]>(["source_code", "repo_docs"]);
  const [runError, setRunError] = useState("");
  const [runLoading, setRunLoading] = useState(false);
  const [activeRun, setActiveRun] = useState<RunSummary | undefined>();
  const [answerError, setAnswerError] = useState("");
  const [answerLoading, setAnswerLoading] = useState(false);
  const [indexEstimate, setIndexEstimate] = useState<LoadState<IndexEstimate>>({ loading: false });
  const [indexPrepareLoading, setIndexPrepareLoading] = useState(false);
  const [indexPrepareMessage, setIndexPrepareMessage] = useState("");
  const [indexPrepareJob, setIndexPrepareJob] = useState<IndexPrepareJob | undefined>();
  const [indexRunNotice, setIndexRunNotice] = useState<{ title: string; message: string; tone: "info" | "warning" } | undefined>();
  const [activePage, setActivePage] = useState<Page>("chat");

  useEffect(() => {
    refreshBase();
  }, []);

  useEffect(() => {
    if (!config.data) return;
    setPrompt((current) => current || config.data?.ui.default_prompt || "");
    setAllowedSources((config.data.enabled_sources || []).filter((source) => sourceOrder.includes(source)));
  }, [config.data]);

  useEffect(() => {
    if (!selectedRunId) return;
    loadRun(selectedRunId);
  }, [selectedRunId]);

  async function refreshBase() {
    setHealth(defaultState());
    setConfig(defaultState());
    setProviderAuth({ loading: true });
    setWorkspaces({ loading: true });
    setRuns(defaultState());
    setIndexEstimate({ loading: true });
    await Promise.allSettled([
      api.health().then((data) => setHealth({ data, loading: false })).catch((error) => setHealth({ error: error.message, loading: false })),
      api.config().then((data) => setConfig({ data, loading: false })).catch((error) => setConfig({ error: error.message, loading: false })),
      api.providerAuth().then((data) => setProviderAuth({ data, loading: false })).catch((error) => setProviderAuth({ error: error.message, loading: false })),
      api.workspaces().then((data) => setWorkspaces({ data: data.workspaces, loading: false })).catch((error) => setWorkspaces({ error: error.message, loading: false })),
      api.indexEstimate().then((data) => setIndexEstimate({ data, loading: false })).catch((error) => setIndexEstimate({ error: error.message, loading: false })),
      api.runs().then((data) => {
        setRuns({ data: data.runs, loading: false });
        setSelectedRunId((current) => {
          if (current && data.runs.some((run) => run.run_id === current)) return current;
          return data.runs[0]?.run_id || "";
        });
        if (!data.runs.length) {
          setRunDetail({ loading: false });
          setTrace({ loading: false });
        }
      }).catch((error) => setRuns({ error: error.message, loading: false })),
    ]);
  }

  async function loadRun(runId: string) {
    setRunDetail({ loading: true });
    setTrace({ loading: true });
    await Promise.allSettled([
      api.run(runId).then((data) => setRunDetail({ data, loading: false })).catch((error) => setRunDetail({ error: error.message, loading: false })),
      api.trace(runId).then((data) => setTrace({ data, loading: false })).catch((error) => setTrace({ error: error.message, loading: false })),
    ]);
  }

  async function submitRun() {
    setRunError("");
    setRunLoading(true);
    setActiveRun(undefined);
    const indexState = indexEstimate.data;
    if (indexState && !indexState.index_ready) {
      const action = indexState.request_index_action;
      if (action === "reindex") {
        setIndexRunNotice({
          title: "Repository change detected — re-indexing",
          message: indexState.index_status_detail || "The repository changed since the last completed index. This retrieval will re-index before searching.",
          tone: "warning",
        });
      } else if (action === "repair") {
        setIndexRunNotice({
          title: "Incomplete index detected — repairing",
          message: indexState.index_status_detail || "This retrieval will repair the incomplete index before searching.",
          tone: "warning",
        });
      } else if (action === "build") {
        setIndexRunNotice({
          title: "No index found — preparing it now",
          message: "This is an active retrieval request, so the repository will be indexed before searching.",
          tone: "info",
        });
      }
    } else {
      setIndexRunNotice(undefined);
    }
    try {
      const run = await api.retrieve({ prompt, allowed_sources: allowedSources });
      setActiveRun(run);
      setSelectedRunId(run.run_id);
      let latest = await api.run(run.run_id);
      setRunDetail({ data: latest, loading: false });
      setActiveRun(latest);
      while (latest.status === "running") {
        await delay(1000);
        latest = await api.run(run.run_id);
        setRunDetail({ data: latest, loading: false });
        setActiveRun(latest);
      }
      if (latest.status === "failed") {
        setRunError(latest.progress_message || "Explanation run failed.");
      } else {
        await loadRun(run.run_id);
      }
      await refreshBase();
      setSelectedRunId(run.run_id);
    } catch (error) {
      setRunError(error instanceof Error ? error.message : String(error));
    } finally {
      setRunLoading(false);
      setActiveRun(undefined);
    }
  }

  async function prepareIndex() {
    setRunError("");
    setIndexPrepareMessage("");
    setIndexPrepareLoading(true);
    setIndexPrepareJob(undefined);
    try {
      const started = await api.prepareIndex();
      setIndexPrepareJob(started);
      let latest = started;
      while (latest.status === "running") {
        await delay(1000);
        latest = await api.indexPrepareJob(started.job_id);
        setIndexPrepareJob(latest);
      }
      if (latest.status === "complete") {
        setIndexPrepareMessage(`Index prepared in ${formatDuration(latest.elapsed_seconds)}.`);
        await refreshBase();
      } else {
        setRunError(latest.message || "Index preparation failed.");
      }
    } catch (error) {
      setRunError(error instanceof Error ? error.message : String(error));
    } finally {
      setIndexPrepareLoading(false);
    }
  }

  async function openWorkspace(workspaceRoot: string) {
    setRunError("");
    setIndexPrepareMessage("");
    setIndexPrepareJob(undefined);
    setIndexPrepareLoading(false);
    try {
      await api.openWorkspace(workspaceRoot);
      setSelectedRunId("");
      setRunDetail({ loading: false });
      setTrace({ loading: false });
      await refreshBase();
    } catch (error) {
      setRunError(error instanceof Error ? error.message : String(error));
    }
  }

  async function submitAnswers(answers: Record<string, string>) {
    if (!selectedRunId) return;
    setAnswerError("");
    setAnswerLoading(true);
    try {
      await api.evaluateAnswers(selectedRunId, answers);
      await loadRun(selectedRunId);
    } catch (error) {
      setAnswerError(error instanceof Error ? error.message : String(error));
    } finally {
      setAnswerLoading(false);
    }
  }

  function startNewChat() {
    setSelectedRunId("");
    setRunDetail({ loading: false });
    setTrace({ loading: false });
    setAnswerError("");
    setAnswerLoading(false);
    setRunError("");
    setActiveRun(undefined);
  }

  const currentEvidence = runDetail.data?.evidence || [];
  const currentTrace = trace.data ? [...trace.data.orchestration_trace, ...trace.data.retrieval_trace] : [];
  const currentChecks = getUnderstandingChecks(runDetail.data);
  const currentEvaluations = runDetail.data?.answer_evaluation?.evaluations || [];
  const questionsPending = currentChecks.length > 0 && currentEvaluations.length === 0;
  const chatProgress = indexPrepareLoading
    ? indexPrepareJob?.message || "Preparing index."
    : runLoading
      ? activeRun?.progress_message || "Running prompt."
      : "";
  const chatProgressPercent = indexPrepareLoading ? indexPrepareJob?.progress_percent : runLoading ? activeRun?.progress_percent : undefined;
  const chatProgressLogs = indexPrepareLoading ? indexPrepareJob?.logs || [] : runLoading ? activeRun?.progress_logs || [] : [];

  return (
    <div className="appShell">
      <aside className="sideNav">
        <div className="brandMark">GI</div>
        <nav>
          <button className={activePage === "chat" ? "navButton active" : "navButton"} type="button" onClick={() => setActivePage("chat")}>Chat Run</button>
          <button className={activePage === "workspace" ? "navButton active" : "navButton"} type="button" onClick={() => setActivePage("workspace")}>Workspace</button>
          <button className={activePage === "connections" ? "navButton active" : "navButton"} type="button" onClick={() => setActivePage("connections")}>Connections</button>
          <button className={activePage === "settings" ? "navButton active" : "navButton"} type="button" onClick={() => setActivePage("settings")}>Settings</button>
        </nav>
      </aside>
      <main className="mainGrid">
        {indexRunNotice && (
          <div className={`indexRunPopup ${indexRunNotice.tone}`} role="alert" aria-live="assertive">
            <div>
              <strong>{indexRunNotice.title}</strong>
              <span>{indexRunNotice.message}</span>
            </div>
            <button type="button" className="textButton compactButton" onClick={() => setIndexRunNotice(undefined)}>Dismiss</button>
          </div>
        )}
        <header className="topBar">
          <div>
            <h1>Guided Intelligence</h1>
            <p>{health.data?.workspace_root || "Local retrieval workspace"}</p>
          </div>
          <button className="iconButton" type="button" onClick={refreshBase} aria-label="Refresh status">
            Refresh
          </button>
        </header>

        <StatusStrip health={health} />

        {activePage === "chat" && (
          <section className="chatPage">
            <div className="chatMainColumn">
              <RunPanel
                prompt={prompt}
                setPrompt={setPrompt}
                allowedSources={allowedSources}
                setAllowedSources={setAllowedSources}
                config={config.data}
                runLoading={runLoading}
                runError={runError}
                blocked={questionsPending}
                indexEstimate={indexEstimate.data}
                indexPrepareLoading={indexPrepareLoading}
                indexPrepareMessage={indexPrepareMessage}
                indexPrepareJob={indexPrepareJob}
                progressMessage={chatProgress}
                progressPercent={chatProgressPercent}
                progressLogs={chatProgressLogs}
                onPrepareIndex={prepareIndex}
                onConfigureIndexing={() => setActivePage("workspace")}
                onStartNewChat={startNewChat}
                onSubmit={submitRun}
              />
              <GuidedResponsePanel
                runDetail={runDetail.data}
                checks={currentChecks}
                evaluations={currentEvaluations}
                loading={answerLoading}
                error={answerError}
                onSubmit={submitAnswers}
              />
            </div>
            <RunSummaryPanel runs={runs} selectedRunId={selectedRunId} setSelectedRunId={setSelectedRunId} runDetail={runDetail} />
            <EvidenceGraphPanel
              graph={runDetail.data?.evidence_connections}
              selectedEvidence={currentEvidence}
              candidates={runDetail.data?.candidate_evidence || currentEvidence}
              organization={runDetail.data?.evidence_organization}
            />
            <EvidencePanel
              runId={runDetail.data?.run_id}
              selectedEvidence={currentEvidence}
              candidates={runDetail.data?.candidate_evidence || currentEvidence}
              organization={runDetail.data?.evidence_organization}
            />
            <TracePanel trace={currentTrace} state={trace} />
          </section>
        )}
        {activePage === "workspace" && (
          <section className="settingsPage">
            <WorkspaceIndexPanel
              health={health.data}
              config={config}
              workspaces={workspaces}
              setConfig={setConfig}
              estimate={indexEstimate}
              indexPrepareLoading={indexPrepareLoading}
              indexPrepareMessage={indexPrepareMessage}
              onPrepareIndex={prepareIndex}
              refreshBase={refreshBase}
              onOpenWorkspace={openWorkspace}
            />
          </section>
        )}
        {activePage === "connections" && (
          <section className="settingsPage">
            <ConnectionsPanel health={health.data} config={config} providerAuth={providerAuth} setProviderAuth={setProviderAuth} setConfig={setConfig} refreshBase={refreshBase} />
          </section>
        )}
        {activePage === "settings" && (
          <section className="settingsPage">
            <SettingsPanel health={health.data} config={config} setConfig={setConfig} />
          </section>
        )}
      </main>
    </div>
  );
}

function StatusStrip({ health }: { health: LoadState<Health> }) {
  const isCodexMode = health.data?.retrieval_mode === "codex";
  const items = isCodexMode ? [
    ["Service", health.data?.status === "ok"],
    ["API", health.data?.api_llm_configured || health.data?.llm_configured],
    ["Codex", health.data?.codex_configured],
    [health.data?.codex_prompt_profile ? `Profile: ${health.data.codex_prompt_profile}` : "Codex profile", Boolean(health.data?.codex_prompt_profile)],
  ] as const : [
    ["Service", health.data?.status === "ok"],
    ["API", health.data?.api_llm_configured || health.data?.llm_configured],
    ["Embeddings", health.data?.embedding_configured],
    ["Qdrant", Boolean(health.data?.qdrant_configured && health.data?.qdrant_reachable)],
  ] as const;
  return (
    <section className="statusStrip">
      {items.map(([label, ok]) => (
        <span className={ok ? "statusChip ok" : "statusChip"} key={label}>
          <span />
          {label}
        </span>
      ))}
      {health.error && <span className="statusError">{health.error}</span>}
      {!isCodexMode && health.data?.qdrant_configured && !health.data?.qdrant_reachable && (
        <span className="statusError">{health.data.qdrant_status_detail}</span>
      )}
    </section>
  );
}

function RunPanel(props: {
  prompt: string;
  setPrompt: (value: string) => void;
  allowedSources: string[];
  setAllowedSources: (value: string[]) => void;
  config?: AppConfig;
  runLoading: boolean;
  runError: string;
  blocked: boolean;
  indexEstimate?: IndexEstimate;
  indexPrepareLoading: boolean;
  indexPrepareMessage: string;
  indexPrepareJob?: IndexPrepareJob;
  progressMessage: string;
  progressPercent?: number;
  progressLogs: string[];
  onPrepareIndex: () => void;
  onConfigureIndexing: () => void;
  onStartNewChat: () => void;
  onSubmit: () => void;
}) {
  const sourceOptions = runSourceOptions(props.config);
  const isCodexMode = props.config?.retrieval?.mode === "codex";
  const [help, setHelp] = useState<SourceHelp | null>(null);
  function toggleSource(source: string) {
    if (props.allowedSources.includes(source)) {
      props.setAllowedSources(props.allowedSources.filter((item) => item !== source));
    } else {
      props.setAllowedSources([...props.allowedSources, source]);
    }
  }
  return (
    <section className="panel" id="run">
      <div className="panelHeader">
        <h2>Chat + Retrieval</h2>
        <div className="panelHeaderActions">
          <button className="textButton compactButton" type="button" disabled={props.runLoading || props.indexPrepareLoading} onClick={props.onStartNewChat}>
            New chat
          </button>
          <span className="panelMeta">real pipeline run</span>
        </div>
      </div>
      <textarea value={props.prompt} onChange={(event) => props.setPrompt(event.target.value)} rows={7} />
      {props.progressMessage && <ChatProgressLine message={props.progressMessage} percent={props.progressPercent} logs={props.progressLogs} />}
      <div className="sourceGrid">
        {sourceOptions.map((option) => (
          <div className="checkRow checkRowWithInfo" key={option.key}>
            <label className="checkLabel">
              <input type="checkbox" checked={props.allowedSources.includes(option.sourceKey)} onChange={() => toggleSource(option.sourceKey)} />
              <span>{option.label}</span>
            </label>
            <InfoButton label={`Explain ${option.label}`} onClick={() => setHelp(sourceHelpForKey(option.sourceKey))} />
          </div>
        ))}
      </div>
      {help && <InfoDialog help={help} onClose={() => setHelp(null)} />}
      {props.blocked && <p className="noticeText">Answer the current understanding checks before starting another run.</p>}
      {!isCodexMode && props.indexEstimate?.enable_indexing && props.indexEstimate.file_count > 0 && (
        <IndexPreparationNotice
          estimate={props.indexEstimate}
          indexPrepareLoading={props.indexPrepareLoading}
          onPrepareIndex={props.onPrepareIndex}
          onConfigureIndexing={props.onConfigureIndexing}
          indexingEnabled={props.indexEstimate.enable_indexing}
        />
      )}
      {!isCodexMode && props.indexPrepareMessage && <p className="noticeText">{props.indexPrepareMessage}</p>}
      {props.runError && <p className="errorText">{props.runError}</p>}
      <button className="primaryButton" type="button" disabled={!props.prompt.trim() || props.runLoading || props.blocked || props.indexPrepareLoading} onClick={props.onSubmit}>
        {props.runLoading ? "Running..." : "Run retrieval"}
      </button>
    </section>
  );
}

function IndexPreparationNotice({
  estimate,
  indexPrepareLoading,
  onPrepareIndex,
  onConfigureIndexing,
  indexingEnabled = true,
}: {
  estimate: IndexEstimate;
  indexPrepareLoading: boolean;
  onPrepareIndex: () => void;
  onConfigureIndexing?: () => void;
  indexingEnabled?: boolean;
}) {
  const ready = Boolean(estimate.index_ready);
  const stale = estimate.index_status === "stale";
  const incomplete = estimate.index_status === "incomplete";
  return (
    <div className={indexPrepareLoading ? "indexNotice running" : ready ? "indexNotice ready" : stale || incomplete ? "indexNotice warning" : "indexNotice"}>
      <div className="indexNoticeText">
        <strong>{indexPrepareLoading ? "Indexing is running." : ready ? "Index is ready." : stale ? "Repository change detected — re-indexing is required." : incomplete ? "Index preparation is incomplete." : "Index is not prepared."}</strong>
        <span>
          Prepares native retrieval for BM25, Qdrant, and CodeGraph. Scope: {formatCount(estimate.file_count)} files, about {formatCount(estimate.estimated_chunks)} chunks.
          {!indexingEnabled
            ? " Enable indexing and save retrieval settings before preparing the index."
            : ready
              ? ` ${estimate.index_status_detail || ""}`
              : ` ${estimate.index_status_detail || "Run indexing before retrieval."} Estimate: ${formatIndexEstimateDuration(estimate)}.`}
          {estimate.index_last_built_at ? ` Last prepared: ${formatDateTime(estimate.index_last_built_at)}.` : ""}
          {" "}
          {!ready && onConfigureIndexing && (
            <>
              If that is too long, open Workspace and add folders to "Do not index these directories/files", then refresh the estimate.
              {" "}
            </>
          )}
          {onConfigureIndexing && (
            <button className="inlineLinkButton" type="button" onClick={onConfigureIndexing}>
              Edit exclusions in Workspace
            </button>
          )}
        </span>
      </div>
      <button className="textButton indexButton" type="button" disabled={indexPrepareLoading || !indexingEnabled} onClick={onPrepareIndex}>
        {indexPrepareLoading ? "Preparing..." : ready ? "Refresh index" : "Prepare index"}
      </button>
    </div>
  );
}

function ChatProgressLine({ message, percent, logs }: { message: string; percent?: number; logs?: string[] }) {
  const determinate = typeof percent === "number" && Number.isFinite(percent);
  const progress = determinate ? Math.max(0, Math.min(100, percent)) : 0;
  return (
    <div className="chatProgressLine">
      <div className={determinate ? "progressLine determinate" : "progressLine"}>
        <span style={determinate ? { width: `${progress}%` } : undefined} />
      </div>
      <p>{determinate ? `${Math.round(progress)}% - ${message}` : message}</p>
      {logs && logs.length > 0 && (
        <div className="progressLogs">
          {logs.slice(-3).map((item) => <span key={item}>{item}</span>)}
        </div>
      )}
    </div>
  );
}

type RunSourceOption = {
  key: string;
  sourceKey: string;
  label: string;
};

function runSourceOptions(config?: AppConfig): RunSourceOption[] {
  const options = new Map<string, RunSourceOption>();
  for (const sourceKey of ["source_code", "repo_docs", "local_notes", "notebooklm"]) {
    options.set(sourceKey, { key: sourceKey, sourceKey, label: sourceLabels[sourceKey] || sourceKey });
  }
  const remoteSources = mergeRemoteMcpSources(config?.connections.remote_mcp_sources);
  for (const source of remoteSources) {
    if (source.enabled === false) continue;
    const sourceKey = source.source_key || connectorSourceKey(source);
    const label = connectorRunLabel(source);
    options.set(sourceKey, { key: sourceKey, sourceKey, label });
  }
  return sourceOrder.filter((sourceKey) => options.has(sourceKey)).map((sourceKey) => options.get(sourceKey) as RunSourceOption);
}

function connectorRunLabel(source: RemoteMcpSource): string {
  if (source.provider === "github" && source.source_category === "issue_tracker") return "GitHub issues";
  if (source.provider === "github" && source.source_category === "pull_request") return "GitHub PRs";
  if (source.provider === "shortcut") return "Shortcut";
  if (source.provider === "notion") return "Notion";
  if (source.provider === "atlassian" && source.source_category === "issue_tracker") return "Jira";
  if (source.provider === "atlassian" && source.source_category === "documentation") return "Confluence";
  return source.title || providerLabel(source.provider);
}

function connectorSourceKey(source: RemoteMcpSource): string {
  if (source.name === "github-issues") return "github_issues";
  if (source.name === "github-prs") return "github_pull_requests";
  if (source.name === "notion-pages") return "notion";
  if (source.name === "jira-issues") return "jira";
  if (source.name === "confluence-pages") return "confluence";
  if (source.name === "shortcut-stories") return "shortcut";
  if (source.name === "linear-issues") return "linear";
  if (source.name === "slack-messages") return "slack";
  if (source.name === "google-drive-documents") return "google_drive";
  return source.provider || source.name;
}

function ConnectionsPanel({
  health,
  config,
  providerAuth,
  setProviderAuth,
  setConfig,
  refreshBase,
}: {
  health?: Health;
  config: LoadState<AppConfig>;
  providerAuth: LoadState<Record<string, ProviderAuthState>>;
  setProviderAuth: (state: LoadState<Record<string, ProviderAuthState>>) => void;
  setConfig: (state: LoadState<AppConfig>) => void;
  refreshBase: () => void;
}) {
  const [saving, setSaving] = useState(false);
  const [testingRemoteName, setTestingRemoteName] = useState("");
  const [discoveringRemoteName, setDiscoveringRemoteName] = useState("");
  const [remoteTestResults, setRemoteTestResults] = useState<Record<string, Record<string, unknown>>>({});
  const [remoteTestErrors, setRemoteTestErrors] = useState<Record<string, string>>({});
  const [remoteToolResults, setRemoteToolResults] = useState<Record<string, Array<Record<string, unknown>>>>({});
  const [connectingProviderName, setConnectingProviderName] = useState("");
  const [expandedRemoteCards, setExpandedRemoteCards] = useState<Record<string, boolean>>({});
  const [providerTokenDrafts, setProviderTokenDrafts] = useState<Record<string, string>>({});
  const [help, setHelp] = useState<SourceHelp | null>(null);
  const shortcutTokenInputRef = useRef<HTMLInputElement | null>(null);
  const [saveError, setSaveError] = useState("");
  const builtIns = [
    ["Source Code", "Built in", "CodeGraph + Qdrant"],
    ["Documentation", "Built in", "workspace index"],
    ["Local Notes", "Optional", "obsidian-hybrid-search"],
  ];
  const mcpSources = config.data?.connections.mcp_sources || [];
  const remoteMcpSources = mergeRemoteMcpSources(config.data?.connections.remote_mcp_sources);
  const providerAuthData = providerAuth.data || {};
  const remoteMcpEntries = remoteMcpSources.map((source, index) => ({ source, index }));
  const githubRemoteIssueEntry = remoteMcpEntries.find((entry) => entry.source.name === "github-issues");
  const githubRemotePullRequestEntry = remoteMcpEntries.find((entry) => entry.source.name === "github-prs");
  const githubRemoteEntries = [githubRemoteIssueEntry, githubRemotePullRequestEntry].filter((entry): entry is { source: RemoteMcpSource; index: number } => Boolean(entry));
  const otherRemoteMcpEntries = remoteMcpEntries.filter((entry) => entry.source.name !== "github-issues" && entry.source.name !== "github-prs");
  const githubRemoteScope = githubRemoteIssueEntry?.source.scope || githubRemotePullRequestEntry?.source.scope || health?.github_repository || "";
  const githubRepoScope = parseGitHubRepoScope(githubRemoteScope);
  const githubRemoteSource = githubRemoteIssueEntry?.source || githubRemotePullRequestEntry?.source;
  const githubCardExpanded = Boolean(expandedRemoteCards.github);
  const githubEnabledParts = [
    githubRemoteIssueEntry?.source.enabled !== false ? "Issues" : "",
    githubRemotePullRequestEntry?.source.enabled !== false ? "PRs" : "",
  ].filter(Boolean);
  const githubEnabledLabel = githubEnabledParts.length ? githubEnabledParts.join(" + ") : "Disabled";

  function toggleRemoteCard(name: string) {
    setExpandedRemoteCards((current) => ({ ...current, [name]: !current[name] }));
  }

  function updateRemoteMcpSource(index: number, patch: Partial<RemoteMcpSource>) {
    if (!config.data) return;
    const nextSources = remoteMcpSources.map((source, sourceIndex) => sourceIndex === index ? { ...source, ...patch } : source);
    setConfig({
      data: {
        ...config.data,
        connections: {
          ...config.data.connections,
          remote_mcp_sources: nextSources,
        },
      },
      loading: false,
    });
    setSaveError("");
    setRemoteTestResults((current) => ({ ...current, [remoteMcpSources[index]?.name || String(index)]: undefined as unknown as Record<string, unknown> }));
    setRemoteTestErrors((current) => ({ ...current, [remoteMcpSources[index]?.name || String(index)]: "" }));
  }

  function updateRemoteMcpFeature(index: number, feature: string, enabled: boolean) {
    const source = remoteMcpSources[index];
    if (!source) return;
    updateRemoteMcpSource(index, { features: { ...(source.features || {}), [feature]: enabled } });
  }

  function updateRemoteMcpSources(indexes: number[], patch: Partial<RemoteMcpSource>) {
    if (!config.data) return;
    const indexSet = new Set(indexes);
    const nextSources = remoteMcpSources.map((source, sourceIndex) => indexSet.has(sourceIndex) ? { ...source, ...patch } : source);
    setConfig({
      data: {
        ...config.data,
        connections: {
          ...config.data.connections,
          remote_mcp_sources: nextSources,
        },
      },
      loading: false,
    });
    setSaveError("");
    for (const index of indexes) {
      const sourceName = remoteMcpSources[index]?.name || String(index);
      setRemoteTestResults((current) => ({ ...current, [sourceName]: undefined as unknown as Record<string, unknown> }));
      setRemoteTestErrors((current) => ({ ...current, [sourceName]: "" }));
    }
  }

  function updateConnectedContextTerms(key: "disclaimer_required_terms" | "stale_block_terms", value: string) {
    if (!config.data) return;
    setConfig({
      data: {
        ...config.data,
        connected_context: {
          ...(config.data.connected_context || {}),
          [key]: commaSeparatedToList(value),
        },
      },
      loading: false,
    });
    setSaveError("");
  }

  function updateGitHubRepoScope(patch: Partial<{ owner: string; repo: string }>) {
    const next = { ...githubRepoScope, ...patch };
    updateRemoteMcpSources(githubRemoteEntries.map((entry) => entry.index), {
      scope: formatGitHubRepoScope(next.owner, next.repo),
    });
  }

  async function saveConnections() {
    if (!config.data) return;
    setSaving(true);
    setSaveError("");
    try {
      const updated = await api.saveConfig({
        ...config.data,
        connections: {
          ...stripLegacyGitHubConnectionConfig(config.data.connections),
          remote_mcp_sources: remoteMcpSources.map(stripRemoteMcpCredentials),
          mcp_sources: mcpSources,
        },
      });
      setConfig({ data: updated, loading: false });
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : String(error));
    } finally {
      setSaving(false);
    }
  }

  async function testRemoteMcpConnection(source: RemoteMcpSource) {
    if (!source.enabled) {
      setRemoteTestErrors((current) => ({ ...current, [source.name]: "Enable this hosted MCP connector before testing." }));
      return;
    }
    if (!source.endpoint_url.trim()) {
      setRemoteTestErrors((current) => ({ ...current, [source.name]: "Remote MCP endpoint URL is required." }));
      return;
    }
    if (requiresConfiguredQueryTool(source) && !source.query_tool_name.trim()) {
      setRemoteTestErrors((current) => ({ ...current, [source.name]: "Query tool name is required." }));
      return;
    }
    setTestingRemoteName(source.name);
    setRemoteTestErrors((current) => ({ ...current, [source.name]: "" }));
    setRemoteTestResults((current) => ({ ...current, [source.name]: undefined as unknown as Record<string, unknown> }));
    try {
      const result = await api.testRemoteMcpConnection({ ...source, test_query: source.scope || source.name });
      setRemoteTestResults((current) => ({ ...current, [source.name]: result }));
    } catch (error) {
      setRemoteTestErrors((current) => ({ ...current, [source.name]: error instanceof Error ? error.message : String(error) }));
    } finally {
      setTestingRemoteName("");
    }
  }

  async function testRemoteMcpGroup(groupName: string, sources: RemoteMcpSource[]) {
    const enabledSources = sources.filter((source) => source.enabled !== false);
    if (!enabledSources.length) {
      setRemoteTestErrors((current) => ({ ...current, [groupName]: "Enable issues or PRs before testing." }));
      return;
    }
    for (const source of enabledSources) {
      if (!source.endpoint_url.trim()) {
        setRemoteTestErrors((current) => ({ ...current, [groupName]: "Remote MCP endpoint URL is required." }));
        return;
      }
      if (requiresConfiguredQueryTool(source) && !source.query_tool_name.trim()) {
        setRemoteTestErrors((current) => ({ ...current, [groupName]: "Query tool name is required." }));
        return;
      }
    }
    setTestingRemoteName(groupName);
    setRemoteTestErrors((current) => ({ ...current, [groupName]: "" }));
    for (const source of enabledSources) {
      setRemoteTestResults((current) => ({ ...current, [source.name]: undefined as unknown as Record<string, unknown> }));
      setRemoteTestErrors((current) => ({ ...current, [source.name]: "" }));
    }
    try {
      for (const source of enabledSources) {
        const result = await api.testRemoteMcpConnection({ ...source, test_query: source.scope || source.name });
        setRemoteTestResults((current) => ({ ...current, [source.name]: result }));
      }
    } catch (error) {
      setRemoteTestErrors((current) => ({ ...current, [groupName]: error instanceof Error ? error.message : String(error) }));
    } finally {
      setTestingRemoteName("");
    }
  }

  async function discoverRemoteMcpTools(source: RemoteMcpSource) {
    if (!source.endpoint_url.trim()) {
      setRemoteTestErrors((current) => ({ ...current, [source.name]: "Remote MCP endpoint URL is required before tool discovery." }));
      return;
    }
    setDiscoveringRemoteName(source.name);
    setRemoteTestErrors((current) => ({ ...current, [source.name]: "" }));
    try {
      const result = await api.listRemoteMcpTools(source);
      if (!result.ok) {
        setRemoteTestErrors((current) => ({ ...current, [source.name]: String(result.error || "Tool discovery failed.") }));
        setRemoteToolResults((current) => ({ ...current, [source.name]: [] }));
        return;
      }
      const tools = Array.isArray(result.tools) ? result.tools.filter((tool): tool is Record<string, unknown> => Boolean(tool && typeof tool === "object" && !Array.isArray(tool))) : [];
      setRemoteToolResults((current) => ({ ...current, [source.name]: tools }));
    } catch (error) {
      setRemoteTestErrors((current) => ({ ...current, [source.name]: error instanceof Error ? error.message : String(error) }));
    } finally {
      setDiscoveringRemoteName("");
    }
  }

  async function connectRemoteProvider(source: RemoteMcpSource) {
    setConnectingProviderName(source.provider);
    setRemoteTestErrors((current) => ({ ...current, [source.name]: "", [source.provider]: "" }));
    try {
      if (source.provider === "shortcut") {
        const token = (providerTokenDrafts.shortcut || shortcutTokenInputRef.current?.value || "").trim();
        if (token) {
          const updated = await api.saveProviderAuth({
            provider: "shortcut",
            auth_type: "bearer",
            bearer_token: token,
          });
          setProviderAuth({ data: updated, loading: false });
          setProviderTokenDrafts((current) => ({ ...current, shortcut: "" }));
          setConnectingProviderName("");
          return;
        }
        const message = "Paste a Shortcut API token before saving.";
        setRemoteTestErrors((current) => ({ ...current, [source.name]: message, shortcut: message }));
        setConnectingProviderName("");
        return;
      }
      const result = await api.startProviderAuthConnect({
        provider: source.provider,
        endpoint_url: source.endpoint_url,
      });
      window.location.href = result.authorize_url;
      const pollUntil = Date.now() + 120000;
      const poll = async () => {
        const updated = await api.providerAuth();
        setProviderAuth({ data: updated, loading: false });
        if (updated[source.provider]?.connected || Date.now() >= pollUntil) {
          setConnectingProviderName("");
          return;
        }
        window.setTimeout(poll, 2000);
      };
      window.setTimeout(poll, 2000);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setRemoteTestErrors((current) => ({ ...current, [source.name]: message, [source.provider]: message }));
      setConnectingProviderName("");
    }
  }

  return (
    <>
      <section className="panel" id="connections">
        <div className="panelHeader">
          <div>
            <h2>Connections</h2>
            <p className="panelPurpose">Manage built-in sources and hosted provider connectors used as retrieval evidence.</p>
          </div>
          <button className="textButton" type="button" onClick={refreshBase}>Reload</button>
        </div>
        <div className="connectionSection">
          <div className="sectionHeader">
            <h3>Built-in sources</h3>
            <p>Local retrieval surfaces available from the selected workspace and configured local tools.</p>
          </div>
          <div className="connectionGrid">
            {builtIns.map(([name, status, detail]) => (
              <ConnectionTile key={name} name={name} status={status} detail={detail} onInfo={() => setHelp(builtInConnectionHelp(name))} />
            ))}
          </div>
        </div>
        {remoteMcpSources.length > 0 && (
          <div className="connectionSection remoteMcpSection">
          <div className="sectionHeader">
            <h3>Hosted MCP connectors</h3>
            <p>Remote MCP uses provider-hosted endpoints. It never falls back to local command MCP.</p>
          </div>
          <div className="formGrid two">
            <label className="fieldLabel">
              Required disclaimer terms
              <input
                value={listToCommaSeparated(config.data?.connected_context?.disclaimer_required_terms || ["do not use"])}
                placeholder="do not use"
                onChange={(event) => updateConnectedContextTerms("disclaimer_required_terms", event.target.value)}
              />
              <span className="fieldHint">All terms must appear before a document can be blocked as stale guidance.</span>
            </label>
            <label className="fieldLabel">
              Stale block terms
              <input
                value={listToCommaSeparated(config.data?.connected_context?.stale_block_terms || ["stale", "superseded", "outdated", "deprecated"])}
                placeholder="stale, superseded, outdated, deprecated"
                onChange={(event) => updateConnectedContextTerms("stale_block_terms", event.target.value)}
              />
              <span className="fieldHint">At least one term must appear with the disclaimer terms to block current guidance.</span>
            </label>
          </div>
          <div className="remoteMcpGrid">
            {githubRemoteSource && (
              <article className="remoteMcpCard" key="github-hosted-mcp">
                <div className="remoteMcpHeader">
                  <button className="remoteMcpHeaderMain" type="button" onClick={() => toggleRemoteCard("github")} aria-expanded={githubCardExpanded}>
                    <div>
                      <h4>GitHub</h4>
                      <p>GitHub / issues and pull requests / {providerAuthData.github?.connected ? "connected" : "not connected"}</p>
                    </div>
                    <div className="remoteMcpHeaderMeta">
                      <span className={githubEnabledParts.length ? "statusPill enabled" : "statusPill disabled"}>{githubEnabledLabel}</span>
                      <span className={providerAuthData.github?.connected ? "statusPill connected" : "statusPill"}>{providerAuthData.github?.connected ? "Connected" : "Not connected"}</span>
                      <span className="expandIcon">{githubCardExpanded ? "Collapse" : "Expand"}</span>
                    </div>
                  </button>
                  <InfoButton label="Explain GitHub connection" onClick={() => setHelp(connectionHelpForProvider("github"))} />
                </div>
                {githubCardExpanded && (
                  <div className="remoteMcpBody">
                    <div className="formGrid two">
                      <label className="fieldLabel">
                        Repository owner
                        <input
                          value={githubRepoScope.owner}
                          placeholder="microsoft"
                          onChange={(event) => updateGitHubRepoScope({ owner: event.target.value })}
                        />
                      </label>
                      <label className="fieldLabel">
                        Repository name
                        <input
                          value={githubRepoScope.repo}
                          placeholder="TypeScript"
                          onChange={(event) => updateGitHubRepoScope({ repo: event.target.value })}
                        />
                      </label>
                    </div>
                    <p className="fieldHint">
                      Repo scope: {githubRemoteScope || "not set"}
                    </p>
                    <div className="sourceGrid">
                      {githubRemoteIssueEntry && (
                        <label className="checkRow">
                          <input
                            type="checkbox"
                            checked={githubRemoteIssueEntry.source.enabled !== false}
                            disabled={!config.data}
                            onChange={(event) => updateRemoteMcpSource(githubRemoteIssueEntry.index, { enabled: event.target.checked })}
                          />
                          <span>Fetch GitHub issues</span>
                        </label>
                      )}
                      {githubRemotePullRequestEntry && (
                        <label className="checkRow">
                          <input
                            type="checkbox"
                            checked={githubRemotePullRequestEntry.source.enabled !== false}
                            disabled={!config.data}
                            onChange={(event) => updateRemoteMcpSource(githubRemotePullRequestEntry.index, { enabled: event.target.checked })}
                          />
                          <span>Fetch GitHub PRs</span>
                        </label>
                      )}
                    </div>
                    <div className="formGrid two">
                      {githubRemoteIssueEntry?.source.enabled !== false && (
                        <fieldset className="inlineFieldset">
                          <legend>Issues</legend>
                          <label className="fieldLabel">
                            Result limit
                            <input
                              value={String(githubRemoteIssueEntry.source.result_limit || 5)}
                              type="number"
                              min="1"
                              onChange={(event) => updateRemoteMcpSource(githubRemoteIssueEntry.index, { result_limit: numberOrDefault(event.target.value, 5) })}
                            />
                          </label>
                          <label className="fieldLabel">
                            Minimum score
                            <input
                              value={String(githubRemoteIssueEntry.source.min_score ?? 0)}
                              type="number"
                              min="0"
                              step="0.01"
                              onChange={(event) => updateRemoteMcpSource(githubRemoteIssueEntry.index, { min_score: numberOrZero(event.target.value) })}
                            />
                          </label>
                        </fieldset>
                      )}
                      {githubRemotePullRequestEntry?.source.enabled !== false && (
                        <fieldset className="inlineFieldset">
                          <legend>PRs</legend>
                          <label className="fieldLabel">
                            Result limit
                            <input
                              value={String(githubRemotePullRequestEntry.source.result_limit || 5)}
                              type="number"
                              min="1"
                              onChange={(event) => updateRemoteMcpSource(githubRemotePullRequestEntry.index, { result_limit: numberOrDefault(event.target.value, 5) })}
                            />
                          </label>
                          <label className="fieldLabel">
                            Minimum score
                            <input
                              value={String(githubRemotePullRequestEntry.source.min_score ?? 0)}
                              type="number"
                              min="0"
                              step="0.01"
                              onChange={(event) => updateRemoteMcpSource(githubRemotePullRequestEntry.index, { min_score: numberOrZero(event.target.value) })}
                            />
                          </label>
                        </fieldset>
                      )}
                    </div>
                    <button className="textButton" type="button" disabled={testingRemoteName === "github"} onClick={() => testRemoteMcpGroup("github", githubRemoteEntries.map((entry) => entry.source))}>
                      {testingRemoteName === "github" ? "Testing..." : "Test GitHub MCP"}
                    </button>
                    <button className="primaryButton compactButton" type="button" disabled={connectingProviderName === "github" || providerAuth.loading} onClick={() => connectRemoteProvider(githubRemoteSource)}>
                      {connectingProviderName === "github" ? "Waiting for browser..." : providerAuthData.github?.connected ? "Reconnect GitHub" : "Connect GitHub in browser"}
                    </button>
                    <details className="advancedDetails">
                      <summary>Advanced provider connection</summary>
                      <p>Endpoint and MCP tools are predefined for GitHub. Browser OAuth is saved once for the tool and reused by every workspace.</p>
                      <label className="fieldLabel">
                        Remote MCP endpoint
                        <input
                          value={githubRemoteSource.endpoint_url || ""}
                          placeholder="https://api.githubcopilot.com/mcp/"
                          onChange={(event) => updateRemoteMcpSources(githubRemoteEntries.map((entry) => entry.index), { endpoint_url: event.target.value })}
                        />
                      </label>
                    </details>
                    {githubRemoteIssueEntry && remoteTestResults[githubRemoteIssueEntry.source.name] && <ConnectionTestResult result={remoteTestResults[githubRemoteIssueEntry.source.name]} />}
                    {githubRemotePullRequestEntry && remoteTestResults[githubRemotePullRequestEntry.source.name] && <ConnectionTestResult result={remoteTestResults[githubRemotePullRequestEntry.source.name]} />}
                    {remoteTestErrors.github && (
                      <div className="connectionTest failed">
                        <strong>Hosted MCP failed</strong>
                        <p>{remoteTestErrors.github}</p>
                      </div>
                    )}
                  </div>
                )}
              </article>
            )}
            {otherRemoteMcpEntries.map(({ source, index }) => {
              const expanded = Boolean(expandedRemoteCards[source.name]);
              const enabled = source.enabled !== false;
              return (
                <article className="remoteMcpCard" key={source.name || index}>
                  <div className="remoteMcpHeader">
                    <button className="remoteMcpHeaderMain" type="button" onClick={() => toggleRemoteCard(source.name)} aria-expanded={expanded}>
                      <div>
                        <h4>{source.title || providerLabel(source.provider)}</h4>
                        <p>{providerLabel(source.provider)} / {genericSourceLabel(source.source_category)} / {providerAuthData[source.provider]?.connected ? "connected" : "not connected"}</p>
                      </div>
                      <div className="remoteMcpHeaderMeta">
                        <span className={enabled ? "statusPill enabled" : "statusPill disabled"}>{enabled ? "Enabled" : "Disabled"}</span>
                        <span className={providerAuthData[source.provider]?.connected ? "statusPill connected" : "statusPill"}>{providerAuthData[source.provider]?.connected ? "Connected" : "Not connected"}</span>
                        <span className="expandIcon">{expanded ? "Collapse" : "Expand"}</span>
                      </div>
                    </button>
                    <InfoButton label={`Explain ${source.title || providerLabel(source.provider)} connection`} onClick={() => setHelp(connectionHelpForSource(source))} />
                  </div>
                  {expanded && (
                    <div className="remoteMcpBody">
                      <label className="switchRow">
                        <input
                          type="checkbox"
                          checked={enabled}
                          disabled={!config.data}
                          onChange={(event) => updateRemoteMcpSource(index, { enabled: event.target.checked })}
                        />
                        <span>Enabled</span>
                      </label>
                      <div className="formGrid two">
                  <label className="fieldLabel">
                    Scope
                    <input
                      value={source.scope || ""}
                      placeholder={scopePlaceholder(source.provider)}
                      onChange={(event) => updateRemoteMcpSource(index, { scope: event.target.value })}
                    />
                  </label>
                  <label className="fieldLabel">
                    Result limit
                    <input
                      value={String(source.result_limit || 5)}
                      type="number"
                      min="1"
                      onChange={(event) => updateRemoteMcpSource(index, { result_limit: numberOrDefault(event.target.value, 5) })}
                    />
                  </label>
                      </div>
                      <div className="formGrid two">
                  <label className="fieldLabel">
                    Minimum score
                    <input
                      value={String(source.min_score ?? 0)}
                      type="number"
                      min="0"
                      step="0.01"
                      onChange={(event) => updateRemoteMcpSource(index, { min_score: numberOrZero(event.target.value) })}
                    />
                  </label>
                      </div>
                      {showsFeatureToggles(source) && source.features && Object.keys(source.features).length > 0 && (
                        <div className="featureToggleRow">
                          {Object.entries(source.features).map(([feature, enabled]) => (
                            <label className="checkRow" key={feature}>
                              <input
                                type="checkbox"
                                checked={Boolean(enabled)}
                                onChange={(event) => updateRemoteMcpFeature(index, feature, event.target.checked)}
                              />
                              <span>{featureLabel(feature)}</span>
                            </label>
                          ))}
                        </div>
                      )}
                      {supportsFullContentFetch(source) && (
                        <div className="compactControlRow">
                          <label className="checkRow compact">
                            <input
                              type="checkbox"
                              checked={Boolean(source.enrich_results)}
                              onChange={(event) => updateRemoteMcpSource(index, { enrich_results: event.target.checked })}
                            />
                            <span>Fetch full content for top search hits</span>
                          </label>
                          {source.enrich_results && (
                            <label className="fieldLabel">
                              Full-content fetch limit
                              <input
                                value={String(source.enrich_limit || 3)}
                                type="number"
                                min="1"
                                onChange={(event) => updateRemoteMcpSource(index, { enrich_limit: numberOrDefault(event.target.value, 3) })}
                              />
                            </label>
                          )}
                        </div>
                      )}
                      {source.provider === "shortcut" && (
                        <label className="fieldLabel">
                          Shortcut API token
                          <div className="tokenInputRow">
                            <input
                              value={providerTokenDrafts.shortcut || ""}
                              type="password"
                              ref={shortcutTokenInputRef}
                              placeholder={shortcutTokenConfigured(providerAuthData) ? "Token saved. Paste a new token to replace it." : "Paste Shortcut API token"}
                              onChange={(event) => {
                                setProviderTokenDrafts((current) => ({ ...current, shortcut: event.target.value }));
                                setRemoteTestErrors((current) => ({ ...current, [source.name]: "", shortcut: "" }));
                              }}
                            />
                            <button
                              className="primaryButton compactButton"
                              type="button"
                              disabled={connectingProviderName === source.provider || providerAuth.loading || !(providerTokenDrafts.shortcut || "").trim()}
                              onClick={() => connectRemoteProvider(source)}
                            >
                              {connectingProviderName === source.provider ? "Saving..." : "Save"}
                            </button>
                          </div>
                          {shortcutTokenConfigured(providerAuthData) && <span className="fieldHint">A token is saved. Paste a new token only if you want to replace it.</span>}
                        </label>
                      )}
                      <button className="textButton" type="button" disabled={testingRemoteName === source.name} onClick={() => testRemoteMcpConnection(source)}>
                        {testingRemoteName === source.name ? "Testing..." : "Test hosted MCP"}
                      </button>
                      {source.provider !== "shortcut" && (
                        <button className="primaryButton compactButton" type="button" disabled={connectingProviderName === source.provider || providerAuth.loading} onClick={() => connectRemoteProvider(source)}>
                          {connectingProviderName === source.provider ? connectingLabel(source.provider) : providerAuthData[source.provider]?.connected ? `Reconnect ${providerLabel(source.provider)}` : connectButtonLabel(source.provider)}
                        </button>
                      )}
                      <details className="advancedDetails">
                        <summary>Advanced provider connection</summary>
                        <p>Endpoint is predefined for this provider. Browser OAuth is saved once for the tool and reused by every workspace.</p>
                        <label className="fieldLabel">
                          MCP query tool
                          <div className="pathPickerRow">
                            <input
                              value={source.query_tool_name || ""}
                              placeholder="Provider MCP search tool"
                              onChange={(event) => updateRemoteMcpSource(index, { query_tool_name: event.target.value })}
                            />
                            <button className="textButton" type="button" disabled={discoveringRemoteName === source.name} onClick={() => discoverRemoteMcpTools(source)}>
                              {discoveringRemoteName === source.name ? "Discovering..." : "Discover"}
                            </button>
                          </div>
                        </label>
                        {supportsFullContentFetch(source) && (
                          <label className="fieldLabel">
                            MCP fetch tool
                            <input
                              value={source.fetch_tool_name || ""}
                              placeholder="Provider MCP fetch tool"
                              onChange={(event) => updateRemoteMcpSource(index, { fetch_tool_name: event.target.value })}
                            />
                          </label>
                        )}
                        {remoteToolResults[source.name]?.length > 0 && (
                          <div className="toolChoiceRow">
                            {remoteToolResults[source.name].map((tool) => {
                              const name = String(tool.name || "");
                              if (!name) return null;
                              return (
                                <button className={source.query_tool_name === name ? "toolChoice active" : "toolChoice"} type="button" key={name} onClick={() => updateRemoteMcpSource(index, { query_tool_name: name })}>
                                  {name}
                                </button>
                              );
                            })}
                          </div>
                        )}
                        <label className="fieldLabel">
                          Remote MCP endpoint
                          <input
                            value={source.endpoint_url || ""}
                            placeholder="https://provider.example/mcp"
                            onChange={(event) => updateRemoteMcpSource(index, { endpoint_url: event.target.value })}
                          />
                        </label>
                      </details>
                      {remoteTestResults[source.name] && <ConnectionTestResult result={remoteTestResults[source.name]} />}
                      {remoteTestErrors[source.name] && (
                        <div className="connectionTest failed">
                          <strong>Hosted MCP failed</strong>
                          <p>{remoteTestErrors[source.name]}</p>
                        </div>
                      )}
                    </div>
                  )}
                </article>
              );
            })}
          </div>
          </div>
        )}
        {saveError && <p className="errorText">{saveError}</p>}
        {help && <InfoDialog help={help} onClose={() => setHelp(null)} />}
      </section>
      <div className="settingsStickySaveBar">
        <div>
          <strong>Connections</strong>
          <p>Save hosted MCP connector and connected-source settings together.</p>
        </div>
        <button className="primaryButton stickySaveButton" type="button" disabled={!config.data || saving} onClick={saveConnections}>
          {saving ? "Saving..." : "Save changes"}
        </button>
      </div>
    </>
  );
}

function ConnectionTestResult({ result }: { result: Record<string, unknown> }) {
  const ok = Boolean(result.ok);
  const documents = Array.isArray(result.documents) ? result.documents.slice(0, 3) : [];
  return (
    <div className={ok ? "connectionTest ok" : "connectionTest failed"}>
      <strong>{ok ? "Connection test passed" : "Connection test failed"}</strong>
      <p>{ok ? `${String(result.result_count || 0)} normalized documents returned.` : String(result.error || "Unknown error")}</p>
      {documents.map((document, index) => {
        const item = getObject(document);
        return (
          <article key={index}>
            <span>{String(item?.source_id || `document ${index + 1}`)}</span>
            <p>{String(item?.title || "")}</p>
          </article>
        );
      })}
    </div>
  );
}

function sourceHelpForKey(sourceKey: string): SourceHelp {
  const fieldNote = "This run toggle is a second layer. The source is used only when it is also enabled and connected in Connections.";
  const help: Record<string, SourceHelp> = {
    source_code: {
      title: "Source code",
      description: "Searches implementation files inside the currently selected workspace repository.",
      details: [
        "Data comes from the local workspace index built from the selected repo.",
        "It uses the code retrieval path, including code graph narrowing plus BM25/Qdrant search.",
      ],
    },
    repo_docs: {
      title: "Repository docs",
      description: "Searches documentation-like files inside the currently selected workspace repository.",
      details: [
        "Data comes from the selected workspace, not from the tool install directory.",
        "Docs are classified during local BM25/Qdrant indexing and kept separate from provider docs like Notion or Confluence.",
      ],
    },
    local_notes: {
      title: "Local notes",
      description: "Searches configured local notes and Obsidian content for the selected workspace.",
      details: [
        "Data comes from local note paths or the configured Obsidian vault.",
        "Obsidian search runs through the local Obsidian hybrid-search adapter when configured.",
      ],
    },
    notebooklm: {
      title: "NotebookLM",
      description: "Uses NotebookLM-derived project context attached to the workspace.",
      details: ["Data is attached as connected-source context, not fetched from the repo index."],
    },
    github_issues: {
      title: "GitHub issues",
      description: "Searches GitHub issues through the hosted GitHub MCP connection.",
      details: [fieldNote, "Scope usually narrows search to an owner/repo or organization."],
    },
    github_pull_requests: {
      title: "GitHub PRs",
      description: "Searches GitHub pull requests through the hosted GitHub MCP connection.",
      details: [fieldNote, "Scope usually narrows search to an owner/repo or organization."],
    },
    notion: {
      title: "Notion",
      description: "Searches Notion pages, databases, data sources, and optionally comments through hosted MCP.",
      details: [fieldNote, "Full-content fetch can retrieve richer content for top search hits."],
    },
    shortcut: {
      title: "Shortcut",
      description: "Searches Shortcut stories, epics, docs, and optionally comments through hosted MCP.",
      details: [fieldNote, "Authentication uses the saved Shortcut API token."],
    },
    jira: {
      title: "Jira",
      description: "Searches Jira issues and related issue context through hosted Atlassian MCP.",
      details: [fieldNote, "The Atlassian browser connection is shared with Confluence."],
    },
    confluence: {
      title: "Confluence",
      description: "Searches Confluence pages, spaces, and optionally comments through hosted Atlassian MCP.",
      details: [fieldNote, "The Atlassian browser connection is shared with Jira."],
    },
    linear: {
      title: "Linear",
      description: "Searches Linear issues, projects, and comments through hosted MCP.",
      details: [fieldNote],
    },
    slack: {
      title: "Slack",
      description: "Searches Slack messages, files, channels, threads, and users through hosted MCP.",
      details: [fieldNote, "Scope can narrow retrieval to a workspace or channel when the provider supports it."],
    },
    google_drive: {
      title: "Google Drive",
      description: "Searches Google Drive docs, sheets, slides, folders, and files through hosted MCP.",
      details: [fieldNote, "Full-content fetch can retrieve richer file content for top search hits."],
    },
  };
  return help[sourceKey] || {
    title: sourceLabels[sourceKey] || sourceKey,
    description: "Searches a configured connected source during retrieval.",
    details: [fieldNote],
  };
}

function connectionHelpForSource(source: RemoteMcpSource): SourceHelp {
  return connectionHelpForProvider(source.provider, source.source_category);
}

function connectionHelpForProvider(provider: string, sourceCategory = ""): SourceHelp {
  const baseFields = connectionFieldHelp(provider);
  if (provider === "github") {
    return {
      title: "GitHub connection",
      description: "Uses GitHub's hosted MCP endpoint to search issues and pull requests for the configured repository or organization scope.",
      details: [
        "Issues and PRs have separate run toggles, but share this browser-authenticated provider connection.",
        "Data is fetched live from GitHub MCP during retrieval when the matching run toggle is enabled.",
      ],
      fields: baseFields,
    };
  }
  if (provider === "notion") {
    return {
      title: "Notion connection",
      description: "Uses hosted Notion MCP to search workspace pages, databases, data sources, and comments allowed by the Notion OAuth connection.",
      details: ["Full-content fetch enriches the best search hits with page-level content when enabled."],
      fields: baseFields,
    };
  }
  if (provider === "shortcut") {
    return {
      title: "Shortcut connection",
      description: "Uses hosted Shortcut MCP to search stories, epics, docs, and comments available to the saved Shortcut API token.",
      details: ["The token is saved at the tool level and reused by workspaces on this machine."],
      fields: baseFields,
    };
  }
  if (provider === "atlassian" && sourceCategory === "issue_tracker") {
    return {
      title: "Jira connection",
      description: "Uses hosted Atlassian MCP to search Jira issues and related issue context.",
      details: ["The Atlassian browser connection is shared with Confluence."],
      fields: baseFields,
    };
  }
  if (provider === "atlassian") {
    return {
      title: "Confluence connection",
      description: "Uses hosted Atlassian MCP to search Confluence pages, spaces, and comments.",
      details: ["The Atlassian browser connection is shared with Jira."],
      fields: baseFields,
    };
  }
  return {
    title: `${providerLabel(provider)} connection`,
    description: `Uses hosted ${providerLabel(provider)} MCP to search provider content during retrieval.`,
    details: ["The connector must be enabled here and selected in the run panel before it contributes evidence."],
    fields: baseFields,
  };
}

function builtInConnectionHelp(name: string): SourceHelp {
  const normalized = name.toLowerCase();
  if (normalized.includes("source")) return sourceHelpForKey("source_code");
  if (normalized.includes("documentation")) return sourceHelpForKey("repo_docs");
  if (normalized.includes("notes")) return sourceHelpForKey("local_notes");
  return {
    title: name,
    description: "Built-in retrieval source configured for this workspace.",
  };
}

function connectionFieldHelp(provider: string): Array<{ name: string; description: string }> {
  const fields = [
    { name: "Scope", description: "Narrows provider search, such as owner/repo, organization, workspace, project, channel, space, or folder." },
    { name: "Result limit", description: "Maximum search results requested from the provider for one retrieval query." },
    { name: "Minimum score", description: "Drops provider results below this relevance score when the provider returns scores." },
    { name: "Fetch full content for top search hits", description: "For supported providers, fetches richer content for the highest-ranked search results." },
    { name: "Full-content fetch limit", description: "Caps how many top hits are enriched with full content." },
    { name: "MCP query/fetch tool and endpoint", description: "Advanced provider MCP details. These are normally predefined and should only be changed when the provider changes its tool names or endpoint." },
  ];
  if (provider !== "notion") {
    fields.splice(3, 0, { name: "Feature toggles", description: "Choose which provider object types can be searched or fetched when the provider adapter supports reliable filtering." });
  }
  if (provider === "shortcut") {
    fields.splice(1, 0, { name: "Shortcut API token", description: "Personal Shortcut API token used to authorize the hosted MCP connection. Saved at the tool level." });
  }
  return fields;
}

function providerLabel(provider: string): string {
  const labels: Record<string, string> = {
    github: "GitHub",
    notion: "Notion",
    atlassian: "Atlassian",
    shortcut: "Shortcut",
    linear: "Linear",
    slack: "Slack",
    google_drive: "Google Drive",
  };
  return labels[provider] || provider;
}

function connectButtonLabel(provider: string): string {
  if (provider === "shortcut") return "Save Shortcut token";
  return `Connect ${providerLabel(provider)} in browser`;
}

function connectingLabel(provider: string): string {
  if (provider === "shortcut") return "Connecting...";
  return "Waiting for browser...";
}

function shortcutTokenConfigured(providerAuthData: Record<string, ProviderAuthState>): boolean {
  return Boolean(providerAuthData.shortcut?.bearer_token_configured || providerAuthData.shortcut?.api_key_configured);
}

function mergeRemoteMcpSources(sources?: RemoteMcpSource[]): RemoteMcpSource[] {
  const defaults = defaultRemoteMcpSources();
  const byName = new Map(defaults.map((source) => [source.name, source]));
  for (const source of sources || []) {
    const current = byName.get(source.name);
    if (current) {
      byName.set(source.name, repairRemoteMcpDefaults({ ...current, ...source, features: { ...(current.features || {}), ...(source.features || {}) } }, current));
    } else {
      byName.set(source.name, source);
    }
  }
  return Array.from(byName.values());
}

function repairRemoteMcpDefaults(source: RemoteMcpSource, defaults: RemoteMcpSource): RemoteMcpSource {
  return {
    ...source,
    title: defaults.title || source.title,
    endpoint_url: source.endpoint_url || defaults.endpoint_url,
    auth_type: source.auth_type || defaults.auth_type,
    query_tool_name: source.query_tool_name || defaults.query_tool_name,
    fetch_tool_name: source.fetch_tool_name || defaults.fetch_tool_name,
    query_argument_name: source.query_argument_name || defaults.query_argument_name,
    limit_argument_name: source.limit_argument_name || defaults.limit_argument_name,
    enrich_results: defaults.enrich_results ? true : source.enrich_results,
    enrich_limit: source.enrich_limit || defaults.enrich_limit,
  };
}

function stripRemoteMcpCredentials(source: RemoteMcpSource): RemoteMcpSource {
  return {
    ...source,
    oauth_access_token: "",
    bearer_token: "",
    api_key: "",
  };
}

function stripLegacyGitHubConnectionConfig(connections: AppConfig["connections"]): AppConfig["connections"] {
  const { github_repository: _repository, github_fetch_issues: _issues, github_fetch_pull_requests: _pullRequests, ...rest } = connections as AppConfig["connections"] & {
    github_repository?: string;
    github_fetch_issues?: boolean;
    github_fetch_pull_requests?: boolean;
  };
  return rest;
}

function parseGitHubRepoScope(scope: string): { owner: string; repo: string } {
  const normalized = scope.trim().replace(/^https:\/\/github\.com\//i, "").replace(/^github\.com\//i, "").replace(/\.git$/i, "").replace(/^\/+|\/+$/g, "");
  const [owner = "", repo = ""] = normalized.split("/");
  return { owner, repo };
}

function formatGitHubRepoScope(owner: string, repo: string): string {
  const cleanOwner = owner.trim().replace(/^\/+|\/+$/g, "");
  const cleanRepo = repo.trim().replace(/^\/+|\/+$/g, "").replace(/\.git$/i, "");
  if (!cleanOwner && !cleanRepo) return "";
  if (!cleanRepo) return cleanOwner;
  if (!cleanOwner) return cleanRepo;
  return `${cleanOwner}/${cleanRepo}`;
}

function supportsFullContentFetch(source: RemoteMcpSource): boolean {
  return ["notion", "atlassian", "shortcut", "linear", "slack", "google_drive"].includes(source.provider);
}

function showsFeatureToggles(source: RemoteMcpSource): boolean {
  return source.provider !== "notion";
}

function requiresConfiguredQueryTool(source: RemoteMcpSource): boolean {
  return !["notion", "atlassian", "shortcut", "linear", "slack", "google_drive"].includes(source.provider);
}

function defaultRemoteMcpSources(): RemoteMcpSource[] {
  const common = {
    enabled: false,
    auth_type: "oauth",
    bearer_token: "",
    oauth_access_token: "",
    api_key: "",
    api_key_header: "",
    oauth_authorize_url: "",
    headers: {},
    scope: "",
    query_argument_name: "query",
    limit_argument_name: "limit",
    result_limit: 5,
    enrich_results: false,
    enrich_limit: 3,
    timeout_seconds: 20,
    min_score: 0,
    static_tool_arguments: {},
    score_fields: ["score", "relevance", "rank_score", "_score"],
    id_fields: ["source_id", "id", "url", "html_url", "key", "number"],
    title_fields: ["title", "name", "summary", "subject"],
    content_fields: ["content", "body", "text", "description", "summary"],
  };
  return [
    { ...common, name: "github-issues", source_key: "github_issues", provider: "github", title: "GitHub issues", source_category: "issue_tracker", endpoint_url: "https://api.githubcopilot.com/mcp/", features: { issues: true }, query_tool_name: "search_issues" },
    { ...common, name: "github-prs", source_key: "github_pull_requests", provider: "github", title: "GitHub PRs", source_category: "pull_request", endpoint_url: "https://api.githubcopilot.com/mcp/", features: { pull_requests: true }, query_tool_name: "search_pull_requests" },
    { ...common, name: "notion-pages", source_key: "notion", provider: "notion", title: "Notion", source_category: "documentation", endpoint_url: "https://mcp.notion.com/mcp", features: { pages: true, databases: true, data_sources: true, comments: false }, query_tool_name: "notion-search", fetch_tool_name: "notion-fetch", enrich_results: true, enrich_limit: 3 },
    { ...common, name: "jira-issues", source_key: "jira", provider: "atlassian", title: "Jira", source_category: "issue_tracker", endpoint_url: "https://mcp.atlassian.com/v1/mcp/authv2", features: { issues: true, comments: true, linked_pages: true, projects: false }, query_tool_name: "searchJiraIssuesUsingJql", fetch_tool_name: "getJiraIssue", enrich_results: true, enrich_limit: 3 },
    { ...common, name: "confluence-pages", source_key: "confluence", provider: "atlassian", title: "Confluence", source_category: "documentation", endpoint_url: "https://mcp.atlassian.com/v1/mcp/authv2", features: { pages: true, spaces: false, comments: false }, query_tool_name: "searchConfluenceUsingCql", fetch_tool_name: "getConfluencePage", enrich_results: true, enrich_limit: 3 },
    { ...common, name: "shortcut-stories", source_key: "shortcut", provider: "shortcut", title: "Shortcut", source_category: "issue_tracker", endpoint_url: "https://mcp.shortcut.com/mcp", features: { stories: true, epics: true, docs: true, comments: false }, query_tool_name: "", fetch_tool_name: "", enrich_results: true, enrich_limit: 3 },
    { ...common, name: "linear-issues", source_key: "linear", provider: "linear", title: "Linear", source_category: "issue_tracker", endpoint_url: "https://mcp.linear.app/sse", features: { issues: true, projects: true, comments: true }, query_tool_name: "", fetch_tool_name: "", enrich_results: true, enrich_limit: 3 },
    { ...common, name: "slack-messages", source_key: "slack", provider: "slack", title: "Slack", source_category: "local_notes", endpoint_url: "https://mcp.slack.com/mcp", features: { messages: true, files: true, channels: false, threads: true, users: false }, query_tool_name: "", fetch_tool_name: "", enrich_results: true, enrich_limit: 3 },
    { ...common, name: "google-drive-documents", source_key: "google_drive", provider: "google_drive", title: "Google Drive", source_category: "documentation", endpoint_url: "https://drivemcp.googleapis.com/mcp/v1", features: { docs: true, sheets: true, slides: true, folders: false, files: true }, query_tool_name: "search_files", fetch_tool_name: "", enrich_results: true, enrich_limit: 3 },
  ];
}

function featureLabel(feature: string): string {
  return feature.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function scopePlaceholder(provider: string): string {
  return {
    github: "owner/repo or org",
    notion: "workspace, page, or database",
    atlassian: "site/project/space",
    shortcut: "workspace/team/project",
    linear: "workspace/team/project",
    slack: "workspace/channel",
    google_drive: "drive/folder/file",
  }[provider] || "workspace/project/scope";
}

function genericSourceLabel(sourceCategory: string): string {
  return {
    source_code: "Source code",
    documentation: "Documentation",
    issue_tracker: "Issue tracker",
    pull_request: "Pull requests",
    local_notes: "Project notes",
    notebooklm: "NotebookLM",
  }[sourceCategory] || sourceCategory;
}

function WorkspaceIndexPanel({
  health,
  config,
  workspaces,
  setConfig,
  estimate,
  indexPrepareLoading,
  indexPrepareMessage,
  refreshBase,
  onPrepareIndex,
  onOpenWorkspace,
}: {
  health?: Health;
  config: LoadState<AppConfig>;
  workspaces: LoadState<WorkspaceEntry[]>;
  setConfig: (state: LoadState<AppConfig>) => void;
  estimate: LoadState<IndexEstimate>;
  indexPrepareLoading: boolean;
  indexPrepareMessage: string;
  onPrepareIndex: () => void;
  refreshBase: () => void;
  onOpenWorkspace: (workspaceRoot: string) => void | Promise<void>;
}) {
  const [workspaceRoot, setWorkspaceRoot] = useState("");
  const [saving, setSaving] = useState(false);
  const [browsing, setBrowsing] = useState(false);
  const [openingWorkspace, setOpeningWorkspace] = useState(false);
  const [browseError, setBrowseError] = useState("");
  const [codexModels, setCodexModels] = useState<LoadState<CodexModelOption[]>>({ loading: false });
  const [apiConnectionTest, setApiConnectionTest] = useState<LoadState<string>>({ loading: false });
  const [codexConnectionTest, setCodexConnectionTest] = useState<LoadState<string>>({ loading: false });
  const connectionsRef = useRef<HTMLElement | null>(null);
  useEffect(() => {
    setWorkspaceRoot(health?.workspace_root || "");
  }, [health?.workspace_root]);

  function updateIndexing(next: Partial<AppConfig["indexing"]>) {
    if (!config.data) return;
    setConfig({
      data: {
        ...config.data,
        indexing: {
          ...config.data.indexing,
          ...next,
        },
      },
      loading: false,
    });
  }

  function updateRetrieval(next: Partial<AppConfig["retrieval"]>) {
    if (!config.data) return;
    setConfig({
      data: {
        ...config.data,
        retrieval: {
          ...config.data.retrieval,
          ...next,
        },
      },
      loading: false,
    });
  }

  function updateGeneration(next: Partial<NonNullable<AppConfig["generation"]>>) {
    if (!config.data) return;
    setConfig({
      data: {
        ...config.data,
        generation: {
          provider: "api",
          ...config.data.generation,
          ...next,
        },
      },
      loading: false,
    });
  }

  function updateApiConnection(next: Partial<NonNullable<AppConfig["connections"]["api_llm"]>>) {
    if (!config.data) return;
    setConfig({
      data: {
        ...config.data,
        connections: {
          ...config.data.connections,
          api_llm: {
            api_style: "openai_chat_completions",
            endpoint_url: "",
            api_key: "",
            model: "",
            temperature: 0,
            max_tokens: 4000,
            timeout_seconds: 120,
            ...config.data.connections.api_llm,
            ...next,
          },
        },
      },
      loading: false,
    });
  }

  function updateCodexConnection(next: Partial<NonNullable<AppConfig["connections"]["codex"]>>) {
    if (!config.data) return;
    setConfig({
      data: {
        ...config.data,
        connections: {
          ...config.data.connections,
          codex: {
            command: ["codex"],
            ignore_user_config: true,
            timeout_seconds: 30,
            ...config.data.connections.codex,
            ...next,
          },
        },
      },
      loading: false,
    });
  }

  async function saveIndexing() {
    if (!config.data) return;
    setSaving(true);
    try {
      const updated = await api.saveConfig(config.data);
      setConfig({ data: updated, loading: false });
      await refreshBase();
    } catch (error) {
      setConfig({ ...config, error: error instanceof Error ? error.message : String(error), loading: false });
    } finally {
      setSaving(false);
    }
  }

  async function browseWorkspace() {
    setBrowseError("");
    setBrowsing(true);
    try {
      const result = await api.browseWorkspace(workspaceRoot || health?.workspace_root || "");
      if (result.picker_available === false) {
        setBrowseError(result.message || "Directory picker is unavailable. Paste the repository path into the field instead.");
        return;
      }
      if (!result.cancelled && result.workspace_root) {
        setWorkspaceRoot(result.workspace_root);
      }
    } catch (error) {
      setBrowseError(error instanceof Error ? error.message : String(error));
    } finally {
      setBrowsing(false);
    }
  }

  const indexing = config.data?.indexing;
  const retrieval = config.data?.retrieval;
  const generation = config.data?.generation || { provider: "api" as const };
  const apiConnection = config.data?.connections.api_llm || {};
  const codexConnection = config.data?.connections.codex || {};
  const isCodexMode = retrieval?.mode === "codex";
  const apiRequired = retrieval?.mode !== "codex" || generation.provider === "api";
  const codexRequired = retrieval?.mode === "codex" || generation.provider === "codex";
  const apiConfigured = Boolean(
    health?.api_llm_configured ||
    (apiConnection.endpoint_url && (apiConnection.api_key || apiConnection.api_key_configured) && (apiConnection.model || retrieval?.workspace_model || generation.api_model))
  );
  const codexConfigured = Boolean(health?.codex_configured);
  const selectedWorkspaceValue = workspaces.data?.some((workspace) => workspace.workspace_root === workspaceRoot) ? workspaceRoot : "";
  useEffect(() => {
    if (!codexRequired) {
      setCodexModels({ loading: false });
      return;
    }
    let cancelled = false;
    setCodexModels((current) => ({ data: current.data, loading: true }));
    api.codexModels()
      .then((result) => {
        if (!cancelled) setCodexModels({ data: result.models, loading: false });
      })
      .catch((error) => {
        if (!cancelled) setCodexModels({ error: error instanceof Error ? error.message : String(error), loading: false });
      });
    return () => {
      cancelled = true;
    };
  }, [codexRequired, health?.workspace_root]);

  function focusConnections() {
    connectionsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function testApiConnection() {
    setApiConnectionTest({ loading: true });
    try {
      const result = await api.testApiLlmConnection({
        api_style: apiConnection.api_style || "openai_chat_completions",
        endpoint_url: apiConnection.endpoint_url || "",
        api_key: apiConnection.api_key || "",
        model: apiConnection.model || generation.api_model || retrieval?.workspace_model || "",
        temperature: Number(apiConnection.temperature ?? 0),
        max_tokens: 64,
        timeout_seconds: Math.min(Number(apiConnection.timeout_seconds ?? generation.timeout_seconds ?? 30), 15),
      });
      setApiConnectionTest({ data: `Verified ${result.model || "model"} at ${result.endpoint_url || "endpoint"}.`, loading: false });
    } catch (error) {
      setApiConnectionTest({ error: error instanceof Error ? error.message : String(error), loading: false });
    }
  }

  async function testCodexConnection() {
    setCodexConnectionTest({ loading: true });
    try {
      const result = await api.testCodexConnection({
        command: codexConnection.command?.length ? codexConnection.command : retrieval?.codex_command || ["codex"],
        ignore_user_config: codexConnection.ignore_user_config ?? true,
        timeout_seconds: Number(codexConnection.timeout_seconds ?? 30),
      });
      if (result.models?.length) setCodexModels({ data: result.models, loading: false });
      setCodexConnectionTest({ data: `Verified Codex CLI with ${result.model_count || result.models?.length || 0} model options.`, loading: false });
    } catch (error) {
      setCodexConnectionTest({ error: error instanceof Error ? error.message : String(error), loading: false });
    }
  }

  async function openSelectedWorkspace() {
    if (!workspaceRoot.trim()) return;
    setBrowseError("");
    setOpeningWorkspace(true);
    try {
      await onOpenWorkspace(workspaceRoot);
    } finally {
      setOpeningWorkspace(false);
    }
  }

  return (
    <>
      <section className="panel" id="workspace">
        <div className="panelHeader">
          <div>
            <h2>Workspace</h2>
            <p className="panelPurpose">Select the repository and local project context this tool can inspect.</p>
          </div>
        </div>
        <label className="fieldLabel">
          Repository path
          {!!workspaces.data?.length && (
            <select
              value={selectedWorkspaceValue}
              disabled={openingWorkspace}
              onChange={(event) => {
                if (event.target.value) setWorkspaceRoot(event.target.value);
              }}
            >
              <option value="">Choose previous repository...</option>
              {workspaces.data.map((workspace) => (
                <option key={workspace.workspace_root} value={workspace.workspace_root} disabled={!workspace.exists}>
                  {workspace.current ? "Current: " : ""}
                  {workspace.name} - {workspace.workspace_root}
                  {!workspace.exists ? " (missing)" : ""}
                </option>
              ))}
            </select>
          )}
          <div className="pathPickerRow">
            <input
              value={workspaceRoot}
              disabled={openingWorkspace}
              placeholder="Browse or type in full path to the directory"
              onChange={(event) => setWorkspaceRoot(event.target.value)}
            />
            <button className="textButton" type="button" disabled={browsing || openingWorkspace} onClick={browseWorkspace}>
              {browsing ? "Browsing..." : "Browse"}
            </button>
          </div>
        </label>
        <button className="primaryButton" type="button" disabled={!workspaceRoot.trim() || openingWorkspace} onClick={openSelectedWorkspace}>
          {openingWorkspace ? "Switching workspace..." : "Switch to selected workspace"}
        </button>
        {openingWorkspace && (
          <div className="workspaceLoadingLine" aria-live="polite">
            <div className="progressLine">
              <span />
            </div>
            <p>Opening repository and refreshing workspace data.</p>
          </div>
        )}
        {browseError && <p className="errorText">{browseError}</p>}
      </section>

      <section className="panel" id="indexing-settings">
        <div className="panelHeader">
          <div>
            <h2>Evidence Retrieval</h2>
            <p className="panelPurpose">Choose how code evidence is found before an answer is generated.</p>
          </div>
          {!isCodexMode && <button className="textButton" type="button" onClick={refreshBase}>Refresh estimate</button>}
        </div>
        {retrieval && (
          <>
            <label className="fieldLabel">
              Evidence provider
              <select value={retrieval.mode || "workspace"} onChange={(event) => updateRetrieval({ mode: event.target.value as AppConfig["retrieval"]["mode"] })}>
                <option value="workspace">Native workspace retrieval</option>
                <option value="codex">Codex retrieval</option>
              </select>
            </label>
            {retrieval.mode === "codex" && (
              <p
                className="infoText"
                title="Codex mode asks Codex to inspect the selected workspace directly, so local BM25, embeddings, Qdrant, and CodeGraph index preparation are not used."
              >
                Codex mode reads the selected workspace directly and does not use BM25, embeddings, Qdrant, or CodeGraph indexing.
              </p>
            )}
            <DependencyNotice
              ok={retrieval.mode === "codex" ? codexConfigured : apiConfigured}
              label={retrieval.mode === "codex" ? "Requires Codex CLI" : "Requires OpenAI-compatible API"}
              detail={
                retrieval.mode === "codex"
                  ? (codexConfigured ? health?.codex_status_detail || "Codex CLI available." : "Codex retrieval needs a verified Codex CLI connection.")
                  : (apiConfigured ? health?.api_llm_status_detail || "API connection configured." : "Native retrieval still requires the API connection for retrieval planning.")
              }
              onConfigure={focusConnections}
            />
            {retrieval.mode !== "codex" && (
              <label className="fieldLabel">
                Retrieval API model
                <input
                  value={retrieval.workspace_model || ""}
                  placeholder={apiConnection.model || "gpt-5.1-mini"}
                  onChange={(event) => updateRetrieval({ workspace_model: event.target.value })}
                />
              </label>
            )}
            {retrieval.mode === "codex" && (
              <>
                <label className="fieldLabel" title="The model passed to Codex for evidence retrieval runs. Model options are loaded from the local Codex model catalog.">
                  Codex model
                  <select
                    value={retrieval.codex_model || ""}
                    disabled={codexModels.loading || !codexModels.data?.length}
                    onChange={(event) => updateRetrieval({ codex_model: event.target.value })}
                  >
                    {codexModelOptions(codexModels.data, retrieval.codex_model).map((model) => (
                      <option key={model.slug} value={model.slug}>
                        {model.display_name || model.slug}
                        {model.default_reasoning_level ? ` (${model.default_reasoning_level})` : ""}
                      </option>
                    ))}
                  </select>
                </label>
                {codexModels.loading && <p className="noticeText">Loading Codex models...</p>}
                {codexModels.error && <p className="errorText">Could not load Codex models: {codexModels.error}</p>}
                <div className="indexSummary">
                  <Metric
                    label="Prompt profile"
                    value={retrieval.codex_prompt_profile || health?.codex_prompt_profile || "efficient"}
                    description="Prompt profile controls the Codex evidence-gathering prompt contract. The efficient profile is the lower-cost baseline used for CodeRepoQA-style code evidence retrieval."
                  />
                  <Metric label="Timeout" value={`${retrieval.codex_timeout_seconds || 900}s`} description="Maximum time allowed for one Codex evidence retrieval run." />
                  <Metric
                    label="Indexing"
                    value="Skipped"
                    description="Codex mode asks Codex to inspect the selected workspace directly, so local BM25, embeddings, Qdrant, and CodeGraph index preparation are not used."
                  />
                </div>
              </>
            )}
            {retrieval.mode !== "codex" && estimate.data && estimate.data.file_count > 0 && (
              <IndexPreparationNotice
                estimate={estimate.data}
                indexPrepareLoading={indexPrepareLoading}
                onPrepareIndex={onPrepareIndex}
                indexingEnabled={estimate.data.enable_indexing}
              />
            )}
          </>
        )}
        {!isCodexMode && indexing && (
          <>
            <label className="checkRow">
              <input
                type="checkbox"
                checked={indexing.enable_indexing}
                onChange={(event) => updateIndexing({ enable_indexing: event.target.checked })}
              />
              <span>Allow indexing when missing or stale</span>
            </label>
            <label className="fieldLabel">
              Do not index these directories/files
              <textarea
                rows={5}
                value={indexing.exclude_paths.join("\n")}
                onChange={(event) => updateIndexing({ exclude_paths: linesToList(event.target.value) })}
              />
            </label>
          </>
        )}
        {!isCodexMode && estimate.data && (
          <div className="indexSummary">
            <Metric label="Files" value={formatCount(estimate.data.file_count)} />
            <Metric label="Chunks est." value={formatCount(estimate.data.estimated_chunks)} />
            <Metric label="Size" value={`${(estimate.data.total_bytes / 1024 / 1024).toFixed(1)} MB`} />
            <Metric label="CodeGraph est." value={formatStructuralEstimateDuration(estimate.data)} />
          </div>
        )}
        {!isCodexMode && estimate.data?.index_estimate_notes?.map((note) => (
          <p className="noticeText" key={note}>{note}</p>
        ))}
        {!isCodexMode && indexPrepareMessage && <p className="noticeText">{indexPrepareMessage}</p>}
        {!isCodexMode && estimate.error && <p className="errorText">{estimate.error}</p>}
        {config.error && <p className="errorText">{config.error}</p>}
      </section>

      <section className="panel" id="generation-settings">
        <div className="panelHeader">
          <div>
            <h2>Explanation Generation</h2>
            <p className="panelPurpose">Choose how final explanations, checks, and evidence graph text are generated.</p>
          </div>
        </div>
        <label className="fieldLabel">
          Generation provider
          <select value={generation.provider || "api"} onChange={(event) => updateGeneration({ provider: event.target.value as "api" | "codex" })}>
            <option value="api">OpenAI-compatible API</option>
            <option value="codex">Codex CLI</option>
          </select>
        </label>
        <DependencyNotice
          ok={generation.provider === "codex" ? codexConfigured : apiConfigured}
          label={generation.provider === "codex" ? "Requires Codex CLI" : "Requires OpenAI-compatible API"}
          detail={
            generation.provider === "codex"
              ? (codexConfigured ? health?.codex_status_detail || "Codex CLI available." : "Codex generation needs a verified Codex CLI connection.")
              : (apiConfigured ? health?.api_llm_status_detail || "API connection configured." : "API generation requires an endpoint URL, API key, and model.")
          }
          onConfigure={focusConnections}
        />
        {generation.provider === "codex" ? (
          <label className="fieldLabel">
            Codex generation model
            <select
              value={generation.codex_model || retrieval?.codex_model || ""}
              disabled={codexModels.loading || !codexModels.data?.length}
              onChange={(event) => updateGeneration({ codex_model: event.target.value })}
            >
              {codexModelOptions(codexModels.data, generation.codex_model || retrieval?.codex_model).map((model) => (
                <option key={model.slug} value={model.slug}>
                  {model.display_name || model.slug}
                  {model.default_reasoning_level ? ` (${model.default_reasoning_level})` : ""}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <label className="fieldLabel">
            API generation model
            <input
              value={generation.api_model || ""}
              placeholder={apiConnection.model || "gpt-5.1"}
              onChange={(event) => updateGeneration({ api_model: event.target.value })}
            />
          </label>
        )}
        <div className="settingsGrid twoColumn">
          <label className="fieldLabel">
            Completion token limit (optional)
            <input type="number" min={1} placeholder="Provider default" value={generation.max_tokens ?? ""} onChange={(event) => updateGeneration({ max_tokens: event.target.value === "" ? null : Math.max(1, Number(event.target.value)) })} />
          </label>
          <label className="fieldLabel">
            Timeout seconds
            <input type="number" min={1} value={generation.timeout_seconds || 120} onChange={(event) => updateGeneration({ timeout_seconds: Number(event.target.value) || 120 })} />
          </label>
        </div>
      </section>

      <section className="panel" id="workspace-connections" ref={connectionsRef}>
        <div className="panelHeader">
          <div>
            <h2>LLM Providers</h2>
            <p className="panelPurpose">Configure model providers used by retrieval or explanation generation.</p>
          </div>
        </div>
        <div className="workspaceConnectionsGrid">
          <div className="settingsCard">
            <div className="settingsCardHeader">
              <div>
                <h3>OpenAI-compatible API</h3>
                <p>Used by native retrieval and API-based explanation generation.</p>
              </div>
              <span className={apiConfigured ? "statusPill connected" : "statusPill"}>{apiConfigured ? "Configured" : "Not configured"}</span>
            </div>
            <label className="fieldLabel">
              Endpoint URL
              <input value={apiConnection.endpoint_url || ""} placeholder="https://api.openai.com/v1/chat/completions" onChange={(event) => updateApiConnection({ endpoint_url: event.target.value })} />
            </label>
            <label className="fieldLabel">
              API key
              <input type="password" value={apiConnection.api_key || ""} placeholder={apiConnection.api_key_configured || health?.api_llm_configured ? "API key saved. Paste a new key to replace it." : "Paste API key"} onChange={(event) => updateApiConnection({ api_key: event.target.value })} />
            </label>
            <label className="fieldLabel">
              Default API model
              <input value={apiConnection.model || ""} placeholder="gpt-5.1-mini" onChange={(event) => updateApiConnection({ model: event.target.value })} />
            </label>
            <div className="settingsGrid twoColumn">
              <label className="fieldLabel">
                Temperature
                <input type="number" step="0.1" value={apiConnection.temperature ?? 0} onChange={(event) => updateApiConnection({ temperature: Number(event.target.value) || 0 })} />
              </label>
              <label className="fieldLabel">
                Timeout seconds
                <input type="number" min={1} value={apiConnection.timeout_seconds || 30} onChange={(event) => updateApiConnection({ timeout_seconds: Number(event.target.value) || 30 })} />
              </label>
            </div>
            <button className="textButton connectionTestButton" type="button" disabled={apiConnectionTest.loading} onClick={testApiConnection}>
              {apiConnectionTest.loading ? "Testing API..." : "Test API"}
            </button>
            {apiConnectionTest.data && <p className="connectionSuccessText">{apiConnectionTest.data}</p>}
            {apiConnectionTest.error && <p className="errorText">{apiConnectionTest.error}</p>}
          </div>
          <div className="settingsCard">
            <div className="settingsCardHeader">
              <div>
                <h3>Codex CLI</h3>
                <p>Used by Codex retrieval and Codex-based explanation generation.</p>
              </div>
              <span className={codexConfigured ? "statusPill connected" : "statusPill"}>{codexConfigured ? "Configured" : "Not configured"}</span>
            </div>
            <label className="fieldLabel">
              Command
              <input
                value={(codexConnection.command || retrieval?.codex_command || ["codex"]).join(" ")}
                onChange={(event) => updateCodexConnection({ command: linesToList(event.target.value.replace(/\s+/g, "\n")) })}
              />
            </label>
            <label className="fieldLabel">
              Timeout seconds
              <input type="number" min={1} value={codexConnection.timeout_seconds || 30} onChange={(event) => updateCodexConnection({ timeout_seconds: Number(event.target.value) || 30 })} />
            </label>
            <label className="checkRow codexIgnoreToggle">
              <input
                type="checkbox"
                checked={codexConnection.ignore_user_config ?? true}
                onChange={(event) => updateCodexConnection({ ignore_user_config: event.target.checked })}
              />
              <span>Ignore global Codex user config for LLM calls</span>
            </label>
            <button className="textButton connectionTestButton" type="button" disabled={codexConnectionTest.loading} onClick={testCodexConnection}>
              {codexConnectionTest.loading ? "Testing Codex..." : "Test Codex"}
            </button>
            {codexConnectionTest.data && <p className="connectionSuccessText">{codexConnectionTest.data}</p>}
            {codexConnectionTest.error && <p className="errorText">{codexConnectionTest.error}</p>}
          </div>
        </div>
      </section>
      <div className="settingsStickySaveBar">
        <div>
          <strong>Workspace settings</strong>
          <p>Save retrieval, generation, and LLM provider changes together.</p>
        </div>
        <button className="primaryButton stickySaveButton" type="button" disabled={!config.data || saving} onClick={saveIndexing}>
          {saving ? "Saving..." : "Save changes"}
        </button>
      </div>
    </>
  );
}

function ConnectionTile({ name, status, detail, onInfo }: { name: string; status: string; detail: string; onInfo: () => void }) {
  return (
    <div className="connectionTile">
      <div>
        <h3>{name}</h3>
        <p>{detail}</p>
      </div>
      <div className="connectionTileMeta">
        <span>{status}</span>
        <InfoButton label={`Explain ${name}`} onClick={onInfo} />
      </div>
    </div>
  );
}

function DependencyNotice({ ok, label, detail, onConfigure }: { ok: boolean; label: string; detail: string; onConfigure: () => void }) {
  if (ok) return null;
  return (
    <div className="dependencyNotice warning">
      <div>
        <strong>{label}</strong>
        <p>{detail}</p>
      </div>
      {!ok && (
        <button className="textButton compactButton" type="button" onClick={onConfigure}>
          Configure
        </button>
      )}
    </div>
  );
}

function InfoButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      className="infoButton"
      type="button"
      aria-label={label}
      title={label}
      onClick={(event) => {
        event.preventDefault();
        event.stopPropagation();
        onClick();
      }}
    >
      i
    </button>
  );
}

function InfoDialog({ help, onClose }: { help: SourceHelp; onClose: () => void }) {
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return (
    <div className="dialogOverlay" role="presentation" onClick={onClose}>
      <section
        className="infoDialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="source-info-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="dialogHeader">
          <h3 id="source-info-title">{help.title}</h3>
          <button className="iconButton" type="button" aria-label="Close dialog" onClick={onClose}>Close</button>
        </div>
        <p>{help.description}</p>
        {help.details && help.details.length > 0 && (
          <ul className="helpList">
            {help.details.map((detail) => <li key={detail}>{detail}</li>)}
          </ul>
        )}
        {help.fields && help.fields.length > 0 && (
          <dl className="fieldHelpList">
            {help.fields.map((field) => (
              <div key={field.name}>
                <dt>{field.name}</dt>
                <dd>{field.description}</dd>
              </div>
            ))}
          </dl>
        )}
      </section>
    </div>
  );
}

function linesToList(value: string): string[] {
  return value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
}

function codexModelOptions(models: CodexModelOption[] | undefined, currentModel: string | undefined): CodexModelOption[] {
  const current = (currentModel || "").trim();
  const visible = (models || []).filter((model) => model.visibility !== "hide" || model.slug === current);
  if (current && !visible.some((model) => model.slug === current)) {
    return [
      {
        slug: current,
        display_name: current,
        description: "Configured Codex model.",
        default_reasoning_level: "",
        supported_reasoning_levels: [],
        visibility: "configured",
        supported_in_api: false,
        priority: null,
        additional_speed_tiers: [],
      },
      ...visible,
    ];
  }
  return visible;
}

function listToCommaSeparated(value: string[]): string {
  return value.join(", ");
}

function commaSeparatedToList(value: string): string[] {
  const output: string[] = [];
  for (const item of value.split(",")) {
    const text = item.trim();
    if (text && !output.includes(text)) output.push(text);
  }
  return output;
}

function numberOrDefault(value: string, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? Math.round(parsed) : fallback;
}

function numberOrZero(value: string): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : 0;
}

function SettingsPanel({ health, config, setConfig }: { health?: Health; config: LoadState<AppConfig>; setConfig: (state: LoadState<AppConfig>) => void }) {
  const [saving, setSaving] = useState(false);
  async function save() {
    if (!config.data) return;
    setSaving(true);
    try {
      const updated = await api.saveConfig(config.data);
      setConfig({ data: updated, loading: false });
    } catch (error) {
      setConfig({ ...config, error: error instanceof Error ? error.message : String(error), loading: false });
    } finally {
      setSaving(false);
    }
  }
  return (
    <section className="panel" id="settings">
      <div className="panelHeader">
        <h2>Settings</h2>
        <button className="textButton" type="button" onClick={save} disabled={!config.data || saving}>{saving ? "Saving" : "Save"}</button>
      </div>
      <dl className="settingsList">
        <dt>Config</dt>
        <dd>{health?.config_path || "Unknown"}</dd>
        <dt>Runs</dt>
        <dd>{health?.runs_dir || config.data?.runs_dir || "Unknown"}</dd>
      </dl>
      {config.error && <p className="errorText">{config.error}</p>}
    </section>
  );
}

function RunSummaryPanel({ runs, selectedRunId, setSelectedRunId, runDetail }: {
  runs: LoadState<RunSummary[]>;
  selectedRunId: string;
  setSelectedRunId: (value: string) => void;
  runDetail: LoadState<RunDetail>;
}) {
  const selectedRunExists = Boolean(selectedRunId && (runs.data || []).some((run) => run.run_id === selectedRunId));
  const selected = selectedRunExists && runDetail.data?.run_id === selectedRunId ? runDetail.data : undefined;
  return (
    <section className="panel historyPanel">
      <div className="panelHeader">
        <h2>Run History</h2>
        <span className="panelMeta">{runs.data?.length || 0} runs</span>
      </div>
      <div className="runList">
        {(runs.data || []).map((run) => {
          const timestamp = formatRunTimestamp(run.run_id);
          const label = run.title || run.prompt || run.run_id;
          return (
            <button className={run.run_id === selectedRunId ? "runRow selected" : "runRow"} type="button" onClick={() => setSelectedRunId(run.run_id)} key={run.run_id}>
              <span className="runIdentity">
                <span className="runTitle">{label}</span>
                <span className="runId">{run.run_id}</span>
                {timestamp && <span className="runTimestamp">{timestamp}</span>}
              </span>
              <strong>{run.status === "running" ? run.phase || "running" : run.coverage_status}</strong>
            </button>
          );
        })}
        {!runs.loading && !runs.data?.length && <p className="emptyText">No runs yet.</p>}
      </div>
      {selected && (
        <div className="summaryBar">
          <Metric label="Coverage" value={selected.coverage_status} />
          <Metric label="Status" value={selected.status || "complete"} />
          <Metric label="Sufficient" value={String(selected.sufficient)} />
          <Metric label="Evidence" value={String(selected.selected_count)} />
          <Metric label="Time" value={formatOptionalDuration(selected.elapsed_seconds)} />
          <Metric label="Tokens" value={formatTokenUsage(selected.token_usage)} />
          {selected.prompt && (
            <div className="selectedRunPrompt">
              <span>Prompt</span>
              <p>{selected.prompt}</p>
            </div>
          )}
        </div>
      )}
      {selected?.status === "running" && selected.index_estimate && (
        <div className="indexNotice">
          <strong>Indexing is missing, preparing.</strong>
          <span>
            Estimated scope: {formatCount(selected.index_estimate.file_count)} files / {formatCount(selected.index_estimate.estimated_chunks)} chunks.
          </span>
        </div>
      )}
      {runs.error && <p className="errorText">{runs.error}</p>}
    </section>
  );
}

function Metric({ label, value, description }: { label: string; value: string; description?: string }) {
  return (
    <div className={description ? "metric metricWithTooltip" : "metric"} title={description}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function formatCount(value: unknown): string {
  return typeof value === "number" && Number.isFinite(value) ? value.toLocaleString() : "unknown";
}

function formatTokenUsage(usage: RunSummary["token_usage"]): string {
  if (!usage || !Number.isFinite(usage.total_tokens) || usage.total_tokens <= 0) return "unknown";
  const total = usage.total_tokens.toLocaleString();
  if (usage.prompt_tokens > 0 || usage.completion_tokens > 0) {
    return `${total} (${usage.prompt_tokens.toLocaleString()} in / ${usage.completion_tokens.toLocaleString()} out)`;
  }
  return total;
}

function formatOptionalDuration(seconds: unknown): string {
  return typeof seconds === "number" && Number.isFinite(seconds) && seconds > 0 ? formatDuration(seconds) : "unknown";
}

function formatRunTimestamp(runId: string): string {
  const match = /^run-(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z/.exec(runId);
  if (!match) return "";
  const [, year, month, day, hour, minute, second] = match;
  const date = new Date(Date.UTC(Number(year), Number(month) - 1, Number(day), Number(hour), Number(minute), Number(second)));
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatIndexEstimateDuration(estimate: IndexEstimate): string {
  if (
    typeof estimate.estimated_seconds_min === "number" &&
    Number.isFinite(estimate.estimated_seconds_min) &&
    typeof estimate.estimated_seconds_max === "number" &&
    Number.isFinite(estimate.estimated_seconds_max)
  ) {
    return formatDurationRange(estimate.estimated_seconds_min, estimate.estimated_seconds_max);
  }
  const chunks = typeof estimate.estimated_chunks === "number" && Number.isFinite(estimate.estimated_chunks) ? estimate.estimated_chunks : 0;
  const files = typeof estimate.file_count === "number" && Number.isFinite(estimate.file_count) ? estimate.file_count : 0;
  if (chunks <= 0 || files <= 0) return "unknown";
  const minSeconds = Math.max(10, chunks * 0.05 + files * 0.002);
  const maxSeconds = Math.max(minSeconds + 10, chunks * 0.15 + files * 0.006);
  return formatDurationRange(minSeconds, maxSeconds);
}

function formatStructuralEstimateDuration(estimate: IndexEstimate): string {
  if (
    typeof estimate.structural_estimated_seconds_min === "number" &&
    Number.isFinite(estimate.structural_estimated_seconds_min) &&
    typeof estimate.structural_estimated_seconds_max === "number" &&
    Number.isFinite(estimate.structural_estimated_seconds_max)
  ) {
    return formatDurationRange(estimate.structural_estimated_seconds_min, estimate.structural_estimated_seconds_max);
  }
  return formatIndexEstimateDuration(estimate);
}

function formatDurationRange(minValue: unknown, maxValue: unknown): string {
  if (typeof minValue !== "number" || typeof maxValue !== "number") return "unknown";
  if (!Number.isFinite(minValue) || !Number.isFinite(maxValue)) return "unknown";
  if (minValue <= 0 && maxValue <= 0) return "unknown";
  return `${formatDuration(minValue)}-${formatDuration(maxValue)}`;
}

function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds)) return "unknown";
  if (seconds < 60) return `${Math.max(1, Math.round(seconds))}s`;
  const minutes = Math.round(seconds / 60);
  return `${minutes}m`;
}

function formatDateTime(value: string): string {
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) return value;
  return new Date(timestamp).toLocaleString();
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function GuidedResponsePanel({
  runDetail,
  checks,
  evaluations,
  loading,
  error,
  onSubmit,
}: {
  runDetail?: RunDetail;
  checks: UnderstandingCheck[];
  evaluations: AnswerEvaluation[];
  loading: boolean;
  error: string;
  onSubmit: (answers: Record<string, string>) => void;
}) {
  const [answers, setAnswers] = useState<Record<string, string>>({});

  useEffect(() => {
    const next: Record<string, string> = {};
    for (const check of checks) next[check.id] = answers[check.id] || "";
    setAnswers(next);
  }, [runDetail?.run_id]);

  const content = getResponseContent(runDetail);
  const responseHeadings = getMarkdownHeadings(content);
  const canSubmit = checks.length > 0 && checks.every((check) => (answers[check.id] || "").trim()) && !loading && evaluations.length === 0;
  const conceptDefinitions = getConceptDefinitions(runDetail);
  const sourceAttributions = getSourceAttributions(runDetail);
  const nextChecks = getNextChecks(runDetail);
  const intentSufficiency = getIntentSufficiency(runDetail);
  const evidence = runDetail?.evidence || [];
  const totalEvidence = runDetail?.candidate_evidence?.length
    ?? runDetail?.evidence_organization?.candidate_count
    ?? evidence.length;
  const selectedEvidence = runDetail?.evidence_organization?.selected_refs?.length ?? evidence.length;
  return (
    <section className="panel" id="guided-response">
      <div className="panelHeader">
        <h2>Guided Explanation</h2>
        <span className="panelMeta">
          {checks.length ? `${checks.length} checks` : "no checks"} · {totalEvidence} total evidence · {selectedEvidence} selected
        </span>
      </div>
      {content ? (
        <div className="responseReadingArea">
          {responseHeadings.length >= 3 && (
            <nav className="responseOutline" aria-label="Explanation sections">
              <strong>Sections</strong>
              <div>
                {responseHeadings.map((heading) => (
                  <a className={`responseOutlineLevel-${heading.level}`} href={`#${heading.id}`} key={heading.id}>
                    {heading.label}
                  </a>
                ))}
              </div>
            </nav>
          )}
          <div className="responseText">
            {renderMarkdown(content, {
              conceptDefinitions,
              sourceAttributions,
              evidence,
              runId: runDetail?.run_id,
            })}
          </div>
        </div>
      ) : <p className="emptyText">Run retrieval to generate an explanation.</p>}
      {intentSufficiency.length > 0 && (
        <details className="hintBox">
          <summary>Experimental evidence sufficiency</summary>
          {intentSufficiency.map((item) => <p key={item.intent}><strong>{item.intent}</strong>: {item.overall}</p>)}
        </details>
      )}
      {nextChecks.length > 0 && <NextChecksBox checks={nextChecks} />}
      {checks.length > 0 && (
        <div className="questionBox">
          <div className="questionHeader">
            <h3>Understanding Checks</h3>
            <span>{evaluations.length ? "evaluated" : "answer required"}</span>
          </div>
          {checks.map((check) => {
            const evaluation = evaluations.find((item) => item.question_id === check.id);
            return (
              <article className="questionCard" key={check.id}>
                <p>{check.question}</p>
                <textarea
                  rows={4}
                  value={answers[check.id] || ""}
                  disabled={evaluations.length > 0}
                  onChange={(event) => setAnswers({ ...answers, [check.id]: event.target.value })}
                  placeholder="Write your answer..."
                />
                <HintLadder check={check} />
                {evaluation && (
                  <div className={`evaluation ${evaluation.status}`}>
                    <strong>{evaluation.status}</strong>
                    <p>{evaluation.feedback}</p>
                    {evaluation.missing_points.length > 0 && <small>Missing: {evaluation.missing_points.join("; ")}</small>}
                  </div>
                )}
              </article>
            );
          })}
          {error && <p className="errorText">{error}</p>}
          {evaluations.length === 0 && (
            <button className="primaryButton" type="button" disabled={!canSubmit} onClick={() => onSubmit(answers)}>
              {loading ? "Checking..." : "Submit answers"}
            </button>
          )}
        </div>
      )}
    </section>
  );
}

function HintLadder({ check }: { check: UnderstandingCheck }) {
  const [visibleCount, setVisibleCount] = useState(0);
  const visibleHints = check.hints.slice(0, visibleCount);
  const nextHint = check.hints[visibleCount];
  return (
    <div className="hintBox">
      {visibleHints.map((hint, index) => (
        <p key={hint.kind}><strong>Hint {index + 1}</strong>: {hint.text}</p>
      ))}
      {nextHint && (
        <button type="button" className="hintRevealButton" onClick={() => setVisibleCount((count) => count + 1)}>
          {visibleCount === 0 ? "Show first hint" : "Reveal next hint"}
        </button>
      )}
    </div>
  );
}

function NextChecksBox({ checks }: { checks: NextCheck[] }) {
  return (
    <div className="nextChecksBox">
      <h3>Suggested checks</h3>
      {checks.map((check, index) => (
        <article className="nextCheckCard" key={`${check.action}-${index}`}>
          <h4>{check.scenario}</h4>
          <p className="nextCheckAction">{check.action}</p>
          <dl>
            <div>
              <dt>Look for</dt>
              <dd>{check.if_result}</dd>
            </div>
            <div>
              <dt>Means</dt>
              <dd>{check.then_interpretation}</dd>
            </div>
          </dl>
        </article>
      ))}
    </div>
  );
}

const EVIDENCE_GRAPH_NODE_WIDTH = 250;
const EVIDENCE_GRAPH_NODE_HEIGHT = 92;

const evidenceConnectionColors: Record<EvidenceConnection["relationship_kind"], string> = {
  dependency: "#475569",
  control_flow: "#047857",
  data_flow: "#2563eb",
  configuration: "#7c3aed",
  validation: "#b45309",
  rendering: "#be123c",
  other: "#64748b",
};

type EvidenceGraphMode = "all" | "selected";

const evidenceStatusLabels: Record<EvidenceAssessmentStatus, string> = {
  core: "Core",
  supporting: "Supporting",
  adjacent: "Adjacent",
  redundant: "Redundant",
  unclear: "Unclear",
};

function EvidenceGraphPanel({ graph, selectedEvidence, candidates, organization }: {
  graph?: EvidenceConnectionsGraph;
  selectedEvidence: EvidenceItem[];
  candidates: EvidenceItem[];
  organization?: EvidenceOrganization;
}) {
  const connections = graph?.connections || [];
  const [mode, setMode] = useState<EvidenceGraphMode>("all");
  const [selectedEdgeId, setSelectedEdgeId] = useState("");
  const [selectedNodeRef, setSelectedNodeRef] = useState("");
  const visibleConnections = mode === "all" ? (graph?.candidate_connections || connections) : connections;
  const activeEdgeId = selectedEdgeId || (visibleConnections.length ? "connection-0" : "");
  const selectedConnection = visibleConnections[Number(activeEdgeId.replace("connection-", ""))] || visibleConnections[0];
  const selectedRefs = useMemo(
    () => new Set(organization?.selected_refs?.length ? organization.selected_refs : selectedEvidence.map((item) => item.source_id)),
    [organization?.selected_refs, selectedEvidence],
  );
  const visibleEvidence = useMemo(
    () => mode === "selected" ? candidates.filter((item) => selectedRefs.has(item.source_id)) : candidates,
    [candidates, mode, selectedRefs],
  );
  const assessmentsByRef = useMemo(
    () => new Map((organization?.assessments || []).map((assessment) => [assessment.evidence_ref, assessment])),
    [organization?.assessments],
  );
  const evidenceByRef = useMemo(() => new Map(candidates.map((item) => [item.source_id, item])), [candidates]);
  const flow = useMemo(
    () => evidenceGraphElements(visibleConnections, visibleEvidence, assessmentsByRef, selectedRefs, activeEdgeId, mode === "all"),
    [visibleConnections, visibleEvidence, assessmentsByRef, selectedRefs, activeEdgeId, mode],
  );
  const selectedNode = selectedNodeRef ? evidenceByRef.get(selectedNodeRef) : undefined;
  const selectedAssessment = selectedNodeRef ? assessmentsByRef.get(selectedNodeRef) : undefined;
  const disconnectedReason = graph?.disconnected_evidence?.find((item) => item.evidence_ref === selectedNodeRef)?.reason;
  const connectedRefs = useMemo(() => new Set(connections.flatMap((item) => [item.source_ref, item.target_ref])), [connections]);
  const connectedSelectedCount = [...selectedRefs].filter((ref) => connectedRefs.has(ref)).length;
  const disconnectedSelectedCount = selectedRefs.size - connectedSelectedCount;

  useEffect(() => {
    setSelectedEdgeId("");
    setSelectedNodeRef("");
    setMode("all");
  }, [graph]);

  if (!flow.nodes.length) return null;
  const source = selectedConnection ? evidenceByRef.get(selectedConnection.source_ref) : undefined;
  const target = selectedConnection ? evidenceByRef.get(selectedConnection.target_ref) : undefined;
  return (
    <section className="panel evidenceGraphPanel" id="evidence-flow">
      <div className="panelHeader evidenceGraphHeader">
        <div>
          <h2>Evidence Flow</h2>
          <span className="panelMeta">
            {mode === "all"
              ? `${candidates.length} candidates · ${selectedRefs.size} selected`
              : `${selectedRefs.size} selected · ${connectedSelectedCount} connected · ${disconnectedSelectedCount} disconnected`}
          </span>
        </div>
        <div className="evidenceGraphModeSwitch" aria-label="Evidence graph mode">
          <button className={mode === "all" ? "active" : ""} type="button" onClick={() => setMode("all")}>All candidates</button>
          <button className={mode === "selected" ? "active" : ""} type="button" onClick={() => setMode("selected")}>Selected only</button>
        </div>
      </div>
      {mode === "all" && organization?.assessments?.length ? (
        <div className="evidenceGraphLegend">
          {(Object.keys(evidenceStatusLabels) as EvidenceAssessmentStatus[]).map((status) => (
            <span className={`evidenceStatus evidenceStatus-${status}`} key={status}>{evidenceStatusLabels[status]}</span>
          ))}
          <span className="selectedEvidenceLegend">Selected for generation</span>
        </div>
      ) : null}
      {graph?.status === "error" && <p className="errorText">{graph.error || "Evidence connections could not be generated; candidates remain inspectable."}</p>}
      {mode === "all" && graph?.candidate_connections_error && <p className="errorText">{graph.candidate_connections_error}</p>}
      <div className="evidenceGraphCanvas">
        <ReactFlow
          key={mode}
          nodes={flow.nodes}
          edges={flow.edges}
          fitView
          fitViewOptions={{ padding: 0.16, maxZoom: 0.9 }}
          minZoom={0.2}
          maxZoom={1.5}
          nodesDraggable={false}
          nodesConnectable={false}
          onEdgeClick={(_, edge) => setSelectedEdgeId(edge.id)}
          onNodeClick={(_, node) => setSelectedNodeRef(node.id)}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#d7dee9" gap={22} size={1} />
          <MiniMap pannable zoomable nodeColor="#557a70" maskColor="rgba(226, 232, 240, 0.5)" />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
      {selectedConnection && (
        <article className="evidenceConnectionDetail">
          <div className="evidenceConnectionTitle">
            <span style={{ backgroundColor: evidenceConnectionColors[selectedConnection.relationship_kind] }}>
              {formatConnectionKind(selectedConnection.relationship_kind)}
            </span>
            <h3>{selectedConnection.label}</h3>
          </div>
          <p>{selectedConnection.description}</p>
          <div className="evidenceConnectionRoute">
            <code>{evidenceNodePath(source, selectedConnection.source_ref)}</code>
            <span aria-hidden="true">→</span>
            <code>{evidenceNodePath(target, selectedConnection.target_ref)}</code>
          </div>
          <dl className="evidenceConnectionMeta">
            <div><dt>Grounding</dt><dd>{selectedConnection.grounding}</dd></div>
            <div><dt>Confidence</dt><dd>{selectedConnection.confidence}</dd></div>
            <div><dt>Relationship</dt><dd>{formatConnectionKind(selectedConnection.relationship_kind)}</dd></div>
          </dl>
        </article>
      )}
      {selectedNode && (
        <div className="dialogOverlay" role="presentation" onClick={() => setSelectedNodeRef("")}>
          <article className="evidenceNodeDialog" role="dialog" aria-modal="true" aria-labelledby="evidence-node-dialog-title" onClick={(event) => event.stopPropagation()}>
            <div className="dialogHeader">
              <div>
                <div className="evidenceNodeDialogBadges">
                  {selectedRefs.has(selectedNode.source_id) && <span className="selectedEvidenceLegend">Selected for generation</span>}
                  {selectedAssessment && <span className={`evidenceStatus evidenceStatus-${selectedAssessment.status}`}>{evidenceStatusLabels[selectedAssessment.status]}</span>}
                </div>
                <h3 id="evidence-node-dialog-title">{String(selectedNode.metadata?.coverage_area || "Evidence candidate")}</h3>
                <code>{evidenceNodePath(selectedNode, selectedNode.source_id)}</code>
              </div>
              <button className="textButton compactButton" type="button" onClick={() => setSelectedNodeRef("")}>Close</button>
            </div>
            <dl className="evidenceNodeDetails">
              <div><dt>Claim supported</dt><dd>{String(selectedNode.metadata?.claim_supported || "Not supplied")}</dd></div>
              <div><dt>Why relevant</dt><dd>{String(selectedNode.metadata?.why_relevant || "Not supplied")}</dd></div>
              {selectedAssessment && <div><dt>Organizer assessment</dt><dd>{selectedAssessment.reason}</dd></div>}
              {selectedAssessment?.facet_ids?.length ? <div><dt>Coverage facets</dt><dd>{selectedAssessment.facet_ids.join(", ")}</dd></div> : null}
              <div><dt>Artifact kind</dt><dd>{String(selectedNode.metadata?.deterministic_artifact_kind || selectedNode.metadata?.artifact_kind || "unknown")}</dd></div>
              {disconnectedReason && <div><dt>Why disconnected</dt><dd>{disconnectedReason}</dd></div>}
            </dl>
            <pre className="evidenceDialogCode">{selectedNode.snippet}</pre>
          </article>
        </div>
      )}
    </section>
  );
}

function evidenceGraphElements(
  connections: EvidenceConnection[],
  evidence: EvidenceItem[],
  assessments: Map<string, NonNullable<EvidenceOrganization["assessments"]>[number]>,
  selectedRefs: Set<string>,
  activeEdgeId: string,
  emphasizeSelected: boolean,
): { nodes: Node[]; edges: Edge[] } {
  const evidenceByRef = new Map(evidence.map((item) => [item.source_id, item]));
  const validConnections = connections.filter(
    (connection) => evidenceByRef.has(connection.source_ref) && evidenceByRef.has(connection.target_ref),
  );
  const nodeRefs = evidence.map((item) => item.source_id);
  const graph = new dagre.graphlib.Graph();
  graph.setDefaultEdgeLabel(() => ({}));
  graph.setGraph({ rankdir: "LR", ranksep: 105, nodesep: 42, marginx: 24, marginy: 24 });
  for (const ref of nodeRefs) graph.setNode(ref, { width: EVIDENCE_GRAPH_NODE_WIDTH, height: EVIDENCE_GRAPH_NODE_HEIGHT });
  validConnections.forEach((connection, index) => graph.setEdge(connection.source_ref, connection.target_ref, { index }));
  dagre.layout(graph);

  const nodes: Node[] = nodeRefs.map((ref) => {
    const item = evidenceByRef.get(ref)!;
    const position = graph.node(ref);
    const path = String(item.metadata?.path || sourcePathFromId(item.source_id));
    const lineRange = String(item.metadata?.line_range || "");
    const role = String(item.metadata?.coverage_area || "Source evidence");
    const assessment = assessments.get(ref);
    return {
      id: ref,
      className: [
        "evidenceCandidateNode",
        assessment ? `evidenceCandidateNode-${assessment.status}` : "evidenceCandidateNode-unassessed",
        emphasizeSelected && selectedRefs.has(ref) ? "evidenceCandidateNode-selected" : "",
      ].filter(Boolean).join(" "),
      position: { x: position.x - EVIDENCE_GRAPH_NODE_WIDTH / 2, y: position.y - EVIDENCE_GRAPH_NODE_HEIGHT / 2 },
      data: {
        label: (
          <div className="evidenceGraphNodeLabel" title={String(item.metadata?.claim_supported || "")}>
            <div className="evidenceGraphNodeHeading">
              <strong>{role}</strong>
              {assessment && <small>{evidenceStatusLabels[assessment.status]}</small>}
            </div>
            <span>{path}</span>
            <small>{lineRange}</small>
          </div>
        ),
      },
      style: { width: EVIDENCE_GRAPH_NODE_WIDTH, minHeight: EVIDENCE_GRAPH_NODE_HEIGHT },
    };
  });
  const edges: Edge[] = validConnections.map((connection, index) => {
    const id = `connection-${index}`;
    const color = evidenceConnectionColors[connection.relationship_kind];
    const active = id === activeEdgeId;
    return {
      id,
      source: connection.source_ref,
      target: connection.target_ref,
      label: connection.label,
      markerEnd: { type: MarkerType.ArrowClosed, color },
      style: { stroke: color, strokeWidth: active ? 3 : 2 },
      labelStyle: { fill: "#1f2937", fontSize: 12, fontWeight: active ? 750 : 650 },
      labelBgStyle: { fill: "#ffffff", fillOpacity: 0.94 },
      labelBgPadding: [6, 4],
      labelBgBorderRadius: 4,
      animated: false,
    };
  });
  return { nodes, edges };
}

function evidenceNodePath(item: EvidenceItem | undefined, fallback: string): string {
  if (!item) return fallback;
  const path = String(item.metadata?.path || sourcePathFromId(item.source_id));
  const lineRange = String(item.metadata?.line_range || "");
  return `${path}${lineRange ? `:${lineRange}` : ""}`;
}

function formatConnectionKind(value: EvidenceConnection["relationship_kind"]): string {
  return value.replaceAll("_", " ");
}

function EvidencePanel({ runId, selectedEvidence, candidates, organization }: {
  runId?: string;
  selectedEvidence: EvidenceItem[];
  candidates: EvidenceItem[];
  organization?: EvidenceOrganization;
}) {
  const selectedRefs = new Set(organization?.selected_refs?.length ? organization.selected_refs : selectedEvidence.map((item) => item.source_id));
  const assessments = new Map((organization?.assessments || []).map((assessment) => [assessment.evidence_ref, assessment]));
  const sourceCounts = new Map<string, number>();
  for (const item of candidates) {
    const source = item.source_key || item.metadata?.source_key || item.source_category;
    sourceCounts.set(source, (sourceCounts.get(source) || 0) + 1);
  }
  return (
    <section className="panel evidencePanel" id="evidence">
      <div className="panelHeader">
        <h2>Evidence</h2>
        <span className="panelMeta">{candidates.length} total · {selectedRefs.size} selected</span>
      </div>
      <div className="sourcePills">
        {[...sourceCounts.entries()].map(([source, count]) => (
          <span key={source}>{sourceLabels[source] || source}: {count}</span>
        ))}
      </div>
      <div className="evidenceList">
        {candidates.map((item) => (
          <EvidenceCard
            item={item}
            runId={runId}
            assessment={assessments.get(item.source_id)}
            selected={selectedRefs.has(item.source_id)}
            key={item.source_id}
          />
        ))}
        {!candidates.length && <p className="emptyText">Run retrieval to inspect code and connected-source evidence.</p>}
      </div>
    </section>
  );
}

type EvidenceAssessment = NonNullable<EvidenceOrganization["assessments"]>[number];

function EvidenceCard({ item, runId, source, assessment, selected = false }: {
  item?: EvidenceItem;
  runId?: string;
  source?: SelectedSource;
  assessment?: EvidenceAssessment;
  selected?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const [opening, setOpening] = useState(false);
  const [error, setError] = useState("");
  const evidence = item || source?.evidence;
  const title = source ? "" : evidence?.metadata?.coverage_area || evidence?.source_category || "Source evidence";
  const sourceId = source ? `${source.path}${source.lineRange ? `:${source.lineRange}` : ""}` : evidence?.source_id || source?.href || "";
  const openPath = source?.href || (evidence ? evidenceHrefFromItem(evidence) : "");
  const snippet = evidence?.snippet || "";
  const claimSupported = String(evidence?.metadata?.claim_supported || "").trim();
  const whyRelevant = String(evidence?.metadata?.why_relevant || "").trim();
  const coverageArea = String(evidence?.metadata?.coverage_area || "").trim();

  useEffect(() => {
    if (!expanded) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setExpanded(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [expanded]);

  async function openInVsCode() {
    if (!runId || !openPath) return;
    setOpening(true);
    setError("");
    try {
      await api.openRunSourceFile(runId, openPath);
    } catch (error) {
      setError(error instanceof Error ? error.message : String(error));
    } finally {
      setOpening(false);
    }
  }

  return (
    <article className="evidenceCard">
      <div className="evidenceCardHeader">
        <div className="evidenceMeta">
          {item && (
            <div className="evidenceCardBadges">
              {assessment
                ? <span className={`evidenceStatus evidenceStatus-${assessment.status}`}>{evidenceStatusLabels[assessment.status]}</span>
                : <span className="evidenceStatus evidenceStatus-unassessed">Unassessed</span>}
              {selected && <span className="selectedEvidenceLegend">Selected</span>}
            </div>
          )}
          {title && <span>{title}</span>}
          <strong>{sourceId}</strong>
        </div>
        <div className="evidenceCardActions">
          <button className="textButton compactButton" type="button" onClick={() => setExpanded(true)} disabled={!snippet}>
            Expand
          </button>
          <button className="textButton compactButton" type="button" onClick={openInVsCode} disabled={!runId || !openPath || opening}>
            {opening ? "Opening..." : "Open in VS Code"}
          </button>
        </div>
      </div>
      {(claimSupported || whyRelevant || coverageArea) && (
        <dl className="evidenceReferenceDetails">
          {claimSupported && <div><dt>What this code shows</dt><dd>{claimSupported}</dd></div>}
          {whyRelevant && <div><dt>How it helps answer your question</dt><dd>{whyRelevant}</dd></div>}
          {coverageArea && <div><dt>Part of the answer</dt><dd>{coverageArea}</dd></div>}
        </dl>
      )}
      {snippet ? (
        <pre>{snippet}</pre>
      ) : (
        <p className="emptyText">No selected snippet is available for this source.</p>
      )}
      {error && <p className="errorText">{error}</p>}
      {expanded && (
        <div className="dialogOverlay" role="presentation" onClick={() => setExpanded(false)}>
          <article className="evidenceDialog" role="dialog" aria-modal="true" aria-labelledby="evidence-dialog-title" onClick={(event) => event.stopPropagation()}>
            <div className="dialogHeader">
              <div className="evidenceMeta">
                {title && <span>{title}</span>}
                <h3 id="evidence-dialog-title">{sourceId}</h3>
              </div>
              <button className="textButton compactButton" type="button" onClick={() => setExpanded(false)}>
                Close
              </button>
            </div>
            {(claimSupported || whyRelevant || coverageArea) && (
              <dl className="evidenceReferenceDetails expandedEvidenceReferenceDetails">
                {claimSupported && <div><dt>What this code shows</dt><dd>{claimSupported}</dd></div>}
                {whyRelevant && <div><dt>How it helps answer your question</dt><dd>{whyRelevant}</dd></div>}
                {coverageArea && <div><dt>Part of the answer</dt><dd>{coverageArea}</dd></div>}
              </dl>
            )}
            <pre className="evidenceDialogCode">{snippet}</pre>
          </article>
        </div>
      )}
    </article>
  );
}

function TracePanel({ trace, state }: { trace: Array<Record<string, unknown>>; state: LoadState<RunTrace> }) {
  return (
    <section className="panel tracePanel" id="trace">
      <div className="panelHeader">
        <h2>Trace</h2>
        <span className="panelMeta">{trace.length} events</span>
      </div>
      <div className="traceList">
        {trace.slice(-18).reverse().map((event, index) => (
          <details className="traceRow" key={`${event.event_type}-${index}`}>
            <summary>
              <span>{String(event.event_type || "event")}</span>
              <small>{String(event.created_at || "")}</small>
            </summary>
            <pre>{JSON.stringify(event.payload || event, null, 2)}</pre>
          </details>
        ))}
        {!state.loading && !trace.length && <p className="emptyText">Trace events will appear after a run.</p>}
        {state.error && <p className="errorText">{state.error}</p>}
      </div>
    </section>
  );
}

type MarkdownRenderContext = {
  conceptDefinitions: ConceptDefinition[];
  sourceAttributions: SourceAttribution[];
  evidence: EvidenceItem[];
  runId?: string;
};

type SelectedSource = {
  label: string;
  href: string;
  path: string;
  lineRange: string;
  evidence?: EvidenceItem;
};

function renderMarkdown(markdown: string, context: MarkdownRenderContext): ReactNode[] {
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  const nodes: ReactNode[] = [];
  let index = 0;
  while (index < lines.length) {
    const line = lines[index];
    const trimmed = line.trim();
    if (!trimmed) {
      index += 1;
      continue;
    }
    if (trimmed.startsWith("```")) {
      const language = trimmed.slice(3).trim();
      const codeLines: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].trim().startsWith("```")) {
        codeLines.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) index += 1;
      nodes.push(<MarkdownCodeBlock code={codeLines.join("\n")} language={language} key={`code-${index}`} />);
      continue;
    }
    const heading = /^(#{1,4})\s+(.+)$/.exec(trimmed);
    if (heading) {
      const level = heading[1].length;
      const text = renderInlineMarkdown(heading[2], context);
      const id = markdownHeadingId(heading[2], index);
      if (level === 1) nodes.push(<h1 id={id} key={`h-${index}`}>{text}</h1>);
      else if (level === 2) nodes.push(<h2 id={id} key={`h-${index}`}>{text}</h2>);
      else nodes.push(<h3 id={id} key={`h-${index}`}>{text}</h3>);
      index += 1;
      continue;
    }
    if (isMarkdownTableStart(lines, index)) {
      const headers = parseMarkdownTableRow(lines[index]);
      index += 2;
      const rows: string[][] = [];
      while (index < lines.length && isMarkdownTableRow(lines[index])) {
        rows.push(parseMarkdownTableRow(lines[index]));
        index += 1;
      }
      nodes.push(
        <div className="markdownTableWrap" key={`table-${index}`}>
          <table className="markdownTable">
            <thead>
              <tr>{headers.map((cell, cellIndex) => <th key={`th-${cellIndex}`}>{renderInlineMarkdown(cell, context)}</th>)}</tr>
            </thead>
            <tbody>
              {rows.map((row, rowIndex) => (
                <tr key={`tr-${rowIndex}`}>
                  {headers.map((_header, cellIndex) => (
                    <td key={`td-${rowIndex}-${cellIndex}`}>{renderInlineMarkdown(row[cellIndex] || "", context)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }
    if (/^[-*]\s+/.test(trimmed)) {
      const items: ReactNode[] = [];
      while (index < lines.length && /^[-*]\s+/.test(lines[index].trim())) {
        items.push(<li key={`li-${index}`}>{renderInlineMarkdown(lines[index].trim().replace(/^[-*]\s+/, ""), context)}</li>);
        index += 1;
      }
      nodes.push(<ul key={`ul-${index}`}>{items}</ul>);
      continue;
    }
    if (isOrderedListLine(trimmed)) {
      const items: ReactNode[] = [];
      while (index < lines.length) {
        const itemLine = lines[index].trim();
        if (!itemLine) {
          const nextLine = nextNonEmptyLine(lines, index + 1);
          if (nextLine && isOrderedListLine(nextLine)) {
            index += 1;
            continue;
          }
          break;
        }
        if (!isOrderedListLine(itemLine)) break;
        items.push(<li key={`oli-${index}`}>{renderInlineMarkdown(itemLine.replace(/^\d+[.)]\s+/, ""), context)}</li>);
        index += 1;
      }
      nodes.push(<ol key={`ol-${index}`}>{items}</ol>);
      continue;
    }
    if (isStandaloneMarkdownLink(trimmed)) {
      const items: ReactNode[] = [];
      while (index < lines.length && isStandaloneMarkdownLink(lines[index].trim())) {
        items.push(<span className="sourceChipItem" key={`source-link-${index}`}>{renderInlineMarkdown(normalizeStandaloneMarkdownLink(lines[index].trim()), context)}</span>);
        index += 1;
      }
      nodes.push(<div className="sourceChipGroup" key={`source-links-${index}`}>{items}</div>);
      continue;
    }
    const paragraph: string[] = [trimmed];
    index += 1;
    while (
      index < lines.length &&
      lines[index].trim() &&
      !lines[index].trim().startsWith("```") &&
      !/^(#{1,4})\s+/.test(lines[index].trim()) &&
      !isMarkdownTableStart(lines, index) &&
      !/^[-*]\s+/.test(lines[index].trim()) &&
      !/^\d+[.)]\s+/.test(lines[index].trim())
    ) {
      paragraph.push(lines[index].trim());
      index += 1;
    }
    nodes.push(<p key={`p-${index}`}>{renderInlineMarkdown(paragraph.join(" "), context)}</p>);
  }
  return nodes;
}

type MarkdownHeading = {
  id: string;
  label: string;
  level: number;
};

function getMarkdownHeadings(markdown: string): MarkdownHeading[] {
  if (!markdown) return [];
  const headings: MarkdownHeading[] = [];
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  let insideCodeFence = false;
  lines.forEach((line, index) => {
    if (line.trim().startsWith("```")) {
      insideCodeFence = !insideCodeFence;
      return;
    }
    if (insideCodeFence) return;
    const match = /^(#{1,4})\s+(.+)$/.exec(line.trim());
    if (!match) return;
    headings.push({
      id: markdownHeadingId(match[2], index),
      label: plainMarkdownLabel(match[2]),
      level: match[1].length,
    });
  });
  return headings;
}

function markdownHeadingId(text: string, lineIndex: number): string {
  const slug = plainMarkdownLabel(text)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
  return `explanation-${slug || "section"}-${lineIndex}`;
}

function plainMarkdownLabel(text: string): string {
  return text
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/[*_`~]/g, "")
    .trim();
}

function MarkdownCodeBlock({ code, language }: { code: string; language: string }) {
  const [copyStatus, setCopyStatus] = useState<"idle" | "copied" | "error">("idle");
  const resetTimer = useRef<number | undefined>(undefined);

  useEffect(() => () => {
    if (resetTimer.current !== undefined) window.clearTimeout(resetTimer.current);
  }, []);

  async function copyCode() {
    try {
      await navigator.clipboard.writeText(code);
      setCopyStatus("copied");
    } catch {
      setCopyStatus("error");
    }
    if (resetTimer.current !== undefined) window.clearTimeout(resetTimer.current);
    resetTimer.current = window.setTimeout(() => setCopyStatus("idle"), 1800);
  }

  const copyLabel = copyStatus === "copied" ? "Copied" : copyStatus === "error" ? "Copy failed" : "Copy";
  return (
    <div className="markdownCodeBlock">
      <div className="markdownCodeToolbar">
        <span>{language || "code"}</span>
        <button type="button" onClick={copyCode}>{copyLabel}</button>
      </div>
      <pre className="markdownCode">
        <code className={language ? `language-${language}` : undefined} data-language={language || undefined}>{code}</code>
      </pre>
    </div>
  );
}

function renderInlineMarkdown(text: string, context: MarkdownRenderContext): ReactNode[] {
  const parts = text.split(/(\[[^\]]+\]\([^)]+\)|`[^`]+`|\*\*[^*]+\*\*)/g).filter(Boolean);
  return parts.map((part, index) => {
    const link = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(part);
    if (link) {
      return <SourceMarkdownLink label={link[1]} href={link[2]} context={context} key={index} />;
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return <ConceptText text={part.slice(1, -1)} definitions={context.conceptDefinitions} sourceAttributions={context.sourceAttributions} code key={index} />;
    }
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index}><ConceptText text={part.slice(2, -2)} definitions={context.conceptDefinitions} sourceAttributions={context.sourceAttributions} /></strong>;
    }
    return <ConceptText text={part} definitions={context.conceptDefinitions} sourceAttributions={context.sourceAttributions} key={index} />;
  });
}

function isStandaloneMarkdownLink(text: string): boolean {
  return /^\[[^\]]+\]\([^)]+\)\.?$/.test(text.trim());
}

function normalizeStandaloneMarkdownLink(text: string): string {
  return text.trim().replace(/\.$/, "");
}

function isOrderedListLine(text: string): boolean {
  return /^\d+[.)]\s+/.test(text);
}

function nextNonEmptyLine(lines: string[], startIndex: number): string {
  for (let index = startIndex; index < lines.length; index += 1) {
    const trimmed = lines[index].trim();
    if (trimmed) return trimmed;
  }
  return "";
}

function SourceMarkdownLink({ label, href, context }: { label: string; href: string; context: MarkdownRenderContext }) {
  const [expanded, setExpanded] = useState(false);
  const itemRef = useRef<HTMLSpanElement>(null);
  const normalizedHref = href.replace(/^\.?\//, "");
  const [path, anchor = ""] = normalizedHref.split("#", 2);
  const selectedSource = sourceFromHref(label, normalizedHref, context.evidence);

  useEffect(() => {
    if (!expanded) return;
    const closeOnOutsideClick = (event: globalThis.MouseEvent) => {
      if (!itemRef.current?.contains(event.target as Node)) setExpanded(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setExpanded(false);
    };
    document.addEventListener("mousedown", closeOnOutsideClick);
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOnOutsideClick);
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [expanded]);

  function openPanel(event: MouseEvent<HTMLAnchorElement>) {
    event.preventDefault();
    setExpanded((current) => !current);
  }
  return (
    <span className={expanded ? "sourceMarkdownItem expanded" : "sourceMarkdownItem"} ref={itemRef}>
      <a
        className={expanded ? "sourceMarkdownLink expanded" : "sourceMarkdownLink"}
        href={normalizedHref}
        onClick={openPanel}
        aria-expanded={expanded}
        title={`Preview ${path}${anchor ? ` at ${anchor}` : ""}`}
      >
        <span className="sourceLinkLabel">{sourceFileName(path) || label}</span>
      </a>
      {expanded && context.runId && (
        <span className="sourceReferencePopover" role="dialog" aria-label={`Evidence preview for ${sourceFileName(path) || label}`}>
          <EvidenceCard runId={context.runId} source={selectedSource} />
        </span>
      )}
    </span>
  );
}

function sourceFileName(path: string): string {
  const segments = normalizeSourcePath(path).split("/");
  return segments[segments.length - 1] || path;
}

function sourceFromHref(label: string, href: string, evidence: EvidenceItem[]): SelectedSource {
  const [path, anchor = ""] = href.split("#", 2);
  const lineRange = anchor.replace(/^L/, "L");
  return {
    label,
    href,
    path,
    lineRange,
    evidence: matchingEvidence(path, lineRange, evidence),
  };
}

function matchingEvidence(path: string, lineRange: string, evidence: EvidenceItem[]): EvidenceItem | undefined {
  const normalizedPath = path.replace(/\\/g, "/");
  const exact = evidence.find((item) => {
    const metadata = item.metadata || {};
    return normalizeSourcePath(String(metadata.path || sourcePathFromId(item.source_id))) === normalizedPath
      && String(metadata.line_range || sourceLineRangeFromId(item.source_id)) === lineRange;
  });
  if (exact) return exact;
  return evidence.find((item) => normalizeSourcePath(String(item.metadata?.path || sourcePathFromId(item.source_id))) === normalizedPath);
}

function evidenceHrefFromItem(item: EvidenceItem): string {
  const metadata = item.metadata || {};
  const path = normalizeSourcePath(String(metadata.path || sourcePathFromId(item.source_id)));
  const lineRange = String(metadata.line_range || sourceLineRangeFromId(item.source_id));
  return path ? `${path}${lineRange ? `#${lineRange}` : ""}` : "";
}

function sourcePathFromId(sourceId: string): string {
  const match = /^[^:]+:(.*):L\d+(?:-L\d+)?$/.exec(sourceId);
  return match ? match[1] : "";
}

function sourceLineRangeFromId(sourceId: string): string {
  const match = /:(L\d+(?:-L\d+)?)$/.exec(sourceId);
  return match ? match[1] : "";
}

function normalizeSourcePath(path: string): string {
  return path.replace(/\\/g, "/").replace(/^\.?\//, "");
}

type ConceptDefinition = {
  label: string;
  description: string;
  evidence_refs?: string[];
};

function ConceptText({ text, definitions, sourceAttributions = [], code = false }: { text: string; definitions: ConceptDefinition[]; sourceAttributions?: SourceAttribution[]; code?: boolean }) {
  const sourceMap = sourceAttributionMap(sourceAttributions);
  const sourcePattern = sourceAttributionPattern(sourceAttributions);
  if (sourcePattern) {
    const parts = text.split(sourcePattern).filter(Boolean);
    const content = parts.map((part, index) => {
      const attribution = sourceMap.get(part);
      if (attribution) return <SourceAttributionTerm attribution={attribution} key={`${part}-${index}`} />;
      return <ConceptText text={part} definitions={definitions} sourceAttributions={[]} code={false} key={`${part}-${index}`} />;
    });
    return code ? <code>{content}</code> : <>{content}</>;
  }
  const definitionMap = conceptDefinitionMap(definitions);
  const pattern = conceptDefinitionPattern(definitions);
  if (!pattern) {
    return code ? <code>{text}</code> : <>{text}</>;
  }
  const parts = text.split(pattern).filter(Boolean);
  const content = parts.map((part, index) => {
    const definition = definitionMap.get(part);
    if (!definition) return <span key={`${part}-${index}`}>{part}</span>;
    return <ConceptTerm definition={definition} key={`${part}-${index}`} />;
  });
  return code ? <code>{content}</code> : <>{content}</>;
}

function SourceAttributionTerm({ attribution }: { attribution: SourceAttribution }) {
  const source = attribution.source_ref || attribution.source_kind;
  const note = attribution.note || source;
  return (
    <span className="sourceAttributionTerm" tabIndex={0}>
      {attribution.quote}
      <span className="sourceAttributionTooltip" role="tooltip">
        <strong>{source}</strong>
        <span>{note}</span>
      </span>
    </span>
  );
}

function ConceptTerm({ definition }: { definition: ConceptDefinition }) {
  return (
    <span className="conceptTerm" tabIndex={0}>
      {definition.label}
      <span className="conceptTooltip" role="tooltip">
        {definition.description}
      </span>
    </span>
  );
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function conceptDefinitionMap(definitions: ConceptDefinition[]): Map<string, ConceptDefinition> {
  return new Map(definitions.map((definition) => [definition.label, definition]));
}

function conceptDefinitionPattern(definitions: ConceptDefinition[]): RegExp | undefined {
  const labels = definitions.map((definition) => definition.label).filter(Boolean).sort((left, right) => right.length - left.length);
  if (!labels.length) return undefined;
  return new RegExp(`(${labels.map(escapeRegExp).join("|")})`, "g");
}

function sourceAttributionMap(attributions: SourceAttribution[]): Map<string, SourceAttribution> {
  return new Map(attributions.map((attribution) => [attribution.quote, attribution]));
}

function sourceAttributionPattern(attributions: SourceAttribution[]): RegExp | undefined {
  const quotes = attributions.map((attribution) => attribution.quote).filter(Boolean).sort((left, right) => right.length - left.length);
  if (!quotes.length) return undefined;
  return new RegExp(`(${quotes.map(escapeRegExp).join("|")})`, "g");
}

function getResponseContent(runDetail?: RunDetail): string {
  const response = getObject(runDetail?.result?.response_payload);
  return stripLeakedCheckMarkdown(String(response?.content || ""));
}

function stripLeakedCheckMarkdown(content: string): string {
  return content
    .replace(/(?:\n\s*---\s*)?\n\s*(?:\*\*)?Understanding checks?(?:\*\*)?\s*:\s*[\s\S]*$/i, "")
    .replace(/(?:\n\s*---\s*)?\n\s*(?:#{1,6}\s*)?Understanding checks?\s*:?\s*[\s\S]*$/i, "")
    .replace(/(?:\n\s*---\s*)?\n\s*(?:#{1,6}\s*)?Next checks?\s*:?\s*[\s\S]*$/i, "")
    .trim();
}

function getUnderstandingChecks(runDetail?: RunDetail): UnderstandingCheck[] {
  const response = getObject(runDetail?.result?.response_payload);
  const metadata = getObject(response?.metadata);
  const raw = metadata?.understanding_checks;
  if (!Array.isArray(raw)) return [];
  return raw.filter(isUnderstandingCheck);
}

function getConceptDefinitions(runDetail?: RunDetail): ConceptDefinition[] {
  const response = getObject(runDetail?.result?.response_payload);
  const metadata = getObject(response?.metadata);
  const raw = metadata?.concept_definitions;
  if (!Array.isArray(raw)) return [];
  const definitions: ConceptDefinition[] = [];
  for (const item of raw) {
    const definition = getObject(item);
    const label = typeof definition?.label === "string" ? definition.label.trim() : "";
    const description = typeof definition?.description === "string" ? definition.description.trim() : "";
    if (!label || !description) continue;
    const evidenceRefs = Array.isArray(definition.evidence_refs)
      ? definition.evidence_refs.filter((ref): ref is string => typeof ref === "string" && Boolean(ref.trim()))
      : [];
    definitions.push({ label, description, evidence_refs: evidenceRefs });
  }
  return definitions;
}

function getSourceAttributions(runDetail?: RunDetail): SourceAttribution[] {
  const response = getObject(runDetail?.result?.response_payload);
  const metadata = getObject(response?.metadata);
  const raw = metadata?.source_attributions;
  if (!Array.isArray(raw)) return [];
  const attributions: SourceAttribution[] = [];
  for (const item of raw) {
    const attribution = getObject(item);
    const quote = typeof attribution?.quote === "string" ? attribution.quote.trim() : "";
    const sourceKind = typeof attribution?.source_kind === "string" ? attribution.source_kind.trim() : "";
    const sourceRef = typeof attribution?.source_ref === "string" ? attribution.source_ref.trim() : "";
    const note = typeof attribution?.note === "string" ? attribution.note.trim() : "";
    if (!quote || !sourceKind) continue;
    attributions.push({ quote, source_kind: sourceKind, source_ref: sourceRef, note });
  }
  return attributions;
}

function getNextChecks(runDetail?: RunDetail): NextCheck[] {
  const response = getObject(runDetail?.result?.response_payload);
  const metadata = getObject(response?.metadata);
  const raw = metadata?.next_checks;
  if (!Array.isArray(raw)) return [];
  const checks: NextCheck[] = [];
  for (const item of raw) {
    const check = getObject(item);
    const scenario = typeof check?.scenario === "string" ? check.scenario.trim() : "";
    const action = typeof check?.action === "string" ? check.action.trim() : "";
    const ifResult = typeof check?.if_result === "string" ? check.if_result.trim() : "";
    const thenInterpretation = typeof check?.then_interpretation === "string" ? check.then_interpretation.trim() : "";
    if (!scenario || !action || !ifResult || !thenInterpretation) continue;
    checks.push({ scenario, action, if_result: ifResult, then_interpretation: thenInterpretation });
  }
  return checks;
}

function getObject(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : undefined;
}

function isUnderstandingCheck(value: unknown): value is UnderstandingCheck {
  const item = getObject(value);
  return Boolean(
    item &&
      typeof item.id === "string" &&
      typeof item.intent === "string" &&
      Array.isArray(item.target_stage_ids) &&
      Array.isArray(item.prerequisite_stage_ids) &&
      typeof item.stem_family === "string" &&
      typeof item.reasoning_focus === "string" &&
      typeof item.selection_reason === "string" &&
      typeof item.question === "string" &&
      Array.isArray(item.hints) &&
      item.hints.length === 3 &&
      item.hints.every((hint) => {
        const parsed = getObject(hint);
        return Boolean(parsed && typeof parsed.kind === "string" && typeof parsed.text === "string");
      }) &&
      Array.isArray(item.expected_answer_points) &&
      Array.isArray(item.evidence_refs),
  );
}

function isMarkdownTableStart(lines: string[], index: number): boolean {
  if (index + 1 >= lines.length || !isMarkdownTableRow(lines[index])) return false;
  const separator = parseMarkdownTableRow(lines[index + 1]);
  return separator.length >= 2 && separator.every((cell) => /^:?-{3,}:?$/.test(cell.trim()));
}

function isMarkdownTableRow(line: string): boolean {
  const trimmed = line.trim();
  return trimmed.startsWith("|") && trimmed.endsWith("|") && parseMarkdownTableRow(trimmed).length >= 2;
}

function parseMarkdownTableRow(line: string): string[] {
  const trimmed = line.trim().replace(/^\|/, "").replace(/\|$/, "");
  const cells: string[] = [];
  let current = "";
  let escaped = false;
  for (const character of trimmed) {
    if (escaped) {
      current += character;
      escaped = false;
    } else if (character === "\\") {
      escaped = true;
    } else if (character === "|") {
      cells.push(current.trim());
      current = "";
    } else {
      current += character;
    }
  }
  if (escaped) current += "\\";
  cells.push(current.trim());
  return cells;
}

function getIntentSufficiency(runDetail?: RunDetail): Array<{ intent: string; overall: string }> {
  const response = getObject(runDetail?.result?.response_payload);
  const metadata = getObject(response?.metadata);
  const observation = getObject(metadata?.intent_sufficiency);
  if (observation?.status !== "complete" || !Array.isArray(observation.results)) return [];
  return observation.results.flatMap((value) => {
    const item = getObject(value);
    return typeof item?.intent === "string" && typeof item?.overall === "string"
      ? [{ intent: item.intent, overall: item.overall }]
      : [];
  });
}
