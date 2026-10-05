import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError, sse, MODES } from './api'

const streamOf = (chunks) => {
  const enc = new TextEncoder()
  return new ReadableStream({ start(c) { chunks.forEach((x) => c.enqueue(enc.encode(x))); c.close() } })
}

afterEach(() => vi.restoreAllMocks())

describe('sse', () => {
  it('parses named events even when a block is split across network chunks', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, body: streamOf(['event: stage\nda', 'ta: {"n":1}\n\nevent: done\ndata: {"n":2}\n\n']) })))
    const seen = []
    await sse('/x', {}, async (name, data) => seen.push([name, data]))
    expect(seen).toEqual([['stage', { n: 1 }], ['done', { n: 2 }]])
  })

  it('skips malformed JSON instead of aborting the stream', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, body: streamOf(['data: {oops\n\ndata: {"ok":true}\n\n']) })))
    const seen = []
    await sse('/x', {}, (n, d) => seen.push(d))
    expect(seen).toEqual([{ ok: true }])
  })

  it('throws ApiError carrying the server detail', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 429, statusText: 'x', json: async () => ({ detail: 'slow down' }) })))
    await expect(sse('/x', {}, () => {})).rejects.toMatchObject({ status: 429, message: 'slow down' })
  })
})

describe('api', () => {
  it('encodes repo ids in paths', async () => {
    const f = vi.fn(async () => ({ ok: true, json: async () => ({}) }))
    vi.stubGlobal('fetch', f)
    await api.deleteRepo('a/b c')
    expect(f.mock.calls[0][0]).toBe('/api/repos/a%2Fb%20c')
    expect(f.mock.calls[0][1].method).toBe('DELETE')
  })

  it('wraps failures in ApiError', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 400, statusText: 'Bad', json: async () => ({ detail: 'nope' }) })))
    await expect(api.repos()).rejects.toBeInstanceOf(ApiError)
  })
})

it('compares exactly the three retrieval modes in the UI', () => {
  expect(MODES.map((m) => m.id)).toEqual(['no_context', 'code_only', 'code_history'])
})
