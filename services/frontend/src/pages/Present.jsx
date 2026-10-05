import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api.js'
import EvidenceChain from '../components/EvidenceChain.jsx'

const pct = (v) => (v == null ? '-' : `${Math.round(v * 100)}%`)

const Title = ({ eyebrow, children, sub }) => (
  <div className="mb-8">
    {eyebrow && <div className="eyebrow mb-2 text-base">{eyebrow}</div>}
    <h2 className="gradient-text text-5xl font-semibold leading-tight">{children}</h2>
    {sub && <p className="mt-3 max-w-4xl text-xl muted">{sub}</p>}
  </div>
)

const Box = ({ title, sub, tone = 'default', className = '' }) => (
  <div className={`panel text-center ${className}`} style={tone === 'accent' ? { boxShadow: 'inset 0 0 0 2px var(--accent)' } : undefined}>
    <div className="text-lg font-semibold">{title}</div>
    {sub && <div className="mt-1 text-sm muted">{sub}</div>}
  </div>
)

/* ---------------------------------------------------------------- slides */

function SlideTitle() {
  return (
    <div className="flex h-full flex-col justify-center">
      <div className="eyebrow mb-4 text-lg">College DevOps project</div>
      <h1 className="gradient-text text-8xl font-semibold leading-none">CodeOrigin</h1>
      <p className="mt-6 max-w-4xl text-3xl leading-snug">
        Ask a codebase <em className="not-italic" style={{ color: 'var(--accent)' }}>why</em> it was built this way, and get an answer grounded in its own history.
      </p>
      <p className="mt-6 text-xl muted">A repository-aware RAG system, packaged and delivered as a containerised, tested, monitored DevOps pipeline.</p>
    </div>
  )
}

function SlideProblem() {
  return (
    <div>
      <Title eyebrow="The problem" sub="The current code shows what exists. The reason lives in the history around it.">
        Code can&rsquo;t explain itself
      </Title>
      <div className="panel mb-6"><EvidenceChain /></div>
      <div className="grid gap-4 md:grid-cols-3 text-lg">
        <div className="panel"><b>Ordinary assistants</b><p className="mt-1 muted">See only today&rsquo;s code, so &ldquo;why?&rdquo; becomes a guess.</p></div>
        <div className="panel"><b>CodeOrigin</b><p className="mt-1 muted">Indexes commits, diffs, issues, PRs and reviews, cross-linked, and cites each claim (<code>commit:69e7bbd</code>).</p></div>
        <div className="panel"><b>If the history is silent</b><p className="mt-1 muted">It says so instead of inventing a story.</p></div>
      </div>
    </div>
  )
}

function SlideResearch() {
  const modes = [
    ['no_context', 'Question only', 'what the model guesses'],
    ['code_only', 'Question + current code and docs', 'how most assistants work'],
    ['code_history', 'Code + commits, diffs, issues, PRs, reviews', 'the hypothesis'],
    ['oracle', 'Question + gold evidence, no retrieval', 'separates retrieval from model failure'],
  ]
  return (
    <div>
      <Title eyebrow="Research question" sub="Does adding repository history to an LLM-RAG pipeline improve the accuracy and usefulness of answers?">
        A fair test, decided in advance
      </Title>
      <div className="grid gap-4 md:grid-cols-4">
        {modes.map(([m, d, why]) => (
          <div key={m} className="panel">
            <div className="font-mono text-base" style={{ color: 'var(--accent)' }}>{m}</div>
            <p className="mt-2 text-lg">{d}</p>
            <p className="mt-1 text-sm muted">{why}</p>
          </div>
        ))}
      </div>
      <div className="panel mt-6 text-lg">
        <b>Decision rule (fixed before running):</b> history is useful only if <code>code_history</code> beats <code>code_only</code> on history questions by at least <b>0.10</b> correctness,
        the 95% bootstrap interval excludes 0, and the control category loses no more than <b>0.05</b>.
        <p className="mt-2 text-base muted">Same prompt shape and context budget in every mode, temperature 0, fixed seed. Results are reported per category, never as one blended score.</p>
      </div>
    </div>
  )
}

