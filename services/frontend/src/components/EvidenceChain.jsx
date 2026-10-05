import { useInView } from './motion.jsx'

const NODES = [
  { x: 95, label: 'Session fixation reported', sub: 'issue #7', color: '#d97706' },
  { x: 280, label: 'Move auth to JWT', sub: 'PR #8 \u00b7 HS256 debated', color: '#7c3aed' },
  { x: 465, label: 'Replace cookies with JWT', sub: 'commit 69e7bbd', color: '#0284c7' },
  { x: 645, label: 'issue_token() today', sub: 'src/auth.py', color: '#059669' },
]

/** The issue -> PR -> commit -> code chain, drawn on when it scrolls into view. */
export default function EvidenceChain() {
  const [ref, seen] = useInView()
  return (
    <div ref={ref} className="overflow-x-auto">
      <svg viewBox="0 0 720 150" overflow="visible" className="mx-auto h-auto w-full min-w-[560px] max-w-3xl" role="img" aria-label="Evidence chain from issue to pull request to commit to code">
        {NODES.slice(0, -1).map((n, i) => (
          <path key={n.label} d={`M ${n.x + 18} 55 C ${n.x + 80} 20, ${NODES[i + 1].x - 80} 20, ${NODES[i + 1].x - 18} 55`}
            fill="none" stroke="var(--line)" strokeWidth="2.5" pathLength="1"
            className={seen ? 'draw-path' : ''} style={{ '--d': `${300 + i * 450}ms`, stroke: seen ? NODES[i + 1].color : 'var(--line)' }} />
        ))}
        {NODES.map((n, i) => (
          <g key={n.label} className={seen ? 'pop' : ''} style={{ '--d': `${i * 450}ms`, opacity: seen ? undefined : 0, transformOrigin: `${n.x}px 55px` }}>
            <circle cx={n.x} cy="55" r="18" fill={n.color} opacity="0.18" />
            <circle cx={n.x} cy="55" r="9" fill={n.color} />
            <text x={n.x} y="100" textAnchor="middle" fontSize="14" fill="var(--text)" fontWeight="600">{n.label}</text>
            <text x={n.x} y="120" textAnchor="middle" fontSize="12.5" fill="var(--muted)">{n.sub}</text>
          </g>
        ))}
      </svg>
    </div>
  )
}
