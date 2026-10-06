import { useState } from 'react'
import Recommendations from './Recommendations.jsx'

const pct = (v) => (v == null ? '-' : `${Math.round(v * 100)}%`)
const heat = (v) => (v == null ? {} : { background: `hsl(${Math.round(v * 120)} 70% 45% / 0.2)` })

/**
 * For each category: which model scored highest in `mode`, and whether that is a clear win.
 * "Clear" means the winner's 95% CI lower bound is above the runner-up's upper bound; otherwise it is
 * reported as a tie / too close to call (the demo dataset has only 2-5 questions per category).
 */
export function bestPerCategory(rep, mode) {
  return rep.categories.map((category) => {
    const rows = rep.models
      .map((model) => ({ model, cell: rep.cells[`${model}|${mode}|${category}`] }))
      .filter((r) => r.cell && r.cell.correctness != null)
    if (!rows.length) return { category, rows: [], winners: [], clear: false, n: 0 }
    const top = Math.max(...rows.map((r) => r.cell.correctness))
    const winners = rows.filter((r) => r.cell.correctness === top).map((r) => r.model)
    const rest = rows.filter((r) => r.cell.correctness < top)
    const best = rows.find((r) => r.cell.correctness === top)
    const runnerUpHigh = rest.length ? Math.max(...rest.map((r) => r.cell.correctness_ci?.[1] ?? r.cell.correctness)) : -1
    const lo = best.cell.correctness_ci?.[0] ?? best.cell.correctness
    return { category, rows, winners, clear: winners.length === 1 && rest.length > 0 && lo > runnerUpHigh, n: best.cell.n }
  })
}

/** Models ranked by overall correctness in `mode` (all categories pooled). */
export function rankOverall(rep, mode) {
  return rep.models
    .map((model) => ({ model, t: rep.totals[`${model}|${mode}`] }))
    .filter((r) => r.t && r.t.correctness != null)
    .sort((a, b) => b.t.correctness - a.t.correctness)
}

export default function ModelLeaderboard({ rep }) {
  const modes = rep.modes
  const [mode, setMode] = useState(modes.includes('code_history') ? 'code_history' : modes[0])
  const ranked = rankOverall(rep, mode)
  const topScore = ranked[0]?.t.correctness
  const leaders = ranked.filter((r) => Math.abs(r.t.correctness - topScore) < 0.005).map((r) => r.model)
  const perCat = bestPerCategory(rep, mode)
  const decision = (model) => rep.decisions?.find((d) => d.model === model)

  return (
    <section className="space-y-4">
      <Recommendations rep={rep} />
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Which model is best where</h2>
          <p className="text-sm muted">Correctness per category for the chosen mode. A win is only called clear when its 95% interval sits above the runner-up&rsquo;s.</p>
        </div>
        <div className="flex flex-wrap gap-2" role="group" aria-label="Mode">
          {modes.map((m) => (
            <button key={m} className={m === mode ? 'btn-primary' : 'btn-ghost'} onClick={() => setMode(m)}>{m}</button>
          ))}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {ranked.map((r) => {
          const d = decision(r.model)
          const t = r.t
          return (
            <div key={r.model} className="panel rise">
              <div className="flex items-center justify-between">
                <div className="font-semibold">{r.model}</div>
                {ranked.length > 1 && leaders.includes(r.model) && (
                  <span className="chip" style={{ color: '#047857' }}>{leaders.length > 1 ? 'tied for best' : 'best overall'} in {mode}</span>
                )}
              </div>
              <div className="mt-2 text-4xl font-semibold tracking-tight">{pct(t.correctness)}</div>
              <div className="text-sm muted">overall correctness, 95% CI {pct(t.correctness_ci?.[0])} to {pct(t.correctness_ci?.[1])}</div>
              <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                <dt className="muted">Citation validity</dt><dd>{pct(t.citation_validity)}</dd>
                <dt className="muted">Unsupported claims</dt><dd>{pct(t.unsupported_ratio)}</dd>
                <dt className="muted">Latency</dt><dd>{t.latency_ms == null ? '-' : `${(t.latency_ms / 1000).toFixed(1)} s`}</dd>
                {t.jury_correctness != null && <><dt className="muted">Jury correctness</dt><dd>{pct(t.jury_correctness)}</dd></>}
                {d && <><dt className="muted">History vs code-only</dt><dd>{d.history_diff >= 0 ? '+' : ''}{d.history_diff} <span className="muted">({d.verdict})</span></dd></>}
              </dl>
            </div>
          )
        })}
      </div>

      <div className="panel overflow-x-auto p-0">
        <table className="w-full">
          <thead>
            <tr>
              <th className="th">Category</th>
              {rep.models.map((m) => <th key={m} className="th">{m}</th>)}
              <th className="th">Best</th>
            </tr>
          </thead>
          <tbody>
            {perCat.map((row) => (
              <tr key={row.category} className="border-t" style={{ borderColor: 'var(--line)' }}>
                <td className="td font-mono text-xs">{row.category} <span className="muted">n={row.n}</span></td>
                {rep.models.map((m) => {
                  const cell = rep.cells[`${m}|${mode}|${row.category}`]
                  const win = row.winners.includes(m)
                  return (
                    <td key={m} className="td" style={heat(cell?.correctness)}>
                      {cell ? <span className={win ? 'font-semibold' : ''}>{pct(cell.correctness)}</span> : '-'}
                    </td>
                  )
                })}
                <td className="td text-sm">
                  {!row.winners.length ? '-' : row.clear
                    ? <span className="font-semibold text-emerald-700">{row.winners[0]}</span>
                    : <span className="text-amber-700">{row.winners.length > 1 ? 'tie: ' : 'leads, too close to call: '}{row.winners.join(', ')}</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs muted">Automatic key-fact scoring on this dataset; not human-graded. Small categories give wide intervals, so read &ldquo;too close to call&rdquo; literally.</p>
    </section>
  )
}
