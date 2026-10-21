import { ResponsiveContainer, Tooltip, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts'
import { Users, Building2, ShoppingBag, Footprints } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { AspectKey } from '../api/types'
import { ASPECTS } from '../api/types'
import { ASPECT_META, fmt } from '../lib/format'

/** Small circular score ring, like the MATCH / ECO rings in the reference designs. */
export function ScoreRing({ value, label, color = '#0D9488', size = 56 }: {
  value: number; label: string; color?: string; size?: number
}) {
  const r = (size - 8) / 2
  const c = 2 * Math.PI * r
  const v = Math.max(0, Math.min(100, value))
  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle cx={size / 2} cy={size / 2} r={r} stroke="#E8EEF3" strokeWidth="4" fill="none" />
          <circle cx={size / 2} cy={size / 2} r={r} stroke={color} strokeWidth="4" fill="none"
            strokeLinecap="round" strokeDasharray={`${(v / 100) * c} ${c}`} />
        </svg>
        <span className="absolute inset-0 grid place-items-center text-[13px] font-bold text-navy-deep">{Math.round(v)}%</span>
      </div>
      <span className="text-[10.5px] font-semibold uppercase tracking-wider text-slate-text">{label}</span>
    </div>
  )
}

/**
 * Semi-circular gauge for the Reality Match Score (0–100).
 * Band boundaries (45 / 60) match the backend's alignment thresholds.
 */
export function Gauge({ value, avg, color }: { value: number; avg: number; color: string }) {
  const W = 300, H = 170, cx = W / 2, cy = 150, r = 120
  const toXY = (p: number, rr = r) => {
    const a = Math.PI * (1 - p / 100)
    return [cx + rr * Math.cos(a), cy - rr * Math.sin(a)] as const
  }
  const arc = (from: number, to: number) => {
    const [x1, y1] = toXY(from), [x2, y2] = toXY(to)
    return `M ${x1} ${y1} A ${r} ${r} 0 0 1 ${x2} ${y2}`
  }
  const [ax, ay] = toXY(avg, r + 14)
  const [ax2, ay2] = toXY(avg, r - 14)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-[320px]" role="img"
      aria-label={`Reality match score ${fmt(value)} out of 100`}>
      <path d={arc(0, 45)} stroke="#E3EAF1" strokeWidth="20" fill="none" />
      <path d={arc(45, 60)} stroke="#DDF5F2" strokeWidth="20" fill="none" />
      <path d={arc(60, 100)} stroke="#DCFCE7" strokeWidth="20" fill="none" />
      <path d={arc(0.01, Math.max(0.5, value))} stroke={color} strokeWidth="20" fill="none" strokeLinecap="round" />
      <line x1={ax} y1={ay} x2={ax2} y2={ay2} stroke="#172B3A" strokeWidth="2" strokeDasharray="3 3" />
      <text x={ax} y={ay - 6} textAnchor="middle" className="fill-slate-text" fontSize="10" fontWeight={600}>avg</text>
      <text x={cx} y={cy - 28} textAnchor="middle" fill="#172B3A" fontSize="44" fontWeight={800} fontFamily="Manrope">
        {fmt(value)}
      </text>
      <text x={cx} y={cy - 6} textAnchor="middle" fill="#64748B" fontSize="12" fontWeight={600}>% REALITY MATCH</text>
      <text x={cx - r} y={cy + 18} textAnchor="middle" fill="#64748B" fontSize="10">0</text>
      <text x={cx + r} y={cy + 18} textAnchor="middle" fill="#64748B" fontSize="10">100</text>
    </svg>
  )
}

/**
 * Tourist-friendly aspect chart: one row per topic, plain-language label,
 * a horizontal bar per series with the % printed on it. Replaces the radar.
 */
const ASPECT_ICONS: Record<AspectKey, LucideIcon> = {
  Crowding: Users, Facilities: Building2, Commercialization: ShoppingBag, Accessibility: Footprints,
}

export function AspectBars({ series, notes }: {
  series: { name: string; values: Record<AspectKey, number>; color: string; muted?: boolean }[]
  notes?: Partial<Record<AspectKey, string>>
}) {
  const max = Math.max(10, ...series.flatMap((s) => ASPECTS.map((a) => s.values[a])))
  const scale = Math.ceil(max / 10) * 10
  return (
    <div className="mt-4 space-y-5">
      <div className="flex flex-wrap gap-4 text-[12.5px]">
        {series.map((s) => (
          <span key={s.name} className="inline-flex items-center gap-2 text-slate-text">
            <span className="h-2.5 w-5 rounded-full" style={{ background: s.color, opacity: s.muted ? 0.45 : 1 }} />{s.name}
          </span>
        ))}
      </div>
      {ASPECTS.map((a) => {
        const Icon = ASPECT_ICONS[a]
        return (
          <div key={a} data-reveal>
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <span className="flex items-center gap-2 text-[14.5px] font-semibold text-navy-deep">
                <span className="grid h-8 w-8 place-items-center rounded-lg bg-[#E6F6F4] text-teal-dark"><Icon className="h-4 w-4" /></span>
                {ASPECT_META[a].friendly}
              </span>
              {notes?.[a] && <span className="chip">{notes[a]}</span>}
            </div>
            <div className="space-y-1.5">
              {series.map((s) => (
                <div key={s.name} className="flex items-center gap-3">
                  <div className="h-3.5 flex-1 overflow-hidden rounded-full bg-[#EEF2F6]">
                    <div className="bar-grow h-full rounded-full" style={{ width: `${(s.values[a] / scale) * 100}%`, background: s.color, opacity: s.muted ? 0.45 : 1 }} />
                  </div>
                  <span className="w-12 shrink-0 text-right text-[13px] font-semibold text-navy-deep">{Math.round(s.values[a])}%</span>
                </div>
              ))}
            </div>
          </div>
        )
      })}
      <p className="helper">Percent of reviews that mention each topic. A mention is not a complaint: many are positive.</p>
    </div>
  )
}

export function Distribution({ data }: { data: { bin: string; count: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height={180}>
      <BarChart data={data} margin={{ top: 8, right: 4, left: -18, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke="#EEF2F6" />
        <XAxis dataKey="bin" tick={{ fill: '#64748B', fontSize: 10 }} tickLine={false} axisLine={{ stroke: '#D9E2EA' }} />
        <YAxis tick={{ fill: '#64748B', fontSize: 10 }} tickLine={false} axisLine={false} allowDecimals={false} />
        <Tooltip cursor={{ fill: '#F2F8FA' }} formatter={(v: number) => [`${v} reviews`, 'Reviews']}
          labelFormatter={(l) => `Similarity ${l}%`} contentStyle={{ borderRadius: 10, border: '1px solid #D9E2EA', fontSize: 12 }} />
        <Bar dataKey="count" fill="#14B8A6" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}

/** Horizontal comparison bar: destination share vs dataset average marker. */
export function ShareBar({ value, avg, color }: { value: number; avg: number; color: string }) {
  const scale = Math.max(60, value, avg) * 1.1
  return (
    <div className="relative h-2.5 rounded-full bg-[#EEF2F6]">
      <div className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${(value / scale) * 100}%`, background: color }} />
      <div className="absolute -top-1 h-[18px] w-[2px] rounded bg-navy-deep/70" style={{ left: `${(avg / scale) * 100}%` }}
        title={`Average across all destinations: ${fmt(avg)}%`} />
    </div>
  )
}
