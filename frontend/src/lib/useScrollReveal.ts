import { useEffect } from 'react'

const SELECTOR = 'main .card, main article, main [data-reveal]'

/**
 * Fades elements up as they scroll into view. Watches the page for content that
 * loads later (API data) and staggers siblings slightly. Skipped when the user
 * prefers reduced motion.
 */
export function useScrollReveal(key: string) {
  useEffect(() => {
    const root = document.querySelector('main')
    if (!root || typeof IntersectionObserver === 'undefined') return
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return

    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          e.target.classList.add('is-visible')
          io.unobserve(e.target)
        }
      })
    }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' })

    const seen = new WeakSet<Element>()
    const scan = () => {
      root.querySelectorAll<HTMLElement>(SELECTOR).forEach((el) => {
        if (seen.has(el)) return
        seen.add(el)
        const siblings = el.parentElement ? Array.from(el.parentElement.children) : []
        el.style.transitionDelay = `${Math.min(Math.max(siblings.indexOf(el), 0), 5) * 70}ms`
        el.classList.add('reveal')
        io.observe(el)
      })
    }
    scan()
    const mo = new MutationObserver(scan)
    mo.observe(root, { childList: true, subtree: true })
    return () => { mo.disconnect(); io.disconnect() }
  }, [key])
}
