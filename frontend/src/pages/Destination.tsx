import { Link, useParams } from 'react-router-dom'
import { useMemo } from 'react'
import {
  ArrowLeft, GitCompareArrows, MapPin, Megaphone, MessageCircleHeart, Star, Trophy, MessageSquareText,
  Gauge as GaugeIcon, Lightbulb,
} from 'lucide-react'
import Layout from '../components/Layout'
import { api, useApi } from '../api/client'
import type { AspectDetail, DestinationDetail } from '../api/types'
import { ErrorState, Loading, SectionTitle, Stat } from '../components/ui'
import { AspectInsightCard, ExpandableText, ReviewsSideBySide, Stars, TipsTimeline } from '../components/destination'
import { buildVisitTips } from '../lib/tips'
import { AspectBars, Gauge } from '../components/charts'
import Scene from '../components/Scene'
import { ASPECT_META, BAND, fmt, int } from '../lib/format'

export default function DestinationPage() {
  const { name = '' } = useParams()
  const decoded = decodeURIComponent(name)
  const { data, error, loading } = useApi(`d:${decoded}`, () => api.destination(decoded))
  return (
    <Layout crumbs={['Destinations', data?.Location_Name ?? decoded]}>
      {loading && <Loading label="Reading the reviews…" />}
      {error && <ErrorState message={error} />}
      {data && <Body d={data} />}
    </Layout>
  )
}

