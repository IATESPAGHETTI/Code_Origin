import { useEffect, useState } from 'react'
import { Link, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { api } from './api.js'
import Home from './pages/Home.jsx'
import Repositories from './pages/Repositories.jsx'
import Ask from './pages/Ask.jsx'
import Evaluation from './pages/Evaluation.jsx'
import Present from './pages/Present.jsx'
import Story from './pages/Story.jsx'
import GlassBackdrop from './components/GlassBackdrop.jsx'

const NAV = [
  { to: '/ask', label: 'Ask' },
  { to: '/repos', label: 'Repositories' },
  { to: '/eval', label: 'Evaluation' },
  { to: '/present', label: 'Present' },
]

function Health() {
  const [state, setState] = useState(null)
  useEffect(() => {
    let alive = true
    const tick = () => api.healthAll().then((h) => alive && setState(h)).catch(() => alive && setState({ status: 'down', services: {} }))
    tick()
    const id = setInterval(tick, 15000)
    return () => { alive = false; clearInterval(id) }
  }, [])
  const color = !state ? 'bg-slate-400' : state.status === 'ok' ? 'bg-emerald-500' : state.status === 'degraded' ? 'bg-amber-500' : 'bg-rose-500'
  const down = state ? Object.entries(state.services || {}).filter(([, ok]) => !ok).map(([n]) => n) : []
  const label = !state ? 'checking...' : state.status === 'ok' ? 'all services healthy' : down.length ? `down: ${down.join(', ')}` : 'gateway unreachable'
  return (
    <span className="hidden items-center gap-2 text-xs muted md:flex" role="status">
      <span className={`h-2 w-2 rounded-full ${color} ${state?.status === 'ok' ? 'live-dot' : ''}`} />
      {label}
    </span>
  )
}

export default function App() {
  const location = useLocation()
  if (location.pathname === '/present') return <Present />
  if (location.pathname === '/story') return <Story />
  return (
    <div className="mx-auto max-w-[1760px] px-4 pb-20 sm:px-8 lg:px-14">
      <GlassBackdrop />
      <header className="sticky top-0 z-20 -mx-4 flex items-center justify-between gap-3 px-4 py-4 backdrop-blur-md sm:-mx-8 sm:px-8 lg:-mx-14 lg:px-14" style={{ background: 'linear-gradient(to bottom, color-mix(in srgb, var(--bg) 55%, transparent), transparent)' }}>
        <Link to="/" className="flex items-center gap-2.5" aria-label="CodeOrigin home">
          <img src="/favicon.svg" alt="" className="h-8 w-8" />
          <span className="text-lg font-extrabold tracking-tight">CodeOrigin</span>
        </Link>
        <nav className="panel refract flex items-center gap-1 !rounded-full !p-1">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to}
              className={({ isActive }) => `rounded-full px-4 py-1.5 text-sm font-medium transition ${isActive ? 'text-white' : 'hover:bg-black/5'}`}
              style={({ isActive }) => (isActive ? { background: 'var(--accent-strong)' } : undefined)}>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <Health />
      </header>
      <main key={location.pathname} className="page-enter">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/ask" element={<Ask />} />
          <Route path="/repos" element={<Repositories />} />
          <Route path="/eval" element={<Evaluation />} />
          <Route path="*" element={<p className="muted">Page not found.</p>} />
        </Routes>
      </main>
    </div>
  )
}
