/**
 * Split hero banner: brand-coloured text panel + a photo panel.
 * The photos are portrait, so they sit in their own panel instead of being
 * stretched across the full width (which would blur them).
 */
export default function PhotoHero({ eyebrow, title, photo, alt, position = 'center', compact, children }: {
  eyebrow?: React.ReactNode
  title: React.ReactNode
  photo: string
  alt: string
  position?: string
  compact?: boolean
  children?: React.ReactNode
}) {
  return (
    <section data-reveal className="grid overflow-hidden rounded-tm border border-line bg-navy shadow-card md:grid-cols-[1.35fr_1fr]">
      <div className="relative order-2 flex flex-col justify-center px-6 py-8 text-white md:order-1 md:px-10 md:py-10"
        style={{ background: 'linear-gradient(135deg, var(--tm-primary) 0%, #134E5E 60%, var(--tm-secondary-hover) 100%)' }}>
        {eyebrow && <div className="mb-3 text-[12px] font-semibold uppercase tracking-[0.14em] text-[#99F6E4]">{eyebrow}</div>}
        <h1 className={`font-display font-extrabold leading-tight text-white ${compact ? 'text-[28px] md:text-[32px]' : 'text-[32px] md:text-[40px]'}`}>{title}</h1>
        {children}
      </div>
      <div className={`relative order-1 md:order-2 ${compact ? 'h-44 md:h-auto md:min-h-[230px]' : 'h-56 md:h-auto md:min-h-[340px]'}`}>
        <img src={photo} alt={alt} className="absolute inset-0 h-full w-full object-cover" style={{ objectPosition: position }} />
        <div className="absolute inset-y-0 left-0 hidden w-16 bg-gradient-to-r from-[#123B5D]/60 to-transparent md:block" />
      </div>
    </section>
  )
}
