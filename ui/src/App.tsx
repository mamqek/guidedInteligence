import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { api, AnswerEvaluation, AppConfig, EvidenceItem, Health, IndexEstimate, IndexPrepareJob, ProviderAuthState, RemoteMcpSource, RunDetail, RunSummary, RunTrace, UnderstandingCheck, WorkspaceEntry } from "./api";
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

  const currentEvidence = runDetail.data?.evidence || [];
  const currentTrace = trace.data ? [...trace.data.orchestration_trace, ...trace.data.retrieval_trace] : [];
  const currentChecks = getUnderstandingChecks(runDetail.data);
  const currentEvaluations = runDetail.data?.answer_evaluation?.evaluations || [];
  const questionsPending = currentChecks.length > 0 && currentEvaluations.length === 0;
  const sourceCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const item of currentEvidence) {
      const source = item.source_key || item.metadata?.source_key || item.source_category;
      counts.set(source, (counts.get(source) || 0) + 1);
    }
    return counts;
  }, [currentEvidence]);
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
              onSubmit={submitRun}
            />
            <RunSummaryPanel runs={runs} selectedRunId={selectedRunId} setSelectedRunId={setSelectedRunId} runDetail={runDetail} />
            <GuidedResponsePanel
              runDetail={runDetail.data}
              checks={currentChecks}
              evaluations={currentEvaluations}
              loading={answerLoading}
              error={answerError}
              onSubmit={submitAnswers}
            />
            <EvidencePanel evidence={currentEvidence} sourceCounts={sourceCounts} />
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
  const items = [
    ["Service", health.data?.status === "ok"],
    [".env", health.data?.env_exists],
    ["LLM", health.data?.llm_configured],
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
      {health.data?.qdrant_configured && !health.data?.qdrant_reachable && (
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
  onSubmit: () => void;
}) {
  const sourceOptions = runSourceOptions(props.config);
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
        <span className="panelMeta">real pipeline run</span>
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
      {props.indexEstimate?.enable_indexing && props.indexEstimate.file_count > 0 && (
        <div className={props.indexPrepareLoading ? "indexNotice running" : props.indexEstimate.index_ready ? "indexNotice ready" : "indexNotice"}>
          <div className="indexNoticeText">
            <strong>
              {props.indexPrepareLoading
                ? "Indexing is running."
                : props.indexEstimate.index_ready
                  ? "Index is ready."
                  : "Indexing may run before retrieval."}
            </strong>
            <span>
              Scope: {formatCount(props.indexEstimate.file_count)} files, about {formatCount(props.indexEstimate.estimated_chunks)} chunks.
              {props.indexEstimate.index_ready
                ? ` ${props.indexEstimate.index_status_detail || ""}`
                : ` Estimate: ${formatIndexEstimateDuration(props.indexEstimate)}.`}
              {props.indexEstimate.index_last_built_at ? ` Last prepared: ${formatDateTime(props.indexEstimate.index_last_built_at)}.` : ""}
              {props.indexEstimate.cgc_timeout_risk ? ` CGC estimate: ${formatCgcModeEstimate(props.indexEstimate)}.` : ""}
              {" "}
              {!props.indexEstimate.index_ready && (
                <>
                  If that is too long, open Workspace and add folders to "Do not index these directories/files", then refresh the estimate.
                  {" "}
                </>
              )}
              <button className="inlineLinkButton" type="button" onClick={props.onConfigureIndexing}>
                Edit exclusions in Workspace
              </button>
            </span>
          </div>
          <button className="textButton indexButton" type="button" disabled={props.indexPrepareLoading} onClick={props.onPrepareIndex}>
            {props.indexPrepareLoading ? "Preparing..." : props.indexEstimate.index_ready ? "Refresh index" : "Prepare index"}
          </button>
        </div>
      )}
      {props.indexPrepareMessage && <p className="noticeText">{props.indexPrepareMessage}</p>}
      {props.runError && <p className="errorText">{props.runError}</p>}
      <button className="primaryButton" type="button" disabled={!props.prompt.trim() || props.runLoading || props.blocked || props.indexPrepareLoading} onClick={props.onSubmit}>
        {props.runLoading ? "Running..." : "Run retrieval"}
      </button>
    </section>
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
    ["Source Code", "Built in", "codegraphcontext + qdrant"],
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
    <section className="panel" id="connections">
      <div className="panelHeader">
        <h2>Connections</h2>
        <button className="textButton" type="button" onClick={refreshBase}>Reload</button>
      </div>
      <div className="connectionGrid">
        {builtIns.map(([name, status, detail]) => (
          <ConnectionTile key={name} name={name} status={status} detail={detail} onInfo={() => setHelp(builtInConnectionHelp(name))} />
        ))}
      </div>
      {remoteMcpSources.length > 0 && (
        <div className="remoteMcpSection">
          <div className="sectionHeader">
            <h3>Hosted MCP connectors</h3>
            <p>Remote MCP uses provider-hosted endpoints. It never falls back to local command MCP.</p>
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
                    <label className="fieldLabel">
                      Scope
                      <input
                        value={githubRemoteScope}
                        placeholder="owner/repo or org"
                        onChange={(event) => updateRemoteMcpSources(githubRemoteEntries.map((entry) => entry.index), { scope: event.target.value })}
                      />
                    </label>
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
                      {source.features && Object.keys(source.features).length > 0 && (
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
      <div className="connectionActions">
        <button className="primaryButton compactButton" type="button" disabled={!config.data || saving} onClick={saveConnections}>
          {saving ? "Saving..." : "Save connections"}
        </button>
      </div>
      {saveError && <p className="errorText">{saveError}</p>}
      {help && <InfoDialog help={help} onClose={() => setHelp(null)} />}
    </section>
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
    { name: "Feature toggles", description: "Choose which provider object types can be searched or fetched." },
    { name: "Fetch full content for top search hits", description: "For supported providers, fetches richer content for the highest-ranked search results." },
    { name: "Full-content fetch limit", description: "Caps how many top hits are enriched with full content." },
    { name: "MCP query/fetch tool and endpoint", description: "Advanced provider MCP details. These are normally predefined and should only be changed when the provider changes its tool names or endpoint." },
  ];
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

function supportsFullContentFetch(source: RemoteMcpSource): boolean {
  return ["notion", "atlassian", "shortcut", "linear", "slack", "google_drive"].includes(source.provider);
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
  refreshBase,
  onOpenWorkspace,
}: {
  health?: Health;
  config: LoadState<AppConfig>;
  workspaces: LoadState<WorkspaceEntry[]>;
  setConfig: (state: LoadState<AppConfig>) => void;
  estimate: LoadState<IndexEstimate>;
  refreshBase: () => void;
  onOpenWorkspace: (workspaceRoot: string) => void | Promise<void>;
}) {
  const [workspaceRoot, setWorkspaceRoot] = useState("");
  const [saving, setSaving] = useState(false);
  const [browsing, setBrowsing] = useState(false);
  const [openingWorkspace, setOpeningWorkspace] = useState(false);
  const [browseError, setBrowseError] = useState("");
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
  const selectedWorkspaceValue = workspaces.data?.some((workspace) => workspace.workspace_root === workspaceRoot) ? workspaceRoot : "";

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
          <h2>Workspace Directory</h2>
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
            <input value={workspaceRoot} disabled={openingWorkspace} onChange={(event) => setWorkspaceRoot(event.target.value)} />
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
          <h2>Retrieval Settings</h2>
          <button className="textButton" type="button" onClick={refreshBase}>Refresh estimate</button>
        </div>
        {retrieval && (
          <>
            <label className="fieldLabel">
              Retrieval mode
              <select value={retrieval.mode || "workspace"} onChange={(event) => updateRetrieval({ mode: event.target.value as AppConfig["retrieval"]["mode"] })}>
                <option value="workspace">Workspace index</option>
                <option value="codex">Codex evidence provider</option>
              </select>
            </label>
            {retrieval.mode === "codex" && (
              <div className="indexSummary">
                <Metric label="Codex model" value={retrieval.codex_model || "gpt-5.4-nano"} />
                <Metric label="Timeout" value={`${retrieval.codex_timeout_seconds || 900}s`} />
              </div>
            )}
          </>
        )}
        {indexing && (
          <>
            <label className="checkRow">
              <input
                type="checkbox"
                checked={indexing.enable_indexing}
                disabled={retrieval?.mode === "codex"}
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
        {estimate.data && (
          <div className="indexSummary">
            <Metric label="Files" value={formatCount(estimate.data.file_count)} />
            <Metric label="Chunks est." value={formatCount(estimate.data.estimated_chunks)} />
            <Metric label="Size" value={`${(estimate.data.total_bytes / 1024 / 1024).toFixed(1)} MB`} />
            <Metric label="CGC full" value={formatCgcFullEstimateDuration(estimate.data)} />
            <Metric label="CGC skip ext." value={formatCgcSkipEstimateDuration(estimate.data)} />
          </div>
        )}
        {estimate.data?.index_estimate_notes?.map((note) => (
          <p className="noticeText" key={note}>{note}</p>
        ))}
        <button className="primaryButton" type="button" disabled={!config.data || saving} onClick={saveIndexing}>
          {saving ? "Saving..." : "Save retrieval settings"}
        </button>
        {estimate.error && <p className="errorText">{estimate.error}</p>}
        {config.error && <p className="errorText">{config.error}</p>}
      </section>
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
    <section className="panel">
      <div className="panelHeader">
        <h2>Run History</h2>
        <span className="panelMeta">{runs.data?.length || 0} runs</span>
      </div>
      <div className="runList">
        {(runs.data || []).slice(0, 5).map((run) => {
          const timestamp = formatRunTimestamp(run.run_id);
          return (
            <button className={run.run_id === selectedRunId ? "runRow selected" : "runRow"} type="button" onClick={() => setSelectedRunId(run.run_id)} key={run.run_id}>
              <span className="runIdentity">
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

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
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

function formatCgcModeEstimate(estimate: IndexEstimate): string {
  return `full ${formatCgcFullEstimateDuration(estimate)}, skip external ${formatCgcSkipEstimateDuration(estimate)}`;
}

function formatCgcFullEstimateDuration(estimate: IndexEstimate): string {
  if (
    typeof estimate.cgc_full_estimated_seconds_min === "number" &&
    Number.isFinite(estimate.cgc_full_estimated_seconds_min) &&
    typeof estimate.cgc_full_estimated_seconds_max === "number" &&
    Number.isFinite(estimate.cgc_full_estimated_seconds_max)
  ) {
    return formatDurationRange(estimate.cgc_full_estimated_seconds_min, estimate.cgc_full_estimated_seconds_max);
  }
  return formatCgcSkipEstimateDuration(estimate);
}

function formatCgcSkipEstimateDuration(estimate: IndexEstimate): string {
  if (
    typeof estimate.cgc_skip_external_estimated_seconds_min === "number" &&
    Number.isFinite(estimate.cgc_skip_external_estimated_seconds_min) &&
    typeof estimate.cgc_skip_external_estimated_seconds_max === "number" &&
    Number.isFinite(estimate.cgc_skip_external_estimated_seconds_max)
  ) {
    return formatDurationRange(estimate.cgc_skip_external_estimated_seconds_min, estimate.cgc_skip_external_estimated_seconds_max);
  }
  if (
    typeof estimate.cgc_estimated_seconds_min === "number" &&
    Number.isFinite(estimate.cgc_estimated_seconds_min) &&
    typeof estimate.cgc_estimated_seconds_max === "number" &&
    Number.isFinite(estimate.cgc_estimated_seconds_max)
  ) {
    return formatDurationRange(estimate.cgc_estimated_seconds_min, estimate.cgc_estimated_seconds_max);
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
  const canSubmit = checks.length > 0 && checks.every((check) => (answers[check.id] || "").trim()) && !loading && evaluations.length === 0;
  return (
    <section className="panel" id="guided-response">
      <div className="panelHeader">
        <h2>Guided Explanation</h2>
        <span className="panelMeta">{checks.length ? `${checks.length} checks` : "no checks"}</span>
      </div>
      {content ? <div className="responseText">{renderMarkdown(content)}</div> : <p className="emptyText">Run retrieval to generate an explanation.</p>}
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
                <div className="questionMeta">
                  <span>{check.question_type}</span>
                  <strong>{check.role}</strong>
                  <small>{check.origin}</small>
                </div>
                <p>{check.question}</p>
                <textarea
                  rows={4}
                  value={answers[check.id] || ""}
                  disabled={evaluations.length > 0}
                  onChange={(event) => setAnswers({ ...answers, [check.id]: event.target.value })}
                  placeholder="Write your answer..."
                />
                <details className="hintBox">
                  <summary>Show hint</summary>
                  <p>{check.hint}</p>
                </details>
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

function EvidencePanel({ evidence, sourceCounts }: { evidence: EvidenceItem[]; sourceCounts: Map<string, number> }) {
  return (
    <section className="panel" id="evidence">
      <div className="panelHeader">
        <h2>Evidence</h2>
        <span className="panelMeta">{evidence.length} selected</span>
      </div>
      <div className="sourcePills">
        {[...sourceCounts.entries()].map(([source, count]) => (
          <span key={source}>{sourceLabels[source] || source}: {count}</span>
        ))}
      </div>
      <div className="evidenceList">
        {evidence.map((item) => (
          <article className="evidenceCard" key={item.source_id}>
            <div className="evidenceMeta">
              <span>{item.metadata?.coverage_area || item.source_category}</span>
              <strong>{item.source_id}</strong>
            </div>
            <pre>{item.snippet}</pre>
          </article>
        ))}
        {!evidence.length && <p className="emptyText">Run retrieval to inspect selected code and connected-source evidence.</p>}
      </div>
    </section>
  );
}

function TracePanel({ trace, state }: { trace: Array<Record<string, unknown>>; state: LoadState<RunTrace> }) {
  return (
    <section className="panel" id="trace">
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

function renderMarkdown(markdown: string): ReactNode[] {
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
      const codeLines: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].trim().startsWith("```")) {
        codeLines.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) index += 1;
      nodes.push(<pre className="markdownCode" key={`code-${index}`}>{codeLines.join("\n")}</pre>);
      continue;
    }
    const heading = /^(#{1,4})\s+(.+)$/.exec(trimmed);
    if (heading) {
      const level = heading[1].length;
      const text = renderInlineMarkdown(heading[2]);
      if (level === 1) nodes.push(<h1 key={`h-${index}`}>{text}</h1>);
      else if (level === 2) nodes.push(<h2 key={`h-${index}`}>{text}</h2>);
      else nodes.push(<h3 key={`h-${index}`}>{text}</h3>);
      index += 1;
      continue;
    }
    if (/^[-*]\s+/.test(trimmed)) {
      const items: ReactNode[] = [];
      while (index < lines.length && /^[-*]\s+/.test(lines[index].trim())) {
        items.push(<li key={`li-${index}`}>{renderInlineMarkdown(lines[index].trim().replace(/^[-*]\s+/, ""))}</li>);
        index += 1;
      }
      nodes.push(<ul key={`ul-${index}`}>{items}</ul>);
      continue;
    }
    if (/^\d+[.)]\s+/.test(trimmed)) {
      const items: ReactNode[] = [];
      while (index < lines.length && /^\d+[.)]\s+/.test(lines[index].trim())) {
        items.push(<li key={`oli-${index}`}>{renderInlineMarkdown(lines[index].trim().replace(/^\d+[.)]\s+/, ""))}</li>);
        index += 1;
      }
      nodes.push(<ol key={`ol-${index}`}>{items}</ol>);
      continue;
    }
    const paragraph: string[] = [trimmed];
    index += 1;
    while (
      index < lines.length &&
      lines[index].trim() &&
      !lines[index].trim().startsWith("```") &&
      !/^(#{1,4})\s+/.test(lines[index].trim()) &&
      !/^[-*]\s+/.test(lines[index].trim()) &&
      !/^\d+[.)]\s+/.test(lines[index].trim())
    ) {
      paragraph.push(lines[index].trim());
      index += 1;
    }
    nodes.push(<p key={`p-${index}`}>{renderInlineMarkdown(paragraph.join(" "))}</p>);
  }
  return nodes;
}

function renderInlineMarkdown(text: string): ReactNode[] {
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g).filter(Boolean);
  return parts.map((part, index) => {
    if (part.startsWith("`") && part.endsWith("`")) {
      return <code key={index}>{part.slice(1, -1)}</code>;
    }
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    return part;
  });
}

function getResponseContent(runDetail?: RunDetail): string {
  const response = getObject(runDetail?.result?.response_payload);
  return String(response?.content || "");
}

function getUnderstandingChecks(runDetail?: RunDetail): UnderstandingCheck[] {
  const response = getObject(runDetail?.result?.response_payload);
  const metadata = getObject(response?.metadata);
  const raw = metadata?.understanding_checks;
  if (!Array.isArray(raw)) return [];
  return raw.filter(isUnderstandingCheck);
}

function getObject(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : undefined;
}

function isUnderstandingCheck(value: unknown): value is UnderstandingCheck {
  const item = getObject(value);
  return Boolean(
    item &&
      typeof item.id === "string" &&
      typeof item.role === "string" &&
      typeof item.question_type === "string" &&
      typeof item.question === "string" &&
      typeof item.hint === "string" &&
      Array.isArray(item.expected_answer_points) &&
      Array.isArray(item.evidence_refs) &&
      typeof item.origin === "string",
  );
}
