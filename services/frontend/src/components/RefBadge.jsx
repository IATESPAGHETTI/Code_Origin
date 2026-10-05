import { TYPE_COLOR } from '../api.js'

/*
  Evidence references are IDs for machines (commit:ad7fbfa). People think in titles, so every place that shows
  a reference leads with what it is and demotes the ID to a small tag:

      Add rate limiter to login endpoint        commit ad7fbfa
      Carol Osei · May 5, 2023
*/

const KIND_LABEL = { commit: 'commit', diff: 'commit', issue: 'issue', pr: 'PR', review: 'PR review', code: 'code', doc: 'docs', release: 'release' }

export function splitRef(ref) {
  const i = (ref || '').indexOf(':')
  return i < 0 ? { kind: '', id: ref || '' } : { kind: ref.slice(0, i).toLowerCase(), id: ref.slice(i + 1) }
}

export function fmtDate(iso) {
  if (!iso) return ''
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso)
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

/** item: { ref, source_type?, title?, author?, date? } -> readable parts */
export function describe(item) {
  const { kind, id } = splitRef(item.ref)
  const type = item.source_type || kind
  const label = KIND_LABEL[type] || type
  if (kind === 'code' || kind === 'doc') {
    return { type, primary: id, tag: label, meta: '' }
  }
  const tag = kind === 'commit' ? `commit ${id.slice(0, 7)}` : kind === 'issue' ? `issue ${id}` : kind === 'pr' ? `PR ${id}` : `${label} ${id}`
  const clean = (item.title || '').replace(/^(Diff for commit \w+ \()/, '').trim()
  return { type, primary: clean || tag, tag, meta: [item.author, fmtDate(item.date)].filter(Boolean).join(' · ') }
}

function Dot({ type }) {
  return <span className="mt-[5px] h-2 w-2 shrink-0 rounded-full" style={{ background: TYPE_COLOR[type] || '#999' }} aria-hidden="true" />
}

/** Inline pill: title first, small ID tag after it. */
export default function RefBadge({ item, onClick, dim = false, strike = false, className = '', style }) {
  const d = describe(item)
  const Tag = onClick ? 'button' : 'span'
  return (
    <Tag type={onClick ? 'button' : undefined} onClick={onClick} title={`${d.tag}${d.meta ? ` · ${d.meta}` : ''}`}
      className={`inline-flex max-w-full items-center gap-2 rounded-xl px-2.5 py-1 text-left text-[0.8125rem] leading-snug transition ${onClick ? 'hover:bg-[var(--accent-soft)]' : ''} ${dim ? 'opacity-45' : ''} ${className}`}
      style={{ background: 'rgba(0,0,0,.045)', boxShadow: 'inset 0 0 0 1px rgba(0,0,0,.07)', ...style }}>
      <span className="mt-0 h-2 w-2 shrink-0 rounded-full" style={{ background: TYPE_COLOR[d.type] || '#999' }} aria-hidden="true" />
      <span className={`min-w-0 truncate font-medium ${strike ? 'line-through' : ''}`}>{d.primary}</span>
      {d.primary !== d.tag && <span className="shrink-0 font-mono text-xs muted">{d.tag}</span>}
    </Tag>
  )
}

/** Two-line row for lists: title, then "commit ad7fbfa · Carol Osei · May 5, 2023". */
export function RefLine({ item, right, onClick }) {
  const d = describe(item)
  const Tag = onClick ? 'button' : 'div'
  return (
    <Tag type={onClick ? 'button' : undefined} onClick={onClick} className="flex w-full items-start gap-2 text-left">
      <Dot type={d.type} />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[0.8125rem] font-medium">{d.primary}</span>
        <span className="block truncate text-xs muted">{[d.primary !== d.tag ? d.tag : null, d.meta].filter(Boolean).join(' · ')}</span>
      </span>
      {right}
    </Tag>
  )
}
