import type { AspectKey, Band } from '../api/types'

export const slug = (s: string) =>
  s.toLowerCase().replace(/[’'`]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')

export const destPath = (name: string) => `/destination/${encodeURIComponent(name)}`

export const fmt = (n: number, d = 1) => n.toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d })
export const int = (n: number) => n.toLocaleString()

// color = chart/fill colour; text = AA-contrast colour for small text on `soft`/white.
export const BAND: Record<Band, { label: string; short: string; desc: string; color: string; text: string; soft: string }> = {
  spot_on: {
    label: 'Closely echoes the promise', short: 'Close match', color: '#16A34A', text: '#15803D', soft: '#DCFCE7',
    desc: 'Reviews closely echo the way this destination is described, so the picture you form beforehand is a good guide.',
  },
  unique_vibe: {
    label: 'Its own unique vibe', short: 'Unique vibe', color: '#0D9488', text: '#0F766E', soft: '#DDF5F2',
    desc: 'Reviews echo parts of the description, alongside plenty of everyday local life. Expect a mix of both.',
  },
  authentic: {
    label: 'Expect something different', short: 'Different', color: '#123B5D', text: '#123B5D', soft: '#E3EAF1',
    desc: 'Visitors describe this place quite differently from its marketing. Come with an open mind and enjoy it on its own terms.',
  },
}

export const ASPECT_META: Record<AspectKey, { label: string; friendly: string; desc: string; color: string }> = {
  Crowding: {
    label: 'Crowding', friendly: 'Popularity & crowds',
    desc: 'Queues, busy periods and how many people visitors meet.', color: '#0D9488',
  },
  Facilities: {
    label: 'Facilities', friendly: 'Facilities & upkeep',
    desc: 'Toilets, parking, cleanliness, litter and maintenance.', color: '#123B5D',
  },
  Commercialization: {
    label: 'Commercialization', friendly: 'Local market & costs',
    desc: 'Vendors, ticket prices, souvenirs and local business.', color: '#14B8A6',
  },
  Accessibility: {
    label: 'Accessibility', friendly: 'Getting there & around',
    desc: 'Transport, roads, walking, climbing and stairs.', color: '#16A34A',
  },
}

export const RELATIVE_LABEL = {
  above: 'Talked about more than usual',
  typical: 'About as often as usual',
  below: 'Talked about less than usual',
} as const

/** Strip leading emoji/markdown from v1 status strings. */
export const cleanStatus = (s: string) => s.replace(/^[^A-Za-z]+/, '').replace(/\*\*/g, '').trim()
