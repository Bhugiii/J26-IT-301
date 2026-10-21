import { useState } from 'react'
import {
  Sunrise, Banknote, Handshake, Backpack, Toilet, Footprints, Car, Coffee, Shirt, Camera, Waves, Sun, Binoculars,
  VolumeX, Leaf, Umbrella, Ticket, Droplets, Clock, Map as MapIcon, CupSoda, Compass, Fish, BookOpen,
  CalendarCheck, DoorOpen, Users, Building2, ShoppingBag, Star, Check, MessageCircleHeart,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { AspectDetail, AspectKey } from '../api/types'
import { ASPECTS } from '../api/types'
import { ASPECT_META, RELATIVE_LABEL } from '../lib/format'
import type { TipIcon, TipWhen, VisitTip } from '../lib/tips'
import { WHEN_LABEL } from '../lib/tips'

export const ASPECT_ICON: Record<AspectKey, LucideIcon> = {
  Crowding: Users, Facilities: Building2, Commercialization: ShoppingBag, Accessibility: Footprints,
}

const TIP_ICON: Record<TipIcon, LucideIcon> = {
  sunrise: Sunrise, cash: Banknote, handshake: Handshake, backpack: Backpack, toilet: Toilet, shoe: Footprints,
  car: Car, pause: Coffee, shirt: Shirt, footprints: Footprints, camera: Camera, waves: Waves, sun: Sun,
  binoculars: Binoculars, volume: VolumeX, leaf: Leaf, umbrella: Umbrella, ticket: Ticket, droplet: Droplets,
  clock: Clock, map: MapIcon, cup: CupSoda, compass: Compass, fish: Fish, book: BookOpen,
}
const WHEN_ICON: Record<TipWhen, LucideIcon> = { before: CalendarCheck, arrive: DoorOpen, during: Compass }

export function Stars({ n, size = 'h-3.5 w-3.5' }: { n: number; size?: string }) {
  return (
    <span className="inline-flex" role="img" aria-label={`${n} out of 5 stars`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <Star key={i} className={`${size} ${i <= Math.round(n) ? 'fill-accent text-accent' : 'text-line'}`} />
      ))}
    </span>
  )
}

