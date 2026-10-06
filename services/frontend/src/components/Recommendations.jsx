import { recommendations } from '../lib/recommend.js'

const BADGE = {
  clear: ['clear winner', '#047857'],
  slight: ['slight edge', '#b45309'],
  tie: ['tie', '#475569'],
  none: ['no data', '#64748b'],
}

/** "Which model should I use for what?" in plain words, from the same numbers as the tables below it. */
export default function Recommendations({ rep }) {
  const items = recommendations(rep)
  if (rep.models.length < 2) {
    return (
      <div className="panel">
        <h2 className="text-lg font-semibold">Which model should I use for what?</h2>
        <p className="mt-1 text-sm muted">This run tested a single model ({rep.models[0]}), so there is nothing to compare. Open a run with several models, or start one, to get recommendations.</p>
      </div>
    )
  }
  if (!items.length) return null
  return (
    <div className="panel space-y-1">
      <h2 className="text-lg font-semibold">Which model should I use for what?</h2>
      <p className="text-sm muted">
        A plain-language summary of this run. A tie or a slight edge means the data cannot separate the models yet; small question sets give wide intervals.
      </p>
      <div className="mt-2 divide-y" style={{ borderColor: 'var(--line)' }}>
        {items.map((it) => {
          const [badge, color] = BADGE[it.confidence] || BADGE.none
          return (
            <div key={it.id} className="grid gap-2 py-3 md:grid-cols-[1.4fr_1fr_1.6fr] md:items-center">
              <div>
                <div className="font-medium">{it.label}</div>
                <div className="text-xs muted">scored in <span className="font-mono">{it.mode}</span> mode</div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {it.winners.map((w) => <span key={w} className="chip" style={{ color: 'var(--accent)', fontWeight: 600 }}>{w}</span>)}
                <span className="text-xs font-semibold" style={{ color }}>{badge}</span>
              </div>
              <div className="text-sm">
                {it.values.map((v, i) => (
                  <span key={v.model} className={it.winners.includes(v.model) ? 'font-semibold' : 'muted'}>{i ? ' · ' : ''}{v.model} {v.text}</span>
                ))}
                {it.note && <div className="text-xs muted">{it.note}</div>}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
