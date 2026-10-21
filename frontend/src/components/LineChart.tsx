import { useState } from 'react'

const fmt = (n: number | null | undefined, d = 0) => (n == null ? '—' : n.toFixed(d))
const shortDate = (iso: string) => new Date(iso + 'T12:00:00').toLocaleDateString(undefined, { month: 'short', day: 'numeric' })

export interface Line { label: string; color: string; values: (number | null)[]; dots?: boolean; dashed?: boolean }

export function LineChart({ dates, lines, height = 170, min, max, unit = '' }: {
  dates: string[]; lines: Line[]; height?: number; min?: number; max?: number; unit?: string
}) {
  const [hover, setHover] = useState<number | null>(null)
  const W = 800, padL = 34, padR = 8, padT = 8, padB = 20
  const all = lines.flatMap((l) => l.values).filter((v): v is number => v != null)
  if (!all.length) return <div className="text-sm text-[var(--ink-muted)]">No data in this range.</div>
  const lo = min ?? Math.floor(Math.min(...all)), hi = max ?? Math.ceil(Math.max(...all))
  const span = hi - lo || 1
  const x = (i: number) => padL + (dates.length <= 1 ? 0 : (i / (dates.length - 1)) * (W - padL - padR))
  const y = (v: number) => padT + (1 - (v - lo) / span) * (height - padT - padB)
  const path = (vals: (number | null)[]) => {
    let d = '', pen = false
    vals.forEach((v, i) => {
      if (v == null) { pen = false; return }
      d += `${pen ? 'L' : 'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)} `
      pen = true
    })
    return d
  }
  const ticks = [lo, lo + span / 2, hi]
  const labelIdx = [0, Math.floor(dates.length / 3), Math.floor((2 * dates.length) / 3), dates.length - 1]
  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${height}`} className="w-full" onMouseLeave={() => setHover(null)}
        onMouseMove={(e) => {
          const r = e.currentTarget.getBoundingClientRect()
          const px = ((e.clientX - r.left) / r.width) * W
          setHover(Math.max(0, Math.min(dates.length - 1, Math.round(((px - padL) / (W - padL - padR)) * (dates.length - 1)))))
        }}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={padL} x2={W - padR} y1={y(t)} y2={y(t)} stroke="var(--grid)" strokeWidth={1} />
            <text x={padL - 6} y={y(t) + 4} textAnchor="end" fontSize={11} fill="var(--ink-muted)">{Math.round(t)}</text>
          </g>
        ))}
        {labelIdx.map((i) => (
          <text key={i} x={x(i)} y={height - 5} textAnchor={i === 0 ? 'start' : i === dates.length - 1 ? 'end' : 'middle'} fontSize={11} fill="var(--ink-muted)">{shortDate(dates[i])}</text>
        ))}
        {lines.map((l) => (
          <g key={l.label}>
            <path d={path(l.values)} fill="none" stroke={l.color} strokeWidth={l.dots ? 1 : 2} strokeDasharray={l.dashed ? '5 4' : undefined} opacity={l.dots ? 0.5 : 1} strokeLinejoin="round" />
            {l.dots && dates.length <= 200 && l.values.map((v, i) => v != null && <circle key={i} cx={x(i)} cy={y(v)} r={2.2} fill={l.color} />)}
          </g>
        ))}
        {hover != null && <line x1={x(hover)} x2={x(hover)} y1={padT} y2={height - padB} stroke="var(--ink-muted)" strokeDasharray="3 3" />}
      </svg>
      {hover != null && (
        <div className="tabular pointer-events-none absolute top-0 right-0 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-2.5 py-1.5 text-[12px] text-[var(--ink)] shadow-lg">
          <div className="font-medium">{shortDate(dates[hover])}</div>
          {lines.map((l) => (
            <div key={l.label} className="flex items-center gap-1.5">
              <span className="size-2 rounded-full" style={{ background: l.color }} />{l.label}: {fmt(l.values[hover], 1)}{unit}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