function SlideArchitecture() {
  return (
    <div>
      <Title eyebrow="Architecture" sub="Seven containers behind one gateway. Every service has a health check and runs as a non-root user.">
        Small services, one entry point
      </Title>
      <div className="grid gap-4 text-center md:grid-cols-5">
        <Box title="Browser" sub="React + Tailwind (nginx) :5180" />
        <Box title="Gateway :8200" sub="limits, rate limit, request IDs, API key, /metrics" tone="accent" className="md:col-span-1" />
        <div className="grid gap-4 md:col-span-3 md:grid-cols-3">
          <Box title="Ingest :8201" sub="git + GitHub API, SQLite" />
          <Box title="Orchestrator :8204" sub="pipeline + guardrails" />
          <Box title="Eval :8205" sub="runs, stats, report" />
        </div>
      </div>
      <div className="mt-4 grid gap-4 text-center md:grid-cols-4">
        <Box title="RAG :8202" sub="vector + BM25, rank fusion" />
        <Box title="ChromaDB :8206" sub="vector store" />
        <Box title="LLM :8203" sub="Ollama client + jury" />
        <Box title="Ollama (host)" sub="llama2, codellama, starcoder2, gemma" />
      </div>
      <p className="mt-6 text-lg muted">Browser &rarr; Gateway &rarr; Ingest / Orchestrator / Eval &rarr; RAG + LLM &rarr; ChromaDB + Ollama. Shared code lives in one place and is copied into services, with a CI check that fails on drift.</p>
    </div>
  )
}

function SlideFlow() {
  const steps = [
    ['Safety', 'G10'], ['Retrieve', 'G8'], ['On topic?', 'G1'], ['Enough history?', 'G2'],
    ['Follow links', ''], ['Build context', 'G5'], ['Generate', ''], ['Check citations', 'G3'], ['Check grounding', 'G4'], ['Redact', 'G6'],
  ]
  return (
    <div>
      <Title eyebrow="One question, end to end" sub="Guardrails are enforced in code, not by asking a small model to behave.">
        From question to cited answer
      </Title>
      <div className="flex flex-wrap items-center gap-3">
        {steps.map(([s, g], i) => (
          <div key={s} className="flex items-center gap-3">
            <div className="panel !py-3 text-center">
              <div className="text-lg font-semibold">{s}</div>
              {g && <div className="chip mt-1" style={{ color: 'var(--accent)' }}>{g}</div>}
            </div>
            {i < steps.length - 1 && <span className="text-2xl muted">&rarr;</span>}
          </div>
        ))}
      </div>
      <div className="mt-8 grid gap-3 text-base md:grid-cols-2">
        <div className="panel"><b>G1</b> off-topic refused with no model call &middot; <b>G2</b> says &ldquo;the history doesn&rsquo;t say&rdquo; &middot; <b>G3</b> invented citations stripped &middot; <b>G4</b> unsupported sentences flagged</div>
        <div className="panel"><b>G5</b> commit text is untrusted data (prompt-injection neutralised) &middot; <b>G6</b> secrets redacted at ingest and in output &middot; <b>G7</b> input limits &middot; <b>G8</b> repo isolation &middot; <b>G9</b> signed webhooks &middot; <b>G10</b> unsafe requests refused</div>
      </div>
    </div>
  )
}

function SlideDevOps() {
  const items = [
    ['Containers', '7 multi-stage images, non-root, health checks, read-only filesystems, dropped capabilities'],
    ['Compose', 'One base file plus dev, prod, monitoring and demo overrides; Ollama GPU profile; env-driven config'],
    ['CI', 'Lint, drift checks, 6 test jobs, frontend build, compose smoke test, end-to-end eval gate'],
    ['Security', 'gitleaks secret scan and Trivy dependency/Dockerfile scan on every push; secrets only in .env'],
    ['CD', 'Tag v* builds, scans and publishes every image to GHCR, then cuts a release'],
    ['Monitoring', 'Prometheus + Grafana + Loki, with alert rules and evaluation scores as metrics'],
  ]
  return (
    <div>
      <Title eyebrow="DevOps" sub="Everything below was run for real: images built, stack healthy, pipeline green on GitHub.">
        Built to be shipped
      </Title>
      <div className="grid gap-4 md:grid-cols-3">
        {items.map(([t, d]) => (
          <div key={t} className="panel"><div className="text-xl font-semibold" style={{ color: 'var(--accent)' }}>{t}</div><p className="mt-2 text-lg">{d}</p></div>
        ))}
      </div>
    </div>
  )
}

