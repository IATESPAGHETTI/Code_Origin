import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api.js'

/*
 * Scroll-driven story (/story). Every scene is a tall section with a pinned (sticky) full-screen stage.
 * A single rAF loop turns the scroll position into a 0..1 progress value per scene (--p) and one global
 * value (--pg); everything on screen is plain CSS reading those variables, so motion is continuous and
 * tied to the scroll, with no per-frame React renders.
 */

const pct = (v) => (v == null ? '-' : `${Math.round(v * 100)}%`)
const clamp01 = (x) => Math.min(Math.max(x, 0), 1)

/** this element's own 0..1 window (a..b) inside the scene's progress */
const seg = (a, b) => ({ '--s': `clamp(0, calc((var(--p) - ${a}) / ${(b - a).toFixed(4)}), 1)` })

/** scroll-linked reveal: slides/scales/fades in across [a, b] of the scene */
function Sx({ a, b, dy = 44, dx = 0, className = '', style, children }) {
  return <div className={`sx ${className}`} style={{ ...seg(a, b), '--dy': `${dy}px`, '--dx': `${dx}px`, ...style }}>{children}</div>
}

const Heading = ({ eyebrow, title, sub, a = 0.02, b = 0.16 }) => (
  <div className="mb-6">
    <Sx a={a} b={b} dy={24}><div className="eyebrow mb-1 text-base">{eyebrow}</div></Sx>
    <Sx a={a + 0.02} b={b + 0.04} dy={34}><h2 className="gradient-text text-4xl font-semibold leading-tight lg:text-5xl">{title}</h2></Sx>
    {sub && <Sx a={a + 0.05} b={b + 0.08} dy={30}><p className="mt-2 max-w-4xl text-lg muted lg:text-xl">{sub}</p></Sx>}
  </div>
)

/* ================================================================ scenes */

function Hero() {
  return (
    <div className="relative">
      <div style={{ transform: 'translate3d(0, calc(var(--p) * -90px), 0) scale(calc(1 - var(--p) * 0.18))', opacity: 'calc(1 - var(--p) * 1.35)', transformOrigin: 'left center' }}>
        <div className="eyebrow mb-3 text-lg">College DevOps project</div>
        <h1 className="gradient-text text-7xl font-semibold leading-none lg:text-9xl">CodeOrigin</h1>
      </div>
      <p className="mt-6 max-w-4xl text-2xl leading-snug lg:text-3xl" style={{ transform: 'translate3d(0, calc(var(--p) * -50px), 0)', opacity: 'calc(1 - var(--p) * 1.8)' }}>
        Ask a codebase <span style={{ color: 'var(--accent)' }}>why</span> it was built this way, and get an answer grounded in its own history.
      </p>
      <p className="mt-5 max-w-3xl text-lg muted lg:text-xl" style={{ opacity: 'calc(1 - var(--p) * 2.4)' }}>
        A repository-aware RAG system, packaged and delivered as a containerised, tested, monitored DevOps pipeline.
      </p>
      <div className="mt-12 flex items-center gap-3 text-sm muted" style={{ opacity: 'calc(1 - var(--p) * 4)' }}>
        <span className="inline-block h-9 w-5 rounded-full border-2 border-current p-1"><span className="block h-2 w-full animate-bounce rounded-full bg-current" /></span>
        Scroll to begin
      </div>
    </div>
  )
}

const CHAIN = [
  { x: 40, label: 'Session fixation reported', sub: 'issue #7', color: '#d97706' },
  { x: 250, label: 'Move auth to JWT', sub: 'PR #8 · HS256 debated', color: '#7c3aed' },
  { x: 470, label: 'Replace cookies with JWT', sub: 'commit 69e7bbd', color: '#0284c7' },
  { x: 680, label: 'issue_token() today', sub: 'src/auth.py', color: '#059669' },
]

