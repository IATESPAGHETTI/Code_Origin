import { useEffect, useRef, useState } from 'react'
import { api, MODES, REFUSAL_LABEL } from '../api.js'
import RefBadge from '../components/RefBadge.jsx'
import PipelineView from '../components/PipelineView.jsx'
import { Typewriter } from '../components/motion.jsx'

const EXAMPLES = [
  'Why was session-cookie authentication replaced with JWT?',
  'Which issue led to the gateway key being moved to the environment?',
  'Who introduced the login rate limiter and why?',
  'Why was the invoice total cache removed?',
]

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

function EvidenceModal({ repo, refName, onClose }) {
  const [data, setData] = useState(null)
  const [err, setErr] = useState('')
  useEffect(() => { api.evidence(repo, refName).then(setData).catch((e) => setErr(e.message)) }, [repo, refName])
  return (
    <div className="fixed inset-0 z-30 flex items-center justify-center bg-black/30 p-4 backdrop-blur-sm" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="panel refract glass-strong scale-in max-h-[80vh] w-full max-w-2xl overflow-auto" onClick={(e) => e.stopPropagation()}>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="min-w-0 text-base font-semibold"><RefBadge item={{ ref: refName, title: data?.chunks?.[0]?.metadata?.title, author: data?.chunks?.[0]?.metadata?.author, date: (data?.chunks?.[0]?.metadata?.date || '').slice(0, 10) }} /></h3>
          <button className="btn-ghost" onClick={onClose}>Close</button>
        </div>
        {err && <p className="text-sm text-rose-600">{err}</p>}
        {!data && !err && <p className="muted text-sm">Loading...</p>}
        {data?.chunks.map((c) => (
          <div key={c.id} className="mb-3">
            {c.metadata?.url && <a className="text-xs underline" style={{ color: 'var(--accent)' }} href={c.metadata.url} target="_blank" rel="noreferrer">open on GitHub</a>}
            <pre className="mt-1 whitespace-pre-wrap rounded-xl bg-black/[.04] p-3 text-xs">{c.text}</pre>
          </div>
        ))}
      </div>
    </div>
  )
}

function Guardrails({ items }) {
  return (
    <div className="flex flex-wrap gap-1">
      {items.map((g, i) => (
        <span key={g.id} style={{ '--d': `${i * 70}ms` }} className={`chip pop ${g.triggered ? 'text-amber-700' : 'muted'}`}
          title={`${g.name}: ${g.action}\n${JSON.stringify(g.detail)}`}>
          {g.id} {g.triggered ? g.action : 'pass'}
        </span>
      ))}
    </div>
  )
}

function Answer({ res, onEvidence, animate }) {
  const unsupported = new Set((res.grounding?.sentences || []).filter((s) => s.checked && !s.supported).map((s) => s.text))
  const [typed, setTyped] = useState(!animate)
  return (
    <div className="space-y-3 border-t pt-4" style={{ borderColor: 'var(--line)' }}>
      {res.refused ? (
        <div className="rounded-xl border border-amber-500/50 bg-amber-500/10 p-3 text-sm">
          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-amber-700">
            Refused &middot; {REFUSAL_LABEL[res.refusal_type] || res.refusal_type}
          </div>
          {res.answer}
        </div>
      ) : (
        <p className="text-[0.9375rem] leading-relaxed">
          {typed
            ? (res.grounding?.sentences?.map((s) => s.text) ?? [res.answer]).map((s, i) => (
              <span key={i} className={unsupported.has(s) ? 'rounded bg-rose-500/15 underline decoration-rose-500 decoration-dotted' : ''}
                title={unsupported.has(s) ? 'Not supported by the retrieved evidence (G4)' : undefined}>{s} </span>))
            : <Typewriter text={res.answer} onDone={() => setTyped(true)} />}
        </p>
      )}
      {typed && res.citations.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {res.citations.map((c, i) => (
            <RefBadge key={c.ref} item={c} onClick={() => onEvidence(c.ref)} className="pop" style={{ '--d': `${i * 90}ms` }} />
          ))}
        </div>
      )}
      {res.invalid_citations.length > 0 && <p className="text-xs text-rose-600">Removed invented citations (G3): {res.invalid_citations.join(', ')}</p>}
      {typed && <Guardrails items={res.guardrails} />}
      <p className="text-xs muted">{res.timings.total_ms} ms &middot; {res.tokens.in} tokens in / {res.tokens.out} out</p>
    </div>
  )
}

function Card({ card, onEvidence, animate }) {
  const label = MODES.find((m) => m.id === card.mode)?.label
  return (
    <article className="panel rise space-y-4" aria-label={label}>
      <header className="flex items-center justify-between">
        <h3 className="text-base font-semibold">{label}</h3>
        <span className="text-xs muted">
          {card.error ? 'failed' : card.result ? (card.result.refused ? 'refused' : 'answered') : 'running'}
        </span>
      </header>
      <PipelineView events={card.events} finished={!!card.result || !!card.error} />
      {card.error && <p role="alert" className="text-sm text-rose-600">{card.error}</p>}
      {card.result && <Answer res={card.result} onEvidence={onEvidence} animate={animate} />}
    </article>
  )
}

