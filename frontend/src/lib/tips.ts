import type { AspectDetail, AspectKey, Band, DestinationDetail } from '../api/types'

/**
 * Practical visit tips for first-time tourists.
 * Every tip says what to do (`action`), why it helps (`why`) and when to use it (`when`).
 * Tips marked `fromReviews` are triggered by what visitors to this destination mention
 * more (or less) than at a typical destination; the rest depend on the kind of place.
 */
export type TipWhen = 'before' | 'arrive' | 'during'
export interface VisitTip {
  id: string
  when: TipWhen
  icon: TipIcon
  title: string
  action: string
  why: string
  fromReviews?: boolean
}
export type TipIcon =
  | 'sunrise' | 'cash' | 'handshake' | 'backpack' | 'toilet' | 'shoe' | 'car' | 'pause' | 'shirt'
  | 'footprints' | 'camera' | 'waves' | 'sun' | 'binoculars' | 'volume' | 'leaf' | 'umbrella' | 'ticket'
  | 'droplet' | 'clock' | 'map' | 'cup' | 'compass' | 'fish' | 'book'

export const WHEN_LABEL: Record<TipWhen, { title: string; hint: string }> = {
  before: { title: 'Before you go', hint: 'Plan and pack' },
  arrive: { title: 'When you arrive', hint: 'First few minutes' },
  during: { title: 'During your visit', hint: 'Make the most of it' },
}

// ---- Tips triggered by what visitors mention (relative to a typical destination) ----
const ASPECT_TIPS: Partial<Record<`${AspectKey}:${AspectDetail['relative']}`, VisitTip[]>> = {
  'Crowding:above': [
    { id: 'early', when: 'before', icon: 'sunrise', title: 'Plan an early start',
      action: 'Aim to arrive within the first hour after opening.',
      why: 'Visitors here often mention crowds. Mornings are calmer, cooler and better for photos.' },
    { id: 'quiet-corner', when: 'during', icon: 'compass', title: 'Head for the quieter corners first',
      action: 'Start with the parts most people visit last, then come back to the main sights.',
      why: 'You move against the flow of visitors and get more space to enjoy the place.' },
  ],
  'Crowding:below': [
    { id: 'linger', when: 'during', icon: 'pause', title: 'Slow down and take your time',
      action: 'Plan a relaxed visit with time to sit, look around and take photos.',
      why: 'Visitors rarely mention crowds here, so it is a good place to linger.' },
  ],
  'Commercialization:above': [
    { id: 'small-notes', when: 'before', icon: 'cash', title: 'Bring small notes in rupees',
      action: 'Carry small rupee notes and some coins for tickets, parking and small purchases.',
      why: 'Tickets, shops and sellers come up often in reviews here. Small notes make paying quick and easy.' },
    { id: 'agree-price', when: 'arrive', icon: 'handshake', title: 'Agree the price first',
      action: 'For guides, rides or tuk-tuks, agree the full price before you start.',
      why: 'A clear price up front keeps the visit relaxed and avoids misunderstandings later.' },
  ],
  'Facilities:above': [
    { id: 'pack-basics', when: 'before', icon: 'backpack', title: 'Pack the basics',
      action: 'Bring water, tissues and hand sanitiser in your day bag.',
      why: 'Visitors often comment on toilets and upkeep here, so having your own supplies keeps you comfortable.' },
    { id: 'toilet-first', when: 'arrive', icon: 'toilet', title: 'Use the toilets near the entrance',
      action: 'Use the facilities at the entrance or car park before you start exploring.',
      why: 'There may be few or no toilets further inside.' },
  ],
  'Accessibility:above': [
    { id: 'transport', when: 'before', icon: 'car', title: 'Arrange your transport both ways',
      action: 'Book your ride there and agree a pick-up time for the return before you set off.',
      why: 'Visitors often mention the journey here. Transport can be hard to find for the trip back.' },
    { id: 'shoes', when: 'before', icon: 'shoe', title: 'Wear comfortable shoes',
      action: 'Choose closed shoes with good grip rather than sandals or flip-flops.',
      why: 'Reviews here mention plenty of walking, steps or climbing.' },
    { id: 'pace', when: 'during', icon: 'pause', title: 'Pace yourself',
      action: 'Take short breaks in the shade and drink water before you feel thirsty.',
      why: 'The walking here takes effort, and the heat makes it harder than it looks.' },
  ],
}

