import { Link } from 'react-router-dom'
import { CountUp, Reveal } from '../components/motion.jsx'
import HeroDemo from '../components/HeroDemo.jsx'
import EvidenceChain from '../components/EvidenceChain.jsx'

const TICKER = [
  ['commit', 'Replace session cookies with JWT'], ['issue', 'Session fixation allows account takeover'], ['pr', 'Move authentication to short-lived JWT'],
  ['commit', 'Add rate limiter to login endpoint'], ['issue', 'Brute-force attempts against /login'], ['pr', 'Throttle failed logins'],
  ['commit', 'Introduce Decimal money type'], ['issue', 'Ledger balances drift by fractions of a cent'],
  ['commit', 'Revert: cache invoice totals in memory'], ['issue', 'Invoice export shows stale totals after refunds'],
  ['commit', 'Move gateway key to environment variable'], ['issue', 'Live gateway key was committed in config.py'],
  ['commit', 'Raise JWT TTL from 15 to 60 minutes'], ['pr', 'Raise JWT TTL to 60 minutes'],
]
const DOT = { commit: '#0284c7', issue: '#d97706', pr: '#7c3aed' }

const GUARDS = [
  ['G1', 'Off-topic refusal', 'Decided from retrieval scores, never by trusting a small model to refuse.'],
  ['G2', 'No evidence, no answer', 'History questions with no supporting commit, issue or PR are declined.'],
  ['G3', 'Citation enforcement', 'Every cited ref is checked against what was retrieved. Invented ones are stripped.'],
  ['G4', 'Claim grounding', 'Sentences the evidence does not support are flagged as likely hallucination.'],
  ['G5', 'Injection defence', 'Commit messages and issues are untrusted data. Instruction-like text is neutralised.'],
  ['G6', 'Secret redaction', 'Keys and tokens in old diffs are redacted before indexing and again on output.'],
]

const STATS = [
  { to: 3, label: 'modes compared head to head' },
  { to: 9, label: 'question categories' },
  { to: 10, label: 'guardrails, enforced in code' },
  { to: 95, suffix: '%', label: 'confidence intervals on every result' },
]

const I = (d) => (
  <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{d}</svg>
)
const ICONS = {
  git: I(<><circle cx="6" cy="6" r="2.2" /><circle cx="6" cy="18" r="2.2" /><circle cx="18" cy="9" r="2.2" /><path d="M6 8.2v7.6M18 11.2c0 3-6 2-12 5" /></>),
  search: I(<><circle cx="11" cy="11" r="6.5" /><path d="m20 20-4-4" /></>),
  chart: I(<path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />),
  pulse: I(<path d="M3 12h4l2-6 4 12 2-6h6" />),
}

function Bento({ icon, title, children, className = '', delay = 0 }) {
  return (
    <Reveal delay={delay} className={className}>
      <div className="panel lift h-full !p-7">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl" style={{ background: 'var(--accent-soft)', color: 'var(--accent)' }}>{ICONS[icon]}</div>
        <h3 className="mt-5 text-lg font-semibold">{title}</h3>
        <div className="mt-2 text-[0.9375rem] leading-relaxed muted">{children}</div>
      </div>
    </Reveal>
  )
}

