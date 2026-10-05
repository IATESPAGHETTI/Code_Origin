import { useEffect, useReducer } from 'react'
import { api, TYPE_COLOR } from '../api.js'
import { AnimatedNumber } from './motion.jsx'

const STEPS = [
  { id: 'clone', label: 'Clone', hint: 'git clone / fetch' },
  { id: 'github', label: 'GitHub', hint: 'issues, PRs, releases' },
  { id: 'links', label: 'Link graph', hint: 'issue - PR - commit' },
  { id: 'commits', label: 'Commits', hint: 'messages and diffs' },
  { id: 'code', label: 'Source', hint: 'functions and docs' },
  { id: 'index', label: 'Index', hint: 'embed and store' },
]
const ORDER = ['clone', 'github', 'links', 'commits', 'code', 'issues', 'index']
const BIN_ORDER = ['commit', 'diff', 'issue', 'pr', 'review', 'release', 'code', 'doc']

const init = { stage: null, status: 'running', message: '', progress: 0, github: null, links: null, commits: [], commitProg: null,
  files: [], fileProg: null, counts: {}, redactions: 0, samples: [], reached: {} }

function reduce(s, ev) {
  if (ev.type === 'end') return { ...s, status: ev.status, progress: ev.status === 'done' ? 100 : s.progress }
  const next = { ...s, message: ev.message || s.message, progress: ev.progress ?? s.progress }
  if (ev.stage && ev.stage !== 'index') { next.stage = ev.stage; next.reached = { ...s.reached, [ev.stage]: true } }
  const d = ev.data
  if (!d) return next
  if (d.kind === 'github') next.github = d
  if (d.kind === 'links') next.links = d
  if (d.kind === 'commit') { next.commits = [...s.commits, d].slice(-7); next.commitProg = { i: d.index, n: d.total } }
  if (d.kind === 'file') { next.files = [...s.files, d].slice(-5); next.fileProg = { i: d.index, n: d.total } }
  if (d.kind === 'chunks') {
    next.counts = d.counts; next.redactions = d.redactions
    next.samples = [...s.samples, ...d.samples.map((x, i) => ({ ...x, k: `${ev.id}-${i}` }))].slice(-6)
    next.reached = { ...next.reached, index: true }
  }
  return next
}

