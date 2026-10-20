import { Link, useParams } from 'react-router-dom'
import {
  ArrowLeft, GitCompareArrows, MapPin, Megaphone, MessageCircleHeart, Star, Trophy, MessageSquareText,
  Gauge as GaugeIcon, ShieldCheck, Quote, Lightbulb,
} from 'lucide-react'
import Layout from '../components/Layout'
import { api, useApi } from '../api/client'
import type { AspectDetail, DestinationDetail } from '../api/types'
import { ErrorState, Loading, SectionTitle, Stat, TipCard } from '../components/ui'
import { AspectBars, Distribution, Gauge, ShareBar } from '../components/charts'
import Scene from '../components/Scene'
import { ASPECT_META, BAND, RELATIVE_LABEL, fmt, int } from '../lib/format'

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

export function Stars({ n, size = 'h-3.5 w-3.5' }: { n: number; size?: string }) {
  return (
    <span className="inline-flex" aria-label={`${n} out of 5 stars`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <Star key={i} className={`${size} ${i <= Math.round(n) ? 'fill-accent text-accent' : 'text-line'}`} />
      ))}
    </span>
  )
}

function Body({ d }: { d: DestinationDetail }) {
  const band = BAND[d.Score_Band]
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
        <Stat label="Reviews analysed" icon={MessageSquareText} value={int(d.Total_Reviews)} sub="Real visitor reviews compared with the marketing text" />
        <Stat label="Visitor rating" icon={Star}
          value={<>{d.Average_Rating.toFixed(2)}<span className="text-[16px] font-semibold text-slate-text"> / 5</span></>}
          sub={`${fmt(d.Positive_Pct, 0)}% of visitors rated it 4★ or higher`} />
      </section>

      {/* Gauge + Radar */}
      <section className="grid gap-6 lg:grid-cols-5">
        <div className="card flex flex-col p-6 lg:col-span-2">
          <h3 className="font-display text-[19px] font-bold">Reality Match Score</h3>
          <p className="helper">How closely reviews echo the marketing promise</p>
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
          <p className="helper">How often reviews mention each topic here, compared with a typical destination</p>
          <AspectBars
            series={[
              { name: 'This place', values: destPct, color: '#0D9488' },
              { name: 'Typical destination', values: avgPct, color: '#123B5D', muted: true },
            ]}
            notes={Object.fromEntries(d.Aspects.map((a) => [a.key, RELATIVE_SHORT[a.relative]]))} />
        </div>
      </section>

      {/* Promise vs Reality */}
      <section>
        <SectionTitle eyebrow="Expectation vs. experience" title="The promise and what visitors said"
          desc="The marketing description side by side with the real review that echoes it most closely." />
        <div className="grid gap-5 md:grid-cols-2">
          <div data-reveal className="rounded-tm border border-[#B4E9E2] bg-sky/70 p-6">
            <div className="flex items-center gap-2 text-[13px] font-semibold uppercase tracking-wider text-navy">
              <span className="grid h-8 w-8 place-items-center rounded-lg bg-white text-navy"><Megaphone className="h-4 w-4" /></span>
              The marketing promise
            </div>
            <blockquote className="mt-4 font-display text-[18px] font-semibold leading-relaxed text-navy-deep">“{d.Marketing_Promise}”</blockquote>
            <p className="helper mt-4">The expectation a traveller forms before visiting.</p>
          </div>
          <div data-reveal className="rounded-tm border border-[#BBF7D0] bg-[#DCFCE7] p-6">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-[13px] font-semibold uppercase tracking-wider text-[#15803D]">
                <span className="grid h-8 w-8 place-items-center rounded-lg bg-white text-success"><MessageCircleHeart className="h-4 w-4" /></span>
                A real visitor review
              </div>
              {d.Best_Review_Similarity != null && (
                <span className="rounded-full bg-white px-2.5 py-1 text-[11.5px] font-semibold text-[#15803D]">{fmt(d.Best_Review_Similarity)}% similar</span>
              )}
            </div>
            {d.Best_Review_Title && <h4 className="mt-4 text-[16px] font-semibold">{d.Best_Review_Title}</h4>}
            {d.Best_Review_Rating != null && <div className="mt-1"><Stars n={d.Best_Review_Rating} /></div>}
            <blockquote className="mt-2 text-[15px] leading-relaxed text-navy-deep">“{d.Best_Reality_Review}”</blockquote>
            <p className="helper mt-4">The review whose meaning is closest to the promise (highest cosine similarity).</p>
          </div>
        </div>
      </section>

      {/* Tips */}
      <section id="tips" className="scroll-mt-24">
        <SectionTitle eyebrow="From your helpful local friend" title="Pro-tips for a great visit"
          desc="Based on what visitors mention most compared with other destinations." />
        <div className="grid gap-4 md:grid-cols-2">
          {d.Tips.map((t, i) => <TipCard key={i} tip={t} />)}
        </div>
      </section>

      {/* Aspect breakdown */}
      <section>
        <SectionTitle eyebrow="Aspect insights" title="The four things travellers notice"
          desc="Bars show how often reviews mention each aspect here; the dark marker is the average destination." />
        <div className="grid gap-4 md:grid-cols-2">
          {d.Aspects.map((a) => <AspectCard key={a.key} a={a} />)}
        </div>
      </section>

      {/* Explainability */}
      <section className="grid gap-6 lg:grid-cols-5">
        <div className="card p-6 lg:col-span-3">
          <h3 className="font-display text-[19px] font-bold">How individual reviews compare</h3>
          <p className="helper">Number of reviews at each similarity level to the marketing text</p>
          <div className="mt-3"><Distribution data={d.Score_Distribution} /></div>
        </div>
        <div data-reveal className="flex flex-col rounded-tm border border-line bg-[#EEF3F7] p-6 lg:col-span-2">
          <div className="flex items-center gap-3">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-white text-navy"><ShieldCheck className="h-5 w-5" /></span>
            <h3 className="font-display text-[18px] font-bold">Explainability report</h3>
          </div>
          <ul className="mt-4 space-y-2.5 text-[13.5px] leading-relaxed">
            <li>• {int(d.Total_Reviews)} reviews and the marketing text were embedded with <b className="text-navy-deep">paraphrase-multilingual-mpnet-base-v2</b> (768-dimension vectors).</li>
            <li>• Each review gets a cosine similarity to the promise; the score is their average × 100.</li>
            <li>• Aspects are tagged with one shared keyword taxonomy designed for destinations rather than hotels (whole-word and phrase matching).</li>
            <li>• Tips are triggered when an aspect is mentioned at least 25% more (or less) often than at the average destination.</li>
            <li>• The score reflects similarity of meaning, not a check of whether each claim is true.</li>
          </ul>
        </div>
      </section>
    </div>
  )
}