function Problem() {
  return (
    <div>
      <Heading eyebrow="The problem" title={'Code can’t explain itself'} sub="The current code shows what exists. The reason lives in the history around it." />
      <div className="panel mb-5 !p-3">
        <svg viewBox="-70 0 860 150" className="h-auto w-full" role="img" aria-label="Evidence chain from issue to pull request to commit to code">
          {CHAIN.slice(0, -1).map((n, i) => {
            const a = 0.18 + i * 0.17
            return (
              <path key={n.label} d={`M ${n.x + 18} 55 C ${n.x + 80} 15, ${CHAIN[i + 1].x - 80} 15, ${CHAIN[i + 1].x - 18} 55`} fill="none" stroke={CHAIN[i + 1].color}
                strokeWidth="3" pathLength="1" style={{ ...seg(a, a + 0.15), strokeDasharray: 1, strokeDashoffset: 'calc(1 - var(--s))' }} />
            )
          })}
          {CHAIN.map((n, i) => {
            const a = 0.12 + i * 0.17
            return (
              <g key={n.label} style={{ ...seg(a, a + 0.12), opacity: 'var(--s)', transform: 'scale(calc(0.4 + 0.6 * var(--s)))', transformBox: 'fill-box', transformOrigin: 'center' }}>
                <circle cx={n.x} cy="55" r="19" fill={n.color} opacity="0.18" />
                <circle cx={n.x} cy="55" r="9" fill={n.color} />
                <text x={n.x} y="100" textAnchor="middle" fontSize="15" fill="var(--text)" fontWeight="600">{n.label}</text>
                <text x={n.x} y="121" textAnchor="middle" fontSize="13" fill="var(--muted)">{n.sub}</text>
              </g>
            )
          })}
        </svg>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        {[
          ['Ordinary assistants', 'See only today’s code, so “why?” becomes a guess.', -90],
          ['CodeOrigin', 'Indexes commits, diffs, issues, PRs and reviews, cross-linked, and cites each claim.', 0],
          ['If the history is silent', 'It says so instead of inventing a story.', 90],
        ].map(([t, d, dx], i) => (
          <Sx key={t} a={0.55 + i * 0.1} b={0.75 + i * 0.1} dx={dx} dy={50}>
            <div className="panel h-full text-lg"><b>{t}</b><p className="mt-1 muted">{d}</p></div>
          </Sx>
        ))}
      </div>
    </div>
  )
}

function Research() {
  const modes = [
    ['no_context', 'Question only', 'what the model guesses'],
    ['code_only', 'Question + current code and docs', 'how most assistants work'],
    ['code_history', 'Code + commits, diffs, issues, PRs, reviews', 'the hypothesis'],
    ['oracle', 'Question + the gold evidence, no retrieval', 'separates retrieval from model failure'],
  ]
  return (
    <div>
      <Heading eyebrow="Research question" title="A fair test, decided in advance" sub="Does adding repository history to an LLM-RAG pipeline improve the accuracy and usefulness of answers?" />
      <div className="grid gap-4 md:grid-cols-4">
        {modes.map(([m, d, why], i) => (
          <Sx key={m} a={0.18 + i * 0.12} b={0.38 + i * 0.12} dx={i % 2 ? 70 : -70} dy={40}>
            <div className="panel relative h-full">
              <div className="pointer-events-none absolute inset-0 rounded-3xl" style={{ boxShadow: 'inset 0 0 0 2px var(--accent)', opacity: m === 'code_history' ? 'clamp(0, calc((var(--p) - 0.7) * 5), 1)' : 0 }} />
              <div className="font-mono text-base" style={{ color: 'var(--accent)' }}>{m}</div>
              <p className="mt-2 text-lg">{d}</p>
              <p className="mt-1 text-sm muted">{why}</p>
            </div>
          </Sx>
        ))}
      </div>
      <Sx a={0.68} b={0.86} dy={60}>
        <div className="panel mt-5 text-lg">
          <b>Decision rule, fixed before running:</b> history is useful only if <code>code_history</code> beats <code>code_only</code> on history questions by at least <b>0.10</b> correctness,
          the 95% bootstrap interval excludes 0, and the control category loses no more than <b>0.05</b>.
          <p className="mt-2 text-base muted">Same prompt shape and context budget in every mode, temperature 0, fixed seed. Per-category results, never one blended score.</p>
        </div>
      </Sx>
    </div>
  )
}

