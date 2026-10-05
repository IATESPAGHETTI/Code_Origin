import RefBadge, { RefLine } from './RefBadge.jsx'

/** Which stages exist for each mode, in pipeline order. */
const STAGES = [
  { id: 'safety', label: 'Safety check', tag: 'G10', modes: ['no_context', 'code_only', 'code_history', 'oracle'] },
  { id: 'retrieve', label: 'Hybrid retrieval', tag: 'vector + BM25', modes: ['code_only', 'code_history', 'oracle'] },
  { id: 'gate_topic', label: 'On-topic gate', tag: 'G1', modes: ['code_only', 'code_history'] },
  { id: 'gate_history', label: 'History evidence gate', tag: 'G2', modes: ['code_history'] },
  { id: 'expand', label: 'Follow cross-links', tag: 'issue - PR - commit', modes: ['code_history'] },
  { id: 'context', label: 'Build context', tag: 'G5 injection filter', modes: ['code_only', 'code_history', 'oracle'] },
  { id: 'generate', label: 'Generate', tag: 'LLM', modes: ['no_context', 'code_only', 'code_history', 'oracle'] },
  { id: 'citations', label: 'Verify citations', tag: 'G3', modes: ['no_context', 'code_only', 'code_history', 'oracle'] },
  { id: 'grounding', label: 'Check grounding', tag: 'G4', modes: ['code_only', 'code_history', 'oracle'] },
  { id: 'redaction', label: 'Redact secrets', tag: 'G6', modes: ['no_context', 'code_only', 'code_history', 'oracle'] },
]

export function derive(events) {
  const st = {}
  let mode = null
  let blockedAt = null
  for (const e of events) {
    if (e.stage === 'start') { mode = e.detail.mode; continue }
    if (e.stage === 'refused') continue
    const prev = st[e.stage] || {}
    st[e.stage] = { status: e.status, detail: { ...prev.detail, ...e.detail }, t: e.t_ms }
    if (e.status === 'blocked' && !blockedAt) blockedAt = e.stage
  }
  return { st, mode, blockedAt }
}

function Icon({ status }) {
  if (status === 'running') return <span className="spinner" aria-label="running" />
  const map = {
    done: ['#10b981', '✓'], blocked: ['#f43f5e', '✕'], skipped: ['var(--muted)', '–'], pending: ['var(--line)', ''],
  }
  const [bg, glyph] = map[status] || map.pending
  return (
    <span className={`flex h-[18px] w-[18px] items-center justify-center rounded-full text-xs font-bold text-white ${status === 'done' || status === 'blocked' ? 'pop' : ''}`}
      style={{ background: bg, opacity: status === 'skipped' ? 0.5 : 1 }}>{glyph}</span>
  )
}

const Mini = ({ children, className = '' }) => <span className={`chip ${className}`}>{children}</span>
const typeChip = (t) => <span className="chip" style={{ color: TYPE_COLOR[t] }}>{t}</span>

function Bar({ value, color, delay = 0 }) {
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full" style={{ background: 'var(--panel-2)' }}>
      <div className="bar h-full rounded-full" style={{ width: `${Math.max(2, Math.round((value || 0) * 100))}%`, background: color, '--d': `${delay}ms` }} />
    </div>
  )
}

