import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api.js'
import ModelLeaderboard from '../components/ModelLeaderboard.jsx'

const ALL_MODES = ['no_context', 'code_only', 'code_history', 'oracle']
const pct = (v) => (v == null ? '-' : `${Math.round(v * 100)}%`)
const num = (v) => (v == null ? '-' : v)

function heat(v) {
  if (v == null) return {}
  const hue = Math.round(v * 120)   // red -> green
  return { background: `hsl(${hue} 70% 45% / 0.18)` }
}

function Verdicts({ decisions }) {
  if (!decisions?.length) return <p className="muted text-sm">Run both Code only and Code + history to apply the decision rule.</p>
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {decisions.map((d) => (
        <div key={d.model} className="panel rise">
          <div className="text-xs muted">{d.model}</div>
          <div className={`text-lg font-semibold ${d.history_helps && !d.control_harmed ? 'text-emerald-600' : d.verdict === 'inconclusive' ? 'text-amber-600' : 'text-rose-600'}`}>
            {d.verdict}
          </div>
          <div className="text-sm muted">history vs code-only on history questions: {d.history_diff >= 0 ? '+' : ''}{d.history_diff} (95% CI {d.history_ci[0]} to {d.history_ci[1]})</div>
        </div>
      ))}
    </div>
  )
}