// ---- Tips that depend on the kind of place ----
const TYPE_TIPS: Record<string, VisitTip[]> = {
  'Religious Sites': [
    { id: 'dress', when: 'before', icon: 'shirt', title: 'Dress to cover shoulders and knees',
      action: 'Wear clothes that cover your shoulders and knees, or carry a light scarf or sarong.',
      why: 'This is a place of worship and modest dress is expected at the entrance.' },
    { id: 'shoes-off', when: 'arrive', icon: 'footprints', title: 'Remove your shoes and hat',
      action: 'Take off your shoes and hat before entering the sacred area. Thin socks help on hot ground.',
      why: 'It is a sign of respect, and stone paths can get very hot by midday.' },
    { id: 'photo-respect', when: 'during', icon: 'camera', title: 'Take photos respectfully',
      action: 'Never pose with your back to a Buddha statue, and ask before photographing people praying.',
      why: 'Turning your back to a statue for a photo is considered disrespectful in Sri Lanka.' },
  ],
  Beaches: [
    { id: 'swim-safe', when: 'arrive', icon: 'waves', title: 'Check where it is safe to swim',
      action: 'Swim only where locals swim and where flags or lifeguards show it is safe.',
      why: 'Currents can be strong in some seasons, even when the sea looks calm.' },
    { id: 'sun', when: 'during', icon: 'sun', title: 'Protect yourself from the sun',
      action: 'Use sunscreen, wear a hat and rest in the shade in the middle of the day.',
      why: 'The tropical sun is strong, and sunburn can spoil the rest of your trip.' },
  ],
  Farms: [
    { id: 'factory-tour', when: 'arrive', icon: 'leaf', title: 'Ask about the factory tour',
      action: 'Ask at the entrance when the next guided tour starts.',
      why: 'The tour shows how tea goes from leaf to cup and is the best part of the visit.' },
    { id: 'taste', when: 'during', icon: 'cup', title: 'Taste before you buy',
      action: 'Try the teas in the tasting room before choosing what to take home.',
      why: 'Flavours vary a lot between grades, and tasting helps you pick one you will enjoy.' },
  ],
  Gardens: [
    { id: 'morning-garden', when: 'before', icon: 'sunrise', title: 'Visit in the morning',
      action: 'Plan to arrive in the morning rather than the afternoon.',
      why: 'It is cooler for walking, and the light is softer for photos.' },
    { id: 'umbrella', when: 'before', icon: 'umbrella', title: 'Pack a small umbrella',
      action: 'Bring a compact umbrella for both sun and sudden showers.',
      why: 'Gardens have open lawns with little cover, and rain can arrive quickly.' },
  ],
  'Historic Sites': [
    { id: 'guide', when: 'arrive', icon: 'book', title: 'Consider a local guide',
      action: 'Hire a guide at the entrance and agree the fee before you start.',
      why: 'A guide brings the history to life and shows you details that are easy to miss.' },
    { id: 'ruins-sun', when: 'before', icon: 'sun', title: 'Bring water and a hat',
      action: 'Carry plenty of water and wear a hat or carry an umbrella.',
      why: 'Old ruins and fort walls have very little shade.' },
  ],
  Museums: [
    { id: 'closing-day', when: 'before', icon: 'clock', title: 'Check the opening days',
      action: 'Check opening days and hours before you set off.',
      why: 'Some museums close one day a week or on public holidays.' },
    { id: 'allow-time', when: 'during', icon: 'clock', title: 'Allow one to two hours',
      action: 'Give yourself one to two hours rather than a quick stop.',
      why: 'You will have time to read the displays without rushing.' },
  ],
  'Waterfalls': [
    { id: 'grip', when: 'before', icon: 'shoe', title: 'Wear shoes with good grip',
      action: 'Choose shoes or sandals with a firm grip.',
      why: 'Paths and rocks near waterfalls are wet and slippery.' },
    { id: 'viewpoint', when: 'during', icon: 'droplet', title: 'Enjoy the falls from the viewpoints',
      action: 'Stay on paths and viewpoints, and do not climb on wet rocks.',
      why: 'Water levels can rise quickly after rain upstream.' },
  ],
  'Zoological Gardens': [
    { id: 'zoo-early', when: 'before', icon: 'sunrise', title: 'Go early in the day',
      action: 'Plan to arrive soon after opening.',
      why: 'Animals are more active in the cooler morning hours.' },
  ],
  'Bodies of Water': [
    { id: 'lake-walk', when: 'during', icon: 'map', title: 'Walk the lakeside path',
      action: 'Take a slow walk around the lake in the early morning or late afternoon.',
      why: 'It is cooler, quieter and the light on the water is at its best.' },
  ],
}

