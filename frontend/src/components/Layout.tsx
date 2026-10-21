import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, MapPin, GitCompareArrows, Search, Menu, X, ChevronRight,
  LayoutGrid, Compass, Heart, User, Route, CircleUser, Users, Sun, UsersRound, ShieldCheck, ScanSearch,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { api, useApi } from '../api/client'
import { destPath } from '../lib/format'
import { useScrollReveal } from '../lib/useScrollReveal'

/**
 * Main menu shared with the other TravelMind components (same items, order and style).
 * Only "Expectation-Reality" (this component) is active here; the other items belong to
 * teammates' components and are shown disabled so the menu matches the integrated app.
 */
type MenuItem = { label: string; icon: LucideIcon; mine?: boolean }
const MAIN_MENU: MenuItem[] = [
  { label: 'Dashboard', icon: LayoutGrid },
  { label: 'Recommendations', icon: Compass },
  { label: 'Saved Places', icon: Heart },
  { label: 'Traveller Profile', icon: User },
  { label: 'Itinerary Planner', icon: Route },
  { label: 'Account', icon: CircleUser },
  { label: 'Crowd Prediction', icon: Users },
  { label: 'Weather Intelligence', icon: Sun },
  { label: 'Traveller Segments', icon: UsersRound },
  { label: 'Expectation-Reality', icon: ShieldCheck, mine: true },
  { label: 'Discover Places', icon: ScanSearch },
  { label: 'Attraction-Rich Areas', icon: MapPin },
]

/** This component's own pages, shown under "Expectation-Reality". */
const MY_PAGES = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/destinations', label: 'Destinations', icon: MapPin },
  { to: '/compare', label: 'Compare', icon: GitCompareArrows },
]

export default function Layout({ children, crumbs }: { children: React.ReactNode; crumbs: string[] }) {
  const [open, setOpen] = useState(false)
  const loc = useLocation()
  useEffect(() => setOpen(false), [loc.pathname])
  useScrollReveal(loc.pathname + loc.search)

  return (
    <div className="min-h-screen lg:pl-[248px]">
      {/* Sidebar */}
      <aside className={`fixed inset-y-0 left-0 z-40 flex w-[248px] flex-col border-r border-line bg-white transition-transform lg:translate-x-0 ${open ? 'translate-x-0' : '-translate-x-full'}`}>
        <Link to="/" className="flex items-center gap-3 px-5 pb-5 pt-6" aria-label="TravelMind home">
          <img src="/brand/mark.png" alt="" className="h-12 w-auto shrink-0" />
          <span className="min-w-0">
            <span className="block text-[14px] font-bold leading-[1.15] text-navy">Travel<br />Mind</span>
            <span className="mt-1 block text-[11.5px] text-slate-text">Sri Lanka, your way.</span>
          </span>
        </Link>
        <div className="px-5 pb-2 pt-1 text-[10.5px] font-semibold uppercase tracking-[0.16em] text-slate-text">Main menu</div>
        <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto px-3 pb-6" aria-label="Main menu">
          {MAIN_MENU.map(({ label, icon: Icon, mine }) => mine ? (
            <div key={label}>
              <Link to="/" aria-current="page"
                className="flex items-center gap-3 rounded-lg border border-[#B4E9E2] border-l-[3px] border-l-teal bg-[#E6F6F4] px-3 py-2.5 text-[13.5px] font-semibold text-teal-dark">
                <Icon className="h-[17px] w-[17px]" />{label}
              </Link>
              <div className="ml-[22px] mt-1 flex flex-col gap-0.5 border-l border-line pl-3">
                {MY_PAGES.map(({ to, label: sub, icon: SubIcon, end }) => (
                  <NavLink key={to} to={to} end={end}
                    className={({ isActive }) =>
                      `flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] transition-colors ${
                        isActive || (to === '/destinations' && loc.pathname.startsWith('/destination/'))
                          ? 'bg-offwhite font-semibold text-teal-dark' : 'font-medium text-navy hover:bg-offwhite hover:text-teal-dark'}`}>
                    <SubIcon className="h-4 w-4" />{sub}
                  </NavLink>
                ))}
              </div>
            </div>
          ) : (
            <span key={label} aria-disabled="true" title="Part of another TravelMind component"
              className="flex cursor-not-allowed select-none items-center gap-3 rounded-lg border-l-[3px] border-transparent px-3 py-2.5 text-[13.5px] font-medium text-slate-text/70">
              <Icon className="h-[17px] w-[17px]" />{label}
            </span>
          ))}
        </nav>
      </aside>
      {open && <div className="fixed inset-0 z-30 bg-navy-deep/40 lg:hidden" onClick={() => setOpen(false)} />}

      {/* Top bar */}
      <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-line bg-white/90 px-4 backdrop-blur md:px-8">
        <button className="rounded-lg p-2 text-navy lg:hidden" onClick={() => setOpen(!open)} aria-label="Menu">
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
        <Link to="/" className="shrink-0 lg:hidden" aria-label="TravelMind home">
          <img src="/brand/mark.png" alt="" className="h-9 w-auto" />
        </Link>
        <nav className="hidden min-w-0 items-center gap-1.5 text-[13px] sm:flex">
          <span className="text-slate-text">TravelMind</span>
          <ChevronRight className="h-3.5 w-3.5 text-slate-text/60" />
          <Link to="/" className="text-slate-text hover:text-teal-dark">Expectation-Reality</Link>
          {crumbs.map((c, i) => (
            <span key={i} className="flex min-w-0 items-center gap-1.5">
              <ChevronRight className="h-3.5 w-3.5 text-slate-text/60" />
              <span className={`truncate ${i === crumbs.length - 1 ? 'font-semibold text-navy-deep' : 'text-slate-text'}`}>{c}</span>
            </span>
          ))}
        </nav>
        <div className="ml-auto w-full max-w-[320px]"><QuickSearch /></div>
      </header>

      <main className="mx-auto max-w-[1240px] px-4 pb-16 pt-6 md:px-8">{children}</main>
    </div>
  )
}

