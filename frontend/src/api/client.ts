import { useEffect, useState } from 'react'
import type { DestinationDetail, Overview } from './types'

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? ''

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) {
    let detail = `Request failed (${res.status})`
    try { detail = (await res.json()).detail ?? detail } catch { /* ignore */ }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => get<{ status: string; destinations: number; reviews: number }>('/api/health'),
  overview: () => get<Overview>('/api/overview'),
  destination: (name: string) => get<DestinationDetail>(`/api/destination/${encodeURIComponent(name)}`),
}

// Tiny cache so navigating between pages doesn't refetch.
const cache = new Map<string, unknown>()

export function useApi<T>(key: string | null, fn: () => Promise<T>) {
  const [data, setData] = useState<T | undefined>(key ? (cache.get(key) as T | undefined) : undefined)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState<boolean>(!!key && !cache.has(key))

  useEffect(() => {
    if (!key) return
    let alive = true
    if (cache.has(key)) { setData(cache.get(key) as T); setLoading(false); setError(null); return }
    setLoading(true); setError(null)
    fn()
      .then((d) => { cache.set(key, d); if (alive) setData(d) })
      .catch((e: Error) => { if (alive) setError(e.message) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  return { data, error, loading }
}
