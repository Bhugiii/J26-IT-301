import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Search, SlidersHorizontal, Gauge as GaugeIcon, Star, MessageSquareText } from 'lucide-react'
import Layout from '../components/Layout'
import PhotoHero from '../components/PhotoHero'
import { api, useApi } from '../api/client'
import { ErrorState, Loading } from '../components/ui'
import DestinationCard from '../components/DestinationCard'
import { fmt } from '../lib/format'

const SORTS = {
  score: { label: 'Reality match', fn: (a: S, b: S) => b.score - a.score },
  rating: { label: 'Visitor rating', fn: (a: S, b: S) => b.avg_rating - a.avg_rating },
  reviews: { label: 'Most reviewed', fn: (a: S, b: S) => b.total_reviews - a.total_reviews },
  name: { label: 'Name A–Z', fn: (a: S, b: S) => a.name.localeCompare(b.name) },
}
type S = import('../api/types').DestinationSummary

export default function Destinations() {
  const { data, error, loading } = useApi('overview', api.overview)
  const [params, setParams] = useSearchParams()
  const type = params.get('type') ?? 'All'
  const province = params.get('province') ?? 'All'
  const sort = (params.get('sort') ?? 'score') as keyof typeof SORTS
  const [q, setQ] = useState('')

  const set = (k: string, v: string) => {
    const p = new URLSearchParams(params)
    if (v === 'All' || (k === 'sort' && v === 'score')) p.delete(k); else p.set(k, v)
    setParams(p, { replace: true })
  }

  const list = useMemo(() => {
    if (!data) return []
    const s = q.trim().toLowerCase()
    return data.destinations
      .filter((d) => type === 'All' || d.type === type)
      .filter((d) => province === 'All' || d.province === province)
      .filter((d) => !s || `${d.name} ${d.city} ${d.district}`.toLowerCase().includes(s))
      .sort(SORTS[sort]?.fn ?? SORTS.score.fn)
  }, [data, type, province, sort, q])

  const avg = (k: 'score' | 'avg_rating') => list.length ? list.reduce((t, d) => t + d[k], 0) / list.length : 0

  return (
    <Layout crumbs={['Destinations']}>
      {loading && <Loading />}
      {error && <ErrorState message={error} />}
      {data && (
        <div className="fade-in">
          <div className="mb-6">
            <PhotoHero compact photo="/photos/stilt-fishermen.jpg" alt="Stilt fishermen silhouetted against a Sri Lankan sunset" position="center 45%"
              eyebrow="Expectation vs. experience" title="Ranked destinations">
              <p className="mt-2 max-w-xl text-[15px] leading-relaxed text-white/85">
                Every destination ranked by how closely real visitor reviews echo its marketing. Open any destination for
                the full picture and friendly tips for your visit.
              </p>
            </PhotoHero>
          </div>

          {/* Filter bar like the reference design */}
          <div className="card mb-5 flex flex-col gap-4 p-4 xl:flex-row xl:items-center">
            <div className="flex flex-1 flex-wrap gap-1 rounded-xl bg-offwhite p-1">
              {['All', ...data.types].map((t) => (
                <button key={t} onClick={() => set('type', t)}
                  className={`rounded-lg px-3 py-1.5 text-[13px] font-medium transition-colors ${type === t ? 'bg-white text-navy shadow-card' : 'text-slate-text hover:text-navy'}`}>
                  {t === 'All' ? 'All types' : t}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-5 border-line xl:border-l xl:pl-5">
              <Metric icon={GaugeIcon} label="Avg match" value={`${fmt(avg('score'))}%`} />
              <Metric icon={Star} label="Avg rating" value={avg('avg_rating').toFixed(2)} />
              <Metric icon={MessageSquareText} label="Showing" value={`${list.length}`} />
            </div>
          </div>

          <div className="mb-5 grid gap-3 md:grid-cols-[1fr_220px_200px]">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-text" />
              <input className="input pl-9" placeholder="Filter by name, city or district…" aria-label="Filter destinations" value={q} onChange={(e) => setQ(e.target.value)} />
            </div>
            <select className="input" value={province} onChange={(e) => set('province', e.target.value)} aria-label="Province">
              <option value="All">All provinces</option>
              {data.provinces.map((p) => <option key={p}>{p}</option>)}
            </select>
            <div className="relative">
              <SlidersHorizontal className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-text" />
              <select className="input pl-9" value={sort} onChange={(e) => set('sort', e.target.value)} aria-label="Sort">
                {Object.entries(SORTS).map(([k, v]) => <option key={k} value={k}>Sort: {v.label}</option>)}
              </select>
            </div>
          </div>

          {list.length === 0 ? (
            <div className="card p-10 text-center">
              <h3 className="font-display text-[18px] font-bold">No destinations match these filters</h3>
              <p className="mt-1 text-[14px]">Try another type or province — there's plenty more to discover.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {list.map((d) => <DestinationCard key={d.name} d={d} highlight={d.rank === 1 ? 'Top reality match' : undefined} />)}
            </div>
          )}
        </div>
      )}
    </Layout>
  )
}

function Metric({ icon: Icon, label, value }: { icon: typeof Star; label: string; value: string }) {
  return (
    <div className="flex items-center gap-2">
      <Icon className="h-4 w-4 text-teal" />
      <div>
        <div className="text-[10.5px] font-semibold uppercase tracking-wider text-slate-text">{label}</div>
        <div className="text-[14px] font-bold text-navy-deep">{value}</div>
      </div>
    </div>
  )
}
