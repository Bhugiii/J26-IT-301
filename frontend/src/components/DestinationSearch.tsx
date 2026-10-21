import { useId, useMemo, useRef, useState } from 'react'
import { Search, X } from 'lucide-react'

/**
 * Search box for picking a destination (replaces a dropdown).
 * The current choice is shown as the placeholder; typing filters the list.
 * Keyboard: arrows to move, Enter to pick, Escape to close.
 */
export default function DestinationSearch({ value, options, onPick, color, label }: {
  value: string | null
  options: string[]
  onPick: (name: string) => void
  color: string
  label: string
}) {
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const [idx, setIdx] = useState(0)
  const input = useRef<HTMLInputElement>(null)
  const listId = useId()

  const results = useMemo(() => {
    const s = q.trim().toLowerCase()
    if (!s) return options
    const starts = options.filter((n) => n.toLowerCase().startsWith(s))
    const words = options.filter((n) => !starts.includes(n) && n.toLowerCase().split(/[\s(-]+/).some((w) => w.startsWith(s)))
    const rest = options.filter((n) => !starts.includes(n) && !words.includes(n) && n.toLowerCase().includes(s))
    return [...starts, ...words, ...rest]
  }, [q, options])

  const pick = (name: string) => {
    onPick(name)
    setQ('')
    setOpen(false)
    input.current?.blur()
  }

  return (
    <div className={`card relative flex items-center gap-3 p-3 ${open ? 'z-40' : 'z-10'}`}>
      <span className="h-3 w-3 shrink-0 rounded-full" style={{ background: color }} />
      <div className="relative min-w-0 flex-1">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-text" />
        <input
          ref={input}
          type="text"
          role="combobox"
          aria-label={label}
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={open && results[idx] ? `${listId}-${idx}` : undefined}
          className="w-full rounded-lg border border-transparent bg-offwhite py-2 pl-8 pr-8 text-[14.5px] font-semibold text-navy-deep placeholder:font-semibold placeholder:text-navy-deep/80 focus:border-teal focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky"
          placeholder={value ?? 'Search destinations…'}
          value={q}
          onChange={(e) => { setQ(e.target.value); setIdx(0); setOpen(true) }}
          onFocus={() => { setOpen(true); setIdx(0) }}
          onBlur={() => setTimeout(() => { setOpen(false); setQ('') }, 150)}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown') { e.preventDefault(); setOpen(true); setIdx((i) => Math.min(i + 1, results.length - 1)) }
            if (e.key === 'ArrowUp') { e.preventDefault(); setIdx((i) => Math.max(i - 1, 0)) }
            if (e.key === 'Enter' && results[idx]) pick(results[idx])
            if (e.key === 'Escape') { setOpen(false); setQ(''); input.current?.blur() }
          }}
        />
        {q && (
          <button type="button" aria-label="Clear search" onMouseDown={(e) => { e.preventDefault(); setQ(''); setIdx(0) }}
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-slate-text hover:text-navy">
            <X className="h-4 w-4" />
          </button>
        )}
        {open && (
          <ul id={listId} role="listbox"
            className="absolute left-0 right-0 top-full z-30 mt-2 max-h-72 overflow-y-auto rounded-tm border border-line bg-white py-1 shadow-lift">
            {results.length === 0 && <li className="px-3 py-2.5 text-[13.5px] text-slate-text">No destination matches “{q}”</li>}
            {results.map((n, i) => (
              <li key={n} id={`${listId}-${i}`} role="option" aria-selected={n === value}>
                <button type="button" onMouseDown={(e) => { e.preventDefault(); pick(n) }} onMouseEnter={() => setIdx(i)}
                  className={`flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-[13.5px] ${
                    i === idx ? 'bg-[#E6F6F4] text-teal-dark' : 'text-navy-deep'}`}>
                  <span className="truncate">{n}</span>
                  {n === value && <span className="shrink-0 text-[11.5px] font-semibold text-teal-dark">Selected</span>}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}