function AspectCard({ a }: { a: AspectDetail }) {
  const m = ASPECT_META[a.key]
  return (
    <div className="card flex flex-col p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[11.5px] font-semibold uppercase tracking-wider" style={{ color: m.color }}>{m.label}</div>
          <h4 className="text-[16.5px] font-semibold">{m.friendly}</h4>
          <p className="helper mt-0.5">{m.desc}</p>
        </div>
        <div className="text-right">
          <div className="font-display text-[24px] font-extrabold text-navy-deep">{fmt(a.share_pct)}%</div>
          <div className="text-[11px] text-slate-text">{int(a.mentions)} reviews</div>
        </div>
      </div>
      <div className="mt-4"><ShareBar value={a.share_pct} avg={a.dataset_avg_pct} color={m.color} /></div>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[12px]">
        <span className="chip" style={a.relative === 'above' ? { background: '#DDF5F2', borderColor: '#B4E9E2', color: '#172B3A' } : undefined}>
          {RELATIVE_LABEL[a.relative]}
        </span>
        <span className="text-slate-text">Average destination: {fmt(a.dataset_avg_pct)}%</span>
      </div>
      {a.positive_pct != null && (
        <p className="mt-3 text-[13px]">
          <b className="text-navy-deep">{fmt(a.positive_pct, 0)}%</b> of visitors who mentioned this rated their visit 4★ or higher.
        </p>
      )}
      {a.snippet && (
        <figure className="mt-3 rounded-xl bg-offwhite p-3.5">
          <Quote className="h-4 w-4 text-teal-bright" />
          <blockquote className="mt-1 text-[13.5px] italic leading-relaxed text-navy-deep">{a.snippet.text}</blockquote>
          <figcaption className="mt-1.5 flex items-center gap-2 text-[11.5px] text-slate-text">
            <Stars n={a.snippet.rating} size="h-3 w-3" /> Visitor review
          </figcaption>
        </figure>
      )}
    </div>
  )
}
