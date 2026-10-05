import { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'
import IngestView from '../components/IngestView.jsx'

const STATUS_STYLE = {
  ready: 'text-emerald-700', ingesting: 'text-amber-700', queued: 'text-amber-700', failed: 'text-rose-600', registered: 'muted',
}

function Counts({ counts }) {
  const entries = Object.entries(counts || {}).filter(([k]) => !k.startsWith('_'))
  if (!entries.length) return <span className="muted">-</span>
  return (
    <div className="flex flex-wrap gap-1">
      {entries.map(([k, v]) => <span key={k} className="chip">{k} {v}</span>)}
    </div>
  )
}

export default function Repositories() {
  const [repos, setRepos] = useState([])
  const [source, setSource] = useState('')
  const [ref, setRef] = useState('')
  const [maxCommits, setMaxCommits] = useState('')
  const [active, setActive] = useState(null)   // { repoId, jobId } shown in the live panel
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => api.repos().then((r) => setRepos(r.repos)).catch((e) => setError(e.message)), [])
  useEffect(() => { load() }, [load])

  const submit = async (e) => {
    e.preventDefault()
    setError(''); setBusy(true)
    try {
      const body = { source: source.trim() }
      if (ref.trim()) body.ref = ref.trim()
      if (maxCommits) body.max_commits = Number(maxCommits)
      const r = await api.addRepo(body)
      setActive({ repoId: r.repo_id, jobId: r.job_id })
      setSource('')
      load()
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  const act = async (fn, id) => {
    setError('')
    try {
      const r = await fn(id)
      if (r?.job_id) setActive({ repoId: id, jobId: r.job_id })
      load()
    } catch (err) { setError(err.message) }
  }

  return (
    <div className="space-y-6">
      <form onSubmit={submit} className="panel space-y-3 !p-6">
        <h2 className="text-lg font-semibold">Add a GitHub repository</h2>
        <p className="text-sm muted">
          Paste a github.com URL or <code>owner/repo</code>. CodeOrigin clones it, reads commits and diffs, and pulls issues, pull
          requests and reviews from the GitHub API (set <code>GITHUB_TOKEN</code> on the server for higher rate limits and private repos).
        </p>
        <div className="grid gap-3 sm:grid-cols-[1fr_160px_140px_auto]">
          <input className="input" required placeholder="https://github.com/owner/repo" value={source} onChange={(e) => setSource(e.target.value)} aria-label="Repository" />
          <input className="input" placeholder="branch / tag (optional)" value={ref} onChange={(e) => setRef(e.target.value)} aria-label="Ref" />
          <input className="input" type="number" min="1" placeholder="max commits" value={maxCommits} onChange={(e) => setMaxCommits(e.target.value)} aria-label="Max commits" />
          <button className="btn-primary" disabled={busy || !source.trim()}>{busy ? 'Adding...' : 'Index'}</button>
        </div>
        {error && <p role="alert" className="text-sm text-rose-600">{error}</p>}
      </form>

      {active && (
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs muted">
            <span className="font-mono">{active.repoId}</span>
            <button className="underline" onClick={() => setActive(null)}>dismiss</button>
          </div>
          <IngestView key={active.jobId} jobId={active.jobId} onDone={load} />
        </div>
      )}

      <div className="panel overflow-x-auto !p-0">
        <table className="w-full">
          <thead><tr><th className="th">Repository</th><th className="th">Status</th><th className="th">Indexed evidence</th><th className="th"></th></tr></thead>
          <tbody>
            {repos.length === 0 && <tr><td className="td muted" colSpan="4">No repositories yet.</td></tr>}
            {repos.map((r) => (
              <tr key={r.id} className="rise border-t" style={{ borderColor: 'var(--line)' }}>
                <td className="td align-top">
                  <div className="font-medium">{r.kind === 'github' ? `${r.owner}/${r.name}` : r.name}</div>
                  <div className="font-mono text-xs muted">{r.id}</div>
                  {r.last_sha && <div className="text-xs muted">HEAD {r.last_sha.slice(0, 7)}</div>}
                  {r.error && <div className="mt-1 text-xs text-rose-600">{r.error}</div>}
                </td>
                <td className={`td align-top ${STATUS_STYLE[r.status] || ''}`}>{r.status}</td>
                <td className="td align-top"><Counts counts={r.counts} /></td>
                <td className="td align-top text-right">
                  <div className="flex justify-end gap-2">
                    <button className="btn-ghost" disabled={r.status === 'ingesting'} onClick={() => act(api.syncRepo, r.id)}>Sync</button>
                    <button className="btn-ghost" disabled={r.status === 'ingesting'}
                      onClick={() => window.confirm(`Delete ${r.id} and its index?`) && act(api.deleteRepo, r.id)}>Delete</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