function SlideCI() {
  const jobs = ['lint-and-drift', 'test: rag', 'test: llm', 'test: ingest', 'test: orchestrator', 'test: eval', 'test: gateway', 'frontend', 'security (gitleaks + Trivy)', 'compose-smoke', 'eval-gate']
  return (
    <div>
      <Title eyebrow="Pipeline" sub="Latest run on main: all 11 jobs passed.">
        What CI checks on every push
      </Title>
      <div className="grid gap-3 md:grid-cols-4">
        {jobs.map((j) => (
          <div key={j} className="panel flex items-center gap-3 !py-3 text-lg">
            <span className="h-3 w-3 rounded-full bg-emerald-500" /> {j}
          </div>
        ))}
      </div>
      <div className="panel mt-6 text-lg">
        <b>Running it for real found real problems:</b> a HIGH vulnerability in a frontend dependency (fixed), Dockerfiles running as root (fixed), a tool-version drift in the linter (pinned), and a wrong script call in the smoke test (fixed).
      </div>
      <a className="btn-primary mt-6 inline-flex" href="https://github.com/IATESPAGHETTI/Code_Origin/actions" target="_blank" rel="noreferrer">Open the Actions page</a>
    </div>
  )
}

function SlideResults() {
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
      <Title eyebrow="Live from the evaluation service" sub={run ? `Run #${run.id}, ${run.config?.split} split, ${run.total} answers, real local models. Overall correctness per mode.` : ''}>
        What the experiment shows so far
      </Title>
      {state.loading && <p className="text-xl muted">Loading results...</p>}
      {(state.none || state.error) && <p className="text-xl muted">No finished evaluation run is available. {state.error}</p>}
      {rep && (
        <>
          <div className="grid gap-4 md:grid-cols-3">
            {rep.models.map((m) => {
              const d = rep.decisions.find((x) => x.model === m)
              return (
                <div key={m} className="panel">
                  <div className="text-xl font-semibold">{m}</div>
                  <div className="mt-3 space-y-2">
                    {modes.map((mo) => {
                      const v = rep.totals[`${m}|${mo}`]?.correctness
                      return (
                        <div key={mo}>
                          <div className="flex justify-between text-base"><span className="font-mono">{mo}</span><b>{pct(v)}</b></div>
                          <div className="h-3 overflow-hidden rounded bg-black/10"><div className="h-full" style={{ width: `${(v || 0) * 100}%`, background: mo === 'code_history' ? 'var(--accent)' : '#9aa0a6' }} /></div>
                        </div>
                      )
                    })}
                  </div>
                  {d && <p className="mt-3 text-base">History vs code-only: <b>{d.history_diff >= 0 ? '+' : ''}{d.history_diff}</b> <span className="muted">({d.verdict})</span></p>}
                </div>
              )
            })}
          </div>
          <p className="mt-6 text-lg muted">Honest reading: a small development split, scored automatically. History raises both 7B models; only llama2 clears the pre-registered rule (codellama has the same effect but a wider interval), and the 3B model barely benefits. It shows the pipeline works. It is not yet a research conclusion.</p>
        </>
      )}
    </div>
  )
}

function SlideHealth() {
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
      <Title eyebrow="Live system check" sub="Asked through the gateway every few seconds.">
        The running stack
      </Title>
      <div className="grid gap-4 md:grid-cols-3">
        {rows.map(([name, ok]) => (
          <div key={name} className="panel flex items-center gap-3 text-xl">
            <span className={`h-4 w-4 rounded-full ${ok == null ? 'bg-slate-400' : ok ? 'bg-emerald-500 live-dot' : 'bg-rose-500'}`} />
            <span className="capitalize">{name}</span>
            <span className="ml-auto text-base muted">{ok == null ? 'checking' : ok ? 'healthy' : 'down'}</span>
          </div>
        ))}
      </div>
      <div className="mt-6 flex flex-wrap gap-3">
        <Link className="btn-primary" to="/ask">Ask a question live</Link>
        <Link className="btn-ghost" to="/repos">Repositories</Link>
        <Link className="btn-ghost" to="/eval">Evaluation</Link>
      </div>
    </div>
  )
}

function SlideLimits() {
  return (
    <div>
      <Title eyebrow="Honest limits" sub="What the evidence does and does not support.">
        What we would do next
      </Title>
      <div className="grid gap-4 md:grid-cols-2 text-lg">
        <div className="panel"><b>Limits</b>
          <ul className="mt-2 list-disc space-y-1 pl-5 muted">
            <li>Evaluated on a seeded demo repository, dev split, automatic scoring.</li>
            <li>The LLM jury is too lenient to trust until compared with human grades.</li>
            <li>Guardrail thresholds rest on very few negative examples.</li>
            <li>Small local models; one GPU with 6 GB.</li>
          </ul>
        </div>
        <div className="panel"><b>Next</b>
          <ul className="mt-2 list-disc space-y-1 pl-5 muted">
            <li>Test on a real repository with 40+ human-verified questions.</li>
            <li>Human-grade about 60 answers; measure judge agreement.</li>
            <li>One held-out run, then the final analysis.</li>
            <li>Publish tagged images through the release pipeline.</li>
          </ul>
        </div>
      </div>
    </div>
  )
}

