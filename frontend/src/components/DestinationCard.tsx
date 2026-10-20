import { Link } from 'react-router-dom'
import { MapPin, MessageSquareText, ArrowRight } from 'lucide-react'
import type { DestinationSummary } from '../api/types'
import { ASPECT_META, BAND, destPath, int } from '../lib/format'
import { ScoreRing } from './charts'
import Scene from './Scene'

export default function DestinationCard({ d, highlight }: { d: DestinationSummary; highlight?: string }) {
  const band = BAND[d.band]
  return (
    <article className="card fade-in flex flex-col overflow-hidden transition-shadow hover:shadow-lift sm:flex-row">
      <Link to={destPath(d.name)} className="relative block h-44 shrink-0 sm:h-auto sm:w-[240px]">
        <Scene name={d.name} type={d.type} className="h-full w-full" />
        <span className="absolute left-3 top-3 rounded-md bg-white/95 px-2 py-1 text-[11px] font-bold text-navy-deep shadow">
          #{d.rank} <span className="font-medium text-slate-text">RANK</span>
        </span>
        {highlight && (
          <span className="absolute inset-x-0 bottom-0 bg-navy/95 py-1.5 text-center text-[11px] font-bold uppercase tracking-[0.14em] text-white">
            {highlight}
          </span>
        )}
      </Link>
      <div className="flex min-w-0 flex-1 flex-col p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <Link to={destPath(d.name)} className="font-display text-[19px] font-bold text-navy-deep hover:text-teal">{d.name}</Link>
            <div className="mt-0.5 flex items-center gap-1 text-[13px]">
              <MapPin className="h-3.5 w-3.5" />{d.city !== d.district ? `${d.city}, ` : ''}{d.district} · {d.province}
            </div>
          </div>
          <div className="flex shrink-0 gap-3">
            <ScoreRing value={d.score} label="Match" color={band.color} />
            <ScoreRing value={d.positive_pct} label="Rated 4★+" color="#14B8A6" />
          </div>
        </div>
        <p className="mt-3 text-[14px] leading-relaxed">
          <span className="font-semibold" style={{ color: band.text }}>{band.label}.</span>{' '}
          {d.rank === 1 ? 'The highest reality match of all destinations analysed.' : `Higher reality match than ${Math.round(d.percentile)}% of other destinations.`}{' '}
          Visitors talk most about <span className="font-medium text-navy-deep">{ASPECT_META[d.top_aspect].friendly.toLowerCase()}</span>.
        </p>
        <div className="mt-3 flex flex-wrap gap-1.5">
          <span className="chip">{d.type}</span>
          <span className="chip">{ASPECT_META[d.top_aspect].label}</span>
        </div>
        <div className="mt-auto flex flex-wrap items-end justify-between gap-3 border-t border-line pt-3 sm:mt-4">
          <div className="flex gap-6">
            <div>
              <div className="text-[10.5px] font-semibold uppercase tracking-wider text-slate-text">Reviews</div>
              <div className="flex items-center gap-1 text-[13px] font-semibold text-navy-deep">
                <MessageSquareText className="h-3.5 w-3.5 text-teal" />{int(d.total_reviews)}
              </div>
            </div>
            <div>
              <div className="text-[10.5px] font-semibold uppercase tracking-wider text-slate-text">Avg rating</div>
              <div className="text-[13px] font-semibold text-navy-deep">{d.avg_rating.toFixed(2)} / 5</div>
            </div>
          </div>
          <Link to={destPath(d.name)} className="btn-primary py-2">View insight <ArrowRight className="h-4 w-4" /></Link>
        </div>
      </div>
    </article>
  )
}
