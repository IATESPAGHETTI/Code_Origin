import { useEffect, useState } from 'react'

const QUESTION = 'Why was session-cookie auth replaced with JWT?'
const ANSWER =
  'Session fixation allowed account takeover, so authentication moved to short-lived signed tokens. HS256 was chosen because it is a single service with no external verifiers.'
const REFS = [
  { label: 'Session fixation allows account takeover', tag: 'issue #7', c: '#d97706' },
  { label: 'Move authentication to short-lived JWT', tag: 'PR #8', c: '#7c3aed' },
  { label: 'Replace session cookies with JWT', tag: 'commit 69e7bbd', c: '#0284c7' },
]
const STEPS = ['Safety', 'Retrieve', 'Gate', 'Context', 'Generate', 'Verify']
const HITS = [
  { ref: 'Replace session cookies with JWT', tag: 'commit 69e7bbd', v: 0.86, b: 0.74, c: '#0284c7' },
  { ref: 'Session fixation allows takeover', tag: 'issue #7', v: 0.71, b: 0.62, c: '#d97706' },
  { ref: 'Move auth to short-lived JWT', tag: 'PR #8', v: 0.64, b: 0.51, c: '#7c3aed' },
]
const GUARDS = ['G1 on-topic', 'G3 citations valid', 'G4 grounded', 'G5 injection-safe']

const prefersReduced = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

/** A self-playing run of the real pipeline: the steps light up in order as the answer is produced. */
export default function HeroDemo() {
  const [step, setStep] = useState(-1)   // index into STEPS currently running
  const [q, setQ] = useState(0)
  const [a, setA] = useState(0)
  const [refs, setRefs] = useState(0)
  const [guards, setGuards] = useState(0)
  const [cycle, setCycle] = useState(0)

  useEffect(() => {
    if (prefersReduced()) { setStep(STEPS.length); setQ(QUESTION.length); setA(ANSWER.length); setRefs(REFS.length); setGuards(GUARDS.length); return undefined }
    let cancelled = false
    const timers = []
    const at = (ms, fn) => timers.push(setTimeout(() => !cancelled && fn(), ms))
    setStep(-1); setQ(0); setA(0); setRefs(0); setGuards(0)
    let t = 500
    for (let i = 1; i <= QUESTION.length; i++) { at(t, () => setQ(i)); t += 24 }
    t += 300
    ;[0, 1, 2, 3].forEach((s) => { at(t, () => setStep(s)); t += s === 1 ? 900 : 520 })
    at(t, () => setStep(4)); t += 400
    for (let i = 1; i <= ANSWER.length; i += 2) { at(t, () => setA(Math.min(i + 1, ANSWER.length))); t += 20 }
    at(t, () => setStep(5)); t += 250
    REFS.forEach((_, i) => { at(t, () => setRefs(i + 1)); t += 240 })
    GUARDS.forEach((_, i) => { at(t, () => setGuards(i + 1)); t += 200 })
    at(t, () => setStep(6))
    at(t + 5000, () => setCycle((c) => c + 1))
    return () => { cancelled = true; timers.forEach(clearTimeout) }
  }, [cycle])

  return (
    <div className="panel refract overflow-hidden !p-0 text-left" role="img" aria-label="Animated example of CodeOrigin answering a question">
      <div className="flex items-center gap-2 border-b px-4 py-2.5" style={{ borderColor: 'var(--line)' }}>
        <span className="h-2.5 w-2.5 rounded-full bg-[#ff5f57]" /><span className="h-2.5 w-2.5 rounded-full bg-[#febc2e]" /><span className="h-2.5 w-2.5 rounded-full bg-[#28c840]" />
        <span className="ml-3 font-mono text-xs muted">codeorigin / local__repo</span>
        <span className="ml-auto flex items-center gap-1.5 text-xs muted"><span className="live-dot h-1.5 w-1.5 rounded-full bg-emerald-500" />live pipeline</span>
      </div>

      <div className="grid gap-0 lg:grid-cols-[1.15fr_1fr]">
        <div className="space-y-4 p-5">
          <div className="font-mono text-sm">
            <span className="mr-2" style={{ color: 'var(--accent)' }}>&rsaquo;</span>
            <span className={a === 0 ? 'caret' : ''}>{QUESTION.slice(0, q)}</span>
          </div>
          <p className={`min-h-[104px] text-[0.9375rem] leading-relaxed ${a > 0 && a < ANSWER.length ? 'caret' : ''}`} style={{ color: 'var(--text)' }}>{ANSWER.slice(0, a)}</p>
          <div className="flex min-h-[24px] flex-wrap gap-1.5">
            {REFS.slice(0, refs).map((r) => (
              <span key={r.label + cycle} className="pop inline-flex items-center gap-2 rounded-xl px-2.5 py-1 text-[0.8125rem]" style={{ background: 'rgba(0,0,0,.045)', boxShadow: 'inset 0 0 0 1px rgba(0,0,0,.07)' }}>
                <span className="h-2 w-2 rounded-full" style={{ background: r.c }} /><span className="font-medium">{r.label}</span><span className="font-mono text-xs muted">{r.tag}</span>
              </span>))}
          </div>
          <div className="flex min-h-[24px] flex-wrap gap-1.5">
            {GUARDS.slice(0, guards).map((g) => <span key={g + cycle} className="chip pop muted"><span className="mr-1 text-emerald-600">&#10003;</span>{g}</span>)}
          </div>
        </div>

        <div className="border-t p-5 lg:border-l lg:border-t-0" style={{ borderColor: 'var(--line)', background: 'rgba(255,255,255,.35)' }}>
          <ol className="mb-4 flex flex-wrap gap-1.5">
            {STEPS.map((s, i) => (
              <li key={s} className="rounded-md border px-2 py-0.5 text-xs transition-all duration-300"
                style={{
                  borderColor: i === step ? 'var(--accent)' : 'var(--line)',
                  background: i < step ? 'rgba(26,157,75,.10)' : i === step ? 'var(--accent-soft)' : 'transparent',
                  color: i < step ? '#1a9d4b' : i === step ? 'var(--accent)' : 'var(--muted)',
                }}>
                {i < step ? '✓ ' : ''}{s}
              </li>
            ))}
          </ol>
          <div className="space-y-3">
            {HITS.map((h, i) => (
              <div key={h.ref} className={`transition-all duration-500 ${step >= 1 ? 'translate-y-0 opacity-100' : 'translate-y-2 opacity-0'}`} style={{ transitionDelay: `${i * 120}ms` }}>
                <div className="flex items-baseline justify-between gap-2 text-[0.8125rem]"><span className="min-w-0 truncate font-medium">{h.ref}<span className="ml-2 font-mono text-xs muted">{h.tag}</span></span><span className="text-xs muted">{h.v.toFixed(2)}</span></div>
                <div className="mt-1 h-1 overflow-hidden rounded-full bg-black/10">
                  <div className="h-full rounded-full transition-all duration-1000 ease-out" style={{ width: step >= 1 ? `${h.v * 100}%` : '0%', background: h.c, transitionDelay: `${i * 120}ms` }} />
                </div>
                <div className="mt-1 h-1 overflow-hidden rounded-full bg-black/10">
                  <div className="h-full rounded-full bg-black/35 transition-all duration-1000 ease-out" style={{ width: step >= 1 ? `${h.b * 100}%` : '0%', transitionDelay: `${i * 120 + 80}ms` }} />
                </div>
              </div>
            ))}
          </div>
          <p className="mt-4 font-mono text-xs muted">vector similarity / BM25 keywords</p>
        </div>
      </div>
    </div>
  )
}
