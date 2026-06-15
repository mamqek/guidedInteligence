import { useEffect, useMemo, useState } from "react";
import { api, AppConfig, EvidenceItem, Health, McpSource, RunDetail, RunSummary, RunTrace } from "./api";
import { sourceLabels, sourceOrder } from "./constants";

type LoadState<T> = {
  data?: T;
  error?: string;
  loading: boolean;
};

const defaultState = <T,>(): LoadState<T> => ({ loading: true });

export function App() {
  const [health, setHealth] = useState<LoadState<Health>>(defaultState);
  const [config, setConfig] = useState<LoadState<AppConfig>>(defaultState);
  const [runs, setRuns] = useState<LoadState<RunSummary[]>>(defaultState);
  const [selectedRunId, setSelectedRunId] = useState<string>("");
  const [runDetail, setRunDetail] = useState<LoadState<RunDetail>>({ loading: false });
  const [trace, setTrace] = useState<LoadState<RunTrace>>({ loading: false });
  const [prompt, setPrompt] = useState("");
  const [allowedSources, setAllowedSources] = useState<string[]>(["source_code", "documentation"]);
  const [runError, setRunError] = useState("");
  const [runLoading, setRunLoading] = useState(false);

  useEffect(() => {
    refreshBase();
  }, []);

  useEffect(() => {
    if (!config.data) return;
    setPrompt((current) => current || config.data?.ui.default_prompt || "");
    setAllowedSources(config.data.enabled_source_categories.filter((source) => sourceOrder.includes(source)));
  }, [config.data]);

  useEffect(() => {
    if (!selectedRunId) return;
    loadRun(selectedRunId);
  }, [selectedRunId]);

  async function refreshBase() {
    setHealth(defaultState());
    setConfig(defaultState());
    setRuns(defaultState());
    await Promise.allSettled([
      api.health().then((data) => setHealth({ data, loading: false })).catch((error) => setHealth({ error: error.message, loading: false })),
      api.config().then((data) => setConfig({ data, loading: false })).catch((error) => setConfig({ error: error.message, loading: false })),
      api.runs().then((data) => {
        setRuns({ data: data.runs, loading: false });
        setSelectedRunId((current) => current || data.runs[0]?.run_id || "");
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
    try {
      const run = await api.retrieve({ prompt, allowed_sources: allowedSources });
      await refreshBase();
      setSelectedRunId(run.run_id);
    } catch (error) {
      setRunError(error instanceof Error ? error.message : String(error));
    } finally {
      setRunLoading(false);
    }
  }

  const currentEvidence = runDetail.data?.evidence || [];
  const currentTrace = trace.data ? [...trace.data.orchestration_trace, ...trace.data.retrieval_trace] : [];
  const sourceCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const item of currentEvidence) counts.set(item.source_category, (counts.get(item.source_category) || 0) + 1);
    return counts;
  }, [currentEvidence]);

  return (
    <div className="appShell">
      <aside className="sideNav">
        <div className="brandMark">GI</div>
        <nav>
          <a href="#run">Chat Run</a>
          <a href="#connections">Connections</a>
          <a href="#evidence">Evidence</a>
          <a href="#trace">Trace</a>
          <a href="#settings">Settings</a>
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

        <section className="workArea">
          <div className="leftColumn">
            <RunPanel
              prompt={prompt}
              setPrompt={setPrompt}
              allowedSources={allowedSources}
              setAllowedSources={setAllowedSources}
              runLoading={runLoading}
              runError={runError}
              onSubmit={submitRun}
            />
            <ConnectionsPanel config={config.data} refreshBase={refreshBase} />
            <SettingsPanel health={health.data} config={config} setConfig={setConfig} />
          </div>
          <div className="rightColumn">
            <RunSummaryPanel runs={runs} selectedRunId={selectedRunId} setSelectedRunId={setSelectedRunId} runDetail={runDetail} />
            <EvidencePanel evidence={currentEvidence} sourceCounts={sourceCounts} />
            <TracePanel trace={currentTrace} state={trace} />
          </div>
        </section>
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
    ["Qdrant", health.data?.qdrant_configured],
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
    </section>
  );
}

function RunPanel(props: {
  prompt: string;
  setPrompt: (value: string) => void;
  allowedSources: string[];
  setAllowedSources: (value: string[]) => void;
  runLoading: boolean;
  runError: string;
  onSubmit: () => void;
}) {
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
      <div className="sourceGrid">
        {sourceOrder.map((source) => (
          <label className="checkRow" key={source}>
            <input type="checkbox" checked={props.allowedSources.includes(source)} onChange={() => toggleSource(source)} />
            <span>{sourceLabels[source]}</span>
          </label>
        ))}
      </div>
      {props.runError && <p className="errorText">{props.runError}</p>}
      <button className="primaryButton" type="button" disabled={!props.prompt.trim() || props.runLoading} onClick={props.onSubmit}>
        {props.runLoading ? "Running..." : "Run retrieval"}
      </button>
    </section>
  );
}

function ConnectionsPanel({ config, refreshBase }: { config?: AppConfig; refreshBase: () => void }) {
  const builtIns = [
    ["Source Code", "Built in", "codegraphcontext + qdrant"],
    ["Documentation", "Built in", "workspace index"],
    ["Local Notes", "Optional", "obsidian-hybrid-search"],
  ];
  const mcpSources = config?.connections.mcp_sources || [];
  return (
    <section className="panel" id="connections">
      <div className="panelHeader">
        <h2>Connections</h2>
        <button className="textButton" type="button" onClick={refreshBase}>Reload</button>
      </div>
      <div className="connectionGrid">
        {builtIns.map(([name, status, detail]) => (
          <ConnectionTile key={name} name={name} status={status} detail={detail} />
        ))}
        {mcpSources.map((source) => (
          <ConnectionTile key={source.name} name={source.name} status={source.enabled === false ? "Disabled" : "MCP"} detail={`${source.source_category} / ${source.query_tool_name}`} />
        ))}
        <ConnectionTile name="Custom MCP" status="Add source" detail="Configure in .guided-intelligence/config.json" />
      </div>
    </section>
  );
}

function ConnectionTile({ name, status, detail }: { name: string; status: string; detail: string }) {
  return (
    <div className="connectionTile">
      <div>
        <h3>{name}</h3>
        <p>{detail}</p>
      </div>
      <span>{status}</span>
    </div>
  );
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
  const selected = runDetail.data;
  return (
    <section className="panel">
      <div className="panelHeader">
        <h2>Run History</h2>
        <span className="panelMeta">{runs.data?.length || 0} runs</span>
      </div>
      <div className="runList">
        {(runs.data || []).slice(0, 5).map((run) => (
          <button className={run.run_id === selectedRunId ? "runRow selected" : "runRow"} type="button" onClick={() => setSelectedRunId(run.run_id)} key={run.run_id}>
            <span>{run.run_id}</span>
            <strong>{run.coverage_status}</strong>
          </button>
        ))}
        {!runs.loading && !runs.data?.length && <p className="emptyText">No runs yet.</p>}
      </div>
      {selected && (
        <div className="summaryBar">
          <Metric label="Coverage" value={selected.coverage_status} />
          <Metric label="Sufficient" value={String(selected.sufficient)} />
          <Metric label="Evidence" value={String(selected.selected_count)} />
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