function Retrieve({ d, running }) {
  if (running && !d.hits) {
    return (
      <div className="space-y-2" aria-busy="true">
        <p className="text-xs muted">Embedding the question and scanning {d.types?.join(', ')}...</p>
        {[0, 1, 2].map((i) => <div key={i} className="skeleton scanline h-6" style={{ opacity: 1 - i * 0.25 }} />)}
      </div>
    )
  }
  return (
    <div className="space-y-2">
      <p className="text-xs muted">{d.hits.length} chunks in {d.took_ms} ms. Bars: <span style={{ color: '#4f75fe' }}>vector similarity</span> and <span style={{ color: '#f59e0b' }}>BM25 keywords</span>.</p>
      <ul className="space-y-2">
        {d.hits.slice(0, 6).map((h, i) => (
          <li key={h.ref + i} className="drop-in" style={{ animationDelay: `${i * 90}ms` }}>
            <RefLine item={h} right={<span className="shrink-0 text-xs muted">rel {h.relevance}</span>} />
            <div className="mt-1 grid gap-1">
              <Bar value={h.vector_score} color="#4f75fe" delay={i * 90} />
              <Bar value={h.bm25_score} color="#f59e0b" delay={i * 90 + 60} />
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

function Gauge({ value, threshold, blocked, label }) {
  const pct = Math.min(100, Math.round(value * 100))
  return (
    <div>
      <div className="relative h-3 rounded-full" style={{ background: 'var(--panel-2)' }}>
        <div className="bar h-full rounded-full" style={{ width: `${Math.max(2, pct)}%`, background: blocked ? '#f43f5e' : '#10b981' }} />
        <div className="absolute -top-1 h-5 w-0.5 rounded" style={{ left: `${Math.round(threshold * 100)}%`, background: 'var(--text)' }} title={`threshold ${threshold}`} />
      </div>
      <p className="mt-1 text-xs muted">{label}: <b>{value}</b> {blocked ? '<' : '>='} threshold <b>{threshold}</b>{blocked ? ' - blocked' : ' - passed'}</p>
    </div>
  )
}

function Context({ d }) {
  const used = d.used || []
  const cut = d.cut || []
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs muted"><span>{d.chars} / {d.budget} characters (same budget in every mode)</span>
        {d.neutralised > 0 && <span className="font-semibold text-amber-600">{d.neutralised} instruction-like span(s) neutralised</span>}</div>
      <Bar value={d.chars / d.budget} color="#6366f1" />
      <div className="flex flex-wrap gap-1.5">
        {used.map((u, i) => <RefBadge key={u.ref + i} item={u} className="pop" style={{ '--d': `${i * 60}ms` }} />)}
        {cut.map((c, i) => <RefBadge key={c.ref + i} item={c} dim strike className="pop" style={{ '--d': `${(used.length + i) * 60}ms` }} />)}
      </div>
    </div>
  )
}

function Grounding({ d }) {
  return (
    <ul className="space-y-1.5">
      {d.sentences.map((s, i) => (
        <li key={i} className="slide-in text-xs" style={{ animationDelay: `${i * 120}ms` }}>
          <div className={s.checked && !s.supported ? 'rounded bg-rose-500/15 px-1 underline decoration-rose-500 decoration-dotted' : ''}>{s.text}</div>
          {s.checked ? <Bar value={s.support} color={s.supported ? '#10b981' : '#f43f5e'} delay={i * 120} /> : <span className="muted">{s.abstention ? 'abstention' : 'too short to check'}</span>}
        </li>
      ))}
    </ul>
  )
}

function Detail({ id, s, running, d }) {
  switch (id) {
    case 'safety': return <p className="text-xs muted">{s.status === 'blocked' ? `Blocked: ${d.category}` : 'No secret-exfiltration, command or prompt-override pattern found.'}</p>
    case 'retrieve': return <Retrieve d={d} running={running} />
    case 'gate_topic': return <Gauge value={d.top_relevance} threshold={d.threshold} blocked={s.status === 'blocked'} label="best chunk relevance" />
    case 'gate_history':
      return d.history_intent === false
        ? <p className="text-xs muted">Not a history question, so no history evidence is required.</p>
        : <Gauge value={Math.max(0, ...(d.history_hits ? [d.threshold + (d.history_hits > 0 ? 0.01 : -0.01)] : [0]))} threshold={d.threshold} blocked={s.status === 'blocked'} label={`${d.history_hits} history chunk(s) above`} />
    case 'expand':
      return (
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          {d.added?.length ? d.added.map((h, i) => <RefBadge key={h.ref} item={h} className="pop" style={{ '--d': `${i * 120}ms` }} />) : <span className="muted">Nothing new to pull in.</span>}
        </div>
      )
    case 'context': return <Context d={d} />
    case 'generate':
      return running
        ? <div className="flex items-center gap-2 text-xs muted"><span className="dots"><span /><span /><span /></span>{d.model} is reading {d.evidence_blocks} evidence block(s) ({d.prompt_chars} chars)</div>
        : <p className="text-xs muted">{d.model}: {d.tokens_in} tokens in, {d.tokens_out} out, {d.took_ms} ms</p>
    case 'citations':
      return (
        <div className="flex flex-wrap gap-1.5 text-xs">
          {d.valid.map((r, i) => <RefBadge key={r} item={d.meta?.[r] || { ref: r }} className="pop" style={{ '--d': `${i * 100}ms`, boxShadow: 'inset 0 0 0 1px #1a9d4b' }} />)}
          {d.invalid.map((r, i) => <span key={r} className="chip pop line-through" style={{ '--d': `${(d.valid.length + i) * 100}ms`, color: '#d92d4a' }}>{r} (invented, stripped)</span>)}
          {!d.valid.length && !d.invalid.length && <span className="muted">The answer cites nothing.</span>}
        </div>
      )
    case 'grounding': return <Grounding d={d} />
    case 'redaction': return <p className="text-xs muted">{d.redactions ? `${d.redactions} secret(s) redacted from the answer` : 'No secrets in the answer.'}</p>
    default: return null
  }
}

/**
 * The pipeline, animated from real events. Each stage lights up as the backend reports it, with the data it
 * produced (scores, gate decisions, context, citations) rather than a fake progress bar.
 */
export default function PipelineView({ events, finished }) {
  const { st, mode, blockedAt } = derive(events)
  if (!mode) return <div className="skeleton h-24" aria-busy="true" />
  const applicable = STAGES.filter((s) => s.modes.includes(mode))
  const blockedIdx = blockedAt ? applicable.findIndex((s) => s.id === blockedAt) : -1
  return (
    <ol className="relative space-y-3 pl-1" aria-label="Pipeline">
      {applicable.map((s, i) => {
        const ev = st[s.id]
        let status = 'pending'
        if (ev) status = ev.status === 'start' ? 'running' : ev.status
        else if (blockedIdx >= 0 && i > blockedIdx) status = 'skipped'
        else if (finished) status = 'skipped'
        const showDetail = ev && (status === 'done' || status === 'blocked' || status === 'running')
        return (
          <li key={s.id} className={`flex gap-3 ${status === 'pending' ? 'opacity-45' : ''} ${status === 'skipped' ? 'opacity-30' : ''}`}>
            <div className="flex flex-col items-center">
              <Icon status={status} />
              {i < applicable.length - 1 && <span className="mt-1 w-px flex-1" style={{ background: status === 'done' ? '#10b981' : 'var(--line)', transition: 'background .5s' }} />}
            </div>
            <div className="min-w-0 flex-1 pb-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold">{s.label}</span>
                <Mini className="muted">{s.tag}</Mini>
                {ev?.t != null && status !== 'running' && <span className="ml-auto text-xs muted">{ev.t} ms</span>}
              </div>
              {showDetail && <div className="scale-in mt-1.5"><Detail id={s.id} s={ev} running={status === 'running'} d={ev.detail} /></div>}
              {status === 'skipped' && <p className="text-xs muted">skipped</p>}
            </div>
          </li>
        )
      })}
    </ol>
  )
}

export { typeChip }
