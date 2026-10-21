import { useEffect, useState } from 'react'
import { slug } from '../lib/format'

// /images/manifest.json lists available photo slugs, e.g. ["galle-fort"].
// Loaded once; without it no photo requests are made.
let manifest: Promise<Set<string>> | null = null
function photoManifest() {
  manifest ??= fetch('/images/manifest.json')
    .then((r) => (r.ok ? r.json() : []))
    .then((l: unknown) => new Set(Array.isArray(l) ? (l as string[]) : []))
    .catch(() => new Set<string>())
  return manifest
}

/**
 * Coastal photos supplied for the project, used where they truthfully fit:
 * reef/turtle photo for the snorkelling and turtle spots, coastline photos for beaches.
 * They show the Sri Lankan coast in general (not the exact beach), so they carry a
 * small "Sri Lankan coast" caption.
 */
const COAST_PHOTOS = ['/photos/coast-aerial.jpg', '/photos/sri-lanka-sand.jpg', '/photos/stilt-fishermen.jpg']
const REEF = ['Pigeon Island National Park', 'Hikkaduwa Beach']
function stockPhoto(name: string, type: string): { src: string; caption: string } | null {
  if (REEF.includes(name)) return { src: '/photos/turtle-snorkel.jpg', caption: 'Sri Lankan reef' }
  if (type === 'Beaches') return { src: COAST_PHOTOS[hash(name) % COAST_PHOTOS.length], caption: 'Sri Lankan coast' }
  return null
}

/**
 * Destination visual. Priority: an exact photo listed in /images/manifest.json,
 * then a fitting project photo (coastal places), then an illustrated scene
 * drawn for the destination type.
 */
export default function Scene({ name, type, className = '', rounded = '' }: {
  name: string; type: string; className?: string; rounded?: string
}) {
  const [photoOk, setPhotoOk] = useState(false)
  const stock = stockPhoto(name, type)
  useEffect(() => {
    let alive = true
    photoManifest().then((m) => { if (alive) setPhotoOk(m.has(slug(name))) })
    return () => { alive = false }
  }, [name])
  return (
    <div className={`${/\babsolute\b/.test(className) ? '' : 'relative'} overflow-hidden bg-navy ${rounded} ${className}`}>
      <Illustration name={name} type={type} />
      {!photoOk && stock && (
        <>
          <img src={stock.src} alt="" loading="lazy" className="absolute inset-0 h-full w-full object-cover" />
          <span className="absolute bottom-2 right-2 rounded bg-black/45 px-1.5 py-0.5 text-[10px] font-medium text-white/90">{stock.caption}</span>
        </>
      )}
      {photoOk && (
        <img
          src={`/images/${slug(name)}.jpg`}
          alt=""
          loading="lazy"
          onError={() => setPhotoOk(false)}
          className="absolute inset-0 h-full w-full object-cover"
        />
      )}
    </div>
  )
}

function hash(s: string) {
  let h = 0
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0
  return h
}

const SKIES = [
  ['#172B3A', '#0D9488', '#DDF5F2'],
  ['#123B5D', '#14B8A6', '#E6F6F4'],
  ['#172B3A', '#1F6E7A', '#CDEFEA'],
]