function SlideEnd() {
  return (
    <div className="flex h-full flex-col justify-center">
      <h2 className="gradient-text text-7xl font-semibold">Questions?</h2>
      <p className="mt-6 text-2xl muted">github.com/IATESPAGHETTI/Code_Origin</p>
      <div className="mt-8 flex gap-3">
        <Link className="btn-primary" to="/ask">Live demo</Link>
        <Link className="btn-ghost" to="/">Exit presentation</Link>
      </div>
    </div>
  )
}

const SLIDES = [
  ['Title', SlideTitle], ['Problem', SlideProblem], ['Research design', SlideResearch], ['Architecture', SlideArchitecture],
  ['Question flow', SlideFlow], ['DevOps', SlideDevOps], ['CI/CD', SlideCI], ['Results', SlideResults],
  ['Live system', SlideHealth], ['Limits', SlideLimits], ['Questions', SlideEnd],
]

/* ------------------------------------------------------------------ shell */

export default function Present() {
  const navigate = useNavigate()
  const initial = () => {
    const n = parseInt(window.location.hash.replace('#', ''), 10)
    return Number.isFinite(n) ? Math.min(Math.max(n - 1, 0), SLIDES.length - 1) : 0
  }
  const [i, setI] = useState(initial)
  const go = useCallback((n) => setI((cur) => Math.min(Math.max(typeof n === 'function' ? n(cur) : n, 0), SLIDES.length - 1)), [])

  useEffect(() => { window.history.replaceState(null, '', `#${i + 1}`) }, [i])
  useEffect(() => {
    const onKey = (e) => {
      if (['ArrowRight', 'PageDown', ' ', 'Enter'].includes(e.key)) { e.preventDefault(); go((c) => c + 1) }
      else if (['ArrowLeft', 'PageUp', 'Backspace'].includes(e.key)) { e.preventDefault(); go((c) => c - 1) }
      else if (e.key === 'Home') go(0)
      else if (e.key === 'End') go(SLIDES.length - 1)
      else if (e.key === 'f' || e.key === 'F') {
        if (document.fullscreenElement) document.exitFullscreen?.()
        else document.documentElement.requestFullscreen?.()
      } else if (e.key === 'Escape' && !document.fullscreenElement) navigate('/')
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [go, navigate])

  const Slide = SLIDES[i][1]
  const label = useMemo(() => SLIDES[i][0], [i])
  return (
    <div className="fixed inset-0 z-50 flex flex-col" style={{ background: 'var(--bg)' }}>
      <div className="flex items-center justify-between px-8 py-4">
        <Link to="/" className="flex items-center gap-2.5" aria-label="Exit presentation">
          <img src="/favicon.svg" alt="" className="h-7 w-7" /><span className="text-lg font-extrabold tracking-tight">CodeOrigin</span>
        </Link>
        <span className="text-sm muted">{label} &middot; {i + 1} / {SLIDES.length}</span>
      </div>
      <main className="min-h-0 flex-1 overflow-y-auto px-8 pb-6 lg:px-20">
        <div key={i} className="page-enter mx-auto h-full max-w-[1500px]">
          <Slide />
        </div>
      </main>
      <div className="flex items-center justify-between px-8 py-4">
        <button className="btn-ghost" onClick={() => go((c) => c - 1)} disabled={i === 0}>&larr; Back</button>
        <div className="flex gap-2" role="tablist" aria-label="Slides">
          {SLIDES.map(([n], k) => (
            <button key={n} role="tab" aria-selected={k === i} aria-label={n} onClick={() => go(k)}
              className="h-2.5 rounded-full transition-all" style={{ width: k === i ? 28 : 10, background: k === i ? 'var(--accent)' : 'rgba(0,0,0,.2)' }} />
          ))}
        </div>
        <button className="btn-primary" onClick={() => go((c) => c + 1)} disabled={i === SLIDES.length - 1}>Next &rarr;</button>
      </div>
      <p className="pb-2 text-center text-xs muted">Arrow keys or space to move &middot; F for full screen &middot; Esc to exit</p>
    </div>
  )
}