function ArchRow({ items, a }) {
  return (
    <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(${items.length}, minmax(0, 1fr))` }}>
      {items.map(([t, s], i) => (
        <Sx key={t} a={a + i * 0.05} b={a + 0.12 + i * 0.05} dy={46}>
          <div className="panel h-full text-center"><div className="text-lg font-semibold">{t}</div><div className="mt-1 text-sm muted">{s}</div></div>
        </Sx>
      ))}
    </div>
  )
}

function ArchArrow({ a }) {
  return <Sx a={a} b={a + 0.06} dy={10}><div className="my-1 text-center text-xl muted">&darr;</div></Sx>
}

function Architecture() {
  return (
    <div>
      <Heading eyebrow="Architecture" title="Small services, one entry point" sub="Seven containers behind one gateway, every one with a health check and a non-root user." />
      <div className="mx-auto max-w-4xl space-y-1">
        <ArchRow a={0.12} items={[['Browser', 'React + Tailwind on nginx :5180'], ['Gateway :8200', 'limits, rate limit, request IDs, API key, /metrics']]} />
        <ArchArrow a={0.28} />
        <ArchRow a={0.3} items={[['Ingest :8201', 'git + GitHub API, SQLite'], ['Orchestrator :8204', 'pipeline + guardrails'], ['Eval :8205', 'runs, stats, report']]} />
        <ArchArrow a={0.5} />
        <ArchRow a={0.52} items={[['RAG :8202', 'vector + BM25, rank fusion'], ['LLM :8203', 'Ollama client + jury']]} />
        <ArchArrow a={0.66} />
        <ArchRow a={0.68} items={[['ChromaDB :8206', 'vector store'], ['Ollama (host)', 'llama2, codellama, starcoder2, gemma']]} />
      </div>
      <Sx a={0.84} b={0.96} dy={20}><p className="mt-5 text-center text-base muted">Shared code lives in one place and is copied into services, with a CI check that fails on drift.</p></Sx>
    </div>
  )
}

const FLOW = [
  ['Safety', 'G10', 'Refuses requests for secrets, command execution or prompt override before any retrieval.'],
  ['Retrieve', 'G8', 'Vector + BM25 search, scoped to a single repository so repos never mix.'],
  ['On topic?', 'G1', 'If nothing relevant is found the question is refused with no model call.'],
  ['Enough history?', 'G2', 'A “why” question with no history evidence gets “the history doesn’t say”, not a guess.'],
  ['Follow links', '', 'Issue, PR and commit cross-links pull in the evidence that explains each other.'],
  ['Build context', 'G5', 'Commit text is untrusted data: instruction-like text is neutralised inside a fixed context budget.'],
  ['Generate', '', 'Local model at temperature 0, same prompt shape in every mode.'],
  ['Check citations', 'G3', 'Every [ref] the model writes is checked against what was retrieved; invented ones are stripped.'],
  ['Check grounding', 'G4', 'Each sentence must be supported by the evidence; unsupported ones are flagged.'],
  ['Redact', 'G6', 'Secrets are removed at ingest and again from the final answer.'],
]

function Flow() {
  const w = 0.085
  const start = (i) => 0.1 + i * w
  return (
    <div>
      <Heading eyebrow="One question, end to end" title="From question to cited answer" sub="Guardrails are enforced in code, not by asking a small model to behave." />
      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-5">
        {FLOW.map(([s, g], i) => (
          <div key={s} className="panel relative !p-3 text-center">
            <div className="pointer-events-none absolute inset-0 rounded-3xl" style={{ ...seg(start(i) - 0.03, start(i) + 0.03), opacity: 'var(--s)', background: 'var(--accent-soft)', boxShadow: 'inset 0 0 0 2px var(--accent)' }} />
            <div className="relative text-base font-semibold lg:text-lg">{s}</div>
            <div className="relative mt-1 h-6">{g && <span className="chip" style={{ color: 'var(--accent)' }}>{g}</span>}</div>
          </div>
        ))}
      </div>
      <div className="panel relative h-36 !p-6">
        {FLOW.map(([s, g, d], i) => (
          <div key={s} className="absolute inset-0 flex flex-col justify-center px-6"
            style={{ opacity: `min(clamp(0, calc((var(--p) - ${start(i) - 0.02}) / 0.03), 1), calc(1 - clamp(0, calc((var(--p) - ${start(i) + w - 0.02}) / 0.03), 1)))` }}>
            <div className="text-lg font-semibold" style={{ color: 'var(--accent)' }}>{i + 1}. {s} {g && <span className="chip ml-2">{g}</span>}</div>
            <p className="mt-1 text-xl">{d}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

function DevOps() {
  const items = [
    ['Containers', '7 multi-stage images, non-root, health checks, read-only filesystems, dropped capabilities'],
    ['Compose', 'One base file plus dev, prod, monitoring and demo overrides; Ollama GPU profile; env-driven config'],
    ['CI', 'Lint, drift checks, 6 test jobs, frontend build, compose smoke test, end-to-end eval gate'],
    ['Security', 'gitleaks secret scan and Trivy dependency and Dockerfile scan on every push; secrets only in .env'],
    ['CD', 'A v* tag builds, scans and publishes every image to GHCR, then cuts a release'],
    ['Monitoring', 'Prometheus + Grafana + Loki, with alert rules and evaluation scores as metrics'],
  ]
  return (
    <div>
      <Heading eyebrow="DevOps" title="Built to be shipped" sub="Everything here was run for real: images built, stack healthy, pipeline green on GitHub." />
      <div className="grid gap-4 md:grid-cols-3">
        {items.map(([t, d], i) => (
          <Sx key={t} a={0.12 + i * 0.11} b={0.32 + i * 0.11} dx={i % 2 ? 90 : -90} dy={50}>
            <div className="panel h-full"><div className="text-xl font-semibold" style={{ color: 'var(--accent)' }}>{t}</div><p className="mt-2 text-lg">{d}</p></div>
          </Sx>
        ))}
      </div>
    </div>
  )
}

const JOBS = ['lint-and-drift', 'test: rag', 'test: llm', 'test: ingest', 'test: orchestrator', 'test: eval', 'test: gateway', 'frontend', 'security (gitleaks + Trivy)', 'compose-smoke', 'eval-gate']

function CI() {
  return (
    <div>
      <Heading eyebrow="Pipeline" title="What CI checks on every push" sub="Latest run on main: all 11 jobs passed." />
      <div className="grid gap-3 md:grid-cols-4">
        {JOBS.map((j, i) => {
          const a = 0.1 + i * 0.065
          return (
            <Sx key={j} a={Math.max(0.05, a - 0.1)} b={a} dy={30}>
              <div className="panel relative flex items-center gap-3 !py-3 text-lg">
                <span className="relative inline-block h-4 w-4">
                  <span className="absolute inset-0 rounded-full bg-slate-300" />
                  <span className="absolute inset-0 rounded-full bg-emerald-500" style={{ ...seg(a, a + 0.05), opacity: 'var(--s)', transform: 'scale(calc(0.5 + 0.5 * var(--s)))' }} />
                </span>
                {j}
              </div>
            </Sx>
          )
        })}
      </div>
      <div className="mt-5 h-3 overflow-hidden rounded-full bg-black/10"><div className="h-full rounded-full bg-emerald-500" style={{ width: 'calc(clamp(0, (var(--p) - 0.1) / 0.75, 1) * 100%)' }} /></div>
      <Sx a={0.84} b={0.94} dy={20}>
        <div className="panel mt-5 text-lg">
          <b>Running it for real found real problems:</b> a HIGH vulnerability in a frontend dependency (fixed), Dockerfiles running as root (fixed), linter-version drift (pinned), and a wrong script call in the smoke test (fixed).
          <div className="mt-3"><a className="btn-primary" href="https://github.com/IATESPAGHETTI/Code_Origin/actions" target="_blank" rel="noreferrer">Open the Actions page</a></div>
        </div>
      </Sx>
    </div>
  )
}

function Results() {
  const [state, setState] = useState({ loading: true })
  useEffect(() => {
    let alive = true
    api.evalRuns().then(async (d) => {
      const done = (d.runs || []).filter((r) => r.status === 'done').sort((a, b) => b.total - a.total)
      if (!done.length) return alive && setState({ none: true })
      const body = await api.evalRun(done[0].id)
      if (alive) setState({ run: body.run, rep: body.report })
    }).catch((e) => alive && setState({ error: e.message }))
    return () => { alive = false }
  }, [])
  const { rep, run } = state
  const modes = ['no_context', 'code_only', 'code_history']
  return (
    <div>
      <Heading eyebrow="Live from the evaluation service" title="What the experiment shows so far"
        sub={run ? `Run #${run.id}, ${run.config?.split} split, ${run.total} answers, real local models. Overall correctness per mode.` : ''} />
      {state.loading && <p className="text-xl muted">Loading results...</p>}
      {(state.none || state.error) && <p className="text-xl muted">No finished evaluation run is available. {state.error}</p>}
      {rep && (
        <>
          <div className="grid gap-4 md:grid-cols-3">
            {rep.models.map((m, mi) => {
              const d = rep.decisions.find((x) => x.model === m)
              const a = 0.12 + mi * 0.08
              return (
                <Sx key={m} a={a} b={a + 0.16} dy={60}>
                  <div className="panel h-full">
                    <div className="text-xl font-semibold">{m}</div>
                    <div className="mt-3 space-y-2">
                      {modes.map((mo, k) => {
                        const v = rep.totals[`${m}|${mo}`]?.correctness || 0
                        const g = a + 0.14 + k * 0.1
                        return (
                          <div key={mo} style={{ ...seg(g, g + 0.18), '--v': v }}>
                            <div className="flex justify-between text-base"><span className="font-mono">{mo}</span><b style={{ opacity: 'var(--s)' }}>{pct(v)}</b></div>
                            <div className="h-3 overflow-hidden rounded bg-black/10">
                              <div className="h-full rounded" style={{ width: 'calc(var(--v) * var(--s) * 100%)', background: mo === 'code_history' ? 'var(--accent)' : '#9aa0a6' }} />
                            </div>
                          </div>
                        )
                      })}
                    </div>
                    {d && (
                      <p className="mt-3 text-base" style={{ ...seg(0.7, 0.82), opacity: 'var(--s)' }}>
                        History vs code-only: <b>{d.history_diff >= 0 ? '+' : ''}{d.history_diff}</b> <span className="muted">({d.verdict})</span>
                      </p>
                    )}
                  </div>
                </Sx>
              )
            })}
          </div>
          <Sx a={0.84} b={0.95} dy={20}>
            <p className="mt-5 text-lg muted">Honest reading: a small development split, scored automatically. History raises both 7B models; only llama2 clears the pre-registered rule (codellama has the same effect but a wider interval), and the 3B model barely benefits. It shows the pipeline works. It is not yet a research conclusion.</p>
          </Sx>
        </>
      )}
    </div>
  )
}