// Destination-specific additions (replace or extend the type tips).
const SAFARI = ['Bundala National Park', 'Kaudulla National Park', 'Minneriya National Park', 'Udawalawe National Park',
  'Wilpattu National Park', 'Minneriya Tusker Safaris']
const NAME_TIPS: Record<string, VisitTip[]> = {
  ...Object.fromEntries(SAFARI.map((n) => [n, [
    { id: 'jeep', when: 'before', icon: 'car', title: 'Book your safari jeep ahead',
      action: 'Book a jeep and driver the day before, and choose an early morning or late afternoon drive.',
      why: 'Animals are most active in the cooler hours, so these drives have the best sightings.' },
    { id: 'binoculars', when: 'before', icon: 'binoculars', title: 'Bring binoculars and neutral clothes',
      action: 'Pack binoculars and wear green, brown or beige clothing.',
      why: 'Animals are often far away, and muted colours help you blend in.' },
    { id: 'quiet-jeep', when: 'during', icon: 'volume', title: 'Stay quiet and inside the jeep',
      action: 'Keep your voice low and stay seated inside the vehicle.',
      why: 'It keeps you safe and makes animals less likely to move away.' },
  ] as VisitTip[]])),
  'Horton Plains National Park': [
    { id: 'hp-early', when: 'before', icon: 'sunrise', title: 'Start as early as you can',
      action: 'Aim to begin the walk soon after the park opens.',
      why: 'Mist often rolls in by late morning and can hide the views.' },
    { id: 'hp-layers', when: 'before', icon: 'shirt', title: 'Bring a warm layer',
      action: 'Pack a light jacket or jumper, even if it is hot elsewhere.',
      why: 'Early mornings in the highlands are surprisingly cold.' },
  ],
  'Pigeon Island National Park': [
    { id: 'snorkel', when: 'during', icon: 'fish', title: 'Snorkel gently and do not touch the coral',
      action: 'Float calmly, keep your fins away from the reef and never stand on coral.',
      why: 'The coral is fragile and is home to the fish and turtles you came to see.' },
    { id: 'boat', when: 'before', icon: 'ticket', title: 'Book the boat in the morning',
      action: 'Arrange your boat trip for the morning.',
      why: 'The sea is usually calmer and the water clearer earlier in the day.' },
  ],
  'Sinharaja Forest Reserve': [
    { id: 'leech', when: 'before', icon: 'leaf', title: 'Prepare for a wet rainforest',
      action: 'Wear long socks tucked into trousers and bring insect repellent.',
      why: 'The forest is damp, and leeches are common on the trails.' },
    { id: 'forest-guide', when: 'arrive', icon: 'compass', title: 'Walk with a local guide',
      action: 'Arrange a guide at the entrance before entering the forest.',
      why: 'Guides know the trails and can spot birds and animals you would otherwise miss.' },
  ],
  'Udawattekele Sanctuary': [
    { id: 'udawattekele-path', when: 'during', icon: 'map', title: 'Stay on the marked trails',
      action: 'Follow the signed paths and keep a map photo on your phone.',
      why: 'The forest trails cross each other and are easy to mix up.' },
  ],
  'Pinnawala Elephant Orphanage': [
    { id: 'bath-time', when: 'arrive', icon: 'clock', title: 'Ask about bathing and feeding times',
      action: 'Check the day\'s schedule at the entrance and plan around the river bathing time.',
      why: 'Seeing the elephants walk to the river and bathe is the highlight of most visits.' },
  ],
  'Twin Baths (Kuttam Pokuna)': [
    { id: 'twin-sun', when: 'before', icon: 'sun', title: 'Bring water and a hat',
      action: 'Carry water and wear a hat or carry an umbrella.',
      why: 'The ancient pools are in open ground with very little shade.' },
  ],
}