export default function Ask() {
  const [repos, setRepos] = useState([])
  const [models, setModels] = useState([])
  const [repo, setRepo] = useState('')
  const [model, setModel] = useState('')
  const [question, setQuestion] = useState('')
  const [compare, setCompare] = useState(true)
  const [mode, setMode] = useState('code_history')
  const [slowMo, setSlowMo] = useState(true)
  const [cards, setCards] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [evidenceRef, setEvidenceRef] = useState(null)
  const abort = useRef(null)

  useEffect(() => {
    api.repos().then((r) => {
      const ready = r.repos.filter((x) => x.status === 'ready')
      setRepos(ready)
      setRepo((cur) => cur || ready[0]?.id || '')
    }).catch((e) => setError(e.message))
    api.config().then((c) => { setModels(c.models || []); setModel((cur) => cur || c.settings.default_model) }).catch(() => {})
    return () => abort.current?.abort()
  }, [])

  const modes = compare ? MODES.map((m) => m.id) : [mode]

  const patch = (m, fn) => setCards((cs) => cs.map((c) => (c.mode === m ? fn(c) : c)))

  const submit = async (e) => {
    e?.preventDefault()
    if (!question.trim() || !repo || loading) return
    setLoading(true); setError('')
    setCards(modes.map((m) => ({ mode: m, events: [], result: null, error: null })))
    abort.current = new AbortController()
    try {
      for (const m of modes) {   // sequential: one local model, honest latency numbers
        try {
          await api.askStream({ repo, question: question.trim(), mode: m, model: model || undefined }, async (_name, ev) => {
            if (ev.type === 'stage') {
              patch(m, (c) => ({ ...c, events: [...c.events, ev] }))
              if (slowMo) await sleep(ev.status === 'start' ? 250 : 520)   // let each stage be seen
            } else if (ev.type === 'result') {
              patch(m, (c) => ({ ...c, result: ev.result }))
            } else if (ev.type === 'error') {
              patch(m, (c) => ({ ...c, error: `${ev.status}: ${ev.detail}` }))
            }
          }, abort.current.signal)
        } catch (err) {
          if (err.name === 'AbortError') return
          patch(m, (c) => ({ ...c, error: err.message }))
        }
      }
    } finally { setLoading(false) }
  }

  return (
    <div className="space-y-6">
      <form onSubmit={submit} className="panel space-y-4 !p-6">
        <div className="grid gap-3 sm:grid-cols-[1fr_1fr_auto]">
          <select className="input" value={repo} onChange={(e) => setRepo(e.target.value)} aria-label="Repository">
            {repos.length === 0 && <option value="">No indexed repository: add one first</option>}
            {repos.map((r) => <option key={r.id} value={r.id}>{r.id}</option>)}
          </select>
          <select className="input" value={model} onChange={(e) => setModel(e.target.value)} aria-label="Model">
            {models.length === 0 && model && <option value={model}>{model}</option>}
            {models.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
          <div className="flex items-center gap-4 text-sm">
            <label className="flex items-center gap-2"><input type="checkbox" checked={compare} onChange={(e) => setCompare(e.target.checked)} />Compare 3 modes</label>
            <label className="flex items-center gap-2" title="Pause on each pipeline stage so it can be followed"><input type="checkbox" checked={slowMo} onChange={(e) => setSlowMo(e.target.checked)} />Slow motion</label>
          </div>
        </div>
        {!compare && (
          <div className="flex gap-2" role="radiogroup" aria-label="Mode">
            {MODES.map((m) => (
              <button type="button" key={m.id} role="radio" aria-checked={mode === m.id} title={m.hint}
                className={mode === m.id ? 'btn-primary' : 'btn-ghost'} onClick={() => setMode(m.id)}>{m.label}</button>
            ))}
          </div>
        )}
        <textarea className="input min-h-[84px]" maxLength={1000} placeholder="Ask why something is the way it is..." value={question}
          onChange={(e) => setQuestion(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) submit(e) }} />
        <div className="flex flex-wrap items-center gap-2">
          <button className="btn-primary" disabled={loading || !question.trim() || !repo}>{loading ? 'Running pipeline...' : 'Ask'}</button>
          {EXAMPLES.map((ex) => <button type="button" key={ex} className="chip-q" onClick={() => setQuestion(ex)}>{ex}</button>)}
        </div>
        {error && <p role="alert" className="text-sm text-rose-600">{error}</p>}
      </form>

      <div className={`grid items-start gap-5 ${cards.length > 1 ? 'lg:grid-cols-3' : ''}`}>
        {cards.map((c) => <Card key={c.mode} card={c} onEvidence={setEvidenceRef} animate={slowMo} />)}
      </div>
      {evidenceRef && <EvidenceModal repo={repo} refName={evidenceRef} onClose={() => setEvidenceRef(null)} />}
    </div>
  )
}
