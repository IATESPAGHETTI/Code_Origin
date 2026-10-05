import { useEffect } from 'react'

/*
  Behind the glass (light): a soft pastel light field plus fine detail the glass can bend, namely a hairline dot grid,
  thin rings and a couple of luminous filaments. Frosted glass over a smooth gradient shows nothing; refraction
  only reads where an edge crosses something crisp, so the crisp detail is deliberately faint and elegant.
*/
export default function GlassBackdrop() {
  // pointer light: one listener lights whichever glass surface the pointer is over
  useEffect(() => {
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return undefined
    const onMove = (e) => {
      const el = e.target.closest?.('.panel')
      if (!el) return
      const r = el.getBoundingClientRect()
      el.style.setProperty('--gx', `${e.clientX - r.left}px`)
      el.style.setProperty('--gy', `${e.clientY - r.top}px`)
    }
    document.addEventListener('pointermove', onMove, { passive: true })
    return () => document.removeEventListener('pointermove', onMove)
  }, [])

  return (
    <>
      <svg width="0" height="0" style={{ position: 'absolute' }} aria-hidden="true" focusable="false">
        <filter id="refract" x="0" y="0" width="100%" height="100%" colorInterpolationFilters="sRGB">
          <feTurbulence type="fractalNoise" baseFrequency="0.008 0.013" numOctaves="2" seed="11" result="noise" />
          <feGaussianBlur in="noise" stdDeviation="1.5" result="soft" />
          <feDisplacementMap in="SourceGraphic" in2="soft" scale="34" xChannelSelector="R" yChannelSelector="B" />
        </filter>
      </svg>
      <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10 overflow-hidden" style={{ background: 'var(--bg)' }}>
        {/* pastel light field */}
        <div className="blob blob-a left-[-8%] top-[-6%] h-[520px] w-[520px]" />
        <div className="blob blob-b right-[-6%] top-[8%] h-[480px] w-[480px]" />
        <div className="blob blob-c bottom-[-12%] left-[30%] h-[460px] w-[460px]" />
        {/* hairline dot grid that fades out downward */}
        <div className="absolute inset-0" style={{ backgroundImage: 'radial-gradient(rgba(0,0,0,.16) 1px, transparent 1px)', backgroundSize: '26px 26px', opacity: 0.55,
          WebkitMaskImage: 'radial-gradient(ellipse 85% 65% at 50% 0%, #000 15%, transparent 75%)', maskImage: 'radial-gradient(ellipse 85% 65% at 50% 0%, #000 15%, transparent 75%)' }} />
        {/* thin rings and filaments: what the glass edge bends */}
        <div className="absolute right-[-140px] top-[4%] h-[600px] w-[600px] rounded-full border border-black/[.09]" style={{ animation: 'rotate 140s linear infinite' }} />
        <div className="absolute right-[-60px] top-[10%] h-[440px] w-[440px] rounded-full border border-[#0071e3]/[.18]" style={{ animation: 'rotate 100s linear infinite reverse' }} />
        <div className="absolute left-[-180px] top-[46%] h-[560px] w-[560px] rounded-full border border-black/[.08]" style={{ animation: 'rotate 170s linear infinite' }} />
        <div className="absolute left-[42%] top-[24%] h-px w-[48%] rotate-[-16deg]" style={{ background: 'linear-gradient(90deg, transparent, rgba(0,113,227,.55), transparent)' }} />
        <div className="absolute left-[8%] top-[66%] h-px w-[42%] rotate-[10deg]" style={{ background: 'linear-gradient(90deg, transparent, rgba(94,92,230,.45), transparent)' }} />
      </div>
    </>
  )
}