/** Long review text, clamped with a "Read more" toggle. */
export function ExpandableText({ text, lines = 5, className = '' }: { text: string; lines?: number; className?: string }) {
  const [open, setOpen] = useState(false)
  const long = text.length > lines * 70
  return (
    <div>
      <p className={className} style={!open && long ? {
        display: '-webkit-box', WebkitLineClamp: lines, WebkitBoxOrient: 'vertical', overflow: 'hidden',
      } : undefined}>{text}</p>
      {long && (
        <button onClick={() => setOpen(!open)} className="mt-1.5 text-[13px] font-semibold text-teal-dark hover:underline">
          {open ? 'Show less' : 'Read more'}
        </button>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Part 1 — Pro tips, grouped by when to use them
// ---------------------------------------------------------------------------
export function TipsTimeline({ tips }: { tips: VisitTip[] }) {
  const groups = (['before', 'arrive', 'during'] as TipWhen[]).map((w) => ({ w, items: tips.filter((t) => t.when === w) }))
    .filter((g) => g.items.length)
  return (
    <div className="space-y-6">
      {groups.map(({ w, items }, gi) => {
        const WIcon = WHEN_ICON[w]
        return (
          <div key={w}>
            <div data-reveal className="flex items-center gap-3 rounded-tm bg-navy px-4 py-3 text-white">
              <span className="grid h-9 w-9 place-items-center rounded-lg bg-white/15"><WIcon className="h-[18px] w-[18px]" /></span>
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[#99F6E4]">Step {gi + 1}</div>
                <div className="font-display text-[16.5px] font-bold leading-tight text-white">{WHEN_LABEL[w].title}</div>
              </div>
              <span className="ml-auto text-[13px] text-white/75">{WHEN_LABEL[w].hint} · {items.length} {items.length === 1 ? 'tip' : 'tips'}</span>
            </div>
            <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {items.map((t) => {
              const Icon = TIP_ICON[t.icon] ?? Compass
              return (
                <article key={t.id} className="card h-full p-4">
                  <div className="flex items-start gap-3">
                    <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-[#E6F6F4] text-teal-dark"><Icon className="h-[18px] w-[18px]" /></span>
                    <div className="min-w-0">
                      <h4 className="text-[15px] font-semibold leading-snug text-navy-deep">{t.title}</h4>
                      <p className="mt-1 text-[14px] leading-relaxed text-navy-deep/90">{t.action}</p>
                      <p className="mt-1.5 text-[13px] leading-relaxed text-slate-text"><span className="font-semibold text-teal-dark">Why it helps: </span>{t.why}</p>
                      {t.fromReviews && (
                        <span className="mt-2 inline-flex items-center gap-1 rounded-full bg-[#FEF6E4] px-2 py-0.5 text-[11.5px] font-semibold text-[#8A5A00]">
                          <MessageCircleHeart className="h-3 w-3" /> Based on visitor reviews of this place
                        </span>
                      )}
                    </div>
                  </div>
                </article>
              )
            })}
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Part 2 — The four things travellers notice, with a reading guide
// ---------------------------------------------------------------------------
const LEVELS: { key: AspectDetail['relative']; label: string }[] = [
  { key: 'below', label: 'Rarely' }, { key: 'typical', label: 'Average' }, { key: 'above', label: 'A lot' },
]

export function AspectInsightCard({ a }: { a: AspectDetail }) {
  const m = ASPECT_META[a.key]
  const Icon = ASPECT_ICON[a.key]
  const happy = a.positive_pct != null ? Math.round(a.positive_pct / 10) : null
  return (
    <article className="card flex flex-col p-5">
      <div className="flex items-start gap-3">
        <span className="grid h-11 w-11 shrink-0 place-items-center rounded-lg text-white" style={{ background: m.color }}>
          <Icon className="h-5 w-5" />
        </span>
        <div>
          <h4 className="font-display text-[17px] font-bold leading-snug">{m.friendly}</h4>
          <p className="mt-0.5 text-[13.5px] leading-relaxed">{m.desc}</p>
        </div>
      </div>

      {/* Reading guide: a simple three-step scale */}
      <div className="mt-4">
        <div className="mb-1.5 flex items-center justify-between text-[12px] font-semibold text-slate-text">
          <span>How much visitors talk about it here</span>
          <span className="text-navy-deep">{RELATIVE_LABEL[a.relative]}</span>
        </div>
        <div className="grid grid-cols-3 gap-1.5" role="img" aria-label={`Level: ${RELATIVE_LABEL[a.relative]}`}>
          {LEVELS.map((l) => {
            const on = l.key === a.relative
            return (
              <div key={l.key} className={`flex items-center justify-center gap-1 rounded-lg py-2 text-[12.5px] font-semibold transition-colors ${
                on ? 'text-white shadow-card' : 'bg-[#EEF2F6] text-slate-text'}`} style={on ? { background: m.color } : undefined}>
                {on && <Check className="h-3.5 w-3.5" />}{l.label}
              </div>
            )
          })}
        </div>
      </div>

      <div className="mt-4 rounded-lg border border-line bg-offwhite p-3.5">
        <div className="text-[11.5px] font-semibold uppercase tracking-[0.1em] text-teal-dark">What this means for you</div>
        <p className="mt-1 text-[14px] leading-relaxed text-navy-deep">{m.guide[a.relative]}</p>
      </div>

      <div className="mt-auto flex flex-wrap gap-x-5 gap-y-1 pt-4 text-[12.5px] text-slate-text">
        <span><b className="text-navy-deep">{Math.round(a.share_pct)}%</b> of reviews mention it (typical place: {Math.round(a.dataset_avg_pct)}%)</span>
        {happy != null && <span><b className="text-navy-deep">{happy} in 10</b> of those visitors gave 4 or 5 stars</span>}
      </div>
    </article>
  )
}

// ---------------------------------------------------------------------------
// Part 3 — Real reviews side by side, one per topic
// ---------------------------------------------------------------------------
const MOOD = (r: number) => r >= 5 ? 'Loved it' : r >= 4 ? 'Liked it' : r >= 3 ? 'Mixed feelings' : 'Not impressed'

export function ReviewsSideBySide({ aspects }: { aspects: AspectDetail[] }) {
  const [picked, setPicked] = useState<AspectKey[]>([])
  const toggle = (k: AspectKey) => setPicked((p) => (p.includes(k) ? p.filter((x) => x !== k) : [...p, k]))
  const withSnip = ASPECTS.map((k) => aspects.find((a) => a.key === k)!).filter((a) => a && a.snippet)

  return (
    <div>
      <div data-reveal className="mb-4 flex flex-wrap items-center gap-2">
        <span className="mr-1 text-[13.5px] font-semibold text-navy-deep">What matters most to you?</span>
        {withSnip.map((a) => {
          const on = picked.includes(a.key)
          const Icon = ASPECT_ICON[a.key]
          return (
            <button key={a.key} onClick={() => toggle(a.key)} aria-pressed={on}
              className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[13px] font-medium transition-colors ${
                on ? 'border-teal bg-teal text-white' : 'border-line bg-white text-navy hover:border-teal hover:text-teal-dark'}`}>
              <Icon className="h-3.5 w-3.5" />{ASPECT_META[a.key].friendly}
            </button>
          )
        })}
        {picked.length > 0 && (
          <button onClick={() => setPicked([])} className="text-[13px] font-semibold text-teal-dark hover:underline">Show all</button>
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {withSnip.map((a) => {
          const m = ASPECT_META[a.key]
          const Icon = ASPECT_ICON[a.key]
          const dim = picked.length > 0 && !picked.includes(a.key)
          const r = a.snippet!.rating
          return (
            <article key={a.key} className={`card flex flex-col overflow-hidden transition-opacity duration-300 ${dim ? 'opacity-40' : ''} ${
              picked.includes(a.key) ? 'ring-2 ring-teal' : ''}`}>
              <div className="flex items-center gap-2 px-4 py-3 text-white" style={{ background: m.color }}>
                <Icon className="h-4 w-4" />
                <span className="text-[13.5px] font-semibold">{m.friendly}</span>
              </div>
              <div className="flex flex-1 flex-col p-4">
                <div className="flex items-center justify-between gap-2">
                  <Stars n={r} />
                  <span className={`rounded-full px-2 py-0.5 text-[11.5px] font-semibold ${
                    r >= 4 ? 'bg-[#DCFCE7] text-[#15803D]' : 'bg-[#EEF2F6] text-navy'}`}>{MOOD(r)}</span>
                </div>
                {a.snippet!.title && <h4 className="mt-2.5 text-[14.5px] font-semibold leading-snug">{a.snippet!.title}</h4>}
                <ExpandableText text={`“${a.snippet!.text}”`} lines={5} className="mt-1.5 text-[13.5px] leading-relaxed text-navy-deep/90" />
                <dl className="mt-auto grid grid-cols-2 gap-2 border-t border-line pt-3 text-[12px]">
                  <div>
                    <dt className="text-slate-text">Talked about</dt>
                    <dd className="font-semibold text-navy-deep">{a.relative === 'above' ? 'A lot' : a.relative === 'below' ? 'Rarely' : 'Average'}</dd>
                  </div>
                  <div>
                    <dt className="text-slate-text">Happy visitors</dt>
                    <dd className="font-semibold text-navy-deep">{a.positive_pct != null ? `${Math.round(a.positive_pct / 10)} in 10` : 'Not enough reviews'}</dd>
                  </div>
                </dl>
              </div>
            </article>
          )
        })}
      </div>
    </div>
  )
}
