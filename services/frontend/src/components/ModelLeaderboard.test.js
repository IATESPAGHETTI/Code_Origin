import { describe, expect, it } from 'vitest'
import { bestPerCategory, rankOverall } from './ModelLeaderboard.jsx'

const cell = (c, lo, hi, n = 4) => ({ correctness: c, correctness_ci: [lo, hi], n })
const rep = {
  models: ['a', 'b'],
  categories: ['x', 'y', 'z'],
  cells: {
    'a|m|x': cell(1, 1, 1), 'b|m|x': cell(0.25, 0, 0.5),      // clear win for a
    'a|m|y': cell(0.5, 0, 1), 'b|m|y': cell(0.25, 0, 0.5),    // a leads but CIs overlap
    'a|m|z': cell(0.5, 0, 1), 'b|m|z': cell(0.5, 0, 1),       // tie
  },
  totals: { 'a|m': { correctness: 0.7 }, 'b|m': { correctness: 0.3 } },
}

describe('bestPerCategory', () => {
  const r = bestPerCategory(rep, 'm')
  it('calls a clear win only when the winner CI is above the runner-up CI', () => {
    expect(r[0]).toMatchObject({ winners: ['a'], clear: true })
    expect(r[1]).toMatchObject({ winners: ['a'], clear: false })
  })
  it('reports ties', () => expect(r[2].winners).toEqual(['a', 'b']))
  it('handles a mode nobody ran', () => expect(bestPerCategory(rep, 'none')[0].winners).toEqual([]))
})

it('ranks models by overall correctness', () => {
  expect(rankOverall(rep, 'm').map((x) => x.model)).toEqual(['a', 'b'])
})