export default function Home() {
  return (
    <div className="space-y-36 pt-10">
      {/* ---- hero: copy on the left, live product window on the right ---- */}
      <section className="grid items-center gap-10 lg:grid-cols-[0.82fr_1.3fr]">
        <div>
          <Link to="/eval" className="rise panel !rounded-full inline-flex items-center gap-2 !px-3.5 !py-1.5 text-xs" style={{ '--d': '0ms' }}>
            <span className="live-dot h-1.5 w-1.5 rounded-full bg-emerald-500" />
            <span className="muted">Pre-registered evaluation with per-category results</span>
            <span style={{ color: 'var(--accent)' }}>&rarr;</span>
          </Link>
          <h1 className="rise mt-7 text-5xl font-semibold leading-[1.03] sm:text-6xl xl:text-7xl" style={{ '--d': '100ms' }}>
            <span className="gradient-text">Know </span><span className="live-color">why</span><span className="gradient-text"> your code looks the way it does.</span>
          </h1>
          <p className="rise mt-7 max-w-xl text-xl leading-relaxed muted" style={{ '--d': '220ms' }}>
            Code shows what a system is. The reasons live in commits, issues, pull requests and reviews.
            CodeOrigin finds them and answers with citations you can open.
          </p>
          <div className="rise mt-10 flex flex-wrap items-center gap-3" style={{ '--d': '340ms' }}>
            <Link to="/ask" className="btn-primary !px-6 !py-3 !text-[0.9375rem]">Ask a question</Link>
            <Link to="/repos" className="btn-ghost !px-6 !py-3 !text-[0.9375rem]">Index a repository</Link>
          </div>
        </div>
        <div className="rise" style={{ '--d': '420ms' }}><HeroDemo /></div>
      </section>

      <Reveal as="section">
        <div className="fade-edges overflow-hidden" aria-hidden="true">
          <div className="ticker py-1">
            {[...TICKER, ...TICKER].map(([k, t], i) => (
              <span key={i} className="mr-3 inline-flex items-center gap-2 whitespace-nowrap rounded-xl px-3 py-1.5 text-[0.8125rem]" style={{ background: 'rgba(255,255,255,.7)', boxShadow: '0 0 0 1px rgba(0,0,0,.07)' }}>
                <span className="h-2 w-2 rounded-full" style={{ background: DOT[k] }} /><span className="muted">{k}</span><span className="font-medium">{t}</span>
              </span>))}
          </div>
        </div>
      </Reveal>

      {/* ---- bento ---- */}
      <section>
        <Reveal><p className="eyebrow">What it does</p></Reveal>
        <Reveal delay={60}><h2 className="gradient-text mt-3 max-w-2xl text-4xl font-semibold leading-tight sm:text-5xl">The history of a codebase, made answerable.</h2></Reveal>
        <div className="mt-14 grid gap-5 md:grid-cols-6">
          <Bento icon="git" title="Reads everything git remembers" className="md:col-span-2" delay={0}>
            Commits, diffs, issues, pull requests, reviews and releases, cross-linked at ingest so one hit brings the rest of the story.
          </Bento>
          <Bento icon="search" title="Retrieval you can inspect" className="md:col-span-2" delay={80}>
            Embeddings plus BM25, so exact SHAs and issue numbers still match. Every score is visible, per chunk.
          </Bento>
          <Bento icon="pulse" title="Watch the pipeline run" className="md:col-span-2" delay={160}>
            Each answer streams its stages live: scores, gate decisions, the context it built, citation and grounding checks.
          </Bento>
          <Reveal delay={60} className="md:col-span-4">
            <div className="panel lift h-full !p-7">
              <h3 className="text-lg font-semibold">A chain of evidence, not a snippet</h3>
              <p className="mt-2 max-w-xl text-[0.9375rem] muted">Follow a decision from the original report to the code that exists today.</p>
              <div className="mt-6"><EvidenceChain /></div>
            </div>
          </Reveal>
          <Bento icon="chart" title="Measured, not asserted" className="md:col-span-2" delay={140}>
            The same questions in three modes, scored per category with confidence intervals and a decision rule fixed before the run.
          </Bento>
        </div>
      </section>

      {/* ---- guardrails ---- */}
      <section>
        <Reveal><p className="eyebrow">Guardrails</p></Reveal>
        <Reveal delay={60}><h2 className="gradient-text mt-3 max-w-2xl text-4xl font-semibold leading-tight sm:text-5xl">Enforced in code, not by asking nicely.</h2></Reveal>
        <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {GUARDS.map(([id, t, d], i) => (
            <Reveal key={id} delay={(i % 3) * 80}>
              <div className="panel lift h-full !p-6">
                <div className="flex items-center justify-between">
                  <h3 className="text-base font-semibold">{t}</h3>
                  <span className="chip" style={{ color: 'var(--accent)' }}>{id}</span>
                </div>
                <p className="mt-2.5 text-[0.9375rem] leading-relaxed muted">{d}</p>
              </div>
            </Reveal>
          ))}
        </div>
        <div className="mt-6 grid grid-cols-2 gap-5 md:grid-cols-4">
          {STATS.map((s, i) => (
            <Reveal key={s.label} delay={i * 80}>
              <div className="panel text-center !py-7">
                <div className="gradient-text text-5xl font-semibold"><CountUp to={s.to} suffix={s.suffix || ''} /></div>
                <div className="mt-2 text-xs muted">{s.label}</div>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ---- cta ---- */}
      <Reveal as="section">
        <div className="panel glass-strong relative overflow-hidden !p-16 text-center">
          <div aria-hidden="true" className="pointer-events-none absolute inset-0" style={{ background: 'radial-gradient(60% 90% at 50% 130%, rgba(0,113,227,.20), transparent 70%)' }} />
          <h2 className="gradient-text relative mx-auto max-w-2xl text-4xl font-semibold leading-tight sm:text-5xl">Ask the question the code can&rsquo;t answer.</h2>
          <p className="relative mx-auto mt-5 max-w-xl text-lg muted">Index a repository, ask why, and open the evidence behind every claim.</p>
          <div className="relative mt-9 flex justify-center gap-3">
            <Link to="/repos" className="btn-primary !px-6 !py-3 !text-[0.9375rem]">Index a repository</Link>
            <Link to="/ask" className="btn-ghost !px-6 !py-3 !text-[0.9375rem]">Ask something</Link>
          </div>
        </div>
      </Reveal>
    </div>
  )
}