function Illustration({ name, type }: { name: string; type: string }) {
  const h = hash(name)
  const sky = SKIES[h % SKIES.length]
  const sunX = 60 + (h % 280)
  const id = `g${h}`
  return (
    <svg viewBox="0 0 400 240" preserveAspectRatio="xMidYMid slice" className="absolute inset-0 h-full w-full" aria-hidden>
      <defs>
        <linearGradient id={`${id}s`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={sky[0]} />
          <stop offset="0.6" stopColor={sky[1]} />
          <stop offset="1" stopColor={sky[2]} />
        </linearGradient>
        <radialGradient id={`${id}u`}>
          <stop offset="0" stopColor="#FFFFFF" stopOpacity="0.95" />
          <stop offset="1" stopColor="#FFFFFF" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width="400" height="240" fill={`url(#${id}s)`} />
      <circle cx={sunX} cy={70 + (h % 30)} r="70" fill={`url(#${id}u)`} opacity="0.55" />
      <circle cx={sunX} cy={70 + (h % 30)} r="16" fill="#FFFFFF" opacity="0.9" />
      <Layer type={type} h={h} />
    </svg>
  )
}

function Hills({ h, y = 170, c1 = '#1D5470', c2 = '#123B5D' }: { h: number; y?: number; c1?: string; c2?: string }) {
  const a = 20 + (h % 30)
  return (
    <>
      <path d={`M0 ${y} Q 90 ${y - 50 - a} 190 ${y - 10} T 400 ${y - 20} V240 H0Z`} fill={c1} opacity="0.85" />
      <path d={`M0 ${y + 25} Q 120 ${y - 15} 230 ${y + 20} T 400 ${y + 5} V240 H0Z`} fill={c2} />
    </>
  )
}

function Layer({ type, h }: { type: string; h: number }) {
  switch (type) {
    case 'Beaches':
      return (
        <>
          <rect y="150" width="400" height="90" fill="#0D9488" />
          {[160, 175, 190].map((y, i) => (
            <path key={y} d={`M0 ${y} q 25 -6 50 0 t 50 0 t 50 0 t 50 0 t 50 0 t 50 0 t 50 0 t 50 0`} stroke="#DDF5F2" strokeOpacity={0.5 - i * 0.12} fill="none" strokeWidth="2" />
          ))}
          <path d="M0 205 Q 200 185 400 210 V240 H0Z" fill="#F1E6CF" />
          <g transform={`translate(${h % 2 ? 320 : 70} 205)`} fill="#172B3A">
            <path d="M0 0 C 4 -40 10 -70 22 -95" stroke="#172B3A" strokeWidth="5" fill="none" />
            <path d="M22 -95 q -30 -5 -45 12 q 22 -8 45 -12 q 10 -25 38 -28 q -25 15 -38 28 q 30 -4 42 14 q -24 -10 -42 -14 q -12 22 -35 30 q 20 -15 35 -30Z" />
          </g>
        </>
      )
    case 'Bodies of Water':
      return (
        <>
          <Hills h={h} y={150} />
          <rect y="185" width="400" height="55" fill="#14B8A6" opacity="0.9" />
          <path d="M40 200 h60 M180 212 h90 M300 198 h50" stroke="#DDF5F2" strokeWidth="2" opacity="0.7" />
        </>
      )
    case 'Farms':
      return (
        <>
          <Hills h={h} y={150} c1="#16A34A" c2="#166534" />
          {Array.from({ length: 7 }).map((_, i) => (
            <path key={i} d={`M-10 ${180 + i * 9} Q 200 ${165 + i * 9} 410 ${185 + i * 9}`} stroke="#22A35A" strokeWidth="3" fill="none" opacity="0.7" />
          ))}
          <rect x={250 + (h % 60)} y="146" width="46" height="22" fill="#F5F8FA" />
          <path d={`M${246 + (h % 60)} 147 l27 -14 l27 14z`} fill="#172B3A" />
        </>
      )
    case 'Gardens':
    case 'Zoological Gardens':
      return (
        <>
          <Hills h={h} y={175} c1="#16A34A" c2="#166534" />
          {[50, 120, 300, 350].map((x, i) => (
            <g key={x} transform={`translate(${x} ${185 - (i % 2) * 10})`}>
              <rect x="-3" y="0" width="6" height="40" fill="#172B3A" />
              <circle cx="0" cy="-10" r={22 + (i % 2) * 6} fill={i % 2 ? '#16A34A' : '#15803D'} />
            </g>
          ))}
        </>
      )
    case 'Historic Sites':
      return (
        <>
          <Hills h={h} y={190} c1="#1D5470" c2="#1F6B57" />
          <path d="M150 190 C 150 120 165 95 205 92 C 250 90 262 120 262 190Z" fill="#172B3A" />
          <path d="M150 190 h112" stroke="#123B5D" strokeWidth="4" />
          <rect x="40" y="185" width="90" height="20" fill="#123B5D" />
          {[40, 58, 76, 94, 112].map((x) => <rect key={x} x={x} y="178" width="10" height="8" fill="#123B5D" />)}
        </>
      )
    case 'Religious Sites':
      return (
        <>
          <Hills h={h} y={200} c1="#1D5470" c2="#123B5D" />
          <g transform={`translate(${h % 2 ? 240 : 160} 0)`}>
            <rect x="-70" y="188" width="140" height="14" fill="#F5F8FA" />
            <path d="M-55 188 A 55 55 0 0 1 55 188Z" fill="#F5F8FA" />
            <rect x="-10" y="118" width="20" height="18" fill="#EAF2F5" />
            <path d="M-5 118 L0 70 L5 118Z" fill="#EAF2F5" />
          </g>
        </>
      )
    case 'Museums':
      return (
        <>
          <Hills h={h} y={205} />
          <g fill="#F5F8FA">
            <path d="M120 120 L200 88 L280 120Z" />
            <rect x="120" y="122" width="160" height="8" />
            {[130, 160, 190, 220, 250].map((x) => <rect key={x} x={x} y="132" width="14" height="58" />)}
            <rect x="112" y="190" width="176" height="12" />
          </g>
        </>
      )
    case 'Waterfalls':
      return (
        <>
          <path d="M0 240 V90 Q 60 70 150 95 L 150 240Z" fill="#123B5D" />
          <path d="M250 240 V100 Q 330 75 400 92 V240Z" fill="#123B5D" />
          <path d="M150 95 Q 200 88 250 100 L250 240 H150Z" fill="#172B3A" />
          {[165, 185, 205, 225].map((x, i) => (
            <rect key={x} x={x} y={98} width={10 + (i % 2) * 6} height="142" fill="#DDF5F2" opacity={0.55 + (i % 2) * 0.3} />
          ))}
          <ellipse cx="200" cy="232" rx="90" ry="14" fill="#F5F8FA" opacity="0.6" />
        </>
      )
    case 'National Parks':
    case 'Nature & Wildlife Areas':
    default:
      return (
        <>
          <Hills h={h} y={175} c1="#1F6B57" c2="#174F42" />
          {[70, 290].map((x, i) => (
            <g key={x} transform={`translate(${x + (h % 40)} ${190 - i * 6})`} fill="#172B3A">
              <rect x="-2" y="-30" width="4" height="34" />
              <ellipse cx="0" cy="-34" rx="34" ry="9" />
            </g>
          ))}
          <g transform={`translate(${170 + (h % 50)} 200)`} fill="#172B3A">
            <ellipse cx="0" cy="-14" rx="20" ry="13" />
            <circle cx="20" cy="-18" r="9" />
            <path d="M27 -14 q 6 10 2 20" stroke="#172B3A" strokeWidth="3" fill="none" />
            {[-13, -5, 6, 13].map((x) => <rect key={x} x={x} y="-6" width="5" height="12" />)}
          </g>
        </>
      )
  }
}
