import { describe, expect, it } from 'vitest'
import { pick, recommendations } from './recommend.js'

const c = (v, n = 4) => ({ correctness: v, n })
const rep = {
  models: ['big', 'small'],
  modes: ['code_only', 'code_history'],
  categories: ['design_rationale', 'current_state', 'off_topic'],
  cells: {
    'big|code_history|design_rationale': c(0.9), 'small|code_history|design_rationale': c(0.3),
    'big|code_only|current_state': c(1), 'small|code_only|current_state': c(1),
    'big|code_history|off_topic': c(1), 'small|code_history|off_topic': c(1),
  },
  totals: {
    'big|code_history': { unsupported_ratio: 0.3, gold_cited: 0.2, latency_ms: 9000 },
    'small|code_history': { unsupported_ratio: 0.6, gold_cited: 0, latency_ms: 800 },
  },
}
const by = Object.fromEntries(recommendations(rep).map((r) => [r.id, r]))

describe('pick', () => {
  it('calls a tie within 2%', () => expect(pick([{ model: 'a', v: 0.91 }, { model: 'b', v: 0.9 }], 'high').confidence).toBe('tie'))
  it('calls a slight edge for a small lead', () => expect(pick([{ model: 'a', v: 0.8 }, { model: 'b', v: 0.74 }], 'high').confidence).toBe('slight'))
  it('works for lower-is-better values and ignores missing ones', () => {
    const r = pick([{ model: 'a', v: 0.6 }, { model: 'b', v: 0.3 }, { model: 'c', v: null }], 'low')
    expect(r.winners).toEqual(['b'])
    expect(r.confidence).toBe('clear')
  })
  it('handles no data', () => expect(pick([{ model: 'a', v: null }], 'high').confidence).toBe('none'))
})

describe('recommendations', () => {
  it('names a clear winner for history questions', () => {
    expect(by.history.winners).toEqual(['big'])
    expect(by.history.confidence).toBe('clear')
  })
  it('reports ties instead of inventing a winner', () => {
    expect([...by.code.winners].sort()).toEqual(['big', 'small'])
    expect(by.code.confidence).toBe('tie')
    expect(by.refuse.confidence).toBe('tie')
  })
  it('prefers fewer unsupported claims', () => expect(by.honest.winners).toEqual(['big']))
  it('does not recommend a fast model that is too inaccurate', () => {
    expect(by.fast.winners).toEqual(['big'])
    expect(by.fast.note).toMatch(/small is faster/)
  })
  it('gives no verdicts for a single-model run', () => {
    expect(recommendations({ ...rep, models: ['big'] })).toEqual([])
  })
  it('returns nothing without a code_history run', () => {
    expect(recommendations({ ...rep, modes: ['code_only'] })).toEqual([])
  })
})