function Health() {
  const [h, setH] = useState(null)
  useEffect(() => {
    let alive = true
    const tick = () => api.healthAll().then((x) => alive && setH(x)).catch(() => alive && setH({ status: 'down', services: {} }))
    tick()
    const id = setInterval(tick, 5000)
    return () => { alive = false; clearInterval(id) }
  }, [])
  const rows = [['gateway', h ? h.status !== 'down' : null], ...Object.entries(h?.services || {})]
  return (
    <div>
      <Heading eyebrow="Live system check" title="The running stack" sub="Asked through the gateway every few seconds." />
      <div className="grid gap-4 md:grid-cols-3">
        {rows.map(([name, ok], i) => (
          <Sx key={name} a={0.1 + i * 0.08} b={0.28 + i * 0.08} dy={40}>
            <div className="panel flex items-center gap-3 text-xl">
              <span className={`h-4 w-4 rounded-full ${ok == null ? 'bg-slate-400' : ok ? 'live-dot bg-emerald-500' : 'bg-rose-500'}`} />
              <span className="capitalize">{name}</span>
              <span className="ml-auto text-base muted">{ok == null ? 'checking' : ok ? 'healthy' : 'down'}</span>
            </div>
          </Sx>
        ))}
      </div>
      <Sx a={0.7} b={0.85} dy={20}>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link className="btn-primary" to="/ask">Ask a question live</Link>
          <Link className="btn-ghost" to="/repos">Repositories</Link>
          <Link className="btn-ghost" to="/eval">Evaluation</Link>
        </div>
      </Sx>
    </div>
  )
}

