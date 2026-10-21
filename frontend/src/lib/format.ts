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

/**
 * Plain-language wording for the four topics. `label` is the internal research
 * name (not shown to travellers); `friendly` is what travellers see.
 * `guide` tells a traveller what a high, typical or low level means in practice.
 */
export const ASPECT_META: Record<AspectKey, {
  label: string; friendly: string; desc: string; color: string
  guide: { above: string; typical: string; below: string }
}> = {
  Crowding: {
    label: 'Crowding', friendly: 'How busy it gets', color: '#0D9488',
    desc: 'How often visitors talk about crowds, queues and busy times.',
    guide: {
      above: 'Expect plenty of other visitors, especially at popular times. Arriving early makes for a calmer visit.',
      typical: 'About as busy as most places. Some times of day will be quieter than others.',
      below: 'Visitors rarely mention crowds here, so you can usually explore at a relaxed pace.',
    },
  },
  Facilities: {
    label: 'Facilities', friendly: 'Toilets, parking and upkeep', color: '#123B5D',
    desc: 'How often visitors talk about toilets, parking, cleanliness and how well the place is looked after.',
    guide: {
      above: 'Facilities come up often in reviews. Bring your own water, tissues and hand sanitiser to be comfortable.',
      typical: 'Facilities are mentioned about as often as at most places. Basic supplies are still handy.',
      below: 'Facilities rarely come up, so they are unlikely to affect your visit.',
    },
  },
  Commercialization: {
    label: 'Commercialization', friendly: 'Tickets, shops and prices', color: '#14B8A6',
    desc: 'How often visitors talk about entry tickets, prices, sellers and shopping.',
    guide: {
      above: 'Money comes up often here. Expect entry fees, shops or sellers, and carry small notes in rupees.',
      typical: 'Prices and shopping come up about as often as at most places.',
      below: 'Prices and sellers rarely come up, so you can enjoy the visit without much spending.',
    },
  },
  Accessibility: {
    label: 'Accessibility', friendly: 'Getting there and walking', color: '#16A34A',
    desc: 'How often visitors talk about the journey, roads, walking, steps and climbing.',
    guide: {
      above: 'Expect some effort: a longer journey, plenty of walking or steps to climb. Wear comfortable shoes and allow extra time.',
      typical: 'Getting there and around takes about as much effort as most places.',
      below: 'The journey and walking are rarely mentioned, so this should be an easy visit.',
    },
  },
}

export const RELATIVE_LABEL = {
  above: 'Talked about a lot',
  typical: 'Talked about an average amount',
  below: 'Rarely talked about',
} as const

/** Strip leading emoji/markdown from v1 status strings. */
export const cleanStatus = (s: string) => s.replace(/^[^A-Za-z]+/, '').replace(/\*\*/g, '').trim()
