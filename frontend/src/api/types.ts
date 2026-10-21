export const ASPECTS = ['Crowding', 'Facilities', 'Commercialization', 'Accessibility'] as const
export type AspectKey = (typeof ASPECTS)[number]
export type Band = 'spot_on' | 'unique_vibe' | 'authentic'

export interface DestinationSummary {
  name: string
  type: string
  province: string
  district: string
  city: string
  total_reviews: number
  score: number
  percentile: number
  rank: number
  band: Band
  avg_rating: number
  positive_pct: number
  aspects_pct: Record<AspectKey, number>
  top_aspect: AspectKey
}

export interface Overview {
  total_destinations: number
  total_reviews: number
  avg_score: number
  min_score: number
  max_score: number
  median_score: number
  aspect_avg_pct: Record<AspectKey, number>
  types: string[]
  provinces: string[]
  destinations: DestinationSummary[]
}

export interface Snippet { text: string; rating: number; title?: string }

export interface AspectDetail {
  key: AspectKey
  mentions: number
  share_pct: number
  dataset_avg_pct: number
  relative: 'above' | 'typical' | 'below'
  positive_pct: number | null
  snippet: Snippet | null
}

export interface Tip { aspect: string | null; icon: string; title: string; body: string }

export interface DestinationDetail {
  Location_Name: string
  Total_Reviews: number
  Average_Reality_Score: number
  Crowding_Mentions: number
  Facilities_Mentions: number
  Commercialization_Mentions: number
  Accessibility_Mentions: number
  Marketing_Promise: string
  /** A review about the topic visitors mention most; explains the gap with the advert. */
  Contrasting_Reality_Review: string | null
  Alignment_Status: string
  Recommendations: string[]
  Location_Type: string
  Province: string
  District: string
  City: string
  Score_Percentile: number
  Score_Rank: number
  Score_Band: Band
  Dataset_Avg_Score: number
  Average_Rating: number
  Positive_Pct: number
  Contrasting_Review_Title?: string | null
  Contrasting_Review_Rating?: number | null
  Contrasting_Review_Similarity?: number | null
  Contrasting_Review_Aspect?: AspectKey | null
  Score_Distribution: { bin: string; count: number }[]
  Aspects: AspectDetail[]
  Tips: Tip[]
}
