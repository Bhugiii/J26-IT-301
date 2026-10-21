import { useEffect } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import Layout from '../components/Layout'
import PhotoHero from '../components/PhotoHero'
import { api, useApi } from '../api/client'
import type { DestinationDetail } from '../api/types'
import { ErrorState, Loading } from '../components/ui'
import { AspectBars, Gauge } from '../components/charts'
import Scene from '../components/Scene'
import { ASPECT_META, BAND, destPath, fmt, int } from '../lib/format'

const COLORS = ['#0D9488', '#123B5D']

export default function Compare() {
  const { data: ov, error: ovErr } = useApi('overview', api.overview)
  const [params, setParams] = useSearchParams()
  const names = ov ? [...ov.destinations].sort((a, b) => a.rank - b.rank).map((d) => d.name) : []
  const a = params.get('a') ?? names[0] ?? null
  const b = params.get('b') ?? names.find((n) => n !== a) ?? null
  const A = useApi(a ? `d:${a}` : null, () => api.destination(a!))
  const B = useApi(b ? `d:${b}` : null, () => api.destination(b!))

  const set = (k: 'a' | 'b', v: string) => {
    const p = new URLSearchParams(params)
    p.set('a', a ?? ''); p.set('b', b ?? ''); p.set(k, v)
    setParams(p, { replace: true })
  }

  // Partial names in the URL (e.g. ?a=galle) resolve on the server; write the
  // resolved names back so the dropdowns show what is actually compared.
  useEffect(() => {
    const ra = A.data?.Location_Name, rb = B.data?.Location_Name
    if ((ra && ra !== a) || (rb && rb !== b)) {
      const p = new URLSearchParams(params)
      if (ra) p.set('a', ra)
      if (rb) p.set('b', rb)
      setParams(p, { replace: true })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [A.data, B.data])

  const err = ovErr ?? A.error ?? B.error
  return (
    <Layout crumbs={['Compare']}>
      <div className="mb-6">
        <PhotoHero compact photo="/photos/turtle-snorkel.jpg" alt="Snorkeller swimming above a sea turtle over a coral reef" position="center 55%"
          eyebrow="Side by side" title="Compare destinations">
          <p className="mt-2 max-w-xl text-[15px] leading-relaxed text-white/85">Pick two places to see how their promise and visitor experience line up.</p>
        </PhotoHero>
      </div>
      {err && <ErrorState message={err} />}
      {!err && ov && (
        <div className="mb-6 grid gap-3 md:grid-cols-2">
          {(['a', 'b'] as const).map((k, i) => (
            <label key={k} className="card flex items-center gap-3 p-3">
              <span className="h-3 w-3 shrink-0 rounded-full" style={{ background: COLORS[i] }} />
              <select className="input border-0 px-1 py-1 font-semibold focus:ring-0" value={(k === 'a' ? a : b) ?? ''}
                onChange={(e) => set(k, e.target.value)} aria-label={`Destination ${i + 1}`}>
                {names.filter((n) => n !== (k === 'a' ? b : a)).map((n) => <option key={n}>{n}</option>)}
              </select>
            </label>
          ))}
        </div>
      )}
      {!err && (A.loading || B.loading || !ov) && <Loading />}
      {!err && A.data && B.data && <Body a={A.data} b={B.data} />}
    </Layout>
  )
}

function Body({ a, b }: { a: DestinationDetail; b: DestinationDetail }) {
  const pct = (d: DestinationDetail) => Object.fromEntries(d.Aspects.map((x) => [x.key, x.share_pct])) as Record<string, number>
  const rows: { label: string; fa: (d: DestinationDetail) => string }[] = [
    { label: 'Reality match', fa: (d) => `${fmt(d.Average_Reality_Score)}%` },
    { label: 'Match band', fa: (d) => BAND[d.Score_Band].label },
    { label: 'Ranking', fa: (d) => `#${d.Score_Rank}` },
    { label: 'Visitor rating', fa: (d) => `${d.Average_Rating.toFixed(2)} / 5` },
    { label: 'Rated 4★ or higher', fa: (d) => `${fmt(d.Positive_Pct, 0)}%` },
    { label: 'Reviews analysed', fa: (d) => int(d.Total_Reviews) },
    ...d4().map((k) => ({ label: `Reviews about ${ASPECT_META[k].friendly.toLowerCase()}`, fa: (d: DestinationDetail) => `${fmt(d.Aspects.find((x) => x.key === k)!.share_pct)}%` })),
  ]
  return (
    <div className="fade-in space-y-6">
      <div className="grid gap-5 md:grid-cols-2">
        {[a, b].map((d, i) => (
          <div key={d.Location_Name} className="card overflow-hidden">
            <div className="relative h-32">
              <Scene name={d.Location_Name} type={d.Location_Type} className="absolute inset-0" />
              <div className="absolute inset-0 bg-gradient-to-t from-navy-deep/85 to-transparent" />
              <div className="absolute bottom-3 left-4 right-4 text-white">
                <div className="text-[12px] text-white/80">{d.Location_Type} · {d.District}</div>
                <div className="font-display text-[20px] font-bold">{d.Location_Name}</div>
              </div>
              <span className="absolute right-3 top-3 h-3 w-3 rounded-full ring-2 ring-white" style={{ background: COLORS[i] }} />
            </div>
            <div className="flex flex-col items-center p-5">
              <Gauge value={d.Average_Reality_Score} avg={d.Dataset_Avg_Score} color={BAND[d.Score_Band].color} />
              <Link to={destPath(d.Location_Name)} className="mt-3 inline-flex items-center gap-1 text-[14px] font-semibold text-teal-dark hover:underline">
                Full insight <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </div>
        ))}
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card p-6">
          <h3 className="font-display text-[19px] font-bold">What visitors talk about</h3>
          <p className="helper">How often reviews mention each topic at each place</p>
          <AspectBars series={[
            { name: a.Location_Name, values: pct(a) as never, color: COLORS[0] },
            { name: b.Location_Name, values: pct(b) as never, color: COLORS[1] },
          ]} />
        </div>
        <div className="card overflow-hidden">
          <table className="w-full text-[13.5px]">
            <thead>
              <tr className="bg-offwhite text-left">
                <th className="px-4 py-3 font-semibold text-slate-text">Metric</th>
                {[a, b].map((d, i) => (
                  <th key={i} className="px-4 py-3 font-semibold text-navy-deep">
                    <span className="mr-1.5 inline-block h-2 w-2 rounded-full" style={{ background: COLORS[i] }} />{d.Location_Name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.label} className="border-t border-line">
                  <td className="px-4 py-2.5 text-slate-text">{r.label}</td>
                  <td className="px-4 py-2.5 font-medium text-navy-deep">{r.fa(a)}</td>
                  <td className="px-4 py-2.5 font-medium text-navy-deep">{r.fa(b)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function d4() { return ['Crowding', 'Facilities', 'Commercialization', 'Accessibility'] as const }