function LimitCol({ title, items, dx, a }) {
  return (
    <Sx a={a} b={a + 0.3} dx={dx} dy={30}>
      <div className="panel h-full text-lg"><b>{title}</b>
        <ul className="mt-2 list-disc space-y-1 pl-5 muted">{items.map((t) => <li key={t}>{t}</li>)}</ul>
      </div>
    </Sx>
  )
}

function Limits() {
  return (
    <div>
      <Heading eyebrow="Honest limits" title="What we would do next" sub="What the evidence does and does not support." />
      <div className="grid gap-4 md:grid-cols-2">
        <LimitCol title="Limits" dx={-140} a={0.15} items={['Evaluated on a seeded demo repository, dev split, automatic scoring.', 'The LLM jury is too lenient to trust until compared with human grades.', 'Guardrail thresholds rest on very few negative examples.', 'Small local models on one 6 GB GPU.']} />
        <LimitCol title="Next" dx={140} a={0.3} items={['Test on a real repository with 40+ human-verified questions.', 'Human-grade about 60 answers and measure judge agreement.', 'One held-out run, then the final analysis.', 'Publish tagged images through the release pipeline.']} />
      </div>
    </div>
  )
}

function End() {
  return (
    <div className="text-center">
      <div style={{ ...seg(0.05, 0.4), opacity: 'var(--s)', transform: 'scale(calc(0.7 + 0.3 * var(--s)))' }}>
        <h2 className="gradient-text text-7xl font-semibold lg:text-9xl">Questions?</h2>
      </div>
      <Sx a={0.3} b={0.55} dy={30}><p className="mt-6 text-2xl muted">github.com/IATESPAGHETTI/Code_Origin</p></Sx>
      <Sx a={0.5} b={0.75} dy={30}>
        <div className="mt-8 flex justify-center gap-3">
          <Link className="btn-primary" to="/ask">Live demo</Link>
          <Link className="btn-ghost" to="/">Exit presentation</Link>
        </div>
      </Sx>
    </div>
  )
}