const BAND_TIPS: Record<Band, VisitTip> = {
  spot_on: { id: 'band', when: 'before', icon: 'camera', title: 'Expect what you have seen in photos',
    action: 'Plan your visit around the sights in the advert.',
    why: 'Visitors\' experiences here closely match how the place is described.', fromReviews: true },
  unique_vibe: { id: 'band', when: 'before', icon: 'compass', title: 'Expect a mix of calm and lively',
    action: 'Read two or three recent reviews to see what to expect today.',
    why: 'Visitors describe parts of the advert, but also plenty of everyday local life.', fromReviews: true },
  authentic: { id: 'band', when: 'before', icon: 'compass', title: 'Go in with an open mind',
    action: 'Read a few recent reviews before you go, and treat the advert as a rough guide.',
    why: 'Visitors describe this place quite differently from its advert.', fromReviews: true },
}

const GENERAL_TIPS: VisitTip[] = [
  { id: 'water', when: 'during', icon: 'droplet', title: 'Drink water regularly',
    action: 'Carry at least one bottle of water and refill it when you can.',
    why: 'Sri Lanka is hot and humid, and you can get dehydrated quickly while sightseeing.' },
  { id: 'cash', when: 'before', icon: 'cash', title: 'Carry some cash',
    action: 'Bring enough rupees in cash for entry, snacks and transport.',
    why: 'Smaller places may not accept cards.' },
  { id: 'ticket', when: 'arrive', icon: 'ticket', title: 'Keep your ticket until you leave',
    action: 'Keep your entry ticket somewhere safe for the whole visit.',
    why: 'Some sites check tickets again at inner gates or viewpoints.' },
]

const ORDER: TipWhen[] = ['before', 'arrive', 'during']

export function buildVisitTips(d: DestinationDetail): VisitTip[] {
  const out: VisitTip[] = []
  const add = (t: VisitTip, fromReviews = false) => {
    if (!out.some((x) => x.id === t.id || x.title === t.title)) out.push({ ...t, fromReviews: t.fromReviews ?? fromReviews })
  }
  // 1) What visitors to this place mention more or less than usual
  d.Aspects.forEach((a) => (ASPECT_TIPS[`${a.key}:${a.relative}`] ?? []).forEach((t) => add(t, true)))
  // 2) How well the experience matches the advert
  add(BAND_TIPS[d.Score_Band])
  // 3) This particular place, then the kind of place
  const named = NAME_TIPS[d.Location_Name]
  ;(named ?? []).forEach((t) => add(t))
  if (!named || d.Location_Type === 'Religious Sites') (TYPE_TIPS[d.Location_Type] ?? []).forEach((t) => add(t))
  // 4) Good advice anywhere in Sri Lanka
  GENERAL_TIPS.forEach((t) => add(t))
  return out.sort((x, y) => ORDER.indexOf(x.when) - ORDER.indexOf(y.when)).slice(0, 12)
}
