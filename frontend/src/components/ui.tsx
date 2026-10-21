import { Sunrise, Leaf, ShoppingBag, Footprints, Backpack, Sparkles, Camera, Map as MapIcon, RefreshCw, Compass } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { Tip } from '../api/types'

const TIP_ICONS: Record<string, LucideIcon> = {
  sunrise: Sunrise, leaf: Leaf, bag: ShoppingBag, boot: Footprints, backpack: Backpack,
  sparkles: Sparkles, camera: Camera, map: MapIcon,
}

export function TipCard({ tip }: { tip: Tip }) {
  const Icon = TIP_ICONS[tip.icon] ?? Sparkles
  return (
    <div className="card group flex gap-4 p-5 transition-shadow hover:shadow-lift">
      <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-sky text-teal">
        <Icon className="h-5 w-5" />
      </span>
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h4 className="text-[15.5px] font-semibold">{tip.title}</h4>
          {tip.aspect && <span className="chip py-0 text-[11px]">{tip.aspect}</span>}
        </div>
        <p className="mt-1 text-[14px] leading-relaxed">{tip.body}</p>
      </div>
    </div>
  )
}

export function Stat({ label, value, sub, icon: Icon }: {
  label: string; value: React.ReactNode; sub?: React.ReactNode; icon?: LucideIcon
}) {
  return (
    <div className="card p-5">
      <div className="flex items-start justify-between">
        <span className="text-[12px] font-semibold uppercase tracking-[0.1em] text-slate-text">{label}</span>
        {Icon && <Icon className="h-[18px] w-[18px] text-teal" />}
      </div>
      <div className="mt-2 font-display text-[28px] font-extrabold leading-none text-navy-deep">{value}</div>
      {sub && <div className="mt-2 border-l-2 border-line pl-2 text-[12.5px] italic text-slate-text">{sub}</div>}
    </div>
  )
}

export function Loading({ label = 'Loading insights…' }: { label?: string }) {
  return (
    <div className="grid min-h-[50vh] place-items-center">
      <div className="flex flex-col items-center gap-3 text-slate-text">
        <Compass className="h-8 w-8 animate-spin text-teal [animation-duration:2.4s]" />
        <span className="text-[14px]">{label}</span>
      </div>
    </div>
  )
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="card mx-auto mt-10 max-w-xl p-8 text-center">
      <div className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-sky text-teal"><RefreshCw className="h-5 w-5" /></div>
      <h3 className="mt-4 font-display text-[20px] font-bold">We couldn't load this just now</h3>
      <p className="mt-2 text-[14px]">{message}</p>
      <p className="mt-3 text-[13px]">
        Make sure the backend is running: <code className="rounded bg-offwhite px-1.5 py-0.5 text-navy">uvicorn main:app --reload</code> in the <code className="rounded bg-offwhite px-1.5 py-0.5 text-navy">backend</code> folder.
      </p>
      <button className="btn-primary mt-5" onClick={() => location.reload()}>Try again</button>
    </div>
  )
}

export function SectionTitle({ eyebrow, title, desc, right }: {
  eyebrow?: string; title: string; desc?: string; right?: React.ReactNode
}) {
  return (
    <div data-reveal className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        {eyebrow && <div className="eyebrow mb-1">{eyebrow}</div>}
        <h2 className="font-display text-[22px] font-bold">{title}</h2>
        {desc && <p className="mt-1 max-w-2xl text-[14px]">{desc}</p>}
      </div>
      {right}
    </div>
  )
}