function Body({ d }: { d: DestinationDetail }) {
  const band = BAND[d.Score_Band]
  const tips = useMemo(() => buildVisitTips(d), [d])
  const total = useApi('overview', api.overview).data?.total_destinations
  const RELATIVE_SHORT = { above: 'More than usual', typical: 'About usual', below: 'Less than usual' } as const
  const avgPct = Object.fromEntries(d.Aspects.map((a) => [a.key, a.dataset_avg_pct])) as Record<AspectDetail['key'], number>
  const destPct = Object.fromEntries(d.Aspects.map((a) => [a.key, a.share_pct])) as Record<AspectDetail['key'], number>

  return (
    <div className="fade-in space-y-8">
      {/* Hero */}
      <section data-reveal className="relative overflow-hidden rounded-tm">
        <Scene name={d.Location_Name} type={d.Location_Type} className="absolute inset-0" />
        <div className="absolute inset-0 bg-gradient-to-r from-navy-deep/90 via-navy-deep/65 to-navy-deep/10" />
        <div className="relative px-6 py-9 text-white md:px-10 md:py-12">
          <Link to="/destinations" className="inline-flex items-center gap-1.5 text-[13px] font-medium text-white/80 hover:text-white">
            <ArrowLeft className="h-4 w-4" /> All destinations
          </Link>
          <div className="mt-4 flex flex-wrap gap-2">
            <span className="rounded-full bg-white/15 px-3 py-1 text-[12px] font-semibold backdrop-blur">{d.Location_Type}</span>
            <span className="rounded-full px-3 py-1 text-[12px] font-semibold" style={{ background: band.soft, color: band.text }}>{band.label}</span>
          </div>
          <h1 className="mt-3 max-w-3xl font-display text-[32px] font-extrabold leading-tight text-white md:text-[42px]">{d.Location_Name}</h1>
          <p className="mt-1 flex items-center gap-1.5 text-[14px] text-white/80">
            <MapPin className="h-4 w-4" />{d.City !== d.District ? `${d.City}, ` : ''}{d.District} · {d.Province}
          </p>
          <p className="mt-4 max-w-2xl text-[16px] leading-relaxed text-white/90">{band.desc}</p>
          <div className="mt-6 flex flex-wrap gap-3">
            <a href="#tips" className="btn bg-white text-navy hover:bg-sky"><Lightbulb className="h-4 w-4" /> See visit tips</a>
            <Link to={`/compare?a=${encodeURIComponent(d.Location_Name)}`} className="btn border border-white/30 text-white hover:bg-white/10">
              <GitCompareArrows className="h-4 w-4" /> Compare
            </Link>
          </div>
        </div>
      </section>

      {/* KPI row */}
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Reality match" icon={GaugeIcon}
          value={<>{fmt(d.Average_Reality_Score)}<span className="text-[16px] font-semibold text-slate-text">%</span></>}
          sub={`Average across all destinations: ${fmt(d.Dataset_Avg_Score)}%`} />
        <Stat label="Ranking" icon={Trophy}
          value={<>#{d.Score_Rank}{total ? <span className="text-[16px] font-semibold text-slate-text"> of {total}</span> : null}</>}
          sub={d.Score_Rank === 1 ? 'The highest reality match of all destinations' : `Higher match than ${Math.round(d.Score_Percentile)}% of other destinations`} />
        <Stat label="Reviews analysed" icon={MessageSquareText} value={int(d.Total_Reviews)} sub="Real visitor reviews of this place" />
        <Stat label="Visitor rating" icon={Star}
          value={<>{d.Average_Rating.toFixed(2)}<span className="text-[16px] font-semibold text-slate-text"> / 5</span></>}
          sub={`${fmt(d.Positive_Pct, 0)}% of visitors rated it 4★ or higher`} />
      </section>

      {/* Gauge + Radar */}
      <section className="grid gap-6 lg:grid-cols-5">
        <div className="card flex flex-col p-6 lg:col-span-2">
          <h3 className="font-display text-[19px] font-bold">Reality Match Score</h3>
          <p className="helper">How closely visitors' experiences match the advert</p>
          <div className="flex flex-1 items-center justify-center py-4">
            <Gauge value={d.Average_Reality_Score} avg={d.Dataset_Avg_Score} color={band.color} />
          </div>
          <div className="grid grid-cols-3 gap-2 text-center text-[11.5px]">
            {(['authentic', 'unique_vibe', 'spot_on'] as const).map((b) => (
              <div key={b} className={`rounded-lg px-2 py-1.5 ${d.Score_Band === b ? 'font-bold ring-1' : ''}`}
                style={{ background: BAND[b].soft, color: BAND[b].text, ['--tw-ring-color' as string]: BAND[b].color }}>
                {BAND[b].short}<span className="block font-normal opacity-80">{b === 'authentic' ? '≤ 45%' : b === 'unique_vibe' ? '45–60%' : '> 60%'}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="card p-6 lg:col-span-3">
          <h3 className="font-display text-[19px] font-bold">What visitors talk about</h3>
          <p className="helper">How often reviews mention each topic here, compared with a typical place</p>
          <AspectBars
            series={[
              { name: 'This place', values: destPct, color: '#0D9488' },
              { name: 'Typical place', values: avgPct, color: '#123B5D', muted: true },
            ]}
            notes={Object.fromEntries(d.Aspects.map((a) => [a.key, RELATIVE_SHORT[a.relative]]))} />
        </div>
      </section>

      {/* Advert vs real visit */}
      <section>
        <SectionTitle eyebrow="Advert vs. real visit" title="What the advert says and what a visitor found"
          desc="The advert side by side with a real review about the topic visitors here talk about most." />
        <div className="grid gap-5 md:grid-cols-2">
          <div data-reveal className="flex flex-col rounded-tm border border-[#B4E9E2] bg-sky/70 p-6">
            <div className="flex items-center gap-2 text-[13px] font-semibold uppercase tracking-wider text-navy">
              <span className="grid h-8 w-8 place-items-center rounded-lg bg-white text-navy"><Megaphone className="h-4 w-4" /></span>
              What the advert says
            </div>
            <blockquote className="mt-4 font-display text-[18px] font-semibold leading-relaxed text-navy-deep">“{d.Marketing_Promise}”</blockquote>
            <p className="mt-auto pt-4 text-[13px] text-slate-text">This is the picture most travellers have before they arrive.</p>
          </div>
          <div data-reveal className="flex flex-col rounded-tm border border-line bg-white p-6 shadow-card">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-[13px] font-semibold uppercase tracking-wider text-[#15803D]">
                <span className="grid h-8 w-8 place-items-center rounded-lg bg-[#DCFCE7] text-[#15803D]"><MessageCircleHeart className="h-4 w-4" /></span>
                What a visitor found
              </div>
              {d.Contrasting_Review_Aspect && (
                <span className="chip">About: {ASPECT_META[d.Contrasting_Review_Aspect].friendly.toLowerCase()}</span>
              )}
            </div>
            {d.Contrasting_Review_Title && <h4 className="mt-4 text-[16px] font-semibold">{d.Contrasting_Review_Title}</h4>}
            {d.Contrasting_Review_Rating != null && <div className="mt-1"><Stars n={d.Contrasting_Review_Rating} /></div>}
            {d.Contrasting_Reality_Review
              ? <ExpandableText text={`“${d.Contrasting_Reality_Review}”`} lines={6} className="mt-2 text-[15px] leading-relaxed text-navy-deep" />
              : <p className="mt-3 text-[14px]">No visitor review is available for this place yet.</p>}
          </div>
        </div>
      </section>

      {/* Pro tips */}
      <section id="tips" className="scroll-mt-24">
        <SectionTitle eyebrow="Expectation vs. experience" title="Pro tips for a great visit"
          desc="Simple steps for before you go, when you arrive and while you explore." />
        <TipsTimeline tips={tips} />
      </section>

      {/* The four things travellers notice */}
      <section>
        <SectionTitle eyebrow="Aspect insights" title="The four things travellers notice"
          desc="What each topic means and what to expect from it at this place." />
        <div className="grid gap-4 md:grid-cols-2">
          {d.Aspects.map((a) => <AspectInsightCard key={a.key} a={a} />)}
        </div>
      </section>

      {/* Real reviews side by side */}
      <section>
        <SectionTitle eyebrow="Real reviews side by side" title="What visitors say about each topic"
          desc="Pick what matters most to you to highlight the reviews that answer it." />
        <ReviewsSideBySide aspects={d.Aspects} />
      </section>
    </div>
  )
}
