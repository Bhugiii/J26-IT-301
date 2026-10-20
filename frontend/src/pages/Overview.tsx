import { Link } from 'react-router-dom'
import { ArrowRight, MapPin, MessageSquareText, Gauge as GaugeIcon, Sparkles, Info } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, Cell, CartesianGrid } from 'recharts'
import Layout from '../components/Layout'
import PhotoHero from '../components/PhotoHero'
import { api, useApi } from '../api/client'
import { ErrorState, Loading, SectionTitle, Stat } from '../components/ui'
import DestinationCard from '../components/DestinationCard'
import { ASPECTS } from '../api/types'
import type { Overview as OverviewData } from '../api/types'
import { ASPECT_META, BAND, fmt, int } from '../lib/format'

export default function Overview() {
  const { data, error, loading } = useApi('overview', api.overview)
  return (
    <Layout crumbs={['Overview']}>
      {loading && <Loading />}
      {error && <ErrorState message={error} />}
      {data && <Body data={data} />}
    </Layout>
  )
}

function Body({ data }: { data: OverviewData }) {
  const ranked = [...data.destinations].sort((a, b) => a.rank - b.rank)
  const top = ranked.slice(0, 3)
  const best = ranked[0]
  const bandCounts = (['spot_on', 'unique_vibe', 'authentic'] as const).map((b) => ({
    band: b, n: data.destinations.filter((d) => d.band === b).length,
  }))
  const aspectData = ASPECTS.map((a) => ({ name: ASPECT_META[a].label, value: data.aspect_avg_pct[a], color: ASPECT_META[a].color }))

  return (
    <div className="fade-in space-y-8">
      {/* Hero */}
      <PhotoHero photo="/photos/coast-aerial.jpg" alt="Aerial view of a palm-fringed bay on Sri Lanka's southern coast" position="center 40%"
        eyebrow={<span className="inline-flex items-center gap-2"><Sparkles className="h-3.5 w-3.5" /> Explainable expectation data</span>}
        title="Know what to expect before you go">
        <div className="mt-6 flex flex-wrap gap-3">
          <Link to="/destinations" className="btn-primary">Explore destinations <ArrowRight className="h-4 w-4" /></Link>
        </div>
      </PhotoHero>

      {/* KPIs */}
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Destinations" value={data.total_destinations} icon={MapPin} sub={`${data.types.length} destination types, ${data.provinces.length} provinces`} />
        <Stat label="Reviews analysed" value={int(data.total_reviews)} icon={MessageSquareText} sub="Real visitor reviews paired with marketing text" />
        <Stat label="Avg reality match" value={<>{fmt(data.avg_score)}<span className="text-[16px] font-semibold text-slate-text">%</span></>}
          icon={GaugeIcon} sub={`Range ${fmt(data.min_score)}% – ${fmt(data.max_score)}% across destinations`} />
        <Stat label="Closest match" value={<span className="text-[20px]">{best.name}</span>} icon={Sparkles}
          sub={`${fmt(best.score)}% reality match`} />
      </section>

      {/* Top matches */}
      <section>
        <SectionTitle eyebrow="Ranked by reality match" title="Where the experience matches the promise"
          right={<Link to="/destinations" className="btn-ghost">See all {data.total_destinations} <ArrowRight className="h-4 w-4" /></Link>} />
        <div className="space-y-4">
          {top.map((d, i) => <DestinationCard key={d.name} d={d} highlight={i === 0 ? 'Top reality match' : undefined} />)}
        </div>
      </section>

      {/* Two insight panels */}
      <section className="grid gap-6 lg:grid-cols-2">
        <div className="card p-6">
          <h3 className="font-display text-[19px] font-bold">What visitors talk about</h3>
          <p className="helper mt-0.5">Average share of a destination's reviews that mention each aspect</p>
          <div className="mt-4 h-[230px]">
            <ResponsiveContainer>
              <BarChart data={aspectData} layout="vertical" margin={{ left: 20, right: 30 }}>
                <CartesianGrid horizontal={false} stroke="#EEF2F6" />
                <XAxis type="number" tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11, fill: '#64748B' }} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="name" width={120} tick={{ fontSize: 12, fill: '#172B3A', fontWeight: 600 }} axisLine={false} tickLine={false} />
                <Tooltip formatter={(v: number) => `${fmt(v)}% of reviews`} cursor={{ fill: '#F2F8FA' }} contentStyle={{ borderRadius: 10, fontSize: 12 }} />
                <Bar dataKey="value" radius={[0, 6, 6, 0]} barSize={22} label={{ position: 'right', fontSize: 11, fill: '#172B3A', formatter: (v: number) => `${fmt(v)}%` }}>
                  {aspectData.map((a) => <Cell key={a.name} fill={a.color} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="card p-6">
          <h3 className="font-display text-[19px] font-bold">How destinations line up</h3>
          <p className="helper mt-0.5">Destinations grouped by their reality match band</p>
          <div className="mt-5 space-y-4">
            {bandCounts.map(({ band, n }) => (
              <div key={band}>
                <div className="flex items-center justify-between text-[13.5px]">
                  <span className="font-semibold text-navy-deep">{BAND[band].label}</span>
                  <span className="font-semibold text-navy-deep">{n}</span>
                </div>
                <div className="mt-1.5 h-2.5 rounded-full bg-[#EEF2F6]">
                  <div className="h-full rounded-full" style={{ width: `${(n / data.total_destinations) * 100}%`, background: BAND[band].color }} />
                </div>
                <p className="helper mt-1">
                  {band === 'spot_on' ? 'Score above 60%: reviews closely echo the description.'
                    : band === 'unique_vibe' ? 'Score 45–60%: reviews echo parts of the description, plus everyday local life.'
                    : 'Score 45% or below: visitors describe it quite differently, so come with an open mind.'}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section data-reveal className="flex flex-col gap-4 rounded-tm border border-line bg-[#EEF3F7] p-6 sm:flex-row">
        <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-white text-navy"><Info className="h-5 w-5" /></span>
        <div>
          <h3 className="font-display text-[18px] font-bold">Why these scores?</h3>
          <p className="mt-1 text-[14px] leading-relaxed">
            Each marketing description and each review is turned into a 768-dimensional meaning vector with a multilingual
            Sentence-BERT model. The Reality Match Score is the average cosine similarity between a destination's marketing
            text and its reviews, shown as a percentage. It measures how closely visitors' words echo the promise — it is a
            guide for setting expectations, not a rating of the destination.
          </p>
        </div>
      </section>
    </div>
  )
}
