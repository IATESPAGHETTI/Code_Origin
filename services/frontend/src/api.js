// Thin client for the gateway. Same-origin in production (nginx proxies /api),
// proxied by Vite in dev, or pointed at another host with VITE_API_URL.
const BASE = import.meta.env.VITE_API_URL || ''
const KEY = import.meta.env.VITE_API_KEY || ''

export class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === 'string' ? detail : JSON.stringify(detail))
    this.status = status
  }
}

const headers = (body) => ({ ...(body ? { 'Content-Type': 'application/json' } : {}), ...(KEY ? { 'X-API-Key': KEY } : {}) })

async function req(path, { method = 'GET', body, text = false } = {}) {
  const res = await fetch(`${BASE}${path}`, { method, headers: headers(body), body: body ? JSON.stringify(body) : undefined })
  if (!res.ok) {
    let detail = res.statusText
    try { detail = (await res.json()).detail ?? detail } catch { /* not json */ }
    throw new ApiError(res.status, detail)
  }
  return text ? res.text() : res.json()
}

/**
 * Server-Sent Events over fetch (so POST bodies and the API-key header work, which EventSource cannot do).
 * `onEvent(name, data)` is awaited per event: returning a promise applies back-pressure, which is how the UI
 * paces stages in slow motion.
 */
export async function sse(path, { method = 'GET', body, signal } = {}, onEvent) {
  const res = await fetch(`${BASE}${path}`, { method, headers: headers(body), body: body ? JSON.stringify(body) : undefined, signal })
  if (!res.ok) {
    let detail = res.statusText
    try { detail = (await res.json()).detail ?? detail } catch { /* not json */ }
    throw new ApiError(res.status, detail)
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const blocks = buf.split('\n\n')
    buf = blocks.pop()
    for (const block of blocks) {
      let name = 'message'
      let data = ''
      for (const line of block.split('\n')) {
        if (line.startsWith('event:')) name = line.slice(6).trim()
        else if (line.startsWith('data:')) data += line.slice(5).trim()
      }
      if (!data) continue
      let parsed
      try { parsed = JSON.parse(data) } catch { continue }
      await onEvent(name, parsed)
    }
  }
}

export const api = {
  healthAll: () => req('/api/health/all'),
  config: () => req('/api/config'),
  repos: () => req('/api/repos'),
  addRepo: (b) => req('/api/repos', { method: 'POST', body: b }),
  deleteRepo: (id) => req(`/api/repos/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  syncRepo: (id) => req(`/api/repos/${encodeURIComponent(id)}/sync`, { method: 'POST' }),
  job: (id) => req(`/api/jobs/${id}`),
  jobStream: (id, onEvent, signal) => sse(`/api/jobs/${id}/events`, { signal }, onEvent),
  ask: (b) => req('/api/ask', { method: 'POST', body: b }),
  askStream: (b, onEvent, signal) => sse('/api/ask/stream', { method: 'POST', body: b, signal }, onEvent),
  evidence: (repo, ref) => req(`/api/evidence/${encodeURIComponent(repo)}/${encodeURIComponent(ref)}`),
  evalDatasets: () => req('/api/eval/datasets'),
  evalStart: (b) => req('/api/eval/runs', { method: 'POST', body: b }),
  evalRuns: () => req('/api/eval/runs'),
  evalRun: (id) => req(`/api/eval/runs/${id}`),
  evalReport: (id) => req(`/api/eval/runs/${id}/report`, { text: true }),
}

export const MODES = [
  { id: 'no_context', label: 'No context', hint: 'Question only: what the model knows by itself' },
  { id: 'code_only', label: 'Code only', hint: 'Current source code and docs' },
  { id: 'code_history', label: 'Code + history', hint: 'Code plus commits, diffs, issues, PRs and reviews' },
]

export const REFUSAL_LABEL = {
  off_topic: 'Off-topic (G1)',
  insufficient_history: 'No history evidence (G2)',
  unsafe_request: 'Unsafe request (G10)',
}

export const TYPE_COLOR = {
  commit: '#0284c7', diff: '#0ea5e9', issue: '#d97706', pr: '#7c3aed', review: '#8b5cf6',
  code: '#059669', doc: '#10b981', release: '#e11d48',
}