function Step({ step, state, i }) {
  return (
    <li className="flex items-center gap-3">
      <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold transition-all duration-300 ${state === 'active' ? 'flash' : ''}`}
        style={{ background: state === 'done' ? '#1a9d4b' : state === 'active' ? 'var(--accent)' : 'rgba(0,0,0,.07)', color: state === 'pending' ? 'var(--muted)' : '#fff' }}>
        {state === 'done' ? '✓' : state === 'active' ? <span className="spinner !h-3 !w-3 !border-white/40 !border-t-white" /> : i + 1}
      </span>
      <div className={state === 'pending' ? 'opacity-45' : ''}>
        <div className="text-sm font-medium">{step.label}</div>
        <div className="text-xs muted">{step.hint}</div>
      </div>
    </li>
  )
}

/** Live view of an ingest job: every number and row here is a real event from the ingest service. */
export default function IngestView({ jobId, onDone }) {
  const [s, dispatch] = useReducer(reduce, init)

  useEffect(() => {
    const ctl = new AbortController()
    api.jobStream(jobId, (name, data) => {
      if (name === 'end') { dispatch({ type: 'end', status: data.status }); onDone?.(); return }
      dispatch(data)
    }, ctl.signal).catch(() => {})
    return () => ctl.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId])

  const done = s.status === 'done'
  const failed = s.status === 'failed'
  const cur = ORDER.indexOf(s.stage === 'issues' ? 'code' : s.stage)
  const stateOf = (id) => {
    if (done) return 'done'
    const idx = ORDER.indexOf(id)
    if (id === 'index') return s.reached.index ? 'active' : 'pending'
    return idx < cur ? 'done' : idx === cur ? 'active' : 'pending'
  }
  const total = Object.values(s.counts).reduce((a, b) => a + b, 0)
  const maxBin = Math.max(1, ...Object.values(s.counts))

  return (
    <section className="panel rise space-y-5 !p-6" aria-label="Live ingestion">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-base font-semibold">{done ? 'Indexed' : failed ? 'Ingestion failed' : 'Indexing live'}</h2>
          <p className="text-xs muted">{s.message || 'starting...'}</p>
        </div>
        <div className="text-right">
          <div className="text-3xl font-semibold tabular-nums"><AnimatedNumber value={total} /></div>
          <div className="text-xs muted">chunks indexed</div>
        </div>
      </header>

      <div className="h-1.5 overflow-hidden rounded-full bg-black/[.07]">
        <div className={`h-full rounded-full transition-all duration-500 ${!done && !failed ? 'progress-live' : ''}`}
          style={{ width: `${s.progress}%`, background: failed ? '#d92d4a' : done ? '#1a9d4b' : 'var(--accent)' }} />
      </div>

      <div className="grid gap-6 lg:grid-cols-[190px_1.3fr_1fr]">
        <ol className="space-y-4">{STEPS.map((st, i) => <Step key={st.id} step={st} state={stateOf(st.id)} i={i} />)}</ol>

        <div className="min-w-0 space-y-2">
          <div className="flex items-center justify-between text-xs muted">
            <span>Commits {s.commitProg ? `${s.commitProg.i} / ${s.commitProg.n}` : ''}</span>
            {s.links && <span>{s.links.edges} cross-links</span>}
          </div>
          {s.github && <p className="text-xs muted">{s.github.issues} issues, {s.github.prs} pull requests, {s.github.releases} releases from GitHub</p>}
          <ul className="space-y-1.5">
            {s.commits.length === 0 && <li className="skeleton scanline h-10" />}
            {s.commits.map((c) => (
              <li key={c.sha} className="slide-in flex items-center gap-2 rounded-xl bg-black/[.035] px-3 py-2 text-sm">
                <span className="chip shrink-0" style={{ color: TYPE_COLOR.commit }}>{c.sha}</span>
                <span className="min-w-0 flex-1 truncate">{c.subject}</span>
                {c.links?.length > 0 && <span className="hidden shrink-0 gap-1 sm:flex">{c.links.slice(0, 2).map((l) => <span key={l} className="chip" style={{ color: TYPE_COLOR[l.split(':')[0]] }}>{l}</span>)}</span>}
                <span className="shrink-0 text-xs muted">{c.files} files</span>
              </li>
            ))}
          </ul>
          {s.files.length > 0 && (
            <div className="pt-2">
              <div className="text-xs muted">Source {s.fileProg ? `${s.fileProg.i} / ${s.fileProg.n}` : ''}</div>
              <ul className="mt-1 space-y-1">
                {s.files.map((f) => (
                  <li key={f.path} className="slide-in flex items-center gap-2 font-mono text-xs">
                    <span style={{ color: TYPE_COLOR[f.type] }}>{f.type}</span><span className="truncate">{f.path}</span><span className="ml-auto muted">{f.chunks} chunks</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className="min-w-0 space-y-3">
          <div className="text-xs muted">Chunks by source</div>
          {BIN_ORDER.filter((t) => s.counts[t]).map((t) => (
            <div key={t}>
              <div className="flex justify-between text-xs"><span className="font-mono" style={{ color: TYPE_COLOR[t] }}>{t}</span><span className="tabular-nums"><AnimatedNumber value={s.counts[t]} /></span></div>
              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-black/[.07]">
                <div className="h-full rounded-full transition-all duration-500" style={{ width: `${(100 * s.counts[t]) / maxBin}%`, background: TYPE_COLOR[t] }} />
              </div>
            </div>
          ))}
          {total === 0 && <div className="skeleton scanline h-16" />}
          {s.redactions > 0 && <p className="text-xs font-medium text-amber-700">{s.redactions} secret(s) redacted before indexing</p>}
          {s.samples.length > 0 && (
            <ul className="space-y-1.5 pt-1">
              {s.samples.map((x) => (
                <li key={x.k} className="drop-in rounded-lg border px-2.5 py-1.5 text-xs" style={{ borderColor: 'var(--line)' }}>
                  <span className="font-mono font-semibold" style={{ color: TYPE_COLOR[x.type] }}>{x.ref}</span>
                  <div className="truncate muted">{x.preview}</div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  )
}
