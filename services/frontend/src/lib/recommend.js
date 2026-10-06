// Plain-language "use model X for Y" guidance computed from an evaluation report.
// Every line carries its confidence: categories are small, so a tie or a slight edge is reported as such,
// never as a win.

const GROUP = {
  design_rationale: 'history', bug_origin: 'history', change_attribution: 'history', issue_linkage: 'history', evolution: 'history',
  current_state: 'control', unanswerable: 'guardrail', off_topic: 'guardrail', adversarial: 'guardrail',
}

const pct = (v) => `${Math.round(v * 100)}%`

/** mean of a metric over the categories of one group, weighted by question count */
function pooled(rep, model, mode, group, key) {
  let num = 0
  let den = 0
  rep.categories.forEach((c) => {
    if (GROUP[c] !== group) return
    const cell = rep.cells[`${model}|${mode}|${c}`]
    if (!cell || cell[key] == null) return
    num += cell[key] * cell.n
    den += cell.n
  })
  return den ? num / den : null
}

/**
 * Best model(s) for one value per model. 'tie' = within 2% of the best, 'clear' = at least a 10% lead
 * over the next model, otherwise 'slight'. `better` is 'high' or 'low'.
 */
export function pick(values, better) {
  const ok = values.filter((x) => x.v != null)
  if (!ok.length) return { winners: [], confidence: 'none' }
  const sign = better === 'high' ? -1 : 1
  const sorted = [...ok].sort((a, b) => sign * (a.v - b.v))
  const best = sorted[0].v
  const scale = better === 'low' && best > 1 ? best : 1 // latency is in ms, ratios are 0..1
  const winners = sorted.filter((x) => Math.abs(x.v - best) <= 0.02 * scale).map((x) => x.model)
  const rest = sorted.find((x) => !winners.includes(x.model))
  const lead = rest ? Math.abs(rest.v - best) : Infinity
  const confidence = winners.length > 1 ? 'tie' : lead >= 0.1 * scale ? 'clear' : 'slight'
  return { winners, confidence }
}

export function recommendations(rep) {
  const hist = rep.modes.includes('code_history') ? 'code_history' : null
  if (!hist || rep.models.length < 2) return [] // nothing to compare with a single model
  const codeMode = rep.modes.includes('code_only') ? 'code_only' : hist
  const models = rep.models
  const tot = (m, key) => rep.totals[`${m}|${hist}`]?.[key] ?? null
  const items = []
  const add = (id, label, mode, vals, better, fmt, note = '') => {
    const { winners, confidence } = pick(vals, better)
    items.push({ id, label, mode, winners, confidence, values: vals.map((x) => ({ model: x.model, text: x.v == null ? '-' : fmt(x.v) })), note })
  }

  add('history', 'Why was it built this way? (history questions)', hist,
    models.map((m) => ({ model: m, v: pooled(rep, m, hist, 'history', 'correctness') })), 'high', pct)
  add('code', 'What does this code do today? (current-code questions)', codeMode,
    models.map((m) => ({ model: m, v: pooled(rep, m, codeMode, 'control', 'correctness') })), 'high', pct, 'Based on very few questions.')
  add('refuse', 'Declining off-topic, unanswerable or unsafe questions', hist,
    models.map((m) => ({ model: m, v: pooled(rep, m, hist, 'guardrail', 'correctness') })), 'high', pct,
    'Mostly enforced by the guardrails in code, so models usually tie here.')
  add('honest', 'Fewest unsupported claims (most trustworthy)', hist,
    models.map((m) => ({ model: m, v: tot(m, 'unsupported_ratio') })), 'low', pct)
  add('cite', 'Cites the real evidence', hist,
    models.map((m) => ({ model: m, v: tot(m, 'gold_cited') })), 'high', pct, 'Share of answers that cite the gold evidence. Most models rarely cite in the requested format; this is a real weakness, not a counting artefact.')

  // fastest, but only among models that are accurate enough: a fast wrong answer is not a recommendation
  const hv = models.map((m) => ({ model: m, v: pooled(rep, m, hist, 'history', 'correctness') }))
  const topH = Math.max(...hv.map((x) => x.v ?? 0))
  const good = new Set(hv.filter((x) => (x.v ?? 0) >= 0.8 * topH).map((x) => x.model))
  const lat = models.map((m) => ({ model: m, v: tot(m, 'latency_ms') }))
  const { winners: fastGood, confidence } = pick(lat.filter((x) => good.has(x.model)), 'low')
  const { winners: fastAny } = pick(lat, 'low')
  items.push({
    id: 'fast', label: 'Fastest answers (among models that are accurate enough)', mode: hist, winners: fastGood, confidence,
    values: lat.map((x) => ({ model: x.model, text: x.v == null ? '-' : `${(x.v / 1000).toFixed(1)} s` })),
    note: fastAny.some((m) => !good.has(m)) ? `${fastAny.join(', ')} is faster but is not accurate enough on history questions.` : '',
  })
  return items
}
