import { useEffect, useRef, useState } from 'react'

const reduced = () => typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

/** true once the element has scrolled into view (one-shot). */
export function useInView(options = { threshold: 0.15 }) {
  const ref = useRef(null)
  const [seen, setSeen] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el) return undefined
    if (seen || reduced() || typeof IntersectionObserver === 'undefined') { setSeen(true); return undefined }
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setSeen(true); io.disconnect() } }, options)
    io.observe(el)
    return () => io.disconnect()
  }, [seen, options])
  return [ref, seen]
}

/** Fades and lifts its children into place when scrolled into view. `delay` staggers siblings. */
export function Reveal({ children, delay = 0, className = '', as: Tag = 'div' }) {
  const [ref, seen] = useInView()
  return <Tag ref={ref} className={`reveal ${seen ? 'in' : ''} ${className}`} style={{ '--d': `${delay}ms` }}>{children}</Tag>
}

/** Counts from 0 to `to` when scrolled into view. */
export function CountUp({ to, duration = 1400, suffix = '' }) {
  const [ref, seen] = useInView()
  const [n, setN] = useState(reduced() ? to : 0)
  useEffect(() => {
    if (!seen || reduced()) { if (seen) setN(to); return undefined }
    let raf
    const t0 = performance.now()
    const tick = (t) => {
      const p = Math.min(1, (t - t0) / duration)
      setN(Math.round(to * (1 - Math.pow(1 - p, 3))))
      if (p < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [seen, to, duration])
  return <span ref={ref}>{n}{suffix}</span>
}

/** Soft animated gradient blobs behind a section. */
export function Aurora({ className = '' }) {
  return (
    <div aria-hidden="true" className={`pointer-events-none absolute inset-0 -z-10 overflow-hidden ${className}`}>
      <div className="blob blob-a -left-24 -top-24 h-[420px] w-[420px]" />
      <div className="blob blob-b right-[-80px] top-10 h-[380px] w-[380px]" />
      <div className="blob blob-c bottom-[-120px] left-1/3 h-[340px] w-[340px]" />
    </div>
  )
}


/** Eases from the previous value to the new one, so live counters visibly tick up. */
export function AnimatedNumber({ value, duration = 500 }) {
  const [shown, setShown] = useState(value)
  const from = useRef(value)
  useEffect(() => {
    if (reduced()) { setShown(value); from.current = value; return undefined }
    const start = from.current
    const t0 = performance.now()
    let raf
    const tick = (t) => {
      const p = Math.min(1, (t - t0) / duration)
      const v = Math.round(start + (value - start) * (1 - Math.pow(1 - p, 3)))
      setShown(v)
      from.current = v
      if (p < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [value, duration])
  return <span>{shown.toLocaleString()}</span>
}

/** Reveals text word by word. `enabled=false` shows it immediately. */
export function Typewriter({ text, enabled = true, wordsPerSecond = 28, onDone }) {
  const words = (text || '').split(' ')
  const [n, setN] = useState(enabled && !reduced() ? 0 : words.length)
  useEffect(() => {
    if (!enabled || reduced()) { setN(words.length); onDone?.(); return undefined }
    setN(0)
    const id = setInterval(() => {
      setN((c) => {
        if (c + 1 >= words.length) { clearInterval(id); onDone?.(); return words.length }
        return c + 1
      })
    }, 1000 / wordsPerSecond)
    return () => clearInterval(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text, enabled])
  return <>{words.slice(0, n).join(' ')}{n < words.length && <span className="caret" />}</>
}