function CategoryTable({ rep, model }) {
  return (
    <div className="panel overflow-x-auto p-0">
      <div className="px-4 pt-3 font-semibold">{model}: correctness by category</div>
      <table className="w-full">
        <thead><tr><th className="th">Category</th>{rep.modes.map((m) => <th key={m} className="th">{m}</th>)}</tr></thead>
        <tbody>
          {rep.categories.map((c) => (
            <tr key={c} className="border-t" style={{ borderColor: 'var(--line)' }}>
              <td className="td font-mono text-xs">{c}</td>
              {rep.modes.map((m) => {
                const cell = rep.cells[`${model}|${m}|${c}`]
                return (
                  <td key={m} className="td" style={heat(cell?.correctness)}>
                    {cell ? <>{pct(cell.correctness)} <span className="text-xs muted">n={cell.n}</span></> : '-'}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Totals({ rep }) {
  return (
    <div className="panel overflow-x-auto p-0">
      <div className="px-4 pt-3 font-semibold">Retrieval, citations, hallucination and cost (pooled)</div>
      <table className="w-full">
        <thead>
          <tr>{['Model', 'Mode', 'Evidence recall', 'Evidence precision', 'Citation validity', 'Unsupported claims', 'Refusal correct', 'Latency ms', 'Tokens in/out'].map((h) => <th key={h} className="th">{h}</th>)}</tr>
        </thead>
        <tbody>
          {rep.models.flatMap((m) => rep.modes.map((mo) => {
            const t = rep.totals[`${m}|${mo}`]
            if (!t) return null
            return (
              <tr key={`${m}${mo}`} className="border-t" style={{ borderColor: 'var(--line)' }}>
                <td className="td">{m}</td><td className="td font-mono text-xs">{mo}</td>
                <td className="td">{pct(t.evidence_recall)}</td><td className="td">{pct(t.evidence_precision)}</td>
                <td className="td">{pct(t.citation_validity)}</td><td className="td">{pct(t.unsupported_ratio)}</td>
                <td className="td">{pct(t.refusal_correct)}</td><td className="td">{num(t.latency_ms)}</td>
                <td className="td">{num(t.tokens_in)}/{num(t.tokens_out)}</td>
              </tr>
            )
          }))}
        </tbody>
      </table>
    </div>
  )
}

export default function Evaluation() {
  const [datasets, setDatasets] = useState([])
  const [models, setModels] = useState([])
  const [dataset, setDataset] = useState('demo')
  const [picked, setPicked] = useState(['llama2'])
  const [modes, setModes] = useState(['no_context', 'code_only', 'code_history'])
  const [split, setSplit] = useState('all')
  const [jury, setJury] = useState('gemma:2b')
  const [useJury, setUseJury] = useState(false)
  const [runId, setRunId] = useState(null)
  const [run, setRun] = useState(null)
  const [markdown, setMarkdown] = useState('')
  const [error, setError] = useState('')
  const [history, setHistory] = useState([])
  const [showFailed, setShowFailed] = useState(false)
  const timer = useRef(null)

  useEffect(() => {
    api.evalDatasets().then((d) => { setDatasets(d.datasets); if (d.datasets[0]) setDataset((c) => (d.datasets.some((x) => x.name === c) ? c : d.datasets[0].name)) }).catch((e) => setError(e.message))
    api.config().then((c) => { setModels(c.models || []); if (c.models?.length) setPicked((p) => (p.every((m) => c.models.includes(m)) ? p : [c.models[0]])) }).catch(() => {})
  }, [])

  const poll = useCallback(async (id) => {
    try {
      const body = await api.evalRun(id)
      setRun(body)
      if (body.run.status === 'running') timer.current = setTimeout(() => poll(id), 1500)
    } catch (e) { setError(e.message) }
  }, [])
  useEffect(() => () => clearTimeout(timer.current), [])

  const loadHistory = useCallback(() => api.evalRuns().then((d) => setHistory(d.runs || [])).catch(() => {}), [])
  useEffect(() => { loadHistory() }, [loadHistory, run?.run.status])

  // open the newest finished run once, so the scores are visible without clicking anything
  const autoOpened = useRef(false)
  useEffect(() => {
    if (autoOpened.current || runId || !history.length) return
    const latest = history.find((h) => h.status === 'done')
    if (latest) { autoOpened.current = true; open(latest.id) }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [history])

  const open = (id) => { clearTimeout(timer.current); setError(''); setMarkdown(''); setRun(null); setRunId(id); poll(id) }

  const toggle = (list, setList, v) => setList(list.includes(v) ? list.filter((x) => x !== v) : [...list, v])

  const start = async () => {
    setError(''); setRun(null); setMarkdown('')
    try {
      const r = await api.evalStart({ dataset, models: picked, modes, split, ...(useJury ? { jury_model: jury } : {}) })
      setRunId(r.run_id)
      poll(r.run_id)
    } catch (e) { setError(e.message) }
  }

  const rep = run?.report
  const running = run?.run.status === 'running'
  const choices = models.length ? models : ['llama2', 'codellama:7b', 'starcoder2:3b']

  return (
    <div className="space-y-5">
      <div className="panel space-y-3">
        <h2 className="font-semibold">Run an evaluation</h2>
        <p className="text-sm muted">
          The same questions are asked in each mode and scored per category with 95% confidence intervals. There is no single blended score.
          Oracle mode gives the model the gold evidence to separate retrieval failures from model failures.
        </p>
        <div className="grid gap-4 md:grid-cols-4">
          <label className="text-sm">Dataset
            <select className="input mt-1" value={dataset} onChange={(e) => setDataset(e.target.value)}>
              {datasets.map((d) => <option key={d.file} value={d.name}>{d.name} ({d.items} items)</option>)}
            </select>
          </label>
          <label className="text-sm">Split
            <select className="input mt-1" value={split} onChange={(e) => setSplit(e.target.value)}>
              <option value="all">all</option><option value="dev">dev (tuning)</option><option value="test">test (held-out)</option>
            </select>
          </label>
          <fieldset className="text-sm"><legend>Models</legend>
            {choices.map((m) => <label key={m} className="mr-3 inline-flex items-center gap-1"><input type="checkbox" checked={picked.includes(m)} onChange={() => toggle(picked, setPicked, m)} />{m}</label>)}
          </fieldset>
          <fieldset className="text-sm"><legend>Modes</legend>
            {ALL_MODES.map((m) => <label key={m} className="mr-3 inline-flex items-center gap-1"><input type="checkbox" checked={modes.includes(m)} onChange={() => toggle(modes, setModes, m)} />{m}</label>)}
          </fieldset>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="inline-flex items-center gap-2 text-sm"><input type="checkbox" checked={useJury} onChange={(e) => setUseJury(e.target.checked)} />LLM jury</label>
          <input className="input w-48" value={jury} onChange={(e) => setJury(e.target.value)} disabled={!useJury} aria-label="Jury model" />
          <button className="btn-primary" onClick={start} disabled={running || !picked.length || !modes.length}>{running ? 'Running...' : 'Start run'}</button>
          {runId && <span className="text-sm muted">run #{runId}</span>}
        </div>
        {error && <p role="alert" className="text-sm text-rose-600">{error}</p>}
        {history.length > 0 && (
          <div className="space-y-1">
            <h3 className="text-sm font-semibold">Previous runs</h3>
            <ul className="divide-y divide-black/5 text-sm">
              {history.filter((h) => showFailed || h.status !== 'failed').map((h) => (
                <li key={h.id} className="flex flex-wrap items-center gap-3 py-1.5">
                  <span className="muted">#{h.id}</span>
                  <span className="font-medium">{h.name || h.dataset_name}</span>
                  <span className="muted">{(h.config?.models || []).join(', ')} · {h.config?.split || 'all'} · {h.done}/{h.total}</span>
                  {['all', 'test'].includes(h.config?.split || 'all') && <span className="chip" title="This run included the held-out test questions">touches held-out split</span>}
                  <span className={h.status === 'done' ? 'text-emerald-600' : h.status === 'failed' ? 'text-rose-600' : 'text-amber-600'}>{h.status}</span>
                  <button className="btn-ghost ml-auto" onClick={() => open(h.id)} disabled={runId === h.id && !!run}>Open</button>
                </li>
              ))}
            </ul>
            {history.some((h) => h.status === 'failed') && (
              <button className="text-xs underline muted" onClick={() => setShowFailed((v) => !v)}>
                {showFailed ? 'Hide' : 'Show'} {history.filter((h) => h.status === 'failed').length} interrupted/failed runs
              </button>
            )}
          </div>
        )}
        {run && (
          <div>
            <div className="h-2 overflow-hidden rounded bg-black/10">
              <div className={`h-full bg-[var(--accent)] transition-all duration-500 ${running ? 'progress-live' : ''}`} style={{ width: `${run.run.total ? (100 * run.run.done) / run.run.total : 0}%` }} />
            </div>
            <p className="mt-1 text-xs muted">{run.run.done}/{run.run.total} answers - {run.run.status}{run.run.error ? `: ${run.run.error}` : ''}</p>
          </div>
        )}
      </div>

      {rep && rep.n_results > 0 && (
        <>
          <ModelLeaderboard key={runId} rep={rep} />
          <section className="space-y-3"><h2 className="font-semibold">Verdict (pre-registered rule)</h2><Verdicts decisions={rep.decisions} /></section>
          {rep.models.map((m) => <CategoryTable key={m} rep={rep} model={m} />)}
          <Totals rep={rep} />
          <div className="panel">
            <h3 className="mb-2 font-semibold">Why answers were wrong</h3>
            <div className="flex flex-wrap gap-2">
              {Object.entries(rep.failures).map(([k, v]) => (
                <div key={k} className="rounded-lg border p-2 text-xs" style={{ borderColor: 'var(--line)' }}>
                  <div className="font-mono">{k.replace('|', ' / ')}</div>
                  {Object.entries(v).map(([f, n]) => <div key={f}>{f}: {n}</div>)}
                </div>
              ))}
            </div>
          </div>
          {rep.n_errors > 0 && <p className="text-sm text-amber-600">{rep.n_errors} answers failed to run (see report).</p>}
          <div className="panel">
            <button className="btn-ghost" onClick={() => api.evalReport(runId).then(setMarkdown).catch((e) => setError(e.message))}>Show markdown report</button>
            {markdown && <pre className="mt-3 max-h-[480px] overflow-auto whitespace-pre-wrap rounded-lg bg-black/5 p-3 text-xs">{markdown}</pre>}
          </div>
        </>
      )}
    </div>
  )
}
