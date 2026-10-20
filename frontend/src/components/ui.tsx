import * as Tooltip from '@radix-ui/react-tooltip'
import { motion } from 'motion/react'
import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'
import type { Zone } from '@/types'

export function Card({ title, subtitle, icon, action, className, children }: {
  title: string; subtitle?: ReactNode; icon?: ReactNode; action?: ReactNode; className?: string; children: ReactNode
}) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: 'spring', bounce: 0, duration: 0.6 }}
      className={cn(
        'flex min-w-0 flex-col rounded-[20px] border border-[var(--border)] bg-[var(--surface)] p-5 shadow-[0_1px_0_rgba(255,255,255,0.04)_inset,0_10px_30px_-12px_rgba(0,0,0,0.25)]',
        className,
      )}
    >
      <header className="mb-4 flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          {icon && (
            <div className="flex size-9 shrink-0 items-center justify-center rounded-xl border border-[var(--border)] bg-gradient-to-b from-[var(--surface-2)] to-[var(--surface)] text-[var(--ink-2)]">
              {icon}
            </div>
          )}
          <div className="min-w-0">
            <h2 className="truncate text-[15px] font-semibold tracking-tight text-[var(--ink)]">{title}</h2>
            {subtitle && <p className="truncate text-[12.5px] text-[var(--ink-muted)]">{subtitle}</p>}
          </div>
        </div>
        {action}
      </header>
      {children}
    </motion.section>
  )
}

export const zoneColor: Record<Zone, string> = { green: 'var(--good)', yellow: 'var(--warning)', red: 'var(--critical)' }
export const zoneLabel: Record<Zone, string> = { green: 'Primed', yellow: 'Moderate', red: 'Recover' }

export function StatusPill({ zone, children }: { zone: Zone | 'serious'; children: ReactNode }) {
  const color = zone === 'serious' ? 'var(--serious)' : zoneColor[zone]
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--border)] bg-[var(--surface-2)] px-2.5 py-1 text-[12px] font-medium text-[var(--ink)]">
      <span className="size-2 rounded-full" style={{ background: color }} aria-hidden />
      {children}
    </span>
  )
}

export function Tip({ content, children }: { content: ReactNode; children: ReactNode }) {
  return (
    <Tooltip.Root delayDuration={60}>
      <Tooltip.Trigger asChild>{children}</Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content
          sideOffset={6}
          className="z-50 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-2.5 py-1.5 text-[12px] text-[var(--ink)] shadow-lg"
        >
          {content}
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  )
}

/** Semicircle-ish 270° arc gauge. `value` / `max` drives the fill; optional band highlights a target range. */
export function ArcGauge({ value, max, color, size = 180, band, children, label }: {
  value: number | null | undefined; max: number; color: string; size?: number
  band?: { low: number; high: number; color: string }; children?: ReactNode; label: string
}) {
  const stroke = 12
  const r = (size - stroke) / 2 - 4
  const c = size / 2
  const sweep = 270
  const startAngle = 135
  const polar = (deg: number) => {
    const rad = (deg * Math.PI) / 180
    return [c + r * Math.cos(rad), c + r * Math.sin(rad)]
  }
  const arc = (from: number, to: number) => {
    const a0 = startAngle + (from / max) * sweep
    const a1 = startAngle + (to / max) * sweep
    const [x0, y0] = polar(a0)
    const [x1, y1] = polar(a1)
    const large = a1 - a0 > 180 ? 1 : 0
    return `M ${x0} ${y0} A ${r} ${r} 0 ${large} 1 ${x1} ${y1}`
  }
  const v = Math.max(0, Math.min(max, value ?? 0))
  const len = (sweep / 360) * 2 * Math.PI * r
  return (
    <div className="relative" style={{ width: size, height: size }} role="img" aria-label={label}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <path d={arc(0, max)} fill="none" stroke="var(--surface-2)" strokeWidth={stroke} strokeLinecap="round" />
        {band && (
          <path d={arc(band.low, band.high)} fill="none" stroke={band.color} strokeWidth={stroke + 8} strokeLinecap="butt" opacity={0.55} />
        )}
        {value != null && (
          <motion.path
            d={arc(0, max)}
            fill="none"
            stroke={color}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={len}
            initial={{ strokeDashoffset: len }}
            animate={{ strokeDashoffset: len * (1 - v / max) }}
            transition={{ type: 'spring', bounce: 0, duration: 1.4 }}
          />
        )}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center">{children}</div>
    </div>
  )
}

export function Metric({ label, value, unit, delta, hint }: {
  label: string; value: ReactNode; unit?: string; delta?: ReactNode; hint?: string
}) {
  const body = (
    <div className="min-w-0 rounded-xl bg-[var(--surface-2)] px-3 py-2.5">
      <div className="truncate text-[11.5px] font-medium tracking-wide text-[var(--ink-muted)] uppercase">{label}</div>
      <div className="tabular mt-0.5 flex items-baseline gap-1 text-[18px] font-semibold text-[var(--ink)]">
        {value ?? '—'}
        {unit && value != null && <span className="text-[12px] font-normal text-[var(--ink-muted)]">{unit}</span>}
      </div>
      {delta && <div className="tabular truncate text-[11.5px] text-[var(--ink-2)]">{delta}</div>}
    </div>
  )
  return hint ? <Tip content={hint}>{body}</Tip> : body
}

export function signed(n: number | null | undefined, digits = 1, unit = '') {
  if (n == null) return null
  const s = n.toFixed(digits)
  return `${n > 0 ? '+' : n < 0 ? '−' : '±'}${s.replace('-', '')}${unit}`
}

export function fmtH(h: number | null | undefined) {
  if (h == null) return '—'
  const hh = Math.floor(h)
  const mm = Math.round((h - hh) * 60)
  return `${hh}:${String(mm).padStart(2, '0')}`
}

export function dayLabel(iso: string) {
  return new Date(iso + 'T12:00:00').toLocaleDateString(undefined, { weekday: 'short' })
}