function QuickSearch() {
  const { data } = useApi('overview', api.overview)
  const [q, setQ] = useState('')
  const [focus, setFocus] = useState(false)
  const [idx, setIdx] = useState(0)
  const nav = useNavigate()
  const box = useRef<HTMLDivElement>(null)
  const results = useMemo(() => {
    if (!data || !q.trim()) return []
    const s = q.trim().toLowerCase()
    // Rank: name starts with query > a word in the name starts with it > name contains it > city/district match.
    const rankOf = (n: string, place: string) => {
      const name = n.toLowerCase()
      if (name.startsWith(s)) return 0
      if (name.split(/[\s(-]+/).some((w) => w.startsWith(s))) return 1
      if (name.includes(s)) return 2
      if (place.toLowerCase().includes(s)) return 3
      return 9
    }
    return data.destinations
      .map((d) => ({ d, r: rankOf(d.name, `${d.city} ${d.district}`) }))
      .filter((x) => x.r < 9)
      .sort((x, y) => x.r - y.r || y.d.total_reviews - x.d.total_reviews)
      .slice(0, 7)
      .map((x) => x.d)
  }, [data, q])

  const go = (name: string) => { nav(destPath(name)); setQ(''); setFocus(false) }

  return (
    <div className="relative" ref={box}>
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-text" />
      <input className="input py-2 pl-9" placeholder="Search destinations…" value={q}
        role="combobox" aria-expanded={focus && results.length > 0} aria-controls="search-results"
        aria-autocomplete="list" aria-activedescendant={focus && results[idx] ? `search-opt-${idx}` : undefined}
        onChange={(e) => { setQ(e.target.value); setIdx(0) }}
        onFocus={() => setFocus(true)} onBlur={() => setTimeout(() => setFocus(false), 150)}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown') setIdx((i) => Math.min(i + 1, results.length - 1))
          if (e.key === 'ArrowUp') setIdx((i) => Math.max(i - 1, 0))
          if (e.key === 'Enter' && results[idx]) go(results[idx].name)
          if (e.key === 'Escape') setFocus(false)
        }} aria-label="Search destinations" />
      {focus && results.length > 0 && (
        <ul id="search-results" role="listbox" className="absolute left-0 right-0 top-full z-50 mt-1 overflow-hidden rounded-xl border border-line bg-white shadow-lift">
          {results.map((d, i) => (
            <li key={d.name} id={`search-opt-${i}`} role="option" aria-selected={i === idx}>
              <button onMouseDown={() => go(d.name)}
                className={`flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-[13px] ${i === idx ? 'bg-sky/60' : 'hover:bg-offwhite'}`}>
                <span className="truncate font-medium text-navy-deep">{d.name}</span>
                <span className="shrink-0 text-[11px] text-slate-text">{d.score.toFixed(1)}%</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}