/** [name, scene height in screens, component, where "jump here" lands (fraction of the scene)] */
const SCENES = [
  ['Title', 1.8, Hero, 0], ['Problem', 2.6, Problem, 0.5], ['Research design', 2.4, Research, 0.5], ['Architecture', 2.8, Architecture, 0.5],
  ['Question flow', 3.4, Flow, 0.3], ['DevOps', 2.2, DevOps, 0.6], ['CI/CD', 2.6, CI, 0.35], ['Results', 2.8, Results, 0.55],
  ['Live system', 1.8, Health, 0.6], ['Limits', 1.8, Limits, 0.7], ['Questions', 1.5, End, 0.8],
]

/* ================================================================== shell */

export default function Story() {
  const navigate = useNavigate()
  const root = useRef(null)
  const scroller = useRef(null)
  const sections = useRef([])
  const loop = useRef({ jump: () => {} })
  const [active, setActive] = useState(0)

  const goTo = useCallback((i, instant = false) => {
    const sc = scroller.current
    const k = Math.min(Math.max(i, 0), SCENES.length - 1)
    const el = sections.current[k]
    if (!sc || !el) return
    const top = el.offsetTop + SCENES[k][3] * Math.max(el.offsetHeight - sc.clientHeight, 0)
    sc.scrollTo({ top, behavior: instant ? 'instant' : 'smooth' })
    if (instant) loop.current.jump()
  }, [])

  // the animation loop: damped scroll position -> CSS variables
  useEffect(() => {
    const sc = scroller.current
    const rootEl = root.current
    if (!sc || !rootEl) return undefined
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    let target = sc.scrollTop
    let cur = target
    let raf = 0
    let running = false
    let lastActive = -1

    const apply = () => {
      const vh = sc.clientHeight
      const max = sc.scrollHeight - vh
      rootEl.style.setProperty('--pg', (max > 0 ? cur / max : 0).toFixed(4))
      let act = 0
      sections.current.forEach((el, i) => {
        if (!el) return
        const top = el.offsetTop
        const p = clamp01((cur - top) / Math.max(el.offsetHeight - vh, 1))
        el.style.setProperty('--p', p.toFixed(4))
        if (target + vh * 0.5 >= top) act = i
      })
      if (act !== lastActive) { lastActive = act; setActive(act) }
    }
    const tick = () => {
      cur += (target - cur) * 0.2
      if (Math.abs(target - cur) < 0.4) { cur = target; running = false }
      apply()
      if (running) raf = requestAnimationFrame(tick)
    }
    const onScroll = () => {
      target = sc.scrollTop
      if (reduce) { cur = target; apply(); return }
      if (!running) { running = true; raf = requestAnimationFrame(tick) }
    }
    loop.current.jump = () => { target = sc.scrollTop; cur = target; apply() }

    sc.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', apply)
    apply()
    sc.focus({ preventScroll: true })
    return () => { sc.removeEventListener('scroll', onScroll); window.removeEventListener('resize', apply); cancelAnimationFrame(raf) }
  }, [])

  // open at the scene named in the URL (#4)
  useEffect(() => {
    const n = parseInt(window.location.hash.replace('#', ''), 10)
    if (Number.isFinite(n) && n > 1) requestAnimationFrame(() => goTo(n - 1, true))
  }, [goTo])
  useEffect(() => { window.history.replaceState(null, '', `#${active + 1}`) }, [active])

  useEffect(() => {
    const onKey = (e) => {
      if ([' ', 'PageDown', 'ArrowRight'].includes(e.key)) { e.preventDefault(); goTo(active + 1) }
      else if (['PageUp', 'ArrowLeft'].includes(e.key)) { e.preventDefault(); goTo(active - 1) }
      else if (e.key === 'Home') { e.preventDefault(); goTo(0) }
      else if (e.key === 'End') { e.preventDefault(); goTo(SCENES.length - 1) }
      else if (e.key === 'f' || e.key === 'F') {
        if (document.fullscreenElement) document.exitFullscreen?.()
        else document.documentElement.requestFullscreen?.()
      } else if (e.key === 'Escape' && !document.fullscreenElement) navigate('/')
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [active, goTo, navigate])

  return (
    <div ref={root} className="fixed inset-0 z-50 overflow-hidden" style={{ background: 'var(--bg)', '--pg': 0 }}>
      {/* drifting backdrop: moves and shifts colour with overall progress */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true" style={{ filter: 'hue-rotate(calc(var(--pg) * 120deg))' }}>
        <div className="orb" style={{ width: 420, height: 420, left: '-8%', top: '8%', background: 'rgba(0,113,227,.13)', transform: 'translate3d(calc(var(--pg) * 380px), calc(var(--pg) * 260px), 0)' }} />
        <div className="orb" style={{ width: 360, height: 360, right: '-6%', top: '38%', background: 'rgba(168,85,247,.11)', transform: 'translate3d(calc(var(--pg) * -420px), calc(var(--pg) * -300px), 0)' }} />
        <div className="orb" style={{ width: 300, height: 300, left: '38%', bottom: '-14%', background: 'rgba(16,185,129,.10)', transform: 'translate3d(calc(var(--pg) * -240px), calc(var(--pg) * -160px), 0)' }} />
      </div>

      <div className="pointer-events-none absolute inset-x-0 top-0 z-10">
        <div className="h-1" style={{ background: 'var(--accent)', transform: 'scaleX(var(--pg))', transformOrigin: 'left' }} />
        <div className="pointer-events-auto flex items-center justify-between px-6 py-3 backdrop-blur-md lg:px-14" style={{ background: 'color-mix(in srgb, var(--bg) 62%, transparent)' }}>
          <Link to="/" className="flex items-center gap-2.5" aria-label="Exit presentation">
            <img src="/favicon.svg" alt="" className="h-7 w-7" /><span className="text-lg font-extrabold tracking-tight">CodeOrigin</span>
          </Link>
          <span className="text-sm muted">{SCENES[active][0]} &middot; {active + 1} / {SCENES.length}</span>
          <span className="flex items-center gap-2">
            <Link to="/present" className="btn-ghost !py-1.5 text-sm">Quick deck</Link>
            <Link to="/" className="btn-ghost !py-1.5 text-sm">Exit</Link>
          </span>
        </div>
      </div>

      <nav className="absolute right-4 top-1/2 z-10 hidden -translate-y-1/2 flex-col items-end gap-3 md:flex" aria-label="Scenes">
        {SCENES.map(([name], k) => (
          <button key={name} onClick={() => goTo(k)} aria-label={name} aria-current={k === active} title={name} className="group flex items-center gap-2">
            <span className={`text-xs transition ${k === active ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'} muted`}>{name}</span>
            <span className="rounded-full transition-all duration-300" style={{ width: 10, height: k === active ? 28 : 10, background: k === active ? 'var(--accent)' : 'rgba(0,0,0,.22)' }} />
          </button>
        ))}
      </nav>

      <div ref={scroller} tabIndex={0} aria-label="Presentation" className="relative h-full overflow-y-auto outline-none">
        {SCENES.map(([name, len, Scene], k) => (
          <section key={name} ref={(el) => { sections.current[k] = el }} aria-label={name} style={{ height: `${len * 100}vh`, '--p': 0 }}>
            <div className="sticky top-0 flex h-screen items-center overflow-hidden px-6 pb-10 pt-16 lg:px-24">
              <div className="mx-auto w-full max-w-[1400px]"><Scene /></div>
            </div>
          </section>
        ))}
      </div>

      <p className="pointer-events-none absolute bottom-2 left-0 right-0 z-10 text-center text-xs muted">Scroll &middot; Space / &larr; &rarr; jump between scenes &middot; F full screen &middot; Esc exit</p>
    </div>
  )
}
